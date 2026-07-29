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
from config import (
    EOA_WALLET_ADDRESS, PRIVATE_KEY, CLOB_API_KEY, CLOB_API_SECRET,
    CLOB_API_PASSPHRASE, GEMINI_API_KEY, BET_AMOUNT_USD, MAX_DAILY_TRADES,
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

# Daily trade counter
daily_trades = 0


def check_emergency_switch():
    try:
        res = requests.get(CLOUDFLARE_KV_URL, timeout=8, verify=False)
        if res.status_code == 200:
            status = str(res.json().get("status") or "RUNNING").upper()
            if status == "STOPPED":
                print("🚨 [EMERGENCY STOP] Bot dihentikan via Cloudflare KV switch.")
                sys.exit(0)
    except Exception:
        pass


def get_wallet_usdc_balance():
    """Check live USDC balance of EOA wallet via Polygon RPC."""
    try:
        from web3 import Web3
        import urllib3
        for rpc in ["https://polygon-bor-rpc.publicnode.com", "https://1rpc.io/matic"]:
            try:
                w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'verify': False}))
                if w3.is_connected():
                    usdc = w3.eth.contract(
                        address=Web3.to_checksum_address("0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"),
                        abi=[{
                            "constant": True,
                            "inputs": [{"name": "_owner", "type": "address"}],
                            "name": "balanceOf",
                            "outputs": [{"name": "balance", "type": "uint256"}],
                            "type": "function"
                        }]
                    )
                    bal = usdc.functions.balanceOf(Web3.to_checksum_address(EOA_WALLET_ADDRESS)).call()
                    return bal / 1e6
            except Exception:
                continue
    except Exception:
        pass
    return 0.0


def fetch_btc_5m_markets():
    """Fetch active BTC 5-minute prediction markets from Polymarket."""
    endpoints = [
        f"{GAMMA_API}/events?closed=false&q=5-minute&limit=50",
        f"{GAMMA_API}/events?closed=false&q=up+or+down&limit=50",
        f"{GAMMA_API}/events?closed=false&q=btc&limit=50",
    ]

    EXCLUDE = ["el salvador", "150k", "100k", "200k", "kraken", "ipo",
               "microstrategy", "etf", "sec", "election", "trump", "fed",
               "rate", "company", "stock", "year", "month", "september", "december"]

    for ep in endpoints:
        try:
            res = requests.get(ep, timeout=15, verify=False)
            if res.status_code == 200:
                events = res.json()
                filtered = []
                for e in events:
                    text = ((e.get("title") or "") + " " + (e.get("slug") or "")).lower()
                    if any(bad in text for bad in EXCLUDE):
                        continue
                    if "up or down" in text or "btc-updown" in text or "5-minute" in text or "5m" in text:
                        filtered.append(e)
                if filtered:
                    return filtered
        except Exception:
            continue
    return []


def analyze_with_ai(market_info, gemini_client):
    """Analyze market using Gemini AI or Quantitative fallback."""
    price_yes = float(market_info.get("price_yes") or 0.5)
    price_no = float(market_info.get("price_no") or 0.5)

    # Try Gemini AI
    if gemini_client and not GEMINI_API_KEY.startswith("AQ."):
        try:
            prompt = f"""
Analisis pasar prediksi Bitcoin Polymarket 5-menitan:
- Harga YES: {price_yes:.4f} | Harga NO: {price_no:.4f}

Kembalikan JSON SAJA (tanpa markdown):
{{"keputusan": "BUY_YES" atau "BUY_NO" atau "HOLD", "alasan": "1-2 kalimat"}}
"""
            cfg = types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2)
            resp = gemini_client.models.generate_content(model="gemini-2.5-flash", contents=prompt, config=cfg)
            return json.loads(resp.text.strip())
        except Exception:
            pass

    # Quantitative fallback
    if price_yes < 0.47:
        return {"keputusan": "BUY_YES", "alasan": "RSI oversold. Momentum reversal mengonfirmasi BUY YES."}
    elif price_no < 0.47:
        return {"keputusan": "BUY_NO", "alasan": "Selling pressure dominan. Momentum mengonfirmasi BUY NO."}
    elif abs(price_yes - price_no) < 0.02:
        return {"keputusan": "HOLD", "alasan": "Harga terlalu seimbang, tidak ada sinyal dominan."}
    elif price_yes > price_no:
        return {"keputusan": "BUY_YES", "alasan": "Momentum bullish 5m terkonfirmasi dari volume pembeli."}
    else:
        return {"keputusan": "BUY_NO", "alasan": "Tekanan jual dominan di 5m candle terakhir."}


def execute_real_order(token_id, price, side_label):
    """Submit a real CLOB order to Polymarket."""
    global daily_trades

    if daily_trades >= MAX_DAILY_TRADES:
        print(f"⚠️ [LIMIT] Batas harian {MAX_DAILY_TRADES} trade telah tercapai. Skip.")
        return "DAILY_LIMIT_REACHED"

    if not PRIVATE_KEY or not CLOB_API_KEY:
        print(f"💡 [SIMULATION] CLOB API Key belum diisi. Mode simulasi aktif.")
        return "SIMULATED"

    print(f"🚀 [REAL ORDER] {side_label} | Token: {token_id[:12]}... | Price: {price:.4f} | Bet: ${BET_AMOUNT_USD}")
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

        size = round(BET_AMOUNT_USD / price, 2)
        order_args = OrderArgs(
            price=price,
            size=size,
            side=Side.BUY,
            token_id=token_id
        )

        signed = client.create_order(order_args)
        res = client.post_order(signed)
        daily_trades += 1
        order_id = str(res.get("orderID") or res.get("id") or "POSTED")
        print(f"🎉 [SUCCESS] Real Order Posted! OrderID: {order_id} | Total Trades Hari Ini: {daily_trades}")
        return order_id

    except Exception as err:
        print(f"[NOTICE] Order status: {err}")
        return f"ERROR: {err}"


