"""
Privacy Guard Module - Generic Policy Engine with Priority Arbitration
Expression-based security policy evaluation for LLM Gateway
Uses rule-engine library for safe and flexible policy evaluation
Supports priority-based conflict resolution
"""

import re
import json
import logging
from typing import Dict, List, Optional, Any, AsyncIterator
from dataclasses import dataclass, field
from fastapi import HTTPException

try:
    import rule_engine
except ImportError:
    rule_engine = None
    logging.warning("rule-engine library not installed. Policy engine will be disabled.")

logger = logging.getLogger(__name__)


# ======================== Action Severity Map ========================
# Used for conflict resolution when priorities are equal
# Higher severity = higher precedence
ACTION_SEVERITY_MAP = {
    "block": 100,
    "log_and_block": 90,
    "reroute": 50,
    "allow": 0
}


# ======================== Data Structures ========================

@dataclass
class PolicyContext:
    """Context object for policy evaluation"""
    model: str
    prompt: str
    prompt_length: int
    has_attachments: bool
    attachment_count: int
    # Pre-computed regex matches for common patterns
    contains_confidential: bool = False
    contains_injection: bool = False
    contains_credential: bool = False
    contains_api_key: bool = False  # AWS AKIA or OpenAI sk-
    is_trivial_greeting: bool = False  # Short greetings like "hello", "你好", "test"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for rule engine"""
        return {
            "model": self.model,
            "prompt": self.prompt,
            "prompt_length": self.prompt_length,
            "has_attachments": self.has_attachments,
            "attachment_count": self.attachment_count,
            "contains_confidential": self.contains_confidential,
            "contains_injection": self.contains_injection,
            "contains_credential": self.contains_credential,
            "contains_api_key": self.contains_api_key,
            "is_trivial_greeting": self.is_trivial_greeting
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> 'PolicyContext':
        """Create PolicyContext from dict with regex pre-computation"""
        model = data.get("model", "")
        prompt = data.get("prompt", "")
        prompt_length = len(prompt)
        has_attachments = data.get("has_attachments", False)
        attachment_count = data.get("attachment_count", 0)

        # Pre-compute common regex patterns
        contains_confidential = bool(re.search(r'(?i)(confidential|internal only|secret)', prompt))
        contains_injection = bool(re.search(r'(?i)(ignore previous|disregard|forget instructions)', prompt))
        contains_credential = bool(re.search(r'(sk-[a-zA-Z0-9]{20,}|password|api_key)', prompt))

        # Detect AWS or OpenAI API keys
        # OpenAI: sk-[variant]-[base64] where variant can be "proj", "test", or omitted
        # AWS: AKIA[16 uppercase alphanumeric]
        contains_api_key = bool(re.search(r'(AKIA[0-9A-Z]{16}|sk-(?:proj-|test-)?[a-zA-Z0-9]{20,})', prompt))

        # Detect trivial greetings (short prompts with only basic greetings)
        is_trivial_greeting = False
        if prompt_length < 20:
            is_trivial_greeting = bool(re.match(r'^\s*(你好|hello|hi|test|测试)\s*[!?。！？]*\s*$', prompt, re.IGNORECASE))

        return PolicyContext(
            model=model,
            prompt=prompt,
            prompt_length=prompt_length,
            has_attachments=has_attachments,
            attachment_count=attachment_count,
            contains_confidential=contains_confidential,
            contains_injection=contains_injection,
            contains_credential=contains_credential,
            contains_api_key=contains_api_key,
            is_trivial_greeting=is_trivial_greeting
        )


@dataclass
class MaskingContext:
    """Stores bidirectional mapping for masked entities"""
    mask_to_original: Dict[str, str] = field(default_factory=dict)
    counter: Dict[str, int] = field(default_factory=dict)

    def add_mapping(self, entity_type: str, original: str, placeholder_prefix: str) -> str:
        """Create a unique placeholder and store the mapping"""
        if entity_type not in self.counter:
            self.counter[entity_type] = 0
        self.counter[entity_type] += 1

        placeholder = f"{placeholder_prefix}{self.counter[entity_type]}]"
        self.mask_to_original[placeholder] = original
        return placeholder


# ======================== Context Builder ========================

class ContextBuilder:
    """Extract context from request payload for policy evaluation"""

    @staticmethod
    def extract_from_openai_format(payload: Dict[str, Any]) -> PolicyContext:
        """
        Extract context from OpenAI-compatible format

        Payload structure:
        {
            "model": "gpt-4o",
            "messages": [
                {"role": "user", "content": "text"},
                {"role": "user", "content": [{"type": "text", "text": "..."}, {"type": "image_url", "image_url": {...}}]}
            ]
        }
        """
        model = payload.get("model", "")
        messages = payload.get("messages", [])

        # Extract prompt text
        prompt_parts = []
        has_attachments = False
        attachment_count = 0

        for msg in messages:
            content = msg.get("content", "")

            # Handle string content
            if isinstance(content, str):
                prompt_parts.append(content)

            # Handle array content (multimodal)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        item_type = item.get("type", "")

                        if item_type == "text":
                            prompt_parts.append(item.get("text", ""))

                        elif item_type == "image_url":
                            has_attachments = True
                            attachment_count += 1

                        elif item_type in ["file", "audio", "video"]:
                            has_attachments = True
                            attachment_count += 1

        prompt = " ".join(prompt_parts)

        return PolicyContext.from_dict({
            "model": model,
            "prompt": prompt,
            "has_attachments": has_attachments,
            "attachment_count": attachment_count
        })

    @staticmethod
    def extract_from_anthropic_format(payload: Dict[str, Any]) -> PolicyContext:
        """Extract context from Anthropic Claude format"""
        model = payload.get("model", "")
        messages = payload.get("messages", [])
        system = payload.get("system", "")

        prompt_parts = [system] if system else []
        has_attachments = False
        attachment_count = 0

        for msg in messages:
            content = msg.get("content", "")

            if isinstance(content, str):
                prompt_parts.append(content)
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            prompt_parts.append(item.get("text", ""))
                        elif item.get("type") == "image":
                            has_attachments = True
                            attachment_count += 1

        prompt = " ".join(prompt_parts)

        return PolicyContext.from_dict({
            "model": model,
            "prompt": prompt,
            "has_attachments": has_attachments,
            "attachment_count": attachment_count
        })

    @staticmethod
    def extract_context(payload: Dict[str, Any], format_hint: str = "openai") -> PolicyContext:
        """
        Extract context from payload with format auto-detection

        Args:
            payload: Request payload dictionary
            format_hint: Format hint ("openai", "anthropic", "auto")
        """
        if format_hint == "anthropic" or "system" in payload:
            return ContextBuilder.extract_from_anthropic_format(payload)
        else:
            return ContextBuilder.extract_from_openai_format(payload)


# ======================== Generic Policy Engine ========================

class GenericPolicyEngine:
    """
    Expression-based policy evaluation engine
    Uses rule-engine library for safe rule evaluation
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("privacy_guard", {})
        self.enabled = self.config.get("enabled", False)

        # Policy engine
        self.policies_config = self.config.get("policies", {})
        self.policies_enabled = self.policies_config.get("enabled", False)
        self.policies = []

        # Regex audit (legacy support)
        self.regex_audit_config = self.config.get("regex_audit", {})
        self.regex_audit_enabled = self.regex_audit_config.get("enabled", False)
        self.audit_patterns = []

        # Data masking (legacy support)
        self.data_masking_config = self.config.get("data_masking", {})
        self.data_masking_enabled = self.data_masking_config.get("enabled", False)
        self.masking_patterns = []

        # Initialize
        self._compile_policies()
        self._compile_regex_patterns()

    def _compile_policies(self):
        """
        Compile and sort policy rules using rule-engine
        Sorting: By priority (desc), then by action severity (desc)
        """
        if not self.policies_enabled or not rule_engine:
            return

        rules = self.policies_config.get("rules", [])
        compiled_policies = []

        for rule_config in rules:
            try:
                name = rule_config.get("name", "Unnamed Policy")
                condition_str = rule_config.get("condition", "")
                action = rule_config.get("action", {})
                priority = rule_config.get("priority", 0)  # Default priority: 0

                # Compile rule using rule-engine
                compiled_rule = rule_engine.Rule(condition_str)

                # Get action severity for secondary sorting
                action_type = action.get("type", "allow")
                severity = ACTION_SEVERITY_MAP.get(action_type, 0)

                compiled_policies.append({
                    "name": name,
                    "condition": compiled_rule,
                    "action": action,
                    "priority": priority,
                    "severity": severity
                })

                logger.info(f"Compiled policy: {name} (Priority: {priority}, Severity: {severity})")

            except Exception as e:
                logger.error(f"Failed to compile policy '{rule_config.get('name')}': {e}")

        # Sort policies: Higher priority first, then higher severity
        # This ensures that in conflicts, the most important policy wins
        self.policies = sorted(
            compiled_policies,
            key=lambda p: (p["priority"], p["severity"]),
            reverse=True  # Descending order
        )

        # Log sorted order
        if self.policies:
            logger.info("Policy evaluation order (after priority sorting):")
            for idx, policy in enumerate(self.policies, 1):
                logger.info(f"  {idx}. {policy['name']} (Priority: {policy['priority']}, Severity: {policy['severity']})")

    def _compile_regex_patterns(self):
        """Compile regex audit patterns (legacy support)"""
        if not self.regex_audit_enabled:
            return

        for rule in self.regex_audit_config.get("rules", []):
            try:
                compiled = re.compile(rule["pattern"])
                self.audit_patterns.append({
                    "name": rule["name"],
                    "pattern": compiled,
                    "action": rule["action"],
                    "message": rule.get("message", "")
                })
            except re.error as e:
                logger.error(f"Invalid regex in audit rule '{rule['name']}': {e}")

        # Compile masking patterns
        if self.data_masking_enabled:
            for rule in self.data_masking_config.get("rules", []):
                try:
                    compiled = re.compile(rule["pattern"])
                    self.masking_patterns.append({
                        "name": rule["name"],
                        "pattern": compiled,
                        "placeholder_prefix": rule["placeholder_prefix"],
                        "entity_type": rule["entity_type"]
                    })
                except re.error as e:
                    logger.error(f"Invalid regex in masking rule '{rule['name']}': {e}")

    # ======================== Policy Evaluation ========================

    def evaluate_policies(self, context: PolicyContext) -> Optional[Dict[str, Any]]:
        """
        Evaluate policies in priority order with short-circuit evaluation

        Policies are pre-sorted by priority (desc) and severity (desc).
        First matching policy executes and stops evaluation.

        Returns:
            None if no policy matched
            {"action": "block", "message": "...", "policy_name": "...", "priority": ...} if blocked
            {"action": "reroute", "target_provider": "...", "target_model": "...", "policy_name": "...", "priority": ...} if rerouted
        """
        if not self.enabled or not self.policies_enabled or not rule_engine:
            return None

        context_dict = context.to_dict()

        # Short-circuit evaluation: Stop at first match
        for policy in self.policies:
            try:
                # Evaluate rule
                if policy["condition"].evaluate(context_dict):
                    action = policy["action"]
                    action_type = action.get("type", "")
                    policy_name = policy["name"]
                    priority = policy["priority"]

                    # Enhanced audit logging
                    logger.warning(
                        f"[Privacy Guard] Action Taken: {action_type.upper()}. "
                        f"Triggered by Policy: '{policy_name}' (Priority: {priority})"
                    )

                    if action_type == "block":
                        return {
                            "action": "block",
                            "message": action.get("message", "Request blocked by policy"),
                            "policy_name": policy_name,
                            "priority": priority
                        }

                    elif action_type == "log_and_block":
                        # Print red alert to console
                        logger.error(f"\033[91m🚨 SECURITY ALERT: {policy_name} (Priority: {priority})\033[0m")
                        logger.error(f"\033[91m   Message: {action.get('message', 'Policy violation')}\033[0m")
                        logger.error(f"\033[91m   Model: {context.model}, Prompt Length: {context.prompt_length}\033[0m")

                        return {
                            "action": "block",
                            "message": action.get("message", "Request blocked by security policy"),
                            "policy_name": policy_name,
                            "priority": priority
                        }

                    elif action_type == "reroute":
                        logger.info(f"   → Rerouting to: {action.get('target_provider')}/{action.get('target_model')}")

                        return {
                            "action": "reroute",
                            "target_provider": action.get("target_provider", ""),
                            "target_model": action.get("target_model", "preserve"),
                            "policy_name": policy_name,
                            "priority": priority
                        }

                    # Short-circuit: Stop evaluation after first match
                    break

            except Exception as e:
                logger.error(f"Error evaluating policy '{policy['name']}': {e}")
                # Continue to next policy on error

        return None

    # ======================== Legacy Regex Audit (Preserved) ========================

    def audit_request(self, messages: List[Dict[str, str]]) -> None:
        """Legacy regex audit - raises HTTPException if blocked"""
        if not self.enabled or not self.regex_audit_enabled:
            return

        full_text = "\n".join(msg.get("content", "") for msg in messages)

        for audit_rule in self.audit_patterns:
            match = audit_rule["pattern"].search(full_text)
            if match:
                if audit_rule["action"] == "block":
                    logger.error(f"Audit BLOCK: {audit_rule['name']}")
                    raise HTTPException(
                        status_code=400,
                        detail=audit_rule["message"]
                    )
                elif audit_rule["action"] == "log":
                    logger.warning(f"Audit LOG: {audit_rule['name']} - {match.group()[:50]}")

    # ======================== Legacy Data Masking (Preserved) ========================

    def mask_request(self, messages: List[Dict[str, str]]) -> tuple[List[Dict[str, str]], MaskingContext]:
        """Legacy data masking"""
        if not self.enabled or not self.data_masking_enabled:
            return messages, MaskingContext()

        context = MaskingContext()
        masked_messages = []

        for msg in messages:
            content = msg.get("content", "")
            masked_content = self._mask_text(content, context)
            masked_messages.append({**msg, "content": masked_content})

        return masked_messages, context

    def _mask_text(self, text: str, context: MaskingContext) -> str:
        """Apply masking patterns"""
        masked = text
        for rule in self.masking_patterns:
            def replacer(match):
                original = match.group()
                return context.add_mapping(
                    rule["entity_type"],
                    original,
                    rule["placeholder_prefix"]
                )
            masked = rule["pattern"].sub(replacer, masked)
        return masked

    def unmask_response(self, response_text: str, context: MaskingContext) -> str:
        """Unmask response"""
        if not self.enabled or not self.data_masking_enabled:
            return response_text

        unmasked = response_text
        for placeholder, original in context.mask_to_original.items():
            unmasked = unmasked.replace(placeholder, original)
        return unmasked

    async def unmask_streaming_response(
        self,
        stream: AsyncIterator[str],
        context: MaskingContext
    ) -> AsyncIterator[str]:
        """Unmask streaming response"""
        if not self.enabled or not self.data_masking_enabled:
            async for chunk in stream:
                yield chunk
            return

        buffer = ""
        max_placeholder_length = self._get_max_placeholder_length(context)

        async for chunk in stream:
            buffer += chunk

            while len(buffer) > max_placeholder_length:
                earliest_match_pos = len(buffer)
                matched_placeholder = None

                for placeholder in context.mask_to_original.keys():
                    pos = buffer.find(placeholder)
                    if pos != -1 and pos < earliest_match_pos:
                        earliest_match_pos = pos
                        matched_placeholder = placeholder

                if matched_placeholder:
                    if earliest_match_pos > 0:
                        yield buffer[:earliest_match_pos]
                    yield context.mask_to_original[matched_placeholder]
                    buffer = buffer[earliest_match_pos + len(matched_placeholder):]
                else:
                    yield buffer[0]
                    buffer = buffer[1:]

        if buffer:
            for placeholder, original in context.mask_to_original.items():
                buffer = buffer.replace(placeholder, original)
            yield buffer

    def _get_max_placeholder_length(self, context: MaskingContext) -> int:
        """Get max placeholder length for buffer sizing"""
        if not context.mask_to_original:
            return 0
        return max(len(p) for p in context.mask_to_original.keys())


# ======================== Factory ========================

def create_privacy_guard(config: Dict[str, Any]) -> GenericPolicyEngine:
    """Factory function to create privacy guard instance"""
    return GenericPolicyEngine(config)
