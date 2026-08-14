"""ContextBuilder - GSSC流水线实现

实现 Gather-Select-Structure-Compress 上下文构建流程：
1. Gather: 从多源收集候选信息（历史、记忆、RAG、工具结果）
2. Select: 基于优先级、相关性、多样性筛选
3. Structure: 组织成结构化上下文模板
4. Compress: 在预算内压缩与规范化
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import json
import re
import tiktoken
import math

from core.message import Message
from core.llm import PentestAgentLLM
from tools.builtin.memory_tool import MemoryTool
# RAG系统本项目暂不引入（见 docs/DESIGN.md「Retrieval-Augmented Generation Design」，
# 仍在未来拓展开发中）。下方 rag_tool 相关接线整体注释保留，需要启用时取消注释即可，
# 届时 tools/builtin/rag_tool.py（目前是空文件）也需要先实现 RAGTool。
from agent.state import AgentState
from agent.models import ToolResult

# episodic的phase/event_type结构化收窄条件必须是这两个已知枚举的子集（见docs/DESIGN.md
# 「Memory taxonomy」/「Episodic Memory判断」），LLM判定结果里出现枚举外的值一律丢弃该字段，
# 不影响其余已校验通过的字段
_KNOWN_PHASES = {"recon", "vuln_analysis", "exploitation", "post_exploitation"}
_KNOWN_EVENT_TYPES = {
    "asset_discovery", "credential_found", "exploit_attempt", "recon_negative",
    "defense_observed", "privesc_lateral_move", "osint_finding", "scope_directive",
}


@dataclass
class ContextPacket:
    """上下文信息包"""
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    token_count: int = 0
    relevance_score: float = 0.0  # 0.0-1.0
    
    def __post_init__(self):
        """自动计算token数"""
        if self.token_count == 0:
            self.token_count = count_tokens(self.content)


@dataclass
class ContextConfig:
    """上下文构建配置"""
    max_tokens: int = 8000  # 总预算
    reserve_ratio: float = 0.15  # 生成余量（10-20%）
    min_relevance: float = 0.3  # 最小相关性阈值
    enable_mmr: bool = True  # 启用最大边际相关性（多样性）
    mmr_lambda: float = 0.7  # MMR平衡参数（0=纯多样性, 1=纯相关性）
    system_prompt_template: str = ""  # 系统提示模板
    enable_compression: bool = True  # 启用压缩
    
    def get_available_tokens(self) -> int:
        """获取可用token预算（扣除余量）"""
        return int(self.max_tokens * (1 - self.reserve_ratio))


class ContextBuilder:
    """上下文构建器 - GSSC流水线
    
    用法示例：
    ```python
    builder = ContextBuilder(
        memory_tool=memory_tool,
        # rag_tool=rag_tool,  # RAG本项目暂不引入，见__init__
        config=ContextConfig(max_tokens=8000)
    )
    
    context = builder.build(
        user_query="用户问题",
        conversation_history=[...],
        system_instructions="系统指令"
    )
    ```
    """
    
    def __init__(
        self,
        memory_tool: Optional[MemoryTool] = None,
        # rag_tool: Optional[Any] = None,  # RAG本项目暂不引入，见文件头注释；启用时取消注释
        config: Optional[ContextConfig] = None,
        llm: Optional[PentestAgentLLM] = None
    ):
        self.memory_tool = memory_tool
        # self.rag_tool = rag_tool  # 同上，随构造参数一并禁用
        self.config = config or ContextConfig()
        self._encoding = tiktoken.get_encoding("cl100k_base")
        # 可选：用于"先查semantic、再由LLM判断episodic结构化收窄参数"这一步
        # （见_decide_episodic_params）。不提供时该判断步骤跳过，退化为纯代码逻辑兜底
        self.llm = llm
    
    def build(
        self,
        user_query: str,
        state: Optional[AgentState] = None,
        engagement_id: Optional[str] = None,
        conversation_history: Optional[List[Message]] = None,
        system_instructions: Optional[str] = None,
        additional_packets: Optional[List[ContextPacket]] = None
    ) -> str:
        """构建完整上下文

        Args:
            user_query: 用户查询
            state: 当前AgentState，用于提取target_ref/phase以收窄episodic记忆检索
            engagement_id: 当前engagement标识，episodic记忆检索的唯一边界（不传则跳过episodic检索）
            conversation_history: 对话历史
            system_instructions: 系统指令
            additional_packets: 额外的上下文包

        Returns:
            结构化上下文字符串
        """
        # 1. Gather: 收集候选信息
        packets = self._gather(
            user_query=user_query,
            state=state,
            engagement_id=engagement_id,
            conversation_history=conversation_history or [],
            system_instructions=system_instructions,
            additional_packets=additional_packets or []
        )
        
        # 2. Select: 筛选与排序
        selected_packets = self._select(packets, user_query)
        
        # 3. Structure: 组织成结构化模板
        structured_context = self._structure(
            selected_packets=selected_packets,
            user_query=user_query,
            system_instructions=system_instructions
        )
        
        # 4. Compress: 压缩与规范化（如果超预算）
        final_context = self._compress(structured_context)
        
        return final_context
    
    def _gather(
        self,
        user_query: str,
        state: Optional[AgentState],
        engagement_id: Optional[str],
        conversation_history: List[Message],
        system_instructions: Optional[str],
        additional_packets: List[ContextPacket]
    ) -> List[ContextPacket]:
        """Gather: 收集候选信息"""
        packets = []

        # P0: 系统指令（强约束）
        if system_instructions:
            packets.append(ContextPacket(
                content=system_instructions,
                metadata={"type": "instructions"}
            ))

        # P1: 从记忆中获取任务状态与关键结论
        if self.memory_tool:
            effective_state = state if state is not None else AgentState()
            target_ref = state.target.address if (state and state.target) else None
            phase = state.ptes_phase if state else None

            try:
                # semantic先行：与当前查询相关的可迁移知识（自由文本；融合排序与disputed
                # 过滤已在memory/types/semantic.py的检索层实现）。按docs/DESIGN.md「Episodic
                # Memory 检索策略」的设计，episodic的结构化收窄参数要基于这里的检索结果
                # 判断，所以semantic必须先跑完，episodic分支在它后面
                semantic_result = None
                semantic_has_results = False
                if user_query and user_query.strip():
                    semantic_result = self.memory_tool.execute(
                        effective_state, action="search",
                        memory_type="semantic", query=user_query, limit=5
                    )
                    semantic_has_results = _memory_search_has_results(semantic_result)
                    if semantic_has_results:
                        packets.append(ContextPacket(
                            content=semantic_result.output,
                            metadata={"type": "related_memory", "source": "semantic"}
                        ))

                # episodic：本engagement下的结构化任务状态与结论。engagement_id是
                # episodic检索唯一的安全边界，缺失则跳过整个分支，不做无边界搜索——这条
                # 硬约束不受下面"LLM判断"影响：LLM只负责判断target_ref/phase/event_type/
                # query这些收窄条件，engagement_id永远来自调用方传入的可信参数
                if engagement_id:
                    semantic_context = semantic_result.output if semantic_has_results else ""
                    decision = self._decide_episodic_params(
                        user_query=user_query,
                        semantic_context=semantic_context,
                        default_target_ref=target_ref,
                        default_phase=phase,
                    )
                    if decision["should_query"]:
                        episodic_kwargs: Dict[str, Any] = {
                            "memory_type": "episodic",
                            "engagement_id": engagement_id,
                            "min_importance": 0.5,
                            "limit": 5,
                        }
                        if decision.get("target_ref"):
                            episodic_kwargs["target_ref"] = decision["target_ref"]
                        if decision.get("phase"):
                            episodic_kwargs["phase"] = decision["phase"]
                        if decision.get("event_type"):
                            episodic_kwargs["event_type"] = decision["event_type"]
                        if decision.get("query"):
                            episodic_kwargs["query"] = decision["query"]
                        episodic_result = self.memory_tool.execute(
                            effective_state, action="search", **episodic_kwargs
                        )
                        if _memory_search_has_results(episodic_result):
                            packets.append(ContextPacket(
                                content=episodic_result.output,
                                metadata={"type": "task_state", "source": "episodic", "importance": "high"}
                            ))

                # working：本session内最近几次工具调用的Action+Observation。这类记忆
                # 自动直写、不经LLM筛选重要性（见memory/extraction.py:log_working_memory），
                # 内容是未经压缩的原始工具输出，所以limit刻意设得比episodic/semantic小，
                # 只取最近几条，避免把token预算和信噪比拖垮——不设min_importance阈值，
                # 因为写入时本就没有有意义的重要性区分，靠retrieve()自身的新近性排序即可
                working_result = self.memory_tool.execute(
                    effective_state, action="search",
                    memory_type="working", query=user_query, limit=3
                )
                if _memory_search_has_results(working_result):
                    packets.append(ContextPacket(
                        content=working_result.output,
                        metadata={"type": "recent_actions", "source": "working"}
                    ))
            except Exception as e:
                print(f"⚠️ 记忆检索失败: {e}")

        # P2: 从RAG中获取事实证据 —— RAG本项目暂不引入，整块注释保留，
        # 启用时需同步取消__init__里rag_tool参数/属性的注释
        # if self.rag_tool:
        #     try:
        #         rag_results = self.rag_tool.run({
        #             "action": "search",
        #             "query": user_query,
        #             "limit": 5
        #         })
        #         if rag_results and "未找到" not in rag_results and "错误" not in rag_results:
        #             packets.append(ContextPacket(
        #                 content=rag_results,
        #                 metadata={"type": "knowledge_base"}
        #             ))
        #     except Exception as e:
        #         print(f"⚠️ RAG检索失败: {e}")
        
        # P3: 对话历史（辅助材料）
        if conversation_history:
            # 只保留最近N条
            recent_history = conversation_history[-10:]
            history_text = "\n".join([
                f"[{msg.role}] {msg.content}"
                for msg in recent_history
            ])
            packets.append(ContextPacket(
                content=history_text,
                metadata={"type": "history", "count": len(recent_history)}
            ))
        
        # 添加额外包
        packets.extend(additional_packets)

        return packets

    def _decide_episodic_params(
        self,
        user_query: str,
        semantic_context: str,
        default_target_ref: Optional[str],
        default_phase: Optional[str],
    ) -> Dict[str, Any]:
        """基于semantic检索结果，让LLM判断episodic的结构化收窄参数。

        对齐docs/DESIGN.md「Episodic Memory 检索策略」："LLM先查询Semantic（联想相似
        情境/经验，思考可能的攻击链）→ 基于此LLM再判断具体metadata参数作SQL查询"。

        engagement_id不在这里决定——它是episodic唯一的安全边界，永远由调用方传入的
        可信参数提供，这个判断结果只负责target_ref/phase/event_type/query这些收窄条件。

        Returns:
            dict，恒含 should_query(bool)；可能含 target_ref/phase/event_type/query。
            self.llm未提供、调用异常、响应解析失败，都返回兜底dict而不抛出，让episodic
            分支退化为此前"直接用当前state"的确定性行为，不会比没有这个判断步骤更差。
        """
        fallback: Dict[str, Any] = {
            "should_query": True,
            "target_ref": default_target_ref,
            "phase": default_phase,
            "event_type": None,
            "query": None,
        }
        if not self.llm:
            return fallback

        prompt = (
            "你是渗透测试Agent的记忆检索助手。以下是当前任务和已检索到的语义经验，"
            "请判断本轮是否需要查询episodic memory（记录某次engagement内实际发生过的"
            "具体事件），以及应该用什么结构化条件收窄查询。\n\n"
            f"当前任务：{user_query}\n\n"
            f"语义经验检索结果：\n{semantic_context or '（无相关语义经验）'}\n\n"
            f"当前已知的默认target/phase（仅供参考，可沿用也可按语义经验判断换成其他值）：\n"
            f"target_ref={default_target_ref or '未知'}, phase={default_phase or '未知'}\n\n"
            "只输出一段JSON，不要输出任何其他文字，字段如下：\n"
            "{\n"
            '  "should_query": true/false,  // 本轮是否需要查episodic\n'
            '  "target_ref": "字符串或null",  // 要收窄到的目标host/IP，不确定就沿用默认值\n'
            '  "phase": "recon/vuln_analysis/exploitation/post_exploitation之一，或null",\n'
            '  "event_type": ["asset_discovery/credential_found/exploit_attempt/'
            'recon_negative/defense_observed/privesc_lateral_move/osint_finding/'
            'scope_directive中的0个或多个"],\n'
            '  "query": "子串关键词，如CVE编号/服务版本号，或null"\n'
            "}"
        )

        try:
            response = self.llm.invoke(
                [{"role": "user", "content": prompt}],
                temperature=0, max_tokens=200,
            )
            decision = _parse_episodic_decision(response.content)
            if decision is None:
                return fallback
            # 缺省字段用默认值兜底（而非留空）——尤其target_ref/phase，避免LLM只回答了
            # should_query却漏写其他字段时，退化成完全不收窄的宽查询。用setdefault而不是
            # 直接赋值：LLM显式给出null是"判断后决定不按此维度收窄"，要尊重这个决定，
            # 只有键完全缺失才视为"没回答"而回退到默认值
            decision.setdefault("target_ref", default_target_ref)
            decision.setdefault("phase", default_phase)
            return decision
        except Exception:
            return fallback

    def _select(
        self,
        packets: List[ContextPacket],
        user_query: str
    ) -> List[ContextPacket]:
        """Select: 基于分数与预算的筛选"""
        # 1) 计算相关性（关键词重叠）
        query_tokens = set(user_query.lower().split())
        for packet in packets:
            content_tokens = set(packet.content.lower().split())
            if len(query_tokens) > 0:
                overlap = len(query_tokens & content_tokens)
                packet.relevance_score = overlap / len(query_tokens)
            else:
                packet.relevance_score = 0.0
        
        # 2) 计算新近性（指数衰减）
        def recency_score(ts: datetime) -> float:
            delta = max((datetime.now() - ts).total_seconds(), 0)
            tau = 3600  # 1小时时间尺度，可暴露到配置
            return math.exp(-delta / tau)
        
        # 3) 计算复合分：0.7*相关性 + 0.3*新近性
        scored_packets: List[Tuple[float, ContextPacket]] = []
        for p in packets:
            rec = recency_score(p.timestamp)
            score = 0.7 * p.relevance_score + 0.3 * rec
            scored_packets.append((score, p))
        
        # 4) 系统指令 + episodic任务状态 + working最近动作：固定纳入，不受min_relevance过滤。
        # task_state/recent_actions都是结构化事件记录/原始工具输出，和自然语言user_query
        # 字面重叠通常很低，若仍走min_relevance过滤几乎总会被丢弃，等于让P1这层形同虚设。
        # related_memory（semantic）不在此列，仍按relevance参与筛选——语义记忆
        # 本就该按与当前问题的相关度取舍。
        ALWAYS_INCLUDE_TYPES = {"instructions", "task_state", "recent_actions"}
        priority_packets = [p for (_, p) in scored_packets if p.metadata.get("type") in ALWAYS_INCLUDE_TYPES]
        remaining = [p for (s, p) in sorted(scored_packets, key=lambda x: x[0], reverse=True)
                     if p.metadata.get("type") not in ALWAYS_INCLUDE_TYPES]

        # 5) 依据 min_relevance 过滤（对非优先包）
        filtered = [p for p in remaining if p.relevance_score >= self.config.min_relevance]

        # 6) 按预算填充
        available_tokens = self.config.get_available_tokens()
        selected: List[ContextPacket] = []
        used_tokens = 0

        # 先放入优先包（不排序）
        for p in priority_packets:
            if used_tokens + p.token_count <= available_tokens:
                selected.append(p)
                used_tokens += p.token_count
        
        # 再按分数加入其余
        for p in filtered:
            if used_tokens + p.token_count > available_tokens:
                continue
            selected.append(p)
            used_tokens += p.token_count
        
        return selected
    
    def _structure(
        self,
        selected_packets: List[ContextPacket],
        user_query: str,
        system_instructions: Optional[str]
    ) -> str:
        """Structure: 组织成结构化上下文模板"""
        sections = []
        
        # [Role & Policies] - 系统指令
        p0_packets = [p for p in selected_packets if p.metadata.get("type") == "instructions"]
        if p0_packets:
            role_section = "[Role & Policies]\n"
            role_section += "\n".join([p.content for p in p0_packets])
            sections.append(role_section)
        
        # [Task] - 当前任务
        sections.append(f"[Task]\n用户问题：{user_query}")
        
        # [State] - 任务状态（episodic的关键结论 + working的最近动作，来源不同分开标注）
        p1_task_packets = [p for p in selected_packets if p.metadata.get("type") == "task_state"]
        p1_action_packets = [p for p in selected_packets if p.metadata.get("type") == "recent_actions"]
        if p1_task_packets or p1_action_packets:
            state_lines = ["[State]"]
            if p1_task_packets:
                state_lines.append("关键进展与未决问题：")
                state_lines.extend(p.content for p in p1_task_packets)
            if p1_action_packets:
                state_lines.append("最近执行的动作（避免短期内重复）：")
                state_lines.extend(p.content for p in p1_action_packets)
            sections.append("\n".join(state_lines))
        
        # [Evidence] - 事实证据
        p2_packets = [
            p for p in selected_packets
            if p.metadata.get("type") in {"related_memory", "knowledge_base", "retrieval", "tool_result"}
        ]
        if p2_packets:
            evidence_section = "[Evidence]\n事实与引用：\n"
            for p in p2_packets:
                evidence_section += f"\n{p.content}\n"
            sections.append(evidence_section)
        
        # [Context] - 辅助材料（历史等）
        p3_packets = [p for p in selected_packets if p.metadata.get("type") == "history"]
        if p3_packets:
            context_section = "[Context]\n对话历史与背景：\n"
            context_section += "\n".join([p.content for p in p3_packets])
            sections.append(context_section)
        
        # [Output] - 输出约束
        output_section = """[Output]
                            请按以下格式回答：
                            1. 结论（简洁明确）
                            2. 依据（列出支撑证据及来源）
                            3. 风险与假设（如有）
                            4. 下一步行动建议（如适用）"""
        sections.append(output_section)
        
        return "\n\n".join(sections)
    
    def _compress(self, context: str) -> str:
        """Compress: 压缩与规范化"""
        if not self.config.enable_compression:
            return context
        
        current_tokens = count_tokens(context)
        available_tokens = self.config.get_available_tokens()
        
        if current_tokens <= available_tokens:
            return context
        
        # 简单截断策略（保留前N个token）
        # 实际应用中可用LLM做高保真摘要
        print(f"⚠️ 上下文超预算 ({current_tokens} > {available_tokens})，执行截断")
        
        # 按段落截断，保留结构
        lines = context.split("\n")
        compressed_lines = []
        used_tokens = 0
        
        for line in lines:
            line_tokens = count_tokens(line)
            if used_tokens + line_tokens > available_tokens:
                break
            compressed_lines.append(line)
            used_tokens += line_tokens
        
        return "\n".join(compressed_lines)


def _memory_search_has_results(result: ToolResult) -> bool:
    """判断memory_tool的search调用是否真的命中了记忆。

    ToolResult.success只代表"调用没有内部报错"——未命中时_search_memory仍返回
    success=True，但output是"🔍 未找到..."提示语，因此需要额外判断output内容。
    """
    return bool(result and result.success and result.output and "未找到" not in str(result.output))


def _parse_episodic_decision(text: str) -> Optional[Dict[str, Any]]:
    """从LLM文本响应里提取episodic查询决策JSON，校验phase/event_type枚举取值。

    LLM输出不保证是纯JSON（可能带代码块围栏或额外说明文字），所以先尝试整体解析，
    失败再退化为正则提取最外层花括号内容重试；两次都失败或类型不对，返回None交给
    调用方（_decide_episodic_params）走兜底，而不是让一个格式问题打断整个检索流程。
    """
    if not text:
        return None

    candidate = text.strip()
    try:
        decision = json.loads(candidate)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if not match:
            return None
        try:
            decision = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    if not isinstance(decision, dict):
        return None

    result: Dict[str, Any] = {"should_query": bool(decision.get("should_query", True))}

    if "target_ref" in decision:
        result["target_ref"] = decision["target_ref"] or None

    if "phase" in decision:
        phase = decision["phase"]
        result["phase"] = phase if phase in _KNOWN_PHASES else None

    if "event_type" in decision:
        raw_events = decision["event_type"]
        if isinstance(raw_events, str):
            raw_events = [raw_events]
        if isinstance(raw_events, list):
            filtered = [e for e in raw_events if e in _KNOWN_EVENT_TYPES]
            result["event_type"] = filtered or None
        else:
            result["event_type"] = None

    if "query" in decision:
        result["query"] = decision["query"] or None

    return result


def count_tokens(text: str) -> int:
    """计算文本token数（使用tiktoken）"""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # 降级方案：粗略估算（1 token ≈ 4 字符）
        return len(text) // 4

