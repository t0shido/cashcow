#!/usr/bin/env python3
"""
Utility script to set up a USDC trustline for the Stellar Trading Bot
"""
import os
from dotenv import load_dotenv
from stellar_sdk import (
    Asset, Keypair, Network, Server, TransactionBuilder
)

def setup_usdc_trustline():
    """Set up a trustline for USDC on the account"""
    # Load environment variables from .env file
    load_dotenv()
    
    # Get the secret key from environment variables
    secret_key = os.getenv('STELLAR_SECRET_KEY')
    if not secret_key:
        print("Error: STELLAR_SECRET_KEY not found in environment variables")
        return False
    
    # Get the USDC issuer
    usdc_issuer = os.getenv('QUOTE_ASSET_ISSUER')
    usdc_asset_code = os.getenv('QUOTE_ASSET_USDC', 'USDC')
    
    if not usdc_issuer:
        print("Error: QUOTE_ASSET_ISSUER not found in environment variables")
        return False
        
    # Connect to Stellar
    network = os.getenv('STELLAR_NETWORK', 'PUBLIC')
    if network == 'TESTNET':
        horizon_url = os.getenv('HORIZON_URL', 'https://horizon-testnet.stellar.org')
        network_passphrase = Network.TESTNET_NETWORK_PASSPHRASE
    else:
        horizon_url = os.getenv('HORIZON_URL', 'https://horizon.stellar.org')
        network_passphrase = Network.PUBLIC_NETWORK_PASSPHRASE
    
    # Set up server and keypair
    server = Server(horizon_url)
    keypair = Keypair.from_secret(secret_key)
    public_key = keypair.public_key
    
    print(f"Setting up USDC trustline for account: {public_key}")
    print(f"USDC Issuer: {usdc_issuer}")
    print(f"Network: {network}")
    
    try:
        # Create a trustline for USDC
        account = server.load_account(public_key)
        
        # Create the USDC asset
        usdc = Asset(usdc_asset_code, usdc_issuer)
        
        # Create a transaction to establish a trustline
        transaction = (
            TransactionBuilder(
                source_account=account,
                network_passphrase=network_passphrase,
                base_fee=100
            )
            .append_change_trust_op(
                asset=usdc,
                limit="1000"  # Set a limit of 1000 USDC
            )
            .set_timeout(30)
            .build()
        )
        
        # Sign the transaction
        transaction.sign(keypair)
        
        # Submit the transaction
        response = server.submit_transaction(transaction)
        print("Trustline established successfully!")
        print(f"Transaction Hash: {response['hash']}")
        return True
        
    except Exception as e:
        print(f"Error establishing trustline: {str(e)}")
        return False

if __name__ == "__main__":
    setup_usdc_trustline()
