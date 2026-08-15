"""
Plan and Solve Agent实现 - 在渗透测试中的侦查与信息收集阶段，分解规划与逐步执行的智能体
Reference: https://github.com/jjyaoao/HelloAgents/blob/main/hello_agents/agents/plan_solve_agent.py
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable, AsyncGenerator
from core.llm import PentestAgentLLM
from core.agent import Agent
from core.message import Message
from core.config import Config
from core.streaming import StreamEvent, StreamEventType
from core.lifecycle import LifecycleHook
from tools.registry import ToolRegistry
from agent.state import AgentState
from context.builder import ContextBuilder

# PTES阶段边界，用于engagement结束时的兜底归纳（DESIGN.md: Semantic memory时机设计）
_PTES_PHASES = ["recon", "vuln_analysis", "exploitation", "post_exploitation"]

# 侦察阶段计划偏差上报标记，取值必须与post_recon_react_agent.py的_REPLAN_MARKER保持一致，
# 是编排层识别"⚠️ REPLAN_NEEDED"信号的统一约定
_REPLAN_MARKER = "⚠️ REPLAN_NEEDED:"

# 侦察阶段工具参数里表示扫描目标的key（nmap_scan用的是target；其余是未来新增工具可能
# 出现的等价写法），按顺序尝试提取target_ref
_HOST_ARG_KEYS = ("target", "TARGET", "host", "ip", "address", "RHOSTS")

RECON_PLANNER_SYSTEM_PROMPT = """你是一名资深渗透测试工程师，当前处于 PTES 方法论的「情报收集」（Intelligence Gathering）阶段。

## 角色与目标
你的唯一目标是围绕给定的目标（IP/域名/网段）建立一份准确、可验证的资产清单（Target → Host → Port → Service），
为后续的「威胁建模/漏洞分析」与「利用」阶段提供输入。你不负责漏洞利用、载荷投递或会话管理——那是后续阶段的职责。

## 已知背景
用户问题之前如果附带一段背景信息，那是系统基于本次 engagement 已发现的资产、以及历史相似场景下的
经验教训自动整理的（例如"该目标此前已扫描过，22/tcp 已确认开放 OpenSSH"）。制定计划时请优先参考，
避免安排重复扫描已经确认过的内容。

## 可用工具边界
执行器在本阶段只能使用信息收集类工具（如端口/服务扫描 nmap_scan，后续可能接入子域名枚举、WHOIS/DNS 查询、
HTTP 指纹识别等）。规划时：
- 只能拆解为这一类工具能完成的、或纯推理/归纳类的步骤；
- 严禁生成任何涉及模块检索、载荷配置、漏洞利用、会话/任务管理的步骤（例如 search_module、run_module、
set_option、execute_session、session/job 管理类操作）——这些属于利用阶段，此处出现即视为越界。

## 步骤设计要求（generate_plan 已强制输出为 string 数组，但每个 step 字符串必须满足）
1. 明确写出本步骤要收集的具体对象（如「探测目标存活主机与开放端口」而非笼统的「进行侦查」）；
2. 步骤之间存在逻辑依赖顺序（先发现主机 → 再扫描端口 → 再识别服务/版本 → 最后归纳整理），
后一步骤可引用前一步骤的产出；
3. 计划的最后一步固定为「汇总所有发现，整理成结构化资产清单」；
4. 步骤总数控制在 3~7 步，避免过度拆解带来不必要的 LLM/工具调用开销。

## 重要提醒
- 目标范围以用户输入中给出的地址/网段为准，不得擅自扩大扫描范围；
- 若某一步的产出可能使后续步骤失效或需要新增步骤，不在这里处理——你只负责生成初始计划，
偏差处理由执行阶段负责触发重规划。
"""

RECON_EXECUTOR_SYSTEM_PROMPT = """你是一名资深渗透测试工程师，正在执行「情报收集」阶段计划中的某一具体步骤。

## 角色与目标
严格按照给定的当前步骤行动，只做信息收集，不做任何利用性操作。你的输出会被后续步骤引用，
并最终汇总为结构化资产清单，因此每一步的结果必须准确、可复用。

