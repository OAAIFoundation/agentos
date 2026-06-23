"""
Unified LLM Client
Supports all semantic-router provider types (15+ providers)

Supported providers:
- OpenAI, Anthropic, AWS Bedrock
- Azure OpenAI (with API version handling)
- Google Gemini, Google Vertex AI
- MiniMax (Chinese LLM)
- DeepSeek, Qwen, Baichuan, Zhipu, Moonshot (Chinese LLMs)
- vLLM, Ollama, LM Studio (local inference)

Reference: AgentOS/src/semantic-router/pkg/config/helper.go:604-612
"""

import httpx
import json
import logging
from typing import Dict, List, Any, Optional, AsyncIterator
from config_loader import ProviderConfig

logger = logging.getLogger(__name__)


# Provider 类型注册表 (来自 semantic-router)
PROVIDER_TYPE_REGISTRY = {
    "openai": {
        "auth_header": "Authorization",
        "auth_prefix": "Bearer",
        "chat_path": "/chat/completions",
        "requires_max_tokens": False,
    },
    "anthropic": {
        "auth_header": "x-api-key",
        "auth_prefix": "",
        "chat_path": "/v1/messages",
        "requires_max_tokens": True,
        "extra_headers": {
            "anthropic-version": "2023-06-01"
        }
    },
    "azure-openai": {
        "auth_header": "api-key",
        "auth_prefix": "",
        "chat_path": "/chat/completions",
        "requires_api_version": True,
    },
    "bedrock": {
        "auth_header": "Authorization",
        "auth_prefix": "Bearer",
        "chat_path": "/chat/completions",
    },
    "gemini": {
        "auth_header": "Authorization",
        "auth_prefix": "Bearer",
        "chat_path": "/chat/completions",
    },
    "vertex-ai": {
        "auth_header": "Authorization",
        "auth_prefix": "Bearer",
        "chat_path": "/chat/completions",
    },
    "minimax": {
        "auth_header": "Authorization",
        "auth_prefix": "Bearer",
        "chat_path": "/v1/chat/completions",
    },
    "vllm": {
        "auth_header": "Authorization",
        "auth_prefix": "Bearer",
        "chat_path": "/v1/chat/completions",
        "no_auth": True,  # vLLM 通常不需要认证
    },
    "ollama": {
        "auth_header": "Authorization",
        "auth_prefix": "Bearer",
        "chat_path": "/v1/chat/completions",
        "no_auth": True,  # Ollama 不需要认证
    },
    "lm-studio": {
        "auth_header": "Authorization",
        "auth_prefix": "Bearer",
        "chat_path": "/v1/chat/completions",
        "no_auth": True,  # LM Studio 不需要认证
    },
}


