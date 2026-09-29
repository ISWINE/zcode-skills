@echo off
REM ============================================================
REM  Lab setup STEP 2 of 2 : create the VM + network + start
REM  install (unattended). Run AFTER the reboot of step 1.
REM  - Needs admin (auto-asks UAC)
REM  - Log: D:\lab\logs\20-create-vm.log
REM ============================================================
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator rights, click YES on the UAC popup...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "D:\lab\20-create-vm.ps1"
