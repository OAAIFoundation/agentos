"""
Test Suite for Priority-based Policy Arbitration
Tests conflict resolution when multiple policies match
"""

import pytest
from privacy_guard import (
    GenericPolicyEngine,
    PolicyContext,
    ContextBuilder,
    create_privacy_guard,
    ACTION_SEVERITY_MAP
)


# ======================== Test Fixtures ========================

@pytest.fixture
def conflict_scenario_config():
    """Configuration with intentional policy conflicts"""
    return {
        "privacy_guard": {
            "enabled": True,
            "policies": {
                "enabled": True,
                "rules": [
                    # Rule A: Lower priority reroute
                    {
                        "name": "Confidential Reroute",
                        "priority": 10,
                        "condition": "contains_confidential == true",
                        "action": {
                            "type": "reroute",
                            "target_provider": "local_vllm",
                            "target_model": "qwen"
                        }
                    },
                    # Rule B: Higher priority block (should win)
                    {
                        "name": "Block Source Code Leaks",
                        "priority": 100,
                        "condition": "contains_confidential == true",
                        "action": {
                            "type": "block",
                            "message": "Source code leak detected"
                        }
                    },
                    # Rule C: Same priority as A, but block > reroute in severity
                    {
                        "name": "Credential Block",
                        "priority": 10,
                        "condition": "contains_credential == true",
                        "action": {
                            "type": "block",
                            "message": "Credential detected"
                        }
                    },
                    # Rule D: Same priority as C, reroute (lower severity)
                    {
                        "name": "Credential Reroute",
                        "priority": 10,
                        "condition": "contains_credential == true",
                        "action": {
                            "type": "reroute",
                            "target_provider": "secure_provider",
                            "target_model": "secure_model"
                        }
                    }
                ]
            },
            "regex_audit": {"enabled": False},
            "data_masking": {"enabled": False}
        }
    }


@pytest.fixture
def engine(conflict_scenario_config):
    """Create policy engine with conflict scenarios"""
    return create_privacy_guard(conflict_scenario_config)


# ======================== Test 1: Priority Wins ========================

def test_higher_priority_wins(engine):
    """
    Test that higher priority policy wins in conflict
    Both Rule A (priority 10) and Rule B (priority 100) match,
    but Rule B should execute because priority 100 > 10
    """
    context = PolicyContext.from_dict({
        "model": "gpt-4o",
        "prompt": "This is confidential source code",  # Triggers contains_confidential
        "has_attachments": False,
        "attachment_count": 0
    })

    result = engine.evaluate_policies(context)

    # Should execute Rule B (block) not Rule A (reroute)
    assert result is not None
    assert result["action"] == "block"
    assert result["policy_name"] == "Block Source Code Leaks"
    assert result["priority"] == 100
    assert "Source code leak" in result["message"]


def test_lower_priority_ignored(engine):
    """
    Test that lower priority policy is never evaluated when higher priority matches
    """
    context = PolicyContext.from_dict({
        "model": "gpt-4o",
        "prompt": "This is confidential information",
        "has_attachments": False,
        "attachment_count": 0
    })

    result = engine.evaluate_policies(context)

    # Should NOT be reroute (Rule A), should be block (Rule B)
    assert result["action"] == "block"
    assert result["priority"] == 100
    # Verify it's NOT the reroute action
    assert "target_provider" not in result or result.get("target_provider") != "local_vllm"


# ======================== Test 2: Severity Wins When Priority Equal ========================

def test_severity_breaks_tie_when_priority_equal(engine):
    """
    Test that action severity resolves conflicts when priorities are equal
    Rule C (block, priority 10) vs Rule D (reroute, priority 10)
    Block (severity 100) > Reroute (severity 50)
    """
    context = PolicyContext.from_dict({
        "model": "gpt-4o",
        "prompt": "My password is abc123",  # Only triggers contains_credential
        "has_attachments": False,
        "attachment_count": 0
    })

    result = engine.evaluate_policies(context)

    # Should execute Rule C (block) because block severity > reroute severity
    assert result is not None
    assert result["action"] == "block"
    assert result["policy_name"] == "Credential Block"
    assert result["priority"] == 10
    assert "Credential detected" in result["message"]