## 可用工具
你只能调用信息收集类工具（当前包括 nmap_scan，用于发现目标存活主机、开放端口与服务版本；
后续可能新增 whois/DNS/子域名枚举/HTTP 指纹识别工具）。
- 禁止调用 search_module、run_module、set_option、show_option、execute_session、
compatible_payloads、shell_upgrade，以及任何 session/job 管理类工具——即便工具注册表中存在，
也不属于本阶段职责，不要调用。
- 如果当前步骤确实需要利用类操作才能完成，说明步骤设计有误，请直接说明
⚠️ 该步骤超出侦查阶段职责范围，无法在当前工具集下完成」，不要强行调用越权工具。

## 记忆工具的使用
如果工具列表中包含 memory 工具，允许（也鼓励）调用它：
- 用 memory(action=search, ...) 查询该目标是否已经扫描过、已知端口/服务是什么，避免对同一目标
重复扫描——扫描类操作有真实的时间与网络开销，重复执行会拖慢整个engagement的进度。
- 若某一步的阴性结果（端口关闭、未发现存活主机等）值得记录，可用 memory(action=add, ...) 主动补充，
不必等待系统自动判断。

## 输出格式
每次执行完当前步骤后，用如下结构汇报（可省略未发现的字段）：
- 目标/主机: <address>
- 发现端口: <port>/<protocol> (<state>)
- 服务: <service name> <product> <version>
- 其他线索: <banner/技术栈/证书信息等>
- 结论: 一句话总结本步骤对整体资产清单的贡献

