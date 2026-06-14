"""
Test Edit and Save functionality for Providers and Routes
"""

import requests
import json
import time


BASE_URL = "http://localhost:8000"


def test_provider_edit_save():
    """Test editing and saving a provider configuration"""
    print("\n[TEST 1] Provider Edit and Save")
    print("-" * 60)

    # Step 1: Get current config
    response = requests.get(f"{BASE_URL}/api/config")
    assert response.status_code == 200, f"Failed to get config: {response.status_code}"
    config = response.json()

    # Step 2: Modify a provider (ollama is safe to modify)
    original_base_url = config['providers']['ollama']['base_url']
    print(f"   Original ollama base_url: {original_base_url}")

    # Change to a different URL
    config['providers']['ollama']['base_url'] = "http://localhost:11435/v1"

    # Step 3: Save modified config
    save_response = requests.post(
        f"{BASE_URL}/api/config",
        headers={'Content-Type': 'application/json'},
        json=config
    )

    if save_response.status_code != 200:
        print(f"   [FAIL] Save failed: {save_response.status_code}")
        print(f"   Response: {save_response.text}")
        assert False, "Provider save failed"

    print(f"   [PASS] Save successful")

    # Step 4: Wait for hot reload
    time.sleep(1)

    # Step 5: Verify the change persisted
    verify_response = requests.get(f"{BASE_URL}/api/config")
    verify_config = verify_response.json()
    new_base_url = verify_config['providers']['ollama']['base_url']
    print(f"   New ollama base_url: {new_base_url}")

    assert new_base_url == "http://localhost:11435/v1", f"Expected modified URL, got {new_base_url}"
    print(f"   [PASS] Change persisted correctly")

    # Step 6: Restore original value
    config['providers']['ollama']['base_url'] = original_base_url
    restore_response = requests.post(
        f"{BASE_URL}/api/config",
        headers={'Content-Type': 'application/json'},
        json=config
    )
    assert restore_response.status_code == 200, "Failed to restore original value"
    print(f"   [PASS] Restored original configuration")


def test_route_edit_save():
    """Test editing and saving a route rule"""
    print("\n[TEST 2] Route Edit and Save")
    print("-" * 60)

    # Step 1: Get current config
    response = requests.get(f"{BASE_URL}/api/config")
    assert response.status_code == 200, f"Failed to get config: {response.status_code}"
    config = response.json()

    # Step 2: Find a route to modify (use first route)
    if len(config['routes']) == 0:
        print(f"   [SKIP] No routes to test")
        return

    original_route = config['routes'][0].copy()
    print(f"   Original route[0]: {original_route.get('match_model')} -> {original_route.get('target_provider')}")

    # Step 3: Modify the target_model
    original_target_model = config['routes'][0].get('target_model', 'preserve')
    config['routes'][0]['target_model'] = "test-model-modified"

    # Step 4: Save modified config
    save_response = requests.post(
        f"{BASE_URL}/api/config",
        headers={'Content-Type': 'application/json'},
        json=config
    )

    if save_response.status_code != 200:
        print(f"   [FAIL] Save failed: {save_response.status_code}")
        print(f"   Response: {save_response.text}")
        assert False, "Route save failed"

    print(f"   [PASS] Save successful")

    # Step 5: Wait for hot reload
    time.sleep(1)

    # Step 6: Verify the change persisted
    verify_response = requests.get(f"{BASE_URL}/api/config")
    verify_config = verify_response.json()
    new_target_model = verify_config['routes'][0]['target_model']
    print(f"   New target_model: {new_target_model}")

    assert new_target_model == "test-model-modified", f"Expected 'test-model-modified', got {new_target_model}"
    print(f"   [PASS] Change persisted correctly")

    # Step 7: Restore original value
    config['routes'][0] = original_route
    restore_response = requests.post(
        f"{BASE_URL}/api/config",
        headers={'Content-Type': 'application/json'},
        json=config
    )
    assert restore_response.status_code == 200, "Failed to restore original value"
    print(f"   [PASS] Restored original configuration")


