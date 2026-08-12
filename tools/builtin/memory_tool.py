"""记忆工具

为HelloAgents框架提供记忆能力的工具实现。
可以作为工具添加到任何Agent中，让Agent具备记忆功能。
专注于用户接口和参数处理
Reference: https://github.com/jjyaoao/HelloAgents/blob/learn_version/hello_agents/tools/builtin/memory_tool.py
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..base import BaseTool, ToolParameter, tool_action
from memory import MemoryManager, MemoryConfig
from agent.models import ToolResult
from agent.state import AgentState
class MemoryTool(BaseTool):
    """
    记忆工具 - 为Agent提供记忆功能
    """

    def __init__(
        self,
        user_id: str = "default_user",
        memory_config: MemoryConfig = None,
        memory_types: List[str] = None
    ):
        super().__init__(
            name="memory",
            description="记忆工具 - 可以存储和检索对话历史、知识和经验"
        )

        # 初始化记忆管理器
        self.memory_config = memory_config or MemoryConfig()
        self.memory_types = memory_types or ["working", "episodic", "semantic"]

        self.memory_manager = MemoryManager(
            config=self.memory_config,
            user_id=user_id,
            enable_working="working" in self.memory_types,
            enable_episodic="episodic" in self.memory_types,
            enable_semantic="semantic" in self.memory_types,
            enable_perceptual="perceptual" in self.memory_types
        )

        # 会话状态
        self.current_session_id = None
        self.conversation_count = 0

    # action -> 处理方法名，白名单方式分发（避免 getattr 任意字符串拼接带来的风险）
    _ACTIONS = {
        "add": "_add_memory",
        "search": "_search_memory",
        "summary": "_get_summary",
        "stats": "_get_stats",
        "update": "_update_memory",
        "remove": "_remove_memory",
        "forget": "_forget",
        "clear_all": "_clear_all",
        "purge_engagement": "_purge_engagement",
    }

    def execute(self,
                state: AgentState,
                action: str,
                **kwargs) -> ToolResult:
        """执行记忆操作工具（非展开模式）

        Args:
            state: Agent运行状态（记忆工具本身不依赖它，仅满足BaseTool接口）
            action: 要执行的操作，见 _ACTIONS
            **kwargs: 对应action所需的具体参数，转发给相应的处理方法

        Returns:
            ToolResult，output为执行结果字符串

        支持的操作：
        - add: 添加记忆（支持4种类型: working/episodic/semantic/perceptual）
        - search: 搜索记忆
        - summary: 获取记忆摘要
        - stats: 获取统计信息
        - update: 更新记忆
        - remove: 删除记忆
        - forget: 遗忘记忆（多种策略）
        - clear_all: 清空所有记忆
        - purge_engagement: 按engagement_id硬删除该engagement下的episodic记忆（用户显式触发，不会自动执行）
        """
        method_name = self._ACTIONS.get(action)
        if method_name is None:
            return ToolResult(
                tool="memory",
                success=False,
                output=None,
                message=f"Unknown action: {action!r}. Expected one of: {', '.join(self._ACTIONS)}.",
            )

        handler = getattr(self, method_name)
        try:
            output = handler(**kwargs)
        except TypeError as e:
            return ToolResult(
                tool="memory",
                success=False,
                output=None,
                message=f"Invalid parameters for action '{action}': {e}",
            )

        return ToolResult(
            tool="memory",
            success=not output.startswith("❌"),
            output=output,
            message="",
        )

    def get_parameters(self) -> List[ToolParameter]:
        """获取工具参数定义 - BaseTool基类要求的接口"""
        return [
            ToolParameter(
                name="action",
                type="string",
                description=(
                    "要执行的操作："
                    "add(添加记忆), search(搜索记忆), summary(获取摘要), stats(获取统计), "
                    "update(更新记忆), remove(删除记忆), forget(遗忘记忆), clear_all(清空所有记忆), "
                    "purge_engagement(按engagement_id硬删除该engagement下的episodic记忆，需用户显式触发)"
                ),
                required=True
            ),
            ToolParameter(name="content", type="string", description="记忆内容（add/update时可用；感知记忆可作描述）", required=False),
            ToolParameter(name="query", type="string", description="搜索查询（search时可用）", required=False),
            ToolParameter(name="memory_type", type="string", description="仅perceptual需要显式指定；working/episodic/semantic由is_target_bound自动判定，此参数会被忽略（默认：working）", required=False, default="working"),
            ToolParameter(name="importance", type="number", description="重要性分数，0.0-1.0（add/update时可用）", required=False),
            ToolParameter(name="is_target_bound", type="boolean", description="add时可用：该记忆是否绑定具体渗透target/engagement。True→episodic，False→semantic，不传→working", required=False),
            ToolParameter(name="engagement_id", type="string", description="项目级作用域标识，比target_ref高一层——一次engagement可能涉及多个target。add时可用（episodic建议提供）；search时可用（传入后episodic memory只检索该engagement下的记录）；purge_engagement时必需（指定要硬删除哪个engagement的episodic记忆）", required=False),
            ToolParameter(name="target_ref", type="string", description="add时可用：资产级标识（IP/host），is_target_bound=True时应提供", required=False),
            ToolParameter(name="phase", type="string", description="add时可用：所处PTES阶段，recon/vuln_analysis/exploitation/post_exploitation之一，用于按阶段过滤检索", required=False),
            ToolParameter(name="event_type", type="string", description="add时可用：事件类型标签，例如asset_discovery/credential_found/exploit_attempt/recon_negative/defense_observed/privesc_lateral_move/osint_finding/scope_directive（episodic）或vuln_technique_knowledge/exploit_applicability_knowledge/vuln_analysis_technique/privesc_lateral_strategy/tool_best_practice/evasion_technique/pattern_insight（semantic）。仅用于与is_target_bound做一致性校验，不决定分类", required=False),
            ToolParameter(name="outcome", type="string", description="add时可用（episodic）：事件结果，success/tech_fail/op_fail/negative之一，用于区分技术性失败与操作性失败", required=False),
            ToolParameter(name="context", type="object", description="add时可用（episodic）：不适合归入结构化字段的自由补充信息，例如原始命令行、完整报文片段等排查用细节；不参与分类/过滤，只作为附加信息存储", required=False),
            ToolParameter(name="causal_ref", type="array", description="add时可用（episodic）：该事件依赖/关联的其他episodic记忆ID列表，用于记录攻击路径因果链（如凭据取自主机A被用于登录主机B）", required=False),
            ToolParameter(name="entities", type="array", description="add时可用：该记忆涉及的实体列表，如CVE编号、exploit模块名（semantic记忆建议提供，便于构建知识图谱，缺失时图谱部分会退化为纯向量检索）", required=False),
            ToolParameter(name="confidence", type="number", description="add时可用（semantic）：该知识的可信度，0.0-1.0，与importance解耦——importance回答多重要，confidence回答多可信", required=False),
            ToolParameter(name="derived_from", type="array", description="add时可用（semantic）：该知识是从哪些episodic记忆ID归纳得到的，用于溯源", required=False),
            ToolParameter(name="limit", type="integer", description="搜索结果数量限制（默认：5）", required=False, default=5),
            ToolParameter(name="memory_id", type="string", description="目标记忆ID（update/remove时必需）", required=False),
            ToolParameter(name="file_path", type="string", description="感知记忆：本地文件路径（image/audio）", required=False),
            ToolParameter(name="modality", type="string", description="感知记忆模态：text/image/audio（不传则按扩展名推断）", required=False),
            ToolParameter(name="strategy", type="string", description="遗忘策略：importance_based/time_based/capacity_based/access_based（forget时可用）", required=False, default="importance_based"),
            ToolParameter(name="threshold", type="number", description="遗忘阈值（forget时可用，默认0.1）", required=False, default=0.1),
            ToolParameter(name="max_age_days", type="integer", description="最大保留天数（time_based）/ 最长未访问天数（access_based）", required=False, default=30),
        ]

    # perception information encoding to memory
    @tool_action("memory_add", "添加新记忆到记忆系统中")
    def _add_memory(
        self,
        content: str = "",
        memory_type: str = "working",
        importance: float = 0.5,
        file_path: str = None,
        modality: str = None,
        is_target_bound: bool = None,
        engagement_id: str = None,
        target_ref: str = None,
        phase: str = None,
        event_type: str = None,
        outcome: str = None,
        context: Dict[str, Any] = None,
        causal_ref: List[str] = None,
        entities: List[str] = None,
        confidence: float = None,
        derived_from: List[str] = None
    ) -> str:
        """添加记忆

        Args:
            content: 记忆内容
            memory_type: 仅perceptual需要显式指定；working/episodic/semantic由is_target_bound自动判定
            importance: 重要性分数，0.0-1.0
            file_path: 感知记忆：本地文件路径（image/audio）
            modality: 感知记忆模态：text/image/audio（不传则按扩展名推断）
            is_target_bound: 该记忆是否绑定具体渗透target/engagement，episodic/semantic的判定开关
            engagement_id: 项目级作用域标识，比target_ref高一层（episodic建议提供）
            target_ref: 资产级标识（IP/host），is_target_bound=True时应提供
            phase: 所处PTES阶段：recon/vuln_analysis/exploitation/post_exploitation
            event_type: 事件类型标签，仅用于与is_target_bound做一致性校验，不决定分类
            outcome: 事件结果（episodic）：success/tech_fail/op_fail/negative
            context: 不适合归入结构化字段的自由补充信息（episodic），不参与分类/过滤
            causal_ref: 该事件依赖/关联的其他episodic记忆ID列表（episodic）
            entities: 该记忆涉及的实体列表（如CVE编号、exploit模块名），semantic记忆建议提供
            confidence: 该知识的可信度，0.0-1.0（semantic）
            derived_from: 该知识归纳自哪些episodic记忆ID（semantic）

        Returns:
            执行结果
        """
        metadata = {}
        try:
            # 确保会话ID存在
            # session到底持续多久，取决于MemoryTool对象活多久
            # agent 启动时构造一个 MemoryTool 实例（生命周期跟进程绑定），进程退出，session 自然结束
            if self.current_session_id is None:
                self.current_session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 感知记忆走独立通道，不受is_target_bound影响，显式覆盖_classify_memory_type的分类结果
            if memory_type == "perceptual":
                metadata["type"] = "perceptual"
                if file_path:
                    inferred = modality or self._infer_modality(file_path)
                    metadata.setdefault("modality", inferred)
                    metadata.setdefault("raw_data", file_path)

            # 结构化分类字段，供 MemoryManager._classify_memory_type 使用
            if is_target_bound is not None:
                metadata["is_target_bound"] = is_target_bound
            if engagement_id:
                metadata["engagement_id"] = engagement_id
            if target_ref:
                metadata["target_ref"] = target_ref
            if phase:
                metadata["phase"] = phase
            if event_type:
                metadata["event_type"] = event_type
            if outcome:
                metadata["outcome"] = outcome
            if context:
                metadata["context"] = context
            if causal_ref:
                metadata["causal_ref"] = causal_ref
            if entities:
                metadata["entities"] = entities
            if confidence is not None:
                metadata["confidence"] = confidence
            if derived_from:
                metadata["derived_from"] = derived_from

            # 添加会话信息到元数据
            # session id的自动管理，确保每个记忆都有明确的会话归属
            metadata.update({
                "session_id": self.current_session_id,
                "timestamp": datetime.now().isoformat()
            })

            memory_id = self.memory_manager.add_memory(
                content=content,
                memory_type=memory_type,
                importance=importance,
                metadata=metadata,
                auto_classify=True
            )

            return f"✅ 记忆已添加 (ID: {memory_id[:8]}...)"

        except Exception as e:
            return f"❌ 添加记忆失败: {str(e)}"

    def _infer_modality(self, path: str) -> str:
        """根据扩展名推断模态（默认image/audio/text）"""
        # 多模态数据的智能处理
        try:
            ext = (path.rsplit('.', 1)[-1] or '').lower()
            if ext in {"png", "jpg", "jpeg", "bmp", "gif", "webp"}:
                return "image"
            if ext in {"mp3", "wav", "flac", "m4a", "ogg"}:
                return "audio"
            return "text"
        except Exception:
            return "text"


    # core function
    @tool_action("memory_search", "搜索相关记忆")
    def _search_memory(
        self,
        query: str,
        limit: int = 5,
        memory_type: str = None,
        min_importance: float = 0.1,
        engagement_id: str = None
    ) -> str:
        """搜索记忆

        Args:
            query: 搜索查询内容
            limit: 搜索结果数量限制
            memory_type: 限定记忆类型：working/episodic/semantic/perceptual
            min_importance: 最低重要性阈值
            engagement_id: 传入时episodic memory只检索该engagement下的记录，
                避免跨engagement的记忆互相串扰（semantic不受此限制，语义知识本就应跨engagement复用）

        Returns:
            搜索结果
        """
        try:
            # 处理memory_type参数
            memory_types = [memory_type] if memory_type else None

            # 多类型搜索
            results = self.memory_manager.retrieve_memories(
                query=query,
                limit=limit,
                memory_types=memory_types,
                min_importance=min_importance,
                engagement_id=engagement_id
            )

            if not results:
                return f"🔍 未找到与 '{query}' 相关的记忆"

            # 格式化结果
            formatted_results = []
            formatted_results.append(f"🔍 找到 {len(results)} 条相关记忆:")

            for i, memory in enumerate(results, 1):
                memory_type_label = {
                    "working": "工作记忆",
                    "episodic": "情景记忆",
                    "semantic": "语义记忆",
                    "perceptual": "感知记忆"
                }.get(memory.memory_type, memory.memory_type)

                content_preview = memory.content[:80] + "..." if len(memory.content) > 80 else memory.content
                formatted_results.append(
                    f"{i}. [{memory_type_label}] {content_preview} (重要性: {memory.importance:.2f})"
                )

            return "\n".join(formatted_results)

        except Exception as e:
            return f"❌ 搜索记忆失败: {str(e)}"

    @tool_action("memory_summary", "获取记忆系统摘要（包含重要记忆和统计信息）")
    def _get_summary(self, limit: int = 10) -> str:
        """获取记忆摘要

        Args:
            limit: 显示的重要记忆数量

        Returns:
            记忆摘要
        """
        try:
            stats = self.memory_manager.get_memory_stats()

            summary_parts = [
                f"📊 记忆系统摘要",
                f"总记忆数: {stats['total_memories']}",
                f"当前会话: {self.current_session_id or '未开始'}",
                f"对话轮次: {self.conversation_count}"
            ]

            # 各类型记忆统计
            if stats['memories_by_type']:
                summary_parts.append("\n📋 记忆类型分布:")
                for memory_type, type_stats in stats['memories_by_type'].items():
                    count = type_stats.get('count', 0)
                    avg_importance = type_stats.get('avg_importance', 0)
                    type_label = {
                        "working": "工作记忆",
                        "episodic": "情景记忆",
                        "semantic": "语义记忆",
                        "perceptual": "感知记忆"
                    }.get(memory_type, memory_type)

                    summary_parts.append(f"  • {type_label}: {count} 条 (平均重要性: {avg_importance:.2f})")

            # 获取重要记忆 - 修复重复问题
            important_memories = self.memory_manager.retrieve_memories(
                query="",
                memory_types=None,  # 从所有类型中检索
                limit=limit * 3,  # 获取更多候选，然后去重
                min_importance=0.5  # 降低阈值以获取更多记忆
            )

            if important_memories:
                # 去重：使用记忆ID和内容双重去重
                seen_ids = set()
                seen_contents = set()
                unique_memories = []

                for memory in important_memories:
                    # 使用ID去重
                    if memory.id in seen_ids:
                        continue

                    # 使用内容去重（防止相同内容的不同记忆）
                    content_key = memory.content.strip().lower()
                    if content_key in seen_contents:
                        continue

                    seen_ids.add(memory.id)
                    seen_contents.add(content_key)
                    unique_memories.append(memory)

                # 按重要性排序
                unique_memories.sort(key=lambda x: x.importance, reverse=True)
                summary_parts.append(f"\n⭐ 重要记忆 (前{min(limit, len(unique_memories))}条):")

                for i, memory in enumerate(unique_memories[:limit], 1):
                    content_preview = memory.content[:60] + "..." if len(memory.content) > 60 else memory.content
                    summary_parts.append(f"  {i}. {content_preview} (重要性: {memory.importance:.2f})")

            return "\n".join(summary_parts)

        except Exception as e:
            return f"❌ 获取摘要失败: {str(e)}"

    @tool_action("memory_stats", "获取记忆系统的统计信息")
    def _get_stats(self) -> str:
        """获取统计信息

        Returns:
            统计信息
        """
        try:
            stats = self.memory_manager.get_memory_stats()

            stats_info = [
                f"📈 记忆系统统计",
                f"总记忆数: {stats['total_memories']}",
                f"启用的记忆类型: {', '.join(stats['enabled_types'])}",
                f"会话ID: {self.current_session_id or '未开始'}",
                f"对话轮次: {self.conversation_count}"
            ]

            return "\n".join(stats_info)

        except Exception as e:
            return f"❌ 获取统计信息失败: {str(e)}"

    @tool_action("memory_update", "更新已存在的记忆")
    def _update_memory(self, memory_id: str, content: str = None, importance: float = None) -> str:
        """更新记忆

        Args:
            memory_id: 要更新的记忆ID
            content: 新的记忆内容
            importance: 新的重要性分数

        Returns:
            执行结果
        """
        try:
            metadata = {}
            success = self.memory_manager.update_memory(
                memory_id=memory_id,
                content=content,
                importance=importance,
                metadata=metadata or None
            )
            return "✅ 记忆已更新" if success else "⚠️ 未找到要更新的记忆"
        except Exception as e:
            return f"❌ 更新记忆失败: {str(e)}"

    @tool_action("memory_remove", "删除指定的记忆")
    def _remove_memory(self, memory_id: str) -> str:
        """删除记忆

        Args:
            memory_id: 要删除的记忆ID

        Returns:
            执行结果
        """
        try:
            success = self.memory_manager.remove_memory(memory_id)
            return "✅ 记忆已删除" if success else "⚠️ 未找到要删除的记忆"
        except Exception as e:
            return f"❌ 删除记忆失败: {str(e)}"

    # 基于重要性forget
    # 基于时间forget
    # 基于容量forget
    @tool_action("memory_forget", "按照策略批量遗忘记忆")
    def _forget(self, strategy: str = "importance_based", threshold: float = 0.1, max_age_days: int = 30) -> str:
        """遗忘记忆（支持多种策略）

        Args:
            strategy: 遗忘策略：importance_based(基于重要性)/time_based(基于时间)/capacity_based(基于容量)
            threshold: 遗忘阈值（importance_based时使用）
            max_age_days: 最大保留天数（time_based时使用）

        Returns:
            执行结果
        """
        try:
            count = self.memory_manager.forget_memories(
                strategy=strategy,
                threshold=threshold,
                max_age_days=max_age_days
            )
            return f"🧹 已遗忘 {count} 条记忆（策略: {strategy}）"
        except Exception as e:
            return f"❌ 遗忘记忆失败: {str(e)}"

    @tool_action("memory_clear", "清空所有记忆（危险操作，请谨慎使用）")
    def _clear_all(self) -> str:
        """清空所有记忆

        Returns:
            执行结果
        """
        try:
            self.memory_manager.clear_all_memories()
            return "🧽 已清空所有记忆"
        except Exception as e:
            return f"❌ 清空记忆失败: {str(e)}"

    @tool_action("memory_purge_engagement", "按engagement_id硬删除该engagement下的episodic记忆（危险操作，需用户显式触发，不会自动执行）")
    def _purge_engagement(self, engagement_id: str = "") -> str:
        """按engagement_id清空episodic记忆

        只清空episodic——semantic memory是从episodic归纳出的、脱离具体target/engagement后
        仍然成立的抽象知识，不会被这个操作连带清掉。

        Args:
            engagement_id: 要清空的engagement标识（必需）

        Returns:
            执行结果
        """
        if not engagement_id:
            return "❌ purge_engagement需要提供engagement_id"
        try:
            count = self.memory_manager.purge_episodic_by_engagement(engagement_id)
            return f"🧹 已清空 engagement_id={engagement_id} 下的 {count} 条episodic记忆"
        except Exception as e:
            return f"❌ 按engagement清空记忆失败: {str(e)}"
