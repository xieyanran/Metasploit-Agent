from tools.base import BaseTool
from typing import Any, Callable, Dict, List, Optional
from agent.state import AgentState
from agent.models import ToolResult
# Reference: https://github.com/jjyaoao/HelloAgents/blob/learn_version/hello_agents/tools/registry.py
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

    # 对外查询接口
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取工具函数"""
        return self._tools.get(name)

    def get_all_tools(self) -> List[BaseTool]:
        """获取所有已注册的 Tool 对象（不含 register_function 注册的函数式工具）"""
        return list(self._tools.values())

    def get_function(self, name: str) -> Optional[Callable]:
        """获取工具函数"""
        func_info = self._functions.get(name)
        return func_info["func"] if func_info else None

    def to_function_schemas(self) -> List[Dict[str, Any]]:
        """把所有已注册的Tool对象转换成OpenAI Function Calling的tools schema列表。

        提炼出来的共用方法：PostReconReActAgent（vuln_analysis/exploitation/
        post_exploitation三阶段共用的ReAct循环）和
        Reconnaissance_planandsolve_agent.py::Executor（侦察阶段Plan-and-Solve的
        逐步执行器）都需要"把注册表里的工具转成Function Calling schema"这个能力，
        之前各写一份容易漂移，见docs/DESIGN.md「复用点」。不包含Thought/Finish这类
        ReAct专属的内置工具schema——那些由调用方自己在返回结果前追加。
        """
        return [self._tool_to_schema(tool) for tool in self._tools.values()]

    @staticmethod
    def _tool_to_schema(tool: BaseTool) -> Dict[str, Any]:
        """将单个BaseTool转换为Function Calling schema"""
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for param in tool.get_parameters():
            properties[param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }

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

    def execute_tool(self, name: str, state: Optional[AgentState] = None, **kwargs) -> ToolResult:
        """
        执行工具

        Args:
            name: 工具名称
            state: 当前Agent运行状态
            **kwargs: 工具所需的具体参数

        Returns:
            ToolResult: 标准化的工具执行结果
        """
        # 优先查找Tool对象
        if name in self._tools:
            tool = self._tools[name]
            try:
                return tool.execute(state, **kwargs)
            except Exception as e:
                return ToolResult(
                    tool=name,
                    success=False,
                    output=None,
                    message=f"执行工具 '{name}' 时发生异常: {str(e)}",
                )

        # 查找函数工具（简便注册方式，只接受单个字符串输入）
        if name in self._functions:
            func = self._functions[name]["func"]
            input_text = kwargs.get("input", "")
            try:
                result = func(input_text)
                return ToolResult(tool=name, success=True, output=result)
            except Exception as e:
                return ToolResult(
                    tool=name,
                    success=False,
                    output=None,
                    message=f"函数执行失败: {str(e)}",
                )

        # 工具不存在
        return ToolResult(
            tool=name,
            success=False,
            output=None,
            message=f"未找到名为 '{name}' 的工具",
        )
    
