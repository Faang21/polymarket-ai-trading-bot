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

TARGET_WALLET = os.environ.get("TARGET_WALLET", "0xCB243AeCb5DDdBDa87aB95250131a06887a21de6")
PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "06133b641e505538421c74c5355e19cb497f572dbb233b582972e535c2a0bb19")

RPC_ENDPOINTS = [
    "https://polygon-bor-rpc.publicnode.com",
    "https://1rpc.io/matic",
    "https://rpc.ankr.com/polygon",
    "https://polygon.llamarpc.com"
]

USDC_NATIVE_ADDR = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"
USDC_BRIDGED_ADDR = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
POL_PROXY_VAULT = "0x08B21737f9d4284a17813dcfEB2974D2155Efe70"
USDC_PROXY_VAULT = "0xC9182AfAAd0666dd8CbeAa33Caa0Bd1340001337"

ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": False,
        "inputs": [{"name": "_to", "type": "address"}, {"name": "_value", "type": "uint256"}],
        "name": "transfer",
        "outputs": [{"name": "success", "type": "bool"}],
        "type": "function"
    }
]

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


def withdraw_token(w3, token_address, signer_acc, to_address, vault_address):
    try:
        token_contract = w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=ERC20_ABI)
        
        bal_eoa = token_contract.functions.balanceOf(Web3.to_checksum_address(to_address)).call()
        bal_vault = token_contract.functions.balanceOf(Web3.to_checksum_address(vault_address)).call()

        print(f"\n--- Checking USDC Token ({token_address[:10]}...) ---")
        print(f"    Target Wallet ({to_address[:10]}...): ${bal_eoa / 1e6:.2f} USDC")
        print(f"    Vault Balance ({vault_address[:10]}...): ${bal_vault / 1e6:.2f} USDC")

        if bal_vault > 0:
            print(f"🚀 Transferring ${bal_vault / 1e6:.2f} USDC from Vault to Target Wallet {to_address}...")
            
            nonce = w3.eth.get_transaction_count(signer_acc.address, 'pending')
            gas_price = w3.eth.gas_price

            proxy_contract = w3.eth.contract(address=Web3.to_checksum_address(vault_address), abi=PROXY_EXECUTE_ABI)
            
            transfer_data = token_contract.functions.transfer(
                Web3.to_checksum_address(to_address),
                bal_vault
            )._encode_transaction_data()

            try:
                tx_data = proxy_contract.functions.execute(
                    Web3.to_checksum_address(token_address),
                    0,
                    bytes.fromhex(transfer_data[2:])
                ).build_transaction({
                    'chainId': 137,
                    'gas': 65000,
                    'gasPrice': gas_price,
                    'nonce': nonce
                })
            except Exception:
                tx_data = token_contract.functions.transfer(
                    Web3.to_checksum_address(to_address),
                    bal_vault
                ).build_transaction({
                    'chainId': 137,
                    'gas': 65000,
                    'gasPrice': gas_price,
                    'nonce': nonce
                })

            signed_tx = w3.eth.account.sign_transaction(tx_data, PRIVATE_KEY)
            raw_tx = get_raw_bytes(signed_tx)
            tx_hash = w3.eth.send_raw_transaction(raw_tx)
            print(f"🎉 SUCCESS! ${bal_vault / 1e6:.2f} USDC Transfer Sent to {to_address}! TxHash: {tx_hash.hex()}")
            return True

    except Exception as e:
        print(f"[NOTICE] USDC Token transfer status: {e}")
    return False


def main():
    print("==================================================================")
    print("🏦 DIRECT BLOCKCHAIN ON-CHAIN WITHDRAWAL ENGINE")
    print(f"🎯 Destination Target Wallet: {TARGET_WALLET}")
    print("==================================================================")

    w3 = get_web3()
    if not w3:
        print("[ERROR] Could not connect to Polygon RPC.")
        sys.exit(1)

    signer_acc = Account.from_key(PRIVATE_KEY)
    print(f"[INFO] Authenticated Signer: {signer_acc.address}")

    # 1. PRIORITY 1: Transfer USDC FIRST while gas is fresh!
    withdraw_token(w3, USDC_NATIVE_ADDR, signer_acc, TARGET_WALLET, USDC_PROXY_VAULT)
    withdraw_token(w3, USDC_BRIDGED_ADDR, signer_acc, TARGET_WALLET, USDC_PROXY_VAULT)

    # 2. PRIORITY 2: Transfer POL Vault Balance
    pol_vault_wei = w3.eth.get_balance(Web3.to_checksum_address(POL_PROXY_VAULT))
    pol_eoa_wei = w3.eth.get_balance(signer_acc.address)
    print(f"\n[POL BALANCE] Signer EOA: {w3.from_wei(pol_eoa_wei, 'ether'):.4f} POL")
    print(f"[POL BALANCE] Vault POL: {w3.from_wei(pol_vault_wei, 'ether'):.4f} POL")
    
    if pol_vault_wei > w3.to_wei(0.1, 'ether'):
        if pol_eoa_wei >= w3.to_wei(0.002, 'ether'):
            try:
                print(f"🚀 Executing POL Vault Transfer ({w3.from_wei(pol_vault_wei, 'ether'):.2f} POL) to {TARGET_WALLET}...")
                nonce = w3.eth.get_transaction_count(signer_acc.address, 'pending')
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
                print(f"🎉 SUCCESS! POL Transfer Sent to {TARGET_WALLET}! TxHash: {tx_hash.hex()}")
            except Exception as err:
                print(f"[NOTICE] POL Transfer status: {err}")

    print("\n🎉 [ON-CHAIN WITHDRAWAL FINISHED]")


if __name__ == "__main__":
    main()
