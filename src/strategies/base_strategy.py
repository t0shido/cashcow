"""
Base strategy module for Stellar Trading Bot
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

from loguru import logger

class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies
    
    All strategy implementations should inherit from this class
    and implement the execute method.
    """
    
    def __init__(self, stellar_api, settings):
        """
        Initialize the strategy
        
        Args:
            stellar_api: StellarAPI instance
            settings: Settings instance
        """
        self.stellar_api = stellar_api
        self.settings = settings
        self.name = "base"
        logger.debug(f"Initialized {self.name} strategy")
    
    @abstractmethod
    def execute(self) -> Dict[str, Any]:
        """
        Execute the trading strategy
        
        This method should be implemented by all strategy classes.
        
        Returns:
            Dict with execution results
        """
        pass
    
    def get_name(self) -> str:
        """
        Get the strategy name
        
        Returns:
            Strategy name
        """
        return self.name
