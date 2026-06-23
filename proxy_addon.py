"""
Proxy Addon - Router logic for mitmproxy
类似 Semantic Router 的 ExtProc Filter

使用方式:
    mitmdump -s proxy_addon.py --listen-port 8801 --ssl-insecure

架构对比:
    Semantic Router:  Envoy → ExtProc (Go)  → Upstream
    Our Router:       mitmdump → Addon (Python) → Upstream
"""

import sys
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from mitmproxy import http

from config_loader import load_config, RouterConfig
from route_matcher import RouteMatcher
from dns_resolver import resolve_hostname

# Setup logging (no custom basicConfig - let mitmproxy handle it)
logger = logging.getLogger(__name__)

# Log file for sharing with Dashboard
LOG_FILE = Path("proxy_logs.jsonl")

# In-memory logs (backup)
request_logs: List[Dict[str, Any]] = []
MAX_LOGS = 1000


class RouterProxyAddon:
    """
    mitmproxy Addon that implements Router logic

    类似 Semantic Router 的架构:
    - Envoy ExtProc Filter → RouterProxyAddon
    - gRPC ProcessRequest → request() method
    - gRPC ProcessResponse → response() method
    """

    def __init__(self, config: Optional[RouterConfig] = None, matcher: Optional[RouteMatcher] = None):
        """
        Initialize addon

        Args:
            config: Router configuration (auto-loads if None)
            matcher: Route matcher (auto-creates if None)
        """
        # Auto-load when used with mitmdump
        if config is None:
            logger.info("Auto-loading configuration from config/config.yaml")
            config = load_config("config/config.yaml")

        if matcher is None:
            logger.info("Auto-initializing route matcher")
            matcher = RouteMatcher(config)

        self.config = config
        self.matcher = matcher

        logger.info("=" * 60)
        logger.info("RouterProxyAddon Initialized")
        logger.info("=" * 60)
        logger.info(f"Providers: {len(config.providers)}")
        logger.info(f"Routes: {len(config.routes)}")
        logger.info("=" * 60)

    def request(self, flow: http.HTTPFlow) -> None:
        """
        拦截并转发给 Router 进行路由处理

        新架构: Proxy → Router → LLM Provider
        """
        request = flow.request

        # 只处理 LLM API 请求
        if not self._is_llm_request(request):
            return

        logger.info(f"[PROXY] Intercepted: {request.method} {request.pretty_url}")

        try:
            # ========================================
            # 转发给 Router 处理（新架构）
            # ========================================

            # 保存原始信息用于日志
            original_host = request.host
            original_url = request.pretty_url

            # 修改请求目标为 Router
            request.scheme = "http"
            request.host = "localhost"
            request.port = 8001

            # 保留原始 path
            # 例如: /v1/messages 或 /model/.../invoke-with-response-stream
            # Router 会处理不同的 API 格式

            # 移除原来的 Host header，设置为 Router
            request.headers["Host"] = "localhost:8001"

            # 添加追踪 header，告诉 Router 原始请求来自哪里
            request.headers["X-Original-Host"] = original_host
            request.headers["X-Proxy-Forwarded"] = "true"

            logger.info(f"[PROXY] Forwarding to Router: {original_host} → localhost:8001")

            # 简单记录日志（详细日志由 Router 处理）
            try:
                if request.content:
                    body = json.loads(request.content.decode('utf-8'))
                    model = body.get("model", "unknown")
                    self._log_simple(original_url, model)
            except:
                pass

        except json.JSONDecodeError:
            logger.warning("[PROXY] Failed to parse request body as JSON")
        except Exception as e:
            logger.error(f"[PROXY] Error processing request: {e}")
            import traceback
            traceback.print_exc()

    def response(self, flow: http.HTTPFlow) -> None:
        """
        拦截响应（类似 Envoy ExtProc ProcessResponse）

        Args:
            flow: mitmproxy HTTP flow object
        """
        if not self._is_llm_request(flow.request):
            return

        status_code = flow.response.status_code
        logger.info(f"[PROXY] Response: {status_code} from {flow.request.host}")

        if status_code >= 400:
            self._log_error(flow)

    def _is_llm_request(self, request: http.Request) -> bool:
        """判断是否是 LLM API 请求"""
        # 检查路径
        if "/chat/completions" in request.path or "/v1/messages" in request.path:
            return True

        # 检查 Host（包括 IP 地址）
        llm_hosts = [
            "api.anthropic.com",
            "api.openai.com",
            "claude.ai",
            "api.claude.ai",
            "bedrock-runtime",
            "api.deepseek.com",
            "160.79.104.10",  # Anthropic IP
        ]
        return any(host in request.pretty_host for host in llm_hosts)

    def _log_request(self, original_model: str, target_provider: str,
                     target_model: str, messages: list):
        """记录请求到全局日志（Dashboard 会读取）"""
        global request_logs

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": "info",
            "category": "routing",
            "message": f"Routed {original_model} → {target_provider}/{target_model}",
            "details": {
                "original_model": original_model,
                "target_provider": target_provider,
                "target_model": target_model,
                "stream": False,
                "message_preview": messages[0].get("content", "")[:50] if messages else ""
            }
        }

        # Write to file (for Dashboard to read)
        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write log to file: {e}")

        # Also keep in memory (backup)
        request_logs.append(log_entry)
        if len(request_logs) > MAX_LOGS:
            request_logs = request_logs[-MAX_LOGS:]

    def _log_error(self, flow: http.HTTPFlow):
        """记录错误"""
        global request_logs

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": "error",
            "category": "proxy",
            "message": f"Error {flow.response.status_code}: {flow.request.pretty_url}",
            "details": {
                "status_code": flow.response.status_code,
                "host": flow.request.host,
                "path": flow.request.path
            }
        }

        # Write to file
        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write error log to file: {e}")

        # Also keep in memory
        request_logs.append(log_entry)
        if len(request_logs) > MAX_LOGS:
            request_logs = request_logs[-MAX_LOGS:]

    def _log_simple(self, url: str, model: str):
        """简单记录转发日志"""
        global request_logs

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": "info",
            "category": "proxy",
            "message": f"Forwarded to Router: {model}",
            "details": {
                "url": url,
                "model": model,
                "forwarded_to": "localhost:8001"
            }
        }

        # Write to file
        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write log: {e}")

        # Also keep in memory
        request_logs.append(log_entry)
        if len(request_logs) > MAX_LOGS:
            request_logs = request_logs[-MAX_LOGS:]


def get_request_logs() -> List[Dict[str, Any]]:
    """获取请求日志（供 Dashboard API 使用）"""
    return request_logs.copy()


# ========================================
# mitmdump entry point
# ========================================
# When mitmdump loads this script, it expects "addons" list

addons = [
    RouterProxyAddon()
]
