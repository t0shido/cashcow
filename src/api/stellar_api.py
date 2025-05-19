"""
Stellar API module for interacting with the Stellar network
"""
from typing import Dict, List, Optional, Union
from decimal import Decimal
import time

from stellar_sdk import (
    Server, Keypair, TransactionBuilder, Network, Asset, 
    Operation, ChangeTrust, Payment, PathPaymentStrictReceive,
    PathPaymentStrictSend, ManageBuyOffer, ManageSellOffer
)
from stellar_sdk.exceptions import BadRequestError, NotFoundError
from loguru import logger

class StellarAPI:
    """Class to interact with the Stellar network"""
    
    def __init__(self, secret_key: str, network: str = 'TESTNET', horizon_url: Optional[str] = None):
        """
        Initialize the Stellar API
        
        Args:
            secret_key: The secret key for the Stellar account
            network: The network to use ('TESTNET' or 'PUBLIC')
            horizon_url: Optional custom Horizon server URL
        """
        self.keypair = Keypair.from_secret(secret_key)
        self.account_id = self.keypair.public_key
        
        # Set network and server
        if network == 'TESTNET':
            self.network = Network.TESTNET_NETWORK_PASSPHRASE
            self.horizon_url = horizon_url or 'https://horizon-testnet.stellar.org'
        else:
            self.network = Network.PUBLIC_NETWORK_PASSPHRASE
            self.horizon_url = horizon_url or 'https://horizon.stellar.org'
        
        self.server = Server(horizon_url=self.horizon_url)
        logger.debug(f"Initialized Stellar API for account {self.account_id}")
        logger.debug(f"Using network: {network}, Horizon URL: {self.horizon_url}")
    
    def get_account_info(self) -> Dict:
        """
        Get account information
        
        Returns:
            Dict containing account information
        """
        try:
            account = self.server.load_account(self.account_id)
            return {
                'account_id': self.account_id,
                'sequence': account.sequence,
                'balances': account.balances
            }
        except NotFoundError:
            logger.error(f"Account {self.account_id} not found")
            raise
    
    def get_balance(self, asset_code: str = 'XLM', asset_issuer: Optional[str] = None) -> Decimal:
        """
        Get balance for a specific asset
        
        Args:
            asset_code: The asset code (default: XLM)
            asset_issuer: The asset issuer (required for non-native assets)
            
        Returns:
            Decimal balance of the asset
        """
        account = self.server.load_account(self.account_id)
        
        for balance in account.balances:
            if asset_code == 'XLM' and balance.get('asset_type') == 'native':
                return Decimal(balance.get('balance', '0'))
            elif (balance.get('asset_code') == asset_code and 
                  balance.get('asset_issuer') == asset_issuer):
                return Decimal(balance.get('balance', '0'))
        
        return Decimal('0')
    
    def create_asset(self, code: str, issuer: Optional[str] = None) -> Asset:
        """
        Create an asset object
        
        Args:
            code: The asset code
            issuer: The asset issuer (None for XLM)
            
        Returns:
            Asset object
        """
        if code == 'XLM' or code == 'native':
            return Asset.native()
        else:
            if not issuer:
                raise ValueError(f"Issuer is required for asset {code}")
            return Asset(code, issuer)
    
    def trust_asset(self, asset_code: str, asset_issuer: str, limit: Optional[str] = None) -> Dict:
        """
        Create a trustline for an asset
        
        Args:
            asset_code: The asset code
            asset_issuer: The asset issuer
            limit: Optional trust limit
            
        Returns:
            Dict with transaction details
        """
        asset = Asset(asset_code, asset_issuer)
        
        account = self.server.load_account(self.account_id)
        transaction = (
            TransactionBuilder(
                source_account=account,
                network_passphrase=self.network,
                base_fee=100
            )
            .append_change_trust_op(asset=asset, limit=limit)
            .set_timeout(30)
            .build()
        )
        
        transaction.sign(self.keypair)
        response = self.server.submit_transaction(transaction)
        
        logger.info(f"Created trustline for {asset_code} (issuer: {asset_issuer})")
        return {
            'success': True,
            'hash': response['hash'],
            'ledger': response['ledger']
        }
    
    def get_order_book(self, selling_asset: Asset, buying_asset: Asset, limit: int = 20) -> Dict:
        """
        Get order book for a trading pair
        
        Args:
            selling_asset: The asset to sell
            buying_asset: The asset to buy
            limit: Number of orders to return
            
        Returns:
            Dict with order book data
        """
        order_book = self.server.order_book(
            selling=selling_asset,
            buying=buying_asset,
            limit=limit
        ).call()
        
        return order_book
    
    def create_sell_offer(
        self, 
        selling_code: str, 
        selling_issuer: Optional[str], 
        buying_code: str, 
        buying_issuer: Optional[str],
        amount: str,
        price: str,
        offer_id: int = 0
    ) -> Dict:
        """
        Create a sell offer
        
        Args:
            selling_code: Code of the asset to sell
            selling_issuer: Issuer of the asset to sell (None for XLM)
            buying_code: Code of the asset to buy
            buying_issuer: Issuer of the asset to buy (None for XLM)
            amount: Amount to sell
            price: Price in terms of buying asset
            offer_id: Offer ID (0 for new offer)
            
        Returns:
            Dict with transaction details
        """
        selling_asset = self.create_asset(selling_code, selling_issuer)
        buying_asset = self.create_asset(buying_code, buying_issuer)
        
        account = self.server.load_account(self.account_id)
        transaction = (
            TransactionBuilder(
                source_account=account,
                network_passphrase=self.network,
                base_fee=100
            )
            .append_manage_sell_offer_op(
                selling=selling_asset,
                buying=buying_asset,
                amount=amount,
                price=price,
                offer_id=offer_id
            )
            .set_timeout(30)
            .build()
        )
        
        transaction.sign(self.keypair)
        response = self.server.submit_transaction(transaction)
        
        logger.info(
            f"Created sell offer: {amount} {selling_code} for {buying_code} at price {price}"
        )
        return {
            'success': True,
            'hash': response['hash'],
            'ledger': response['ledger']
        }
    
    def create_buy_offer(
        self, 
        buying_code: str, 
        buying_issuer: Optional[str], 
        selling_code: str, 
        selling_issuer: Optional[str],
        amount: str,
        price: str,
        offer_id: int = 0
    ) -> Dict:
        """
        Create a buy offer
        
        Args:
            buying_code: Code of the asset to buy
            buying_issuer: Issuer of the asset to buy (None for XLM)
            selling_code: Code of the asset to sell
            selling_issuer: Issuer of the asset to sell (None for XLM)
            amount: Amount to buy
            price: Price in terms of selling asset
            offer_id: Offer ID (0 for new offer)
            
        Returns:
            Dict with transaction details
        """
        buying_asset = self.create_asset(buying_code, buying_issuer)
        selling_asset = self.create_asset(selling_code, selling_issuer)
        
        account = self.server.load_account(self.account_id)
        transaction = (
            TransactionBuilder(
                source_account=account,
                network_passphrase=self.network,
                base_fee=100
            )
            .append_manage_buy_offer_op(
                buying=buying_asset,
                selling=selling_asset,
                amount=amount,
                price=price,
                offer_id=offer_id
            )
            .set_timeout(30)
            .build()
        )
        
        transaction.sign(self.keypair)
        response = self.server.submit_transaction(transaction)
        
        logger.info(
            f"Created buy offer: {amount} {buying_code} with {selling_code} at price {price}"
        )
        return {
            'success': True,
            'hash': response['hash'],
            'ledger': response['ledger']
        }
    
    def cancel_offer(self, offer_id: int) -> Dict:
        """
        Cancel an existing offer
        
        Args:
            offer_id: ID of the offer to cancel
            
        Returns:
            Dict with transaction details
        """
        # To cancel an offer, we update it with amount=0
        account = self.server.load_account(self.account_id)
        
        # First, we need to get the offer details
        offers = self.server.offers().for_account(self.account_id).call()
        offer = None
        
        for record in offers['_embedded']['records']:
            if int(record['id']) == offer_id:
                offer = record
                break
        
        if not offer:
            raise ValueError(f"Offer with ID {offer_id} not found")
        
        # Get the assets from the offer
        if offer['selling']['asset_type'] == 'native':
            selling_asset = Asset.native()
        else:
            selling_asset = Asset(
                offer['selling']['asset_code'], 
                offer['selling']['asset_issuer']
            )
        
        if offer['buying']['asset_type'] == 'native':
            buying_asset = Asset.native()
        else:
            buying_asset = Asset(
                offer['buying']['asset_code'], 
                offer['buying']['asset_issuer']
            )
        
        # Create a transaction to cancel the offer
        transaction = (
            TransactionBuilder(
                source_account=account,
                network_passphrase=self.network,
                base_fee=100
            )
            .append_manage_sell_offer_op(
                selling=selling_asset,
                buying=buying_asset,
                amount="0",  # Setting amount to 0 cancels the offer
                price="1",   # Price doesn't matter when cancelling
                offer_id=offer_id
            )
            .set_timeout(30)
            .build()
        )
        
        transaction.sign(self.keypair)
        response = self.server.submit_transaction(transaction)
        
        logger.info(f"Cancelled offer with ID {offer_id}")
        return {
            'success': True,
            'hash': response['hash'],
            'ledger': response['ledger']
        }
    
    def get_active_offers(self) -> List[Dict]:
        """
        Get all active offers for the account
        
        Returns:
            List of active offers
        """
        offers = self.server.offers().for_account(self.account_id).call()
        return offers['_embedded']['records']
    
    def send_payment(
        self, 
        destination: str, 
        asset_code: str, 
        amount: str, 
        asset_issuer: Optional[str] = None,
        memo_text: Optional[str] = None
    ) -> Dict:
        """
        Send a payment
        
        Args:
            destination: Destination account ID
            asset_code: Code of the asset to send
            amount: Amount to send
            asset_issuer: Issuer of the asset (None for XLM)
            memo_text: Optional memo text
            
        Returns:
            Dict with transaction details
        """
        asset = self.create_asset(asset_code, asset_issuer)
        
        account = self.server.load_account(self.account_id)
        transaction_builder = TransactionBuilder(
            source_account=account,
            network_passphrase=self.network,
            base_fee=100
        )
        
        # Add memo if provided
        if memo_text:
            transaction_builder.add_text_memo(memo_text)
        
        # Add payment operation
        transaction_builder.append_payment_op(
            destination=destination,
            asset=asset,
            amount=amount
        )
        
        # Build and sign transaction
        transaction = transaction_builder.set_timeout(30).build()
        transaction.sign(self.keypair)
        
        # Submit transaction
        response = self.server.submit_transaction(transaction)
        
        logger.info(f"Sent {amount} {asset_code} to {destination}")
        return {
            'success': True,
            'hash': response['hash'],
            'ledger': response['ledger']
        }
