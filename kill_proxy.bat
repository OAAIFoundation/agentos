@echo off
REM Kill all processes using ports 8801 and 8001

echo ============================================================
echo Killing Router and Dashboard processes
echo ============================================================
echo.

echo Checking port 8801 (Proxy)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8801"') do (
    if not "%%a"=="0" (
        echo   Killing PID %%a
        taskkill /F /PID %%a 2>nul
    )
)

echo.
echo Checking port 8001 (Dashboard)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8001"') do (
    if not "%%a"=="0" (
        echo   Killing PID %%a
        taskkill /F /PID %%a 2>nul
    )
)

echo.
echo ============================================================
echo Done! Ports 8801 and 8001 are now free.
echo ============================================================
echo.
pause
