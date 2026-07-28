import os
import sys
import time
import json
import csv
import requests
from datetime import datetime, timezone

# Try importing Google GenAI SDK (google-genai)
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    print("[WARNING] Package 'google-genai' is not installed or available.")

# Configuration & Constants
CLOUDFLARE_KV_URL = os.environ.get("CLOUDFLARE_KV_URL", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
PRIVATE_KEY_BURNER = os.environ.get("PRIVATE_KEY_BURNER", "")
CSV_FILENAME = "catatan_simulasi_polymarket.csv"
POLYMARKET_GAMMA_URL = "https://gamma-api.polymarket.com/events?closed=false&limit=10"


def step_1_check_emergency_switch():
    """Step 1: Check Cloudflare KV Switch Status before execution."""
    print("--- [STEP 1] Checking Emergency Switch Status ---")
    if not CLOUDFLARE_KV_URL:
        print("[INFO] CLOUDFLARE_KV_URL environment variable is not set. Defaulting to RUNNING.")
        return

    try:
        response = requests.get(CLOUDFLARE_KV_URL, timeout=10)
        if response.status_code == 200:
            data = response.json()
            status = str(data.get("status") or data.get("bot_status") or "RUNNING").upper()
            print(f"[SWITCH STATUS] Cloudflare KV Switch returned: {status}")
            if status == "STOPPED":
                print("🚨 [EMERGENCY STOP] Saklar Bot dalam posisi STOPPED! Menghentikan eksekusi bot segera.")
                sys.exit(0)
        else:
            print(f"[WARNING] Cloudflare KV HTTP status: {response.status_code}. Continuing run...")
    except Exception as e:
        print(f"[WARNING] Error contacting Cloudflare KV switch: {e}. Continuing run...")


def step_2_fetch_polymarket_data():
    """Step 2: Fetch 10 active Polymarket events using exponential backoff retries."""
    print("\n--- [STEP 2] Fetching Active Market Data from Polymarket Gamma API ---")
    max_retries = 5
    base_delay = 2

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[FETCH] Attempt {attempt}/{max_retries} requesting {POLYMARKET_GAMMA_URL}...")
            res = requests.get(POLYMARKET_GAMMA_URL, timeout=15)
            if res.status_code == 200:
                events = res.json()
                print(f"[SUCCESS] Successfully fetched {len(events)} active events from Polymarket.")
                return events
            else:
                print(f"[WARNING] Received status code {res.status_code} from Polymarket API.")
        except Exception as e:
            print(f"[WARNING] Attempt {attempt} failed: {e}")

        if attempt < max_retries:
            sleep_time = base_delay ** attempt
            print(f"[RETRY] Waiting {sleep_time}s before next attempt (Exponential Backoff)...")
            time.sleep(sleep_time)

    print("[ERROR] Failed to fetch market data after 5 retries.")
    return []


def step_3_analyze_with_gemini(market_info, gemini_client):
    """Step 3: Analyze market using Gemini 3.6 Flash Engine asking for structured JSON decision."""
    if not gemini_client:
        return {"keputusan": "HOLD", "alasan": "Gemini API Client tidak tersedia (Mock mode)."}

    prompt = f"""
Kamu adalah AI Trading Bot Senior spesialis pasar prediksi Polymarket.
Analisis data pasar prediksi berikut dan berikan keputusan trading terbaik:

Detail Pasar:
- Judul Event: {market_info.get('title')}
- Pertanyaan Pasar: {market_info.get('question')}
- Harga Outcome YES: {market_info.get('price_yes')}
- Harga Outcome NO: {market_info.get('price_no')}
- Volume: {market_info.get('volume')}

Aturan Keputusan:
1. "BUY_YES": Jika kamu yakin outcome YES memiliki probabilitas keberhasilan jauh lebih tinggi daripada harganya sekarang.
2. "BUY_NO": Jika kamu yakin outcome NO memiliki nilai value jauh lebih tinggi.
3. "HOLD": Jika pasar terlalu berisiko, informasi tidak cukup, atau harga sudah wajar.

Berikan jawaban STRICT JSON tanpa teks tambahan di luar JSON:
{{
  "keputusan": "BUY_YES" | "BUY_NO" | "HOLD",
  "alasan": "Penjelasan singkat maksimal 2 kalimat"
}}
"""

    model_name = "gemini-2.5-flash"

    try:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.2
        )
        response = gemini_client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=config
        )
        
        raw_text = response.text.strip()
        decision_data = json.loads(raw_text)
        return decision_data
    except Exception as e:
        print(f"   [GEMINI ERROR] Exception during API call: {e}")
        # Fallback response
        return {"keputusan": "HOLD", "alasan": f"Error analisis Gemini: {str(e)}"}


