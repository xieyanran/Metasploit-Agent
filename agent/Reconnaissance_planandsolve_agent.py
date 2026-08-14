"""
Plan and Solve Agent实现 - 在渗透测试中的侦查与信息收集阶段，分解规划与逐步执行的智能体
Reference: https://github.com/jjyaoao/HelloAgents/blob/main/hello_agents/agents/plan_solve_agent.py
"""
import json
from typing import Optional, List, Dict, Any, AsyncGenerator
from core.llm import PentestAgentLLM
from core.agent import Agent
from core.message import Message
from core.config import Config
from core.streaming import StreamEvent, StreamEventType
from core.lifecycle import LifecycleHook
from tools.registry import ToolRegistry

RECON_PLANNER_SYSTEM_PROMPT = """你是一名资深渗透测试工程师，当前处于 PTES 方法论的「情报收集」（Intelligence Gathering）阶段。

## 角色与目标
你的唯一目标是围绕给定的目标（IP/域名/网段）建立一份准确、可验证的资产清单（Target → Host → Port → Service），
为后续的「威胁建模/漏洞分析」与「利用」阶段提供输入。你不负责漏洞利用、载荷投递或会话管理——那是后续阶段的职责。

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
  「⚠️ 该步骤超出侦查阶段职责范围，无法在当前工具集下完成」，不要强行调用越权工具。

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

    def plan(self, question: str, **kwargs) -> List[str]:
        """""
        生成执行计划（使用 Function Calling）

        Args:
            question: 要解决的问题
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

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"请为以下问题生成详细的执行计划：\n\n{question}"}
        ]

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
    ):
        self.llm_client = llm_client
        self.system_prompt = system_prompt or RECON_EXECUTOR_SYSTEM_PROMPT
        self.tool_registry = tool_registry
        self.enable_tool_calling = enable_tool_calling and tool_registry is not None
        self.max_tool_iterations = max_tool_iterations

    def execute(self, question: str, plan: List[str], **kwargs) -> str:
        """
        按计划执行任务（支持 Function Calling）

        Args:
            question: 原始问题
            plan: 执行计划
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
            context = f"""# 原始问题：

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
            response_text = self._execute_step(context, **kwargs)

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

    def _execute_step(self, context: str, **kwargs) -> str:
        """
        执行单个步骤（支持 Function Calling）

        Args:
            context: 上下文信息
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

        # 启用工具调用模式
        from .simple_agent import SimpleAgent
        # 临时创建一个 SimpleAgent 实例来复用工具调用逻辑
        temp_agent = SimpleAgent(
            name="temp_executor",
            llm=self.llm_client,
            tool_registry=self.tool_registry
        )
        tool_schemas = temp_agent._build_tool_schemas()

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
                break

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

                # 执行工具（复用基类方法）
                result = temp_agent._execute_tool_call(tool_name, arguments)

                # 添加工具结果到消息
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": result
                })

        # 如果超过最大迭代次数，获取最后一次回答
        if current_iteration >= self.max_tool_iterations:
            llm_response = self.llm_client.invoke(messages, **kwargs)
            return llm_response.content if hasattr(llm_response, 'content') else str(llm_response)

        return ""

class PlanSolveAgent(Agent):
    """
    Plan and Solve Agent - 分解规划与逐步执行的智能体

    这个Agent能够：
    1. 将复杂问题分解为简单步骤（使用 Function Calling）
    2. 按照计划逐步执行
    3. 维护执行历史和上下文
    4. 得出最终答案
    5. 支持工具调用（可选）

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
        max_tool_iterations: int = 3
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
        """
        # 传递 tool_registry 到基类
        super().__init__(
            name,
            llm,
            system_prompt,
            config,
            tool_registry=tool_registry
        )

        self.planner = Planner(self.llm, planner_prompt)
        self.executor = Executor(
            self.llm,
            executor_prompt,
            tool_registry=tool_registry,
            enable_tool_calling=enable_tool_calling,
            max_tool_iterations=max_tool_iterations
        )

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
        
        # 1. 生成计划
        plan = self.planner.plan(input_text, **kwargs)
        if not plan:
            final_answer = "无法生成有效的行动计划，任务终止。"
            print(f"\n--- 任务终止 ---\n{final_answer}")
            
            # 保存到历史记录
            self.add_message(Message(input_text, "user"))
            self.add_message(Message(final_answer, "assistant"))
            
            return final_answer
        
        # 2. 执行计划
        final_answer = self.executor.execute(input_text, plan, **kwargs)
        print(f"\n--- 任务完成 ---\n最终答案: {final_answer}")
        
        # 保存到历史记录
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(final_answer, "assistant"))

        return final_answer

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

            # 生成计划（同步方法，暂时保持）
            plan = self.planner.plan(input_text, **kwargs)

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

                prompt = f"""原始问题: {input_text}

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
    








