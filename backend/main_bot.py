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

# Ensure script directory is always in sys.path for config.py import
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

# SSL Bypass
ssl._create_default_https_context = ssl._create_unverified_context
os.environ["PYTHONHTTPSVERIFY"] = "0"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Monkey-patch httpx
try:
    import httpx
    _orig = httpx.Client.__init__
    def _patched(self, *args, **kwargs):
        kwargs['verify'] = False
        _orig(self, *args, **kwargs)
    httpx.Client.__init__ = _patched
except Exception:
    pass

# ============================================================
# KONFIGURASI BOT
# ============================================================
try:
    from config import (
        EOA_WALLET_ADDRESS,
        PRIVATE_KEY,
        CLOB_API_KEY,
        BET_AMOUNT_USD,
        MAX_TRADES_PER_CYCLE,
        MAX_DAILY_TRADES,
        GITHUB_TOKEN,
        REPO_OWNER,
        REPO_NAME,
        CLOB_HOST,
        GAMMA_API,
        CLOUDFLARE_KV_URL,
        CSV_FILENAME
    )
    POLYMARKET_DEPOSIT = "0x998DAe6C3Eb18ecDD9C985CA4975051046F18EF0"
    CLOB_API_SECRET = ""
    CLOB_API_PASSPHRASE = ""
    GEMINI_API_KEY = ""
except ImportError:
    # Read directly from config.py if present in directory
    import config
    EOA_WALLET_ADDRESS       = config.EOA_WALLET_ADDRESS
    PRIVATE_KEY              = config.PRIVATE_KEY
    POLYMARKET_DEPOSIT       = getattr(config, "POLYMARKET_DEPOSIT_ADDRESS", "0x998DAe6C3Eb18ecDD9C985CA4975051046F18EF0")
    CLOB_API_KEY             = config.CLOB_API_KEY
    CLOB_API_SECRET          = getattr(config, "CLOB_API_SECRET", "")
    CLOB_API_PASSPHRASE      = getattr(config, "CLOB_API_PASSPHRASE", "")
    GEMINI_API_KEY           = getattr(config, "GEMINI_API_KEY", "")
    BET_AMOUNT_USD           = getattr(config, "BET_AMOUNT_USD", 1.0)
    MAX_TRADES_PER_CYCLE     = getattr(config, "MAX_TRADES_PER_CYCLE", 10)
    MAX_DAILY_TRADES         = getattr(config, "MAX_DAILY_TRADES", 100)
    GITHUB_TOKEN             = getattr(config, "GITHUB_TOKEN", "")
    REPO_OWNER               = getattr(config, "REPO_OWNER", "Faang21")
    REPO_NAME                = getattr(config, "REPO_NAME", "polymarket-ai-trading-bot")
    CLOB_HOST                = getattr(config, "CLOB_HOST", "https://clob.polymarket.com")
    GAMMA_API                = getattr(config, "GAMMA_API", "https://gamma-api.polymarket.com")
    CLOUDFLARE_KV_URL        = getattr(config, "CLOUDFLARE_KV_URL", "https://bot-control.aangcrypto21.workers.dev/status")
    CSV_FILENAME             = getattr(config, "CSV_FILENAME", "catatan_trading_real.csv")

# Import GenAI
try:
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except Exception:
    GENAI_AVAILABLE = False

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
    try:
        from web3 import Web3
        for rpc in ["https://polygon-bor-rpc.publicnode.com", "https://1rpc.io/matic", "https://rpc.ankr.com/polygon"]:
            try:
                w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'verify': False}))
                if w3.is_connected():
                    abi = [{"constant": True, "inputs": [{"name": "_owner", "type": "address"}],
                            "name": "balanceOf", "outputs": [{"name": "balance", "type": "uint256"}],
                            "type": "function"}]
                    usdc = w3.eth.contract(address=Web3.to_checksum_address("0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"), abi=abi)
                    bal_eoa = usdc.functions.balanceOf(Web3.to_checksum_address(EOA_WALLET_ADDRESS)).call()
                    bal_dep = usdc.functions.balanceOf(Web3.to_checksum_address(POLYMARKET_DEPOSIT)).call()
                    return (bal_eoa + bal_dep) / 1e6
            except Exception:
                continue
    except Exception:
        pass
    return 0.0


