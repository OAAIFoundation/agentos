"""
测试所有 Provider 类型

验证 LLMClient 对所有 semantic-router provider 的支持
"""

import asyncio
import logging
import os
from config_loader import ProviderConfig
from llm_client import LLMClient

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def test_provider(client: LLMClient, provider: ProviderConfig, model: str):
    """测试单个 provider"""
    try:
        logger.info(f"\n{'='*60}")
        logger.info(f"Testing: {provider.name} / {model}")
        logger.info(f"{'='*60}")

        # 检查 API key
        api_key = provider.get_api_key()
        if not api_key or api_key in ["EMPTY", "ollama", "lm-studio"]:
            logger.warning(f"⚠️  No API key for {provider.name}, skipping...")
            return

        # 发送测试请求
        messages = [
            {"role": "user", "content": "Say 'Hello from AI!' in exactly 5 words."}
        ]

        response = await client.chat_completion(
            provider=provider,
            model=model,
            messages=messages,
            max_tokens=50,
            temperature=0.7
        )

        # 提取响应
        content = response["choices"][0]["message"]["content"]
        tokens = response.get("usage", {}).get("total_tokens", 0)

        logger.info(f"✅ SUCCESS!")
        logger.info(f"   Response: {content}")
        logger.info(f"   Tokens: {tokens}")

    except Exception as e:
        logger.error(f"❌ FAILED: {provider.name}")
        logger.error(f"   Error: {str(e)[:100]}")


async def test_all_providers():
    """测试所有 provider 类型"""

    # 定义所有 provider 测试案例
    test_cases = [
        # OpenAI
        (
            ProviderConfig(
                name="openai",
                base_url="https://api.openai.com/v1",
                api_key=os.environ.get("OPENAI_API_KEY", ""),
                provider_type="openai"
            ),
            "gpt-4o-mini"
        ),

        # Anthropic
        (
            ProviderConfig(
                name="anthropic",
                base_url="https://api.anthropic.com",
                api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
                provider_type="anthropic"
            ),
            "claude-3-5-sonnet-20241022"
        ),

        # AWS Bedrock
        (
            ProviderConfig(
                name="bedrock",
                base_url="https://bedrock-runtime.us-east-2.amazonaws.com/v1",
                api_key=os.environ.get("AWS_BEDROCK_TOKEN", ""),
                provider_type="bedrock"
            ),
            "anthropic.claude-3-5-sonnet-20241022-v2:0"
        ),

        # Azure OpenAI
        (
            ProviderConfig(
                name="azure-openai",
                base_url="https://my-resource.openai.azure.com/openai/deployments/gpt-4o",
                api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
                provider_type="azure-openai",
                api_version="2024-10-21"
            ),
            "gpt-4o"
        ),

        # Google Gemini
        (
            ProviderConfig(
                name="gemini",
                base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                api_key=os.environ.get("GOOGLE_API_KEY", ""),
                provider_type="gemini"
            ),
            "gemini-1.5-flash"
        ),

        # Google Vertex AI
        (
            ProviderConfig(
                name="vertex-ai",
                base_url="https://us-central1-aiplatform.googleapis.com/v1",
                api_key=os.environ.get("VERTEX_AI_TOKEN", ""),
                provider_type="vertex-ai"
            ),
            "gemini-1.5-pro"
        ),

        # MiniMax
        (
            ProviderConfig(
                name="minimax",
                base_url="https://api.minimax.io",
                api_key=os.environ.get("MINIMAX_API_KEY", ""),
                provider_type="minimax"
            ),
            "abab6.5-chat"
        ),

        # DeepSeek (OpenAI 兼容)
        (
            ProviderConfig(
                name="deepseek",
                base_url="https://api.deepseek.com",
                api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
                provider_type="openai"
            ),
            "deepseek-chat"
        ),

        # Qwen (阿里云)
        (
            ProviderConfig(
                name="qwen",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                api_key=os.environ.get("QWEN_API_KEY", ""),
                provider_type="openai"
            ),
            "qwen-turbo"
        ),

        # 本地 vLLM
        (
            ProviderConfig(
                name="local-vllm",
                base_url="http://127.0.0.1:8000/v1",
                api_key="EMPTY",
                provider_type="vllm"
            ),
            "local-model"
        ),

        # 本地 Ollama
        (
            ProviderConfig(
                name="local-ollama",
                base_url="http://127.0.0.1:11434/v1",
                api_key="ollama",
                provider_type="ollama"
            ),
            "llama3.1:8b"
        ),

        # 本地 LM Studio
        (
            ProviderConfig(
                name="local-lm-studio",
                base_url="http://127.0.0.1:1234/v1",
                api_key="lm-studio",
                provider_type="lm-studio"
            ),
            "local-model"
        ),
    ]

    # 创建客户端
    async with LLMClient(timeout=30.0) as client:
        logger.info("\n" + "="*60)
        logger.info("🚀 Testing All Provider Types")
        logger.info("="*60 + "\n")

        logger.info("Available Providers:")
        for provider, model in test_cases:
            status = "✓" if provider.get_api_key() else "✗"
            logger.info(f"  {status} {provider.name} ({provider.provider_type})")

        logger.info("\n" + "="*60)
        logger.info("Starting Tests...")
        logger.info("="*60)

        # 依次测试每个 provider
        for provider, model in test_cases:
            await test_provider(client, provider, model)
            await asyncio.sleep(1)  # 避免请求过快

    logger.info("\n" + "="*60)
    logger.info("✅ All Tests Completed!")
    logger.info("="*60 + "\n")


async def test_streaming():
    """测试流式响应"""
    logger.info("\n" + "="*60)
    logger.info("🔄 Testing Streaming Response")
    logger.info("="*60 + "\n")

    provider = ProviderConfig(
        name="openai",
        base_url="https://api.openai.com/v1",
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        provider_type="openai"
    )

    if not provider.get_api_key():
        logger.warning("⚠️  No OpenAI API key, skipping streaming test")
        return

    messages = [
        {"role": "user", "content": "Count from 1 to 5"}
    ]

    async with LLMClient(timeout=30.0) as client:
        try:
            stream = await client.chat_completion(
                provider=provider,
                model="gpt-4o-mini",
                messages=messages,
                stream=True,
                max_tokens=50
            )

            logger.info("Streaming response:")
            logger.info("-" * 60)
            async for chunk in stream:
                print(chunk, end="", flush=True)
            logger.info("\n" + "-" * 60)
            logger.info("✅ Streaming test completed")

        except Exception as e:
            logger.error(f"❌ Streaming test failed: {e}")


if __name__ == "__main__":
    print("\n" + "="*60)
    print("🧪 Enhanced LLM Client - Provider Test Suite")
    print("="*60 + "\n")

    print("📋 Required Environment Variables:")
    print("  - OPENAI_API_KEY")
    print("  - ANTHROPIC_API_KEY")
    print("  - AWS_BEDROCK_TOKEN")
    print("  - AZURE_OPENAI_API_KEY")
    print("  - GOOGLE_API_KEY")
    print("  - VERTEX_AI_TOKEN")
    print("  - MINIMAX_API_KEY")
    print("  - DEEPSEEK_API_KEY")
    print("  - QWEN_API_KEY")
    print("\n📋 Optional (Local Services):")
    print("  - vLLM: http://127.0.0.1:8000")
    print("  - Ollama: http://127.0.0.1:11434")
    print("  - LM Studio: http://127.0.0.1:1234")
    print("\n" + "="*60 + "\n")

    # Run normal tests
    asyncio.run(test_all_providers())

    # Run streaming test
    asyncio.run(test_streaming())
