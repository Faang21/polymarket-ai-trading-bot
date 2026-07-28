@echo off
title Polymarket AI Trading Bot 24/7 VPS Runner
color 0A
echo =========================================================
echo 🚀 Starting Polymarket AI Trading Bot on VPS (24/7)
echo =========================================================

set PY_CMD=python
where python >nul 2>nul
if %errorlevel% neq 0 (
  where py >nul 2>nul
  if %errorlevel% equ 0 (
    set PY_CMD=py
  ) else if exist "C:\Python310\python.exe" (
    set PY_CMD="C:\Python310\python.exe"
  ) else if exist "C:\Python311\python.exe" (
    set PY_CMD="C:\Python311\python.exe"
  ) else if exist "C:\Program Files\Python310\python.exe" (
    set PY_CMD="C:\Program Files\Python310\python.exe"
  ) else (
    echo.
    echo ❌ Python belum terinstall di VPS ini!
    echo Harap install Python terlebih dahulu.
    pause
    exit /b 1
  )
)

echo 1. Installing Python dependencies using %PY_CMD%...
%PY_CMD% -m pip install -r backend/requirements.txt
echo.
echo 2. Launching 24/7 Bitcoin Trading Bot Loop...
%PY_CMD% backend/run_vps_247.py
pause
