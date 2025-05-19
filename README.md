# Stellar Trading Bot

A Python-based trading bot for the Stellar network, designed to be deployed on AWS Lightsail.

## Features

- Automated trading on the Stellar network
- Real-time market data analysis
- Configurable trading strategies
- Secure key management
- Logging and performance tracking

## Project Structure

```
tradebot/
├── config/           # Configuration files
├── logs/             # Log files
├── src/              # Source code
│   ├── api/          # API connections
│   ├── strategies/   # Trading strategies
│   ├── utils/        # Utility functions
│   └── main.py       # Main entry point
├── tests/            # Test files
├── .env.example      # Example environment variables
├── requirements.txt  # Python dependencies
└── README.md         # This file
```

## Setup

1. Clone this repository:
   ```
   git clone https://github.com/t0shido/cashcow.git
   cd cashcow
   ```

2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

3. Set up your environment variables (see detailed instructions below)

4. Run the bot:
   ```
   python src/main.py
   ```

## Environment Setup

This bot requires a `.env` file with your Stellar account credentials and trading parameters. Follow these steps to set it up:

### 1. Creating your .env file

Create a `.env` file in the root directory of the project by copying the example file:

```
cp .env.example .env
```

### 2. Obtaining Stellar Credentials

If you don't already have a Stellar account:

1. Generate a new Stellar key pair using one of these methods:
   - Using Stellar Laboratory: Visit [Stellar Laboratory](https://laboratory.stellar.org/#account-creator?network=test) and generate a keypair
   - Using the Stellar CLI: Run `stellar account generate` if you have the Stellar CLI installed

2. Fund your account:
   - For testnet: Use the [Stellar Friendbot](https://laboratory.stellar.org/#account-creator?network=test)
   - For mainnet: Transfer XLM from an exchange or another account

### 3. Configure your .env file

Edit your `.env` file and add your account credentials and trading parameters:

```
# Stellar account credentials
STELLAR_SECRET_KEY=S...      # Your Stellar secret key (starts with 'S')
STELLAR_PUBLIC_KEY=G...      # Your Stellar public key (starts with 'G')

# Network settings
STELLAR_NETWORK=TESTNET      # Use TESTNET for testing, PUBLIC for mainnet
HORIZON_URL=https://horizon-testnet.stellar.org  # Network URL

# Trading parameters
BASE_ASSET=XLM
QUOTE_ASSET=USDC
QUOTE_ASSET_ISSUER=GBBD47IF6LWK7P7MDEVSCWR7DPUWV3NY3DTQEVFL4NAT4AQH3ZLLFLA5
TRADE_AMOUNT=10              # Amount in base asset
MAX_SPREAD=0.01              # Maximum spread (1%)
MIN_PROFIT=0.005             # Minimum profit (0.5%)

# XLM/USDC strategy settings
BUY_THRESHOLD=0.2            # Buy XLM when price is below this USD value
SELL_THRESHOLD=0.3           # Sell XLM when price is above this USD value
MAX_XLM_PER_TRADE=100        # Maximum XLM to buy/sell per trade
MAX_USDC_PER_TRADE=30        # Maximum USDC to use per trade
PRICE_CHECK_INTERVAL=300     # Seconds between price checks
TRADING_ENABLED=true         # Enable/disable trading

# Bot settings
POLLING_INTERVAL=60          # Seconds between market checks
STRATEGY=xlm_usdc_simple     # Strategy name

# Logging
LOG_LEVEL=INFO
```

### 4. Security Best Practices

⚠️ **IMPORTANT SECURITY WARNINGS** ⚠️

- **NEVER commit your `.env` file to git** or share it publicly
- **NEVER share your Stellar secret key** (the one that starts with 'S') with anyone
- The `.gitignore` file is set up to exclude your `.env` file automatically
- For production use, consider using a secure secrets manager
- Regularly rotate your keys for enhanced security
- Use a dedicated trading account with only the funds you're willing to trade
- Start with the testnet before moving to mainnet

## Testing

Before running the bot with real funds:

1. Set `STELLAR_NETWORK=TESTNET` in your `.env` file
2. Fund your testnet account using Friendbot
3. Run the bot to ensure it functions correctly
4. Check logs in the `logs/` directory for any issues

## Deployment

Instructions for deploying to AWS Lightsail are included in the `deployment/` directory.

## Monitoring and Maintenance

- Check the log files regularly in the `logs/` directory
- Monitor your Stellar account using [Stellar Expert](https://stellar.expert/)
- Periodically review trading performance and adjust strategy parameters as needed
