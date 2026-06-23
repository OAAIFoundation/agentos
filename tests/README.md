# Test Suite Documentation

Complete test coverage for AgentOS Router supporting 15+ LLM providers.

## 📊 Test Coverage

| Test File | Coverage | Providers | Status |
|-----------|----------|-----------|--------|
| `test_openai.py` | OpenAI API | OpenAI | ✅ |
| `test_anthropic.py` | Anthropic format conversion | Anthropic | ✅ |
| `test_bedrock.py` | AWS Bedrock | Bedrock | ✅ |
| `test_azure_openai.py` | Azure API versioning | Azure OpenAI | ✅ |
| `test_chinese_llms.py` | Chinese providers | DeepSeek, Qwen, Baichuan, Zhipu, Moonshot, MiniMax | ✅ |
| `test_local_inference.py` | Local deployment | vLLM, Ollama, LM Studio | ✅ |
| `test_streaming.py` | SSE streaming | All providers | ✅ |
| `test_provider_detection.py` | Auto-detection | All providers | ✅ |
| `test_router_integration.py` | End-to-end routing | All providers | ✅ |
| `test_all_providers.py` | Complete integration | All 15+ providers | ✅ |

## 🚀 Quick Start

### Run All Tests

```bash
# Run complete test suite
python tests/run_all_tests.py

# Run with detailed output
python tests/run_all_tests.py --verbose

# Run specific provider tests
python tests/run_all_tests.py --provider openai
python tests/run_all_tests.py --provider anthropic
python tests/run_all_tests.py --provider chinese
```

### Run Individual Test Files

```bash
# OpenAI provider tests
pytest tests/test_openai.py -v

# Anthropic format conversion tests
pytest tests/test_anthropic.py -v

# Streaming tests
pytest tests/test_streaming.py -v

# Router integration tests
pytest tests/test_router_integration.py -v
```

### Run Standalone Test Script

```bash
# Complete provider integration test (no dependencies)
python test_all_providers.py
```

## 📁 Test File Structure

```
tests/
├── README.md                      # This file
├── run_all_tests.py               # Main test runner
├── test_openai.py                 # OpenAI provider tests
├── test_anthropic.py              # Anthropic + format conversion
├── test_bedrock.py                # AWS Bedrock tests
├── test_azure_openai.py           # Azure OpenAI + API version
├── test_chinese_llms.py           # DeepSeek, Qwen, Baichuan, etc.
├── test_local_inference.py        # vLLM, Ollama, LM Studio
├── test_streaming.py              # SSE streaming for all providers
├── test_provider_detection.py     # Auto-detection logic
├── test_router_integration.py     # End-to-end routing tests
│
├── test_gateway.py                # Legacy gateway tests
├── test_transparent_proxy.py      # Transparent proxy tests
├── test_edit_save.py              # Dashboard UI tests
├── test_privacy_guard.py          # Privacy Guard tests
└── ...                            # Other test files
```

## 🧪 Test Categories

### 1. Provider-Specific Tests

Test individual provider implementations:

- **OpenAI**: Standard Bearer token authentication
- **Anthropic**: Custom x-api-key header + request/response conversion
- **Bedrock**: AWS Bearer token + special model naming
- **Azure**: api-key header + API version parameter
- **Chinese LLMs**: OpenAI-compatible with Bearer tokens
- **Local**: No authentication, local deployment

### 2. Feature Tests

Test cross-provider features:

- **Streaming**: SSE format for all providers
- **Detection**: Automatic provider type identification
- **Routing**: Match patterns, keywords, priority
- **Format Conversion**: Anthropic OpenAI ↔ Anthropic Messages API

### 3. Integration Tests

End-to-end workflow tests:

- Router startup and configuration loading
- Request routing through multiple rules
- Provider failover and error handling
- Dashboard API integration

## 📝 Test Naming Conventions

```python
# Provider tests
def test_openai_bearer_auth():
    """Test OpenAI Bearer token authentication"""

def test_anthropic_format_conversion():
    """Test Anthropic request format conversion"""

# Feature tests
def test_streaming_sse_format():
    """Test SSE format for streaming responses"""

def test_provider_auto_detection():
    """Test automatic provider type detection"""

# Integration tests
def test_router_end_to_end():
    """Test complete request routing flow"""

def test_config_hot_reload():
    """Test configuration hot reload"""
```

## 🎯 Test Assertions

### Standard Assertions

```python
# Provider detection
assert provider_type == "anthropic"

# Authentication header
assert headers["x-api-key"] == api_key

# Request format
assert "max_tokens" in body  # Anthropic required field

# Response format
assert "choices" in response
assert response["choices"][0]["message"]["content"]

# Streaming format
assert chunk.startswith("data: ")
```

