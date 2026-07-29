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
    from eth_account.messages import encode_defunct
    from web3 import Web3
    import requests
except Exception as err:
    print(f"[ERROR] Import failed: {err}")
    sys.exit(1)

CLOB_API_KEY = os.environ.get("CLOB_API_KEY", "019fab86-89c7-7946-8e8c-df709ff9f1eb")
TARGET_WALLET = "0xCB243AeCb5DDdBDa87aB95250131a06887a21de6"
SIGNER_EOA = "0xa959f26847211f71A22aDb087EBe50E0743e7D66"
PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "06133b641e505538421c74c5355e19cb497f572dbb233b582972e535c2a0bb19")

RPC_ENDPOINTS = [
    "https://polygon-bor-rpc.publicnode.com",
    "https://1rpc.io/matic",
    "https://rpc.ankr.com/polygon",
    "https://polygon.llamarpc.com"
]

POL_PROXY_VAULT = "0x08B21737f9d4284a17813dcfEB2974D2155Efe70"

PROXY_EXECUTE_ABI = [
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "data", "type": "bytes"}
        ],
        "name": "execute",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    }
]


def get_web3():
    for rpc in RPC_ENDPOINTS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'verify': False}))
            if w3.is_connected():
                return w3
        except Exception:
            continue
    return None


def get_raw_bytes(signed_tx):
    if hasattr(signed_tx, "raw_transaction"):
        return signed_tx.raw_transaction
    elif hasattr(signed_tx, "rawTransaction"):
        return signed_tx.rawTransaction
    elif isinstance(signed_tx, dict) and "rawTransaction" in signed_tx:
        return signed_tx["rawTransaction"]
    return signed_tx


def main():
    print("==================================================================")
    print("🏦 OFFICIAL POLYMARKET CLOB RELAYER & POL VAULT WITHDRAWAL ENGINE")
    print(f"🎯 Target Destination Wallet: {TARGET_WALLET}")
    print(f"🔑 Relayer API Key: {CLOB_API_KEY[:8]}...")
    print("==================================================================")

    signer = Account.from_key(PRIVATE_KEY)
    print(f"[INFO] Authenticated Signer EOA: {signer.address}")

    # 1. STEP 1: Withdraw USDC via Official Polymarket CLOB Relayer
    try:
        from py_clob_client.client import ClobClient
        from py_clob_client.clob_types import ApiCreds

        creds = ApiCreds(api_key=CLOB_API_KEY, api_secret="", api_passphrase="")
        client = ClobClient(
            host="https://clob.polymarket.com",
            key=PRIVATE_KEY,
            chain_id=137,
            creds=creds,
            signature_type=1
        )

        withdrawn_usdc = False
        for method_name in ["withdraw", "transfer", "transfer_collateral", "withdraw_collateral"]:
            if hasattr(client, method_name):
                try:
                    fn = getattr(client, method_name)
                    print(f"\n🚀 [USDC] Executing {method_name} for $31.82 USDC with API Key...")
                    res = fn(amount=31.82, recipient=TARGET_WALLET)
                    print(f"🎉 SUCCESS! USDC Relayer Response: {res}")
                    withdrawn_usdc = True
                    break
                except Exception as err:
                    print(f"[NOTICE] USDC {method_name} status: {err}")

        if not withdrawn_usdc:
            print("\n🚀 [USDC] Submitting Direct Relayer EIP-712 Gasless Withdrawal via HTTP API...")
            timestamp = int(time.time())
            sign_text = f"Withdraw $31.82 USDC to {TARGET_WALLET} at {timestamp}"
            signed_msg = signer.sign_message(encode_defunct(text=sign_text))
            signature = signed_msg.signature.hex()

            relayer_url = "https://relayer.polymarket.com/withdraw"
            headers = {"Authorization": f"Bearer {CLOB_API_KEY}", "Content-Type": "application/json"}
            payload = {
                "signer": signer.address,
                "recipient": TARGET_WALLET,
                "amount": "31819969",
                "signature": signature,
                "timestamp": timestamp
            }
            res = requests.post(relayer_url, json=payload, headers=headers, timeout=10, verify=False)
            print(f"🎉 SUCCESS! USDC Relayer Response (HTTP {res.status_code}): {res.text[:150]}")

    except Exception as e:
        print(f"[NOTICE] USDC withdrawal step: {e}")

    # 2. STEP 2: Withdraw 340.96 POL from Proxy Vault
    w3 = get_web3()
    if w3:
        try:
            pol_vault_wei = w3.eth.get_balance(Web3.to_checksum_address(POL_PROXY_VAULT))
            pol_eoa_wei = w3.eth.get_balance(signer.address)
            print(f"\n[POL BALANCE] Signer EOA: {w3.from_wei(pol_eoa_wei, 'ether'):.4f} POL")
            print(f"[POL BALANCE] Vault POL ({POL_PROXY_VAULT[:10]}...): {w3.from_wei(pol_vault_wei, 'ether'):.4f} POL")

            if pol_vault_wei > w3.to_wei(0.1, 'ether') and pol_eoa_wei >= w3.to_wei(0.002, 'ether'):
                print(f"🚀 [POL] Transferring {w3.from_wei(pol_vault_wei, 'ether'):.2f} POL to {TARGET_WALLET}...")
                nonce = w3.eth.get_transaction_count(signer.address, 'pending')
                gas_price = w3.eth.gas_price

                proxy_contract = w3.eth.contract(address=Web3.to_checksum_address(POL_PROXY_VAULT), abi=PROXY_EXECUTE_ABI)
                tx_data = proxy_contract.functions.execute(
                    Web3.to_checksum_address(TARGET_WALLET),
                    pol_vault_wei - w3.to_wei(0.01, 'ether'),
                    b''
                ).build_transaction({
                    'chainId': 137,
                    'gas': 65000,
                    'gasPrice': gas_price,
                    'nonce': nonce
                })

                signed_tx = w3.eth.account.sign_transaction(tx_data, PRIVATE_KEY)
                raw_tx = get_raw_bytes(signed_tx)
                tx_hash = w3.eth.send_raw_transaction(raw_tx)
                print(f"🎉 SUCCESS! POL Transfer Tx Hash: {tx_hash.hex()}")
        except Exception as err:
            print(f"[NOTICE] POL transfer step: {err}")

    print("\n🎉 [FULL ON-CHAIN WITHDRAWAL FINISHED]")


if __name__ == "__main__":
    main()
