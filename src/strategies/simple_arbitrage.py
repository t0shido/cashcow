"""
Simple arbitrage strategy for Stellar Trading Bot
"""
from typing import Dict, Any, List, Tuple
from decimal import Decimal
import time

from loguru import logger
from stellar_sdk import Asset

from strategies.base_strategy import BaseStrategy

class SimpleArbitrageStrategy(BaseStrategy):
    """
    Simple arbitrage strategy that looks for price differences
    between different trading pairs on the Stellar DEX
    """
    
    def __init__(self, stellar_api, settings):
        """
        Initialize the strategy
        
        Args:
            stellar_api: StellarAPI instance
            settings: Settings instance
        """
        super().__init__(stellar_api, settings)
        self.name = "simple_arbitrage"
        
        # Create assets
        self.base_asset = self._create_asset(settings.base_asset)
        self.quote_asset = self._create_asset(
            settings.quote_asset, 
            settings.quote_asset_issuer
        )
        
        # Set trading parameters
        self.trade_amount = settings.trade_amount
        self.max_spread = settings.max_spread
        self.min_profit = settings.min_profit
        
        logger.info(f"Initialized {self.name} strategy")
        logger.info(f"Trading pair: {settings.base_asset}/{settings.quote_asset}")
        logger.info(f"Trade amount: {self.trade_amount} {settings.base_asset}")
        logger.info(f"Max spread: {self.max_spread * 100}%")
        logger.info(f"Min profit: {self.min_profit * 100}%")
    
    def _create_asset(self, code: str, issuer: str = None) -> Asset:
        """
        Create an asset object
        
        Args:
            code: Asset code
            issuer: Asset issuer (None for XLM)
            
        Returns:
            Asset object
        """
        if code == 'XLM':
            return Asset.native()
        else:
            if not issuer:
                raise ValueError(f"Issuer is required for asset {code}")
            return Asset(code, issuer)
    
    def _get_best_prices(self) -> Tuple[Decimal, Decimal]:
        """
        Get best bid and ask prices
        
        Returns:
            Tuple of (best_bid, best_ask)
        """
        order_book = self.stellar_api.get_order_book(
            selling_asset=self.base_asset,
            buying_asset=self.quote_asset
        )
        
        # Get best bid (highest price someone is willing to buy base asset)
        bids = order_book.get('bids', [])
        best_bid = Decimal(bids[0].get('price', '0')) if bids else Decimal('0')
        
        # Get best ask (lowest price someone is willing to sell base asset)
        asks = order_book.get('asks', [])
        best_ask = Decimal(asks[0].get('price', '0')) if asks else Decimal('0')
        
        return best_bid, best_ask
    
    def _check_arbitrage_opportunity(self) -> Dict[str, Any]:
        """
        Check for arbitrage opportunities
        
        Returns:
            Dict with opportunity details
        """
        # Get best prices
        best_bid, best_ask = self._get_best_prices()
        
        if best_bid == Decimal('0') or best_ask == Decimal('0'):
            logger.warning("No valid prices found in order book")
            return {
                'opportunity': False,
                'reason': "No valid prices found"
            }
        
        # Calculate spread
        spread = (best_ask - best_bid) / best_ask
        
        # Check if spread is large enough for arbitrage
        if spread > self.max_spread:
            # Calculate potential profit
            potential_profit = (best_bid - best_ask) * self.trade_amount
            profit_percentage = spread - self.settings.max_spread
            
            if profit_percentage >= self.min_profit:
                logger.info(f"Arbitrage opportunity found!")
                logger.info(f"Spread: {spread:.4%}")
                logger.info(f"Best bid: {best_bid}")
                logger.info(f"Best ask: {best_ask}")
                logger.info(f"Potential profit: {potential_profit} {self.settings.quote_asset}")
                logger.info(f"Profit percentage: {profit_percentage:.4%}")
                
                return {
                    'opportunity': True,
                    'best_bid': best_bid,
                    'best_ask': best_ask,
                    'spread': spread,
                    'profit_percentage': profit_percentage,
                    'potential_profit': potential_profit
                }
        
        logger.debug(f"No arbitrage opportunity. Spread: {spread:.4%}")
        return {
            'opportunity': False,
            'reason': f"Spread too small ({spread:.4%})"
        }
    
    def _execute_arbitrage(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute arbitrage trade
        
        Args:
            opportunity: Opportunity details
            
        Returns:
            Dict with execution results
        """
        # First, buy at the best ask price
        buy_result = self.stellar_api.create_buy_offer(
            buying_code=self.settings.base_asset,
            buying_issuer=None if self.settings.base_asset == 'XLM' else self.settings.base_asset_issuer,
            selling_code=self.settings.quote_asset,
            selling_issuer=self.settings.quote_asset_issuer,
            amount=str(self.trade_amount),
            price=str(opportunity['best_ask'])
        )
        
        logger.info(f"Buy order placed: {buy_result}")
        
        # Wait for the buy order to be processed
        time.sleep(5)
        
        # Then, sell at the best bid price
        sell_result = self.stellar_api.create_sell_offer(
            selling_code=self.settings.base_asset,
            selling_issuer=None if self.settings.base_asset == 'XLM' else self.settings.base_asset_issuer,
            buying_code=self.settings.quote_asset,
            buying_issuer=self.settings.quote_asset_issuer,
            amount=str(self.trade_amount),
            price=str(opportunity['best_bid'])
        )
        
        logger.info(f"Sell order placed: {sell_result}")
        
        return {
            'success': True,
            'buy_result': buy_result,
            'sell_result': sell_result
        }
    
    def execute(self) -> Dict[str, Any]:
        """
        Execute the trading strategy
        
        Returns:
            Dict with execution results
        """
        try:
            # Check account balance
            base_balance = self.stellar_api.get_balance(
                asset_code=self.settings.base_asset,
                asset_issuer=None if self.settings.base_asset == 'XLM' else self.settings.base_asset_issuer
            )
            
            quote_balance = self.stellar_api.get_balance(
                asset_code=self.settings.quote_asset,
                asset_issuer=self.settings.quote_asset_issuer
            )
            
            logger.debug(f"Current balance: {base_balance} {self.settings.base_asset}")
            logger.debug(f"Current balance: {quote_balance} {self.settings.quote_asset}")
            
            # Check for arbitrage opportunity
            opportunity = self._check_arbitrage_opportunity()
            
            if opportunity['opportunity']:
                # Execute arbitrage if opportunity exists
                return self._execute_arbitrage(opportunity)
            else:
                return {
                    'success': False,
                    'reason': opportunity['reason']
                }
                
        except Exception as e:
            logger.error(f"Error executing strategy: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }
