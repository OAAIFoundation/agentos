#!/bin/bash

# LLM Routing Gateway Test Script
# This script tests various routing scenarios

GATEWAY_URL="http://localhost:8000"
AUTH_HEADER="Authorization: Bearer dummy"

echo "================================================"
echo "LLM Routing Gateway Test Suite"
echo "================================================"
echo ""

# Test 1: Health check
echo "Test 1: Health Check"
echo "-------------------"
curl -s $GATEWAY_URL | jq .
echo ""
echo ""

# Test 2: Basic routing (gpt-4o without keywords -> should route based on config)
echo "Test 2: Basic Routing (gpt-4o without keywords)"
echo "-----------------------------------------------"
curl -s -X POST $GATEWAY_URL/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "$AUTH_HEADER" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Hello, how are you?"}],
    "stream": false
  }' | jq .
echo ""
echo ""

# Test 3: Keyword-based routing (gpt-4o with "translate" keyword)
echo "Test 3: Keyword-Based Routing (gpt-4o with translate)"
echo "-----------------------------------------------------"
curl -s -X POST $GATEWAY_URL/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "$AUTH_HEADER" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "Please translate this text to French"}],
    "stream": false
  }' | jq .
echo ""
echo ""

# Test 4: Wildcard routing (gpt-4-turbo)
echo "Test 4: Wildcard Routing (gpt-4-turbo)"
echo "--------------------------------------"
curl -s -X POST $GATEWAY_URL/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "$AUTH_HEADER" \
  -d '{
    "model": "gpt-4-turbo",
    "messages": [{"role": "user", "content": "What is the weather?"}],
    "stream": false
  }' | jq .
echo ""
echo ""

# Test 5: Streaming test
echo "Test 5: Streaming Response"
echo "-------------------------"
curl -s -X POST $GATEWAY_URL/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "$AUTH_HEADER" \
  -d '{
    "model": "gpt-3.5-turbo",
    "messages": [{"role": "user", "content": "Count from 1 to 3"}],
    "stream": true
  }'
echo ""
echo ""

# Test 6: Config reload
echo "Test 6: Manual Config Reload"
echo "----------------------------"
curl -s -X POST $GATEWAY_URL/reload | jq .
echo ""
echo ""

echo "================================================"
echo "Test Suite Completed"
echo "================================================"
