@echo off
REM ============================================================
REM  Lab setup STEP 1 of 2 : enable Hyper-V (built-in feature)
REM  - Needs admin (auto-asks UAC) and ONE reboot
REM  - Log: <script dir>\logs\10-dism.log
REM ============================================================
if not exist "%~dp0logs" mkdir "%~dp0logs"
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator rights, click YES on the UAC popup...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo === Lab step 1/2 : enable Hyper-V (built-in Windows feature) ===
echo Nothing third-party is installed. C-drive impact: Windows feature
echo payload only (a few hundred MB inside C:\Windows, unavoidable for
echo any virtualization option, WSL included).
echo.

dism /online /enable-feature /featurename:Microsoft-Hyper-V-All /all /norestart >"%~dp0logs\10-dism.log" 2>&1
set RC=%errorlevel%
if "%RC%"=="0" goto ok
if "%RC%"=="3010" goto ok
echo.
echo FAILED, exit code %RC%. See %~dp0logs\10-dism.log
pause
exit /b 1

:ok
echo [OK] Hyper-V feature enabled. Log: %~dp0logs\10-dism.log
echo.

REM --- one-shot task chaining: after reboot, continue setup automatically ---
REM (RunOnce self-deletes after running; the personal-machine equivalent
REM  of enterprise task sequencing / MDT chaining)
choice /C YN /M "Auto-continue step 2 after reboot (one UAC click later) (Y) or manual (N)"
if %errorlevel%==2 goto nocontinue
reg add "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce" /v LabSetup /t REG_SZ /d "%~dp020-run.bat" /f >nul
echo [OK] After reboot and sign-in, step 2 starts automatically
echo      (it will ask one UAC click; the RunOnce entry deletes itself).
goto askreboot

:nocontinue
echo [OK] Manual mode. After reboot run:  %~dp020-run.bat

:askreboot
echo.
echo === ONE REBOOT IS REQUIRED to activate Hyper-V ===
choice /C YN /M "Reboot now (Y) or later (N)"
if %errorlevel%==2 goto later
shutdown /r /t 10 /c "Lab setup: reboot to activate Hyper-V. After sign-in, setup continues automatically."
echo Rebooting in 10 seconds...
pause
exit /b 0

:later
echo OK. Reboot whenever you want.
pause
