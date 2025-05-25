#!/usr/bin/env python3
"""
XLM/USDC Swing Trading Bot - Lightweight Version

This is a simplified version of the Stellar Trading Bot that focuses only on
the XLM/USDC swing trading strategy. It handles:
1. Loading environment variables and configuration
2. Setting up logging
3. Initializing the Stellar API connection
4. Running the XLM/USDC swing trading strategy
5. Handling graceful shutdown when interrupted
"""
import os
import time
import signal
import sys
from datetime import datetime
from dotenv import load_dotenv
from loguru import logger

# Import the necessary components
from src.api.stellar_api import StellarAPI
from src.strategies.xlm_usdc_simple import XlmUsdcSimpleStrategy
from config.settings import Settings

# Global variables
running = True

def signal_handler(sig, frame):
    """Handle exit signals gracefully"""
    global running
    logger.info("Shutting down bot...")
    running = False

def setup_logger():
    """Set up the logger with appropriate configuration"""
    # Remove default logger
    logger.remove()
    
    # Add console logger
    logger.add(
        sys.stdout,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level=os.getenv("LOG_LEVEL", "INFO")
    )
    
    # Add file logger
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(
        log_dir, 
        f"xlm_usdc_trader_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    
    logger.add(
        log_file,
        rotation="10 MB",
        retention="1 week",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=os.getenv("LOG_LEVEL", "INFO")
    )

def main():
    """Main function to run the XLM/USDC trading bot"""
    # Load environment variables from .env file
    load_dotenv()
    
    # Setup logger
    setup_logger()
    logger.info("Starting XLM/USDC Swing Trading Bot...")
    
    # Initialize settings from environment variables
    settings = Settings()
    logger.info(f"Network: {settings.network}")
    logger.info(f"Trading pair: {settings.base_asset}/{settings.quote_asset}")
    
    # Initialize Stellar API with the provided credentials
    stellar_api = StellarAPI(
        secret_key=settings.stellar_secret_key,
        network=settings.network,
        horizon_url=settings.horizon_url
    )
    
    # Check if the account exists on the network
    try:
        account_info = stellar_api.get_account_info()
        logger.info(f"Account: {account_info['account_id']}")
        logger.info(f"Account balance: {stellar_api.get_balance()}")
    except Exception as e:
        logger.error(f"Error accessing Stellar account: {str(e)}")
        logger.error("Please check your STELLAR_SECRET_KEY and network settings.")
        sys.exit(1)
    
    # Initialize the XLM/USDC swing trading strategy
    strategy = XlmUsdcSimpleStrategy(
        stellar_api=stellar_api,
        settings=settings
    )
    
    # Log startup information
    logger.info("Bot running with XLM/USDC swing trading strategy")
    logger.info(f"Polling interval: {settings.polling_interval} seconds")
    
    # Main trading loop
    while running:
        try:
            # Execute one cycle of the trading strategy
            strategy.execute()
            
            # Wait for the specified polling interval before the next cycle
            time.sleep(settings.polling_interval)
            
        except Exception as e:
            # Catch and log any errors
            logger.error(f"Error in main loop: {str(e)}")
            time.sleep(settings.polling_interval)

if __name__ == "__main__":
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the main function
    main()
