@echo off
REM ============================================================
REM  30-baseline : pristine checkpoint + full system report
REM  One UAC click. Details: see 30-baseline.ps1 header.
REM ============================================================
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator rights, click YES on the UAC popup...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp030-baseline.ps1"
