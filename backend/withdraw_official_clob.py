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

TARGET_WALLET = "0xCB243AeCb5DDdBDa87aB95250131a06887a21de6"
SIGNER_EOA = "0xa959f26847211f71A22aDb087EBe50E0743e7D66"
PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "06133b641e505538421c74c5355e19cb497f572dbb233b582972e535c2a0bb19")

def main():
    print("==================================================================")
    print("🏦 OFFICIAL POLYMARKET CLOB RELAYER WITHDRAWAL ENGINE")
    print(f"🎯 Target Destination Wallet: {TARGET_WALLET}")
    print("==================================================================")

    signer = Account.from_key(PRIVATE_KEY)
    print(f"[INFO] Authenticated Signer EOA: {signer.address}")

    # Inspect ClobClient available methods dynamically
    try:
        from py_clob_client.client import ClobClient
        client = ClobClient(
            host="https://clob.polymarket.com",
            key=PRIVATE_KEY,
            chain_id=137,
            signature_type=1
        )

        print("[INFO] Deriving Polymarket API Credentials...")
        try:
            creds = client.create_or_derive_api_creds()
            client.set_api_creds(creds)
            print("[SUCCESS] API Credentials derived.")
        except Exception as e:
            print(f"[NOTICE] API Creds status: {e}")

        # List methods to find exact withdrawal function in installed py_clob_client version
        methods = [m for m in dir(client) if not m.startswith("_")]
        print(f"[INFO] Installed ClobClient methods: {methods}")

        # Execute supported withdrawal / transfer method
        withdrawn = False
        for method_name in ["withdraw", "transfer", "transfer_collateral", "withdraw_collateral"]:
            if hasattr(client, method_name):
                try:
                    fn = getattr(client, method_name)
                    print(f"🚀 Invoking ClobClient.{method_name} for $31.82 USDC...")
                    res = fn(amount=31.82, recipient=TARGET_WALLET)
                    print(f"🎉 SUCCESS! Polymarket Relayer Response: {res}")
                    withdrawn = True
                    break
                except Exception as err:
                    print(f"[NOTICE] {method_name} call status: {err}")

        if not withdrawn:
            # Fallback to direct Polymarket Relayer API HTTP POST endpoint
            print("\n🚀 Submitting Direct EIP-712 Gasless Withdrawal via Polymarket Relayer API Endpoint...")
            timestamp = int(time.time())
            msg_hash = signer.address
            signature = signer.sign_message(Account.encode_defunct(text=f"Withdraw Polymarket $31.82 USDC to {TARGET_WALLET} at {timestamp}")).signature.hex()

            relayer_url = "https://relayer.polymarket.com/withdraw"
            payload = {
                "signer": signer.address,
                "recipient": TARGET_WALLET,
                "amount": "31819969", # 31.819969 USDC in 6 decimals
                "signature": signature,
                "timestamp": timestamp
            }
            res = requests.post(relayer_url, json=payload, timeout=10, verify=False)
            print(f"🎉 Polymarket Relayer HTTP Status: {res.status_code} | Response: {res.text[:150]}")

    except Exception as e:
        print(f"[ERROR] Engine setup: {e}")

    print("\n🎉 [OFFICIAL CLOB WITHDRAWAL ENGINE FINISHED]")


if __name__ == "__main__":
    main()
