"""
Configuration Loader for Router
Inspired by vLLM Semantic Router config structure
"""

import os
import yaml
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """
    Provider configuration (支持所有 semantic-router provider 类型)

    参考: AgentOS/src/semantic-router/pkg/config/canonical_providers.go
    """
    name: str
    base_url: str
    api_key: str

    # 可选字段（用于特殊 provider）
    provider_type: Optional[str] = None  # openai, anthropic, azure-openai, bedrock, etc.
    api_version: Optional[str] = None    # Azure OpenAI 需要
    extra_headers: Optional[Dict[str, str]] = None  # 额外的 HTTP 头

    def get_api_key(self) -> str:
        """Resolve API key from environment if needed"""
        if self.api_key.startswith("env:"):
            env_var = self.api_key.split(":", 1)[1]
            key = os.environ.get(env_var)
            if not key:
                logger.warning(f"Environment variable {env_var} not set for provider {self.name}")
                return ""
            return key
        return self.api_key

    def get_chat_endpoint(self) -> str:
        """
        Get the full chat completions endpoint URL

        Different providers use different endpoints:
        - Anthropic: /v1/messages
        - Azure OpenAI: /chat/completions?api-version=...
        - MiniMax: /v1/chat/completions
        - Others: /chat/completions (OpenAI-compatible)

        参考: semantic-router/pkg/config/helper.go:757-793
        """
        base_url = self.base_url.rstrip("/")

        # Anthropic 特殊端点
        if "anthropic.com" in self.base_url:
            return f"{base_url}/v1/messages"

        # Azure OpenAI 需要 api-version 参数
        elif "openai.azure.com" in self.base_url:
            api_version = self.api_version or "2024-10-21"
            return f"{base_url}/chat/completions?api-version={api_version}"

        # MiniMax 特殊路径
        elif "minimax" in self.base_url or self.name == "minimax":
            return f"{base_url}/v1/chat/completions"

        # 标准 OpenAI 兼容端点
        elif self.base_url.endswith("/v1"):
            return f"{base_url}/chat/completions"
        else:
            return f"{base_url}/chat/completions"


@dataclass
class RouteRule:
    """
    Route rule configuration
    Inspired by semantic-router decision rules, but simplified
    """
    match_model: str  # Pattern to match (supports * wildcard)
    target_provider: str
    target_model: str  # "preserve" means keep original model name

    # Optional conditions (for keyword-based routing)
    contains_keywords: Optional[List[str]] = None

    # Priority (higher = evaluated first)
    priority: int = 0

    def __post_init__(self):
        # Convert single keyword to list
        if self.contains_keywords and isinstance(self.contains_keywords, str):
            self.contains_keywords = [self.contains_keywords]


@dataclass
class PrivacyGuardConfig:
    """Privacy guard configuration"""
    enabled: bool = True
    policies: Dict[str, Any] = field(default_factory=dict)
    regex_audit: Dict[str, Any] = field(default_factory=dict)
    data_masking: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouterConfig:
    """
    Main router configuration
    Inspired by vLLM Semantic Router config.yaml structure
    """
    providers: Dict[str, ProviderConfig]
    routes: List[RouteRule]
    privacy_guard: PrivacyGuardConfig

    # Router server settings
    server: Dict[str, Any] = field(default_factory=lambda: {
        "host": "0.0.0.0",
        "port": 8000,
        "workers": 1,
    })

    # Logging settings
    logging: Dict[str, Any] = field(default_factory=lambda: {
        "level": "INFO",
        "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    })

    @classmethod
    def from_yaml(cls, config_path: str) -> "RouterConfig":
        """
        Load configuration from YAML file
        Similar to semantic-router's config loading
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Parse providers
        providers = {}
        for name, prov_data in data.get("providers", {}).items():
            providers[name] = ProviderConfig(
                name=name,
                base_url=prov_data["base_url"],
                api_key=prov_data.get("api_key", ""),
                provider_type=prov_data.get("provider_type"),
                api_version=prov_data.get("api_version"),
                extra_headers=prov_data.get("extra_headers"),
            )

        # Parse routes (sorted by priority descending)
        routes = []
        for route_data in data.get("routes", []):
            route = RouteRule(
                match_model=route_data["match_model"],
                target_provider=route_data["target_provider"],
                target_model=route_data["target_model"],
                contains_keywords=route_data.get("contains_keywords"),
                priority=route_data.get("priority", 0),
            )
            routes.append(route)

        # Sort routes by priority (higher first)
        routes.sort(key=lambda r: r.priority, reverse=True)

        # Parse privacy guard
        privacy_data = data.get("privacy_guard", {})
        privacy_guard = PrivacyGuardConfig(
            enabled=privacy_data.get("enabled", True),
            policies=privacy_data.get("policies", {}),
            regex_audit=privacy_data.get("regex_audit", {}),
            data_masking=privacy_data.get("data_masking", {}),
        )

        # Parse server settings
        server = data.get("server", {})
        if not server:
            server = {"host": "0.0.0.0", "port": 8000, "workers": 1}

        # Parse logging settings
        logging_config = data.get("logging", {})
        if not logging_config:
            logging_config = {
                "level": "INFO",
                "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            }

        return cls(
            providers=providers,
            routes=routes,
            privacy_guard=privacy_guard,
            server=server,
            logging=logging_config,
        )

    def get_provider(self, name: str) -> Optional[ProviderConfig]:
        """Get provider by name"""
        return self.providers.get(name)

    def get_all_provider_names(self) -> List[str]:
        """Get all provider names"""
        return list(self.providers.keys())


def load_config(config_path: str = "config/config.yaml") -> RouterConfig:
    """
    Load router configuration from YAML file

    Args:
        config_path: Path to config.yaml file

    Returns:
        RouterConfig object
    """
    logger.info(f"Loading configuration from {config_path}")
    config = RouterConfig.from_yaml(config_path)
    logger.info(f"Loaded {len(config.providers)} providers")
    logger.info(f"Loaded {len(config.routes)} routing rules")
    return config


# Example usage and testing
if __name__ == "__main__":
    # Test configuration loading
    logging.basicConfig(level=logging.INFO)

    try:
        config = load_config("config/config.yaml")

        print("\n=== Router Configuration ===")
        print(f"Providers: {len(config.providers)}")
        for name, provider in list(config.providers.items())[:3]:
            print(f"  - {name}: {provider.base_url}")

        print(f"\nRoutes: {len(config.routes)}")
        for route in config.routes[:5]:
            print(f"  - {route.match_model} → {route.target_provider}/{route.target_model}")
            if route.contains_keywords:
                print(f"    Keywords: {route.contains_keywords}")

        print(f"\nPrivacy Guard: {'Enabled' if config.privacy_guard.enabled else 'Disabled'}")

    except Exception as e:
        print(f"Error loading config: {e}")
        import traceback
        traceback.print_exc()
