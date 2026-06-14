# AgentOS - LLM Routing Gateway

A production-ready LLM API routing gateway with a web-based configuration dashboard. Route requests across multiple LLM providers (OpenAI, DeepSeek, Qwen, local models) with intelligent keyword-based routing, cost optimization, and hot configuration reload.

## 🌟 Key Features

- ✅ **Multi-Provider Routing** - OpenAI, DeepSeek, Qwen, Ollama, vLLM support
- ✅ **Web Dashboard** - Visual configuration editor with drag-drop routing rules
- ✅ **Smart Routing** - Keyword-based and wildcard pattern matching
- ✅ **Cost Optimization** - Auto-downgrade expensive models for simple tasks
- ✅ **Hot Reload** - Update configuration without restarting
- ✅ **OpenAI Compatible** - Drop-in replacement for OpenAI API
- ✅ **Streaming Support** - Full SSE (Server-Sent Events) passthrough
- ✅ **Production Ready** - Comprehensive test suite, error handling, backups
- 🆕 **Privacy Guard** - Three-layer security with PII masking, audit logging, and policy enforcement

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your API keys
```

Required environment variables:
```bash
OPENAI_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx
QWEN_API_KEY=sk-xxx
```

### 3. Start Gateway

```bash
python gateway.py
```

Gateway starts on `http://localhost:8000`

### 4. Access Dashboard

Open browser: **http://localhost:8000/dashboard**

Configure providers, routing rules, and save - all through the web UI!

## 🎨 Web Dashboard

Modern web interface built with Vue 3 + Tailwind CSS (zero build process):

**Features:**
- ✅ **Live Edit & Save**: Click "Edit" on any provider or route to modify configuration directly
- ✅ **Visual Provider Management**: Add/edit/delete providers with form validation
- ✅ **Route Editor**: Edit match patterns, target providers, models, and keywords
- ✅ **Real-time Persistence**: Changes save immediately to `config.yaml` with auto-backup
- ✅ **Hot Reload**: Configuration updates without restart
- ✅ **Input Validation**: Invalid configs rejected with clear error messages

**Access:** http://localhost:8000/dashboard

### Editing Configuration via UI

**Edit Provider:**
1. Navigate to Providers page
2. Click "Edit" button on any provider card
3. Modify Base URL or API Key (`env:VAR_NAME` format supported)
4. Click "Save Changes" - backup created automatically at `config.yaml.backup`

**Edit Route:**
1. Navigate to Route Rules page
2. Click "Edit" button on any route card
3. Modify:
   - **Match Model**: Use `*` wildcards (e.g., `gpt-4*`)
   - **Target Provider**: Select from dropdown
   - **Target Model**: Use `preserve` or specific model name
   - **Keywords**: Comma-separated list (e.g., `translate, summary`)
4. Click "Save Changes" - hot reload applies instantly

All changes are validated server-side and reject invalid configurations with 400 status.

## ⚙️ Configuration

### config.yaml Structure

Located in `config/config.yaml`:

```yaml
# Define providers
providers:
  openai:
    base_url: "https://api.openai.com/v1"
    api_key: "env:OPENAI_API_KEY"  # Reads from environment

  deepseek:
    base_url: "https://api.deepseek.com/v1"
    api_key: "env:DEEPSEEK_API_KEY"

  local_vllm:
    base_url: "http://127.0.0.1:8000/v1"
    api_key: "EMPTY"

# Define routing rules (first match wins!)
routes:
  # Rule 1: Keyword-based routing
  - match_model: "gpt-4o"
    contains_keywords: ["translate", "summary"]
    target_provider: "local_vllm"
    target_model: "Qwen2-7B-Instruct"

  # Rule 2: Wildcard matching
  - match_model: "gpt-4*"
    target_provider: "deepseek"
    target_model: "deepseek-chat"

  # Rule 3: Fallback
  - match_model: "*"
    target_provider: "openai"
    target_model: "preserve"  # Keep original model name
```

**Edit via Dashboard:** http://localhost:8000/dashboard

## 🌐 Provider Support

AgentOS supports **18 LLM providers** with intelligent routing and API format adaptation.

### Provider Support Matrix

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

**Summary:** 15/18 providers have full support. 3 providers (Anthropic, Google Gemini, Baidu) have partial support with auto-adapters.

### Support Levels

**✅ Full Support (15 providers)**
- Request interception & model replacement
- Keyword-based routing
- Streaming (SSE) passthrough
- Transparent error handling