def fetch_btc_5m_markets():
    """Fokus KHUSUS pasar BTC Up or Down 5m / 15m (btc-updown-5m)."""
    endpoints = [
        f"{GAMMA_API}/events?closed=false&q=btc-updown-5m&limit=100",
        f"{GAMMA_API}/events?closed=false&q=5-minute&limit=100",
        f"{GAMMA_API}/events?closed=false&tag_slug=bitcoin&limit=100"
    ]

    all_markets = []
    seen_slugs = set()

    for ep in endpoints:
        try:
            res = requests.get(ep, timeout=15, verify=False)
            if res.status_code == 200:
                for e in res.json():
                    title = (e.get("title") or "").lower()
                    slug = (e.get("slug") or "").lower()
                    if slug in seen_slugs:
                        continue
                    
                    # Target 100% pasar BTC Up or Down 5m/15m
                    is_target = ("btc-updown-5m" in slug) or ("btc up or down" in title) or ("bitcoin up or down" in title)
                    if is_target:
                        markets_list = e.get("markets", [])
                        if markets_list and len(markets_list) > 0:
                            all_markets.append(e)
                            seen_slugs.add(slug)
        except Exception:
            continue

    # Fallback jika pasar 5m persis sedang berganti menit
    if not all_markets:
        for ep in endpoints:
            try:
                res = requests.get(ep, timeout=15, verify=False)
                if res.status_code == 200:
                    for e in res.json():
                        title = (e.get("title") or "").lower()
                        slug = (e.get("slug") or "").lower()
                        text = title + " " + slug
                        if slug in seen_slugs: continue
                        if ("btc" in text or "bitcoin" in text) and ("up or down" in text or "updown" in text):
                            markets_list = e.get("markets", [])
                            if markets_list and len(markets_list) > 0:
                                all_markets.append(e)
                                seen_slugs.add(slug)
                                if len(all_markets) >= 3: break
            except Exception:
                continue

    return all_markets


def analyze_with_ai(price_yes, price_no, gemini_client):
    if price_yes > price_no:
        return {"keputusan": "BUY_YES", "alasan": f"Momentum UP dominan ({price_yes:.2f})."}
    elif price_no > price_yes:
        return {"keputusan": "BUY_NO", "alasan": f"Momentum DOWN dominan ({price_no:.2f})."}
    else:
        return {"keputusan": "BUY_YES", "alasan": "Harga imbang, masuk posisi UP/YES."}


def execute_real_order(token_id, price, side_label):
    """Kirim REAL order ke Polymarket CLOB dengan auto-fallback signature type (0=EOA, 2=Proxy)."""
    global cycle_trades, daily_trades
    if cycle_trades >= MAX_TRADES_PER_CYCLE:
        return "CYCLE_LIMIT"
    if daily_trades >= MAX_DAILY_TRADES:
        return "DAILY_LIMIT"

    print(f"   🚀 [{side_label}] Token: {str(token_id)[:16]}... | Price: {price:.4f} | Bet: ${BET_AMOUNT_USD}")
    
    try:
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import ApiCreds, OrderArgs
    except ImportError:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import ApiCreds, OrderArgs

    creds = ApiCreds(
        api_key=CLOB_API_KEY,
        api_secret=CLOB_API_SECRET,
        api_passphrase=CLOB_API_PASSPHRASE
    )
    size = round(BET_AMOUNT_USD / max(price, 0.01), 2)
    order_args = OrderArgs(
        price=price,
        size=size,
        side="BUY",
        token_id=str(token_id)
    )

    last_err = ""
    for sig_type in [0, 2, 1]:
        try:
            client = ClobClient(
                host=CLOB_HOST,
                key=PRIVATE_KEY,
                chain_id=137,
                signature_type=sig_type,
                funder=POLYMARKET_DEPOSIT
            )
            # Derivasi API Creds otomatis dari Private Key untuk Polymarket V2
            try:
                derived_creds = client.create_or_derive_api_creds()
                client.set_api_creds(derived_creds)
            except Exception:
                creds = ApiCreds(
                    api_key=CLOB_API_KEY,
                    api_secret=CLOB_API_SECRET,
                    api_passphrase=CLOB_API_PASSPHRASE
                )
                client.set_api_creds(creds)

            signed = client.create_order(order_args)
            res    = client.post_order(signed)
            cycle_trades += 1
            daily_trades += 1
            order_id = str(res.get("orderID") or res.get("id") or "POSTED")
            print(f"   🎉 ORDER SUKSES! ID: {order_id} (SigType={sig_type}) | Cycle: {cycle_trades}")
            return order_id
        except Exception as err:
            last_err = str(err)
            if "Unauthorized" in last_err or "401" in last_err or "400" in last_err or "invalid order version" in last_err:
                continue # Coba sig_type berikutnya
            else:
                break

    print(f"   ⚠️ Order status: {last_err[:100]}")
    return f"ERROR: {last_err[:40]}"


