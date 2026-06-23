"""
Start proxy using mitmproxy Python API
直接调用 mitmdump 函数
"""

import sys
import os

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Optional: Configure upstream proxy if needed
# os.environ["HTTPS_PROXY"] = "http://your-proxy.example.com:8080"
# os.environ["HTTP_PROXY"] = "http://your-proxy.example.com:8080"

print("=" * 60)
print("Starting Envoy-Style Proxy (mitmdump)")
print("=" * 60)
print()
print("Architecture (inspired by Semantic Router):")
print()
print("  Client → mitmdump (:8801) → RouterAddon → LLM Provider")
print("           [Envoy]             [ExtProc]")
print()
print("=" * 60)
print()
print("Listen: 0.0.0.0:8801")
print("Mode: Regular HTTP/HTTPS Proxy")
print()
print("Configure clients with:")
print("  $env:HTTPS_PROXY = 'http://localhost:8801'")
print("  $env:HTTP_PROXY = 'http://localhost:8801'")
print()
print("Dashboard: http://localhost:8001/dashboard")
print("  (Start separately: python start_router.py)")
print()
print("=" * 60)
print()

# Start mitmdump
from mitmproxy.tools import main

sys.argv = [
    "mitmdump",
    "-s", "proxy_addon.py",
    "--listen-port", "8801",
    "--ssl-insecure",
    "--set", "termlog_verbosity=info",
]

print("Starting mitmdump...")
print("  (Configure upstream proxy via HTTPS_PROXY env var if needed)")
print()

sys.exit(main.mitmdump())
