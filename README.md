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

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in your credentials
4. Run the bot: `python src/main.py`

## Deployment

Instructions for deploying to AWS Lightsail are included in the `deployment/` directory.

## Security Notice

Never commit your private keys or secret information. Always use environment variables or secure key management.
