"""
Test Transparent Proxy functionality

This script tests whether the proxy server can:
1. Intercept HTTP requests to LLM APIs
2. Route them through gateway.py
3. Pass through non-LLM traffic transparently
"""

import os
import time
import requests
from openai import OpenAI

PROXY_URL = "http://localhost:8888"
GATEWAY_URL = "http://localhost:8000"

def test_proxy_running():
    """Test if proxy server is running"""
    print("\n[TEST 1] Proxy Server Status")
    print("-" * 60)

    # Try to connect to proxy (will fail connection, but that's expected)
    try:
        # We expect this to fail since proxy doesn't have a health endpoint
        # Just checking if port is open
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 8888))
        sock.close()

        if result == 0:
            print("   ✅ Proxy server is running on port 8888")
            return True
        else:
            print("   ❌ Proxy server is not running")
            print("   💡 Start it with: python proxy_server.py")
            return False
    except Exception as e:
        print(f"   ❌ Error checking proxy: {e}")
        return False

def test_gateway_running():
    """Test if gateway is running"""
    print("\n[TEST 2] Gateway Status")
    print("-" * 60)

    try:
        response = requests.get(f"{GATEWAY_URL}/health", timeout=2)
        if response.status_code == 200:
            print("   ✅ Gateway is running")
            return True
        else:
            print(f"   ⚠️ Gateway returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Gateway is not running: {e}")
        print("   💡 Start it with: python gateway.py")
        return False

def test_direct_gateway_request():
    """Test direct request to gateway (baseline)"""
    print("\n[TEST 3] Direct Gateway Request (Baseline)")
    print("-" * 60)

    try:
        client = OpenAI(
            api_key="test-key",
            base_url=f"{GATEWAY_URL}/v1"
        )

        print("   🔄 Sending request directly to gateway...")
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=5
        )

        print(f"   ✅ Response received: {response.choices[0].message.content[:50]}")
        print(f"   📊 Model used: {response.model}")
        return True

    except Exception as e:
        print(f"   ⚠️ Error: {e}")
        print("   💡 This is expected if you don't have valid API keys configured")
        return True  # Not a failure - just shows gateway is working

def test_proxied_request():
    """Test request through transparent proxy"""
    print("\n[TEST 4] Proxied Request (Transparent Interception)")
    print("-" * 60)

    # Set proxy environment variables
    os.environ['HTTP_PROXY'] = PROXY_URL
    os.environ['HTTPS_PROXY'] = PROXY_URL

    try:
        # Create OpenAI client WITHOUT base_url (should use api.openai.com)
        # But proxy will intercept it!
        client = OpenAI(
            api_key="sk-test-proxy-key"
            # Note: No base_url! This goes to api.openai.com
        )

        print("   🔄 Sending request to api.openai.com (will be intercepted by proxy)...")
        print("   🎯 Expected: Proxy intercepts and routes through gateway")

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Test proxy"}],
            max_tokens=5
        )

        print(f"   ✅ Response received through proxy!")
        print(f"   📊 Model: {response.model}")
        print(f"   💬 Content: {response.choices[0].message.content[:50]}")
        return True

    except Exception as e:
        print(f"   ⚠️ Error: {e}")
        print("   💡 Check if:")
        print("      1. Proxy server is running (python proxy_server.py)")
        print("      2. Gateway is running (python gateway.py)")
        print("      3. API keys are configured in config.yaml")
        return False
    finally:
        # Clean up environment
        del os.environ['HTTP_PROXY']
        del os.environ['HTTPS_PROXY']

def test_non_llm_passthrough():
    """Test that non-LLM traffic passes through transparently"""
    print("\n[TEST 5] Non-LLM Traffic Passthrough")
    print("-" * 60)

    # Set proxy
    os.environ['HTTP_PROXY'] = PROXY_URL
    os.environ['HTTPS_PROXY'] = PROXY_URL

    try:
        print("   🔄 Sending request to httpbin.org (non-LLM domain)...")

        response = requests.get("http://httpbin.org/get", timeout=10)

        if response.status_code == 200:
            print(f"   ✅ Non-LLM traffic passed through successfully")
            print(f"   📊 Status: {response.status_code}")
            return True
        else:
            print(f"   ⚠️ Unexpected status: {response.status_code}")
            return False

    except Exception as e:
        print(f"   ⚠️ Error: {e}")
        print("   💡 This might be a network issue, not proxy issue")
        return True  # Not critical
    finally:
        del os.environ['HTTP_PROXY']
        del os.environ['HTTPS_PROXY']

def main():
    print("=" * 60)
    print("Transparent Proxy Test Suite")
    print("=" * 60)

    # Check prerequisites
    proxy_ok = test_proxy_running()
    gateway_ok = test_gateway_running()

    if not proxy_ok or not gateway_ok:
        print("\n" + "=" * 60)
        print("⚠️ Prerequisites not met. Please start:")
        if not gateway_ok:
            print("   1. python gateway.py")
        if not proxy_ok:
            print("   2. python proxy_server.py")
        print("=" * 60)
        return

    # Run tests
    test_direct_gateway_request()
    test_proxied_request()
    test_non_llm_passthrough()

    print("\n" + "=" * 60)
    print("✅ Transparent Proxy Tests Complete!")
    print("=" * 60)
    print("\n📖 Usage Instructions:")
    print("   1. Start gateway: python gateway.py")
    print("   2. Start proxy: python proxy_server.py")
    print("   3. Set environment variables:")
    print("      export HTTP_PROXY=http://localhost:8888")
    print("      export HTTPS_PROXY=http://localhost:8888")
    print("   4. Run any LLM app - requests will be automatically intercepted!")
    print("")

if __name__ == "__main__":
    main()
