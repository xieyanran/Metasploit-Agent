"""记忆提取（Memory Extraction）

对应 docs/DESIGN.md "Memory Extraction -> 最终方案" 的落地实现：
1. Working memory：自动直写，不经过LLM，也不需要等Agent主动调用memory工具，
   由每次工具调用的Action+Observation无条件写入。
2. Episodic memory：事件触发的"触发"本身也交给LLM判断——每次工具结果异步调用
   一次LLM，由LLM判断是否构成一个值得记录的事件、属于哪种event_type/outcome，
   并给出摘要；不阻塞agent下一步动作；ADD-only，不覆盖旧记录。
3. Semantic memory：PTES阶段边界触发，对该阶段积累的episodic memory做一次
   归纳提炼；engagement结束时兜底再跑一次。
4. Perceptual memory："证据到达即处理"已在 PerceptualMemory.add() 中实现，
   不需要额外的触发层。

MemoryExtractor 只负责"什么时候写、写什么"，真正的存储/检索仍由
MemoryManager 及各 MemoryType 实现负责。
"""
from __future__ import annotations

import json
import logging
import math
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List, Optional

from core.llm import PentestAgentLLM

from .manager import MemoryManager
from .maintenance import SemanticMemoryMaintainer

logger = logging.getLogger(__name__)

# 与 MemoryManager.EPISODIC_EVENT_TYPES / outcome 枚举对齐，用于校验LLM返回的分类是否合法
_EPISODIC_EVENT_TYPES = (
    "asset_discovery", "credential_found", "exploit_attempt", "recon_negative",
    "defense_observed", "privesc_lateral_move", "osint_finding", "scope_directive",
)
_EPISODIC_OUTCOMES = ("success", "tech_fail", "op_fail", "negative")

_CVE_PATTERN = re.compile(r"CVE-\d{4}-\d{4,7}", re.IGNORECASE)

# 异步归档共用一个小线程池，避免每次触发都新开线程；不影响agent主循环
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="memory-extract")

_EPISODIC_JUDGE_PROMPT = """你是渗透测试记忆归档助手。下面是一次工具调用的名称和输出结果，请判断这条结果\
是否构成一个值得写入episodic memory（渗透测试情景记忆）的事件。

只有以下情况才算事件：
- 发现新的资产/端口/服务（event_type=asset_discovery）
- 发现新的凭据/密钥（event_type=credential_found）
- 一次利用尝试及其结果（event_type=exploit_attempt），outcome需要区分：
  - success：确认拿到了session/权限
  - tech_fail：漏洞不存在/已修复等目标本身的技术性原因导致失败
  - op_fail：网络不通/RPC超时/参数错误等操作性原因导致失败，不代表目标不可利用
- 侦察阶段明确的阴性结果，如未发现开放端口、模块不适用（event_type=recon_negative, outcome=negative）
- 发现防御机制，如IDS/IPS/WAF/AV拦截（event_type=defense_observed）
- 权限提升或横向移动的关键节点（event_type=privesc_lateral_move）
- 被动情报/OSINT发现（event_type=osint_finding）
- 客户scope/限制条件的说明（event_type=scope_directive）

如果只是过程性、无实质信息量的输出（例如常规状态回显、与上述情形无关的报错），不算事件。

本次调用是否成功（仅供参考，最终以输出内容为准）：{tool_success}
工具: {tool_name}
输出:
{output_text}

只输出一个JSON对象，不要输出任何其他文字、不要用markdown代码块包裹：
{{"should_store": true或false, "event_type": "...", "outcome": "...", "summary": "一句话总结这条结果对目标资产/凭据/漏洞点有意义的事实，不要复述工具调用过程"}}
should_store为false时，其他字段可以省略。"""


def _parse_json_object(text: str) -> Optional[Dict[str, Any]]:
    """解析LLM返回的JSON对象，容忍```json代码块包裹；解析失败返回None（fail-closed）"""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = re.sub(r"^json\s*", "", text, flags=re.IGNORECASE).strip()
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    return obj if isinstance(obj, dict) else None