**⚠️ Partial Support (3 providers)**
- Anthropic Claude: Auto-adapter for `/messages` endpoint
- Google Gemini: Auto-adapter for custom format
- Baidu ERNIE: Requires OAuth 2.0 (basic support)

### Adding New Providers

**For OpenAI-Compatible Providers:**
```yaml
providers:
  new_provider:
    base_url: "https://api.example.com/v1"
    api_key: "env:NEW_PROVIDER_API_KEY"
```

Then add to `.env`:
```bash
NEW_PROVIDER_API_KEY=your-key-here
```

**For Custom API Formats:**
Implement adapter function in `gateway.py` - see Anthropic/Gemini adapters as examples.

## 🎯 Usage Examples

### Python SDK

```python
from openai import OpenAI

client = OpenAI(
    api_key="dummy",  # Not used, gateway handles routing
    base_url="http://localhost:8000/v1"
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}]
)
```

### cURL

```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

### LangChain

```python
from langchain.chat_models import ChatOpenAI

llm = ChatOpenAI(
    openai_api_key="dummy",
    openai_api_base="http://localhost:8000/v1",
    model_name="gpt-4o"
)
```

## 🧪 Testing

Run comprehensive test suite:

```bash
# Gateway routing tests
python -m pytest tests/test_gateway.py -v

# UI edit/save functionality tests
python tests/test_edit_save.py

# Privacy Guard tests
python -m pytest tests/test_privacy_guard.py -v

# UI integration tests
python tests/test_ui_integration.py
```

**Test Coverage:**
- ✅ Keyword-based routing
- ✅ Wildcard pattern matching  
- ✅ Model downgrading
- ✅ Default passthrough
- ✅ Error handling
- ✅ Provider edit and save
- ✅ Route edit and save (with keywords)
- ✅ Config validation and rejection
- ✅ Backup file creation
- ⏭️ Streaming (production-validated)

**All tests use mocked HTTP requests - zero API token consumption!**

## 🔧 API Endpoints

### LLM Proxy (OpenAI Compatible)

```
POST /v1/chat/completions
```

### Dashboard & Configuration

```
GET  /dashboard              # Web dashboard UI
GET  /api/config             # Get configuration as JSON
POST /api/config             # Update configuration (used by Edit/Save)
POST /api/reload             # Hot reload configuration
GET  /api/logs               # Get audit logs (with level filtering)
GET  /health                 # Health check
```

**Edit/Save via API:**
```bash
# Get current config
curl http://localhost:8000/api/config

# Save modified config (creates backup automatically)
curl -X POST http://localhost:8000/api/config \
  -H "Content-Type: application/json" \
  -d @config.json
```

## 📊 Routing Logic

**Rules are evaluated in order - first match wins!**

Example routing decisions:

| Request Model | Keywords | Matched Rule | Target | Result |
|---------------|----------|--------------|--------|--------|
| `gpt-4o` | "summary" | Rule 1 | local_vllm | Qwen2-7B-Instruct |
| `gpt-4o` | none | Rule 2 | openai | gpt-4o-mini |
| `gpt-4-turbo` | none | Rule 3 | deepseek | deepseek-chat |
| `claude-3` | none | Rule 4 | ollama | llama3 |

## 🎯 Common Use Cases

### Cost Optimization

Route expensive models to cheaper alternatives:

```yaml
- match_model: "gpt-4*"
  target_provider: "deepseek"
  target_model: "deepseek-chat"  # 10x cheaper
```

### Smart Downgrading

Route simple tasks to smaller models:

```yaml
- match_model: "gpt-4o"
  contains_keywords: ["translate", "summary"]
  target_provider: "openai"
  target_model: "gpt-4o-mini"
```

### Local Development

Route everything to local Ollama:

```yaml
- match_model: "*"
  target_provider: "ollama"
  target_model: "llama3"
```

### Vendor Lock-in Prevention

Easily switch providers without code changes - just update config!

## 📁 Project Structure

```
agentos/
├── gateway.py              # Main gateway application
├── privacy_guard.py        # Privacy Guard security module
├── main.py                 # Legacy gateway (deprecated)
├── requirements.txt        # Python dependencies
├── README.md               # This file
├── PRIVACY_GUARD.md        # Privacy Guard documentation
├── config/
│   ├── config.yaml         # Provider & routing + privacy configuration
│   ├── .env.example        # Environment variable template
│   └── .env.gateway.example
├── web/
│   └── index.html          # Dashboard UI (Vue 3 + Tailwind)
├── tests/                  # All test files (organized)
│   ├── test_gateway.py     # Gateway test suite
│   ├── test_privacy_guard.py  # Privacy Guard unit tests (15 tests)
│   ├── test_privacy_guard_live.py  # Live integration tests
│   ├── test_gateway.sh     # Gateway shell test script
│   └── demo_privacy_guard.sh  # Privacy Guard demo script
└── docs/
    └── CLAUDE.md           # Project development guidelines
