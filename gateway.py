"""
LLM Routing Gateway
A universal routing gateway for LLM APIs with dynamic configuration
Fully compatible with OpenAI /v1/chat/completions API specification
"""

import os
import re
import yaml
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ======================== Configuration ========================

CONFIG_FILE = "config/config.yaml"
config_data: Dict[str, Any] = {}
config_lock = asyncio.Lock()

# ======================== Pydantic Models ========================

class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: Optional[float] = 1.0
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    top_p: Optional[float] = 1.0
    frequency_penalty: Optional[float] = 0.0
    presence_penalty: Optional[float] = 0.0
    n: Optional[int] = 1
    stop: Optional[List[str]] = None

# ======================== FastAPI Application ========================

app = FastAPI(
    title="LLM Routing Gateway",
    description="Universal routing gateway for LLM APIs with dynamic configuration",
    version="2.0.0"
)

# ======================== Configuration Management ========================

def load_config() -> Dict[str, Any]:
    """
    Load configuration from YAML file
    Supports environment variable substitution (env:VAR_NAME)
    """
    config_path = Path(CONFIG_FILE)

    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file {CONFIG_FILE} not found")

    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Process environment variables in provider API keys
    if 'providers' in config:
        for provider_name, provider_config in config['providers'].items():
            if 'api_key' in provider_config:
                api_key = provider_config['api_key']
                if isinstance(api_key, str) and api_key.startswith('env:'):
                    env_var = api_key[4:]  # Remove 'env:' prefix
                    provider_config['api_key'] = os.getenv(env_var, '')
                    if not provider_config['api_key']:
                        print(f"WARNING:  Warning: Environment variable {env_var} not set for provider {provider_name}")

    return config

async def reload_config():
    """
    Reload configuration with thread safety
    """
    global config_data
    async with config_lock:
        try:
            new_config = load_config()
            config_data = new_config
            print(f"\n🔄 Configuration reloaded at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Providers: {len(config_data.get('providers', {}))}")
            print(f"   Routes: {len(config_data.get('routes', []))}")
        except Exception as e:
            print(f"[ERROR] Failed to reload config: {str(e)}")

class ConfigFileHandler(FileSystemEventHandler):
    """
    Watch config file for changes and auto-reload
    """
    def on_modified(self, event):
        if event.src_path.endswith(CONFIG_FILE):
            asyncio.create_task(reload_config())

# ======================== Routing Engine ========================

def match_pattern(pattern: str, value: str) -> bool:
    """
    Match string against pattern with wildcard support
    * matches any sequence of characters
    """
    # Convert wildcard pattern to regex
    regex_pattern = pattern.replace('*', '.*')
    regex_pattern = f'^{regex_pattern}$'
    return bool(re.match(regex_pattern, value))

def check_keywords(messages: List[Message], keywords: List[str]) -> bool:
    """
    Check if any message contains specified keywords
    """
    if not keywords:
        return True

    full_text = ' '.join([msg.content for msg in messages])
    return any(keyword.lower() in full_text.lower() for keyword in keywords)

def find_matching_route(model: str, messages: List[Message], routes: List[Dict]) -> Optional[Dict]:
    """
    Find first matching route based on model and keywords
    Returns the matched route configuration or None
    """
    for route in routes:
        # Check model pattern match
        match_model = route.get('match_model', '*')
        if not match_pattern(match_model, model):
            continue

        # Check keyword match (if specified)
        contains_keywords = route.get('contains_keywords', [])
        if contains_keywords and not check_keywords(messages, contains_keywords):
            continue

        # Match found
        return route

    return None

def resolve_target_model(target_model: str, original_model: str) -> str:
    """
    Resolve target model name
    - If target_model is "preserve" or "${original}", keep original
    - Otherwise use target_model
    """
    if target_model in ["preserve", "${original}"]:
        return original_model
    return target_model

def get_provider_config(provider_name: str) -> Optional[Dict[str, str]]:
    """
    Get provider configuration (base_url and api_key)
    """
    providers = config_data.get('providers', {})
    return providers.get(provider_name)

# ======================== Provider Adapters ========================

def adapt_request_for_anthropic(payload: dict) -> tuple[str, dict, dict]:
    """
    Adapt OpenAI format to Anthropic Claude API format
    Returns: (endpoint, headers, adapted_payload)
    """
    messages = payload.get('messages', [])

    # Anthropic requires system message separate
    system_message = None
    chat_messages = []

    for msg in messages:
        if msg['role'] == 'system':
            system_message = msg['content']
        else:
            chat_messages.append(msg)

    adapted = {
        'model': payload['model'],
        'messages': chat_messages,
        'max_tokens': payload.get('max_tokens', 4096),
        'temperature': payload.get('temperature', 1.0),
        'stream': payload.get('stream', False)
    }

    if system_message:
        adapted['system'] = system_message

    headers = {'anthropic-version': '2023-06-01'}

    return '/messages', headers, adapted

def adapt_request_for_google(payload: dict) -> tuple[str, dict, dict]:
    """
    Adapt OpenAI format to Google Gemini API format
    Returns: (endpoint, headers, adapted_payload)
    """
    # Google Gemini uses OpenAI-compatible format with slight differences
    model = payload['model']
    endpoint = f'/models/{model}:generateContent'

    adapted = {
        'contents': [],
        'generationConfig': {
            'temperature': payload.get('temperature', 1.0),
            'maxOutputTokens': payload.get('max_tokens', 2048),
        }
    }

    # Convert messages to Gemini format
    for msg in payload.get('messages', []):
        role = 'user' if msg['role'] in ['user', 'system'] else 'model'
        adapted['contents'].append({
            'role': role,
            'parts': [{'text': msg['content']}]
        })

    return endpoint, {}, adapted

def detect_provider_type(base_url: str) -> str:
    """
    Detect provider type from base URL
    """
    url_lower = base_url.lower()

    if 'anthropic.com' in url_lower:
        return 'anthropic'
    elif 'generativelanguage.googleapis.com' in url_lower or 'google' in url_lower:
        return 'google'
    elif 'openai.com' in url_lower or 'deepseek' in url_lower or 'dashscope' in url_lower \
         or 'moonshot' in url_lower or 'groq' in url_lower or 'together' in url_lower \
         or 'cohere' in url_lower or 'mistral' in url_lower or 'replicate' in url_lower \
         or 'perplexity' in url_lower or 'bigmodel.cn' in url_lower or 'minimax' in url_lower \
         or 'localhost' in url_lower or '127.0.0.1' in url_lower:
        return 'openai'  # OpenAI-compatible
    else:
        return 'openai'  # Default to OpenAI-compatible

# ======================== Proxy Engine ========================

async def proxy_request(
    target_url: str,
    api_key: str,
    payload: dict,
    stream: bool,
    provider_type: str = 'openai'
) -> Any:
    """
    Forward request to target provider
    Supports both streaming and non-streaming responses
    Transparently passes through errors
    Handles provider-specific API formats
    """
    # Prepare headers based on provider type
    if provider_type == 'anthropic':
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
    elif provider_type == 'google':
        headers = {
            "Content-Type": "application/json"
        }
        # Google uses API key in URL parameter
        if '?' in target_url:
            target_url = f"{target_url}&key={api_key}"
        else:
            target_url = f"{target_url}?key={api_key}"
    else:  # OpenAI-compatible (default)
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            if stream:
                # Streaming request
                async with client.stream(
                    "POST",
                    target_url,
                    json=payload,
                    headers=headers
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        raise HTTPException(
                            status_code=response.status_code,
                            detail=f"Upstream API Error: {error_text.decode()}"
                        )

                    async def stream_generator():
                        async for chunk in response.aiter_bytes():
                            yield chunk

                    return StreamingResponse(
                        stream_generator(),
                        media_type="text/event-stream",
                        headers=dict(response.headers)
                    )
            else:
                # Non-streaming request
                response = await client.post(
                    target_url,
                    json=payload,
                    headers=headers
                )

                if response.status_code != 200:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Upstream API Error: {response.text}"
                    )

                # Handle non-JSON responses gracefully
                try:
                    return JSONResponse(content=response.json())
                except ValueError:
                    # Response is not valid JSON
                    raise HTTPException(
                        status_code=502,
                        detail=f"Upstream returned non-JSON response: {response.text[:200]}"
                    )

        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Upstream API request timeout")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Network error: {str(e)}")