class MemoryExtractor:
    """事件触发的episodic抽取 + 阶段边界触发的semantic归纳"""

    def __init__(
        self,
        memory_manager: MemoryManager,
        llm: Optional[PentestAgentLLM] = None,
        engagement_id: Optional[str] = None,
    ):
        self.memory_manager = memory_manager
        self.llm = llm
        self.engagement_id = engagement_id
        # 已归纳进semantic的episodic id，避免engagement结束兜底时重复归纳同一批记录
        self._consolidated_episode_ids: set[str] = set()
        # 阶段归纳产出新semantic记忆后，交给它做去重/矛盾检测（见 maintenance.py）
        self._semantic_maintainer = SemanticMemoryMaintainer(memory_manager, llm)

    # ---------------- Working: 自动直写 ----------------

    def log_working_memory(self, tool_name: str, parameters: str, output: str) -> None:
        """
        把每次工具调用的Action+Observation自动写入working memory
        不记录MemoryTool自我调用
        """
        if tool_name == "memory":
            return
        try:
            content = f"[{tool_name}] params={parameters} -> {output[:2000]}"
            self.memory_manager.add_memory(
                content=content,
                memory_type="working",
                auto_classify=False,
                metadata={"tool": tool_name, "parameters": parameters, "auto_logged": True},
            )
        except Exception as e:
            logger.warning(f"working memory自动写入失败（不影响工具执行）: {e}")

    # ---------------- Episodic: 事件触发 + 异步摘要归档 ----------------

    def maybe_extract_episodic(
        self,
        tool_name: str,
        output_text: str,
        tool_success: bool,
        target_ref: Optional[str],
        phase: str,
        session_id: Optional[str] = None,
    ) -> None:
        """结构性门槛过滤后异步提交：memory工具自身、没有target_ref时不产出episodic
        （episodic强绑定target，DESIGN.md: is_target_bound=True时target_ref必填）。
        """
        if tool_name == "memory":
            return
        if not target_ref:
            return

        _executor.submit(
            self._extract_episodic_job,
            tool_name, output_text, tool_success, target_ref, phase, session_id,
        )

    def _extract_episodic_job(
        self,
        tool_name: str,
        output_text: str,
        tool_success: bool,
        target_ref: Optional[str],
        phase: str,
        session_id: Optional[str],
    ) -> None:
        try:
            judgment = self._judge_episodic_event(tool_name, output_text, tool_success)
            if judgment is None:
                # LLM判断这不是一次值得记录的事件（或判断失败），直接丢弃，不落库
                # 还有work memory兜底
                return

            metadata = {
                "is_target_bound": True,
                "target_ref": target_ref,
                "event_type": judgment["event_type"],
                "outcome": judgment["outcome"],
                "phase": phase,
                "engagement_id": self.engagement_id,
            }
            if session_id:
                metadata["session_id"] = session_id
            # ADD-only
            self.memory_manager.add_memory(
                content=judgment["summary"],
                memory_type="episodic",
                metadata=metadata,
                auto_classify=True,
            )
        except Exception as e:
            logger.warning(f"episodic记忆异步抽取失败（不影响主流程）: {e}")

    def _judge_episodic_event(
        self, tool_name: str, output_text: str, tool_success: bool
    ) -> Optional[Dict[str, str]]:
        """
        调用LLM判断这次工具结果是否构成episodic事件，返回{event_type, outcome, summary}；
        不构成事件、没有配置LLM、或LLM返回格式不合法时统一返回None（fail-closed，
        宁可漏记也不写入未经校验的垃圾记录）
        """
        if self.llm is None:
            return None

        prompt = _EPISODIC_JUDGE_PROMPT.format(
            tool_success="成功" if tool_success else "失败",
            tool_name=tool_name,
            output_text=output_text[:1500],
        )
        try:
            response = self.llm.invoke([
                {"role": "system", "content": "你是一名渗透测试记忆归档助手，只输出要求的JSON，不要有多余文字。"},
                {"role": "user", "content": prompt},
            ])
            data = _parse_json_object(response.content or "")
        except Exception as e:
            logger.warning(f"episodic事件LLM判断调用失败，跳过本次记录: {e}")
            return None

        if not data or not data.get("should_store"):
            return None

        event_type = data.get("event_type")
        outcome = data.get("outcome")
        summary = (data.get("summary") or "").strip()
        if event_type not in _EPISODIC_EVENT_TYPES or outcome not in _EPISODIC_OUTCOMES or not summary:
            logger.warning(f"episodic事件LLM判断返回格式不合法，跳过: {data}")
            return None

        return {"event_type": event_type, "outcome": outcome, "summary": summary}

    # ---------------- Semantic: 阶段边界触发 + 归纳提炼 ----------------

    def consolidate_phase_async(self, phase: str, target_ref: Optional[str]) -> None:
        """PTES阶段边界触发：对该阶段积累的episodic memory做一次归纳提炼，异步执行"""
        _executor.submit(self._consolidate_phase_job, phase, target_ref)

    def _consolidate_phase_job(self, phase: str, target_ref: Optional[str]) -> None:
        try:
            episodic = self.memory_manager.memory_types.get("episodic")
            if episodic is None:
                return

            candidates = [
                m for m in episodic.get_all()
                if m.id not in self._consolidated_episode_ids
                and m.metadata.get("phase") == phase
                and (target_ref is None or m.metadata.get("target_ref") == target_ref)
            ]
            if not candidates:
                return

            # 需不需要拼接其他字段内容
            joined = "\n".join(
                f"- [{m.metadata.get('event_type')}/{m.metadata.get('outcome')}] {m.content}"
                for m in candidates
            )
            summary = self._summarize(
                joined,
                instruction=(
                    "以上是本次渗透测试某一阶段积累的多条具体事件记录。请归纳出1-3条脱离具体目标后"
                    "仍然成立、可跨目标复用的经验规则（例如某类exploit的适用边界、某种防御的规避技巧）。"
                    "每条一行，只写结论本身，不要编号、不要解释。"
                ),
            )

            # 这样extract entities合理吗
            entities = sorted(set(_CVE_PATTERN.findall(joined)))
            derived_from = [m.id for m in candidates]
            # confidence回答"这条知识有多可信"：由归纳所依据的episodic样本数估计，
            # 样本越多越可信，但边际递减（1条样本约0.3，10条样本约0.65）
            confidence = round(min(1.0, 0.3 + 0.15 * math.log1p(len(candidates))), 3)

            new_ids = []
            for line in [l.strip("-• \t") for l in summary.splitlines() if l.strip()]:
                memory_id = self.memory_manager.add_memory(
                    content=line,
                    memory_type="semantic",
                    metadata={
                        "is_target_bound": False,
                        "event_type": "pattern_insight",
                        "entities": entities,
                        "derived_from": derived_from,
                        "confidence": confidence,
                        "engagement_id": self.engagement_id,
                    },
                    auto_classify=True,
                )
                new_ids.append(memory_id)

            self._consolidated_episode_ids.update(derived_from)
            if new_ids:
                self._semantic_maintainer.maintain(new_ids)
        except Exception as e:
            logger.warning(f"semantic记忆阶段归纳失败（不影响主流程）: {e}")

    def finalize_engagement(self, phases: List[str], target_ref: Optional[str]) -> None:
        """engagement结束时的兜底：确保每个PTES阶段积累的episodic memory都至少归纳过一次"""
        for phase in phases:
            self.consolidate_phase_async(phase, target_ref)

    # ---------------- 内部工具 ----------------

    def _summarize(self, text: str, instruction: str) -> str:
        """调用LLM做摘要/归纳；没有配置LLM时退化为截断原文，保证提取流程不因缺少LLM而中断"""
        if self.llm is None:
            return text[:200]
        try:
            response = self.llm.invoke([
                {"role": "system", "content": "你是一名渗透测试记忆归档助手，只输出要求的内容，不要多余解释。"},
                {"role": "user", "content": f"{instruction}\n\n{text}"},
            ])
            return (response.content or "").strip() or text[:200]
        except Exception as e:
            logger.warning(f"LLM摘要调用失败，回退为截断原文: {e}")
            return text[:200]
