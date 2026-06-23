"""
Route Matching Engine
Inspired by vLLM Semantic Router decision matching logic
"""

import fnmatch
import logging
from typing import Optional, List, Dict, Any
from config_loader import RouteRule, RouterConfig

logger = logging.getLogger(__name__)


class RouteMatcher:
    """
    Route matching engine
    Inspired by semantic-router pkg/decision/matcher.go
    """

    def __init__(self, config: RouterConfig):
        self.config = config
        self.routes = config.routes

    def match(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[RouteRule]:
        """
        Match a request to a routing rule

        Similar to semantic-router's decision matching, but simplified:
        1. Iterate routes by priority (high → low)
        2. Check model pattern match (supports * wildcard)
        3. Check optional keyword conditions
        4. Return first match

        Args:
            model: Requested model name
            messages: Chat messages (for keyword matching)
            metadata: Optional metadata (reserved for future use)

        Returns:
            Matched RouteRule, or None if no match
        """
        logger.debug(f"Matching route for model: {model}")

        # Iterate routes by priority (already sorted in config_loader)
        for route in self.routes:
            if self._matches_route(route, model, messages):
                logger.info(
                    f"Matched route: {route.match_model} → "
                    f"{route.target_provider}/{route.target_model}"
                )
                return route

        logger.warning(f"No route matched for model: {model}")
        return None

    def _matches_route(
        self,
        route: RouteRule,
        model: str,
        messages: List[Dict[str, Any]]
    ) -> bool:
        """
        Check if a route matches the request

        Args:
            route: Route rule to check
            model: Requested model name
            messages: Chat messages

        Returns:
            True if route matches
        """
        # 1. Check model pattern match (supports * wildcard)
        if not self._matches_model_pattern(route.match_model, model):
            return False

        # 2. Check optional keyword conditions
        if route.contains_keywords:
            if not self._contains_keywords(messages, route.contains_keywords):
                return False

        return True

    def _matches_model_pattern(self, pattern: str, model: str) -> bool:
        """
        Check if model matches pattern (supports * wildcard)

        Examples:
            gpt-4* matches gpt-4, gpt-4-turbo, gpt-4o
            gpt-3.5-turbo matches exactly gpt-3.5-turbo
            * matches everything

        Args:
            pattern: Pattern to match (e.g., "gpt-4*")
            model: Model name to check (e.g., "gpt-4-turbo")

        Returns:
            True if pattern matches
        """
        return fnmatch.fnmatch(model, pattern)

    def _contains_keywords(
        self,
        messages: List[Dict[str, Any]],
        keywords: List[str]
    ) -> bool:
        """
        Check if messages contain any of the specified keywords

        Args:
            messages: Chat messages
            keywords: List of keywords to check

        Returns:
            True if any keyword is found (case-insensitive)
        """
        # Extract all text content from messages
        text_content = ""
        for msg in messages:
            if isinstance(msg, dict) and "content" in msg:
                content = msg["content"]
                if isinstance(content, str):
                    text_content += content.lower() + " "
                elif isinstance(content, list):
                    # Handle multi-modal content (array of text/image objects)
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text_content += item.get("text", "").lower() + " "

        # Check if any keyword is present
        for keyword in keywords:
            if keyword.lower() in text_content:
                logger.debug(f"Keyword matched: {keyword}")
                return True

        return False

    def get_route_by_priority(self, priority: int) -> Optional[RouteRule]:
        """Get route by priority (for debugging)"""
        for route in self.routes:
            if route.priority == priority:
                return route
        return None

    def list_routes(self) -> List[RouteRule]:
        """List all routes (for debugging)"""
        return self.routes


# Example usage and testing
if __name__ == "__main__":
    import sys
    from config_loader import load_config

    # Setup logging
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )

    # Load configuration
    config = load_config("config/config.yaml")
    matcher = RouteMatcher(config)

    print("\n=== Route Matcher Test ===\n")

    # Test cases
    test_cases = [
        {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Please translate this text"}],
            "expected": "gpt-4o-mini",  # Should match keyword rule
        },
        {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Explain quantum computing"}],
            "expected": "gpt-4o",  # Should preserve (no keyword match)
        },
        {
            "model": "gpt-4-turbo",
            "messages": [{"role": "user", "content": "Hello world"}],
            "expected": "deepseek-chat",  # Should match gpt-4* pattern
        },
        {
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Write code"}],
            "expected": "claude-3-opus-20240229",  # Should preserve
        },
        {
            "model": "unknown-model",
            "messages": [{"role": "user", "content": "Test"}],
            "expected": "unknown-model",  # Should match fallback * rule
        },
    ]

    for i, test in enumerate(test_cases, 1):
        print(f"Test {i}: {test['model']}")
        print(f"  Content: {test['messages'][0]['content']}")

        route = matcher.match(test["model"], test["messages"])

        if route:
            target_model = (
                test["model"] if route.target_model == "preserve"
                else route.target_model
            )
            print(f"  ✓ Matched: {route.target_provider}/{target_model}")
            print(f"  Priority: {route.priority}")

            if target_model == test["expected"]:
                print(f"  ✅ PASS (expected {test['expected']})")
            else:
                print(f"  ❌ FAIL (expected {test['expected']}, got {target_model})")
        else:
            print(f"  ❌ No route matched!")

        print()
