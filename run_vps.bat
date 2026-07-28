@echo off
title Polymarket AI Trading Bot 24/7 VPS Runner
color 0A
echo =========================================================
echo 🚀 Starting Polymarket AI Trading Bot on VPS (24/7)
echo =========================================================
echo 1. Installing Python dependencies...
pip install -r backend/requirements.txt
echo.
echo 2. Launching 24/7 Bitcoin Trading Bot Loop...
python backend/run_vps_247.py
pause
