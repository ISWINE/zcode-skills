@echo off
REM ============================================================
REM  Start the lab VM (one double-click, one UAC click).
REM  Needed only until next sign-out/sign-in, after which
REM  "powershell -File D:\lab\lab.ps1 start" works directly.
REM ============================================================
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator rights, click YES on the UAC popup...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0lab.ps1" start
echo.
echo VM booting (~30s), then:  ssh lab
timeout /t 3 >nul
