"""
最小示例：连接本地 msfrpcd，给定一个目标 URL/host，跑一次 PlanSolveAgent 侦察阶段流程。

⚠️ 仅可对已获得授权的目标执行扫描。

前置条件：
1. 已启动 msfrpcd，务必加 -S（关闭 SSL）——metasploit/rpc.py 的 MetasploitRPCClient
   目前只支持明文 HTTP，不加 -S 会连接被重置，例如：
     msfrpcd -P 123456 -U msf -a 127.0.0.1 -p 55554 -S
2. .env 中已配置 MSF_RPC_HOST/MSF_RPC_PORT/MSF_RPC_USERNAME/MSF_RPC_PASSWORD，
   且端口与实际启动 msfrpcd 时用的 -p 一致
   （不传参数时 MetasploitRPCClient 会自动读取 .env 里的这几个变量）
3. .env 中已配置 LLM_MODEL_ID/LLM_API_KEY/LLM_BASE_URL

用法：
    python examples/run_plan_solve_agent.py <目标URL或host>
    python examples/run_plan_solve_agent.py            # 使用下面的 DEFAULT_TARGET
"""
import sys
from pathlib import Path
from urllib.parse import urlparse

# 让脚本可以直接用 `python examples/run_plan_solve_agent.py` 运行，
# 而不必是 `python -m examples.run_plan_solve_agent`
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from metasploit.rpc import MetasploitRPCClient
from metasploit.client import MetasploitClient
from metasploit.exceptions import MetasploitError
from tools.registry import ToolRegistry
from tools.builtin import register_builtin_tools
from core.llm import PentestAgentLLM
from core.scope import EngagementScope
from agent.reconnaissance_planandsolve_agent import PlanSolveAgent

DEFAULT_TARGET = "http://example.com"  # 换成已获得授权的测试目标


def resolve_host(url_or_host: str) -> str:
    """接受完整 URL 或裸 host/IP，统一提取出 nmap_scan 可用的 host。"""
    parsed = urlparse(url_or_host)
    return parsed.hostname or url_or_host


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_TARGET
    host = resolve_host(target)

    print(f"🎯 目标: {target}  ->  host: {host}")
    print("⚠️ 请确认已获得对该目标的合法测试授权。\n")

    # 1. 连接本地 msfrpcd（host/port/username/password 从 .env 里的
    #    MSF_RPC_HOST/MSF_RPC_PORT/MSF_RPC_USERNAME/MSF_RPC_PASSWORD 自动读取）
    try:
        rpc = MetasploitRPCClient()
        client = MetasploitClient(rpc)
        version_info = client.core.version()
        print(f"✅ 已连接 msfrpcd {rpc.host}:{rpc.port}，framework version: {version_info}")
    except MetasploitError as e:
        print(f"❌ 无法连接 msfrpcd（{e}）。请确认 msfrpcd 已启动，且 .env 里的 "
              "MSF_RPC_HOST/MSF_RPC_PORT/MSF_RPC_USERNAME/MSF_RPC_PASSWORD 与其一致。")
        return

    # 1.5. 加载 engagement scope（scope.json，见 scope.example.json）。
    #      文件不存在时 fail closed：任何目标都会被 scope 护栏拒绝，而不是放行。
    scope = EngagementScope.load()
    print(f"🔒 已加载 scope：{len(scope.entries)} 条授权记录（来源: {scope.source}）")
    if not scope.entries:
        print("   ⚠️ scope 为空，所有目标都会被拒绝。请 cp scope.example.json scope.json 并配置授权目标。")

    # 2. 注册侦察阶段能用到的工具（当前只有 nmap_scan 会被 Planner 用到，
    #    其余利用类工具会被 system prompt 明确禁止调用，但仍会一并注册进 registry）
    registry = ToolRegistry()
    register_builtin_tools(registry, client, scope)

    # 3. 构造 LLM 客户端（provider/model/key 从 .env 自动解析）
    llm = PentestAgentLLM()

    # 4. 构造并运行 PlanSolveAgent
    agent = PlanSolveAgent(name="recon_plan_solve", llm=llm, tool_registry=registry)
    result = agent.run(f"对目标 {host} 进行一次基础的端口和服务扫描，输出结构化资产清单。")

    print("\n================= 最终结果 =================")
    print(result)


if __name__ == "__main__":
    main()
