"""
Test Suite for Generic Policy Engine
Tests expression-based policy evaluation with rule-engine
"""

import pytest
from fastapi import HTTPException

from privacy_guard import (
    GenericPolicyEngine,
    PolicyContext,
    ContextBuilder,
    create_privacy_guard
)


# ======================== Test Fixtures ========================

@pytest.fixture
def policy_engine_config():
    """Sample configuration with expression-based policies"""
    return {
        "privacy_guard": {
            "enabled": True,
            "policies": {
                "enabled": True,
                "rules": [
                    # Rule 1: Block long prompts
                    {
                        "name": "Block very long prompts",
                        "priority": 90,
                        "condition": "prompt_length > 1000",
                        "action": {
                            "type": "block",
                            "message": "Prompt too long (max 1000 chars)"
                        }
                    },
                    # Rule 2: Block too many attachments (check this BEFORE has_attachments)
                    {
                        "name": "Attachment limit",
                        "priority": 80,
                        "condition": "attachment_count > 3",
                        "action": {
                            "type": "block",
                            "message": "Too many attachments (max 3)"
                        }
                    },
                    # Rule 3: Reroute requests with attachments
                    {
                        "name": "Route vision requests",
                        "priority": 50,
                        "condition": "has_attachments == true",
                        "action": {
                            "type": "reroute",
                            "target_provider": "openai",
                            "target_model": "gpt-4o"
                        }
                    },
                    # Rule 4: Log and block expensive models for short prompts
                    {
                        "name": "Block expensive models for short prompts",
                        "priority": 10,
                        "condition": 'model == "gpt-4" and prompt_length < 50',
                        "action": {
                            "type": "log_and_block",
                            "message": "Using expensive model for trivial prompt"
                        }
                    },
                    # Rule 5: Route confidential content
                    {
                        "name": "Route confidential content",
                        "priority": 40,
                        "condition": "contains_confidential == true",
                        "action": {
                            "type": "reroute",
                            "target_provider": "local_vllm",
                            "target_model": "qwen"
                        }
                    }
                ]
            },
            "regex_audit": {"enabled": False},
            "data_masking": {"enabled": False}
        }
    }


@pytest.fixture
def engine(policy_engine_config):
    """Create policy engine instance"""
    return create_privacy_guard(policy_engine_config)


# ======================== Test 1: Context Builder ========================

def test_context_builder_openai_simple():
    """Test context extraction from simple OpenAI format"""
    payload = {
        "model": "gpt-4o",
        "messages": [
            {"role": "user", "content": "Hello, how are you?"},
            {"role": "assistant", "content": "I'm fine, thanks!"}
        ]
    }

    context = ContextBuilder.extract_context(payload)

    assert context.model == "gpt-4o"
    assert "Hello, how are you?" in context.prompt
    assert "I'm fine, thanks!" in context.prompt
    assert context.prompt_length > 0
    assert context.has_attachments == False
    assert context.attachment_count == 0


def test_context_builder_openai_multimodal():
    """Test context extraction with image attachments"""
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image"},
                    {"type": "image_url", "image_url": {"url": "data:image/png;base64,..."}}
                ]
            }
        ]
    }

    context = ContextBuilder.extract_context(payload)

    assert context.model == "gpt-4o"
    assert "Describe this image" in context.prompt
    assert context.has_attachments == True
    assert context.attachment_count == 1


def test_context_builder_anthropic():
    """Test context extraction from Anthropic format"""
    payload = {
        "model": "claude-3-opus",
        "system": "You are a helpful assistant",
        "messages": [
            {"role": "user", "content": "Hello"}
        ]
    }

    context = ContextBuilder.extract_context(payload, format_hint="anthropic")

    assert context.model == "claude-3-opus"
    assert "You are a helpful assistant" in context.prompt
    assert "Hello" in context.prompt


# ======================== Test 2: Policy Evaluation - Pass ========================

def test_policy_no_match(engine):
    """Test that normal requests pass through"""
    context = PolicyContext(
        model="gpt-4o",
        prompt="Short prompt",
        prompt_length=12,
        has_attachments=False,
        attachment_count=0
    )

    result = engine.evaluate_policies(context)
    assert result is None  # No policy matched


# ======================== Test 3: Policy Evaluation - Block ========================

def test_policy_block_long_prompt(engine):
    """Test blocking long prompts"""
    long_text = "A" * 1500
    context = PolicyContext(
        model="gpt-4o",
        prompt=long_text,
        prompt_length=len(long_text),
        has_attachments=False,
        attachment_count=0
    )

    result = engine.evaluate_policies(context)

    assert result is not None
    assert result["action"] == "block"
    assert "too long" in result["message"].lower()


