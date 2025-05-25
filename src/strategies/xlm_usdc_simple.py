"""
Swing Trading Strategy for XLM/USDC on the Stellar Network

This strategy uses a combination of percentage-based price movements and time-based conditions:
1. Initially sells 3 XLM to establish a reference price
2. Buys XLM when any of these conditions are met:
   - Price drops 2% below last sell price
   - 5 hours have passed since last sell without a 2% drop
   - XLM price drops 3% within a 12-hour period
3. Sells XLM when price rises 5% above our last buy price
4. Repeats this cycle to capture price movements while protecting against extended downtrends
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
    Swing trading strategy for XLM/USDC that capitalizes on price movements:
    - Buys when price drops 2% from last sell OR 5 hours have passed since selling OR price drops 3% in 12 hours
    - Sells when price rises 5% from last buy
    - Checks price every minute
    - Tracks price history with timestamps
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
        self.sell_rise_percentage = Decimal('0.05')  # Sell when price rises 5%
        self.initial_reference_amount = Decimal('3')  # Sell 3 XLM initially to establish reference
        self.buy_timeout_hours = 5  # Buy back in after 5 hours if no 2% drop
        self.price_drop_lookback_hours = 12  # Lookback window for price drop detection
        self.significant_drop_percentage = Decimal('0.03')  # Buy when price drops 3% in lookback window
        self.trading_enabled = getattr(settings, 'trading_enabled', True)
        
        # State variables
        self.last_price_check = 0
        self.last_sell_price = None
        self.last_buy_price = None
        self.last_sell_time = None  # Timestamp of last sell
        self.last_buy_time = None   # Timestamp of last buy
        self.waiting_for_buy = False  # True if we've sold and are waiting to buy
        self.waiting_for_sell = False  # True if we've bought and are waiting to sell
        self.initial_reference_set = False
        
        # Price history tracking with timestamps
        self.price_history = []  # List of (timestamp, price) tuples
        
        # Try to load state from file
        self.state_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                      'data', 'xlm_usdc_state.json')
        self._load_state()
        
        logger.info(f"Initialized {self.name} swing trading strategy")
        logger.info(f"Buy when price drops: {self.buy_drop_percentage * 100}%")
        logger.info(f"Buy timeout: {self.buy_timeout_hours} hours")
        logger.info(f"Buy on {self.significant_drop_percentage * 100}% drop in {self.price_drop_lookback_hours} hours")
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
            
    def detect_significant_drop(self, lookback_hours: int, drop_percentage: Decimal) -> bool:
        """
        Detect if there's been a significant price drop within the lookback window
        
        Args:
            lookback_hours: Number of hours to look back
            drop_percentage: The price drop percentage to detect (e.g., 0.03 for 3%)
            
        Returns:
            bool: True if a significant drop is detected, False otherwise
        """
        if not self.price_history or len(self.price_history) < 2:
            return False
            
        # Get current time and price
        current_time = time.time()
        current_price = self.price_history[-1][1] if self.price_history else None
        
        if current_price is None:
            return False
            
        # Calculate the lookback window timestamp
        lookback_timestamp = current_time - (lookback_hours * 3600)
        
        # Find the highest price within the lookback window
        prices_in_window = [(ts, price) for ts, price in self.price_history 
                           if ts >= lookback_timestamp]
        
        if not prices_in_window:
            return False
            
        highest_price_in_window = max(prices_in_window, key=lambda x: x[1])[1]
        
        # Calculate the percentage drop from the highest price
        if highest_price_in_window > 0:
            price_change = (current_price - highest_price_in_window) / highest_price_in_window
            
            # If price dropped by the specified percentage or more
            if price_change <= -drop_percentage:
                logger.info(f"Detected {abs(price_change) * 100:.2f}% price drop in the last {lookback_hours} hours")
                logger.info(f"Highest price: {highest_price_in_window}, Current price: {current_price}")
                return True
                
        return False
    
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
                    
                    self.last_sell_time = state.get('last_sell_time')
                    self.last_buy_time = state.get('last_buy_time')
                    self.waiting_for_buy = state.get('waiting_for_buy', False)
                    self.waiting_for_sell = state.get('waiting_for_sell', False)
                    self.initial_reference_set = state.get('initial_reference_set', False)
                    
                    # Load price history if it exists
                    if state.get('price_history'):
                        self.price_history = [(entry['timestamp'], Decimal(str(entry['price']))) 
                                            for entry in state['price_history']]
                    
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
                'last_sell_time': self.last_sell_time,
                'last_buy_time': self.last_buy_time,
                'waiting_for_buy': self.waiting_for_buy,
                'waiting_for_sell': self.waiting_for_sell,
                'initial_reference_set': self.initial_reference_set,
                'price_history': [{'timestamp': ts, 'price': float(p)} for ts, p in self.price_history[-100:]]  # Save last 100 prices
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
            self.last_sell_time = time.time()
            self.waiting_for_buy = True
            self.waiting_for_sell = False
            self.initial_reference_set = True
            
            # Update price history
            self.price_history.append((self.last_sell_time, current_price))
            
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
            
            # Add to price history
            current_time = time.time()
            self.price_history.append((current_time, current_price))
            
            # Keep only the last 1000 price points
            if len(self.price_history) > 1000:
                self.price_history = self.price_history[-1000:]
            
            # Check balances
            xlm_balance, usdc_balance = self.check_balances()
            
            # First, establish initial reference if not done yet
            if not self.initial_reference_set:
                logger.info("No initial reference price set. Establishing initial reference...")
                result = self.establish_initial_reference(current_price)
                return {'action': 'initial_reference', 'price': current_price, 'result': result}
            
            # Implement swing trading strategy
            if self.waiting_for_buy and self.last_sell_price and self.last_sell_time:
                # Calculate buy target price (2% below last sell price)
                buy_target_price = self.last_sell_price * (Decimal('1') - self.buy_drop_percentage)
                
                # Calculate how much time has passed since last sell (in hours)
                hours_since_sell = (current_time - self.last_sell_time) / 3600
                
                # Calculate price drop in the last 12 hours
                significant_drop = self.detect_significant_drop(self.price_drop_lookback_hours, self.significant_drop_percentage)
                
                logger.info(f"Waiting to buy. Current price: {current_price}, Target buy price: {buy_target_price}"
                           f" ({self.buy_drop_percentage * 100}% below last sell of {self.last_sell_price})")
                logger.info(f"Hours since last sell: {hours_since_sell:.2f}, Timeout: {self.buy_timeout_hours} hours")
                logger.info(f"Detected {self.significant_drop_percentage * 100}% drop in {self.price_drop_lookback_hours}h lookback: {'Yes' if significant_drop else 'No'}")
                
                # Check all buy conditions
                price_drop_condition = current_price <= buy_target_price
                timeout_condition = hours_since_sell >= self.buy_timeout_hours
                lookback_drop_condition = significant_drop
                
                # If any buy condition is met, execute buy
                if price_drop_condition or timeout_condition or lookback_drop_condition:
                    reason = []
                    if price_drop_condition:
                        reason.append(f"Price dropped {self.buy_drop_percentage * 100}% below last sell")
                    if timeout_condition:
                        reason.append(f"Reached {self.buy_timeout_hours}h timeout since last sell")
                    if lookback_drop_condition:
                        reason.append(f"Detected {self.significant_drop_percentage * 100}% drop in {self.price_drop_lookback_hours}h")
                    
                    logger.info(f"Buy condition met: {', '.join(reason)}. Executing buy at {current_price} USDC.")
                    result = self.execute_buy(current_price, xlm_balance, usdc_balance)
                    
                    if result.get('success'):
                        # Update state
                        self.last_buy_price = current_price
                        self.last_buy_time = current_time
                        self.waiting_for_buy = False
                        self.waiting_for_sell = True
                        self._save_state()
                        
                    return {'action': 'buy', 'price': current_price, 'result': result, 'reason': reason}
                else:
                    # Still waiting for a buy condition to be met
                    return {'action': 'hold', 'reason': 'Waiting for buy condition', 'price': current_price}
                    
            elif self.waiting_for_sell and self.last_buy_price:
                # Calculate sell target price (5% above last buy price)
                sell_target_price = self.last_buy_price * (Decimal('1') + self.sell_rise_percentage)
                
                # Calculate how much time has passed since last buy (in hours)
                hours_since_buy = (current_time - self.last_buy_time) if self.last_buy_time else 0
                hours_since_buy /= 3600
                
                logger.info(f"Waiting to sell. Current price: {current_price}, Target sell price: {sell_target_price}"
                           f" ({self.sell_rise_percentage * 100}% above last buy of {self.last_buy_price})")
                logger.info(f"Hours since last buy: {hours_since_buy:.2f}")
                
                # If price has risen enough, sell
                if current_price >= sell_target_price:
                    logger.info(f"Price {current_price} has risen {self.sell_rise_percentage * 100}% above last buy price {self.last_buy_price}. Executing sell.")
                    result = self.execute_sell(current_price, xlm_balance, usdc_balance)
                    
                    if result.get('success'):
                        # Update state
                        self.last_sell_price = current_price
                        self.last_sell_time = current_time
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
                self.last_buy_time = None
                self.last_sell_time = None
                self._save_state()
                
                return {'action': 'reset', 'reason': 'State inconsistency', 'price': current_price}
                
        except Exception as e:
            logger.error(f"Error in strategy execution: {str(e)}")
            return {'action': 'error', 'error': str(e)}
