import os
import sys
import time
import subprocess

# Pre-configured Environment Variables for VPS Execution
os.environ["GEMINI_API_KEY"] = "AQ.Ab8RN6Ieg8z8MtM1DyT6Wfg22XHQaAeRwS4avx6-nzWsLrH8cw"
os.environ["PRIVATE_KEY_BURNER"] = "06133b641e505538421c74c5355e19cb497f572dbb233b582972e535c2a0bb19"
os.environ["CLOUDFLARE_KV_URL"] = "https://bot-control.aangcrypto21.workers.dev/status"

print("=========================================================")
print("🚀 Polymarket AI Trading Bot 24/7 VPS Engine Active")
print("Target: Bitcoin (BTC) 5-Minute Up/Down Markets")
print("Execution Loop: Every 300 seconds (5 minutes)")
print("=========================================================")

bot_path = os.path.join(os.path.dirname(__file__), "main_bot.py")

while True:
    try:
        print(f"\n⏰ [{time.strftime('%Y-%m-%d %H:%M:%S')}] Launching 5-minute Bitcoin trading cycle...")
        subprocess.run([sys.executable, bot_path], check=False)
    except Exception as e:
        print(f"⚠️ Error executing main_bot.py: {e}")

    print("\n⏳ Sleeping 300 seconds (5 minutes) until next cycle...")
    time.sleep(300)
