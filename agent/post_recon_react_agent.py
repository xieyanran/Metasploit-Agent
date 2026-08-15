"""
ReAct Agent - 基于 Function Calling 的实现，覆盖 PTES 除侦察外的三个阶段
（Threat Modeling/Vulnerability Analysis / exploitation / post_exploitation）
Reference: https://github.com/jjyaoao/HelloAgents/blob/main/hello_agents/agents/react_agent.py
"""
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

from core.agent import Agent
from core.message import Message
from core.config import Config
from core.llm import PentestAgentLLM
from tools.registry import ToolRegistry
from agent.state import AgentState
from context.builder import ContextBuilder


# PTES阶段边界，用于engagement结束时的兜底归纳（DESIGN.md: Semantic memory时机设计）
_PTES_PHASES = ["recon", "vuln_analysis", "exploitation", "post_exploitation"]

# 本Agent实际负责的三个阶段是Threat Modeling/Vulnerability Analysis/exploitation/post_exploitation
# （recon由PlanSolveAgent负责，见agent/reconnaissance_planandsolve_agent.py）。编排层
# 在阶段边界调用set_ptes_phase()切换state.ptes_phase后，用同一个Agent实例再次调用
# run()，_build_phase_system_prompt()据此按阶段生成不同措辞的system prompt——阶段切换
# 本身仍然"触发权归编排层，Agent只暴露hook"（不在run()内部自动判断切换时机），只是
# 现在编排层要在三个阶段边界都调用它，不再只是exploitation一个阶段。
_DEFAULT_PHASE = "vuln_analysis"

# 计划偏差上报标记，约定与reconnaissance_planandsolve_agent.py的
# RECON_EXECUTOR_SYSTEM_PROMPT保持一致，供编排层识别"⚠️ REPLAN_NEEDED"信号
_REPLAN_MARKER = "⚠️ REPLAN_NEEDED:"

# 常见Metasploit工具参数里表示目标主机的key（RHOSTS是run_module/set_option的标准
# 选项名，其余是其它工具里出现的等价写法），按顺序尝试提取target_ref
_HOST_ARG_KEYS = ("RHOSTS", "rhosts", "RHOST", "rhost", "target", "host", "ip", "address")

# 每个阶段的中文名与职责说明，插入POST_RECON_REACT_SYSTEM_PROMPT_TEMPLATE生成
# 该阶段的system prompt。三段guidance只描述"本阶段该做什么"，不是代码层面强制的工具
# 白名单——和PlanSolveAgent.Executor不同，本Agent的工具边界一直是靠prompt约束、不是
# 靠ToolRegistry过滤，这次合并沿用同一种做法。
_PHASE_INFO: Dict[str, Dict[str, str]] = {
    "vuln_analysis": {
        "display_name": "威胁建模/漏洞分析（Threat Modeling / Vulnerability Analysis）",
        "guidance": (
            "结合侦察阶段汇总的资产清单（Host/Port/Service），为已识别的服务匹配候选漏洞与利用模块"
            "（如 search_module/get_module_info），评估可利用性与优先级，为下一步「利用」阶段准备候选"
            "攻击路径。本阶段只做匹配与评估，不要调用 run_module/set_option 等真正触发利用的工具——"
            "如果发现现有资产清单不足以支撑判断，应在 Finish 时说明还缺什么信息，而不是自行发起利用。"
        ),
    },
    "exploitation": {
        "display_name": "利用（Exploitation）",
        "guidance": (
            "针对上一阶段（Threat Modeling/Vulnerability Analysis）确定的候选模块，配置并执行实际的漏洞利用（如 "
            "set_option/show_option/run_module/compatible_payloads），建立可用的 session。失败时结合"
            "报错信息判断是否需要更换模块/载荷，仍无法达成时按「计划偏差上报」约定上报，而不是无限重试。"
        ),
    },
    "post_exploitation": {
        "display_name": "后渗透（Post-Exploitation）",
        "guidance": (
            "围绕上一阶段已建立的 session 展开后续操作（如 execute_session/shell_upgrade/"
            "list_sessions/session_compatible_modules），例如信息收集、权限提升、横向移动、持久化等，"
            "并注意 session 可能失效——发现 session 已断开等情况按「计划偏差上报」约定处理。"
        ),
    },
}