# ======================== Logging ========================

def log_route_decision(
    original_model: str,
    target_provider: str,
    target_model: str,
    route_name: Optional[str] = None,
    matched_keywords: bool = False
):
    """
    Log routing decision to console
    """
    print("\n" + "="*80)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🚦 Route Decision")
    print("="*80)
    if route_name:
        print(f"📋 Matched Route: {route_name}")
    if matched_keywords:
        print(f"🔑 Keyword Match: YES")
    print(f"📥 Original Model: {original_model}")
    print(f"🎯 Target Provider: {target_provider}")
    print(f"📤 Target Model: {target_model}")
    if original_model != target_model:
        print(f"🔄 Model Rewritten: {original_model} → {target_model}")
    print("="*80 + "\n")

# ======================== API Routes ========================

@app.on_event("startup")
async def startup_event():
    """
    Load configuration on startup and setup file watcher
    """
    global config_data

    try:
        config_data = load_config()
        print("\n" + "="*80)
        print("[OK] Configuration loaded successfully")
        print(f"   Providers: {list(config_data.get('providers', {}).keys())}")
        print(f"   Routes: {len(config_data.get('routes', []))}")
        print("="*80 + "\n")

        # Setup file watcher for hot reload
        event_handler = ConfigFileHandler()
        observer = Observer()
        observer.schedule(event_handler, path='.', recursive=False)
        observer.start()
        print("[WATCH]  Config file watcher started (hot reload enabled)\n")

    except Exception as e:
        print(f"[ERROR] Failed to load configuration: {str(e)}")
        raise

