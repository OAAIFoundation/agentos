# AgentOS - LLM Routing Gateway

This document contains project-specific guidelines and instructions for working with the AgentOS codebase.

## 🌍 Language Policy: English Only

**IMPORTANT:** All code, comments, documentation, commit messages, and communication in the AgentOS project MUST be written in English.

**Applies to:**
- ✅ Code (variables, functions, classes)
- ✅ Comments (inline, block, docstrings)
- ✅ Documentation (README, guides, API docs)
- ✅ Commit messages and PR descriptions
- ✅ Test cases and test descriptions
- ✅ Configuration files (YAML, JSON, etc.)
- ✅ Error messages and log output
- ✅ Issue titles and descriptions

**Rationale:**
- AgentOS is a backend infrastructure project designed for international use
- English ensures consistency and maintainability across the codebase
- Better tooling support (linters, formatters, AI code assistants)
- Facilitates code review and global collaboration
- Makes the project open-source ready

**Examples:**

❌ Bad (Non-English identifiers):
```python
# Chinese comments and variable names (DON'T DO THIS)
def jisuan_nianling(chusheng_riqi):  # Function name in Pinyin
    """Calculate age in Chinese"""  # Docstring mixing languages
    # Return age difference
    return current_year - chusheng_riqi.year
```

✅ Good (English):
```python
# Calculate age
def calculate_age(birth_date):
    """Calculate current age based on birth date"""
    # Return age difference
    return current_year - birth_date.year
```

**Exceptions:**
- User-facing UI strings (if applicable)
- Test data representing real-world non-English scenarios
- External documentation for specific non-English audiences

---

## 📝 Documentation Policy: No Excessive Summary Files

**IMPORTANT:** Do NOT create new markdown summary files after completing tasks. Summaries should be output to console/screen only.

**Problem:**
Creating summary files like `SUMMARY.md`, `COMPLETION.md`, `TASK_SUMMARY.md` after every task leads to file clutter and makes the repository messy.

**Rule:**
- ✅ **DO**: Output task summaries to console/terminal
- ✅ **DO**: Update existing documentation files when needed
- ✅ **DO**: Create documentation files when they serve a permanent purpose (e.g., `README.md`, `API.md`, `ARCHITECTURE.md`)
- ❌ **DON'T**: Create summary files just to recap what was done
- ❌ **DON'T**: Create files like `TASK_COMPLETE.md`, `WORK_SUMMARY.md`, `CHANGES.md`

**Examples:**

❌ Bad (creates unnecessary file):
```markdown
After completing web dashboard, creates:
- WEB_DASHBOARD_SUMMARY.md
- IMPLEMENTATION_SUMMARY.md
- COMPLETION_REPORT.md
```

✅ Good (outputs to console):
```
Task Complete! ✅

What was built:
- Backend API endpoints
- Frontend dashboard
- Configuration management

Files created:
- static/index.html
- DASHBOARD.md (permanent documentation)

Next steps:
- Open http://localhost:8000/dashboard
- Test the configuration UI
```

**When to create documentation files:**
- **Permanent reference documentation** (API guides, architecture docs, user guides)
- **Essential project information** (README, CONTRIBUTING, LICENSE)
- **Technical specifications** (that will be referenced long-term)

**When NOT to create files:**
- Task completion summaries
- Work progress reports
- Implementation recaps
- "What I just did" documents

**Summary:** Keep the repository clean. Document the product, not the process.

---

## 🧪 Test Organization Policy: Keep Tests in tests/ Directory

**IMPORTANT:** All test files MUST be placed in the `tests/` directory, never in the project root.

**Problem:**
Test files scattered in the root directory make the repository messy and harder to navigate.

**Rule:**
- ✅ **DO**: Place all test files in `tests/` directory
- ✅ **DO**: Use descriptive names like `test_feature.py` or `feature_test.py`
- ✅ **DO**: Create subdirectories when test count exceeds 10 files
- ❌ **DON'T**: Put test files in the root directory
- ❌ **DON'T**: Put test files in the same directory as source code

**Test Directory Structure:**