## 重要提醒
- 只扫描/查询用户明确给出范围内的目标，不得扩大范围；
- 若发现与原计划预期不符（目标不可达、出现计划外的主机/服务、结果提示需调整后续步骤等），
必须在结果开头加标记：`⚠️ REPLAN_NEEDED: <一句话说明偏差原因>`；没有偏差则不加此标记；
- 只客观陈述工具返回的事实，不要臆测未被工具证实的漏洞或版本信息。
"""

# 每次工具结果之后的观测回调：(tool_name, arguments字典, 结果文本, 是否成功) -> None
ToolObservationCallback = Callable[[str, Dict[str, Any], str, bool], None]


class Planner:
    """
    规划器 - 负责将复杂问题分解为简单步骤（使用 Function Calling）
    """

    def __init__(
        self,
        llm_client: PentestAgentLLM,
        system_prompt: Optional[str] = None,
    ):
        self.llm_client = llm_client
        self.system_prompt = system_prompt or RECON_PLANNER_SYSTEM_PROMPT

    def plan(self, question: str, memory_context: Optional[str] = None, **kwargs) -> List[str]:
        """""
        生成执行计划（使用 Function Calling）

        Args:
            question: 要解决的问题
            memory_context: ContextBuilder生成的背景信息（已发现资产/相关经验），作为规划前的
                一次性framing插入system_prompt和实际问题之间；不传则按原逻辑直接生成计划
            **kwargs: LLM调用参数

        Returns:
            步骤列表
        """
        print("--- 正在生成计划 ---")

        # 定义计划生成工具
        plan_tool = {
            "type": "function",
            "function": {
                "name": "generate_plan",
                "description": "生成解决问题的分步计划",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "steps": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "按顺序排列的执行步骤列表"
                        }
                    },
                    "required": ["steps"]
                }
            }
        }

        messages = [{"role": "system", "content": self.system_prompt}]
        if memory_context:
            messages.append({"role": "user", "content": memory_context})
        messages.append({"role": "user", "content": f"请为以下问题生成详细的执行计划：\n\n{question}"})

        try:
            response = self.llm_client.invoke_with_tools(
                messages=messages,
                tools=[plan_tool],
                tool_choice={"type": "function", "function": {"name": "generate_plan"}},
                **kwargs
            )

            # 提取工具调用结果
            if response.tool_calls:
                tool_call = response.tool_calls[0]
                arguments = json.loads(tool_call.arguments)
                plan = arguments.get("steps", [])

                print(f"✅ 计划已生成:")
                for i, step in enumerate(plan, 1):
                    print(f"  {i}. {step}")

                return plan
            else:
                print("❌ 模型未返回计划工具调用")
                return []

        except Exception as e:
            print(f"❌ 生成计划时发生错误: {e}")
            return []

class Executor:
    """
    执行器 - 负责按计划逐步执行（支持Function Calling）
    """

    def __init__(
        self,
        llm_client: PentestAgentLLM,
        system_prompt: Optional[str] = None,
        tool_registry: Optional['ToolRegistry'] = None,
        enable_tool_calling: bool = True,
        max_tool_iterations: int = 3,
        on_tool_observation: Optional[ToolObservationCallback] = None,
    ):
        self.llm_client = llm_client
        self.system_prompt = system_prompt or RECON_EXECUTOR_SYSTEM_PROMPT
        self.tool_registry = tool_registry
        self.enable_tool_calling = enable_tool_calling and tool_registry is not None
        self.max_tool_iterations = max_tool_iterations
        # 每次工具结果之后的观测回调，由持有Agent（PlanSolveAgent）传入，用来把Observation
        # 写入记忆——Executor本身不是Agent子类，不直接持有MemoryExtractor，见DESIGN.md
        # 「复用点」一节里对Plan-and-Solve落地方式的说明
        self.on_tool_observation = on_tool_observation

    def execute(
        self,
        question: str,
        plan: List[str],
        state: Optional[AgentState] = None,
        memory_context: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        按计划执行任务（支持 Function Calling）

        Args:
            question: 原始问题
            plan: 执行计划
            state: Agent运行状态，透传给每次工具调用（ToolRegistry.execute_tool需要）
            memory_context: ContextBuilder生成的背景信息，只在run()开始时计算一次，
                随后原样重复嵌入每一步的context文本里——Plan-and-Solve每一步都是从零
                构建的独立messages（不像ReAct有持续的消息数组），所以"只查一次记忆"
                这个原则在这里是通过"只算一次memory_context字符串、每步复用"实现的，
                而不是每步重新调用ContextBuilder
            **kwargs: LLM调用参数

        Returns:
            最终答案
        """
        history = []
        final_answer = ""

        print("\n--- 正在执行计划 ---")
        for i, step in enumerate(plan, 1):
            print(f"\n-> 执行步骤 {i}/{len(plan)}: {step}")

            # 构建上下文消息
            background_section = f"# 已知背景（记忆系统提供，仅供参考）：\n{memory_context}\n\n" if memory_context else ""
            context = f"""{background_section}# 原始问题：

{question}

# 完整计划：
{self.__format_plan(plan)}

# 历史步骤与结果:
{self._format_history(history) if history else "无"}

# 当前步骤:
{step}

请执行当前步骤并给出结果。
"""
            # 执行单个步骤（支持工具调用）
            response_text = self._execute_step(context, state, **kwargs)

            history.append({"step": step, "result": response_text})
            final_answer = response_text
            print(f"✅ 步骤 {i} 已完成，结果: {final_answer}")

        return final_answer

    def __format_plan(self, plan: List[str]) -> str:
        """格式化计划列表"""
        return "\n".join([f"{i}. {step}" for i, step in enumerate(plan)])

    def _format_history(self, history: List[Dict[str, str]]) -> str:
        """格式化历史记录"""
        return "\n\n".join([f"步骤 {i}: {h['step']}\n结果: {h['result']}"
                            for i, h in enumerate(history, 1)])

    def _execute_step(self, context: str, state: Optional[AgentState], **kwargs) -> str:
        """
        执行单个步骤（支持 Function Calling）

        Args:
            context: 上下文信息
            state: Agent运行状态，透传给工具执行
            **kwargs: 其他参数

        Returns:
            步骤执行结果
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": context}
        ]

        # 如果没有启用工具调用，直接返回
        if not self.enable_tool_calling or not self.tool_registry:
            llm_response = self.llm_client.invoke(messages, **kwargs)
            return llm_response.content if hasattr(llm_response, 'content') else str(llm_response)

        # 启用工具调用模式：直接复用ToolRegistry.to_function_schemas()构建schema、
        # ToolRegistry.execute_tool()执行工具，不再借用SimpleAgent实例
        tool_schemas = self.tool_registry.to_function_schemas()

        current_iteration = 0

        while current_iteration < self.max_tool_iterations:
            current_iteration += 1

            try:
                response = self.llm_client.invoke_with_tools(
                    messages=messages,
                    tools=tool_schemas,
                    tool_choice="auto",
                    **kwargs
                )
            except Exception as e:
                print(f"❌ LLM 调用失败: {e}")
                return f"抱歉，执行该步骤时发生错误：{e}"

            # 处理工具调用
            tool_calls = response.tool_calls
            if not tool_calls:
                # 没有工具调用，返回文本响应
                return response.content or ""

            # 将助手消息添加到历史
            messages.append({
                "role": "assistant",
                "content": response.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.name,
                            "arguments": tc.arguments
                        }
                    }
                    for tc in tool_calls
                ]
            })

            # 执行所有工具调用
            for tool_call in tool_calls:
                tool_name = tool_call.name
                tool_call_id = tool_call.id

                try:
                    arguments = json.loads(tool_call.arguments)
                except json.JSONDecodeError as e:
                    print(f"❌ 工具参数解析失败: {e}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": f"错误：参数格式不正确 - {str(e)}"
                    })
                    continue

                # 执行工具
                print(f"🔧 调用工具: {tool_name}({arguments})")
                result = self.tool_registry.execute_tool(tool_name, state, **arguments)
                result_text = str(result.output) if result.success else f"❌ {result.message or result.output}"
                print(f"   -> {result_text}")

                # Observation -> Memory：交给持有Agent传入的回调处理（Executor自己
                # 不持有MemoryExtractor，见__init__的说明）
                if self.on_tool_observation is not None:
                    self.on_tool_observation(tool_name, arguments, result_text, result.success)

                # 添加工具结果到消息
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": result_text
                })

        # 超过最大迭代次数仍未得到文本回答，退回一次不带工具的调用作为兜底
        llm_response = self.llm_client.invoke(messages, **kwargs)
        return llm_response.content if hasattr(llm_response, 'content') else str(llm_response)

class PlanSolveAgent(Agent):
    """
    Plan and Solve Agent - 分解规划与逐步执行的智能体

    这个Agent能够：
    1. 将复杂问题分解为简单步骤（使用 Function Calling）
    2. 按照计划逐步执行
    3. 维护执行历史和上下文
    4. 得出最终答案
    5. 支持工具调用（可选）
    6. 与 Context/Memory 系统融合（见 docs/DESIGN.md「ReAct利用阶段 × Context/Memory 融合设计」，
    侦察阶段沿用同一套融合思路）：规划前用 ContextBuilder 生成一次背景 framing（避免安排
    重复扫描），每次工具结果之后自动写入 working/episodic memory，计划偏差会落对应的记忆

    特别适合多步骤推理、数学问题、复杂分析等任务。
    """
    def __init__(
        self,
        name: str,
        llm: PentestAgentLLM,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        planner_prompt: Optional[str] = None,
        executor_prompt: Optional[str] = None,
        tool_registry: Optional['ToolRegistry'] = None,
        enable_tool_calling: bool = True,
        max_tool_iterations: int = 3,
        state: Optional[AgentState] = None,
        engagement_id: Optional[str] = None,
    ):
        """
        初始化PlanSolveAgent

        Args:
            name: Agent名称
            llm: LLM实例
            system_prompt: 系统提示词（Agent级别）
            config: 配置对象
            planner_prompt: 规划器的系统提示词（可选，默认使用 RECON_PLANNER_SYSTEM_PROMPT）
            executor_prompt: 执行器的系统提示词（可选，默认使用 RECON_EXECUTOR_SYSTEM_PROMPT）
            tool_registry: 工具注册表（可选）
            enable_tool_calling: 是否启用工具调用
            max_tool_iterations: 最大工具调用迭代次数
            state: 贯穿本次侦察任务的运行状态；不传则新建一个空的AgentState。由编排层在
                跨阶段调用多个Agent时传入同一个state，才能让target/PTES阶段在
                recon->exploitation->post_exploitation之间保持连续
            engagement_id: 项目级作用域标识，episodic记忆检索的唯一安全边界；不传则按
                当前时间自动生成一个（与PostReconReActAgent/MetaspolitSimpleAgent的做法一致）
        """
        # 传递 tool_registry 到基类
        super().__init__(
            name,
            llm,
            system_prompt,
            config,
            tool_registry=tool_registry
        )

        # 贯穿本次侦察任务的运行状态，供工具执行与记忆写入使用
        self.state = state or AgentState()
        # 覆盖Agent基类里默认的None：本Agent对应PTES侦察阶段，天然持有engagement概念
        self.engagement_id = engagement_id or f"engagement_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        self.planner = Planner(self.llm, planner_prompt)
        self.executor = Executor(
            self.llm,
            executor_prompt,
            tool_registry=tool_registry,
            enable_tool_calling=enable_tool_calling,
            max_tool_iterations=max_tool_iterations,
            on_tool_observation=self._on_tool_observation,
        )

        # ContextBuilder懒加载，见_get_context_builder
        self._context_builder: Optional[ContextBuilder] = None

    def run(self, input_text: str, **kwargs) -> str:
        """
        运行Plan and Solve Agent

        Args:
            input_text: 要解决的问题
            **kwargs: 其他参数

        Returns:
            最终答案
        """
        print(f"\n🤖 {self.name} 开始处理问题: {input_text}")

        # 0. 规划前framing：把本次engagement已发现的资产、相关经验一次性取出来，
        # 分别喂给Planner（避免安排重复扫描）和Executor（每步都能看到，见Executor.execute
        # 的memory_context参数说明）。只计算一次，不在每一步/每次规划里重复查询
        memory_context = self._build_memory_context(input_text)

        # 1. 生成计划
        plan = self.planner.plan(input_text, memory_context=memory_context, **kwargs)
        if not plan:
            final_answer = "无法生成有效的行动计划，任务终止。"
            print(f"\n--- 任务终止 ---\n{final_answer}")

            # 保存到历史记录
            self.add_message(Message(input_text, "user"))
            self.add_message(Message(final_answer, "assistant"))

            return final_answer

        # 2. 执行计划
        final_answer = self.executor.execute(
            input_text, plan, self.state, memory_context=memory_context, **kwargs
        )
        print(f"\n--- 任务完成 ---\n最终答案: {final_answer}")

        # 计划偏差信号：本身也要落一条episodic记忆，否则"当时为什么改了计划"这条
        # 复盘线索会随会话结束而丢失（与利用阶段ReAct的处理方式一致，见docs/DESIGN.md）
        if final_answer and final_answer.strip().startswith(_REPLAN_MARKER):
            self._record_replan_signal(final_answer)

        # 保存到历史记录
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(final_answer, "assistant"))

        return final_answer

    def _get_context_builder(self) -> Optional[ContextBuilder]:
        """懒加载ContextBuilder：复用工具注册表里"memory"工具已初始化的MemoryManager。

        没有注册memory工具时返回None，调用方（_build_memory_context）退化为不做记忆
        检索，不影响Agent的基本可用性。
        """
        if not self.tool_registry:
            return None
        memory_tool = self.tool_registry.get_tool("memory")
        if memory_tool is None:
            return None
        if self._context_builder is None:
            self._context_builder = ContextBuilder(memory_tool=memory_tool, llm=self.llm)
        return self._context_builder

    def _build_memory_context(self, input_text: str) -> Optional[str]:
        """在run()开始时调用一次，生成结构化背景文本（[State]/[Evidence]等分区），
        分别喂给Planner.plan()和Executor.execute()。不可用/失败时返回None，调用方
        据此退化为不带背景的原始行为。
        """
        builder = self._get_context_builder()
        if builder is None:
            return None
        try:
            return builder.build(
                user_query=input_text,
                state=self.state,
                engagement_id=self.engagement_id,
                conversation_history=self.get_history(),
                system_instructions=None,
            )
        except Exception as e:
            print(f"⚠️ 上下文构建失败，退化为无背景规划/执行: {e}")
            return None

    def _extract_target_ref(self, arguments: Dict[str, Any]) -> Optional[str]:
        """从工具调用参数里提取target_ref，取不到时兜底到state.target.address。

        侦察阶段的nmap_scan等工具用的参数名是target（见tools/builtin/nmap_scan.py），
        与利用阶段run_module等工具的RHOSTS不同，按侦察阶段实际的工具集调整取值顺序。
        """
        for key in _HOST_ARG_KEYS:
            value = arguments.get(key)
            if value:
                return str(value).split(",")[0].strip()
        if self.state.target:
            return self.state.target.address
        return None

    def _on_tool_observation(
        self, tool_name: str, arguments: Dict[str, Any], output: str, success: bool
    ) -> None:
        """Executor每次工具结果之后的回调：写入working memory + 触发episodic抽取。

        实际的懒加载/写入逻辑复用Agent基类的_record_tool_observation（与PostReconReActAgent
        共用同一套，见core/agent.py），这里只负责把Executor传回的原始参数转换成该方法
        需要的形式。
        """
        self._record_tool_observation(
            tool_name=tool_name,
            arguments=json.dumps(arguments, ensure_ascii=False),
            output=output,
            tool_success=success,
            target_ref=self._extract_target_ref(arguments),
            phase=self.state.ptes_phase,
            session_id=self.engagement_id,
        )

    def _record_replan_signal(self, final_answer: str) -> None:
        """把侦察阶段的计划偏差信号（⚠️ REPLAN_NEEDED）落一条episodic记忆。

        event_type用recon_negative——侦察阶段的偏差通常是"预期的资产/结果没有出现"
        （目标不可达、计划外主机等），比exploitation阶段更贴近defense_observed的场景
        更接近这个既有分类，而不是新造一个类型。同步写入、不走异步LLM判断路径，理由
        与PostReconReActAgent._record_replan_signal一致：这个信号本身已经是LLM判断过的事实。
        """
        extractor = self._get_memory_extractor()
        if extractor is None:
            return
        target_ref = self.state.target.address if self.state.target else None
        if not target_ref:
            return
        reason = final_answer.split(_REPLAN_MARKER, 1)[-1].strip() or final_answer
        extractor.memory_manager.add_memory(
            content=f"侦察阶段计划偏差: {reason}",
            metadata={
                "is_target_bound": True,
                "target_ref": target_ref,
                "event_type": "recon_negative",
                "outcome": "negative",
                "phase": self.state.ptes_phase,
                "engagement_id": self.engagement_id,
            },
            memory_type="episodic",
            auto_classify=True,
        )

    def set_ptes_phase(self, new_phase: str) -> None:
        """供编排层调用：切换本次侦察任务所处的PTES阶段，触发对上一阶段episodic
        memory的归纳。触发时机由编排层决定，本Agent自己不会在run()内部自动调用
        （见docs/DESIGN.md「PTES phase切换：触发权归编排层，Agent只暴露hook」）。
        """
        target_ref = self.state.target.address if self.state.target else None
        super().set_ptes_phase(self.state, new_phase, target_ref)

    def finalize_engagement(self) -> None:
        """engagement结束兜底：确保各PTES阶段积累的episodic memory都至少归纳过一次semantic memory"""
        target_ref = self.state.target.address if self.state.target else None
        super().finalize_engagement(self.state, phases=_PTES_PHASES, target_ref=target_ref)

    async def arun_stream(
        self,
        input_text: str,
        on_start: LifecycleHook = None,
        on_finish: LifecycleHook = None,
        on_error: LifecycleHook = None,
        **kwargs
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        PlanAgent 真正的流式执行

        实时返回：
        - 规划阶段的计划生成
        - 执行阶段的每个步骤输出

        注意：这是一条独立于run()/Executor的流式实现，直接用astream_invoke手写prompt，
        本身不支持Function Calling / 工具调用（预先存在的限制，不在本次融合范围内）。
        这里只把_build_memory_context()生成的背景文本一次性嵌入规划与每一步的prompt，
        与run()路径保持"规划前有背景信息"的一致体验；每步工具结果的记忆写入不适用于
        这条路径，因为它本来就没有工具调用。

        Args:
            input_text: 用户输入
            on_start: 开始钩子
            on_finish: 完成钩子
            on_error: 错误钩子
            **kwargs: 其他参数

        Yields:
            StreamEvent: 流式事件
        """
        # 发送开始事件
        yield StreamEvent.create(
            StreamEventType.AGENT_START,
            self.name,
            input_text=input_text
        )

        try:
            # 阶段 1：规划
            yield StreamEvent.create(
                StreamEventType.STEP_START,
                self.name,
                phase="planning",
                description="生成执行计划"
            )

            print(f"\n🤖 {self.name} 开始处理问题: {input_text}")

            memory_context = self._build_memory_context(input_text)

            # 生成计划（同步方法，暂时保持）
            plan = self.planner.plan(input_text, memory_context=memory_context, **kwargs)

            if not plan:
                error_msg = "无法生成有效的行动计划，任务终止。"

                yield StreamEvent.create(
                    StreamEventType.ERROR,
                    self.name,
                    error=error_msg,
                    phase="planning"
                )

                yield StreamEvent.create(
                    StreamEventType.AGENT_FINISH,
                    self.name,
                    result=error_msg
                )

                self.add_message(Message(input_text, "user"))
                self.add_message(Message(error_msg, "assistant"))
                return

            yield StreamEvent.create(
                StreamEventType.STEP_FINISH,
                self.name,
                phase="planning",
                plan=plan,
                total_steps=len(plan)
            )

            # 阶段 2：执行计划
            step_results = []

            for i, step_description in enumerate(plan):
                step_num = i + 1

                # 步骤开始
                yield StreamEvent.create(
                    StreamEventType.STEP_START,
                    self.name,
                    phase="execution",
                    step=step_num,
                    total_steps=len(plan),
                    description=step_description
                )

                print(f"\n--- 步骤 {step_num}/{len(plan)} ---")
                print(f"📋 {step_description}")

                # 构建执行提示
                context = "\n".join([
                    f"步骤 {j+1}: {plan[j]} -> {step_results[j]}"
                    for j in range(len(step_results))
                ])

                background_section = f"已知背景（记忆系统提供，仅供参考）:\n{memory_context}\n\n" if memory_context else ""

                prompt = f"""{background_section}原始问题: {input_text}

完整计划:
{chr(10).join([f"{j+1}. {s}" for j, s in enumerate(plan)])}

已完成的步骤:
{context if context else "无"}

当前步骤: {step_description}

请执行当前步骤并给出结果。"""

                messages = [{"role": "user", "content": prompt}]

                # 流式执行步骤
                step_result = ""
                async for chunk in self.llm.astream_invoke(messages, **kwargs):
                    step_result += chunk

                    yield StreamEvent.create(
                        StreamEventType.LLM_CHUNK,
                        self.name,
                        chunk=chunk,
                        phase="execution",
                        step=step_num
                    )

                    print(chunk, end="", flush=True)

                print()  # 换行

                step_results.append(step_result)

                # 步骤完成
                yield StreamEvent.create(
                    StreamEventType.STEP_FINISH,
                    self.name,
                    phase="execution",
                    step=step_num,
                    result=step_result
                )

            # 生成最终答案
            yield StreamEvent.create(
                StreamEventType.STEP_START,
                self.name,
                phase="final_answer",
                description="生成最终答案"
            )

            final_prompt = f"""原始问题: {input_text}

执行计划和结果:
{chr(10).join([f"{i+1}. {plan[i]} -> {step_results[i]}" for i in range(len(plan))])}

请基于以上步骤的执行结果，给出原始问题的最终答案。"""

            final_messages = [{"role": "user", "content": final_prompt}]

            final_answer = ""
            async for chunk in self.llm.astream_invoke(final_messages, **kwargs):
                final_answer += chunk

                yield StreamEvent.create(
                    StreamEventType.LLM_CHUNK,
                    self.name,
                    chunk=chunk,
                    phase="final_answer"
                )

            # 发送完成事件
            yield StreamEvent.create(
                StreamEventType.AGENT_FINISH,
                self.name,
                result=final_answer,
                total_steps=len(plan)
            )

            print(f"\n--- 任务完成 ---\n最终答案: {final_answer}")

            # 保存到历史
            self.add_message(Message(input_text, "user"))
            self.add_message(Message(final_answer, "assistant"))

        except Exception as e:
            # 发送错误事件
            yield StreamEvent.create(
                StreamEventType.ERROR,
                self.name,
                error=str(e),
                error_type=type(e).__name__
            )
            raise
