"""语义记忆维护（Semantic Memory Maintenance）

候选生成拆成两条独立通路，不共用同一个相似度阈值：
- 去重候选：SemanticMemory.find_similar()，向量相似度衡量"是否在换个说法讲同一个
  结论"，适合筛去重候选。
- 矛盾候选：SemanticMemory.find_related_by_entities()，基于知识图谱的共享实体，
  衡量"是否在讨论同一个实体"，与措辞是否相似无关。两条结论相反的陈述往往共享几乎
  全部实体和句式（只在结论/否定词上不同），向量相似度反而可能很高甚至判定为"近似
  重复"而被直接合并——所以矛盾候选不能靠向量相似度筛，必须走图谱这条独立通路。

两类候选合并去重后，统一交给LLM判断关系（duplicate/contradiction/complementary/
unrelated），不做任何"相似度高到一定程度就跳过LLM直接合并"的快速路径——这类捷径
正是矛盾候选可能被向量相似度分数误判为重复的来源。矛盾且LLM也判断不出哪条更可信
时，只标记disputed，不做不可逆删除，留给定期人工审查处理。

本模块只负责"何时合并/何时标记矛盾"的裁决逻辑，真正的合并/标记/存储操作由
SemanticMemory（memory/types/semantic.py）的 merge_memories/mark_disputed 等
方法实现。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from core.llm import PentestAgentLLM
from memory.types.semantic import SemanticMemory
from memory.base import MemoryItem

from .manager import MemoryManager

logger = logging.getLogger(__name__)

# 向量相似度低于此值时，认为和该记忆过于不相关，不值得送一次LLM判断
# 只作为去重候选的入场门槛；矛盾候选走find_related_by_entities，不受此阈值约束
_SEMANTIC_CANDIDATE_THRESHOLD = 0.75

_CONTRADICTION_JUDGE_PROMPT = """你是渗透测试知识库的一致性审核助手。下面两条语义记忆（从过往渗透经验中归纳出的\
可复用规则）被判定为可能相关（措辞相似，或讨论同一实体），请判断二者的关系。

记忆A（confidence={confidence_a}）：{content_a}
记忆B（confidence={confidence_b}）：{content_b}

判断标准：
- duplicate：两条陈述的是同一件事，只是措辞不同
- contradiction：两条陈述在同一前提下给出了互斥的结论（例如同一exploit对同一场景一个说有效一个说无效）
- complementary：两条陈述相关但互不冲突，各自成立，都值得保留
- unrelated：只是主题相关，实际内容并不冲突也不重复

只有relation=contradiction时才需要给出resolution：
- 优先信任confidence更高的一条；confidence相近、无法判断哪条更可信时，输出undecided，不要臆断

只输出一个JSON对象，不要输出任何其他文字、不要用markdown代码块包裹：
{{"relation": "duplicate/contradiction/complementary/unrelated", "resolution": "keep_a/keep_b/undecided", "reason": "一句话说明理由"}}
relation不是contradiction时，resolution可以省略。"""


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


class SemanticMemoryMaintainer:
    """对新生成的semantic memory做去重与矛盾检测"""

    def __init__(self, memory_manager: MemoryManager, llm: Optional[PentestAgentLLM] = None):
        self.memory_manager = memory_manager
        self.llm = llm

    def maintain(self, new_memory_ids: List[str]) -> None:
        """对本轮新生成的semantic memory逐条做去重/矛盾检测"""
        semantic = self.memory_manager.memory_types.get("semantic")
        if semantic is None:
            return

        for memory_id in new_memory_ids:
            try:
                self._maintain_one(semantic, memory_id)
            except Exception as e:
                logger.warning(f"semantic记忆维护失败（不影响主流程）: {e}")

    def _maintain_one(self, semantic: SemanticMemory, memory_id: str) -> None:
        candidate_ids = self._gather_candidate_ids(semantic, memory_id)

        for candidate_id in candidate_ids:
            # memory/candidate都可能在循环中途被前一轮裁决合并/删除掉，实时重新读取
            memory = semantic.get_memory(memory_id)
            if memory is None:
                return  # 当前条目已被吸收/删除，无需继续比较剩余候选

            if candidate_id == memory_id:
                continue
            candidate = semantic.get_memory(candidate_id)
            if candidate is None:
                continue  # 候选已在本轮更早的裁决中被合并/删除

            self._judge_and_resolve_contradiction(semantic, memory, candidate)

    @staticmethod
    def _gather_candidate_ids(semantic: SemanticMemory, memory_id: str) -> List[str]:
        """合并两条独立候选来源的id列表（保序去重）：向量近邻负责去重候选，
        实体图谱负责矛盾候选，二者互补而非互斥（见模块docstring）"""
        seen = set()
        candidate_ids: List[str] = []

        for candidate, score in semantic.find_similar(memory_id, top_k=5):
            if score >= _SEMANTIC_CANDIDATE_THRESHOLD and candidate.id not in seen:
                seen.add(candidate.id)
                candidate_ids.append(candidate.id)

        for candidate in semantic.find_related_by_entities(memory_id, limit=5):
            if candidate.id not in seen:
                seen.add(candidate.id)
                candidate_ids.append(candidate.id)

        return candidate_ids

    @staticmethod
    def _pick_keep_and_absorb(memory_a: MemoryItem, memory_b: MemoryItem) -> Tuple[MemoryItem, MemoryItem]:
        """两条记忆判定为重复/矛盾且需要二选一时，优先保留confidence更高的一条"""
        confidence_a = memory_a.metadata.get("confidence") or 0.0
        confidence_b = memory_b.metadata.get("confidence") or 0.0
        return (memory_a, memory_b) if confidence_a >= confidence_b else (memory_b, memory_a)

    def _judge_and_resolve_contradiction(
        self, semantic: SemanticMemory, memory_a: MemoryItem, memory_b: MemoryItem
    ) -> None:
        """LLM判断两条话题相关的语义记忆是重复/矛盾/互补/无关，并按判断结果裁决"""
        if self.llm is None:
            return

        prompt = _CONTRADICTION_JUDGE_PROMPT.format(
            confidence_a=memory_a.metadata.get("confidence", "unknown"),
            content_a=memory_a.content,
            confidence_b=memory_b.metadata.get("confidence", "unknown"),
            content_b=memory_b.content,
        )
        try:
            response = self.llm.invoke([
                {"role": "system", "content": "你是一名渗透测试知识库审核助手，只输出要求的JSON，不要有多余文字。"},
                {"role": "user", "content": prompt},
            ])
            data = _parse_json_object(response.content or "")
        except Exception as e:
            logger.warning(f"矛盾检测LLM调用失败，跳过本次判断: {e}")
            return

        if not data:
            return

        relation = data.get("relation")
        if relation == "duplicate":
            keep, absorb = self._pick_keep_and_absorb(memory_a, memory_b)
            semantic.merge_memories(keep.id, absorb.id)
        elif relation == "contradiction":
            resolution = data.get("resolution")
            reason = data.get("reason", "")
            if resolution == "keep_a":
                semantic.remove(memory_b.id)
            elif resolution == "keep_b":
                semantic.remove(memory_a.id)
            else:
                # undecided：不做不可逆删除，双方都标记disputed，交给定期人工审查
                semantic.mark_disputed(memory_a.id, memory_b.id, reason)
                semantic.mark_disputed(memory_b.id, memory_a.id, reason)
        # complementary / unrelated：两条都成立，不需要处理
