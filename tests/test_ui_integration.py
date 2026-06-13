"""
Test UI Integration - Verify Web UI and Backend API alignment
"""

import requests
import json


BASE_URL = "http://localhost:8000"


def test_config_api():
    """Test that /api/config returns correct structure"""
    print("\n[TEST 1] GET /api/config - Structure Validation")
    print("-" * 60)

    response = requests.get(f"{BASE_URL}/api/config")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    config = response.json()

    # Check top-level structure
    assert "providers" in config, "Missing 'providers' key"
    assert "routes" in config, "Missing 'routes' key"
    assert "privacy_guard" in config, "Missing 'privacy_guard' key"

    # Check privacy_guard structure
    pg = config["privacy_guard"]
    assert "enabled" in pg, "Missing 'privacy_guard.enabled'"
    assert "policies" in pg, "Missing 'privacy_guard.policies'"
    assert "rules" in pg["policies"], "Missing 'privacy_guard.policies.rules'"

    policies = pg["policies"]["rules"]
    print(f"   - Found {len(policies)} policies")

    # Validate each policy has required fields
    for i, policy in enumerate(policies):
        assert "name" in policy, f"Policy {i} missing 'name'"
        assert "priority" in policy, f"Policy {i} missing 'priority'"
        assert "condition" in policy, f"Policy {i} missing 'condition'"
        assert "action" in policy, f"Policy {i} missing 'action'"

        # Check priority is integer
        assert isinstance(policy["priority"], int), f"Policy {i} priority is not int: {type(policy['priority'])}"

        # Check action is object
        assert isinstance(policy["action"], dict), f"Policy {i} action is not dict"
        assert "type" in policy["action"], f"Policy {i} action missing 'type'"

        print(f"   - Policy {i+1}: {policy['name']} (Priority: {policy['priority']}, Action: {policy['action']['type']})")

    print("   [PASS] Config structure is valid")


def test_baseline_policies_present():
    """Test that core baseline policies are present"""
    print("\n[TEST 2] Baseline Policies Presence")
    print("-" * 60)

    response = requests.get(f"{BASE_URL}/api/config")
    config = response.json()
    policies = config["privacy_guard"]["policies"]["rules"]

    # Core baseline policies that should always be enabled
    baseline_names = [
        "Prevent_Cost_Blowout",
        "Prevent_Prompt_Injection",
        "Block_API_Keys"
    ]

    policy_names = [p["name"] for p in policies]

    for baseline in baseline_names:
        if baseline in policy_names:
            print(f"   [PASS] Found: {baseline}")
        else:
            print(f"   [FAIL] Missing: {baseline}")
            assert False, f"Baseline policy missing: {baseline}"

    print(f"   [PASS] All {len(baseline_names)} core baseline policies present")


def test_priority_data_type():
    """Test that priority fields are integers (not strings)"""
    print("\n[TEST 3] Priority Data Type Validation")
    print("-" * 60)

    response = requests.get(f"{BASE_URL}/api/config")
    config = response.json()
    policies = config["privacy_guard"]["policies"]["rules"]

    for i, policy in enumerate(policies):
        priority = policy.get("priority", 0)
        print(f"   - Policy '{policy['name']}': priority = {priority} (type: {type(priority).__name__})")

        assert isinstance(priority, int), f"Priority must be int, got {type(priority)} for policy {policy['name']}"

    print(f"   [PASS] All priorities are integers")


def test_action_structure():
    """Test that action field is correctly structured as object"""
    print("\n[TEST 4] Action Structure Validation")
    print("-" * 60)

    response = requests.get(f"{BASE_URL}/api/config")
    config = response.json()
    policies = config["privacy_guard"]["policies"]["rules"]

    for policy in policies:
        action = policy["action"]

        # Action must be dict
        assert isinstance(action, dict), f"Action must be dict, got {type(action)} for {policy['name']}"

        # Action must have type
        assert "type" in action, f"Action missing 'type' for {policy['name']}"
        action_type = action["type"]

        print(f"   - {policy['name']}: action.type = {action_type}")

        # Validate action-specific fields
        if action_type in ["block", "log_and_block"]:
            assert "message" in action, f"Block action missing 'message' for {policy['name']}"
        elif action_type == "reroute":
            assert "target_provider" in action, f"Reroute action missing 'target_provider' for {policy['name']}"
            assert "target_model" in action, f"Reroute action missing 'target_model' for {policy['name']}"

    print(f"   [PASS] All action structures are valid")


def test_reload_api():
    """Test that /api/reload endpoint works"""
    print("\n[TEST 5] POST /api/reload - Hot Reload")
    print("-" * 60)

    response = requests.post(f"{BASE_URL}/api/reload")

    if response.status_code == 200:
        result = response.json()
        print(f"   [PASS] Reload successful: {result}")
    else:
        print(f"   [FAIL] Reload failed with status {response.status_code}")
        assert False, f"Reload API returned {response.status_code}"


def test_priority_sorting():
    """Test that policies can be sorted by priority"""
    print("\n[TEST 6] Priority Sorting Logic")
    print("-" * 60)

    response = requests.get(f"{BASE_URL}/api/config")
    config = response.json()
    policies = config["privacy_guard"]["policies"]["rules"]

    # Extract priorities
    priorities = [p.get("priority", 0) for p in policies]
    print(f"   - Current order: {priorities}")

    # Check if already sorted (descending)
    sorted_priorities = sorted(priorities, reverse=True)
    print(f"   - Expected order: {sorted_priorities}")

    if priorities == sorted_priorities:
        print(f"   [PASS] Policies are already sorted by priority (desc)")
    else:
        print(f"   [INFO] Policies not sorted, but UI should handle sorting")


def main():
    print("=" * 60)
    print("UI Integration Test Suite")
    print("=" * 60)

    try:
        test_config_api()
        test_baseline_policies_present()
        test_priority_data_type()
        test_action_structure()
        test_reload_api()
        test_priority_sorting()

        print("\n" + "=" * 60)
        print("[SUCCESS] All UI integration tests passed!")
        print("=" * 60)
        print(f"\nWeb Dashboard URL: {BASE_URL}/dashboard")
        print("You can now open this URL in your browser to test the UI.")

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
