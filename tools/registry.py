from tools.base import BaseTool
from typing import Any, Callable, Dict
class ToolRegistry:
    """
    HelloAgents工具注册表

    提供工具的注册、管理和执行功能。
    支持两种工具注册方式：
    1. Tool对象注册（推荐）
    2. 函数直接注册（简便）
    Reference: https://github.com/jjyaoao/HelloAgents/blob/main/hello_agents/tools/registry.py#L222
    """
    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._functions: dict[str, Dict[str, Any]] = {}

    def register_tool(self, tool: BaseTool):
        """注册Tool对象"""
        if tool.name in self._tools:
            print(f"⚠️ 警告:工具 '{tool.name}' 已存在，将被覆盖。")
        self._tools[tool.name] = tool
        print(f"✅ 工具 '{tool.name}' 已注册。")

    def register_function(self, name: str, description: str, func: Callable[[str], str]):
        """
        直接注册函数作为工具（简便方式）

        Args:
            name: 工具名称
            description: 工具描述
            func: 工具函数，接受字符串参数，返回字符串结果
        """
        if name in self._functions:
            print(f"⚠️ 警告:工具 '{name}' 已存在，将被覆盖。")

        self._functions[name] = {
            "description": description,
            "func": func
        }
        print(f"✅ 工具 '{name}' 已注册。")

    def unregister(self, name: str):
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            print(f"🗑️ 工具 '{name}' 已注销。")
        elif name in self._functions:
            del self._functions[name]
            print(f"🗑️ 工具 '{name}' 已注销。")
        else:
            print(f"⚠️ 工具 '{name}' 不存在。")

    def get_tools_description(self) -> str:
        """
        获取所有可用工具的格式化描述字符串

        Returns:
            工具描述字符串，用于构建提示词
        """
        descriptions = []

        # Tool对象描述
        for tool in self._tools.values():
            descriptions.append(f"- {tool.name}: {tool.description}")

        # 函数工具描述
        for name, info in self._functions.items():
            descriptions.append(f"- {name}: {info['description']}")

        return "\n".join(descriptions) if descriptions else "暂无可用工具"

    def execute_tool(self, name: str, input_text: str) -> ToolResponse:
        """
        执行工具，返回 ToolResponse 对象（带熔断器保护）

        Args:
            name: 工具名称
            input_text: 输入参数

        Returns:
            ToolResponse: 标准化的工具响应对象
        """
        response = None

        # 优先查找Tool对象
        if name in self._tools:
            tool = self._tools[name]
            try:
                # 解析参数（支持 JSON 字符串或字典）
                import json
                if isinstance(input_text, str):
                    try:
                        parameters = json.loads(input_text)
                    except json.JSONDecodeError:
                        # 如果不是 JSON，作为普通字符串处理
                        parameters = {"input": input_text}
                elif isinstance(input_text, dict):
                    parameters = input_text
                else:
                    parameters = {"input": str(input_text)}

                # 使用 run_with_timing 自动添加时间统计
                response = tool.run_with_timing(parameters)
            except Exception as e:
                response = ToolResponse.error(
                    code=ToolErrorCode.EXECUTION_ERROR,
                    message=f"执行工具 '{name}' 时发生异常: {str(e)}",
                    context={"tool_name": name, "input": input_text}
                )

        # 查找函数工具（自动包装为新协议）
        elif name in self._functions:
            func = self._functions[name]["func"]
            start_time = time.time()

            try:
                result = func(input_text)
                elapsed_ms = int((time.time() - start_time) * 1000)

                # 包装为 ToolResponse
                response = ToolResponse.success(
                    text=str(result),
                    data={"output": result},
                    stats={"time_ms": elapsed_ms},
                    context={"tool_name": name, "input": input_text}
                )
            except Exception as e:
                elapsed_ms = int((time.time() - start_time) * 1000)
                response = ToolResponse.error(
                    code=ToolErrorCode.EXECUTION_ERROR,
                    message=f"函数执行失败: {str(e)}",
                    stats={"time_ms": elapsed_ms},
                    context={"tool_name": name, "input": input_text}
                )

        # 工具不存在
        else:
            response = ToolResponse.error(
                code=ToolErrorCode.NOT_FOUND,
                message=f"未找到名为 '{name}' 的工具",
                context={"tool_name": name}
            )

        return response
    