```

## 🔒 Security

### Privacy Guard (NEW!)

Three-layer security system for LLM requests:

1. **Policy Check**: Conditional routing based on prompt characteristics
   - Block prompt injection attempts
   - Route long/sensitive prompts to secure providers
   - Enforce content policies

2. **Regex Audit**: Pattern-based detection
   - Block API keys, credentials, tokens
   - Log internal codenames and sensitive terms
   - Detect PII before it reaches LLMs

3. **Data Masking**: Bidirectional PII redaction
   - Mask emails, phones, SSNs in requests
   - Automatically unmask in responses (streaming supported!)
   - Transparent to end users

**Quick Example**:
```yaml
privacy_guard:
  enabled: true
  data_masking:
    rules:
      - name: "Email"
        pattern: "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b"
        placeholder_prefix: "[REDACTED_EMAIL_"
```

📖 **Full Documentation**: See [PRIVACY_GUARD.md](./PRIVACY_GUARD.md)

### Best Practices

- Use `env:VAR_NAME` for API keys (never hardcode)
- Keep `.env` out of version control
- Automatic config backups before save
- Input validation on all API endpoints
- Enable Privacy Guard in production

### Production Recommendations

- Enable HTTPS
- Add authentication middleware
- Set up rate limiting
- Enable audit logging
- Configure Privacy Guard rules

## 🛠️ Development

### Editing Providers and Routes

**Via Web Dashboard (Recommended):**
1. Open http://localhost:8000/dashboard
2. Click "Edit" button on any provider or route card
3. Modify configuration in the popup modal
4. Click "Save Changes" - backup created at `config.yaml.backup`

**Via Config File:**
1. Edit `config/config.yaml` directly
2. POST to `/api/reload` or restart gateway

**Adding New Provider:**
```yaml
providers:
  new_provider:
    base_url: "https://api.example.com/v1"
    api_key: "env:NEW_PROVIDER_KEY"
```

**Adding New Route:**
```yaml
routes:
  - match_model: "claude-*"
    target_provider: "new_provider"
    target_model: "preserve"
```

Route order matters - first match wins!

### Running Tests

```bash
# All tests
python -m pytest tests/test_gateway.py -v

# Specific test
python -m pytest tests/test_gateway.py::test_case1_keyword_downgrade -v

# With coverage
python -m pytest tests/test_gateway.py --cov=gateway
```

## 🏗️ Architecture

```
┌─────────────┐
│   Agent     │  (OpenAI SDK → localhost:8000)
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│      LLM Routing Gateway (gateway.py)       │
│  • Load config.yaml                         │
│  • Match routing rules (keywords, patterns) │
│  • Rewrite model name                       │
│  • Select provider + API key                │
│  • Web Dashboard (Vue 3 + Tailwind)         │
└──────┬──────────────────────────────────────┘
       │
       ├─────► OpenAI API
       ├─────► DeepSeek API
       ├─────► Qwen (Alibaba)
       ├─────► Local Ollama
       └─────► Local vLLM
```

## 📚 Documentation

All documentation is consolidated in this README. See CLAUDE.md for project-specific development guidelines.

## 🐛 Troubleshooting

**Gateway won't start:**
- Check `config/config.yaml` syntax (valid YAML)
- Verify environment variables are set in `.env`
- Run `pip install -r requirements.txt`

**Requests fail:**
- Check provider API keys are correct
- Verify provider `base_url` is accessible
- Check gateway logs for errors

**Wrong routing:**
- Routes match in order (first match wins)
- More specific rules should be at the top
- Test with dashboard's visual editor

**Dashboard not loading:**
- Ensure `web/index.html` exists
- Check gateway is running: `curl http://localhost:8000/health`
- Try direct URL: http://localhost:8000/dashboard

## 📝 Project Guidelines

**Language Policy:** All code, comments, and documentation in English (see `docs/CLAUDE.md`)

**Documentation Policy:** No excessive summary files - keep repo clean (see `docs/CLAUDE.md`)

## 📄 License

MIT

---

**Need help?** Open an issue on GitHub or check the logs for detailed error messages.

**Quick Links:**
- Dashboard: http://localhost:8000/dashboard
- Health Check: http://localhost:8000/health
- API Docs: http://localhost:8000/docs (FastAPI auto-generated)
