from typing import Optional, Iterator
from core.agent import Agent
from core.message import Message
from core.config import Config
from core.llm import PentestAgentLLM
from agent.simple_agent import SimpleAgent
from tools.registry import ToolRegistry
import re

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

            if not tool_calls:
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

        try:
            # 智能参数解析
            if tool_name == 'execute_session':
                # ExecuteSession工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            elif tool_name == 'info_module':
                # InfoModule工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            elif tool_name == 'kill_meterpreter_session':
                # KillMeterpreterSession工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            elif tool_name == 'list_session':
                # ListSession工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            elif tool_name == 'nmap_scan':
                # NmapScan工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            elif tool_name == 'run_module':
                # RunModule工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            elif tool_name == 'search_module':
                # SearchModule工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            elif tool_name == 'set_option':
                # SetOption工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            elif tool_name == 'show_option':
                # ShowOption工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            elif tool_name == 'compatible_payloads':
                # CompatiblePayloads工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            elif tool_name == 'shell_upgrade':
                # ShellUpgrade工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            elif tool_name == 'session_compatible_modules':
                # SessionCompatibleModules工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            elif tool_name == 'list_jobs':
                # ListJobs工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            elif tool_name == 'job_info':
                # JobInfo工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            elif tool_name == 'stop_job':
                # StopJob工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            elif tool_name == 'stop_session':
                # StopSession工具直接传入表达式
                result = self.tool_registry.execute_tool(tool_name, parameters)
            else:
                # 其他工具使用智能参数解析
                param_dict = self._parse_tool_parameters(tool_name, parameters)
                tool = self.tool_registry.get_tool(tool_name)
                if not tool:
                    return f"❌ 错误:未找到工具 '{tool_name}'"
                result = tool.run(param_dict)

            return f"🔧 工具 {tool_name} 执行结果:\n{result}"

        except Exception as e:
            return f"❌ 工具调用失败:{str(e)}"

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

    