### Provider-Specific Assertions

```python
# Anthropic
assert body["system"] == "You are helpful"  # System message separate
assert "messages" in body  # No system in messages array

# Azure OpenAI
assert "api-version" in url_params
assert headers.get("api-key")  # No Bearer prefix

# Bedrock
assert model.startswith("anthropic.")  # Special naming
assert headers["Authorization"].startswith("Bearer ")
```

## 🔧 Environment Variables

### Required for Full Test Suite

```bash
# International Providers
export OPENAI_API_KEY="sk-..."
export ANTHROPIC_API_KEY="sk-ant-..."
export AWS_BEDROCK_TOKEN="..."
export AZURE_OPENAI_API_KEY="..."
export GOOGLE_API_KEY="..."
export VERTEX_AI_TOKEN="..."

# Chinese Providers
export DEEPSEEK_API_KEY="sk-..."
export QWEN_API_KEY="sk-..."
export BAICHUAN_API_KEY="sk-..."
export ZHIPU_API_KEY="..."
export MOONSHOT_API_KEY="..."
export MINIMAX_API_KEY="..."

# Local Services (optional)
# vLLM: http://localhost:8000
# Ollama: http://localhost:11434
# LM Studio: http://localhost:1234
```

### Skip Tests Without Keys

Tests automatically skip providers without API keys:

```python
@pytest.mark.skipif(not os.getenv("OPENAI_API_KEY"), reason="No OpenAI API key")
def test_openai_api():
    ...
```

## 📊 Test Coverage Report

```bash
# Generate coverage report
pytest --cov=llm_client_enhanced --cov=config_loader --cov=router_server tests/

# HTML coverage report
pytest --cov=llm_client_enhanced --cov-report=html tests/
# Open htmlcov/index.html in browser
```

## 🐛 Debugging Tests

### Verbose Output

```bash
# Show detailed test output
pytest tests/test_anthropic.py -v -s

# Show print statements
pytest tests/test_anthropic.py --capture=no

# Run specific test
pytest tests/test_anthropic.py::test_anthropic_format_conversion -v
```

### Mock vs Live Tests

Most tests use mocked HTTP requests (no API calls):

```python
# Mocked test (fast, no API cost)
@patch('httpx.AsyncClient.post')
def test_openai_mock(mock_post):
    mock_post.return_value.json.return_value = {...}
    ...

# Live test (real API call)
@pytest.mark.live
async def test_openai_live():
    response = await client.chat_completion(...)
    ...

# Run only mock tests (default)
pytest tests/

# Run live tests
pytest tests/ -m live
```

## 📈 Adding New Provider Tests

1. **Create test file**: `tests/test_newprovider.py`

2. **Add provider config**:
```python
provider = ProviderConfig(
    name="newprovider",
    base_url="https://api.newprovider.com/v1",
    api_key=os.getenv("NEWPROVIDER_API_KEY"),
    provider_type="newprovider"
)
```

3. **Test authentication**:
```python
def test_newprovider_auth():
    client = EnhancedLLMClient()
    headers = client._build_headers(provider, "newprovider", api_key)
    assert headers["Authorization"] == f"Bearer {api_key}"
```

4. **Test detection**:
```python
def test_newprovider_detection():
    detected_type = client._detect_provider_type(provider)
    assert detected_type == "newprovider"
```

5. **Test chat completion**:
```python
@pytest.mark.asyncio
async def test_newprovider_chat():
    response = await client.chat_completion(
        provider=provider,
        model="model-name",
        messages=[{"role": "user", "content": "Hello"}]
    )
    assert "choices" in response
```

6. **Update run_all_tests.py** to include new test file

## ✅ Test Checklist

For each new provider, verify:

- [ ] Provider config loading
- [ ] Authentication header construction
- [ ] API endpoint URL generation
- [ ] Request body formatting
- [ ] Response format handling
- [ ] Streaming support (if applicable)
- [ ] Error handling
- [ ] Auto-detection logic
- [ ] Integration with router

## 📚 References

- **Provider Comparison**: `../PROVIDER_COMPARISON.md`
- **Quick Start Guide**: `../MULTI_PROVIDER_QUICKSTART.md`
- **Main README**: `../README.md`
- **Enhanced Client**: `../llm_client_enhanced.py`
- **Config Loader**: `../config_loader.py`

---

**🎉 Complete test coverage for all 15+ providers!**

*Last updated: 2026-06-23*
