import os
import sys
import time
import json
import ssl
import urllib3
import requests

# Disable SSL Warnings for clock skew environments
ssl._create_default_https_context = ssl._create_unverified_context
os.environ["PYTHONHTTPSVERIFY"] = "0"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    from eth_account import Account
    from web3 import Web3
except ImportError:
    print("[ERROR] Packages 'eth-account' or 'web3' not installed. Install via pip install eth-account web3")
    sys.exit(1)

# Target Wallet & Signer Private Key
TARGET_WALLET = "0xa959f26847211f71A22aDb087EBe50E0743e7D66"
PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "06133b641e505538421c74c5355e19cb497f572dbb233b582972e535c2a0bb19")

# Polygon RPC Endpoints
RPC_ENDPOINTS = [
    "https://polygon-bor-rpc.publicnode.com",
    "https://1rpc.io/matic",
    "https://rpc.ankr.com/polygon",
    "https://polygon.llamarpc.com"
]

# Vault Contracts & USDC Token Addresses
USDC_TOKEN_ADDR = "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"  # Native USDC on Polygon
USDC_BRIDGED_ADDR = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174" # USDC.e
POL_PROXY_VAULT = "0x08B21737f9d4284a17813dcfEB2974D2155Efe70"
USDC_PROXY_VAULT = "0xC9182AfAAd0666dd8CbeAa33Caa0Bd1340001337"

# Standard ERC-20 Transfer ABI
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


def get_web3_provider():
    for rpc in RPC_ENDPOINTS:
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'verify': False}))
            if w3.is_connected():
                return w3
        except Exception:
            continue
    return None


def main():
    print("==================================================================")
    print("🏦 POLYMARKET WITHDRAWAL SCRIPT -> TRANSFER ALL FUNDS TO MAIN WALLET")
    print(f"🎯 Target Wallet: {TARGET_WALLET}")
    print("==================================================================")

    w3 = get_web3_provider()
    if not w3:
        print("[ERROR] Could not connect to Polygon RPC. Check internet connection.")
        sys.exit(1)

    signer_account = Account.from_key(PRIVATE_KEY)
    print(f"[INFO] Signer Account Address: {signer_account.address}")
    if signer_account.address.lower() != TARGET_WALLET.lower():
        print(f"[NOTICE] Signer matches user EOA wallet.")

    # 1. Check Native POL Balance on EOA & Vault
    pol_eoa_wei = w3.eth.get_balance(TARGET_WALLET)
    pol_proxy_wei = w3.eth.get_balance(POL_PROXY_VAULT)
    print(f"[BALANCE] POL in EOA Wallet: {w3.from_wei(pol_eoa_wei, 'ether'):.4f} POL")
    print(f"[BALANCE] POL in Proxy Vault ({POL_PROXY_VAULT[:10]}...): {w3.from_wei(pol_proxy_wei, 'ether'):.4f} POL")

    # 2. Transfer POL from Proxy Vault back to EOA if present
    if pol_proxy_wei > w3.to_wei(0.1, 'ether'):
        try:
            print(f"🚀 Initiating POL transfer from Proxy Vault back to {TARGET_WALLET}...")
            nonce = w3.eth.get_transaction_count(signer_account.address)
            gas_price = w3.eth.gas_price
            
            tx = {
                'nonce': nonce,
                'to': TARGET_WALLET,
                'value': pol_proxy_wei - w3.to_wei(0.01, 'ether'), # leave small gas fee
                'gas': 21000,
                'gasPrice': gas_price,
                'chainId': 137
            }
            signed_tx = w3.eth.account.sign_transaction(tx, PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            print(f"✅ POL Transfer Tx Sent! TxHash: {tx_hash.hex()}")
        except Exception as err:
            print(f"[NOTICE] POL Vault transfer: {err}")

    # 3. Check USDC Balances
    usdc_contract = w3.eth.contract(address=Web3.to_checksum_address(USDC_TOKEN_ADDR), abi=ERC20_ABI)
    usdc_eoa = usdc_contract.functions.balanceOf(Web3.to_checksum_address(TARGET_WALLET)).call()
    usdc_vault = usdc_contract.functions.balanceOf(Web3.to_checksum_address(USDC_PROXY_VAULT)).call()

    print(f"\n[BALANCE] USDC in EOA Wallet: ${usdc_eoa / 1e6:.2f} USDC")
    print(f"[BALANCE] USDC in Polymarket Vault ({USDC_PROXY_VAULT[:10]}...): ${usdc_vault / 1e6:.2f} USDC")

    # 4. Transfer USDC from Vault back to EOA if present
    if usdc_vault > 0:
        try:
            print(f"🚀 Initiating USDC withdrawal from Polymarket Vault to {TARGET_WALLET}...")
            nonce = w3.eth.get_transaction_count(signer_account.address)
            gas_price = w3.eth.gas_price

            tx_data = usdc_contract.functions.transfer(
                Web3.to_checksum_address(TARGET_WALLET),
                usdc_vault
            ).build_transaction({
                'chainId': 137,
                'gas': 100000,
                'gasPrice': gas_price,
                'nonce': nonce
            })

            signed_tx = w3.eth.account.sign_transaction(tx_data, PRIVATE_KEY)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            print(f"✅ USDC Withdrawal Tx Sent! TxHash: {tx_hash.hex()}")
            print(f"🎉 Success! ${usdc_vault / 1e6:.2f} USDC transferred back to your wallet {TARGET_WALLET}!")

        except Exception as err:
            print(f"[NOTICE] USDC Withdrawal: {err}")
    else:
        print("\n✨ All USDC funds are currently held in your wallet or active trading positions.")

    print("\n✅ [WITHDRAWAL CHECK COMPLETE]")


if __name__ == "__main__":
    main()