# 系统提示词模板
POST_RECON_REACT_SYSTEM_PROMPT_TEMPLATE = """你是一个具备推理和行动能力的资深渗透测试工程师，当前处于 PTES 方法论的「{phase_name}」阶段。

## 本阶段职责
{phase_guidance}

## 工作流程
你可以通过调用工具来完成任务：

1. **Thought 工具**：用于记录你的推理过程和分析
    - 在需要思考时调用
    - 参数：reasoning（你的推理内容）

2. **业务工具**：用于获取信息或执行操作
    - 根据任务需求选择合适的工具
    - 可以多次调用不同工具

3. **Finish 工具**：用于返回最终答案
    - 当你有足够信息得出结论时调用
    - 参数：answer（最终答案）

## 背景信息
消息中如果包含 [State]/[Evidence] 等分区，那是系统基于本次 engagement 已发现的资产/凭据、
以及历史相似场景下的经验教训自动整理的背景信息，请优先参考，避免重复已经验证过的失败路径。

## 记忆工具的使用
如果工具列表中包含 memory 工具，你可以：
- 主动调用 memory(action=search, ...) 查询本次任务或历史经验中是否有相关记录，避免重复无效尝试
- 记录一次利用尝试/凭据发现的结果时（memory action=add），如果这次发现依赖于之前已经记录过的
某条记忆（例如这次用到的凭据来自之前 search 到的某条结果），把该记忆的完整 id 通过 causal_ref
参数带上，以便追溯"凭据从主机A取得、用于登录主机B"这样的攻击路径因果链；memory 工具的搜索结果
与添加确认里都会给出完整的记忆 id（形如 [id: ...] 或 ID: ...），直接引用即可，不要自己编造 id。

## 计划偏差上报
如果发现实际情况与预期不符（例如目标已修复该漏洞、出现了计划外的防御机制拦截、目标环境发生了
实质性变化），调用 Finish 给出最终答案时，请在 answer 开头加上明确标记：
`⚠️ REPLAN_NEEDED: <一句话说明偏差原因>`
没有偏差则不要加这个标记。

## 重要提醒
- 主动使用 Thought 工具记录推理过程
- 可以多次调用工具获取信息
- 只有在确信有足够信息时才调用 Finish
"""