def save_and_sync(records):
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

    if GITHUB_TOKEN:
        try:
            with open(CSV_FILENAME, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{CSV_FILENAME}"
            headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
            r = requests.get(url, headers=headers, verify=False)
            sha = r.json().get("sha") if r.status_code == 200 else None
            body = {"message": f"📊 Real trade [{datetime.now(timezone.utc).strftime('%H:%M')}]",
                    "content": b64, "branch": "main"}
            if sha:
                body["sha"] = sha
            requests.put(url, headers=headers, json=body, verify=False)
            print("📊 Dashboard GitHub diperbarui.")
        except Exception:
            pass


def main():
    global cycle_trades
    cycle_trades = 0

    now = datetime.now().strftime("%H:%M:%S")
    print(f"\n{'='*60}")
    print(f"🚀 POLYMARKET BTC 5M REAL BOT | {now}")
    print(f"💼 Wallet  : {EOA_WALLET_ADDRESS}")
    print(f"🏦 Deposit : {POLYMARKET_DEPOSIT}")
    print(f"💵 Bet     : ${BET_AMOUNT_USD} per trade | Key: {CLOB_API_KEY[:8]}...")
    print(f"{'='*60}")

    check_emergency_switch()

    usdc = get_usdc_balance()
    print(f"[SALDO] USDC Tersedia: ${usdc:.2f}")
    if usdc < BET_AMOUNT_USD:
        print(f"⚠️ Saldo ${usdc:.2f} tidak cukup untuk bet ${BET_AMOUNT_USD}. Skip cycle.")
        return

    markets = fetch_btc_5m_markets()
    if not markets:
        print("[INFO] Tidak ada pasar BTC 5m aktif saat ini. Skip.")
        return

    print(f"[MARKET] {len(markets)} pasar BTC Up or Down 5m aktif ditemukan.")
    records = []

    for idx, event in enumerate(markets):
        if cycle_trades >= MAX_TRADES_PER_CYCLE:
            print(f"[LIMIT] Batas {MAX_TRADES_PER_CYCLE} trade per cycle.")
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
            try: clob_tokens = json.loads(clob_tokens)
            except: clob_tokens = []

        prices = m.get("outcomePrices", [])
        if isinstance(prices, str):
            try: prices = json.loads(prices)
            except: prices = []

        if len(clob_tokens) < 2 or len(prices) < 2:
            continue

        token_yes = clob_tokens[0]
        token_no = clob_tokens[1]
        price_yes = float(prices[0])
        price_no = float(prices[1])

        # Filter harga valid Polymarket CLOB (0.001 - 0.999)
        if price_yes < 0.001 or price_yes > 0.999:
            continue

        result = analyze_with_ai(price_yes, price_no, None)
        keputusan = result.get("keputusan", "BUY_YES")
        alasan = result.get("alasan", "")

        print(f"\n[{idx+1}] {event.get('title', 'BTC Up or Down 5m')[:55]}")
        print(f"     UP:{price_yes:.4f} | DOWN:{price_no:.4f} → {keputusan}")

        order_id, token_used, price_used, side = "HOLD", "", 0.0, "HOLD"
        if keputusan == "BUY_YES" and token_yes:
            order_id = execute_real_order(token_yes, price_yes, "BUY UP/YES")
            token_used, price_used, side = str(token_yes), price_yes, "BUY_YES"
        elif keputusan == "BUY_NO" and token_no:
            order_id = execute_real_order(token_no, price_no, "BUY DOWN/NO")
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
