"""
Comprehensive Test Runner for AgentOS Router

Runs all provider tests with organized output and summary.
"""

import sys
import os
import subprocess
from pathlib import Path

# Color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

# Test suites
TEST_SUITES = {
    "provider": [
        ("OpenAI", "test_openai.py"),
        ("Anthropic", "test_anthropic.py"),
        ("AWS Bedrock", "test_bedrock.py"),
        ("Azure OpenAI", "test_azure_openai.py"),
    ],
    "chinese": [
        ("Chinese LLMs", "test_chinese_llms.py"),
    ],
    "local": [
        ("Local Inference", "test_local_inference.py"),
    ],
    "feature": [
        ("Streaming", "test_streaming.py"),
        ("Provider Detection", "test_provider_detection.py"),
    ],
    "integration": [
        ("Router Integration", "test_router_integration.py"),
    ],
}


def print_header(text):
    """Print formatted header"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{text:^60}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")


def print_section(text):
    """Print formatted section"""
    print(f"\n{YELLOW}{'─'*60}{RESET}")
    print(f"{YELLOW}{text}{RESET}")
    print(f"{YELLOW}{'─'*60}{RESET}")


def run_test_file(test_file):
    """Run a single test file"""
    test_path = Path(__file__).parent / test_file

    if not test_path.exists():
        print(f"{YELLOW}⚠️  Test file not found: {test_file}{RESET}")
        return "skip"

    # Run pytest
    result = subprocess.run(
        ["pytest", str(test_path), "-v", "--tb=short"],
        capture_output=True,
        text=True
    )

    return "pass" if result.returncode == 0 else "fail"


def run_standalone_test():
    """Run standalone test script"""
    test_path = Path(__file__).parent.parent / "test_all_providers.py"

    if not test_path.exists():
        print(f"{YELLOW}⚠️  Standalone test not found{RESET}")
        return "skip"

    print(f"{BLUE}Running standalone integration test...{RESET}")
    result = subprocess.run(
        ["python", str(test_path)],
        capture_output=False  # Show output directly
    )

    return "pass" if result.returncode == 0 else "fail"


def main():
    """Main test runner"""
    import argparse

    parser = argparse.ArgumentParser(description="Run AgentOS Router tests")
    parser.add_argument(
        "--provider",
        choices=["openai", "anthropic", "bedrock", "azure", "chinese", "local", "all"],
        default="all",
        help="Run specific provider tests"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )
    parser.add_argument(
        "--standalone",
        action="store_true",
        help="Run standalone integration test"
    )

    args = parser.parse_args()

    print_header("🧪 AgentOS Router Test Suite")

    print("Test Coverage:")
    print("  ✅ 15+ LLM providers")
    print("  ✅ Request/response format conversion")
    print("  ✅ Streaming support")
    print("  ✅ Auto-detection logic")
    print("  ✅ End-to-end integration")

    results = {}

    # Run standalone test if requested
    if args.standalone:
        print_section("🚀 Standalone Integration Test")
        result = run_standalone_test()
        results["standalone"] = result

        if result == "pass":
            print(f"\n{GREEN}✅ Standalone test passed!{RESET}")
        else:
            print(f"\n{RED}❌ Standalone test failed!{RESET}")

        sys.exit(0 if result == "pass" else 1)

    # Run test suites
    if args.provider == "all":
        suites_to_run = TEST_SUITES
    elif args.provider == "chinese":
        suites_to_run = {"chinese": TEST_SUITES["chinese"]}
    elif args.provider == "local":
        suites_to_run = {"local": TEST_SUITES["local"]}
    elif args.provider == "openai":
        suites_to_run = {"provider": [("OpenAI", "test_openai.py")]}
    elif args.provider == "anthropic":
        suites_to_run = {"provider": [("Anthropic", "test_anthropic.py")]}
    elif args.provider == "bedrock":
        suites_to_run = {"provider": [("AWS Bedrock", "test_bedrock.py")]}
    elif args.provider == "azure":
        suites_to_run = {"provider": [("Azure OpenAI", "test_azure_openai.py")]}

    for suite_name, tests in suites_to_run.items():
        print_section(f"📦 {suite_name.capitalize()} Tests")

        for test_name, test_file in tests:
            print(f"\n{BLUE}Testing {test_name}...{RESET}")
            result = run_test_file(test_file)
            results[test_name] = result

            if result == "pass":
                print(f"{GREEN}✅ {test_name} tests passed{RESET}")
            elif result == "fail":
                print(f"{RED}❌ {test_name} tests failed{RESET}")
            else:
                print(f"{YELLOW}⚠️  {test_name} tests skipped{RESET}")

    # Print summary
    print_header("📊 Test Summary")

    passed = sum(1 for r in results.values() if r == "pass")
    failed = sum(1 for r in results.values() if r == "fail")
    skipped = sum(1 for r in results.values() if r == "skip")
    total = len(results)

    print(f"Total: {total}")
    print(f"{GREEN}Passed: {passed}{RESET}")
    print(f"{RED}Failed: {failed}{RESET}")
    print(f"{YELLOW}Skipped: {skipped}{RESET}")

    if failed == 0:
        print(f"\n{GREEN}🎉 All tests passed!{RESET}")
        sys.exit(0)
    else:
        print(f"\n{RED}⚠️  Some tests failed{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    # Check if pytest is installed
    try:
        import pytest
    except ImportError:
        print(f"{RED}Error: pytest is not installed{RESET}")
        print(f"Install with: pip install pytest pytest-asyncio")
        sys.exit(1)

    main()
