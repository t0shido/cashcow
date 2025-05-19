# XLM/USDC Simple Trading Bot

This is a simple trading bot that focuses on trading between Stellar Lumens (XLM) and USDC. The bot implements a basic price threshold strategy - buying XLM when the price drops below a certain threshold and selling when it rises above another threshold.

## Setup

1. Make sure you have the required dependencies installed:
   ```
   pip install -r requirements.txt
   ```

2. Create a `.env` file by copying `.env.example`:
   ```
   cp .env.example .env
   ```

3. Edit the `.env` file with your Stellar account details and strategy parameters:
   - Set your `STELLAR_SECRET_KEY` and `STELLAR_PUBLIC_KEY`
   - Set `STELLAR_NETWORK` to either `TESTNET` (recommended for testing) or `PUBLIC` (mainnet)
   - Adjust the `BUY_THRESHOLD` and `SELL_THRESHOLD` values to your preferred XLM price points in USD
   - Set `MAX_XLM_PER_TRADE` and `MAX_USDC_PER_TRADE` to control trade size

## Running the Bot

Run the bot with the following command:

```
python src/main.py
```

The bot will:
1. Connect to the Stellar network
2. Check your account balances
3. Monitor the XLM/USDC price
4. Execute trades based on the configured thresholds

## Strategy Logic

The XLM/USDC simple strategy works as follows:

1. The bot checks the current XLM price in USDC from the Stellar DEX
2. If the price is below the `BUY_THRESHOLD`, it buys XLM (up to `MAX_XLM_PER_TRADE`)
3. If the price is above the `SELL_THRESHOLD`, it sells XLM (up to `MAX_XLM_PER_TRADE`)
4. If the price is between thresholds, it holds and takes no action
5. The bot waits for `PRICE_CHECK_INTERVAL` seconds before checking the price again

## Safety Features

- The bot always keeps at least 5 XLM in your account as reserve (Stellar requirement)
- Trading can be enabled/disabled with the `TRADING_ENABLED` setting
- The bot logs all operations and trades to make monitoring easy
- Price checks are rate-limited to avoid excessive API calls

## Monitoring

All bot operations are logged to both console and log files in the `logs/` directory. You can monitor the bot's activity by watching these logs.

## Important Note

This is a simple trading bot that uses basic price thresholds. It doesn't perform complex analysis or use advanced trading strategies. It's designed as a starting point that you can expand upon.

Always test on the Stellar testnet before using on the public network with real funds.
