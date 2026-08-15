"""Agent基类"""
from abc import ABC, abstractmethod
from typing import Optional, Any, List
from .message import Message
from .llm import PentestAgentLLM
from .config import Config

class Agent(ABC):
    """Agent基类"""

    def __init__(
        self,
        name: str,
        llm: PentestAgentLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        tool_registry: Optional[Any] = None
    ):
        self.name = name
        self.llm = llm
        self.system_prompt = system_prompt
        self.config = config or Config()
        self.tool_registry = tool_registry
        self._history: list[Message] = []
        # engagement_id绑定本次agent的记忆写入边界（episodic检索/隔离的唯一安全边界，
        # 见docs/DESIGN.md「ReAct利用阶段 × Context/Memory 融合设计」）；不在这里自动生成，
        # 由持有engagement概念的具体子类（如PostReconReActAgent/MetaspolitSimpleAgent）设置，
        # 不需要engagement概念的子类（如纯对话SimpleAgent）留空即可，不影响其余功能
        self.engagement_id: Optional[str] = None
        self._memory_extractor = None

    @abstractmethod
    def run(self, input_text: str, **kwargs) -> str:
        """运行Agent"""
        pass

    def _get_memory_extractor(self):
        """懒加载MemoryExtractor：复用工具注册表里"memory"工具已初始化的MemoryManager。

        提炼自MetaspolitSimpleAgent的原有实现，作为三类Agent共用的记忆接线点（见DESIGN.md
        「复用点：避免三个Agent各写一套记忆接线代码」），子类只需要在合适的时机调用
        _record_tool_observation，不需要各自重复实现"怎么拿到MemoryExtractor"这段逻辑。
        """
        if not self.tool_registry:
            return None
        memory_tool = self.tool_registry.get_tool("memory")
        if memory_tool is None:
            return None
        if self._memory_extractor is None:
            from memory.extraction import MemoryExtractor
            self._memory_extractor = MemoryExtractor(
                memory_manager=memory_tool.memory_manager,
                llm=self.llm,
                engagement_id=self.engagement_id,
            )
        return self._memory_extractor

    def _record_tool_observation(
        self,
        tool_name: str,
        arguments: str,
        output: str,
        tool_success: bool,
        target_ref: Optional[str],
        phase: str,
        session_id: Optional[str] = None,
    ) -> None:
        """把一次工具调用的Action+Observation写入记忆：working无条件直写 + episodic事件触发抽取。

        target_ref的提取方式由调用方（子类）决定——recon阶段和利用阶段"当前操作对象是谁"
        的取法不同（例如利用阶段要落到host粒度而不是笼统的顶层target），本方法只负责
        统一的写入路径，不对target_ref做任何推断。
        """
        extractor = self._get_memory_extractor()
        if extractor is None:
            return
        extractor.log_working_memory(tool_name, arguments, output)
        extractor.maybe_extract_episodic(
            tool_name=tool_name,
            output_text=output,
            tool_success=tool_success,
            target_ref=target_ref,
            phase=phase,
            session_id=session_id,
        )

    def set_ptes_phase(self, state, new_phase: str, target_ref: Optional[str] = None) -> None:
        """PTES阶段切换：先对上一阶段积累的episodic memory做一次归纳，再切换阶段。

        触发时机的判断权不在这里——调用方（编排层，或子类在能确定阶段边界时）决定
        什么时候调用，本方法只负责"切换时该做什么"，见DESIGN.md「PTES phase切换：
        触发权归编排层，Agent只暴露hook」。
        """
        old_phase = getattr(state, "ptes_phase", None)
        if old_phase == new_phase:
            return
        extractor = self._get_memory_extractor()
        if extractor is not None and old_phase:
            extractor.consolidate_phase_async(old_phase, target_ref)
        state.ptes_phase = new_phase

    def finalize_engagement(self, state, phases: List[str], target_ref: Optional[str] = None) -> None:
        """engagement结束兜底：确保每个PTES阶段积累的episodic memory都至少归纳过一次semantic memory"""
        extractor = self._get_memory_extractor()
        if extractor is not None:
            extractor.finalize_engagement(phases=phases, target_ref=target_ref)
    
    def add_message(self, message: Message):
        """添加消息到历史记录"""
        self._history.append(message)
    
    def clear_history(self):
        """清空历史记录"""
        self._history.clear()
    
    def get_history(self) -> list[Message]:
        """获取历史记录"""
        return self._history.copy()
    
    def __str__(self) -> str:
        return f"Agent(name={self.name}, provider={self.llm.provider})"