"""
Strategy factory for Stellar Trading Bot
"""
from typing import Dict, Type
from loguru import logger

from strategies.base_strategy import BaseStrategy
from strategies.simple_arbitrage import SimpleArbitrageStrategy
from strategies.xlm_usdc_simple import XlmUsdcSimpleStrategy

class StrategyFactory:
    """Factory class to create strategy instances"""
    
    # Registry of available strategies
    _strategies: Dict[str, Type[BaseStrategy]] = {
        'simple_arbitrage': SimpleArbitrageStrategy,
        'xlm_usdc_simple': XlmUsdcSimpleStrategy,
    }
    
    @classmethod
    def get_strategy(cls, strategy_name: str, stellar_api, settings) -> BaseStrategy:
        """
        Get a strategy instance by name
        
        Args:
            strategy_name: Name of the strategy
            stellar_api: StellarAPI instance
            settings: Settings instance
            
        Returns:
            Strategy instance
            
        Raises:
            ValueError: If strategy is not found
        """
        strategy_class = cls._strategies.get(strategy_name)
        
        if not strategy_class:
            available_strategies = ", ".join(cls._strategies.keys())
            logger.error(f"Strategy '{strategy_name}' not found. Available strategies: {available_strategies}")
            raise ValueError(f"Strategy '{strategy_name}' not found")
        
        return strategy_class(stellar_api, settings)
    
    @classmethod
    def register_strategy(cls, name: str, strategy_class: Type[BaseStrategy]) -> None:
        """
        Register a new strategy
        
        Args:
            name: Strategy name
            strategy_class: Strategy class
        """
        cls._strategies[name] = strategy_class
        logger.debug(f"Registered strategy: {name}")
    
    @classmethod
    def get_available_strategies(cls) -> Dict[str, Type[BaseStrategy]]:
        """
        Get all available strategies
        
        Returns:
            Dict of strategy names and classes
        """
        return cls._strategies.copy()
