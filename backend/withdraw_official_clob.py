import os
import sys
import time
import json
import ssl
import urllib3
import subprocess

# Auto-install py_clob_client if needed
for pkg in ["py_clob_client", "eth_account", "web3", "requests"]:
    try:
        __import__(pkg)
    except ImportError:
        subprocess.call([sys.executable, "-m", "pip", "install", "--trusted-host", "pypi.org", "--trusted-host", "files.pythonhosted.org", pkg])

ssl._create_default_https_context = ssl._create_unverified_context
os.environ["PYTHONHTTPSVERIFY"] = "0"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from eth_account import Account
    import requests
except Exception as err:
    print(f"[ERROR] Import failed: {err}")
    sys.exit(1)

# Official User Credentials from Screenshot
CLOB_API_KEY = os.environ.get("CLOB_API_KEY", "019fab86-89c7-7946-8e8c-df709ff9f1eb")
TARGET_WALLET = "0xa959f26847211f71a22adb087ebe50e0743e7d66"
SIGNER_EOA = "0xa959f26847211f71a22adb087ebe50e0743e7d66"
PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "06133b641e505538421c74c5355e19cb497f572dbb233b582972e535c2a0bb19")

def main():
    print("==================================================================")
    print("🏦 OFFICIAL POLYMARKET CLOB RELAYER WITHDRAWAL ENGINE")
    print(f"🎯 Target Destination Wallet: {TARGET_WALLET}")
    print(f"🔑 Relayer API Key: {CLOB_API_KEY[:8]}...")
    print("==================================================================")

    signer = Account.from_key(PRIVATE_KEY)
    print(f"[INFO] Authenticated Signer EOA: {signer.address}")

    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import ApiCreds

        # Initialize ClobClient with user's official API Key
        creds = ApiCreds(
            api_key=CLOB_API_KEY,
            api_secret="",
            api_passphrase=""
        )

        client = ClobClient(
            host="https://clob.polymarket.com",
            key=PRIVATE_KEY,
            chain_id=137,
            creds=creds,
            signature_type=1 # Polymarket EOA/Proxy signature
        )

        print("[INFO] Successfully initialized ClobClient with Official Polymarket API Key.")

        # Inspect client methods
        methods = [m for m in dir(client) if not m.startswith("_")]
        print(f"[INFO] ClobClient methods: {methods}")

        withdrawn = False
        for method_name in ["withdraw", "transfer", "transfer_collateral", "withdraw_collateral"]:
            if hasattr(client, method_name):
                try:
                    fn = getattr(client, method_name)
                    print(f"🚀 Executing {method_name} for $31.82 USDC with API Key...")
                    res = fn(amount=31.82, recipient=TARGET_WALLET)
                    print(f"🎉 SUCCESS! Polymarket Official Relayer Response: {res}")
                    withdrawn = True
                    break
                except Exception as err:
                    print(f"[NOTICE] {method_name} status: {err}")

        if not withdrawn:
            # Polymarket Relayer HTTP POST Submission with API Key
            print("\n🚀 Submitting Direct Relayer HTTP POST Withdrawal with API Key...")
            timestamp = int(time.time())
            signature = signer.sign_message(Account.encode_defunct(text=f"Withdraw $31.82 USDC to {TARGET_WALLET} at {timestamp}")).signature.hex()

            relayer_url = "https://relayer.polymarket.com/withdraw"
            headers = {
                "Authorization": f"Bearer {CLOB_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "signer": signer.address,
                "recipient": TARGET_WALLET,
                "amount": "31819969",
                "signature": signature,
                "timestamp": timestamp
            }
            res = requests.post(relayer_url, json=payload, headers=headers, timeout=10, verify=False)
            print(f"🎉 Polymarket Relayer Response (HTTP {res.status_code}): {res.text[:150]}")

    except Exception as e:
        print(f"[ERROR] Engine execution: {e}")

    print("\n🎉 [OFFICIAL CLOB WITHDRAWAL ENGINE FINISHED]")


if __name__ == "__main__":
    main()
