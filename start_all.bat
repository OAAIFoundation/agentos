@echo off
REM Smart startup script - checks ports and starts both services

echo ============================================================
echo Smart Router Startup
echo ============================================================
echo.

REM Check if ports are in use
echo [1/4] Checking ports...

set PROXY_IN_USE=0
set DASHBOARD_IN_USE=0

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8801" ^| findstr "LISTENING"') do (
    if not "%%a"=="0" set PROXY_IN_USE=1
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8001" ^| findstr "LISTENING"') do (
    if not "%%a"=="0" set DASHBOARD_IN_USE=1
)

if %PROXY_IN_USE%==1 (
    echo   [!] Port 8801 is in use
    echo   [*] Run kill_proxy.bat first, or press Ctrl+C to exit
    pause
    exit /b 1
)

if %DASHBOARD_IN_USE%==1 (
    echo   [!] Port 8001 is in use
    echo   [*] Run kill_proxy.bat first, or press Ctrl+C to exit
    pause
    exit /b 1
)

echo   [OK] Ports 8801 and 8001 are free
echo.

REM Start Proxy in new window
echo [2/4] Starting Proxy (port 8801)...
start "Router Proxy" cmd /k python start_proxy.py
timeout /t 3 /nobreak >nul

REM Start Dashboard in new window
echo [3/4] Starting Dashboard (port 8001)...
start "Router Dashboard" cmd /k python start_router.py
timeout /t 2 /nobreak >nul

echo.
echo [4/4] Services started!
echo.
echo ============================================================
echo Router System Running
echo ============================================================
echo.
echo   Proxy:     http://localhost:8801 (2 windows opened)
echo   Dashboard: http://localhost:8001/dashboard
echo.
echo ============================================================
echo.
echo Next steps:
echo   1. Configure VS Code proxy: http://localhost:8801
echo   2. Restart VS Code
echo   3. Send a message in Claude Code
echo   4. Check Dashboard at: http://localhost:8001/dashboard
echo.
echo To stop: Close both "Router Proxy" and "Router Dashboard" windows
echo          Or run: kill_proxy.bat
echo.
echo ============================================================
echo.

REM Open Dashboard in browser
echo Opening Dashboard in browser...
timeout /t 2 /nobreak >nul
start http://localhost:8001/dashboard

echo.
pause
