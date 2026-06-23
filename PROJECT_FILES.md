# AgentOS Router - Project Files

Complete file structure after cleanup (2026-06-23)

## 🎯 Core Architecture Files

### Router Server
- `router_server.py` - FastAPI server, routing logic, dashboard API
- `llm_client.py` - **Unified** LLM client supporting 15+ providers (merged from llm_client_enhanced.py)
- `config_loader.py` - YAML configuration loader with provider support
- `route_matcher.py` - Route matching logic (wildcards, keywords, priority)

### Transparent Proxy (Envoy-style)
- `proxy_addon.py` - **mitmproxy addon** implementing routing (like semantic-router ExtProc)
- `start_proxy.py` - Start mitmproxy with addon
- `dns_resolver.py` - DNS bypass to avoid routing loops

### Startup Scripts
- `start_all.bat` - **One-click startup** (Router + Proxy, opens Dashboard)
- `kill_proxy.bat` - Kill processes on ports 8001 and 8801
- `start_router.py` - Start router on port 8001
- `start_proxy.py` - Start proxy on port 8801

---

## 📚 Documentation

### Main Documentation (All integrated into README.md)
- `README.md` - **Complete unified documentation** including:
  - ✅ 15+ provider support matrix
  - ✅ Transparent proxy architecture (Envoy-style, inspired by semantic-router)
  - ✅ Implementation details (mitmproxy + RouterProxyAddon)
  - ✅ SSL certificate installation guide (integrated from INSTALL_MITM_CERT.md)
  - ✅ Phase implementation notes (integrated from PHASE*.md)
  - ✅ Quick start, manual setup, troubleshooting
  - ✅ Usage examples for all modes

### Supplementary Documentation
- `PRIVACY_GUARD.md` - Privacy Guard documentation
- `PROJECT_FILES.md` - This file (project structure overview)

**Note**: All Phase documentation (PHASE1_COMPLETE.md, PHASE1_SUCCESS.md, PHASE2_STATUS.md, INSTALL_MITM_CERT.md) has been integrated into README.md for a unified documentation experience.

---

## ⚙️ Configuration

### Config Files
- `config/config.yaml` - **Main configuration** (15+ providers, routing rules)
- `config/config.multi-provider.yaml` - Complete multi-provider example

### Environment Files
- `config/.env.example` - Environment variable template
- `.env` (user-created) - Actual API keys

---

## 🌐 Web Dashboard

### Dashboard UI
- `web/index.html` - **Vue 3 + Tailwind dashboard** (dynamic provider display)

Dashboard features:
- View all providers from config
- View routing rules
- Edit and save configuration
- View request logs
- Real-time monitoring

---

## 🧪 Tests

### Integration Tests
- `test_all_providers.py` - **Complete provider integration test** (all 15+ providers)

### Test Suite (tests/ directory)
- `tests/README.md` - Complete test documentation
- `tests/run_all_tests.py` - Main test runner
- `tests/test_*.py` - Individual provider tests (framework ready)
- `tests/test_gateway.py` - Legacy gateway tests
- `tests/test_transparent_proxy.py` - Transparent proxy tests
- `tests/test_edit_save.py` - Dashboard UI tests
- `tests/test_privacy_guard.py` - Privacy Guard tests

---

## 🗂️ Other Files

### Legacy Gateway (kept for compatibility)
- `gateway.py` - Original gateway implementation
- `proxy_server.py` - Original proxy server
- `demo_transparent_proxy.py` - Demo script

### Privacy & Security
- `privacy_guard.py` - Privacy Guard module
- `data_masking.py` - PII masking module
- `audit_logger.py` - Audit logging
- `session_manager.py` - Session management

---

## 📦 Dependencies

### Requirements
- `requirements.txt` - Python dependencies
- `requirements_router.txt` - Router-specific dependencies (if exists)

Main dependencies:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `httpx` - HTTP client
- `pyyaml` - YAML parser
- `mitmproxy` - Transparent proxy

---

## 🗑️ Deleted Files (Cleanup Sessions)

### Session 1: Failed Attempts Cleanup (2026-06-23 Morning)

**Temporary Documentation (~30 files)**:
- Architecture comparisons, setup guides, status updates
- Troubleshooting guides (now in README.md)
- Duplicate quick start guides

**Failed Approach: hosts File Modification**:
- `add_all_claude_hosts.bat`, `restore_hosts.bat`, `modify_hosts.py`, etc.

**Failed Approach: Alternative Proxy Implementations**:
- `envoy_style_proxy.py`, `proxy_router.py`, `simple_mitm_addon.py`, etc.

**Old Test Files**:
- `test_proxy_chain.py`, `test_mitm_upstream.py`, `test_router.py`, etc.

**Old Startup Scripts**:
- `start_envoy_proxy.bat`, `start_transparent_mode.bat`, `restart_router.bat`, etc.

### Session 2: Documentation Consolidation (2026-06-23 Afternoon)

**Phase Documentation (integrated into README.md)**:
- `PHASE1_COMPLETE.md` - Basic proxy architecture notes
- `PHASE1_SUCCESS.md` - Phase 1 success confirmation
- `PHASE2_STATUS.md` - Router integration status
- `INSTALL_MITM_CERT.md` - Certificate installation guide

**Why removed**: All content integrated into README.md Architecture and Troubleshooting sections for unified documentation.

**Total cleanup**: **~71 files deleted** across both sessions

---

## 🎯 Final Architecture

```
Claude Code Extension
    ↓ HTTP_PROXY=localhost:8801
mitmproxy (:8801)
    ↓ proxy_addon.py (like semantic-router ExtProc)
Router Server (:8001)
    ↓ llm_client.py
LLM Providers (15+)
    - OpenAI
    - Anthropic
    - AWS Bedrock
    - Azure OpenAI
    - Google Gemini
    - Vertex AI
    - DeepSeek
    - Qwen
    - Baichuan
    - Zhipu
    - Moonshot
    - MiniMax
    - vLLM
    - Ollama
    - LM Studio
```

---

## 📊 File Count Summary

| Category | Count |
|----------|-------|
| Core Code | 8 files |
| Documentation | 2 files |
| Configuration | 2 files |
| Web Dashboard | 1 file |
| Tests | 1 main + test suite |
| Startup Scripts | 4 files |
| Legacy/Compatibility | 5 files |

**Total**: ~23 essential files (down from 100+ after cleanup)

---

## ✅ Success Criteria

All files in this list are:
- ✅ Part of the final working solution
- ✅ Currently in use or needed for operation
- ✅ Documented and tested
- ✅ No redundant or duplicate functionality

The cleanup removed **40+ temporary files** from failed attempts while preserving:
- ✅ All working code
- ✅ Implementation process documentation (Phase files)
- ✅ Complete test suite
- ✅ All essential documentation

---

*Last updated: 2026-06-23*
*After cleanup of failed attempts*
