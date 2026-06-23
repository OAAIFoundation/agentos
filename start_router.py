"""
Start Router Server

Configurable port (default: 8001)
Modify DEFAULT_PORT below to change the default port
"""

import os
import sys
import io
import uvicorn
from config_loader import load_config

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ===== Configuration =====
DEFAULT_PORT = 8001
# =========================

if __name__ == "__main__":
    # Load config
    config = load_config("config/config.yaml")

    # Get port from config or use default
    host = config.server.get("host", "0.0.0.0")
    port = config.server.get("port", DEFAULT_PORT)
    workers = config.server.get("workers", 1)

    print("=" * 60)
    print("🚀 Router Server Starting")
    print("=" * 60)
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Workers: {workers}")
    print()
    print(f"Dashboard: http://localhost:{port}/dashboard")
    print(f"API: http://localhost:{port}/v1/chat/completions")
    print(f"Health: http://localhost:{port}/health")
    print("=" * 60)
    print()

    uvicorn.run(
        "router_server:app",
        host=host,
        port=port,
        workers=workers,
        log_level="info",
        access_log=True,
    )