def step_4_record_simulation(records):
    """Step 4: Save transaction & simulation records into CSV."""
    print(f"\n--- [STEP 4] Logging {len(records)} Simulation Results to {CSV_FILENAME} ---")
    file_exists = os.path.exists(CSV_FILENAME)

    fieldnames = [
        "Timestamp",
        "EventTitle",
        "MarketQuestion",
        "TokenID_YES",
        "TokenID_NO",
        "Price_YES",
        "Price_NO",
        "Keputusan",
        "Alasan",
        "Volume"
    ]

    try:
        with open(CSV_FILENAME, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            for rec in records:
                writer.writerow(rec)
        print(f"[SUCCESS] CSV update complete. File '{CSV_FILENAME}' is ready.")
    except Exception as e:
        print(f"[ERROR] Failed writing to CSV: {e}")


def main():
    print("==================================================================")
    print("🚀 Polymarket AI Trading Bot (Gemini 3.6 Flash Engine) Initialized")
    print(f"⏰ Execution Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("==================================================================")

    # 1. Cek Saklar Emergency Status
    step_1_check_emergency_switch()

    # Initialize Gemini Client if API Key is available
    gemini_client = None
    if GENAI_AVAILABLE and GEMINI_API_KEY:
        try:
            gemini_client = genai.Client(api_key=GEMINI_API_KEY)
            print("[INFO] Google GenAI client successfully initialized.")
        except Exception as err:
            print(f"[WARNING] Could not initialize Google GenAI Client: {err}")
    else:
        print("[INFO] GEMINI_API_KEY is not set or SDK missing. Running in simulation fallback mode.")

    # 2. Fetch Data from Polymarket Gamma API
    events = step_2_fetch_polymarket_data()
    if not events:
        print("[INFO] No active events found or API down. Exiting cycle.")
        sys.exit(0)

    print("\n--- [STEP 3] Analyzing Markets with Gemini AI Engine ---")
    simulation_records = []

    for idx, event in enumerate(events, 1):
        event_title = event.get("title", "Unknown Event")
        markets = event.get("markets", [])

        if not markets:
            continue

        market = markets[0]
        market_question = market.get("question", event_title)
        
        # Parse clobTokenIds
        clob_tokens = market.get("clobTokenIds", [])
        if isinstance(clob_tokens, str):
            try:
                clob_tokens = json.loads(clob_tokens)
            except Exception:
                clob_tokens = []

        token_id_yes = clob_tokens[0] if len(clob_tokens) > 0 else "N/A"
        token_id_no = clob_tokens[1] if len(clob_tokens) > 1 else "N/A"

        # Parse Outcome Prices
        outcome_prices = market.get("outcomePrices", [])
        if isinstance(outcome_prices, str):
            try:
                outcome_prices = json.loads(outcome_prices)
            except Exception:
                outcome_prices = []

        price_yes = outcome_prices[0] if len(outcome_prices) > 0 else "0.50"
        price_no = outcome_prices[1] if len(outcome_prices) > 1 else "0.50"
        volume = market.get("volume", "0")

        market_info = {
            "title": event_title,
            "question": market_question,
            "price_yes": price_yes,
            "price_no": price_no,
            "volume": volume
        }

        print(f"\n[{idx}/{len(events)}] Analyzing Market: '{market_question[:60]}...'")
        print(f"    Prices -> YES: ${price_yes} | NO: ${price_no} | Volume: ${volume}")

        # Send to Gemini
        ai_result = step_3_analyze_with_gemini(market_info, gemini_client)
        keputusan = ai_result.get("keputusan", "HOLD")
        alasan = ai_result.get("alasan", "No reason provided.")

        print(f"    🤖 AI Decision: {keputusan} | Reason: {alasan}")

        simulation_records.append({
            "Timestamp": datetime.now(timezone.utc).isoformat(),
            "EventTitle": event_title,
            "MarketQuestion": market_question,
            "TokenID_YES": token_id_yes,
            "TokenID_NO": token_id_no,
            "Price_YES": price_yes,
            "Price_NO": price_no,
            "Keputusan": keputusan,
            "Alasan": alasan,
            "Volume": volume
        })

        # Rate Limit / Speed optimization delay (1 second sleep between market calls)
        time.sleep(1)

    # 4. Log all decisions to CSV
    if simulation_records:
        step_4_record_simulation(simulation_records)

    print("\n✅ [CYCLE COMPLETE] Bot cycle finished successfully.")


if __name__ == "__main__":
    main()
