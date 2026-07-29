"""
==========================================================
POLYMARKET REAL TRADING BOT - VPS 24/7 RUNNER
==========================================================
Jalankan script ini di VPS untuk mengaktifkan bot 24/7.
Bot akan berjalan mandiri setiap 5 menit tanpa GitHub.

Command: python backend/run_vps_247.py
==========================================================
"""
import os
import sys
import time
import subprocess
import traceback
from datetime import datetime

# Path ke main_bot.py
BOT_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main_bot.py")
INTERVAL_SECONDS = 300  # 5 menit
MAX_CONSECUTIVE_ERRORS = 10

consecutive_errors = 0
trade_count_today = 0
session_start = datetime.now()

print("=" * 60)
print("🚀 POLYMARKET REAL TRADING BOT - VPS 24/7 ENGINE")
print(f"📅 Session dimulai: {session_start.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"⏱️  Interval cycle: {INTERVAL_SECONDS // 60} menit")
print(f"📄 Bot script: {BOT_SCRIPT}")
print("=" * 60)
print("\n⚡ Tekan Ctrl+C untuk menghentikan bot dengan aman.\n")

while True:
    cycle_start = datetime.now()
    print(f"\n{'='*50}")
    print(f"🔄 [{cycle_start.strftime('%Y-%m-%d %H:%M:%S')}] Memulai cycle trading...")

    try:
        result = subprocess.run(
            [sys.executable, BOT_SCRIPT],
            check=False,
            timeout=240  # Max 4 menit per cycle, lalu timeout
        )

        if result.returncode == 0:
            consecutive_errors = 0
            trade_count_today += 1
            elapsed = (datetime.now() - cycle_start).seconds
            print(f"✅ Cycle selesai dalam {elapsed} detik.")
        else:
            consecutive_errors += 1
            print(f"⚠️ Cycle selesai dengan error code: {result.returncode}")

    except subprocess.TimeoutExpired:
        consecutive_errors += 1
        print("⏰ Cycle timeout (>4 menit). Dilanjutkan ke cycle berikutnya.")

    except KeyboardInterrupt:
        print("\n\n🛑 Bot dihentikan manual oleh pengguna (Ctrl+C).")
        print(f"📊 Total cycle dijalankan: {trade_count_today}")
        print(f"⏱️  Total waktu berjalan: {(datetime.now() - session_start).seconds // 60} menit")
        sys.exit(0)

    except Exception as e:
        consecutive_errors += 1
        print(f"❌ Error tidak terduga: {e}")
        traceback.print_exc()

    # Safety: hentikan jika error berturut-turut terlalu banyak
    if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
        print(f"\n🚨 [AUTO STOP] {MAX_CONSECUTIVE_ERRORS} error berturut-turut terdeteksi!")
        print("Bot dihentikan otomatis untuk melindungi modal kamu.")
        print("Periksa log error di atas dan perbaiki sebelum menjalankan ulang.")
        sys.exit(1)

    next_run = INTERVAL_SECONDS
    print(f"\n⏳ Cycle berikutnya dalam {next_run // 60} menit {next_run % 60} detik...")
    print(f"   (Tekan Ctrl+C untuk berhenti)")

    try:
        time.sleep(next_run)
    except KeyboardInterrupt:
        print("\n\n🛑 Bot dihentikan manual oleh pengguna (Ctrl+C).")
        sys.exit(0)
