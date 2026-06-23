"""
Example: How to configure Agent to use Router
代替透明代理 proxy_server.py 的新方法

核心思路：
1. 不使用 HTTP_PROXY 环境变量
2. 在 Agent 配置中显式指定 base_url 指向 router
3. Router 根据 config.yaml 自动路由到合适的 LLM 提供商
"""

from openai import OpenAI


# ============================================================
# 方法 1: OpenAI SDK (推荐)
# ============================================================

def example_openai_sdk():
    """
    使用 OpenAI SDK 连接到 Router

    配置说明:
    - base_url: 指向 router_server.py 的地址 (默认 http://localhost:8000/v1)
    - api_key: 随意设置 (router 会根据 config.yaml 中的 provider 配置自动使用正确的 API key)
    """
    client = OpenAI(
        base_url="http://localhost:8000/v1",  # Router 地址
        api_key="dummy-key"  # 任意值，router 会替换
    )

    # 发送请求 - 模型名称会被 router 自动路由
    response = client.chat.completions.create(
        model="gpt-4o",  # Router 会根据 config.yaml 规则路由
        messages=[
            {"role": "user", "content": "Translate 'Hello' to Chinese"}
        ],
        temperature=0.7,
    )

    print("Response:", response.choices[0].message.content)
    print(f"Actual model used: {response.model}")  # Router 会返回实际使用的模型


# ============================================================
# 方法 2: LangChain (Agent 框架常用)
# ============================================================

def example_langchain():
    """
    使用 LangChain 连接到 Router
    """
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        base_url="http://localhost:8000/v1",
        api_key="dummy-key",
        model="gpt-4o",
    )

    response = llm.invoke("What is 2+2?")
    print("Response:", response.content)


# ============================================================
# 方法 3: LlamaIndex (RAG 应用常用)
# ============================================================

def example_llamaindex():
    """
    使用 LlamaIndex 连接到 Router
    """
    from llama_index.llms.openai import OpenAI as LlamaIndexOpenAI

    llm = LlamaIndexOpenAI(
        api_base="http://localhost:8000/v1",
        api_key="dummy-key",
        model="gpt-4-turbo",
    )

    response = llm.complete("Explain quantum computing in 2 sentences")
    print("Response:", response.text)


# ============================================================
# 方法 4: AutoGPT / AgentGPT 配置
# ============================================================

"""
在 AutoGPT 的 .env 文件中配置:

OPENAI_API_BASE=http://localhost:8000/v1
OPENAI_API_KEY=dummy-key

AutoGPT 会自动使用 router 作为后端
"""


# ============================================================
# 方法 5: CrewAI (Multi-Agent 系统)
# ============================================================

def example_crewai():
    """
    使用 CrewAI 连接到 Router
    """
    from crewai import Agent, Task, Crew
    from langchain_openai import ChatOpenAI

    # 配置 LLM 指向 router
    llm = ChatOpenAI(
        base_url="http://localhost:8000/v1",
        api_key="dummy-key",
        model="gpt-4o",
    )

    # 创建 Agent (会自动使用 router)
    researcher = Agent(
        role="Researcher",
        goal="Research AI trends",
        llm=llm,
    )

    task = Task(
        description="Research latest AI breakthroughs",
        agent=researcher,
    )

    crew = Crew(agents=[researcher], tasks=[task])
    result = crew.kickoff()
    print("Result:", result)


# ============================================================
# 方法 6: Anthropic Claude SDK
# ============================================================

def example_anthropic_claude():
    """
    使用 Anthropic SDK 连接到 Router
    注意: Router 需要支持 Anthropic API 格式 (待实现)
    """
    from anthropic import Anthropic

    client = Anthropic(
        base_url="http://localhost:8000",  # Router 地址
        api_key="dummy-key",
    )

    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=1024,
        messages=[
            {"role": "user", "content": "Hello, Claude!"}
        ]
    )

    print("Response:", response.content[0].text)


# ============================================================
# 路由示例：展示 Router 如何根据关键词路由
# ============================================================

def demonstrate_keyword_routing():
    """
    演示基于关键词的路由

    根据 config.yaml 中的规则:
    - 包含 "translate", "summary" 关键词的请求 → gpt-4o-mini (便宜模型)
    - 其他请求 → gpt-4o (保持原样)
    """
    client = OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="dummy-key"
    )

    # Case 1: 包含 "translate" 关键词 → 应该路由到 gpt-4o-mini
    print("\n=== Test 1: Keyword Match (translate) ===")
    response1 = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Please translate this: Hello"}]
    )
    print(f"Requested: gpt-4o")
    print(f"Actually used: {response1.model}")  # 应该显示 gpt-4o-mini

    # Case 2: 不包含关键词 → 保持 gpt-4o
    print("\n=== Test 2: No Keyword Match ===")
    response2 = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Explain quantum computing"}]
    )
    print(f"Requested: gpt-4o")
    print(f"Actually used: {response2.model}")  # 应该显示 gpt-4o


# ============================================================
# 多模型路由示例
# ============================================================

def demonstrate_multi_provider_routing():
    """
    演示多提供商路由

    根据 config.yaml:
    - gpt-4* → deepseek-chat (成本节省)
    - claude-* → anthropic (保持原样)
    - qwen-* → qwen (保持原样)
    """
    client = OpenAI(
        base_url="http://localhost:8000/v1",
        api_key="dummy-key"
    )

    test_cases = [
        ("gpt-4-turbo", "Should route to DeepSeek"),
        ("claude-3-opus-20240229", "Should route to Anthropic"),
        ("qwen-max", "Should route to Qwen"),
    ]

    for model, description in test_cases:
        print(f"\n=== Testing: {model} ===")
        print(f"Expected: {description}")

        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Hi"}],
                max_tokens=10
            )
            print(f"Actually used: {response.model}")
        except Exception as e:
            print(f"Error: {e}")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Router Usage Examples")
    print("=" * 60)

    print("\n1. Make sure router_server.py is running:")
    print("   python router_server.py")

    print("\n2. Examples:")
    print("   - OpenAI SDK: example_openai_sdk()")
    print("   - LangChain: example_langchain()")
    print("   - Keyword Routing: demonstrate_keyword_routing()")

    print("\n" + "=" * 60)

    # Run basic example
    print("\nRunning OpenAI SDK example...")
    try:
        example_openai_sdk()
    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure:")
        print("1. router_server.py is running (python router_server.py)")
        print("2. You have at least one LLM provider configured in config/config.yaml")
        print("3. The provider's API key is set in environment variables")
