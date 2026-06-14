"""
Demo script for Transparent Proxy Mode

This script demonstrates how transparent proxy works:
1. No base_url configuration in client
2. Requests go to api.openai.com (or any provider)
3. Proxy intercepts and routes through gateway
4. Gateway applies routing rules automatically

Run this AFTER starting both gateway and proxy:
    python gateway.py
    python proxy_server.py
"""

import os
import time
from openai import OpenAI

def print_separator():
    print("=" * 70)

def demo_without_proxy():
    """Demo 1: Normal request without proxy (will fail without real API key)"""
    print_separator()
    print("DEMO 1: Request WITHOUT Transparent Proxy")
    print_separator()
    print()
    print("📝 Configuration:")
    print("   - No HTTP_PROXY set")
    print("   - No base_url override")
    print("   - Request goes directly to api.openai.com")
    print()

    # Clear proxy settings
    os.environ.pop('HTTP_PROXY', None)
    os.environ.pop('HTTPS_PROXY', None)

    try:
        client = OpenAI(api_key="sk-fake-key-for-demo")

        print("🔄 Sending request to api.openai.com...")
        print("   (This will likely fail with authentication error)")
        print()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )

        print(f"✅ Response: {response.choices[0].message.content}")

    except Exception as e:
        print(f"❌ Error (expected): {str(e)[:100]}...")
        print()
        print("💡 This is expected - we're using a fake API key")
        print("   Next, we'll use transparent proxy to route through gateway!")

    print()

def demo_with_proxy():
    """Demo 2: Request with transparent proxy"""
    print_separator()
    print("DEMO 2: Request WITH Transparent Proxy")
    print_separator()
    print()
    print("📝 Configuration:")
    print("   - HTTP_PROXY=http://localhost:8888")
    print("   - HTTPS_PROXY=http://localhost:8888")
    print("   - Request intercepted by proxy automatically")
    print("   - Proxy routes to gateway on localhost:8000")
    print("   - Gateway applies routing rules")
    print()

    # Set proxy
    os.environ['HTTP_PROXY'] = 'http://localhost:8888'
    os.environ['HTTPS_PROXY'] = 'http://localhost:8888'

    try:
        # Create client WITHOUT base_url - goes to api.openai.com
        client = OpenAI(api_key="demo-key")

        print("🔄 Sending request...")
        print("   Client thinks it's going to: api.openai.com")
        print("   Proxy intercepts and forwards to: localhost:8000")
        print("   Gateway applies routing rules")
        print()

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": "Say hello in one word"}
            ],
            max_tokens=10
        )

        print("✅ Response received through transparent proxy!")
        print(f"   Model: {response.model}")
        print(f"   Content: {response.choices[0].message.content}")
        print()
        print("🎉 Success! Request was automatically intercepted and routed!")

    except Exception as e:
        print(f"⚠️ Error: {e}")
        print()
        print("💡 Troubleshooting:")
        print("   1. Is gateway running? (python gateway.py)")
        print("   2. Is proxy running? (python proxy_server.py)")
        print("   3. Are API keys configured in config/config.yaml?")
        print("   4. Check proxy logs for interception messages")

    print()

def demo_comparison():
    """Demo 3: Side-by-side comparison"""
    print_separator()
    print("DEMO 3: Transparent vs Explicit Mode Comparison")
    print_separator()
    print()

    # Transparent mode
    os.environ['HTTP_PROXY'] = 'http://localhost:8888'
    os.environ['HTTPS_PROXY'] = 'http://localhost:8888'

    print("🔵 TRANSPARENT MODE:")
    print("   Code:")
    print("      client = OpenAI(api_key='sk-xxx')")
    print("      # No base_url - goes to api.openai.com")
    print("      # Proxy intercepts automatically!")
    print()

    # Explicit mode
    os.environ.pop('HTTP_PROXY', None)
    os.environ.pop('HTTPS_PROXY', None)

    print("🟢 EXPLICIT MODE:")
    print("   Code:")
    print("      client = OpenAI(")
    print("          api_key='dummy',")
    print("          base_url='http://localhost:8000/v1'  # Must set this!")
    print("      )")
    print()

    print("🎯 COMPARISON:")
    print()
    print("   Transparent Mode:")
    print("      ✅ No app code changes")
    print("      ✅ Works with ANY LLM SDK")
    print("      ✅ Automatic interception")
    print("      ✅ Just set environment variables once")
    print()
    print("   Explicit Mode:")
    print("      ⚠️ Must modify every app")
    print("      ⚠️ Must configure base_url")
    print("      ⚠️ Different for each SDK")
    print("      ✅ No proxy needed")
    print()

def main():
    print()
    print_separator()
    print("        AgentOS Transparent Proxy - Live Demo")
    print_separator()
    print()
    print("This demo shows how transparent proxy intercepts LLM requests")
    print("without any app configuration changes!")
    print()

    # Check prerequisites
    import socket

    # Check gateway
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 8000))
        sock.close()
        if result != 0:
            print("❌ Gateway is not running on port 8000")
            print("   Start it with: python gateway.py")
            print()
            return
        print("✅ Gateway is running on port 8000")
    except Exception as e:
        print(f"❌ Error checking gateway: {e}")
        return

    # Check proxy
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 8888))
        sock.close()
        if result != 0:
            print("❌ Proxy is not running on port 8888")
            print("   Start it with: python proxy_server.py")
            print()
            return
        print("✅ Proxy is running on port 8888")
    except Exception as e:
        print(f"❌ Error checking proxy: {e}")
        return

    print()
    input("Press Enter to start demo...")
    print()

    # Run demos
    demo_without_proxy()
    time.sleep(2)

    demo_with_proxy()
    time.sleep(2)

    demo_comparison()

    print_separator()
    print("Demo complete!")
    print_separator()
    print()
    print("🎓 What you learned:")
    print("   1. Transparent proxy intercepts requests automatically")
    print("   2. No app code changes needed - just set HTTP_PROXY")
    print("   3. Works with any LLM SDK (OpenAI, Anthropic, etc.)")
    print("   4. Gateway routing rules applied transparently")
    print()
    print("🚀 Next steps:")
    print("   1. Open dashboard: http://localhost:8000/dashboard")
    print("   2. Configure routing rules")
    print("   3. Set HTTP_PROXY in your apps")
    print("   4. All LLM requests automatically routed!")
    print()

if __name__ == "__main__":
    main()
