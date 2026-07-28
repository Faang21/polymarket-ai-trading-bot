@echo off
title Polymarket AI Trading Bot 24/7 VPS Runner
color 0A
echo =========================================================
echo 🚀 Starting Polymarket AI Trading Bot on VPS (24/7)
echo =========================================================

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
echo 1. Installing Python dependencies (SSL Trusted Host Bypass)...
%PY_CMD% -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org --trusted-host pypi.python.org -r backend/requirements.txt
echo.
echo 2. Launching 24/7 Bitcoin Trading Bot Loop...
%PY_CMD% backend/run_vps_247.py
pause
