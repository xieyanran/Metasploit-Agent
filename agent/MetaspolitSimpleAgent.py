from typing import Optional, Iterator
from datetime import datetime
from core.agent import Agent
from core.message import Message
from core.config import Config
from core.llm import PentestAgentLLM
from agent.simple_agent import SimpleAgent
from agent.state import AgentState
from tools.registry import ToolRegistry
import re

# PTES阶段边界，用于engagement结束时的兜底归纳（DESIGN.md: Semantic memory时机设计）
_PTES_PHASES = ["recon", "vuln_analysis", "exploitation", "post_exploitation"]

class MetasploitSimpleAgent(SimpleAgent):
    """
    对话Agent，专门用于与Metasploit进行交互
    """
    def __init__(
        self,
        name: str,
        llm: PentestAgentLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        tool_registry: Optional['ToolRegistry'] = None,
        enable_tool_calling: bool = True

    ):
        super().__init__(name, llm, system_prompt, config)
        self.tool_registry = tool_registry
        self.enable_tool_calling = enable_tool_calling and tool_registry is not None
        # 贯穿整个engagement的运行状态（已发现资产、当前session、已配置的module等），
        # 需要在多次工具调用之间持久化，而不是每次调用临时创建
        self.state = AgentState()
        # engagement_id绑定本次agent进程生命周期，用于episodic/semantic记忆的项目级隔离
        # （_memory_extractor懒加载逻辑已提炼到Agent基类，见core/agent.py::_get_memory_extractor）
        self.engagement_id = f"engagement_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"✅ {name} 初始化完成，工具调用: {'启用' if self.enable_tool_calling else '禁用'}")

    def run(self, input_text: str, max_tool_iterations: int = 3, **kwargs) -> str:
        """
        重写的运行方法 - 实现简单对话逻辑，支持可选工具调用
        """
        print(f"🤖 {self.name} 正在处理: {input_text}")

        # 构建消息列表
        messages = []

        # 添加系统消息（可能包含工具信息）
        enhanced_system_prompt = self._get_enhanced_system_prompt()
        messages.append({"role": "system", "content": enhanced_system_prompt})

        # 添加历史消息
        for msg in self._history:
            messages.append({"role": msg.role, "content": msg.content})

        # 添加当前用户消息
        messages.append({"role": "user", "content": input_text})

        # 如果没有启用工具调用，使用简单对话逻辑
        if not self.enable_tool_calling:
            response = self.llm.invoke(messages, **kwargs)
            self.add_message(Message(input_text, "user"))
            self.add_message(Message(response, "assistant"))
            print(f"✅ {self.name} 响应完成")
            return response

        # 支持多轮工具调用的逻辑
        return self._run_with_tools(messages, input_text, max_tool_iterations, **kwargs)

    def _get_enhanced_system_prompt(self) -> str:
        """构建增强的系统提示词，包含工具信息"""
        base_prompt = self.system_prompt or "你是一个专用于与Metasploit进行交互的资深渗透测试工程师。"

        if not self.enable_tool_calling or not self.tool_registry:
            return base_prompt

        # 获取工具描述
        tools_description = self.tool_registry.get_tools_description()
        if not tools_description or tools_description == "暂无可用工具":
            return base_prompt

        tools_section = "\n\n## 可用工具\n"
        tools_section += "你可以使用以下工具来帮助回答问题:\n"
        tools_section += tools_description + "\n"

        tools_section += "\n## 工具调用格式\n"
        tools_section += "当需要使用工具时，请使用以下格式:\n"
        tools_section += "`[TOOL_CALL:{tool_name}:{parameters}]`\n"
        tools_section += "例如:`[TOOL_CALL:search:Python编程]` 或 `[TOOL_CALL:memory:recall=用户信息]`\n\n"
        tools_section += "工具调用结果会自动插入到对话中，然后你可以基于结果继续回答。\n"

        return base_prompt + tools_section

    def _run_with_tools(self, messages: list, input_text: str, max_tool_iterations: int, **kwargs) -> str:
        """
        支持工具调用的运行逻辑
        """
        current_iteration = 0
        final_response = ""

        while current_iteration < max_tool_iterations:
            # 调用LLM
            # ① Thought：LLM 先"想"
            response = self.llm.invoke(messages, **kwargs)

            # 检查是否有工具调用
            # ② Action：从文本里抠出 [TOOL_CALL:...] 当作要执行的动作
            tool_calls = self._parse_tool_calls(response)

            if tool_calls:
                print(f"🔧 检测到 {len(tool_calls)} 个工具调用")
                # 执行所有工具调用并收集结果

                tool_results = []
                clean_response = response

                for call in tool_calls:
                    # ③ Observation：真正执行动作，拿到环境反馈
                    result = self._execute_tool_call(call['tool_name'], call['parameters'])
                    tool_results.append(result)
                    # 从响应中移除工具调用标记
                    clean_response = clean_response.replace(call['original'], "")

                # 构建包含工具结果的消息
                messages.append({"role": "assistant", "content": clean_response})

                # 添加工具结果
                tool_results_text = "\n\n".join(tool_results)
                messages.append({"role": "user", "content": f"工具执行结果:\n{tool_results_text}\n\n请基于这些结果给出完整的回答。"})

                current_iteration += 1
                continue

            # 没有工具调用，这是最终回答
            final_response = response
            break

        # 如果超过最大迭代次数，获取最后一次回答
        if current_iteration >= max_tool_iterations and not final_response:
            final_response = self.llm.invoke(messages, **kwargs)

        # 保存到历史记录
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(final_response, "assistant"))
        print(f"✅ {self.name} 响应完成")

        return final_response

    def _parse_tool_calls(self, text: str) -> list:
        """解析文本中的工具调用"""
        pattern = r'\[TOOL_CALL:([^:]+):([^\]]+)\]'
        matches = re.findall(pattern, text)

        tool_calls = []
        for tool_name, parameters in matches:
            tool_calls.append({
                'tool_name': tool_name.strip(),
                'parameters': parameters.strip(),
                'original': f'[TOOL_CALL:{tool_name}:{parameters}]'
            })

        return tool_calls

    def _execute_tool_call(self, tool_name: str, parameters: str) -> str:
        """执行工具调用"""
        if not self.tool_registry:
            return f"❌ 错误:未配置工具注册表"

        output = self._run_tool_call(tool_name, parameters)
        self._extract_memories(tool_name, parameters, output)
        return output

    def _run_tool_call(self, tool_name: str, parameters: str) -> str:
        """实际执行工具调用，返回格式化后的结果/错误文本

        统一走 ToolRegistry.execute_tool(name, state, **kwargs) -> ToolResult，
        所有内置Metasploit工具与其他工具共用同一条路径，不再逐个工具名特判。
        """
        try:
            param_dict = self._parse_tool_parameters(tool_name, parameters)
            result = self.tool_registry.execute_tool(tool_name, self.state, **param_dict)
        except Exception as e:
            return f"❌ 工具调用失败:{str(e)}"

        if result.success:
            return f"🔧 工具 {tool_name} 执行结果:\n{result.output}"
        return f"❌ 工具调用失败:{result.message or result.output}"

    def _extract_memories(self, tool_name: str, parameters: str, output: str) -> None:
        """触发本轮工具调用对应的记忆写入：working memory自动直写 + episodic事件触发抽取

        实际的懒加载/写入逻辑已提炼到Agent基类的_record_tool_observation（三类Agent共用，
        见docs/DESIGN.md「复用点：避免三个Agent各写一套记忆接线代码」），这里只负责把
        本Agent当前状态（target/phase）转换成该方法需要的参数。
        """
        target_ref = self.state.target.address if self.state.target else None
        success = not output.startswith("❌")
        self._record_tool_observation(
            tool_name=tool_name,
            arguments=parameters,
            output=output,
            tool_success=success,
            target_ref=target_ref,
            phase=self.state.ptes_phase,
        )

    def set_ptes_phase(self, new_phase: str) -> None:
        """PTES阶段切换：先对上一阶段积累的episodic memory做一次归纳，再切换阶段

        调用方（编排层/规划agent）在检测到recon->vuln_analysis->exploitation->
        post_exploitation的阶段转换时调用，对应DESIGN.md的semantic memory时机设计。
        """
        target_ref = self.state.target.address if self.state.target else None
        super().set_ptes_phase(self.state, new_phase, target_ref)

    def finalize_engagement(self) -> None:
        """engagement结束兜底：确保PTES各阶段积累的episodic memory都至少归纳过一次semantic memory"""
        target_ref = self.state.target.address if self.state.target else None
        super().finalize_engagement(self.state, phases=_PTES_PHASES, target_ref=target_ref)

    def _parse_tool_parameters(self, tool_name: str, parameters: str) -> dict:
        """智能解析工具参数"""
        param_dict = {}

        if '=' in parameters:
            # 格式: key=value 或 action=search,query=Python
            if ',' in parameters:
                # 多个参数:action=search,query=Python,limit=3
                pairs = parameters.split(',')
                for pair in pairs:
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        param_dict[key.strip()] = value.strip()
            else:
                # 单个参数:key=value
                key, value = parameters.split('=', 1)
                param_dict[key.strip()] = value.strip()
        else:
            # 直接传入参数，根据工具类型智能推断
            if tool_name == 'search':
                param_dict = {'query': parameters}
            elif tool_name == 'memory':
                param_dict = {'action': 'search', 'query': parameters}
            else:
                param_dict = {'input': parameters}

        return param_dict

    
