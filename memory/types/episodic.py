"""情景记忆实现

按照第8章架构设计的情景记忆，提供：
- 具体交互事件存储
- 时间序列组织
- 上下文丰富的记忆
- 模式识别能力
"""

from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import os
import math
import json
import logging

logger = logging.getLogger(__name__)

from ..base import BaseMemory, MemoryItem, MemoryConfig
from ..storage import SQLiteDocumentStore

class Episode:
    """情景记忆中的单个情景

    结构化字段（engagement_id/target_ref/phase/event_type/outcome/causal_ref/entities）
    统一保存在 metadata 里；context 是调用方自由填写的补充信息（不进入结构化schema，
    不参与过滤/分类），两者用途不同，分开存放。
    """

    def __init__(
        self,
        episode_id: str,
        user_id: str,
        session_id: str,
        timestamp: datetime,
        content: str,
        context: Optional[Dict[str, Any]] = None,
        outcome: Optional[str] = None,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.episode_id = episode_id
        self.user_id = user_id
        self.session_id = session_id
        self.timestamp = timestamp
        self.content = content
        self.context = context or {}
        self.outcome = outcome
        self.importance = importance
        # 原始metadata全量保留（target_ref/event_type/phase/engagement_id/causal_ref等）
        self.metadata = metadata or {}

class EpisodicMemory(BaseMemory):
    """情景记忆实现

    特点：
    - 存储具体的交互事件
    - 包含丰富的上下文信息
    - 按时间序列组织
    - 支持模式识别和回溯
    """

    def __init__(self, config: MemoryConfig, storage_backend=None):
        super().__init__(config, storage_backend)

        # 本地缓存（内存）
        self.episodes: List[Episode] = []
        self.sessions: Dict[str, List[str]] = {}  # session_id -> episode_ids

        # 模式识别缓存
        self.patterns_cache = {}
        self.last_pattern_analysis = None

        # 权威文档存储（SQLite）——检索的唯一数据源，不再引入向量库
        # （见 DESIGN.md「Episodic Memory 检索策略」：engagement_id 为唯一边界，
        # 检索走结构化精确查询，不做向量语义召回）
        db_dir = self.config.storage_path if hasattr(self.config, 'storage_path') else "./memory_data"
        os.makedirs(db_dir, exist_ok=True)
        db_path = os.path.join(db_dir, "memory.db")
        self.doc_store = SQLiteDocumentStore(db_path=db_path)

    # MetaData Schema 中通用层/episodic特有层需要持久化的结构化字段
    _PERSISTED_KEYS = (
        "target_ref", "event_type", "phase", "engagement_id",
        "is_target_bound", "causal_ref", "entities"
    )

    def add(self, memory_item: MemoryItem) -> str:
        """添加情景记忆"""
        session_id = memory_item.metadata.get("session_id", "default_session")
        outcome = memory_item.metadata.get("outcome")
        context = memory_item.metadata.get("context", {})

        # 创建情景（内存缓存），metadata保留完整原始字段
        episode = Episode(
            episode_id=memory_item.id,
            user_id=memory_item.user_id,
            session_id=session_id,
            timestamp=memory_item.timestamp,
            content=memory_item.content,
            context=context,
            outcome=outcome,
            importance=memory_item.importance,
            metadata=memory_item.metadata
        )
        self.episodes.append(episode)
        if session_id not in self.sessions:
            self.sessions[session_id] = []
        self.sessions[session_id].append(episode.episode_id)

        # 1) 权威存储（SQLite）：额外保留target_ref/event_type/phase/engagement_id/causal_ref，
        # 供阶段边界触发的semantic归纳按phase/target_ref过滤episodic记忆
        ts_int = int(memory_item.timestamp.timestamp())
        properties = {"session_id": session_id, "outcome": outcome, "context": context}
        for key in self._PERSISTED_KEYS:
            if key in memory_item.metadata:
                properties[key] = memory_item.metadata[key]
        self.doc_store.add_memory(
            memory_id=memory_item.id,
            user_id=memory_item.user_id,
            content=memory_item.content,
            memory_type="episodic",
            timestamp=ts_int,
            importance=memory_item.importance,
            properties=properties
        )

        return memory_item.id

    def _touch_last_accessed(self, memory_id: str, now_ts: int) -> None:
        """检索命中时刷新 last_accessed_at（SQLite properties + 内存缓存）"""
        episode = next((e for e in self.episodes if e.episode_id == memory_id), None)
        if episode is not None:
            episode.metadata["last_accessed_at"] = now_ts

        doc = self.doc_store.get_memory(memory_id)
        if not doc:
            return
        properties = doc.get("properties", {}) or {}
        properties["last_accessed_at"] = now_ts
        self.doc_store.update_memory(memory_id=memory_id, properties=properties)

    def retrieve(self, query: str = "", limit: int = 5, **kwargs) -> List[MemoryItem]:
        """检索情景记忆——结构化精确/收窄查询，不做向量语义召回。

        对齐 DESIGN.md「Episodic Memory 检索策略」：
          - engagement_id 是唯一的安全边界，未提供时直接返回空列表，不做无边界搜索
          - target_ref / phase / event_type 是可选的结构化收窄条件，由调用方
            （LLM 在 Action 阶段）显式给出，精确等值匹配，不经过相似度打分
          - query 可选，仅做大小写不敏感的内容子串匹配，用于精确定位已知关键词
            （如 CVE 编号、服务版本号），不是语义相似度检索
          - 只给 engagement_id、不给其他收窄条件时，本方法本身就是默认的
            "近期+高重要性"摘要清单（召回安全网），无需额外方法

        Args:
            query: 可选关键词，对 content 做子串匹配
            limit: 返回数量上限
            engagement_id: 必填，唯一检索边界
            target_ref/phase: 可选，结构化收窄
            event_type: 可选，单个值或列表，精确匹配
            time_range/importance_threshold: 可选，数值区间过滤
        """
        engagement_id = kwargs.get("engagement_id")
        if not engagement_id:
            logger.warning("episodic.retrieve 缺少 engagement_id：这是唯一检索边界，拒绝无边界查询")
            return []

        target_ref = kwargs.get("target_ref")
        phase = kwargs.get("phase")
        event_type = kwargs.get("event_type")  # str 或 list[str]
        time_range: Optional[Tuple[datetime, datetime]] = kwargs.get("time_range")
        importance_threshold: Optional[float] = kwargs.get("importance_threshold")

        properties_filter: Dict[str, Any] = {"engagement_id": engagement_id}
        if target_ref:
            properties_filter["target_ref"] = target_ref
        if phase:
            properties_filter["phase"] = phase

        start_ts = int(time_range[0].timestamp()) if time_range else None
        end_ts = int(time_range[1].timestamp()) if time_range else None
        docs = self.doc_store.search_memories(
            memory_type="episodic",
            start_time=start_ts,
            end_time=end_ts,
            importance_threshold=importance_threshold,
            properties_filter=properties_filter,
            limit=1000
        )

        # event_type 支持单值或列表；SQL 层的 properties_filter 只做等值匹配，
        # 多值匹配在候选集上过滤即可，量级（几十-几百条/engagement）完全撑得住
        if event_type:
            wanted = {event_type} if isinstance(event_type, str) else set(event_type)
            docs = [d for d in docs if (d.get("properties") or {}).get("event_type") in wanted]

        # 关键词是精确子串匹配，不是相似度检索
        if query:
            query_lower = query.lower()
            docs = [d for d in docs if query_lower in (d.get("content") or "").lower()]

        # 排序仅用 recency + importance，不引入向量分数
        now_ts = int(datetime.now().timestamp())
        scored: List[Tuple[float, MemoryItem]] = []
        for doc in docs:
            age_days = max(0.0, (now_ts - int(doc["timestamp"])) / 86400.0)
            recency_score = 1.0 / (1.0 + age_days)
            imp = float(doc.get("importance", 0.5))
            importance_weight = 0.8 + (imp * 0.4)
            combined = recency_score * importance_weight

            item = MemoryItem(
                id=doc["memory_id"],
                content=doc["content"],
                memory_type=doc["memory_type"],
                user_id=doc["user_id"],
                timestamp=datetime.fromtimestamp(doc["timestamp"]),
                importance=doc.get("importance", 0.5),
                metadata={
                    **doc.get("properties", {}),
                    "updated_at": doc.get("updated_at"),
                    "relevance_score": combined,
                    "recency_score": recency_score
                }
            )
            scored.append((combined, item))

        scored.sort(key=lambda x: x[0], reverse=True)
        final = [it for _, it in scored[:limit]]

        # 刷新命中记忆的 last_accessed_at——只碰真正返回的 top-N，不碰扫描过的候选
        for it in final:
            self._touch_last_accessed(it.id, now_ts)
            it.metadata["last_accessed_at"] = now_ts

        return final

    def get_causal_chain(
        self,
        memory_id: str,
        direction: str = "backward",
        max_depth: int = 5
    ) -> List[MemoryItem]:
        """沿 causal_ref 做精确因果链遍历，回答"这条记录是怎么来的/导向了谁"。

        这类查询天然该用图式精确遍历而不是相似度检索——causal_ref 记的是确定性的
        依赖关系（如"凭据X取自主机A，被用于登录主机B"），向量相似度既算不出这种
        因果关系，也没有必要参与。

        Args:
            memory_id: 起点记忆ID
            direction: "backward"（回溯这条记录依赖的前置事件）或
                       "forward"（查找哪些记录的 causal_ref 指向了这条记录）
            max_depth: 最大遍历层数，防止环形引用导致无限遍历

        Returns:
            按遍历顺序排列的 MemoryItem 列表（不含起点本身）
        """
        start_doc = self.doc_store.get_memory(memory_id)
        if not start_doc:
            return []

        visited = {memory_id}
        result_ids: List[str] = []

        if direction == "backward":
            frontier = list((start_doc.get("properties") or {}).get("causal_ref") or [])
            depth = 1
            while frontier and depth <= max_depth:
                next_frontier = []
                for mid in frontier:
                    if mid in visited:
                        continue
                    visited.add(mid)
                    result_ids.append(mid)
                    doc = self.doc_store.get_memory(mid)
                    if doc:
                        next_frontier.extend((doc.get("properties") or {}).get("causal_ref") or [])
                frontier = next_frontier
                depth += 1
        elif direction == "forward":
            # causal_ref 不是索引字段，需要在起点所在 engagement 范围内扫描一次；
            # 量级几十-几百条/engagement，完全可接受
            engagement_id = (start_doc.get("properties") or {}).get("engagement_id")
            engagement_docs = self.doc_store.search_memories(
                memory_type="episodic",
                properties_filter={"engagement_id": engagement_id} if engagement_id else None,
                limit=1000
            )
            frontier = {memory_id}
            depth = 1
            while frontier and depth <= max_depth:
                next_frontier = set()
                for doc in engagement_docs:
                    mid = doc["memory_id"]
                    if mid in visited:
                        continue
                    refs = set((doc.get("properties") or {}).get("causal_ref") or [])
                    if refs & frontier:
                        visited.add(mid)
                        result_ids.append(mid)
                        next_frontier.add(mid)
                frontier = next_frontier
                depth += 1
        else:
            raise ValueError(f"direction 只支持 'backward'/'forward'，收到: {direction}")

        items = []
        for mid in result_ids:
            doc = self.doc_store.get_memory(mid)
            if not doc:
                continue
            items.append(MemoryItem(
                id=doc["memory_id"],
                content=doc["content"],
                memory_type=doc["memory_type"],
                user_id=doc["user_id"],
                timestamp=datetime.fromtimestamp(doc["timestamp"]),
                importance=doc.get("importance", 0.5),
                metadata={**doc.get("properties", {}), "updated_at": doc.get("updated_at")}
            ))
        return items

    def update(
        self,
        memory_id: str,
        content: str = None,
        importance: float = None,
        metadata: Dict[str, Any] = None
    ) -> bool:
        """更新情景记忆（SQLite为权威，Qdrant按需重嵌入）"""
        updated = False
        for episode in self.episodes:
            if episode.episode_id == memory_id:
                if content is not None:
                    episode.content = content
                if importance is not None:
                    episode.importance = importance
                if metadata is not None:
                    episode.metadata.update(metadata)
                    if "outcome" in metadata:
                        episode.outcome = metadata["outcome"]
                    if "context" in metadata:
                        episode.context.update(metadata["context"])
                updated = True
                break

        # 更新SQLite（唯一权威存储，无需再同步向量库）
        doc_updated = self.doc_store.update_memory(
            memory_id=memory_id,
            content=content,
            importance=importance,
            properties=metadata
        )

        return updated or doc_updated

    def remove(self, memory_id: str) -> bool:
        """删除情景记忆（SQLite）"""
        removed = False
        for i, episode in enumerate(self.episodes):
            if episode.episode_id == memory_id:
                removed_episode = self.episodes.pop(i)
                session_id = removed_episode.session_id
                if session_id in self.sessions:
                    self.sessions[session_id].remove(memory_id)
                    if not self.sessions[session_id]:
                        del self.sessions[session_id]
                removed = True
                break

        doc_deleted = self.doc_store.delete_memory(memory_id)

        return removed or doc_deleted

    def has_memory(self, memory_id: str) -> bool:
        """检查记忆是否存在"""
        return any(episode.episode_id == memory_id for episode in self.episodes)

    def clear(self):
        """清空所有情景记忆（仅清理episodic，不影响其他类型）"""
        # 内存缓存
        self.episodes.clear()
        self.sessions.clear()
        self.patterns_cache.clear()

        # SQLite内的episodic全部删除
        docs = self.doc_store.search_memories(memory_type="episodic", limit=10000)
        ids = [d["memory_id"] for d in docs]
        for mid in ids:
            self.doc_store.delete_memory(mid)

    def clear_by_engagement(self, engagement_id: str) -> int:
        """按engagement_id硬删除该engagement下的episodic记忆（用户显式触发，不自动执行）

        直接以SQLite权威库为准扫描，而不是仅遍历内存缓存self.episodes——
        避免跨进程重启后内存缓存为空、导致本该删除的历史记录被漏删。
        """
        docs = self.doc_store.search_memories(memory_type="episodic", limit=10000)
        ids = [
            d["memory_id"] for d in docs
            if (d.get("properties") or {}).get("engagement_id") == engagement_id
        ]

        removed_count = 0
        for memory_id in ids:
            if self.remove(memory_id):
                removed_count += 1

        logger.info(f"engagement清空完成: engagement_id={engagement_id}, 删除 {removed_count} 条episodic记忆")
        return removed_count

    def forget(self, strategy: str = "importance_based", threshold: float = 0.1, max_age_days: int = 30) -> int:
        """情景记忆遗忘机制（硬删除）"""
        forgotten_count = 0
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(days=max_age_days)

        to_remove = []  # 收集要删除的记忆ID

        for episode in self.episodes:
            should_forget = False

            if strategy == "importance_based":
                # 基于重要性遗忘
                if episode.importance < threshold:
                    should_forget = True
            elif strategy == "time_based":
                # 基于时间遗忘（创建时间）
                if episode.timestamp < cutoff_time:
                    should_forget = True
            elif strategy == "access_based":
                # 基于访问频率遗忘（LRU）：从未被检索命中过的记忆，退回用创建时间判断
                last_accessed = episode.metadata.get("last_accessed_at")
                reference_time = datetime.fromtimestamp(last_accessed) if last_accessed else episode.timestamp
                if reference_time < cutoff_time:
                    should_forget = True
            elif strategy == "capacity_based":
                # 基于容量遗忘（保留最重要的）
                if len(self.episodes) > self.config.max_capacity:
                    sorted_episodes = sorted(self.episodes, key=lambda e: e.importance)
                    excess_count = len(self.episodes) - self.config.max_capacity
                    if episode in sorted_episodes[:excess_count]:
                        should_forget = True

            if should_forget:
                to_remove.append(episode.episode_id)

        # 执行硬删除
        for episode_id in to_remove:
            if self.remove(episode_id):
                forgotten_count += 1
                logger.info(f"情景记忆硬删除: {episode_id[:8]}... (策略: {strategy})")

        return forgotten_count

    def get_all(self) -> List[MemoryItem]:
        """获取所有情景记忆（转换为MemoryItem格式）"""
        memory_items = []
        for episode in self.episodes:
            memory_item = MemoryItem(
                id=episode.episode_id,
                content=episode.content,
                memory_type="episodic",
                user_id=episode.user_id,
                timestamp=episode.timestamp,
                importance=episode.importance,
                metadata={**episode.metadata, "context": episode.context}
            )
            memory_items.append(memory_item)
        return memory_items

    def get_stats(self) -> Dict[str, Any]:
        """获取情景记忆统计信息"""
        # 硬删除模式：所有episodes都是活跃的
        active_episodes = self.episodes

        db_stats = self.doc_store.get_database_stats()
        return {
            "count": len(active_episodes),  # 活跃记忆数量
            "forgotten_count": 0,  # 硬删除模式下已遗忘的记忆会被直接删除
            "total_count": len(self.episodes),  # 总记忆数量
            "sessions_count": len(self.sessions),
            "avg_importance": sum(e.importance for e in active_episodes) / len(active_episodes) if active_episodes else 0.0,
            "time_span_days": self._calculate_time_span(),
            "memory_type": "episodic",
            "document_store": {k: v for k, v in db_stats.items() if k.endswith("_count") or k in ["store_type", "db_path"]}
        }

    def get_session_episodes(self, session_id: str) -> List[Episode]:
        """获取指定会话的所有情景"""
        if session_id not in self.sessions:
            return []

        episode_ids = self.sessions[session_id]
        return [e for e in self.episodes if e.episode_id in episode_ids]

    def find_patterns(self, min_frequency: int = 2) -> List[Dict[str, Any]]:
        """发现行为模式"""
        # 检查缓存
        cache_key = f"{min_frequency}"
        if (cache_key in self.patterns_cache and
            self.last_pattern_analysis and
            (datetime.now() - self.last_pattern_analysis).hours < 1):
            return self.patterns_cache[cache_key]

        episodes = self.episodes

        # 简单的模式识别：基于内容关键词 + 结构化字段
        keyword_patterns = {}
        field_patterns = {}

        for episode in episodes:
            # 提取关键词
            words = episode.content.lower().split()
            for word in words:
                if len(word) > 3:  # 忽略短词
                    keyword_patterns[word] = keyword_patterns.get(word, 0) + 1

            # 提取结构化字段模式（phase/event_type/outcome/target_ref/engagement_id）
            for key in ("phase", "event_type", "outcome", "target_ref", "engagement_id"):
                value = episode.metadata.get(key)
                if value:
                    pattern_key = f"{key}:{value}"
                    field_patterns[pattern_key] = field_patterns.get(pattern_key, 0) + 1

        # 筛选频繁模式
        patterns = []

        for keyword, frequency in keyword_patterns.items():
            if frequency >= min_frequency:
                patterns.append({
                    "type": "keyword",
                    "pattern": keyword,
                    "frequency": frequency,
                    "confidence": frequency / len(episodes)
                })

        for field_pattern, frequency in field_patterns.items():
            if frequency >= min_frequency:
                patterns.append({
                    "type": "structured_field",
                    "pattern": field_pattern,
                    "frequency": frequency,
                    "confidence": frequency / len(episodes)
                })

        # 按频率排序
        patterns.sort(key=lambda x: x["frequency"], reverse=True)

        # 缓存结果
        self.patterns_cache[cache_key] = patterns
        self.last_pattern_analysis = datetime.now()

        return patterns

    def get_timeline(self, limit: int = 50) -> List[Dict[str, Any]]:
        """获取时间线视图"""
        episodes = sorted(self.episodes, key=lambda x: x.timestamp, reverse=True)

        timeline = []
        for episode in episodes[:limit]:
            timeline.append({
                "episode_id": episode.episode_id,
                "timestamp": episode.timestamp.isoformat(),
                "content": episode.content[:100] + "..." if len(episode.content) > 100 else episode.content,
                "session_id": episode.session_id,
                "importance": episode.importance,
                "outcome": episode.outcome
            })

        return timeline

    def _calculate_time_span(self) -> float:
        """计算记忆时间跨度（天）"""
        if not self.episodes:
            return 0.0

        timestamps = [e.timestamp for e in self.episodes]
        min_time = min(timestamps)
        max_time = max(timestamps)

        return (max_time - min_time).days

    def _persist_episode(self, episode: Episode):
        """持久化情景到存储后端"""
        if self.storage and hasattr(self.storage, 'add_memory'):
            self.storage.add_memory(
                memory_id=episode.episode_id,
                user_id=episode.user_id,
                content=episode.content,
                memory_type="episodic",
                timestamp=int(episode.timestamp.timestamp()),
                importance=episode.importance,
                properties={
                    "session_id": episode.session_id,
                    "outcome": episode.outcome
                }
            )

    def _remove_from_storage(self, memory_id: str):
        """从存储后端删除"""
        if self.storage and hasattr(self.storage, 'delete_memory'):
            self.storage.delete_memory(memory_id)