def test_policy_sorting_order(engine):
    """Test that policies are correctly sorted by priority then severity"""
    # Check that policies are in correct order
    assert len(engine.policies) == 4

    # Policy order should be:
    # 1. Block Source Code Leaks (priority 100, severity 100)
    # 2. Credential Block (priority 10, severity 100)
    # 3. Confidential Reroute (priority 10, severity 50)
    # 4. Credential Reroute (priority 10, severity 50)

    assert engine.policies[0]["name"] == "Block Source Code Leaks"
    assert engine.policies[0]["priority"] == 100

    # Among priority 10 policies, block (severity 100) comes before reroute (severity 50)
    priority_10_policies = [p for p in engine.policies if p["priority"] == 10]
    assert len(priority_10_policies) == 3

    # First priority-10 policy should be a block (highest severity)
    assert priority_10_policies[0]["action"]["type"] == "block"


# ======================== Test 3: Short-Circuit Evaluation ========================

def test_short_circuit_evaluation(engine):
    """
    Test that evaluation stops after first match (short-circuit)
    Even if multiple policies would match, only the first is executed
    """
    # This context triggers both confidential and credential patterns
    # But we can only verify that the FIRST matching policy executes
    context = PolicyContext.from_dict({
        "model": "gpt-4o",
        "prompt": "This confidential code contains password: secret123",
        "has_attachments": False,
        "attachment_count": 0
    })

    result = engine.evaluate_policies(context)

    # Should execute the HIGHEST priority policy that matches
    assert result is not None
    assert result["policy_name"] == "Block Source Code Leaks"  # Priority 100
    assert result["priority"] == 100


# ======================== Test 4: No Match Scenario ========================

def test_no_policy_matches(engine):
    """Test that None is returned when no policies match"""
    context = PolicyContext.from_dict({
        "model": "gpt-4o",
        "prompt": "This is a normal, safe prompt",  # No triggers
        "has_attachments": False,
        "attachment_count": 0
    })

    result = engine.evaluate_policies(context)
    assert result is None


# ======================== Test 5: Action Severity Map ========================

def test_action_severity_map():
    """Test that severity map has correct ordering"""
    assert ACTION_SEVERITY_MAP["block"] > ACTION_SEVERITY_MAP["log_and_block"]
    assert ACTION_SEVERITY_MAP["log_and_block"] > ACTION_SEVERITY_MAP["reroute"]
    assert ACTION_SEVERITY_MAP["reroute"] > ACTION_SEVERITY_MAP["allow"]


# ======================== Test 6: Integration Test ========================

def test_integration_priority_with_context_builder(engine):
    """Test full pipeline: build context from payload, evaluate with priority"""
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "user", "content": "Share this confidential document"}
        ]
    }

    context = ContextBuilder.extract_context(payload)
    result = engine.evaluate_policies(context)

    # Should trigger highest priority confidential policy
    assert result is not None
    assert result["action"] == "block"
    assert result["priority"] == 100


# ======================== Test 7: Default Priority ========================

def test_default_priority_zero():
    """Test that policies without priority field default to 0"""
    config = {
        "privacy_guard": {
            "enabled": True,
            "policies": {
                "enabled": True,
                "rules": [
                    {
                        "name": "No Priority Specified",
                        # No priority field
                        "condition": "prompt_length > 100",
                        "action": {
                            "type": "block",
                            "message": "Too long"
                        }
                    }
                ]
            }
        }
    }

    engine = create_privacy_guard(config)

    # Should have default priority 0
    assert engine.policies[0]["priority"] == 0


# ======================== Run Tests ========================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