@app.get("/")
async def root():
    """
    Redirect to dashboard
    """
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <meta http-equiv="refresh" content="0; url=/dashboard" />
    </head>
    <body>
        <p>Redirecting to dashboard...</p>
    </body>
    </html>
    """)

@app.get("/health")
async def health_check():
    """
    Health check endpoint
    """
    return {
        "service": "LLM Routing Gateway",
        "status": "running",
        "version": "2.0.0",
        "providers": list(config_data.get('providers', {}).keys()),
        "routes": len(config_data.get('routes', []))
    }

@app.post("/reload")
async def reload_config_endpoint():
    """
    Manual configuration reload endpoint
    """
    await reload_config()
    return {
        "status": "success",
        "message": "Configuration reloaded",
        "providers": list(config_data.get('providers', {}).keys()),
        "routes": len(config_data.get('routes', []))
    }

# ======================== Dashboard & Config API ========================

@app.get("/dashboard")
async def dashboard():
    """
    Serve dashboard HTML
    """
    dashboard_html = Path("web/index.html")
    if not dashboard_html.exists():
        return HTMLResponse(
            content="<h1>Dashboard not found</h1><p>web/index.html is missing</p>",
            status_code=404
        )

    with open(dashboard_html, 'r', encoding='utf-8') as f:
        return HTMLResponse(content=f.read())

@app.get("/api/config")
async def get_config():
    """
    Get current configuration as JSON
    """
    try:
        config_path = Path(CONFIG_FILE)
        if not config_path.exists():
            raise HTTPException(status_code=404, detail="Configuration file not found")

        with open(config_path, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)

        return JSONResponse(content=raw_config)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read config: {str(e)}")

@app.post("/api/config")
async def update_config(request: Request):
    """
    Update configuration from JSON
    """
    try:
        # Get JSON body
        new_config = await request.json()

        # Validate basic structure
        if 'providers' not in new_config or 'routes' not in new_config:
            raise HTTPException(
                status_code=400,
                detail="Invalid config structure: missing 'providers' or 'routes'"
            )

        # Backup existing config
        config_path = Path(CONFIG_FILE)
        backup_path = Path(f"{CONFIG_FILE}.backup")

        if config_path.exists():
            import shutil
            shutil.copy(config_path, backup_path)

        # Write new config
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(new_config, f, default_flow_style=False, allow_unicode=True)

        # Reload configuration
        await reload_config()

        return {
            "status": "success",
            "message": "Configuration updated and reloaded",
            "backup": str(backup_path)
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update config: {str(e)}")

@app.post("/api/reload")
async def api_reload_config():
    """
    Reload configuration via API
    """
    await reload_config()
    return {
        "status": "success",
        "message": "Configuration reloaded",
        "timestamp": datetime.now().isoformat(),
        "providers": list(config_data.get('providers', {}).keys()),
        "routes": len(config_data.get('routes', []))
    }

# ======================== LLM Proxy Routes ========================

@app.post("/v1/chat/completions")
async def chat_completions(request: Request, body: ChatCompletionRequest):
    """
    OpenAI compatible /v1/chat/completions endpoint
    Routes requests based on configuration rules
    """
    # 0. Check for Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        raise HTTPException(
            status_code=401,
            detail="Missing authorization header"
        )

    # 1. Find matching route
    routes = config_data.get('routes', [])
    matched_route = find_matching_route(body.model, body.messages, routes)

    if not matched_route:
        raise HTTPException(
            status_code=400,
            detail=f"No matching route found for model: {body.model}"
        )

    # 2. Extract target configuration
    target_provider_name = matched_route.get('target_provider')
    target_model_pattern = matched_route.get('target_model', 'preserve')
    target_model = resolve_target_model(target_model_pattern, body.model)

    # 3. Get provider configuration
    provider_config = get_provider_config(target_provider_name)
    if not provider_config:
        raise HTTPException(
            status_code=500,
            detail=f"Provider configuration not found: {target_provider_name}"
        )

    base_url = provider_config['base_url']
    api_key = provider_config['api_key']

    # 4. Detect provider type for API adaptation
    provider_type = detect_provider_type(base_url)

    # 5. Construct target URL based on provider type
    if provider_type == 'anthropic':
        # Anthropic uses /v1/messages
        if base_url.endswith('/v1'):
            target_url = f"{base_url}/messages"
        else:
            target_url = f"{base_url}/v1/messages"
    elif provider_type == 'google':
        # Google Gemini uses different endpoint structure
        # Will be constructed in adapter
        target_url = base_url
    else:
        # OpenAI-compatible providers use /v1/chat/completions
        if not base_url.endswith('/chat/completions'):
            if base_url.endswith('/v1'):
                target_url = f"{base_url}/chat/completions"
            elif base_url.endswith('/'):
                target_url = f"{base_url}v1/chat/completions"
            else:
                target_url = f"{base_url}/v1/chat/completions"
        else:
            target_url = base_url

    # 6. Log routing decision
    route_name = matched_route.get('match_model', 'unknown')
    has_keywords = bool(matched_route.get('contains_keywords'))
    log_route_decision(
        body.model,
        target_provider_name,
        target_model,
        route_name,
        has_keywords
    )

    # 7. Prepare forwarding payload
    payload = body.model_dump()
    payload['model'] = target_model

    # 8. Forward request to target provider with type detection
    response = await proxy_request(target_url, api_key, payload, body.stream, provider_type)

    return response

# ======================== Startup Command ========================

if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*60)
    print("  LLM Routing Gateway Starting...")
    print("  Dynamic Multi-Provider Routing with Hot Reload")
    print("  Dashboard: http://localhost:8000/dashboard")
    print("="*60 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