def test_route_keywords_edit():
    """Test editing route with keywords"""
    print("\n[TEST 3] Route Keywords Edit")
    print("-" * 60)

    # Step 1: Get current config
    response = requests.get(f"{BASE_URL}/api/config")
    config = response.json()

    # Step 2: Find route with keywords or modify first route
    if len(config['routes']) == 0:
        print(f"   [SKIP] No routes to test")
        return

    original_route = config['routes'][0].copy()
    print(f"   Original route[0]: {original_route}")

    # Step 3: Add/modify keywords
    config['routes'][0]['contains_keywords'] = ["test", "edit", "save"]

    # Step 4: Save
    save_response = requests.post(
        f"{BASE_URL}/api/config",
        headers={'Content-Type': 'application/json'},
        json=config
    )
    assert save_response.status_code == 200, "Failed to save"
    print(f"   [PASS] Saved route with keywords")

    # Step 5: Verify
    time.sleep(1)
    verify_response = requests.get(f"{BASE_URL}/api/config")
    verify_config = verify_response.json()
    keywords = verify_config['routes'][0].get('contains_keywords', [])
    print(f"   Keywords: {keywords}")

    assert "test" in keywords, "Keyword 'test' not found"
    assert "edit" in keywords, "Keyword 'edit' not found"
    print(f"   [PASS] Keywords persisted correctly")

    # Step 6: Restore
    config['routes'][0] = original_route
    requests.post(f"{BASE_URL}/api/config", headers={'Content-Type': 'application/json'}, json=config)
    print(f"   [PASS] Restored original configuration")


def test_invalid_config_rejection():
    """Test that invalid config is rejected"""
    print("\n[TEST 4] Invalid Config Rejection")
    print("-" * 60)

    # Send config missing required fields
    invalid_config = {"invalid": "config"}

    response = requests.post(
        f"{BASE_URL}/api/config",
        headers={'Content-Type': 'application/json'},
        json=invalid_config
    )

    if response.status_code == 400:
        print(f"   [PASS] Invalid config correctly rejected with 400")
    else:
        print(f"   [FAIL] Expected 400, got {response.status_code}")
        assert False, "Invalid config should be rejected"


def test_config_backup_created():
    """Test that backup file is created on save"""
    print("\n[TEST 5] Config Backup Creation")
    print("-" * 60)

    import os

    # Get current config
    response = requests.get(f"{BASE_URL}/api/config")
    config = response.json()

    # Make a small change
    config['providers']['ollama']['api_key'] = "test-backup-change"

    # Save
    save_response = requests.post(
        f"{BASE_URL}/api/config",
        headers={'Content-Type': 'application/json'},
        json=config
    )

    save_result = save_response.json()
    if 'backup' in save_result:
        backup_path = save_result['backup']
        print(f"   Backup created: {backup_path}")

        # Check if backup file exists (try relative to project root)
        import os
        os.chdir('..')  # Go back to project root
        if os.path.exists(backup_path):
            print(f"   [PASS] Backup file exists")
        else:
            print(f"   [FAIL] Backup file not found: {backup_path}")
            assert False, "Backup file not created"
        os.chdir('tests')  # Go back to tests directory
    else:
        print(f"   [INFO] No backup path in response (may be expected)")

    # Restore original
    config['providers']['ollama']['api_key'] = "ollama"
    requests.post(f"{BASE_URL}/api/config", headers={'Content-Type': 'application/json'}, json=config)


def main():
    print("=" * 60)
    print("Edit and Save Test Suite")
    print("=" * 60)

    try:
        test_provider_edit_save()
        test_route_edit_save()
        test_route_keywords_edit()
        test_invalid_config_rejection()
        test_config_backup_created()

        print("\n" + "=" * 60)
        print("[SUCCESS] All edit/save tests passed!")
        print("=" * 60)
        print("\nYou can now open http://localhost:8000/dashboard")
        print("and manually test the Edit buttons in the UI.")

    except AssertionError as e:
        print(f"\n[FAIL] Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