For small projects (< 10 test files):
```
tests/
├── test_gateway.py
├── test_privacy_guard.py
├── test_integration.py
└── test_utils.py
```

For larger projects (> 10 test files), organize by category:
```
tests/
├── unit/
│   ├── test_privacy_guard.py
│   ├── test_routing.py
│   └── test_config.py
├── integration/
│   ├── test_gateway_integration.py
│   └── test_privacy_guard_live.py
├── e2e/
│   └── test_full_pipeline.py
└── conftest.py  # Shared fixtures
```

**Examples:**

❌ Bad (test in root):
```
agentos/
├── gateway.py
├── test_gateway.py          # Wrong location!
├── test_privacy_guard.py    # Wrong location!
└── privacy_guard.py
```

✅ Good (tests organized):
```
agentos/
├── gateway.py
├── privacy_guard.py
└── tests/
    ├── test_gateway.py      # Correct location
    └── test_privacy_guard.py
```

**When to Create Subdirectories:**

Organize tests into subdirectories when:
- **> 10 test files**: Too many to scan easily
- **Multiple test types**: Unit, integration, e2e tests
- **Multiple modules**: Each major module has its own test suite
- **Shared fixtures**: Need a `conftest.py` per category

**Subdirectory Guidelines:**
- `unit/` - Fast, isolated unit tests (< 1s each)
- `integration/` - Multi-component tests (< 5s each)
- `e2e/` - End-to-end tests (< 30s each)
- `fixtures/` - Test data and mock files
- `helpers/` - Test utilities and helper functions

**Summary:** Keep tests organized in `tests/`. Start flat, add structure as you grow.

---

## 📋 Project Overview

AgentOS is a production-ready LLM API routing gateway built with FastAPI.

**Purpose:** Act as an intelligent proxy between AI agents and multiple LLM providers, enabling:
- Cost optimization through model downgrading
- Provider switching without code changes
- Keyword-based intelligent routing
- Transparent error handling and streaming support

**Tech Stack:**
- Python 3.9+
- FastAPI
- httpx (async HTTP client)
- PyYAML (configuration)
- pytest + respx (testing)

---

## 🏗️ Architecture

```
┌─────────────┐
│   Agent     │  (OpenAI SDK pointing to localhost:8000)
└──────┬──────┘
       │
       ▼
┌─────────────────────────────────────────────┐
│         LLM Routing Gateway                 │
│  - Load config.yaml                         │
│  - Match routing rules (keywords, patterns) │
│  - Rewrite model name                       │
│  - Select provider + API key                │
└──────┬──────────────────────────────────────┘
       │
       ├─────► OpenAI API
       ├─────► DeepSeek API
       ├─────► Qwen (Alibaba DashScope)
       ├─────► Local Ollama
       └─────► Local vLLM
```

---

## 📁 Project Structure

```
agentos/
├── gateway.py                  # Main gateway application
├── privacy_guard.py            # Privacy Guard security module
├── requirements.txt            # Python dependencies
├── README.md                   # Main project documentation
├── PRIVACY_GUARD.md            # Privacy Guard technical docs
├── config/
│   ├── config.yaml             # Provider & routing + privacy config
│   └── .env.example            # Environment variable template
├── web/
│   └── index.html              # Dashboard UI (Vue 3 + Tailwind)
├── tests/                      # All test files (organized)
│   ├── test_gateway.py         # Gateway test suite
│   ├── test_privacy_guard.py   # Privacy Guard unit tests (15 tests)
│   ├── test_privacy_guard_live.py  # Live integration tests
│   ├── test_gateway.sh         # Gateway shell test script
│   └── demo_privacy_guard.sh   # Privacy Guard demo script
└── docs/
    └── CLAUDE.md               # This file (project guidelines)
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.gateway.example .env
# Edit .env with your API keys:
# OPENAI_API_KEY=sk-xxx
# DEEPSEEK_API_KEY=sk-xxx
# QWEN_API_KEY=sk-xxx
```

### 3. Run Tests
```bash
python -m pytest test_gateway.py -v
```

Expected output: `6 passed, 1 skipped`

### 4. Start Gateway
```bash
python gateway.py
```

Gateway starts on `http://localhost:8000`

