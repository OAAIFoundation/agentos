@echo off
REM Quick start script for transparent proxy mode
REM Starts both gateway and proxy server

echo ========================================
echo AgentOS - Transparent Proxy Mode
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if gateway.py exists
if not exist "gateway.py" (
    echo ERROR: gateway.py not found. Are you in the correct directory?
    pause
    exit /b 1
)

REM Check if proxy_server.py exists
if not exist "proxy_server.py" (
    echo ERROR: proxy_server.py not found.
    pause
    exit /b 1
)

echo Starting Gateway on port 8000...
echo.
start "Gateway" cmd /k "python gateway.py"

timeout /t 3 /nobreak >nul

echo Starting Transparent Proxy on port 8888...
echo.
start "Proxy" cmd /k "python proxy_server.py"

timeout /t 2 /nobreak >nul

echo.
echo ========================================
echo Services Started!
echo ========================================
echo.
echo Gateway:          http://localhost:8000
echo Dashboard:        http://localhost:8000/dashboard
echo Transparent Proxy: http://localhost:8888
echo.
echo To enable transparent interception, run:
echo.
echo   set HTTP_PROXY=http://localhost:8888
echo   set HTTPS_PROXY=http://localhost:8888
echo.
echo Or in PowerShell:
echo.
echo   $env:HTTP_PROXY="http://localhost:8888"
echo   $env:HTTPS_PROXY="http://localhost:8888"
echo.
echo Press any key to open dashboard...
pause >nul

start http://localhost:8000/dashboard

echo.
echo ========================================
echo Services are running in separate windows.
echo Close those windows to stop the services.
echo ========================================
