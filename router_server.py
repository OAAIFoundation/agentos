"""
Router Server - OpenAI-Compatible API Gateway
Inspired by vLLM Semantic Router architecture

This server provides an OpenAI-compatible API endpoint that:
1. Receives chat completion requests
2. Matches routing rules from config.yaml
3. Routes to appropriate LLM provider
4. Returns response in OpenAI format

Agents/applications configure their base_url to point to this router.
"""

import os
import sys
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, List, Any, Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel
from pathlib import Path

# Import our modules
from config_loader import load_config, RouterConfig
from route_matcher import RouteMatcher
from llm_client import LLMClient
from db_logger import DatabaseLogger

# Optional: Import privacy guard if available
try:
    from privacy_guard import PrivacyGuard
    PRIVACY_GUARD_AVAILABLE = True
except ImportError:
    PRIVACY_GUARD_AVAILABLE = False
    logging.warning("privacy_guard.py not found - privacy features disabled")


# ======================== Configuration ========================

# Default config path
DEFAULT_CONFIG_PATH = os.environ.get("ROUTER_CONFIG", "config/config.yaml")

# Global instances (initialized at startup)
router_config: Optional[RouterConfig] = None
route_matcher: Optional[RouteMatcher] = None
llm_client: Optional[LLMClient] = None
privacy_guard: Optional[Any] = None
db_logger: Optional[DatabaseLogger] = None

# Request logs storage (in-memory cache for fast access)
request_logs: List[Dict[str, Any]] = []
MAX_LOGS = 100  # Reduced to 100 for memory cache (full history in database)


# ======================== Pydantic Models ========================

class ChatMessage(BaseModel):
    role: str
    content: str | List[Dict[str, Any]]  # Support multi-modal content


class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    temperature: Optional[float] = 1.0
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    # Add other OpenAI parameters as needed


# ======================== FastAPI Lifespan ========================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager
    Similar to semantic-router's initialization flow
    """
    global router_config, route_matcher, llm_client, privacy_guard, db_logger

    # Startup
    logger.info("=" * 60)
    logger.info("🚀 Router Server Starting")
    logger.info("=" * 60)

    try:
        # Initialize database logger
        logger.info("Initializing database logger")
        db_logger = DatabaseLogger()
        log_count = db_logger.get_log_count()
        logger.info(f"Database contains {log_count} historical logs")

        # Load configuration
        logger.info(f"Loading configuration from {DEFAULT_CONFIG_PATH}")
        router_config = load_config(DEFAULT_CONFIG_PATH)

        # Initialize route matcher
        logger.info("Initializing route matcher")
        route_matcher = RouteMatcher(router_config)

        # Initialize LLM client (direct connection via hotspot)
        logger.info("Initializing Enhanced LLM client (支持所有 semantic-router provider 类型)")
        # No upstream proxy needed - direct internet access
        logger.info("Using direct connection (no upstream proxy)")
        # Use 5 second timeout for fast feedback in dashboard testing
        llm_client = LLMClient(timeout=5.0, upstream_proxy=None)

        # Initialize privacy guard (if available and enabled)
        if PRIVACY_GUARD_AVAILABLE and router_config.privacy_guard.enabled:
            logger.info("Initializing privacy guard")
            # Note: PrivacyGuard needs to be adapted to work with new config structure
            # For now, we'll skip it and add it in the next step
            privacy_guard = None
            logger.warning("Privacy guard integration pending")
        else:
            logger.info("Privacy guard disabled")

        logger.info(f"Loaded {len(router_config.providers)} providers")
        logger.info(f"Loaded {len(router_config.routes)} routing rules")

        logger.info("=" * 60)
        logger.info("✅ Router Server Ready")
        logger.info("=" * 60)

        yield  # Run application

    except Exception as e:
        logger.error(f"Failed to start router server: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        # Shutdown
        logger.info("Shutting down router server")
        if llm_client:
            await llm_client.close()


# ======================== FastAPI Application ========================

app = FastAPI(
    title="LLM Router Server",
    description="OpenAI-compatible API gateway with intelligent routing",
    version="1.0.0",
    lifespan=lifespan
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


# ======================== Dashboard & Health Check ========================

@app.get("/")
async def root():
    """Redirect to dashboard"""
    return HTMLResponse(content="""
<!DOCTYPE html>
<html>
<head>
    <meta http-equiv="refresh" content="0; url=/dashboard">
    <title>Redirecting...</title>
</head>
<body>
    <p>Redirecting to <a href="/dashboard">Dashboard</a>...</p>
