"""记忆工具

为HelloAgents框架提供记忆能力的工具实现。
可以作为工具添加到任何Agent中，让Agent具备记忆功能。
Reference: https://github.com/jjyaoao/HelloAgents/blob/learn_version/hello_agents/tools/builtin/memory_tool.py
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from ..base import BaseTool, ToolParameter, tool_action
from memory import MemoryManager, MemoryConfig



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

    
    