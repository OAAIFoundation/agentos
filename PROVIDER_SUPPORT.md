# LLM Provider Support Status

## Overview

AgentOS gateway supports **18 LLM providers** with intelligent routing and API format adaptation.

## Provider Support Matrix

| Provider | Status | API Format | Auth Method | Notes |
|----------|--------|------------|-------------|-------|
| **OpenAI** | ✅ Full | OpenAI | Bearer Token | Native support |
| **Anthropic** | ✅ Full | Custom | x-api-key header | Auto-adapted |
| **Google Gemini** | ⚠️ Partial | Custom | URL param | Auto-adapted |
| **DeepSeek** | ✅ Full | OpenAI | Bearer Token | OpenAI-compatible |
| **Qwen (Alibaba)** | ✅ Full | OpenAI | Bearer Token | OpenAI-compatible |
| **Zhipu (GLM)** | ✅ Full | OpenAI | Bearer Token | OpenAI-compatible |
| **Moonshot** | ✅ Full | OpenAI | Bearer Token | OpenAI-compatible |
| **Baidu** | ⚠️ Partial | Custom | Access Token | Requires OAuth |
| **MiniMax** | ✅ Full | OpenAI | Bearer Token | OpenAI-compatible |
| **Groq** | ✅ Full | OpenAI | Bearer Token | OpenAI-compatible |
| **Together AI** | ✅ Full | OpenAI | Bearer Token | OpenAI-compatible |
| **Replicate** | ✅ Full | OpenAI | Bearer Token | OpenAI proxy |
| **Cohere** | ⚠️ Partial | Custom | Bearer Token | May need adapter |
| **Mistral AI** | ✅ Full | OpenAI | Bearer Token | OpenAI-compatible |
| **Perplexity** | ✅ Full | OpenAI | Bearer Token | OpenAI-compatible |
| **Ollama** | ✅ Full | OpenAI | None | Local, no auth |
| **vLLM** | ✅ Full | OpenAI | None/Custom | Local deployment |
| **LM Studio** | ✅ Full | OpenAI | None | Local, no auth |

## Support Levels

### ✅ Full Support (15 providers)
- **Request interception**: All requests captured
- **Model replacement**: Can rewrite model names
- **Keyword routing**: Supports content-based routing
- **Streaming**: Full SSE passthrough
- **Error handling**: Transparent error propagation

**Providers:** OpenAI, DeepSeek, Qwen, Zhipu, Moonshot, MiniMax, Groq, Together AI, Replicate, Mistral, Perplexity, Ollama, vLLM, LM Studio

### ⚠️ Partial Support (3 providers)
- **Basic routing works** but may need manual configuration
- **API format differences** handled with adapters
- **Some features** may not be fully compatible

**Providers:** 
- **Anthropic Claude**: Different API format (uses `/messages` endpoint, requires `x-api-key` header)
- **Google Gemini**: Different API format (requires API key in URL, different message structure)
- **Baidu ERNIE**: Requires OAuth 2.0 access token flow

## API Format Support

### 1. OpenAI-Compatible (13 providers)
Standard OpenAI `/v1/chat/completions` format:

```json
{
  "model": "gpt-4",
  "messages": [{"role": "user", "content": "Hello"}],
  "temperature": 1.0,
  "stream": false
}
```

**Providers:** OpenAI, DeepSeek, Qwen, Zhipu, Moonshot, MiniMax, Groq, Together AI, Replicate, Mistral, Perplexity, Ollama, vLLM, LM Studio

**Gateway Support:** ✅ Native - No adaptation needed

### 2. Anthropic Claude API
Uses `/v1/messages` endpoint with different format:

```json
{
  "model": "claude-3-opus-20240229",
  "messages": [{"role": "user", "content": "Hello"}],
  "max_tokens": 1024,
  "system": "You are helpful"
}
```

**Authentication:** `x-api-key` header instead of `Authorization`

**Gateway Support:** ✅ Auto-adapted - Automatically converts OpenAI format to Claude format