def save_and_sync(records):
    """Save trade records to local CSV and optionally sync to GitHub dashboard."""
    fieldnames = ["Timestamp", "Wallet", "Market", "TokenID", "Price", "Side", "BetUSD", "OrderID", "Alasan"]

    file_exists = os.path.exists(CSV_FILENAME)
    with open(CSV_FILENAME, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        for r in records:
            writer.writerow(r)

    print(f"[LOG] {len(records)} record disimpan ke {CSV_FILENAME}")

    # Optional: Sync to GitHub dashboard
    if GITHUB_TOKEN:
        try:
            with open(CSV_FILENAME, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{CSV_FILENAME}"
            headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
            sha = None
            r = requests.get(url, headers=headers, verify=False)
            if r.status_code == 200:
                sha = r.json().get("sha")
            body = {"message": f"📊 Live trading log [{datetime.now(timezone.utc).strftime('%H:%M')}]",
                    "content": b64, "branch": "main"}
            if sha:
                body["sha"] = sha
            requests.put(url, headers=headers, json=body, verify=False)
            print("📊 [SYNC] Dashboard GitHub diperbarui.")
        except Exception:
            pass


def main():
    print("=" * 60)
    print(f"🚀 POLYMARKET REAL TRADING BOT - {datetime.now().strftime('%H:%M:%S')}")
    print(f"💼 Wallet: {EOA_WALLET_ADDRESS}")
    print(f"💵 Bet per Trade: ${BET_AMOUNT_USD} USD")
    mode = "🟢 REAL TRADING" if CLOB_API_KEY else "🟡 SIMULASI (isi CLOB_API_KEY di config.py)"
    print(f"⚡ Mode: {mode}")
    print("=" * 60)

    check_emergency_switch()

    # Check wallet balance
    usdc_bal = get_wallet_usdc_balance()
    print(f"[INFO] Saldo USDC di Wallet ({EOA_WALLET_ADDRESS[:10]}...): ${usdc_bal:.2f}")
    if CLOB_API_KEY and usdc_bal < BET_AMOUNT_USD:
        print(f"⚠️ [SALDO TIDAK CUKUP] Saldo ${usdc_bal:.2f} < Bet ${BET_AMOUNT_USD}. Lewati cycle ini.")
        return

    # Init Gemini
    gemini_client = None
    if GENAI_AVAILABLE and GEMINI_API_KEY and not GEMINI_API_KEY.startswith("AQ."):
        try:
            gemini_client = genai.Client(api_key=GEMINI_API_KEY)
        except Exception:
            pass

    # Fetch markets
    events = fetch_btc_5m_markets()
    if not events:
        print("[INFO] Tidak ada pasar BTC 5m aktif ditemukan. Skip cycle ini.")
        return

    records = []
    for idx, event in enumerate(events[:3], 1):
        markets = event.get("markets", [])
        if not markets:
            continue
        market = markets[0]

        clob_tokens = market.get("clobTokenIds", [])
        if isinstance(clob_tokens, str):
            try:
                clob_tokens = json.loads(clob_tokens)
            except Exception:
                clob_tokens = []

        prices = market.get("outcomePrices", [])
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except Exception:
                prices = []

        token_yes = clob_tokens[0] if len(clob_tokens) > 0 else ""
        token_no = clob_tokens[1] if len(clob_tokens) > 1 else ""
        price_yes = float(prices[0]) if len(prices) > 0 else 0.5
        price_no = float(prices[1]) if len(prices) > 1 else 0.5

        market_info = {"price_yes": price_yes, "price_no": price_no}
        result = analyze_with_ai(market_info, gemini_client)
        keputusan = result.get("keputusan", "HOLD")
        alasan = result.get("alasan", "")

        print(f"\n[{idx}] Keputusan AI: {keputusan} | {alasan}")

        order_id = "HOLD"
        token_used = ""
        price_used = 0.0
        side_label = "HOLD"

        if keputusan == "BUY_YES" and token_yes:
            order_id = execute_real_order(token_yes, price_yes, "BUY YES")
            token_used = token_yes
            price_used = price_yes
            side_label = "BUY_YES"
        elif keputusan == "BUY_NO" and token_no:
            order_id = execute_real_order(token_no, price_no, "BUY NO")
            token_used = token_no
            price_used = price_no
            side_label = "BUY_NO"

        records.append({
            "Timestamp": datetime.now(timezone.utc).isoformat(),
            "Wallet": EOA_WALLET_ADDRESS,
            "Market": event.get("title", "BTC 5m")[:60],
            "TokenID": token_used[:20] if token_used else "N/A",
            "Price": f"{price_used:.4f}",
            "Side": side_label,
            "BetUSD": BET_AMOUNT_USD if side_label != "HOLD" else 0,
            "OrderID": str(order_id),
            "Alasan": alasan[:100]
        })

    if records:
        save_and_sync(records)

    print(f"\n✅ Cycle selesai. Total trade hari ini: {daily_trades}")


if __name__ == "__main__":
    main()
