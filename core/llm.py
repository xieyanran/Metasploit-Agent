import os
import time
from openai import OpenAI
from dotenv import load_dotenv
from typing import List, Dict, Optional
from typing import Optional, Iterator, List, Dict, Union, Any, AsyncIterator
from .llm_response import LLMResponse, LLMToolResponse, ToolCall

# 加载 .env 文件中的环境变量
load_dotenv()

class PentestAgentLLM:
    """
    为本项目 "First Pentest Agent" 定制的LLM客户端。
    它用于调用任何兼容OpenAI接口的服务，并默认使用流式响应。
    """
    # 各供应商对应的 API Key 环境变量（按优先级尝试）
    _PROVIDER_ENV_KEYS = {
        "openai": ["OPENAI_API_KEY"],
        "modelscope": ["MODELSCOPE_API_KEY"],
        "zhipu": ["ZHIPU_API_KEY", "ZHIPUAI_API_KEY"],
        "anthropic": ["ANTHROPIC_API_KEY"],
        "dashscope": ["DASHSCOPE_API_KEY"],
        "deepseek": ["DEEPSEEK_API_KEY"],
        "moonshot": ["MOONSHOT_API_KEY"],
        "doubao": ["ARK_API_KEY", "VOLC_API_KEY"],
        "hunyuan": ["HUNYUAN_API_KEY"],
        "minimax": ["MINIMAX_API_KEY"],
        "qianfan": ["QIANFAN_API_KEY", "BAIDU_API_KEY"],
        "siliconflow": ["SILICONFLOW_API_KEY"],
        "gemini": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
        "mistral": ["MISTRAL_API_KEY"],
        "groq": ["GROQ_API_KEY"],
        "cohere": ["COHERE_API_KEY"],
        "together": ["TOGETHER_API_KEY"],
        "azure_openai": ["AZURE_OPENAI_API_KEY"],
    }

    # 各供应商兼容OpenAI接口的默认 base_url（未显式提供 base_url 时使用）
    _PROVIDER_DEFAULT_BASE_URL = {
        "openai": "https://api.openai.com/v1",
        "modelscope": "https://api-inference.modelscope.cn/v1/",
        "zhipu": "https://open.bigmodel.cn/api/paas/v4/",
        "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "deepseek": "https://api.deepseek.com/v1",
        "moonshot": "https://api.moonshot.cn/v1",
        "doubao": "https://ark.cn-beijing.volces.com/api/v3",
        "hunyuan": "https://api.hunyuan.cloud.tencent.com/v1",
        "minimax": "https://api.minimax.chat/v1",
        "qianfan": "https://qianfan.baidubce.com/v2",
        "siliconflow": "https://api.siliconflow.cn/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "mistral": "https://api.mistral.ai/v1",
        "groq": "https://api.groq.com/openai/v1",
        "cohere": "https://api.cohere.ai/compatibility/v1",
        "together": "https://api.together.xyz/v1",
        # anthropic 官方接口不兼容 OpenAI SDK；azure_openai 的地址因资源而异，均无通用默认值，必须显式提供
    }

    def __init__(self, model: str = None, api_key: str = None, base_url: str = None,
                 provider: str = "auto", timeout: int = None, **kwargs):
        """
        初始化客户端。优先使用传入参数；provider="auto"（默认）时自动检测供应商，
        再结合供应商专属环境变量/默认地址，或通用 LLM_* 环境变量解析出最终凭证。
        """
        self.provider = provider if provider and provider != "auto" else self._auto_detect_provider(api_key, base_url)
        self.model = model or os.getenv("LLM_MODEL_ID")
        resolved_api_key, resolved_base_url = self._resolve_credentials(api_key, base_url)
        timeout = timeout or int(os.getenv("LLM_TIMEOUT", 60))

        if not all([self.model, resolved_api_key, resolved_base_url]):
            raise ValueError("模型ID、API密钥和服务地址必须被提供或在.env文件中定义。")

        self.client = OpenAI(api_key=resolved_api_key, base_url=resolved_base_url, timeout=timeout)

    def _auto_detect_provider(self, api_key: Optional[str], base_url: Optional[str]) -> str:
        """
        自动检测LLM提供商
        """
        # 1. 检查特定提供商的环境变量 (最高优先级)
        if os.getenv("MODELSCOPE_API_KEY"): return "modelscope"          # 阿里魔搭
        if os.getenv("OPENAI_API_KEY"): return "openai"                  # OpenAI
        if os.getenv("ZHIPU_API_KEY") or os.getenv("ZHIPUAI_API_KEY"): return "zhipu"      # 智谱AI (GLM)
        if os.getenv("ANTHROPIC_API_KEY"): return "anthropic"            # Anthropic Claude
        if os.getenv("DASHSCOPE_API_KEY"): return "dashscope"            # 阿里云通义千问
        if os.getenv("DEEPSEEK_API_KEY"): return "deepseek"              # 深度求索 DeepSeek
        if os.getenv("MOONSHOT_API_KEY"): return "moonshot"              # 月之暗面 Kimi
        if os.getenv("ARK_API_KEY") or os.getenv("VOLC_API_KEY"): return "doubao"          # 字节豆包/火山引擎
        if os.getenv("HUNYUAN_API_KEY"): return "hunyuan"                # 腾讯混元
        if os.getenv("MINIMAX_API_KEY"): return "minimax"                # MiniMax
        if os.getenv("QIANFAN_API_KEY") or os.getenv("BAIDU_API_KEY"): return "qianfan"    # 百度文心千帆
        if os.getenv("SILICONFLOW_API_KEY"): return "siliconflow"        # 硅基流动
        if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"): return "gemini"     # Google Gemini
        if os.getenv("MISTRAL_API_KEY"): return "mistral"                # Mistral
        if os.getenv("GROQ_API_KEY"): return "groq"                      # Groq
        if os.getenv("COHERE_API_KEY"): return "cohere"                  # Cohere
        if os.getenv("TOGETHER_API_KEY"): return "together"              # Together AI
        if os.getenv("AZURE_OPENAI_API_KEY"): return "azure_openai"      # Azure OpenAI

        # 获取通用的环境变量
        actual_api_key = api_key or os.getenv("LLM_API_KEY")
        actual_base_url = base_url or os.getenv("LLM_BASE_URL")

        # 2. 根据base_url判断提供商
        if actual_base_url:
            base_url_lower = actual_base_url.lower()
            if "api-inference.modelscope.cn" in base_url_lower: return "modelscope"          # api-inference.modelscope.cn
            if "api.openai.com" in base_url_lower: return "openai"                  # api.openai.com
            if "open.bigmodel.cn" in base_url_lower: return "zhipu"                 # open.bigmodel.cn (智谱)
            if "api.anthropic.com" in base_url_lower: return "anthropic"            # api.anthropic.com
            if "dashscope.aliyuncs.com" in base_url_lower: return "dashscope"            # dashscope.aliyuncs.com (通义千问)
            if "api.deepseek.com" in base_url_lower: return "deepseek"              # api.deepseek.com
            if "api.moonshot.cn" in base_url_lower: return "moonshot"              # api.moonshot.cn (Kimi)
            if "ark.cn-beijing.volces.com" in base_url_lower: return "doubao"   # ark.cn-beijing.volces.com (豆包/火山)
            if "api.hunyuan.cloud.tencent.com" in base_url_lower: return "hunyuan"                # api.hunyuan.cloud.tencent.com
            if "api.minimax.chat" in base_url_lower: return "minimax"                # api.minimax.chat
            if "qianfan.baidubce.com" in base_url_lower: return "qianfan"  # qianfan.baidubce.com
            if "api.siliconflow.cn" in base_url_lower: return "siliconflow"        # api.siliconflow.cn
            if "generativelanguage.googleapis.com" in base_url_lower: return "gemini"  # generativelanguage.googleapis.com
            if "api.mistral.ai" in base_url_lower: return "mistral"                # api.mistral.ai
            if "api.groq.com" in base_url_lower: return "groq"                     # api.groq.com
            if "api.cohere.ai" in base_url_lower or "api.cohere.com" in base_url_lower: return "cohere"                 # api.cohere.ai / api.cohere.com
            if "api.together.xyz" in base_url_lower: return "together"             # api.together.xyz
            if "xxx.openai.azure.com" in base_url_lower: return "azure_openai"            # xxx.openai.azure.com
            if "localhost" in base_url_lower or "127.0.0.1" in base_url_lower: 
                if ":11434" in base_url_lower: return "ollama"
                if ":8000" in base_url_lower: return "vllm"
                return "local" # 其他本地端口

        # 3. 根据 API 密钥格式辅助判断，不可靠
        if actual_api_key:
            if actual_api_key.startswith("ms-"): return "modelscope"
            if actual_api_key.startswith("sk-"): return "openai"    

        # 4. 默认返回 'auto'，使用通用配置
        return "auto"

    def _resolve_credentials(self, api_key: Optional[str], base_url: Optional[str]) -> tuple[str, str]:
        """
        根据 self.provider 解析最终使用的 API 密钥和 base_url。
        优先级：显式传入参数 > 供应商专属环境变量 > 通用 LLM_* 环境变量 > 供应商默认地址
        """
        resolved_api_key = api_key
        for env_key in self._PROVIDER_ENV_KEYS.get(self.provider, []):
            resolved_api_key = resolved_api_key or os.getenv(env_key)
        resolved_api_key = resolved_api_key or os.getenv("LLM_API_KEY")

        resolved_base_url = (
            base_url
            or os.getenv("LLM_BASE_URL")
            or self._PROVIDER_DEFAULT_BASE_URL.get(self.provider)
        )
        return resolved_api_key, resolved_base_url
    

    def think(self, messages: List[Dict[str, str]], temperature: float = 0) -> str:
        """
        调用大语言模型进行思考，并返回其响应。
        参考hello agent项目，需要进行修改
        """
        print(f"🧠 正在调用 {self.model} 模型...")
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                stream=True,
            )
            
            # 处理流式响应
            print("✅ 大语言模型响应成功:")
            collected_content = []
            for chunk in response:
                if not chunk.choices:
                    continue
                content = chunk.choices[0].delta.content or ""
                print(content, end="", flush=True)
                collected_content.append(content)
            print()  # 在流式输出结束后换行
            return "".join(collected_content)

        except Exception as e:
            print(f"❌ 调用LLM API时发生错误: {e}")
            return None

    def invoke(self, messages: List[Dict[str, str]], **kwargs) -> LLMResponse:
        """
        非流式调用LLM，返回完整响应对象。

        Args:
            messages: 消息列表
            **kwargs: 其他参数（temperature, max_tokens等）

        Returns:
            LLMResponse: 包含内容、统计信息、推理过程（thinking model）的响应对象

        Example:
            response = llm.invoke([{"role": "user", "content": "你好"}])
            print(response.content)  # 回复内容
            print(response.usage)    # token使用量
            print(response.latency_ms)  # 耗时
            if response.reasoning_content:  # thinking model的推理过程
                print(response.reasoning_content)
        """
        # 直接复用think()已验证可用的self.client（OpenAI兼容客户端），非流式调用；
        # 不依赖self._adapter——历史上这个方法整段复制自参考项目HelloAgents，_adapter
        # 是原项目里的适配器抽象层，本项目从未移植、__init__也从未初始化过，之前调用
        # 必然抛AttributeError（self._adapter/self.temperature/self.max_tokens均不存在）
        temperature = kwargs.pop("temperature", 0)
        max_tokens = kwargs.pop("max_tokens", None)
        call_kwargs = {"temperature": temperature}
        if max_tokens:
            call_kwargs["max_tokens"] = max_tokens
        call_kwargs.update(kwargs)

        start = time.monotonic()
        response = self.client.chat.completions.create(
            model=self.model, messages=messages, stream=False, **call_kwargs
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        message = response.choices[0].message
        usage = response.usage
        return LLMResponse(
            content=message.content or "",
            model=response.model or self.model,
            usage={
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            } if usage else {},
            latency_ms=latency_ms,
            reasoning_content=getattr(message, "reasoning_content", None),
        )

    def invoke_with_tools(
        self,
        messages: List[Dict],
        tools: List[Dict],
        tool_choice: Union[str, Dict] = "auto",
        **kwargs
    ) -> LLMToolResponse:
        """
        调用 LLM 并支持工具调用（Function Calling）

        这是支持 OpenAI Function Calling 的核心方法，用于结构化工具调用。

        Args:
            messages: 消息列表，格式为 [{"role": "user", "content": "..."}]
            tools: 工具 schema 列表，格式为 OpenAI Function Calling 规范
            tool_choice: 工具选择策略
                - "auto": 让模型自动决定是否调用工具（默认）
                - "none": 强制不调用工具
                - "required": 强制调用工具
                - {"type": "function", "function": {"name": "tool_name"}}: 强制调用指定工具
            **kwargs: 其他参数（temperature, max_tokens 等）

        Returns:
            统一的工具调用响应对象 (LLMToolResponse)

        Raises:
            HelloAgentsException: 当 LLM 调用失败时
        """
        # 直接复用invoke()已验证可用的self.client（OpenAI兼容客户端），非流式调用；
        # 不依赖self._adapter——原因同invoke()方法上的注释：_adapter是参考项目
        # HelloAgents里的适配器抽象层，本项目从未移植、__init__也从未初始化过，
        # self.temperature/self.max_tokens同样不存在，调用必然抛AttributeError
        temperature = kwargs.pop("temperature", 0)
        max_tokens = kwargs.pop("max_tokens", None)
        call_kwargs = {"temperature": temperature, "tool_choice": tool_choice}
        if max_tokens:
            call_kwargs["max_tokens"] = max_tokens
        call_kwargs.update(kwargs)

        start = time.monotonic()
        response = self.client.chat.completions.create(
            model=self.model, messages=messages, tools=tools, stream=False, **call_kwargs
        )
        latency_ms = int((time.monotonic() - start) * 1000)

        message = response.choices[0].message
        usage = response.usage
        raw_tool_calls = message.tool_calls or []
        tool_calls = [
            ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments)
            for tc in raw_tool_calls
        ]

        return LLMToolResponse(
            content=message.content,
            tool_calls=tool_calls,
            model=response.model or self.model,
            usage={
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
            } if usage else {},
            latency_ms=latency_ms,
        )

# --- 客户端使用示例 ---
if __name__ == '__main__':
    try:
        llmClient = PentestAgentLLM()
        
        exampleMessages = [
            {"role": "system", "content": "You are a helpful assistant that writes Python code."},
            {"role": "user", "content": "写一个快速排序算法"}
        ]
        
        print("--- 调用LLM ---")
        responseText = llmClient.think(exampleMessages)
        if responseText:
            print("\n\n--- 完整模型响应 ---")
            print(responseText)

    except ValueError as e:
        print(e)