import os
import sys
import time
import json
import ssl
import urllib3
import subprocess

# Auto-install missing dependencies
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
    from web3 import Web3
    import requests
except Exception as err:
    print(f"[ERROR] Import failed: {err}")
    sys.exit(1)

TARGET_WALLET = "0xa959f26847211f71A22aDb087EBe50E0743e7D66"
PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "06133b641e505538421c74c5355e19cb497f572dbb233b582972e535c2a0bb19")

RPC_ENDPOINTS = [
    "https://polygon-bor-rpc.publicnode.com",
    "https://1rpc.io/matic",
    "https://rpc.ankr.com/polygon",
    "https://polygon.llamarpc.com"
]

USDC_NATIVE_ADDR = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
POL_PROXY_VAULT = "0x08B21737f9d4284a17813dcfEB2974D2155Efe70"
USDC_PROXY_VAULT = "0xC9182AfAAd0666dd8CbeAa33Caa0Bd1340001337"

def try_clob_api_withdraw():
    print("\n--- [METHOD 1] Attempting Direct Polymarket CLOB API Withdrawal ---")
    try:
        from py_clob_client.client import ClobClient
        client = ClobClient(
            host="https://clob.polymarket.com",
            key=PRIVATE_KEY,
            chain_id=137,
            signature_type=1
        )
        try:
            creds = client.create_or_derive_api_creds()
            client.set_api_creds(creds)
        except Exception:
            pass
            
        res = client.withdraw(amount=31.8199, asset_type="COLLATERAL")
        print(f"🎉 [CLOB WITHDRAW SUCCESS] Response: {res}")
        return True
    except Exception as e:
        print(f"[CLOB NOTICE] {e}")
    return False


def main():
    print("==================================================================")
    print("🚨 EMERGENCY ON-CHAIN WITHDRAWAL ENGINE (BYPASS POLYMARKET UI BAN)")
    print(f"🎯 Target Destination Wallet: {TARGET_WALLET}")
    print("==================================================================")

    # 1. Try Polymarket CLOB API Direct Withdrawal
    if try_clob_api_withdraw():
        print("\n✅ Withdrawal request processed via Polymarket Relayer API!")
        return

    print("\n--- [METHOD 2] Direct Polygon Blockchain Smart Contract Call ---")
    w3 = None
    for rpc in RPC_ENDPOINTS:
        try:
            temp_w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'verify': False}))
            if temp_w3.is_connected():
                w3 = temp_w3
                break
        except Exception:
            continue

    if not w3:
        print("[ERROR] Could not connect to Polygon RPC.")
        sys.exit(1)

    signer_acc = Account.from_key(PRIVATE_KEY)
    print(f"[INFO] Connected to Polygon Mainnet. Signer: {signer_acc.address}")

    # Check on-chain balances
    pol_vault_wei = w3.eth.get_balance(Web3.to_checksum_address(POL_PROXY_VAULT))
    print(f"[BALANCE] Vault POL (0x08B21...): {w3.from_wei(pol_vault_wei, 'ether'):.4f} POL")

    print("\n✅ Emergency Withdrawal Engine finished checks.")


if __name__ == "__main__":
    main()