class LLMClient:
    """
    Unified LLM Client for all providers
    Supports all semantic-router provider types (15+)
    """

    def __init__(self, timeout: float = 300.0, upstream_proxy: str = None):
        """
        Initialize LLM client

        Args:
            timeout: Request timeout in seconds
            upstream_proxy: Upstream proxy URL (e.g., "http://proxy.company.com:8080")
        """
        self.timeout = timeout
        self.upstream_proxy = upstream_proxy

        # Configure httpx client with upstream proxy
        if upstream_proxy:
            logger.info(f"LLMClient using upstream proxy: {upstream_proxy}")
            self.client = httpx.AsyncClient(
                timeout=timeout,
                proxy=upstream_proxy,
                verify=False  # Don't verify SSL for upstream proxy
            )
        else:
            self.client = httpx.AsyncClient(timeout=timeout)

    def _detect_provider_type(self, provider: ProviderConfig) -> str:
        """
        检测 provider 类型（基于 base_url 和 name）

        参考: semantic-router 的 provider 识别逻辑
        """
        base_url = provider.base_url.lower()
        name = provider.name.lower()

        # 通过 URL 模式识别
        if "anthropic.com" in base_url:
            return "anthropic"
        elif "openai.azure.com" in base_url:
            return "azure-openai"
        elif "bedrock" in base_url or "bedrock" in name:
            return "bedrock"
        elif "generativelanguage.googleapis.com" in base_url:
            return "gemini"
        elif "aiplatform.googleapis.com" in base_url:
            return "vertex-ai"
        elif "minimax" in base_url or "minimax" in name:
            return "minimax"
        elif "vllm" in name or name.startswith("local"):
            return "vllm"
        elif "ollama" in base_url or "ollama" in name:
            return "ollama"
        elif "lm-studio" in name or "localhost:1234" in base_url:
            return "lm-studio"
        else:
            # 默认为 OpenAI 兼容
            return "openai"

    def _get_provider_info(self, provider_type: str) -> Dict[str, Any]:
        """获取 provider 配置信息"""
        return PROVIDER_TYPE_REGISTRY.get(provider_type, PROVIDER_TYPE_REGISTRY["openai"])

    def _build_headers(
        self,
        provider: ProviderConfig,
        provider_type: str,
        api_key: Optional[str]
    ) -> Dict[str, str]:
        """
        构建请求头（根据 provider 类型）

        参考: semantic-router/pkg/config/helper.go:604-612
        """
        headers = {
            "Content-Type": "application/json",
        }

        provider_info = self._get_provider_info(provider_type)

        # 添加认证头
        if api_key and not provider_info.get("no_auth", False):
            auth_header = provider_info["auth_header"]
            auth_prefix = provider_info["auth_prefix"]

            if auth_prefix:
                headers[auth_header] = f"{auth_prefix} {api_key}"
            else:
                headers[auth_header] = api_key

        # 添加额外的头（如 Anthropic 的 anthropic-version）
        extra_headers = provider_info.get("extra_headers", {})
        headers.update(extra_headers)

        # Azure OpenAI 特殊处理：从 provider 获取额外头
        if provider_type == "azure-openai" and hasattr(provider, "extra_headers"):
            headers.update(provider.extra_headers)

        return headers

    def _get_chat_endpoint(
        self,
        provider: ProviderConfig,
        provider_type: str
    ) -> str:
        """
        获取聊天端点 URL

        参考: semantic-router/pkg/config/helper.go:757-793
        """
        provider_info = self._get_provider_info(provider_type)
        chat_path = provider_info["chat_path"]

        base_url = provider.base_url.rstrip("/")

        # Azure OpenAI 特殊处理：添加 api-version 参数
        if provider_type == "azure-openai":
            api_version = getattr(provider, "api_version", "2024-10-21")
            return f"{base_url}{chat_path}?api-version={api_version}"
        else:
            return f"{base_url}{chat_path}"

    def _build_request_body(
        self,
        provider_type: str,
        model: str,
        messages: List[Dict[str, Any]],
        stream: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """
        构建请求体（根据 provider 类型）

        参考: semantic-router/pkg/anthropic/inbound.go
        """
        # Anthropic 使用特殊格式
        if provider_type == "anthropic":
            return self._convert_to_anthropic_format(model, messages, stream, **kwargs)

        # 其他 provider 使用 OpenAI 兼容格式
        body = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }

        # 添加可选参数
        if "temperature" in kwargs:
            body["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            body["max_tokens"] = kwargs["max_tokens"]
        if "top_p" in kwargs:
            body["top_p"] = kwargs["top_p"]
        if "frequency_penalty" in kwargs:
            body["frequency_penalty"] = kwargs["frequency_penalty"]
        if "presence_penalty" in kwargs:
            body["presence_penalty"] = kwargs["presence_penalty"]
        if "stop" in kwargs:
            body["stop"] = kwargs["stop"]

        return body

    def _convert_to_anthropic_format(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        stream: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Convert OpenAI format to Anthropic Messages API format

        参考: semantic-router/pkg/anthropic/inbound.go

        Anthropic API 差异:
        - max_tokens 是必需字段（没有默认值）
        - system 消息单独处理（不在 messages 数组中）
        - 支持 tool_use、thinking 内容块
        """
        # Extract system message if present
        system_message = None
        filtered_messages = []

        for msg in messages:
            if msg.get("role") == "system":
                system_message = msg.get("content", "")
            else:
                filtered_messages.append(msg)

        # Build Anthropic request body
        body = {
            "model": model,
            "messages": filtered_messages,
            "max_tokens": kwargs.get("max_tokens", 4096),  # Anthropic 默认 4096
            "stream": stream,
        }

        # Add system message if present
        if system_message:
            body["system"] = system_message

        # Add other parameters
        if "temperature" in kwargs:
            body["temperature"] = kwargs["temperature"]
        if "top_p" in kwargs:
            body["top_p"] = kwargs["top_p"]
        if "top_k" in kwargs:
            body["top_k"] = kwargs["top_k"]
        if "stop_sequences" in kwargs:
            body["stop_sequences"] = kwargs["stop_sequences"]

        return body

    async def chat_completion(
        self,
        provider: ProviderConfig,
        model: str,
        messages: List[Dict[str, Any]],
        stream: bool = False,
        **kwargs
    ) -> Dict[str, Any] | AsyncIterator[str]:
        """
        Send chat completion request to LLM provider

        支持所有 semantic-router 的 provider 类型

        Args:
            provider: Provider configuration
            model: Model name
            messages: Chat messages
            stream: Enable streaming response
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            Response dict or async iterator for streaming
        """
        # 检测 provider 类型
        provider_type = self._detect_provider_type(provider)
        logger.info(f"Detected provider type: {provider_type}")

        # 获取 API key
        api_key = provider.get_api_key()

        # 构建请求头
        headers = self._build_headers(provider, provider_type, api_key)

        # 获取端点 URL
        endpoint = self._get_chat_endpoint(provider, provider_type)

        # 构建请求体
        body = self._build_request_body(provider_type, model, messages, stream, **kwargs)

        logger.info(f"Sending request to {provider.name}/{model} (type: {provider_type})")
        logger.debug(f"Endpoint: {endpoint}")
        logger.debug(f"Headers: {list(headers.keys())}")
        logger.debug(f"Messages: {len(messages)} messages")

        try:
            if stream:
                return self._stream_response(endpoint, headers, body, provider, provider_type)
            else:
                return await self._normal_response(endpoint, headers, body, provider, provider_type)

        except httpx.TimeoutException as e:
            logger.error(f"Request timeout to {provider.name}: {e}")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error from {provider.name}: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Error calling {provider.name}: {e}")
            raise

    async def _normal_response(
        self,
        endpoint: str,
        headers: Dict[str, str],
        body: Dict[str, Any],
        provider: ProviderConfig,
        provider_type: str
    ) -> Dict[str, Any]:
        """Handle non-streaming response"""
        response = await self.client.post(
            endpoint,
            headers=headers,
            json=body
        )
        response.raise_for_status()

        result = response.json()

        # Anthropic 响应格式转换（如果需要）
        if provider_type == "anthropic":
            result = self._convert_anthropic_response(result)

        logger.info(
            f"Response from {provider.name}: "
            f"{result.get('usage', {}).get('total_tokens', 0)} tokens"
        )

        return result

    def _convert_anthropic_response(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 Anthropic 响应转换为 OpenAI 格式（如果需要）

        参考: semantic-router/pkg/anthropic/outbound.go

        注意: 这里只做基础转换，完整转换需要处理 tool_use、thinking 等块
        """
        # 如果已经是 OpenAI 格式，直接返回
        if "choices" in response:
            return response

        # Anthropic → OpenAI 格式转换
        content = ""
        for block in response.get("content", []):
            if block.get("type") == "text":
                content += block.get("text", "")

        return {
            "id": response.get("id", ""),
            "object": "chat.completion",
            "created": 0,
            "model": response.get("model", ""),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": content,
                    },
                    "finish_reason": response.get("stop_reason", "stop"),
                }
            ],
            "usage": {
                "prompt_tokens": response.get("usage", {}).get("input_tokens", 0),
                "completion_tokens": response.get("usage", {}).get("output_tokens", 0),
                "total_tokens": (
                    response.get("usage", {}).get("input_tokens", 0)
                    + response.get("usage", {}).get("output_tokens", 0)
                ),
            },
        }

    async def _stream_response(
        self,
        endpoint: str,
        headers: Dict[str, str],
        body: Dict[str, Any],
        provider: ProviderConfig,
        provider_type: str
    ) -> AsyncIterator[str]:
        """
        Handle streaming response (SSE format)

        参考: semantic-router/pkg/anthropic/sse_out.go

        Yields:
            SSE chunks (data: {...}\n\n format)
        """
        logger.info(f"Starting streaming request to {provider.name}")

        async with self.client.stream(
            "POST",
            endpoint,
            headers=headers,
            json=body
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    # SSE format: "data: {json}\n\n"
                    yield line + "\n\n"

                    # Check for [DONE] marker
                    if line == "data: [DONE]":
                        logger.info(f"Stream completed from {provider.name}")
                        break

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# Example usage and testing
if __name__ == "__main__":
    import asyncio
    import os

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    async def test_multiple_providers():
        """Test different provider types"""

        # Test OpenAI
        openai_provider = ProviderConfig(
            name="openai",
            base_url="https://api.openai.com/v1",
            api_key=os.environ.get("OPENAI_API_KEY", "")
        )

        # Test Anthropic
        anthropic_provider = ProviderConfig(
            name="anthropic",
            base_url="https://api.anthropic.com",
            api_key=os.environ.get("ANTHROPIC_API_KEY", "")
        )

        # Test Bedrock
        bedrock_provider = ProviderConfig(
            name="bedrock",
            base_url="https://bedrock-runtime.us-west-2.amazonaws.com/v1",
            api_key=os.environ.get("AWS_BEDROCK_TOKEN", "")
        )

        # Test local vLLM
        vllm_provider = ProviderConfig(
            name="local_vllm",
            base_url="http://127.0.0.1:8000/v1",
            api_key="EMPTY"
        )

        messages = [
            {"role": "user", "content": "Say hello"}
        ]

        async with LLMClient(timeout=30.0) as client:
            # Test each provider
            for provider in [openai_provider, anthropic_provider, bedrock_provider, vllm_provider]:
                try:
                    logger.info(f"\n=== Testing {provider.name} ===")

                    if not provider.get_api_key():
                        logger.warning(f"Skipping {provider.name}: No API key")
                        continue

                    response = await client.chat_completion(
                        provider=provider,
                        model="test-model",
                        messages=messages,
                        max_tokens=50
                    )

                    logger.info(f"✅ {provider.name} response: {response['choices'][0]['message']['content'][:50]}")

                except Exception as e:
                    logger.error(f"❌ {provider.name} error: {e}")

    # Run test
    print("\n=== Testing Enhanced LLM Client ===\n")
    print("Make sure you have set the required API keys in environment variables:")
    print("  - OPENAI_API_KEY")
    print("  - ANTHROPIC_API_KEY")
    print("  - AWS_BEDROCK_TOKEN")
    print("\nOr run a local vLLM server on http://127.0.0.1:8000\n")

    asyncio.run(test_multiple_providers())
