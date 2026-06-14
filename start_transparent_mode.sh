#!/bin/bash
# Quick start script for transparent proxy mode
# Starts both gateway and proxy server

echo "========================================"
echo "AgentOS - Transparent Proxy Mode"
echo "========================================"
echo ""

# Check if Python is available
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "ERROR: Python is not installed or not in PATH"
    exit 1
fi

PYTHON_CMD="python3"
if ! command -v python3 &> /dev/null; then
    PYTHON_CMD="python"
fi

# Check if gateway.py exists
if [ ! -f "gateway.py" ]; then
    echo "ERROR: gateway.py not found. Are you in the correct directory?"
    exit 1
fi

# Check if proxy_server.py exists
if [ ! -f "proxy_server.py" ]; then
    echo "ERROR: proxy_server.py not found."
    exit 1
fi

echo "Starting Gateway on port 8000..."
echo ""
$PYTHON_CMD gateway.py &
GATEWAY_PID=$!

sleep 3

echo "Starting Transparent Proxy on port 8888..."
echo ""
$PYTHON_CMD proxy_server.py &
PROXY_PID=$!

sleep 2

echo ""
echo "========================================"
echo "Services Started!"
echo "========================================"
echo ""
echo "Gateway:           http://localhost:8000"
echo "Dashboard:         http://localhost:8000/dashboard"
echo "Transparent Proxy: http://localhost:8888"
echo ""
echo "Gateway PID:  $GATEWAY_PID"
echo "Proxy PID:    $PROXY_PID"
echo ""
echo "To enable transparent interception, run:"
echo ""
echo "  export HTTP_PROXY=http://localhost:8888"
echo "  export HTTPS_PROXY=http://localhost:8888"
echo ""
echo "To stop services:"
echo "  kill $GATEWAY_PID $PROXY_PID"
echo ""
echo "Press Ctrl+C to stop all services..."

# Trap Ctrl+C and kill both processes
trap "echo ''; echo 'Stopping services...'; kill $GATEWAY_PID $PROXY_PID 2>/dev/null; exit" SIGINT SIGTERM

# Wait for processes
wait
