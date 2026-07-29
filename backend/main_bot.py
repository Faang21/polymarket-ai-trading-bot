import os
import sys
import time
import json
import csv
import ssl
import base64
import requests
import urllib3
from datetime import datetime, timezone

# SSL Bypass
ssl._create_default_https_context = ssl._create_unverified_context
os.environ["PYTHONHTTPSVERIFY"] = "0"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Monkey-patch httpx for google-genai
try:
    import httpx
    _orig = httpx.Client.__init__
    def _patched(self, *args, **kwargs):
        kwargs['verify'] = False
        _orig(self, *args, **kwargs)
    httpx.Client.__init__ = _patched
except Exception:
    pass

# Import config
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    EOA_WALLET_ADDRESS, PRIVATE_KEY, POLYMARKET_DEPOSIT_ADDRESS,
    CLOB_API_KEY, CLOB_API_SECRET, CLOB_API_PASSPHRASE,
    GEMINI_API_KEY, BET_AMOUNT_USD, MAX_TRADES_PER_CYCLE, MAX_DAILY_TRADES,
    GITHUB_TOKEN, REPO_OWNER, REPO_NAME, CLOB_HOST, GAMMA_API,
    CLOUDFLARE_KV_URL, CSV_FILENAME
)

# Import GenAI
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Session counters
cycle_trades = 0
daily_trades = 0


def check_emergency_switch():
    try:
        res = requests.get(CLOUDFLARE_KV_URL, timeout=8, verify=False)
        if res.status_code == 200:
            status = str(res.json().get("status") or "RUNNING").upper()
            if status == "STOPPED":
                print("🚨 [EMERGENCY STOP] Bot dihentikan via switch.")
                sys.exit(0)
    except Exception:
        pass


def get_usdc_balance():
    """Cek saldo USDC langsung dari Polygon blockchain."""
    try:
        from web3 import Web3
        for rpc in ["https://polygon-bor-rpc.publicnode.com", "https://1rpc.io/matic"]:
            try:
                w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'verify': False}))
                if w3.is_connected():
                    usdc = w3.eth.contract(
                        address=Web3.to_checksum_address("0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"),
                        abi=[{"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
                              "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
                              "type": "function"}]
                    )
                    # Check deposit address balance (Polymarket proxy vault)
                    bal_deposit = usdc.functions.balanceOf(
                        Web3.to_checksum_address(POLYMARKET_DEPOSIT_ADDRESS)
                    ).call()
                    bal_eoa = usdc.functions.balanceOf(
                        Web3.to_checksum_address(EOA_WALLET_ADDRESS)
                    ).call()
                    return (bal_deposit + bal_eoa) / 1e6
            except Exception:
                continue
    except Exception:
        pass
    return 0.0


def fetch_btc_5m_markets():
    """Fetch ALL active BTC 5-minute markets - bot bisa trade sebanyak yang ada."""
    EXCLUDE = ["el salvador", "150k", "100k", "200k", "kraken", "ipo",
               "microstrategy", "etf", "sec", "election", "trump", "fed",
               "rate", "company", "stock", "year", "month", "september", "december"]

    endpoints = [
        f"{GAMMA_API}/events?closed=false&q=5-minute&limit=100",
        f"{GAMMA_API}/events?closed=false&q=up+or+down&limit=100",
    ]

    all_markets = []
    seen_slugs = set()

    for ep in endpoints:
        try:
            res = requests.get(ep, timeout=15, verify=False)
            if res.status_code == 200:
                for e in res.json():
                    text = ((e.get("title") or "") + " " + (e.get("slug") or "")).lower()
                    slug = e.get("slug", "")
                    if slug in seen_slugs:
                        continue
                    if any(bad in text for bad in EXCLUDE):
                        continue
                    if "up or down" in text or "btc-updown" in text or "5-minute" in text or "5m" in text:
                        all_markets.append(e)
                        seen_slugs.add(slug)
        except Exception:
            continue

    return all_markets