def test_policy_block_too_many_attachments(engine):
    """Test blocking requests with too many attachments"""
    context = PolicyContext(
        model="gpt-4o",
        prompt="Analyze these images",
        prompt_length=20,
        has_attachments=True,
        attachment_count=5  # Exceeds limit of 3
    )

    result = engine.evaluate_policies(context)

    assert result is not None
    assert result["action"] == "block"
    assert "attachments" in result["message"].lower()


def test_policy_log_and_block(engine):
    """Test log_and_block action"""
    context = PolicyContext(
        model="gpt-4",  # Expensive model
        prompt="Hi",    # Very short prompt
        prompt_length=2,
        has_attachments=False,
        attachment_count=0
    )

    result = engine.evaluate_policies(context)

    assert result is not None
    assert result["action"] == "block"
    assert "expensive" in result["message"].lower()


# ======================== Test 4: Policy Evaluation - Reroute ========================

def test_policy_reroute_attachments(engine):
    """Test rerouting requests with attachments"""
    context = PolicyContext(
        model="gpt-4",
        prompt="Describe this image",
        prompt_length=18,
        has_attachments=True,
        attachment_count=1
    )

    result = engine.evaluate_policies(context)

    assert result is not None
    assert result["action"] == "reroute"
    assert result["target_provider"] == "openai"
    assert result["target_model"] == "gpt-4o"


def test_policy_reroute_confidential(engine):
    """Test rerouting confidential content"""
    context = PolicyContext.from_dict({
        "model": "gpt-4o",
        "prompt": "This is confidential information about project X",
        "has_attachments": False,
        "attachment_count": 0
    })

    result = engine.evaluate_policies(context)

    assert result is not None
    assert result["action"] == "reroute"
    assert result["target_provider"] == "local_vllm"
    assert result["target_model"] == "qwen"


# ======================== Test 5: Policy Order (First Match Wins) ========================

def test_policy_first_match_wins(engine):
    """Test that policies are evaluated in order and first match wins"""
    # This context matches multiple policies:
    # 1. has_attachments (Rule 2)
    # 2. contains_confidential (Rule 4)
    # Should match Rule 2 first (reroute to openai/gpt-4o)
    context = PolicyContext.from_dict({
        "model": "gpt-4o",
        "prompt": "This is confidential. Please analyze this image.",
        "has_attachments": True,
        "attachment_count": 1
    })

    result = engine.evaluate_policies(context)

    assert result is not None
    assert result["action"] == "reroute"
    # Should match Rule 2 (attachments), not Rule 4 (confidential)
    assert result["target_model"] == "gpt-4o"  # Not "qwen"


# ======================== Test 6: Integration Test ========================

def test_integration_context_builder_and_policy(engine):
    """Test full pipeline: build context from payload, evaluate policy"""
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Hi"}  # Very short
        ]
    }

    # Build context
    context = ContextBuilder.extract_context(payload)

    # Evaluate
    result = engine.evaluate_policies(context)

    # Should trigger "expensive model for short prompt" rule
    assert result is not None
    assert result["action"] == "block"


def test_integration_multimodal_reroute(engine):
    """Test rerouting multimodal requests"""
    payload = {
        "model": "gpt-4",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this"},
                    {"type": "image_url", "image_url": {"url": "..."}}
                ]
            }
        ]
    }

    context = ContextBuilder.extract_context(payload)
    result = engine.evaluate_policies(context)

    assert result is not None
    assert result["action"] == "reroute"
    assert result["target_model"] == "gpt-4o"


# ======================== Test 7: Disabled Engine ========================

def test_disabled_engine():
    """Test that disabled engine returns None"""
    config = {
        "privacy_guard": {
            "enabled": False,
            "policies": {"enabled": True, "rules": []}
        }
    }

    engine = create_privacy_guard(config)
    context = PolicyContext("gpt-4", "test", 4, False, 0)

    result = engine.evaluate_policies(context)
    assert result is None


# ======================== Test 8: Invalid Expression Handling ========================

def test_invalid_expression_skipped():
    """Test that invalid expressions are skipped gracefully"""
    config = {
        "privacy_guard": {
            "enabled": True,
            "policies": {
                "enabled": True,
                "rules": [
                    {
                        "name": "Invalid rule",
                        "condition": "invalid syntax here!!!",  # Invalid
                        "action": {"type": "block", "message": "Should not reach"}
                    },
                    {
                        "name": "Valid rule",
                        "condition": "prompt_length > 100",
                        "action": {"type": "block", "message": "Too long"}
                    }
                ]
            }
        }
    }

    engine = create_privacy_guard(config)

    # Should skip invalid rule and evaluate valid one
    context = PolicyContext("gpt-4", "A" * 200, 200, False, 0)
    result = engine.evaluate_policies(context)

    assert result is not None
    assert result["action"] == "block"
    assert result["message"] == "Too long"


# ======================== Run Tests ========================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
