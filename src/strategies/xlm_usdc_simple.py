"""
Simple XLM/USDC trading strategy for Stellar Trading Bot
"""
from typing import Dict, Any, Tuple
from decimal import Decimal
import time
from loguru import logger

from strategies.base_strategy import BaseStrategy

class XlmUsdcSimpleStrategy(BaseStrategy):
    """
    Simple XLM/USDC trading strategy that buys low and sells high
    based on predefined price thresholds.
    """
    
    def __init__(self, stellar_api, settings):
        """
        Initialize the strategy
        
        Args:
            stellar_api: StellarAPI instance
            settings: Settings instance
        """
        super().__init__(stellar_api, settings)
        self.name = "xlm_usdc_simple"
        
        # Create assets
        self.xlm_asset = self.stellar_api.create_asset("XLM")  # Native asset
        self.usdc_asset = self.stellar_api.create_asset(
            settings.quote_asset, 
            settings.quote_asset_issuer
        )
        
        # Set trading parameters from settings or defaults
        self.buy_threshold = Decimal(str(getattr(settings, 'buy_threshold', '0.2')))  # Buy XLM when price is below this USD value
        self.sell_threshold = Decimal(str(getattr(settings, 'sell_threshold', '0.3')))  # Sell XLM when price is above this USD value
        self.max_xlm_per_trade = Decimal(str(getattr(settings, 'max_xlm_per_trade', '100')))  # Maximum XLM to buy/sell per trade
        self.max_usdc_per_trade = Decimal(str(getattr(settings, 'max_usdc_per_trade', '30')))  # Maximum USDC to use per trade
        self.price_check_interval = getattr(settings, 'price_check_interval', 300)  # Seconds between price checks
        self.last_trade_time = 0
        self.trading_enabled = getattr(settings, 'trading_enabled', True)
        
        # Initialize state
        self.last_price_check = 0
        
        logger.info(f"Initialized {self.name} strategy")
        logger.info(f"Buy threshold: ${self.buy_threshold}")
        logger.info(f"Sell threshold: ${self.sell_threshold}")
        logger.info(f"Max XLM per trade: {self.max_xlm_per_trade} XLM")
        logger.info(f"Max USDC per trade: {self.max_usdc_per_trade} USDC")
    
    def get_xlm_price(self) -> Tuple[Decimal, Dict]:
        """
        Get current XLM price in USDC
        
        Returns:
            Tuple of (price, order_book_data)
        """
        order_book = self.stellar_api.get_order_book(
            selling_asset=self.xlm_asset,
            buying_asset=self.usdc_asset
        )
        
        # Get best price (lowest ask price - what we'd pay to buy XLM)
        asks = order_book.get('asks', [])
        best_price = Decimal(asks[0].get('price', '0')) if asks else Decimal('0')
        
        return best_price, order_book
    
    def check_balances(self) -> Tuple[Decimal, Decimal]:
        """
        Check account balances
        
        Returns:
            Tuple of (xlm_balance, usdc_balance)
        """
        # Get XLM balance
        xlm_balance = self.stellar_api.get_balance(
            asset_code="XLM"
        )
        
        # Get USDC balance
        usdc_balance = self.stellar_api.get_balance(
            asset_code=self.settings.quote_asset,
            asset_issuer=self.settings.quote_asset_issuer
        )
        
        logger.debug(f"Current balances: {xlm_balance} XLM, {usdc_balance} USDC")
        return xlm_balance, usdc_balance
    
    def execute_buy(self, price: Decimal, xlm_balance: Decimal, usdc_balance: Decimal) -> Dict:
        """
        Execute buy order (Buy XLM with USDC)
        
        Args:
            price: Current XLM price in USDC
            xlm_balance: Current XLM balance
            usdc_balance: Current USDC balance
            
        Returns:
            Dict with execution results
        """
        # Calculate how much to buy
        max_xlm_can_buy = min(
            self.max_xlm_per_trade,  # Max allowed per trade
            usdc_balance / price  # How much we could buy with our USDC
        )
        
        if max_xlm_can_buy < Decimal('1'):
            logger.warning(f"Not enough USDC to buy XLM. Need at least {price} USDC.")
            return {'success': False, 'reason': 'Insufficient USDC balance'}
        
        # Round to 7 decimal places (Stellar precision)
        amount_to_buy = round(max_xlm_can_buy, 7)
        
        # Create the buy offer
        try:
            result = self.stellar_api.create_buy_offer(
                buying_code="XLM",
                buying_issuer=None,  # XLM is native asset
                selling_code=self.settings.quote_asset,
                selling_issuer=self.settings.quote_asset_issuer,
                amount=str(amount_to_buy),
                price=str(price)
            )
            
            logger.info(f"Buy order placed: {amount_to_buy} XLM at {price} USDC/XLM")
            return {'success': True, 'result': result}
        
        except Exception as e:
            logger.error(f"Error placing buy order: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def execute_sell(self, price: Decimal, xlm_balance: Decimal, usdc_balance: Decimal) -> Dict:
        """
        Execute sell order (Sell XLM for USDC)
        
        Args:
            price: Current XLM price in USDC
            xlm_balance: Current XLM balance
            usdc_balance: Current USDC balance
            
        Returns:
            Dict with execution results
        """
        # Keep 5 XLM as reserve (Stellar minimum + fees)
        available_xlm = xlm_balance - Decimal('5')
        
        # Calculate how much to sell
        amount_to_sell = min(
            self.max_xlm_per_trade,  # Max allowed per trade
            available_xlm  # Available balance
        )
        
        if amount_to_sell <= Decimal('0'):
            logger.warning(f"Not enough XLM to sell. Need more than 5 XLM.")
            return {'success': False, 'reason': 'Insufficient XLM balance'}
        
        # Round to 7 decimal places (Stellar precision)
        amount_to_sell = round(amount_to_sell, 7)
        
        # Create the sell offer
        try:
            result = self.stellar_api.create_sell_offer(
                selling_code="XLM",
                selling_issuer=None,  # XLM is native asset
                buying_code=self.settings.quote_asset,
                buying_issuer=self.settings.quote_asset_issuer,
                amount=str(amount_to_sell),
                price=str(price)
            )
            
            logger.info(f"Sell order placed: {amount_to_sell} XLM at {price} USDC/XLM")
            return {'success': True, 'result': result}
        
        except Exception as e:
            logger.error(f"Error placing sell order: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def execute(self) -> Dict[str, Any]:
        """
        Execute the trading strategy
        
        Returns:
            Dict with execution results
        """
        current_time = time.time()
        
        # Skip if we've checked price recently
        if current_time - self.last_price_check < self.price_check_interval:
            return {'action': 'skip', 'reason': 'Price checked recently'}
        
        self.last_price_check = current_time
        
        try:
            # Check if trading is enabled
            if not self.trading_enabled:
                logger.info("Trading is disabled. Skipping execution.")
                return {'action': 'skip', 'reason': 'Trading disabled'}
            
            # Get current price
            price, order_book = self.get_xlm_price()
            logger.info(f"Current XLM price: {price} USDC")
            
            # Check balances
            xlm_balance, usdc_balance = self.check_balances()
            
            # Implement basic strategy:
            # - If price is below buy threshold, buy XLM
            # - If price is above sell threshold, sell XLM
            # - Otherwise, hold
            
            if price <= self.buy_threshold:
                logger.info(f"Price {price} is below buy threshold {self.buy_threshold}. Executing buy.")
                result = self.execute_buy(price, xlm_balance, usdc_balance)
                return {'action': 'buy', 'price': price, 'result': result}
                
            elif price >= self.sell_threshold:
                logger.info(f"Price {price} is above sell threshold {self.sell_threshold}. Executing sell.")
                result = self.execute_sell(price, xlm_balance, usdc_balance)
                return {'action': 'sell', 'price': price, 'result': result}
                
            else:
                logger.info(f"Price {price} is between thresholds. No action taken.")
                return {'action': 'hold', 'price': price}
                
        except Exception as e:
            logger.error(f"Error in strategy execution: {str(e)}")
            return {'action': 'error', 'error': str(e)}