def analyze_with_ai(price_yes, price_no, gemini_client):
    """AI signal engine - Gemini + Quantitative fallback."""
    if gemini_client and not GEMINI_API_KEY.startswith("AQ."):
        try:
            prompt = f"""
Analisis pasar prediksi Bitcoin Polymarket 5-menitan:
- Harga kontrak YES: {price_yes:.4f}
- Harga kontrak NO: {price_no:.4f}

Jawab dengan JSON SAJA tanpa penjelasan lain:
{{"keputusan": "BUY_YES" atau "BUY_NO" atau "HOLD", "alasan": "maksimal 1 kalimat"}}
"""
            cfg = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
            resp = gemini_client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=cfg)
            return json.loads(resp.text.strip())
        except Exception:
            pass

    # Quantitative Signal Engine
    spread = abs(price_yes - price_no)
    if spread < 0.02:
        return {"keputusan": "HOLD", "alasan": "Spread terlalu sempit, pasar seimbang."}
    if price_yes < 0.45:
        return {"keputusan": "BUY_YES", "alasan": f"YES oversold ({price_yes:.2f}), momentum reversal terdeteksi."}
    if price_no < 0.45:
        return {"keputusan": "BUY_NO", "alasan": f"NO oversold ({price_no:.2f}), pressure bearish terkonfirmasi."}
    if price_yes > price_no:
        return {"keputusan": "BUY_YES", "alasan": f"YES lebih dominan ({price_yes:.2f} vs {price_no:.2f})."}
    return {"keputusan": "BUY_NO", "alasan": f"NO lebih dominan ({price_no:.2f} vs {price_yes:.2f})."}


def execute_real_order(token_id, price, side_label):
    """Kirim order REAL ke Polymarket CLOB."""
    global cycle_trades, daily_trades

    if cycle_trades >= MAX_TRADES_PER_CYCLE:
        return "CYCLE_LIMIT"
    if daily_trades >= MAX_DAILY_TRADES:
        return "DAILY_LIMIT"

    print(f"   🚀 [{side_label}] Token: {str(token_id)[:16]}... | Price: {price:.4f} | Bet: ${BET_AMOUNT_USD}")

    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import ApiCreds, OrderArgs, Side

        creds = ApiCreds(
            api_key=CLOB_API_KEY,
            api_secret=CLOB_API_SECRET,
            api_passphrase=CLOB_API_PASSPHRASE
        )
        client = ClobClient(
            host=CLOB_HOST,
            key=PRIVATE_KEY,
            chain_id=137,
            creds=creds,
            signature_type=1
        )

        size = round(BET_AMOUNT_USD / max(price, 0.01), 2)
        order_args = OrderArgs(
            price=price,
            size=size,
            side=Side.BUY,
            token_id=str(token_id)
        )

        signed = client.create_order(order_args)
        res = client.post_order(signed)
        cycle_trades += 1
        daily_trades += 1
        order_id = str(res.get("orderID") or res.get("id") or "POSTED")
        print(f"   🎉 ORDER SUKSES! ID: {order_id} | Cycle: {cycle_trades} | Harian: {daily_trades}")
        return order_id

    except Exception as err:
        print(f"   ⚠️ Order error: {str(err)[:80]}")
        return f"ERROR"


def save_and_sync(records):
    """Simpan ke CSV lokal dan sync ke GitHub dashboard."""
    if not records:
        return

    fieldnames = ["Timestamp", "Market", "TokenID", "Price", "Side", "BetUSD", "OrderID", "Alasan"]
    file_exists = os.path.exists(CSV_FILENAME)

    with open(CSV_FILENAME, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for r in records:
            writer.writerow(r)

    print(f"\n📝 {len(records)} record disimpan ke {CSV_FILENAME}")

    # Sync ke GitHub (hanya dashboard)
    if GITHUB_TOKEN:
        try:
            with open(CSV_FILENAME, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{CSV_FILENAME}"
            headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
            r = requests.get(url, headers=headers, verify=False)
            sha = r.json().get("sha") if r.status_code == 200 else None
            body = {"message": f"📊 Real trade log [{datetime.now(timezone.utc).strftime('%H:%M')}]",
                    "content": b64, "branch": "main"}
            if sha:
                body["sha"] = sha
            requests.put(url, headers=headers, json=body, verify=False)
            print("📊 Dashboard GitHub diperbarui.")
        except Exception:
            pass


def main():
    global cycle_trades
    cycle_trades = 0  # Reset per cycle

    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'='*60}")
    print(f"🚀 POLYMARKET REAL TRADING BOT | {now}")
    print(f"💼 Wallet  : {EOA_WALLET_ADDRESS}")
    print(f"🏦 Deposit : {POLYMARKET_DEPOSIT_ADDRESS}")
    print(f"💵 Bet     : ${BET_AMOUNT_USD} per trade")
    print(f"🔑 API Key : {CLOB_API_KEY[:8]}...")
    print(f"{'='*60}")

    check_emergency_switch()

    # Cek saldo
    usdc = get_usdc_balance()
    print(f"[SALDO] USDC Tersedia: ${usdc:.2f}")
    if usdc < BET_AMOUNT_USD:
        print(f"⚠️ Saldo ${usdc:.2f} tidak cukup untuk bet ${BET_AMOUNT_USD}. Skip cycle.")
        return

    # Init Gemini
    gemini_client = None
    if GENAI_AVAILABLE and not GEMINI_API_KEY.startswith("AQ."):
        try:
            gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception:
            pass

    # Ambil semua pasar BTC 5m aktif
    markets = fetch_btc_5m_markets()
    if not markets:
        print("[INFO] Tidak ada pasar BTC 5m aktif. Skip.")
        return

    print(f"[MARKET] {len(markets)} pasar BTC 5m aktif ditemukan.")

    records = []
    for idx, event in enumerate(markets):
        if cycle_trades >= MAX_TRADES_PER_CYCLE:
            print(f"[LIMIT] Batas {MAX_TRADES_PER_CYCLE} trade per cycle tercapai.")
            break
        if usdc < BET_AMOUNT_USD * (cycle_trades + 1):
            print(f"[LIMIT] Saldo tidak cukup untuk trade berikutnya.")
            break

        market_list = event.get("markets", [])
        if not market_list:
            continue

        m = market_list[0]
        clob_tokens = m.get("clobTokenIds", [])
        if isinstance(clob_tokens, str):
            try:
                clob_tokens = json.loads(clob_tokens)
            except Exception:
                clob_tokens = []

        prices = m.get("outcomePrices", [])
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except Exception:
                prices = []

        if len(clob_tokens) < 2 or len(prices) < 2:
            continue

        token_yes = clob_tokens[0]
        token_no = clob_tokens[1]
        price_yes = float(prices[0])
        price_no = float(prices[1])

        result = analyze_with_ai(price_yes, price_no, gemini_client)
        keputusan = result.get("keputusan", "HOLD")
        alasan = result.get("alasan", "")

        print(f"\n[{idx+1}] {event.get('title','BTC 5m')[:50]}")
        print(f"     YES: {price_yes:.4f} | NO: {price_no:.4f} → {keputusan}")

        order_id = "HOLD"
        token_used = ""
        price_used = 0.0
        side = "HOLD"

        if keputusan == "BUY_YES" and token_yes:
            order_id = execute_real_order(token_yes, price_yes, "BUY YES")
            token_used, price_used, side = str(token_yes), price_yes, "BUY_YES"
        elif keputusan == "BUY_NO" and token_no:
            order_id = execute_real_order(token_no, price_no, "BUY NO")
            token_used, price_used, side = str(token_no), price_no, "BUY_NO"

        records.append({
            "Timestamp": datetime.now(timezone.utc).isoformat(),
            "Market": event.get("title", "BTC 5m")[:60],
            "TokenID": token_used[:20] if token_used else "N/A",
            "Price": f"{price_used:.4f}",
            "Side": side,
            "BetUSD": BET_AMOUNT_USD if side != "HOLD" else 0,
            "OrderID": str(order_id)[:30],
            "Alasan": alasan[:80]
        })

    print(f"\n✅ Cycle selesai. Trade cycle ini: {cycle_trades} | Total harian: {daily_trades}")
    save_and_sync(records)


if __name__ == "__main__":
    main()
