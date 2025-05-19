"""
Market data utilities for Stellar Trading Bot
"""
from typing import Dict, List, Tuple, Optional
from decimal import Decimal
import time
import pandas as pd
import numpy as np
from loguru import logger

class MarketDataAnalyzer:
    """Class for analyzing market data from the Stellar DEX"""
    
    def __init__(self, stellar_api):
        """
        Initialize the market data analyzer
        
        Args:
            stellar_api: StellarAPI instance
        """
        self.stellar_api = stellar_api
        self.price_history = {}
    
    def analyze_order_book(
        self, 
        base_asset_code: str, 
        quote_asset_code: str,
        base_asset_issuer: Optional[str] = None,
        quote_asset_issuer: Optional[str] = None,
        depth: int = 20
    ) -> Dict:
        """
        Analyze order book for a trading pair
        
        Args:
            base_asset_code: Base asset code
            quote_asset_code: Quote asset code
            base_asset_issuer: Base asset issuer (None for XLM)
            quote_asset_issuer: Quote asset issuer (None for XLM)
            depth: Order book depth
            
        Returns:
            Dict with analysis results
        """
        # Create assets
        base_asset = self.stellar_api.create_asset(base_asset_code, base_asset_issuer)
        quote_asset = self.stellar_api.create_asset(quote_asset_code, quote_asset_issuer)
        
        # Get order book
        order_book = self.stellar_api.get_order_book(
            selling_asset=base_asset,
            buying_asset=quote_asset,
            limit=depth
        )
        
        # Extract bids and asks
        bids = order_book.get('bids', [])
        asks = order_book.get('asks', [])
        
        # Calculate metrics
        bid_prices = [Decimal(bid['price']) for bid in bids]
        ask_prices = [Decimal(ask['price']) for ask in asks]
        
        bid_amounts = [Decimal(bid['amount']) for bid in bids]
        ask_amounts = [Decimal(ask['amount']) for ask in asks]
        
        # Calculate weighted average prices
        if bid_prices and bid_amounts:
            weighted_bid = sum(p * a for p, a in zip(bid_prices, bid_amounts)) / sum(bid_amounts)
        else:
            weighted_bid = Decimal('0')
        
        if ask_prices and ask_amounts:
            weighted_ask = sum(p * a for p, a in zip(ask_prices, ask_amounts)) / sum(ask_amounts)
        else:
            weighted_ask = Decimal('0')
        
        # Calculate mid price
        if bid_prices and ask_prices:
            best_bid = bid_prices[0]
            best_ask = ask_prices[0]
            mid_price = (best_bid + best_ask) / 2
            spread = (best_ask - best_bid) / best_ask if best_ask > 0 else Decimal('0')
        else:
            best_bid = Decimal('0')
            best_ask = Decimal('0')
            mid_price = Decimal('0')
            spread = Decimal('0')
        
        # Calculate order book imbalance
        total_bid_volume = sum(bid_amounts)
        total_ask_volume = sum(ask_amounts)
        
        if total_bid_volume + total_ask_volume > 0:
            book_imbalance = (total_bid_volume - total_ask_volume) / (total_bid_volume + total_ask_volume)
        else:
            book_imbalance = Decimal('0')
        
        # Calculate liquidity
        liquidity = total_bid_volume + total_ask_volume
        
        # Store current price in history
        pair_key = f"{base_asset_code}_{quote_asset_code}"
        if pair_key not in self.price_history:
            self.price_history[pair_key] = []
        
        self.price_history[pair_key].append({
            'timestamp': time.time(),
            'mid_price': float(mid_price),
            'best_bid': float(best_bid),
            'best_ask': float(best_ask),
            'spread': float(spread),
            'book_imbalance': float(book_imbalance)
        })
        
        # Keep only the last 1000 data points
        if len(self.price_history[pair_key]) > 1000:
            self.price_history[pair_key] = self.price_history[pair_key][-1000:]
        
        return {
            'best_bid': best_bid,
            'best_ask': best_ask,
            'weighted_bid': weighted_bid,
            'weighted_ask': weighted_ask,
            'mid_price': mid_price,
            'spread': spread,
            'book_imbalance': book_imbalance,
            'liquidity': liquidity,
            'total_bid_volume': total_bid_volume,
            'total_ask_volume': total_ask_volume
        }
    
    def calculate_volatility(
        self, 
        base_asset_code: str, 
        quote_asset_code: str,
        window: int = 100
    ) -> Decimal:
        """
        Calculate price volatility
        
        Args:
            base_asset_code: Base asset code
            quote_asset_code: Quote asset code
            window: Window size for volatility calculation
            
        Returns:
            Volatility as decimal
        """
        pair_key = f"{base_asset_code}_{quote_asset_code}"
        
        if pair_key not in self.price_history or len(self.price_history[pair_key]) < 2:
            return Decimal('0')
        
        # Get price history
        history = self.price_history[pair_key][-window:]
        
        if len(history) < 2:
            return Decimal('0')
        
        # Extract mid prices
        prices = [item['mid_price'] for item in history]
        
        # Calculate returns
        returns = [prices[i] / prices[i-1] - 1 for i in range(1, len(prices))]
        
        # Calculate volatility (standard deviation of returns)
        volatility = Decimal(str(np.std(returns)))
        
        return volatility
    
    def detect_trend(
        self, 
        base_asset_code: str, 
        quote_asset_code: str,
        window: int = 100
    ) -> Dict:
        """
        Detect price trend
        
        Args:
            base_asset_code: Base asset code
            quote_asset_code: Quote asset code
            window: Window size for trend detection
            
        Returns:
            Dict with trend information
        """
        pair_key = f"{base_asset_code}_{quote_asset_code}"
        
        if pair_key not in self.price_history or len(self.price_history[pair_key]) < window:
            return {
                'trend': 'neutral',
                'strength': Decimal('0'),
                'current_price': Decimal('0'),
                'start_price': Decimal('0'),
                'change_percent': Decimal('0')
            }
        
        # Get price history
        history = self.price_history[pair_key][-window:]
        
        # Extract mid prices
        prices = [Decimal(str(item['mid_price'])) for item in history]
        
        # Calculate simple moving average
        if len(prices) >= 20:
            short_ma = sum(prices[-20:]) / 20
        else:
            short_ma = sum(prices) / len(prices)
        
        if len(prices) >= 50:
            long_ma = sum(prices[-50:]) / 50
        else:
            long_ma = sum(prices) / len(prices)
        
        # Determine trend
        current_price = prices[-1]
        start_price = prices[0]
        price_change = current_price - start_price
        
        if price_change == 0 or start_price == 0:
            change_percent = Decimal('0')
        else:
            change_percent = (price_change / start_price) * 100
        
        # Determine trend based on moving averages and price change
        if short_ma > long_ma and price_change > 0:
            trend = 'bullish'
            strength = min(abs(change_percent) / 10, Decimal('1'))
        elif short_ma < long_ma and price_change < 0:
            trend = 'bearish'
            strength = min(abs(change_percent) / 10, Decimal('1'))
        else:
            trend = 'neutral'
            strength = Decimal('0')
        
        return {
            'trend': trend,
            'strength': strength,
            'current_price': current_price,
            'start_price': start_price,
            'change_percent': change_percent,
            'short_ma': short_ma,
            'long_ma': long_ma
        }
