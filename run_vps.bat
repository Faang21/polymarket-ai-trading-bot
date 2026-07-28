@echo off
title Polymarket AI Trading Bot 24/7 VPS Runner
color 0A
echo =========================================================
echo 🚀 Starting Polymarket AI Trading Bot on VPS (24/7)
echo =========================================================

echo 0. Synchronizing VPS System Clock to Real Time...
net start w32time >nul 2>nul
w32tm /resync /force >nul 2>nul

set PY_CMD=python

where python >nul 2>nul
if %errorlevel% equ 0 (
  set PY_CMD=python
) else if exist "C:\Program Files\Python310\python.exe" (
  set PY_CMD="C:\Program Files\Python310\python.exe"
) else if exist "C:\Program Files\Python311\python.exe" (
  set PY_CMD="C:\Program Files\Python311\python.exe"
) else if exist "C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe" (
  set PY_CMD="C:\Users\Administrator\AppData\Local\Programs\Python\Python310\python.exe"
) else if exist "C:\Python310\python.exe" (
  set PY_CMD="C:\Python310\python.exe"
) else (
  where py >nul 2>nul
  if %errorlevel% equ 0 (
    set PY_CMD=py
  ) else (
    echo.
    echo ❌ Python belum terdeteksi. Buka jendela CMD BARU!
    pause
    exit /b 1
  )
)

echo Python Detected: %PY_CMD%
echo.
echo 1. Upgrading pip & installing core packages...
%PY_CMD% -m pip install --upgrade pip --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org
%PY_CMD% -m pip install requests google-genai pandas eth-account httpx --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org
%PY_CMD% -m pip install py-polymarket-client --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org
echo.
echo 2. Launching 24/7 Bitcoin Trading Bot Loop (Every 60s)...
%PY_CMD% backend/run_vps_247.py
pause
