"""
Transparent HTTP/HTTPS Proxy Server
Automatically intercepts LLM API requests and routes them through gateway.py

This proxy runs as a system-level HTTP(S) proxy server that:
1. Intercepts all HTTP/HTTPS traffic on port 8888
2. Detects LLM API requests (OpenAI, Anthropic, DeepSeek, etc.)
3. Routes detected LLM requests through gateway.py routing rules
4. Passes through non-LLM traffic transparently

Usage:
    # Start the proxy server
    python proxy_server.py

    # Configure system proxy (Windows)
    set HTTP_PROXY=http://localhost:8888
    set HTTPS_PROXY=http://localhost:8888

    # Configure system proxy (Linux/Mac)
    export HTTP_PROXY=http://localhost:8888
    export HTTPS_PROXY=http://localhost:8888

Now all LLM requests will be automatically intercepted without any app configuration!
"""

import asyncio
import socket
import ssl
import os
import logging
from typing import Optional, Tuple
from pathlib import Path
from urllib.parse import urlparse

import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

# ======================== Configuration ========================

PROXY_HOST = "127.0.0.1"
PROXY_PORT = 8888
GATEWAY_URL = "http://localhost:8000"  # Gateway routing service

# Upstream proxy configuration (for corporate/enterprise proxy)
# Set these if your machine uses a proxy to access internet
UPSTREAM_PROXY = os.environ.get('UPSTREAM_PROXY', None)  # e.g., "http://proxy.company.com:8080"
# Or set directly here:
# UPSTREAM_PROXY = "http://proxy.company.com:8080"

# LLM API domains to intercept
LLM_DOMAINS = {
    "api.openai.com",
    "api.anthropic.com",
    "api.deepseek.com",
    "dashscope.aliyuncs.com",  # Qwen
    "open.bigmodel.cn",         # Zhipu GLM
    "api.moonshot.cn",          # Moonshot
    "aip.baidubce.com",         # Baidu ERNIE
    "api.minimax.chat",         # MiniMax
    "api.groq.com",             # Groq
    "api.together.xyz",         # Together AI
    "api.replicate.com",        # Replicate
    "api.cohere.ai",            # Cohere
    "api.mistral.ai",           # Mistral
    "api.perplexity.ai",        # Perplexity
}

# LLM API path patterns
LLM_PATH_PATTERNS = [
    "/v1/chat/completions",
    "/v1/completions",
    "/v1/messages",  # Anthropic
    "/chat/completions",
]

# ======================== HTTP Proxy Handler ========================