</body>
</html>
    """)


@app.get("/dashboard")
async def dashboard():
    """Serve dashboard HTML - use the full-featured dashboard"""
    # Use the original full-featured dashboard (has edit, logs, etc.)
    dashboard_path = Path("web/index.html")

    if not dashboard_path.exists():
        return HTMLResponse(
            content="<h1>Dashboard not found</h1><p>web/index.html is missing</p>",
            status_code=404
        )

    with open(dashboard_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/v1/models")
async def list_models():
    """
    List available models (OpenAI-compatible)
    Returns all providers as "models"
    """
    if not router_config:
        raise HTTPException(status_code=500, detail="Router not initialized")

    models = []
    for provider_name in router_config.get_all_provider_names():
        models.append({
            "id": provider_name,
            "object": "model",
            "created": 0,
            "owned_by": "router",
        })

    return {"object": "list", "data": models}


# ======================== Dashboard API Endpoints ========================

@app.get("/api/config")
async def get_config():
    """Get current router configuration"""
    if not router_config:
        raise HTTPException(status_code=500, detail="Router not initialized")

    # Convert config to dict for JSON response
    config_dict = {
        "providers": {
            name: {
                "name": p.name,
                "base_url": p.base_url,
                "api_key": "***" if p.api_key else None  # Mask API keys
            }
            for name, p in router_config.providers.items()
        },
        "routes": [
            {
                "match_model": r.match_model,
                "target_provider": r.target_provider,
                "target_model": r.target_model,
                "contains_keywords": r.contains_keywords,
                "priority": r.priority
            }
            for r in router_config.routes
        ],
        "privacy_guard": {
            "enabled": router_config.privacy_guard.enabled
        }
    }

    return JSONResponse(content=config_dict)


@app.get("/api/stats")
async def get_stats(start_date: str = None, end_date: str = None):
    """
    Get router statistics

    Query parameters:
    - start_date: Start date filter (ISO format)
    - end_date: End date filter (ISO format)
    """
    stats = {
        "providers": len(router_config.providers) if router_config else 0,
        "routes": len(router_config.routes) if router_config else 0,
        "status": "running"
    }

    # Get request statistics from database
    if db_logger:
        db_stats = db_logger.get_stats(start_date=start_date, end_date=end_date)
        stats.update(db_stats)
    else:
        stats["total_requests"] = 0

    return stats


@app.post("/api/config")
async def save_config(request: Request):
    """Save configuration (write to config.yaml)"""
    # TODO: Implement config saving
    # For now, return success but don't actually save
    return {"status": "ok", "message": "Config saving not yet implemented in Router"}


@app.get("/api/logs")
async def get_logs(
    level: str = "all",
    limit: int = 100,
    offset: int = 0,
    provider: str = None,
    start_date: str = None,
    end_date: str = None
):
    """
    Get request logs from database

    Query parameters:
    - level: Filter by log level (all, info, error)
    - limit: Maximum number of records (default: 100)
    - offset: Pagination offset (default: 0)
    - provider: Filter by provider name
    - start_date: Start date filter (ISO format)
    - end_date: End date filter (ISO format)
    """
    if not db_logger:
        return {"logs": []}

    try:
        logs = db_logger.get_logs(
            level=level if level != "all" else None,
            provider=provider,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset
        )
        return {"logs": logs, "count": len(logs)}
    except Exception as e:
        logger.error(f"Failed to get logs: {e}")
        return {"logs": [], "error": str(e)}


@app.post("/api/logs/clear")
async def clear_logs(before_date: str = None):
    """
    Clear logs from database

    Query parameters:
    - before_date: Optional ISO date, only delete logs before this date
    """
    if not db_logger:
        return {"status": "error", "message": "Database logger not initialized"}

    try:
        # Clear database logs
        count = db_logger.clear_logs(before_date=before_date)

        # Also clear memory cache
        global request_logs
        request_logs = []

        logger.info(f"Cleared {count} database logs")
        return {"status": "ok", "cleared": count}
    except Exception as e:
        logger.error(f"Failed to clear logs: {e}")
        return {"status": "error", "message": str(e)}


# ======================== Chat Completion Endpoint ========================

@app.post("/v1/messages")
async def anthropic_messages(request: Request):
    """
    Anthropic Messages API endpoint
    This is what Claude Code Extension actually uses!
    """
    try:
        # Parse request body
        body = await request.json()
        model = body.get("model", "claude-sonnet-4-5")
        messages = body.get("messages", [])

        logger.info(f"[Anthropic API] Received request: model={model}")

        # Route to chat_completions
        chat_request = ChatCompletionRequest(
            model=model,
            messages=[ChatMessage(**msg) for msg in messages],
            max_tokens=body.get("max_tokens", 1024),
            temperature=body.get("temperature", 1.0),
            stream=body.get("stream", False)
        )

        return await chat_completions(chat_request, request)

    except Exception as e:
        logger.error(f"Error in Anthropic Messages API: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest, raw_request: Request):
    """
    Chat completion endpoint (OpenAI-compatible)

    This is the main routing logic, inspired by semantic-router's ExtProc flow:
    1. Extract request parameters
    2. Match routing rule (route_matcher)
    3. Route to target provider (llm_client)
    4. Return response
    """
    global request_logs
    from datetime import datetime

    request_start_time = datetime.now()

    try:
        # Log incoming request
        logger.info(f"Received chat completion request: model={request.model}")

        # Convert Pydantic messages to dict
        messages = [msg.model_dump() for msg in request.messages]

        # Step 1: Match routing rule
        route = route_matcher.match(
            model=request.model,
            messages=messages
        )

        if not route:
            raise HTTPException(
                status_code=400,
                detail=f"No routing rule matched for model: {request.model}"
            )

        # Step 2: Determine target provider and model
        target_provider_name = route.target_provider
        target_model = (
            request.model if route.target_model == "preserve"
            else route.target_model
        )

        provider = router_config.get_provider(target_provider_name)
        if not provider:
            raise HTTPException(
                status_code=500,
                detail=f"Provider not found: {target_provider_name}"
            )

        logger.info(
            f"Routing: {request.model} → "
            f"{target_provider_name}/{target_model}"
        )

        # Add log entry
        log_entry = {
            "timestamp": request_start_time.isoformat(),
            "level": "info",
            "category": "routing",
            "message": f"Routed {request.model} → {target_provider_name}/{target_model}",
            "details": {
                "original_model": request.model,
                "target_provider": target_provider_name,
                "target_model": target_model,
                "stream": request.stream,
                "message_preview": messages[0].get("content", "")[:50] if messages else ""
            }
        }

        # Write to database (persistent)
        if db_logger:
            db_logger.add_log(log_entry)

        # Also keep in memory for fast access
        request_logs.append(log_entry)
        if len(request_logs) > MAX_LOGS:
            request_logs = request_logs[-MAX_LOGS:]

        # Step 3: Forward request to target provider
        kwargs = {
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        # Remove None values
        kwargs = {k: v for k, v in kwargs.items() if v is not None}

        if request.stream:
            # Streaming response
            stream = await llm_client.chat_completion(
                provider=provider,
                model=target_model,
                messages=messages,
                stream=True,
                **kwargs
            )

            # Return as SSE stream
            return StreamingResponse(
                stream,
                media_type="text/event-stream"
            )
        else:
            # Normal response
            response = await llm_client.chat_completion(
                provider=provider,
                model=target_model,
                messages=messages,
                stream=False,
                **kwargs
            )

            return JSONResponse(content=response)

    except HTTPException as e:
        # Log HTTP errors
        error_log = {
            "timestamp": datetime.now().isoformat(),
            "level": "error",
            "category": "routing",
            "message": f"HTTP Error {e.status_code}: {e.detail}",
            "details": {
                "status_code": e.status_code,
                "model": request.model
            }
        }

        # Write to database
        if db_logger:
            db_logger.add_log(error_log)

        # Also keep in memory
        request_logs.append(error_log)
        if len(request_logs) > MAX_LOGS:
            request_logs = request_logs[-MAX_LOGS:]
        raise
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        import traceback
        traceback.print_exc()

        # Log general errors
        error_log = {
            "timestamp": datetime.now().isoformat(),
            "level": "error",
            "category": "system",
            "message": f"Internal error: {str(e)}",
            "details": {
                "model": request.model,
                "error_type": type(e).__name__
            }
        }

        # Write to database
        if db_logger:
            db_logger.add_log(error_log)

        # Also keep in memory
        request_logs.append(error_log)
        if len(request_logs) > MAX_LOGS:
            request_logs = request_logs[-MAX_LOGS:]

        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# ======================== Main Entry Point ========================

def main():
    """Start router server"""
    import uvicorn

    # Load config to get server settings
    config = load_config(DEFAULT_CONFIG_PATH)

    host = config.server.get("host", "0.0.0.0")
    port = config.server.get("port", 8000)
    workers = config.server.get("workers", 1)

    logger.info(f"Starting router server on {host}:{port}")
    logger.info(f"Workers: {workers}")

    uvicorn.run(
        "router_server:app",
        host=host,
        port=port,
        workers=workers,
        log_level="info",
        access_log=True,
    )


if __name__ == "__main__":
    main()
