"""记忆系统的字段级枚举约束

DESIGN.md 反复强调 episodic 记忆要区分"技术性失败"（目标本身不可利用）与
"操作性失败"（网络不通/RPC超时/参数错误等环境原因，不代表目标不可利用），
但此前 outcome 只是一个自由字符串 + 仅告警的校验，调用方传错值（拼写错误、
把一次RPC超时误记成负面结论）不会被拒绝，只在日志里 warning 一下就照样落库。
这里把它收紧为真正的枚举，配合 MemoryManager._validate_common_metadata 做
强制校验（而非仅告警），从类型层面堵住这类误判。
"""
from enum import Enum


class Outcome(str, Enum):
    """episodic 事件结果"""

    SUCCESS = "success"
    TECH_FAIL = "tech_fail"
    OP_FAIL = "op_fail"
    NEGATIVE = "negative"