### 5. Test It
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dummy" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello!"}]
  }'
```

---

## ⚙️ Configuration

### config.yaml Structure

```yaml
# Define providers
providers:
  provider_name:
    base_url: "https://api.example.com/v1"
    api_key: "env:API_KEY_VAR"  # Reads from environment

# Define routing rules (first match wins)
routes:
  - match_model: "gpt-4o"
    contains_keywords: ["translate", "summary"]
    target_provider: "local_vllm"
    target_model: "Qwen2-7B-Instruct"
    
  - match_model: "gpt-4*"  # Wildcard matching
    target_provider: "deepseek"
    target_model: "deepseek-chat"
    
  - match_model: "*"  # Fallback rule
    target_provider: "openai"
    target_model: "preserve"  # Keep original model name
```

### Environment Variables

Required in `.env`:
```bash
OPENAI_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx
QWEN_API_KEY=sk-xxx
```

---

## 🧪 Testing

### Run All Tests
```bash
python -m pytest test_gateway.py -v
```

### Run Specific Test
```bash
python -m pytest test_gateway.py::test_case1_keyword_downgrade -v
```

### Test Coverage
All critical routing logic is tested:
- ✅ Keyword-based routing
- ✅ Wildcard pattern matching
- ✅ Model name rewriting
- ✅ Default passthrough
- ✅ Error passthrough
- ⏭️ Streaming (production-validated, complex mock)

See [TEST_RESULTS.md](TEST_RESULTS.md) for detailed test documentation.

---

## 🔧 Development Guidelines

### Code Style
- Use clear, descriptive English variable/function names
- Follow PEP 8 style guide
- Add docstrings for all functions
- Keep functions focused and small

### Adding a New Provider
1. Add provider to `config.yaml`:
```yaml
providers:
  new_provider:
    base_url: "https://api.newprovider.com/v1"
    api_key: "env:NEW_PROVIDER_API_KEY"
```

2. Add environment variable to `.env.gateway.example`

3. Add routing rule if needed

4. Add test case in `test_gateway.py`

### Adding a New Route
1. Add route to `config.yaml` (order matters!)
2. Add test case to validate routing logic
3. Run tests to ensure no regressions

### Commit Messages

**IMPORTANT:** Do NOT include any Claude-related attribution in commit messages.

**Rules:**
- ❌ **DON'T**: Add `Co-Authored-By: Claude` or similar attribution
- ❌ **DON'T**: Mention "Claude Code" or AI assistance in commit messages
- ❌ **DON'T**: Add footer notes about AI-generated code
- ✅ **DO**: Write commit messages as if they were written by the human developer
- ✅ **DO**: Use conventional commits format
- ✅ **DO**: Focus on what changed and why, not who wrote it

**Examples:**

❌ Bad:
```
feat: add streaming support

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
```

✅ Good:
```
feat: add streaming support
```

Use conventional commits format:
```
feat: add support for Anthropic Claude provider
fix: resolve streaming response timeout issue
test: add test case for wildcard routing
docs: update configuration examples
```

---

## 📚 Documentation

- **[README_GATEWAY.md](README_GATEWAY.md)** - Complete feature documentation, use cases, API reference
- **[QUICKSTART.md](QUICKSTART.md)** - Step-by-step setup and testing guide
- **[TEST_RESULTS.md](TEST_RESULTS.md)** - Detailed test validation results and coverage
- **[TEST_CHEATSHEET.md](TEST_CHEATSHEET.md)** - Quick testing reference and debugging tips

---

## 🐛 Known Issues & Limitations

1. **Streaming Test:** Streaming passthrough works in production but requires complex async mocking in tests (currently skipped)
2. **Deprecation Warnings:** FastAPI `on_event` decorator is deprecated (does not affect functionality)

---

## 🎯 Use Cases

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
Route all requests to local Ollama:
```yaml
- match_model: "*"
  target_provider: "ollama"
  target_model: "llama3"
```

---

## 📞 Support

For issues, questions, or contributions related to AgentOS, please:
1. Check existing documentation
2. Search closed issues on GitHub
3. Open a new issue with detailed description

---

*Last updated: 2026-06-12*
