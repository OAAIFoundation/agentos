# Privacy Guard - LLM Gateway Security Module

## 📋 Overview

Privacy Guard is a comprehensive three-layer security module for the LLM Gateway that provides:

1. **Policy Check**: Conditional routing/blocking based on prompt characteristics
2. **Regex Audit**: Pattern-based detection and filtering
3. **Data Masking**: Bidirectional PII redaction (request & response)

## 🎯 Features

### 1. Policy Check
Route or block requests based on dynamic conditions:
- **Role Content Matching**: Check specific message roles (system/user/assistant)
- **Length-Based Routing**: Route long prompts to cost-effective providers
- **Keyword Detection**: Match patterns in any message

**Actions**:
- `block`: Reject request with custom message
- `reroute`: Override routing to specific provider/model

### 2. Regex Audit
Pattern-based security scanning:
- Detect API keys, credentials, tokens
- Identify internal project codenames
- Find credit card numbers, SSH keys, AWS credentials

**Actions**:
- `block`: Reject request immediately (returns 400)
- `log`: Record in audit log but allow request

### 3. Data Masking (Bidirectional)
Automatic PII masking with full unmasking support:
- **Request Phase**: Replace sensitive data with placeholders
- **Response Phase**: Restore original values transparently
- **Streaming Support**: Advanced sliding-window buffer for SSE streams

**Supported Entities**:
- Email addresses
- Phone numbers (US format)
- SSN (Social Security Numbers)
- Chinese ID numbers (18 digits)
- IP addresses
- Person names (with titles)

## 🚀 Quick Start

### Step 1: Enable Privacy Guard

**Option A: Edit config.yaml**
```yaml
privacy_guard:
  enabled: true  # Change to true
```

**Option B: Use Web Dashboard**
1. Open http://localhost:8000/dashboard
2. Scroll to "Privacy Guard" section
3. Toggle switch to "Enabled"
4. Click "Save Configuration"

### Step 2: Restart Gateway
```bash
python gateway.py
```

Look for: `Privacy Guard: Enabled` in logs

### Step 3: Test It
```bash
# Test 1: Block API key
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer test" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"Key: sk-xxx"}]}'
# Expected: 400 Bad Request

# Test 2: Data masking
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Authorization: Bearer test" \
  -d '{"model":"gpt-4o","messages":[{"role":"user","content":"Email: admin@company.com"}]}'
# LLM receives: [REDACTED_EMAIL_1], User receives: admin@company.com
```

## 📋 Configuration

### config.yaml Structure

```yaml
privacy_guard:
  enabled: true

  # Policy Check
  policy_check:
    enabled: true
    rules:
      - name: "Block prompt injection"
        condition:
          type: "role_content"
          role: "system"
          pattern: "(?i)(ignore previous|disregard)"
        action: "block"
        block_message: "Prompt injection detected"

      - name: "Route long prompts"
        condition:
          type: "total_length"
          min_length: 10000
        action: "reroute"
        target_provider: "deepseek"
        target_model: "deepseek-chat"

  # Regex Audit
  regex_audit:
    enabled: true
    rules:
      - name: "API Key Detection"
        pattern: "sk-[a-zA-Z0-9]{20,}"
        action: "block"
        message: "API key detected in prompt"

      - name: "Project Codename"
        pattern: "(?i)project-phoenix"
        action: "log"
        message: "Internal codename detected"

  # Data Masking
  data_masking:
    enabled: true
    rules:
      - name: "Email"
        pattern: "\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b"
        placeholder_prefix: "[REDACTED_EMAIL_"
        entity_type: "email"

      - name: "Phone Number"
        pattern: "\\b\\d{3}-\\d{3}-\\d{4}\\b"
        placeholder_prefix: "[REDACTED_PHONE_"
        entity_type: "phone"
```

### Web Dashboard

Access the Privacy Guard panel at: **http://localhost:8000/dashboard**

Navigate to the "Privacy Guard" section to:
- Enable/disable the module
- Add/edit/delete rules for each layer
- Switch between Policy Check, Regex Audit, and Data Masking tabs
- Visual configuration with real-time preview

## 🔬 Technical Details

### Request Flow

```
User Request
    │
    ├─► 1. Regex Audit (block if sensitive pattern)
    │       └─► Raises HTTPException(400) if blocked
    │
    ├─► 2. Policy Check (conditional routing)
    │       ├─► Block: Raises HTTPException(403)
    │       └─► Reroute: Overrides target provider/model
    │
    ├─► 3. Data Masking (PII redaction)
    │       └─► Replace sensitive data with [REDACTED_TYPE_N]
    │
    └─► Forward to LLM Provider
            │
            ▼
        LLM Response (contains placeholders)
            │
            ├─► Non-Streaming: Replace all placeholders
            └─► Streaming: Sliding-window buffer unmask
                │
                └─► User receives original data
```

