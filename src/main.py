#!/usr/bin/env python3
"""
Stellar Trading Bot - Main Entry Point

This is the main entry point for the Stellar Trading Bot. It handles:
1. Loading environment variables and configuration
2. Setting up logging
3. Initializing the Stellar API connection
4. Setting up the trading strategy
5. Running the main trading loop
6. Handling graceful shutdown when interrupted

The bot is designed to run continuously, executing the chosen trading strategy
at regular intervals defined by the polling_interval setting.
"""
# Standard library imports
import os                  # Operating system interfaces, used for path operations and environment variables
import time                # Time access and conversions, used for sleep/delay between trading cycles
import signal              # Signal handling to catch Ctrl+C and termination signals for graceful shutdown
import sys                 # System-specific parameters and functions, used by logger

# Third-party library imports
from dotenv import load_dotenv  # Loads environment variables from .env file into os.environ
from loguru import logger       # Advanced logging functionality with better formatting than standard logging

# Local module imports
from config.settings import Settings                  # Configuration management class that loads from environment
from src.api.stellar_api import StellarAPI                # Wrapper for Stellar SDK to simplify network operations
from src.strategies.xlm_usdc_simple import XlmUsdcSimpleStrategy  # XLM/USDC swing trading strategy
from src.utils.logger import setup_logger                 # Custom logger configuration for file and console output

# Global variables
# This flag controls the main loop execution; when set to False, the bot will exit gracefully
running = True

def signal_handler(sig, frame):
    """
    Handle exit signals gracefully
    
    This function is registered as a handler for SIGINT (Ctrl+C) and SIGTERM signals.
    When these signals are received, it sets the global 'running' flag to False,
    which will cause the main loop to exit after the current iteration completes.
    This ensures that any in-progress operations can complete before shutdown.
    
    Args:
        sig: Signal number
        frame: Current stack frame
    """
    global running
    logger.info("Shutting down bot...")
    running = False

def main():
    """
    Main function to run the trading bot
    
    This function performs the following steps:
    1. Loads environment variables from .env file
    2. Sets up logging to both console and file
    3. Initializes the settings from environment variables
    4. Connects to the Stellar network via the StellarAPI
    5. Verifies the account exists and logs its information
    6. Initializes the selected trading strategy
    7. Runs the main trading loop until interrupted
    """
    # Load environment variables from .env file
    # This allows users to configure the bot without changing code
    load_dotenv()
    
    # Setup logger with appropriate configuration
    # This configures logging to both console and a timestamped log file
    setup_logger()
    logger.info("Starting Stellar Trading Bot...")
    
    # Initialize settings from environment variables
    # The Settings class handles validation and default values
    settings = Settings()
    logger.info(f"Network: {settings.network}")
    logger.info(f"Trading pair: {settings.base_asset}/{settings.quote_asset}")
    
    # Initialize Stellar API with the provided credentials
    # This creates a connection to the Stellar network (testnet or public)
    # and sets up the account for trading operations
    stellar_api = StellarAPI(
        secret_key=settings.stellar_secret_key,
        network=settings.network,
        horizon_url=settings.horizon_url
    )
    
    # Check if the account exists on the network and retrieve its information
    # This verifies that the provided secret key is valid and the account is funded
    # If the account doesn't exist or isn't funded, an exception will be raised
    account_info = stellar_api.get_account_info()
    logger.info(f"Account: {account_info['account_id']}")
    
    # Get and log the native XLM balance for quick reference
    # This helps verify that the account has sufficient funds to operate
    logger.info(f"Account balance: {stellar_api.get_balance()}")
    
    # Initialize the XLM/USDC swing trading strategy
    # This strategy buys when price drops and sells when price rises
    strategy = XlmUsdcSimpleStrategy(
        stellar_api=stellar_api,  # API instance for Stellar network operations
        settings=settings         # Configuration settings for the strategy
    )
    
    # Log startup information before entering the main loop
    # This provides confirmation that the bot is running
    logger.info("Bot running with XLM/USDC swing trading strategy")
    logger.info(f"Polling interval: {settings.polling_interval} seconds")
    
    # Main trading loop - this will run continuously until the bot is stopped
    # The 'running' flag is controlled by the signal handler when the process
    # receives an interrupt signal (Ctrl+C) or termination signal
    while running:
        try:
            # Execute one cycle of the trading strategy
            # This is where all the trading logic happens - analyzing market conditions,
            # making trading decisions, and executing trades when appropriate
            # The actual implementation depends on the strategy being used
            strategy.execute()
            
            # Wait for the specified polling interval before the next cycle
            # This prevents excessive API calls and allows time for market conditions to change
            # The polling_interval is configurable in the settings (default: 60 seconds)
            time.sleep(settings.polling_interval)
            
        except Exception as e:
            # Catch and log any errors that occur during strategy execution
            # This prevents the bot from crashing if there's a temporary issue
            # with the network, API, or other external factors
            logger.error(f"Error in main loop: {str(e)}")
            
            # Wait the polling interval before trying again
            # This provides a pause to allow transient issues to resolve
            # before the next execution attempt
            time.sleep(settings.polling_interval)

if __name__ == "__main__":
    # This block only executes when the script is run directly (not imported)
    
    # Register signal handlers for graceful shutdown
    # SIGINT is sent when the user presses Ctrl+C in the terminal
    # SIGTERM is sent when the process is asked to terminate by the system
    # Both signals will trigger our signal_handler function for clean shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run the main function to start the trading bot
    # This is the entry point that initializes everything and starts the main loop
    main()
