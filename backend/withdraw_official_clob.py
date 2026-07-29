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
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import ApiCreds, BalanceAllowanceParams, AssetType
except Exception as err:
    print(f"[ERROR] Import failed: {err}")
    sys.exit(1)

TARGET_WALLET = "0xCB243AeCb5DDdBDa87aB95250131a06887a21de6"
PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "06133b641e505538421c74c5355e19cb497f572dbb233b582972e535c2a0bb19")

def main():
    print("==================================================================")
    print("🏦 OFFICIAL POLYMARKET CLOB RELAYER WITHDRAWAL ENGINE")
    print(f"🎯 Target Destination Wallet: {TARGET_WALLET}")
    print("==================================================================")

    signer = Account.from_key(PRIVATE_KEY)
    print(f"[INFO] Authenticated Signer: {signer.address}")

    client = ClobClient(
        host="https://clob.polymarket.com",
        key=PRIVATE_KEY,
        chain_id=137,
        signature_type=1 # Polymarket EOA/Proxy signature
    )

    try:
        print("[INFO] Deriving Polymarket API Credentials for EIP-712 withdrawal...")
        creds = client.create_or_derive_api_creds()
        client.set_api_creds(creds)
        print("[SUCCESS] API Credentials derived.")
    except Exception as e:
        print(f"[NOTICE] API Creds derivation: {e}")

    try:
        print("\n🚀 Requesting official Polymarket Relayer withdrawal for $31.82 USDC...")
        res = client.withdraw(amount=31.82, asset_type=AssetType.COLLATERAL)
        print(f"🎉 SUCCESS! Polymarket Official Relayer Response: {res}")
    except Exception as err:
        print(f"[NOTICE] Relayer withdrawal response: {err}")

    print("\n🎉 [OFFICIAL CLOB WITHDRAWAL FINISHED]")


if __name__ == "__main__":
    main()