class PostReconReActAgent(Agent):
    """
    ReAct Agent - 基于 Function Calling 的推理与行动，覆盖 PTES 除侦察外的三个阶段
    （Threat Modeling/Vulnerability Analysis / exploitation / post_exploitation）

    核心改进：
    - 使用 Function Calling（结构化输出）
    - 支持 Thought 工具（显式推理）
    - 支持 Finish 工具（结束流程）
    - 无需正则解析，解析成功率 99%+
    - 与 Context/Memory 系统融合（见 docs/DESIGN.md「ReAct阶段 × Context/Memory 融合设计」）：
        每次 run() 开始前用 ContextBuilder 生成一次结构化 framing，每次工具结果之后自动写入
        working/episodic memory，计划偏差与 PTES 阶段切换也会落对应的记忆

    同一个实例按阶段被编排层多次调用：每次 run() 前编排层先调用 set_ptes_phase() 把
    state.ptes_phase 切到当前阶段，本Agent据此生成对应措辞的 system prompt（见
    _build_phase_system_prompt），阶段切换本身仍然只由编排层触发，本Agent不在 run()
    内部自动判断"现在该进入下一阶段了"。
    """

    def __init__(
        self,
        name: str,
        llm: PentestAgentLLM,
        tool_registry: Optional['ToolRegistry'] = None,
        system_prompt: Optional[str] = None,
        config: Optional[Config] = None,
        max_steps: int = 5,
        state: Optional[AgentState] = None,
        engagement_id: Optional[str] = None,
    ):
        """
        初始化 PostReconReActAgent

        Args:
            name: Agent 名称
            llm: LLM 实例
            tool_registry: 工具注册表（可选）
            system_prompt: 系统提示词（可选）。不传时不在构造期固定死一份文本，而是每次
                run()按state.ptes_phase动态生成（见_build_phase_system_prompt）；传了则
                固定使用这份文本，不再按阶段变化——适合只想跑单一阶段、不需要跨阶段复用
                同一实例的调用方
            config: 配置对象
            max_steps: 最大执行步数
            state: 贯穿本次任务的运行状态；不传则新建一个空的AgentState。由编排层在
                跨阶段调用多个Agent时传入同一个state，才能让target/凭据/PTES阶段在
                recon->Threat Modeling/Vulnerability Analysis->exploitation->post_exploitation之间保持连续
            engagement_id: 项目级作用域标识，episodic记忆检索的唯一安全边界；不传则按
                当前时间自动生成一个（与MetaspolitSimpleAgent的做法一致）
        """
        # 传递 tool_registry 到基类；system_prompt故意可以是None——固定文本与否的判断
        # 逻辑见_build_initial_messages，不在这里提前决定
        super().__init__(
            name,
            llm,
            system_prompt,
            config,
            tool_registry=tool_registry or ToolRegistry()
        )

        self.max_steps = max_steps
        # 贯穿本次任务的运行状态，供工具执行时使用
        self.state = state or AgentState()
        # 覆盖Agent基类里默认的None：本Agent天然持有engagement概念
        self.engagement_id = engagement_id or f"engagement_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # 内置工具标记（用于特殊处理）
        self._builtin_tools = {"Thought", "Finish"}

        # 最近一次 run() 的元数据
        self._session_metadata: Dict[str, Any] = {}
        self._current_step = 0
        self._total_tokens = 0

        # ContextBuilder懒加载，见_get_context_builder
        self._context_builder: Optional[ContextBuilder] = None

    def add_tool(self, tool):
        """添加工具到工具注册表"""
        self.tool_registry.register_tool(tool)

    def run(self, input_text: str, **kwargs) -> str:
        """
        运行 ReAct Agent

        Args:
            input_text: 用户问题
            **kwargs: 其他参数

        Returns:
            最终答案
        """
        session_start_time = datetime.now()

        try:
            final_answer = self._run_impl(input_text, session_start_time, **kwargs)
            self._session_metadata["total_steps"] = self._current_step
            self._session_metadata["total_tokens"] = self._total_tokens
            return final_answer
        except KeyboardInterrupt:
            print("\n⚠️ 用户中断")
            raise
        except Exception as e:
            print(f"\n❌ 发生错误: {e}")
            raise

    def _run_impl(self, input_text: str, session_start_time: datetime, **kwargs) -> str:
        """
        ReAct Agent 主逻辑实现

        Args:
            input_text: 用户问题
            session_start_time: 会话开始时间
            **kwargs: 其他参数

        Returns:
            最终答案
        """
        # 构建消息列表（首条消息由ContextBuilder的GSSC流水线生成，见_build_initial_messages）
        # 准备接段: build context
        messages = self._build_initial_messages(input_text)

        # 构建工具 schemas（包含内置工具和用户工具）
        tool_schemas = self._build_tool_schemas()

        current_step = 0
        total_tokens = 0
        final_answer: Optional[str] = None

        print(f"\n🤖 {self.name} 开始处理问题: {input_text}")

        while current_step < self.max_steps:
            current_step += 1
            self._current_step = current_step
            print(f"\n--- 第 {current_step} 步 ---")

            # 调用 LLM（Function Calling）
            # 进入循环
            try:
                # 隐式推理
                response = self.llm.invoke_with_tools(
                    messages=messages,
                    tools=tool_schemas,
                    tool_choice="auto",
                    **kwargs
                )
            except Exception as e:
                print(f"❌ LLM 调用失败: {e}")
                final_answer = f"抱歉，处理过程中发生错误：{e}"
                break

            # 累计 tokens
            if response.usage:
                total_tokens += response.usage.get("total_tokens", 0)
                self._total_tokens = total_tokens

            # 处理工具调用
            tool_calls = response.tool_calls
            if not tool_calls:
                # 没有工具调用（模型未走 Finish 就直接给出文本），将其作为最终答案
                final_answer = response.content or "抱歉，我无法回答这个问题。"
                break

            # 将助手消息（含工具调用）加入历史
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

            # 执行所有的工具调用
            finished = False
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

                # 内置工具：Thought 仅记录推理，不产生外部效果，显式的吐出来
                if tool_name == "Thought":
                    reasoning = arguments.get("reasoning", "")
                    print(f"💭 {reasoning}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": "推理已记录。"
                    })
                    continue

                # 内置工具：Finish 结束整个流程（Action)
                if tool_name == "Finish":
                    final_answer = arguments.get("answer", "")
                    print(f"✅ 完成: {final_answer}")
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": "任务已结束。"
                    })
                    finished = True
                    break

                # 业务工具：统一走 ToolRegistry (Action)
                print(f"🔧 调用工具: {tool_name}({arguments})")
                result = self.tool_registry.execute_tool(tool_name, self.state, **arguments)
                result_text = str(result.output) if result.success else f"❌ {result.message or result.output}"
                print(f"   -> {result_text}")

                # Observation -> Memory：每次工具结果之后无条件走记忆写入（memory工具
                # 自身会被内部逻辑自动跳过，见core/agent.py::_record_tool_observation）
                self._record_tool_observation(
                    tool_name=tool_name,
                    arguments=json.dumps(arguments, ensure_ascii=False),
                    output=result_text,
                    tool_success=result.success,
                    target_ref=self._extract_target_ref(arguments),
                    phase=self.state.ptes_phase,
                    session_id=self.engagement_id,
                )

                # Observation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": result_text
                })

            if finished:
                break

        if final_answer is None:
            # 达到最大步数仍未调用 Finish，退回一次不带工具的调用作为兜底答案
            fallback = self.llm.invoke(messages, **kwargs)
            final_answer = fallback.content if hasattr(fallback, 'content') else str(fallback)

        # 计划偏差信号：本身也要落一条episodic记忆，否则"当时为什么改了计划"这条
        # 复盘线索会随会话结束而丢失（见docs/DESIGN.md）
        if final_answer and final_answer.strip().startswith(_REPLAN_MARKER):
            self._record_replan_signal(final_answer)

        # 保存到历史记录
        self.add_message(Message(input_text, "user"))
        self.add_message(Message(final_answer, "assistant"))

        duration = (datetime.now() - session_start_time).total_seconds()
        print(f"\n--- 任务完成（耗时 {duration:.1f}s，共 {current_step} 步） ---\n最终答案: {final_answer}")

        return final_answer

    def _get_context_builder(self) -> Optional[ContextBuilder]:
        """懒加载ContextBuilder：复用工具注册表里"memory"工具已初始化的MemoryManager。

        没有注册memory工具时返回None，调用方（_build_initial_messages）退化为不做
        记忆检索的裸消息构建，不影响Agent的基本可用性。
        """
        if not self.tool_registry:
            return None
        memory_tool = self.tool_registry.get_tool("memory")
        if memory_tool is None:
            return None
        if self._context_builder is None:
            self._context_builder = ContextBuilder(memory_tool=memory_tool, llm=self.llm)
        return self._context_builder

    def _build_phase_system_prompt(self) -> str:
        """按self.state.ptes_phase生成当前阶段的system prompt文本。

        本Agent同一个实例要跨Threat Modeling/Vulnerability Analysis/exploitation/post_exploitation三个阶段被
        编排层复用（每次run()前编排层调用set_ptes_phase()切阶段），所以system prompt
        不能在构造期固定死一份文本，必须在每次run()时按当时的state.ptes_phase现算。

        state.ptes_phase取不到已知阶段时（例如编排层还没有切出recon默认值就调用了
        本Agent），退化为_DEFAULT_PHASE（Threat Modeling/Vulnerability Analysis，本Agent负责的第一个阶段）而
        不是报错——沿用整个融合设计"记忆/框架相关的辅助信息缺失时退化，不阻塞任务"的
        一贯原则，具体见docs/DESIGN.md「PTES phase 切换：触发权归编排层，Agent只暴露
        hook」。
        """
        info = _PHASE_INFO.get(self.state.ptes_phase, _PHASE_INFO[_DEFAULT_PHASE])
        return POST_RECON_REACT_SYSTEM_PROMPT_TEMPLATE.format(
            phase_name=info["display_name"],
            phase_guidance=info["guidance"],
        )

    def _build_initial_messages(self, input_text: str) -> List[Dict[str, str]]:
        """构建本次run()的首条消息。

        system角色内容：构造时传了固定system_prompt则原样使用（不随阶段变化，适合
        单阶段调用方）；没传则每次都用_build_phase_system_prompt()按当前阶段现算。
        
        user角色内容改由ContextBuilder的GSSC流水线生成——把本次engagement已发现的
        资产/凭据（episodic task_state）和相关经验（semantic related_memory）在第一步
        Thought之前就摆在LLM面前，而不是像过去那样只给一句裸的input_text。

        只在run()开始时调用一次，不在循环内重复调用：循环内的连续性由Function Calling
        协议本身维持的messages数组负责，重复调用会导致[Role & Policies]反复注入、
        token预算迅速超支（见docs/DESIGN.md「融合的基本原则」）。

        system_instructions故意传None：system内容已经作为独立的system角色消息存在，
        再传给ContextBuilder会在[Role & Policies]分区重复注入一遍。
        """
        messages: List[Dict[str, str]] = []
        system_content = self.system_prompt or self._build_phase_system_prompt()
        if system_content:
            messages.append({"role": "system", "content": system_content})

        builder = self._get_context_builder()
        if builder is not None:
            try:
                user_content = builder.build(
                    user_query=input_text,
                    state=self.state,
                    engagement_id=self.engagement_id,
                    conversation_history=self.get_history(),
                    system_instructions=None,
                )
            except Exception as e:
                print(f"⚠️ 上下文构建失败，退化为裸问题文本: {e}")
                user_content = input_text
        else:
            user_content = input_text

        messages.append({"role": "user", "content": user_content})
        return messages

    def _extract_target_ref(self, arguments: Dict[str, Any]) -> Optional[str]:
        """从工具调用参数里提取host级别的target_ref，取不到时兜底到state.target.address。

        exploitation/post_exploitation阶段的因果链（凭据取自主机A、用于登录主机B）
        天然是host级别的，如果统一退化成顶层target地址会丢失这个粒度，causal_ref也
        失去意义（见docs/DESIGN.md「target_ref要落到host粒度」）。
        """
        for key in _HOST_ARG_KEYS:
            value = arguments.get(key)
            if value:
                # RHOSTS可能是逗号分隔的多主机/CIDR，取第一个作为主要标识
                return str(value).split(",")[0].strip()
        if self.state.target:
            return self.state.target.address
        return None

    def _record_replan_signal(self, final_answer: str) -> None:
        """把本Agent所处阶段（Threat Modeling/Vulnerability Analysis/exploitation/post_exploitation之一）的
        计划偏差信号（⚠️ REPLAN_NEEDED）落一条episodic记忆。

        直接同步写入，不走maybe_extract_episodic的异步LLM判断路径——这个信号本身已经
        是LLM明确判断过的"计划失效"事实，不需要再让另一个LLM去判断"这算不算一个事件"；
        同步写入也保证这条记录在run()返回前就已经落库。
        """
        extractor = self._get_memory_extractor()
        if extractor is None:
            return
        target_ref = self.state.target.address if self.state.target else None
        if not target_ref:
            return
        reason = final_answer.split(_REPLAN_MARKER, 1)[-1].strip() or final_answer
        phase_display = _PHASE_INFO.get(self.state.ptes_phase, _PHASE_INFO[_DEFAULT_PHASE])["display_name"]
        extractor.memory_manager.add_memory(
            content=f"{phase_display}阶段计划偏差: {reason}",
            metadata={
                "is_target_bound": True,
                "target_ref": target_ref,
                "event_type": "defense_observed",
                "outcome": "negative",
                "phase": self.state.ptes_phase,
                "engagement_id": self.engagement_id,
            },
            memory_type="episodic",
            auto_classify=True,
        )

    def set_ptes_phase(self, new_phase: str) -> None:
        """供编排层调用：切换本次任务所处的PTES阶段（Threat Modeling/Vulnerability Analysis/exploitation/
        post_exploitation之间），触发对上一阶段episodic memory的归纳。触发时机由
        编排层决定，本Agent自己不会在run()内部自动调用（见docs/DESIGN.md「PTES
        phase切换：触发权归编排层，Agent只暴露hook」）。
        """
        target_ref = self.state.target.address if self.state.target else None
        super().set_ptes_phase(self.state, new_phase, target_ref)

    def finalize_engagement(self) -> None:
        """engagement结束兜底：确保各PTES阶段积累的episodic memory都至少归纳过一次semantic memory"""
        target_ref = self.state.target.address if self.state.target else None
        super().finalize_engagement(self.state, phases=_PTES_PHASES, target_ref=target_ref)

    def _build_tool_schemas(self) -> List[Dict[str, Any]]:
        """构建 Function Calling 工具 schema，包含内置 Thought/Finish 与工具注册表中的业务工具。

        业务工具部分复用 ToolRegistry.to_function_schemas()（见 tools/registry.py），
        Thought/Finish 是 ReAct 专属的内置工具，不属于 ToolRegistry 的职责，在这里追加。
        """
        schemas = [
            {
                "type": "function",
                "function": {
                    "name": "Thought",
                    "description": "记录推理过程和分析，不产生任何外部效果",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reasoning": {"type": "string", "description": "推理内容"}
                        },
                        "required": ["reasoning"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "Finish",
                    "description": "确信已获得足够信息得出结论时调用，结束流程并给出最终答案",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "answer": {"type": "string", "description": "最终答案"}
                        },
                        "required": ["answer"]
                    }
                }
            }
        ]

        schemas.extend(self.tool_registry.to_function_schemas())
        return schemas