class ProxyHandler:
    """HTTP/HTTPS Proxy Connection Handler"""

    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.reader = reader
        self.writer = writer
        self.client_address = writer.get_extra_info('peername')

    async def handle(self):
        """Handle incoming proxy connection"""
        try:
            # Read first line to determine request type
            first_line = await self.reader.readline()
            if not first_line:
                return

            first_line = first_line.decode('utf-8', errors='ignore').strip()
            logger.info(f"[{self.client_address}] {first_line}")

            # Parse method and target
            parts = first_line.split()
            if len(parts) < 2:
                await self._send_error(400, "Bad Request")
                return

            method = parts[0]
            target = parts[1]

            if method == "CONNECT":
                # HTTPS tunnel request
                await self._handle_connect(target)
            else:
                # HTTP request
                await self._handle_http(method, target, first_line)

        except Exception as e:
            logger.error(f"[{self.client_address}] Error: {e}")
        finally:
            try:
                self.writer.close()
                await self.writer.wait_closed()
            except:
                pass

    async def _handle_connect(self, target: str):
        """Handle HTTPS CONNECT tunnel"""
        try:
            # Parse host:port
            if ':' in target:
                host, port = target.split(':', 1)
                port = int(port)
            else:
                host = target
                port = 443

            # Check if this is an LLM API domain
            is_llm_domain = host in LLM_DOMAINS

            if is_llm_domain:
                logger.info(f"[{self.client_address}] 🎯 LLM domain detected: {host}")

            # Establish tunnel to target server
            try:
                target_reader, target_writer = await asyncio.open_connection(host, port)
            except Exception as e:
                logger.error(f"[{self.client_address}] Failed to connect to {host}:{port}: {e}")
                await self._send_error(502, "Bad Gateway")
                return

            # Send 200 Connection Established
            self.writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            await self.writer.drain()

            # Start bidirectional relay
            if is_llm_domain:
                # For LLM domains, intercept and parse traffic
                await self._relay_llm_tunnel(target_reader, target_writer, host)
            else:
                # For non-LLM domains, transparent relay
                await self._relay_tunnel(target_reader, target_writer)

        except Exception as e:
            logger.error(f"[{self.client_address}] CONNECT error: {e}")

    async def _handle_http(self, method: str, url: str, first_line: str):
        """Handle plain HTTP request"""
        try:
            # Parse URL
            parsed = urlparse(url)
            host = parsed.netloc or parsed.path.split('/')[0]
            path = parsed.path if parsed.netloc else '/' + '/'.join(parsed.path.split('/')[1:])

            # Read headers
            headers = {}
            while True:
                line = await self.reader.readline()
                if not line or line == b'\r\n':
                    break
                line = line.decode('utf-8', errors='ignore').strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip().lower()] = value.strip()

            # Read body if present
            body = b''
            if 'content-length' in headers:
                content_length = int(headers['content-length'])
                body = await self.reader.readexactly(content_length)

            # Check if this is an LLM API request
            is_llm_request = self._is_llm_request(host, path)

            if is_llm_request:
                logger.info(f"[{self.client_address}] 🎯 LLM API request: {method} {host}{path}")
                # Route through gateway
                await self._route_through_gateway(method, host, path, headers, body)
            else:
                # Forward to original destination
                await self._forward_http(method, host, path, headers, body)

        except Exception as e:
            logger.error(f"[{self.client_address}] HTTP error: {e}")

    def _is_llm_request(self, host: str, path: str) -> bool:
        """Check if request is to an LLM API"""
        # Check domain
        if host in LLM_DOMAINS:
            return True

        # Check path patterns
        for pattern in LLM_PATH_PATTERNS:
            if pattern in path:
                return True

        return False

    async def _route_through_gateway(self, method: str, host: str, path: str, headers: dict, body: bytes):
        """Route LLM request through gateway.py"""
        try:
            # Construct gateway URL
            gateway_url = f"{GATEWAY_URL}{path}"

            # Forward request to gateway
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=method,
                    url=gateway_url,
                    headers={k: v for k, v in headers.items() if k not in ['host', 'connection']},
                    content=body,
                    timeout=300.0
                )

            # Send response back to client
            self.writer.write(f"HTTP/1.1 {response.status_code} {response.reason_phrase}\r\n".encode())
            for key, value in response.headers.items():
                if key.lower() not in ['connection', 'transfer-encoding']:
                    self.writer.write(f"{key}: {value}\r\n".encode())
            self.writer.write(b"\r\n")
            self.writer.write(response.content)
            await self.writer.drain()

            logger.info(f"[{self.client_address}] ✅ Routed through gateway: {response.status_code}")

        except Exception as e:
            logger.error(f"[{self.client_address}] Gateway routing error: {e}")
            await self._send_error(502, "Bad Gateway")

    async def _forward_http(self, method: str, host: str, path: str, headers: dict, body: bytes):
        """Forward HTTP request to original destination"""
        try:
            # Construct URL
            url = f"http://{host}{path}"

            # Configure proxy if upstream proxy is set
            proxy = UPSTREAM_PROXY if UPSTREAM_PROXY else None

            # Forward request
            async with httpx.AsyncClient(proxies=proxy) as client:
                response = await client.request(
                    method=method,
                    url=url,
                    headers={k: v for k, v in headers.items() if k not in ['host', 'connection']},
                    content=body,
                    timeout=60.0
                )

            # Send response
            self.writer.write(f"HTTP/1.1 {response.status_code} {response.reason_phrase}\r\n".encode())
            for key, value in response.headers.items():
                if key.lower() not in ['connection', 'transfer-encoding']:
                    self.writer.write(f"{key}: {value}\r\n".encode())
            self.writer.write(b"\r\n")
            self.writer.write(response.content)
            await self.writer.drain()

        except Exception as e:
            logger.error(f"[{self.client_address}] Forward error: {e}")
            await self._send_error(502, "Bad Gateway")

    async def _relay_tunnel(self, target_reader: asyncio.StreamReader, target_writer: asyncio.StreamWriter):
        """Transparent bidirectional relay for HTTPS tunnel"""
        async def relay(reader, writer):
            try:
                while True:
                    data = await reader.read(8192)
                    if not data:
                        break
                    writer.write(data)
                    await writer.drain()
            except:
                pass

        # Start both directions
        await asyncio.gather(
            relay(self.reader, target_writer),
            relay(target_reader, self.writer),
            return_exceptions=True
        )

        # Close connections
        try:
            target_writer.close()
            await target_writer.wait_closed()
        except:
            pass

    async def _relay_llm_tunnel(self, target_reader: asyncio.StreamReader, target_writer: asyncio.StreamWriter, host: str):
        """
        Intercept and parse HTTPS traffic for LLM domains
        Note: This requires MITM capabilities with SSL certificate
        For now, we'll use transparent relay and rely on apps using HTTP_PROXY
        """
        # TODO: Implement MITM with SSL certificate for full HTTPS interception
        # For now, fall back to transparent relay
        logger.warning(f"[{self.client_address}] ⚠️ HTTPS interception not yet implemented for {host}")
        logger.warning(f"[{self.client_address}] 💡 Use HTTP_PROXY in your app for automatic routing")
        await self._relay_tunnel(target_reader, target_writer)

    async def _send_error(self, code: int, message: str):
        """Send HTTP error response"""
        response = f"HTTP/1.1 {code} {message}\r\n"
        response += "Content-Type: text/plain\r\n"
        response += f"Content-Length: {len(message)}\r\n"
        response += "\r\n"
        response += message

        try:
            self.writer.write(response.encode())
            await self.writer.drain()
        except:
            pass