### 3. Google Gemini API
Uses `/v1beta/models/{model}:generateContent`:

```json
{
  "contents": [
    {"role": "user", "parts": [{"text": "Hello"}]}
  ],
  "generationConfig": {
    "temperature": 1.0,
    "maxOutputTokens": 2048
  }
}
```

**Authentication:** API key as URL parameter `?key=xxx`

**Gateway Support:** ⚠️ Partial - Basic adapter implemented, may need refinement

### 4. Baidu ERNIE (Wenxin)
Requires OAuth 2.0 access token flow + custom endpoint structure.

**Gateway Support:** ⚠️ Partial - Needs custom OAuth implementation

## Usage Examples

### OpenAI-Compatible Providers (Easiest)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"
)

# Works with: DeepSeek, Qwen, Moonshot, Groq, etc.
response = client.chat.completions.create(
    model="deepseek-chat",  # Or qwen-turbo, moonshot-v1-8k, etc.
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Anthropic Claude (Auto-Adapted)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"
)

# Gateway automatically converts to Claude API format
response = client.chat.completions.create(
    model="claude-3-sonnet-20240229",
    messages=[{"role": "user", "content": "Hello"}]
)
```

### Google Gemini (Auto-Adapted)

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy"
)

# Gateway automatically converts to Gemini API format
response = client.chat.completions.create(
    model="gemini-1.5-pro",
    messages=[{"role": "user", "content": "Hello"}]
)
```

## Routing Features

All fully-supported providers can use these features:

### 1. Model Replacement
```yaml
- match_model: "gpt-4*"
  target_provider: "deepseek"
  target_model: "deepseek-chat"
```

### 2. Keyword-Based Routing
```yaml
- match_model: "gpt-4o"
  contains_keywords: ["translate", "summary"]
  target_provider: "openai"
  target_model: "gpt-4o-mini"
```

### 3. Cost Optimization
```yaml
# Route expensive Claude Opus to cheaper Sonnet
- match_model: "claude-3-opus*"
  target_provider: "anthropic"
  target_model: "claude-3-sonnet-20240229"
```

### 4. Streaming Support
All providers support streaming responses (SSE format).

## Adding New Providers

### For OpenAI-Compatible Providers:

1. Add to `config/config.yaml`:
```yaml
providers:
  new_provider:
    base_url: "https://api.example.com/v1"
    api_key: "env:NEW_PROVIDER_API_KEY"
```

2. Add API key to `.env`:
```bash
NEW_PROVIDER_API_KEY=your-key-here
```

3. Ready to use! Gateway handles it automatically.

### For Non-Compatible Providers:

1. Add provider config as above
2. Implement adapter function in `gateway.py`:
```python
def adapt_request_for_newprovider(payload: dict) -> tuple[str, dict, dict]:
    # Convert OpenAI format to provider's format
    adapted_payload = {...}
    return endpoint, headers, adapted_payload
```

3. Update `detect_provider_type()` function
4. Update `proxy_request()` to use adapter

## Testing Provider Support

Test any provider with this command:

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy" \
  -d '{
    "model": "your-model-name",
    "messages": [{"role": "user", "content": "test"}],
    "stream": false
  }'
```

Check gateway logs to see routing decisions and any errors.

## Known Limitations

1. **Baidu ERNIE**: Requires OAuth 2.0 token exchange (not yet implemented)
2. **Google Gemini**: Adapter is basic, may not support all features
3. **Cohere**: May require custom adapter for full feature parity
4. **Azure OpenAI**: Requires special endpoint structure with deployment names

## Future Enhancements

- [ ] Full Baidu ERNIE OAuth support
- [ ] Enhanced Google Gemini adapter
- [ ] Cohere native adapter
- [ ] Azure OpenAI deployment mapping
- [ ] Provider health checks
- [ ] Automatic failover between providers
- [ ] Response format normalization

---

**Summary:** 15/18 providers have full support with complete routing features. 3 providers have partial support and work with basic routing.
