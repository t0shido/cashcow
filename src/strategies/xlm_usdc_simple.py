"""
Swing Trading Strategy for XLM/USDC on the Stellar Network

This strategy uses percentage-based price movements:
1. Initially sells 1 XLM to establish a reference price
2. Buys XLM when price drops 2% below our last sell price
3. Sells XLM when price rises 3% above our last buy price
4. Repeats this cycle to capture small but frequent price movements
"""
from typing import Dict, Any, Tuple
from decimal import Decimal
import time
import os
import json
from loguru import logger

from strategies.base_strategy import BaseStrategy

class XlmUsdcSimpleStrategy(BaseStrategy):
    """
    Swing trading strategy for XLM/USDC that capitalizes on small price movements:
    - Buys when price drops 2% from last sell
    - Sells when price rises 3% from last buy
    - Checks price every minute
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
        
        # Trading parameters
        self.max_xlm_per_trade = Decimal(str(getattr(settings, 'max_xlm_per_trade', '100')))  # Maximum XLM to buy/sell per trade
        self.max_usdc_per_trade = Decimal(str(getattr(settings, 'max_usdc_per_trade', '30')))  # Maximum USDC to use per trade
        self.price_check_interval = 60  # Check price every minute
        self.buy_drop_percentage = Decimal('0.02')  # Buy when price drops 2%
        self.sell_rise_percentage = Decimal('0.03')  # Sell when price rises 3%
        self.initial_reference_amount = Decimal('1')  # Sell 1 XLM initially to establish reference
        self.trading_enabled = getattr(settings, 'trading_enabled', True)
        
        # State variables
        self.last_price_check = 0
        self.last_sell_price = None
        self.last_buy_price = None
        self.waiting_for_buy = False  # True if we've sold and are waiting to buy
        self.waiting_for_sell = False  # True if we've bought and are waiting to sell
        self.initial_reference_set = False
        
        # Try to load state from file
        self.state_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                      'data', 'xlm_usdc_state.json')
        self._load_state()
        
        logger.info(f"Initialized {self.name} swing trading strategy")
        logger.info(f"Buy when price drops: {self.buy_drop_percentage * 100}%")
        logger.info(f"Sell when price rises: {self.sell_rise_percentage * 100}%")
        logger.info(f"Price check interval: {self.price_check_interval} seconds")
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
    
    def _load_state(self):
        """Load trading state from file if it exists"""
        try:
            # Ensure the data directory exists
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                    
                    # Convert string to Decimal where needed
                    if state.get('last_sell_price'):
                        self.last_sell_price = Decimal(str(state['last_sell_price']))
                    if state.get('last_buy_price'):
                        self.last_buy_price = Decimal(str(state['last_buy_price']))
                    
                    self.waiting_for_buy = state.get('waiting_for_buy', False)
                    self.waiting_for_sell = state.get('waiting_for_sell', False)
                    self.initial_reference_set = state.get('initial_reference_set', False)
                    
                    logger.info(f"Loaded trading state: last_sell_price={self.last_sell_price}, " 
                                f"last_buy_price={self.last_buy_price}, waiting_for_buy={self.waiting_for_buy}, "
                                f"waiting_for_sell={self.waiting_for_sell}")
                                
        except Exception as e:
            logger.warning(f"Failed to load state file: {e}. Will start with fresh state.")
    
    def _save_state(self):
        """Save trading state to file"""
        try:
            # Ensure the data directory exists
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            
            state = {
                'last_sell_price': float(self.last_sell_price) if self.last_sell_price else None,
                'last_buy_price': float(self.last_buy_price) if self.last_buy_price else None,
                'waiting_for_buy': self.waiting_for_buy,
                'waiting_for_sell': self.waiting_for_sell,
                'initial_reference_set': self.initial_reference_set
            }
            
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
                
            logger.debug(f"Saved trading state to {self.state_file}")
            
        except Exception as e:
            logger.error(f"Failed to save state file: {e}")
                
    def establish_initial_reference(self, current_price):
        """
        Establish initial reference price by selling 1 XLM
        
        Args:
            current_price: Current XLM price in USDC
            
        Returns:
            Dict with execution results
        """
        logger.info(f"Establishing initial reference price by selling {self.initial_reference_amount} XLM at {current_price} USDC")
        
        # Check that we have enough XLM (at least 1 XLM + 5 XLM reserve)
        xlm_balance, _ = self.check_balances()
        
        if xlm_balance < (self.initial_reference_amount + Decimal('5')):
            logger.error(f"Not enough XLM to establish reference. Need at least {self.initial_reference_amount + Decimal('5')} XLM.")
            return {'success': False, 'reason': 'Insufficient XLM balance for initial reference'}
        
        # Execute sell order for 1 XLM
        try:
            result = self.stellar_api.create_sell_offer(
                selling_code="XLM",
                selling_issuer=None,  # XLM is native asset
                buying_code=self.settings.quote_asset,
                buying_issuer=self.settings.quote_asset_issuer,
                amount=str(self.initial_reference_amount),
                price=str(current_price)
            )
            
            # Update state
            self.last_sell_price = current_price
            self.waiting_for_buy = True
            self.waiting_for_sell = False
            self.initial_reference_set = True
            
            # Save state
            self._save_state()
            
            logger.info(f"Initial reference sell order placed: {self.initial_reference_amount} XLM at {current_price} USDC/XLM")
            logger.info(f"Waiting for price to drop {self.buy_drop_percentage * 100}% below {current_price} USDC to buy back")
            
            return {'success': True, 'result': result}
            
        except Exception as e:
            logger.error(f"Error establishing initial reference: {str(e)}")
            return {'success': False, 'error': str(e)}
            
    def execute(self) -> Dict[str, Any]:
        """
        Execute the swing trading strategy
        
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
            current_price, _ = self.get_xlm_price()
            logger.info(f"Current XLM price: {current_price} USDC")
            
            # Check balances
            xlm_balance, usdc_balance = self.check_balances()
            
            # First, establish initial reference if not done yet
            if not self.initial_reference_set:
                logger.info("No initial reference price set. Establishing initial reference...")
                result = self.establish_initial_reference(current_price)
                return {'action': 'initial_reference', 'price': current_price, 'result': result}
            
            # Implement swing trading strategy
            if self.waiting_for_buy and self.last_sell_price:
                # Calculate buy target price (2% below last sell price)
                buy_target_price = self.last_sell_price * (Decimal('1') - self.buy_drop_percentage)
                
                logger.info(f"Waiting to buy. Current price: {current_price}, Target buy price: {buy_target_price}"
                           f" ({self.buy_drop_percentage * 100}% below last sell of {self.last_sell_price})")
                
                # If price has dropped enough, buy
                if current_price <= buy_target_price:
                    logger.info(f"Price {current_price} has dropped {self.buy_drop_percentage * 100}% below last sell price {self.last_sell_price}. Executing buy.")
                    result = self.execute_buy(current_price, xlm_balance, usdc_balance)
                    
                    if result.get('success'):
                        # Update state
                        self.last_buy_price = current_price
                        self.waiting_for_buy = False
                        self.waiting_for_sell = True
                        self._save_state()
                        
                    return {'action': 'buy', 'price': current_price, 'result': result}
                else:
                    # Still waiting for price to drop
                    return {'action': 'hold', 'reason': 'Waiting for price to drop for buy', 'price': current_price}
                    
            elif self.waiting_for_sell and self.last_buy_price:
                # Calculate sell target price (3% above last buy price)
                sell_target_price = self.last_buy_price * (Decimal('1') + self.sell_rise_percentage)
                
                logger.info(f"Waiting to sell. Current price: {current_price}, Target sell price: {sell_target_price}"
                           f" ({self.sell_rise_percentage * 100}% above last buy of {self.last_buy_price})")
                
                # If price has risen enough, sell
                if current_price >= sell_target_price:
                    logger.info(f"Price {current_price} has risen {self.sell_rise_percentage * 100}% above last buy price {self.last_buy_price}. Executing sell.")
                    result = self.execute_sell(current_price, xlm_balance, usdc_balance)
                    
                    if result.get('success'):
                        # Update state
                        self.last_sell_price = current_price
                        self.waiting_for_sell = False
                        self.waiting_for_buy = True
                        self._save_state()
                        
                    return {'action': 'sell', 'price': current_price, 'result': result}
                else:
                    # Still waiting for price to rise
                    return {'action': 'hold', 'reason': 'Waiting for price to rise for sell', 'price': current_price}
            
            else:
                # Something is wrong with our state
                logger.warning("Trading state inconsistency detected. Resetting to initial state.")
                self.initial_reference_set = False
                self.waiting_for_buy = False
                self.waiting_for_sell = False
                self.last_buy_price = None
                self.last_sell_price = None
                self._save_state()
                
                return {'action': 'reset', 'reason': 'State inconsistency', 'price': current_price}
                
        except Exception as e:
            logger.error(f"Error in strategy execution: {str(e)}")
            return {'action': 'error', 'error': str(e)}