# ======================== Proxy Server ========================

async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handle incoming client connection"""
    handler = ProxyHandler(reader, writer)
    await handler.handle()

async def start_proxy_server():
    """Start transparent proxy server"""
    server = await asyncio.start_server(
        handle_client,
        PROXY_HOST,
        PROXY_PORT
    )

    addr = server.sockets[0].getsockname()
    logger.info(f"")
    logger.info(f"🚀 Transparent Proxy Server started on {addr[0]}:{addr[1]}")
    logger.info(f"")
    logger.info(f"📋 Configuration Instructions:")
    logger.info(f"")
    logger.info(f"   Windows (CMD):")
    logger.info(f"      set HTTP_PROXY=http://localhost:{PROXY_PORT}")
    logger.info(f"      set HTTPS_PROXY=http://localhost:{PROXY_PORT}")
    logger.info(f"")
    logger.info(f"   Windows (PowerShell):")
    logger.info(f"      $env:HTTP_PROXY=\"http://localhost:{PROXY_PORT}\"")
    logger.info(f"      $env:HTTPS_PROXY=\"http://localhost:{PROXY_PORT}\"")
    logger.info(f"")
    logger.info(f"   Linux/Mac:")
    logger.info(f"      export HTTP_PROXY=http://localhost:{PROXY_PORT}")
    logger.info(f"      export HTTPS_PROXY=http://localhost:{PROXY_PORT}")
    logger.info(f"")
    logger.info(f"🎯 LLM domains being intercepted: {len(LLM_DOMAINS)}")
    logger.info(f"   {', '.join(list(LLM_DOMAINS)[:5])}...")
    logger.info(f"")
    logger.info(f"🔗 Gateway routing service: {GATEWAY_URL}")
    logger.info(f"")
    if UPSTREAM_PROXY:
        logger.info(f"🌐 Upstream proxy: {UPSTREAM_PROXY}")
        logger.info(f"   (Non-LLM traffic will go through upstream proxy)")
        logger.info(f"")
    logger.info(f"✅ Ready to intercept LLM API requests!")
    logger.info(f"")

    async with server:
        await server.serve_forever()

# ======================== Main Entry ========================

def main():
    """Main entry point"""
    try:
        # Check if gateway is running
        logger.info(f"Checking if gateway is running on {GATEWAY_URL}...")
        try:
            import requests
            response = requests.get(f"{GATEWAY_URL}/health", timeout=2)
            if response.status_code == 200:
                logger.info(f"✅ Gateway is running")
            else:
                logger.warning(f"⚠️ Gateway returned status {response.status_code}")
        except Exception as e:
            logger.error(f"❌ Gateway is not running!")
            logger.error(f"   Please start gateway first: python gateway.py")
            logger.error(f"   Error: {e}")
            return

        # Start proxy server
        asyncio.run(start_proxy_server())

    except KeyboardInterrupt:
        logger.info("Proxy server stopped by user")
    except Exception as e:
        logger.error(f"Failed to start proxy server: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
