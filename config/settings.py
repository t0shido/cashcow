"""
Settings module for the Stellar Trading Bot
"""
import os
from loguru import logger

class Settings:
    """Settings class to manage configuration"""
    
    def __init__(self):
        """Initialize settings from environment variables"""
        # Stellar account settings
        self.stellar_secret_key = os.getenv('STELLAR_SECRET_KEY')
        self.stellar_public_key = os.getenv('STELLAR_PUBLIC_KEY')
        
        if not self.stellar_secret_key:
            logger.error("STELLAR_SECRET_KEY not set in environment variables")
            raise ValueError("STELLAR_SECRET_KEY is required")
        
        # Network settings
        self.network = os.getenv('STELLAR_NETWORK', 'TESTNET')
        if self.network not in ['TESTNET', 'PUBLIC']:
            logger.warning(f"Invalid network {self.network}, defaulting to TESTNET")
            self.network = 'TESTNET'
        
        # Set Horizon URL based on network if not explicitly provided
        self.horizon_url = os.getenv('HORIZON_URL')
        if not self.horizon_url:
            if self.network == 'TESTNET':
                self.horizon_url = 'https://horizon-testnet.stellar.org'
            else:
                self.horizon_url = 'https://horizon.stellar.org'
        
        # Trading parameters
        self.base_asset = os.getenv('BASE_ASSET', 'XLM')
        self.quote_asset = os.getenv('QUOTE_ASSET', 'USDC')
        self.quote_asset_issuer = os.getenv('QUOTE_ASSET_ISSUER')
        
        # Convert numeric settings
        try:
            self.trade_amount = float(os.getenv('TRADE_AMOUNT', '10'))
            self.max_spread = float(os.getenv('MAX_SPREAD', '0.01'))
            self.min_profit = float(os.getenv('MIN_PROFIT', '0.005'))
            self.polling_interval = int(os.getenv('POLLING_INTERVAL', '60'))
            
            # XLM/USDC strategy specific settings
            self.buy_threshold = float(os.getenv('BUY_THRESHOLD', '0.2'))
            self.sell_threshold = float(os.getenv('SELL_THRESHOLD', '0.3'))
            self.max_xlm_per_trade = float(os.getenv('MAX_XLM_PER_TRADE', '100'))
            self.max_usdc_per_trade = float(os.getenv('MAX_USDC_PER_TRADE', '30'))
            self.price_check_interval = int(os.getenv('PRICE_CHECK_INTERVAL', '300'))
            self.trading_enabled = os.getenv('TRADING_ENABLED', 'true').lower() == 'true'
        except ValueError as e:
            logger.error(f"Error parsing numeric settings: {str(e)}")
            raise
        
        # Bot settings
        self.strategy = os.getenv('STRATEGY', 'xlm_usdc_simple')
        
        # Logging
        self.log_level = os.getenv('LOG_LEVEL', 'INFO')
    
    def validate(self):
        """Validate settings"""
        if not self.stellar_secret_key:
            return False, "Missing STELLAR_SECRET_KEY"
        
        if self.quote_asset != 'XLM' and not self.quote_asset_issuer:
            return False, f"Missing issuer for {self.quote_asset}"
        
        return True, "Settings valid"