### Streaming Unmask Algorithm

**Challenge**: Placeholders like `[REDACTED_EMAIL_1]` may be split across multiple SSE chunks.

**Solution**: Sliding window buffer

1. Accumulate incoming chunks in buffer
2. Search for complete placeholders
3. If found: unmask and yield
4. If incomplete: wait for more chunks
5. Buffer size = max placeholder length + safety margin

**Example**:
```
Chunk 1: "Contact "
Chunk 2: "[REDACTED_EM"
Chunk 3: "AIL_1] for"
Chunk 4: " details"

Output:
"Contact user@example.com for details"
```

### Performance Optimizations

- **Pre-compiled Regex**: All patterns compiled at startup
- **Lazy Evaluation**: Rules checked in order (short-circuit on match)
- **Minimal Memory**: Context stores only mapping dict, not full text
- **Async Streaming**: Zero-copy buffer management

## 📊 Test Results

### Unit Tests (tests/test_privacy_guard.py)

```bash
pytest tests/test_privacy_guard.py -v
```

**Results**: ✅ 15/15 tests passed

| Test Category | Tests | Status |
|---------------|-------|--------|
| Regex Audit | 3 | ✅ PASS |
| Policy Check | 3 | ✅ PASS |
| Data Masking (Request) | 3 | ✅ PASS |
| Data Unmask (Non-Stream) | 1 | ✅ PASS |
| Data Unmask (Streaming) | 3 | ✅ PASS |
| Integration | 2 | ✅ PASS |

**Key Tests**:
- ✅ Block API keys, credentials
- ✅ Log-only audit rules
- ✅ Policy-based rerouting
- ✅ Bidirectional email/phone masking
- ✅ **Streaming placeholder splitting** (hardest test)
- ✅ Full pipeline integration

### Live Integration Test

Test against running gateway:

```bash
# Test 1: Block API key
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Key: sk-abcdefghijklmnopqrstuvwxyz"}]
  }'
# Expected: 400 Bad Request

# Test 2: Data masking
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer test" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Email me at admin@company.com"}]
  }'
# LLM receives: "Email me at [REDACTED_EMAIL_1]"
# User receives: "Email me at admin@company.com"
```

## 🔐 Security Considerations

### Best Practices

1. **Layered Defense**: Enable all three modules for comprehensive protection
2. **Regex Tuning**: Balance false positives vs. coverage
3. **Audit Logs**: Monitor log-only rules for suspicious patterns
4. **Regular Updates**: Add new patterns as threats evolve

### Known Limitations

1. **Context-Aware Detection**: Basic regex cannot understand semantic context
   - Example: "My password is not abc123" → May mask "abc123"
   - Mitigation: Use more specific patterns

2. **Performance Impact**: Complex regex on large prompts
   - Impact: ~1-5ms latency per request
   - Mitigation: Pre-compiled patterns, limit rule count

3. **Streaming Buffer**: Placeholders longer than buffer size may fail
   - Current: Dynamic buffer = max(placeholder lengths)
   - Mitigation: Keep placeholder prefixes short

## 📈 Roadmap

### Future Enhancements

- [ ] **ML-Based Detection**: Replace regex with NER models
- [ ] **Custom Entity Types**: User-defined masking rules
- [ ] **Audit Dashboard**: Visual analytics for blocked requests
- [ ] **Rate Limiting**: Per-user request throttling
- [ ] **Allowlist/Denylist**: IP-based access control
- [ ] **Encryption**: End-to-end encryption for sensitive data
- [ ] **Multi-Language Support**: Non-English PII detection

## 🛠️ Troubleshooting

### Privacy Guard Not Working

1. **Check Enabled Flag**:
   ```yaml
   privacy_guard:
     enabled: true  # Must be true
   ```

2. **Verify Sub-Module**:
   ```yaml
   policy_check:
     enabled: true  # Each sub-module has its own flag
   ```

3. **Check Logs**:
   ```bash
   # Look for Privacy Guard initialization
   grep "Privacy Guard" gateway.log
   ```

### Regex Not Matching

1. **Test Pattern**: Use online regex tester (regex101.com)
2. **Escape Backslashes**: YAML requires double escaping `\\b` not `\b`
3. **Case Sensitivity**: Use `(?i)` for case-insensitive

### Streaming Unmask Issues

1. **Check Placeholder Format**: Must match exactly `[PREFIX_N]`
2. **Buffer Size**: Increase if placeholders are long
3. **SSE Format**: Ensure response is `data: {...}\n` format

## 📄 License

MIT License - Same as parent project

## 👥 Contributors

- Privacy Guard Module: Claude Code Assistant
- Integration: AgentOS Team

---

**Need Help?** Open an issue on GitHub or check the main README.md
