#!/bin/bash
# AWS Lightsail deployment script for Stellar Trading Bot

# Usage instructions:
# 1. Run this script from your local machine
# 2. Provide your AWS Lightsail instance IP and key file when prompted
# 3. Follow the on-screen instructions

# Colors for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}===== Stellar Trading Bot AWS Deployment =====${NC}"
echo

# Get AWS Lightsail details
read -p "Enter your AWS Lightsail instance IP address: " LIGHTSAIL_IP
read -p "Enter the path to your AWS Lightsail key file (.pem): " KEY_FILE

# We're only deploying the XLM/USDC trading bot
echo -e "${YELLOW}Deploying XLM/USDC Trading Bot...${NC}"

# Validate inputs
if [ -z "$LIGHTSAIL_IP" ] || [ -z "$KEY_FILE" ]; then
    echo -e "${RED}Error: Both IP address and key file are required.${NC}"
    exit 1
fi

if [ ! -f "$KEY_FILE" ]; then
    echo -e "${RED}Error: Key file not found at $KEY_FILE${NC}"
    exit 1
fi

# Make sure the key file has correct permissions
chmod 400 "$KEY_FILE"

echo -e "${YELLOW}Step 1: Transferring project files to AWS Lightsail...${NC}"
# Copy the entire project to the AWS instance
scp -i "$KEY_FILE" -r "$(pwd)" ubuntu@"$LIGHTSAIL_IP":/home/ubuntu/cashcow

echo -e "${YELLOW}Step 2: Setting up the environment on AWS Lightsail...${NC}"
# Execute setup commands on the remote instance
ssh -i "$KEY_FILE" ubuntu@"$LIGHTSAIL_IP" << 'EOF'
    # Print start message
    echo "Setting up on AWS Lightsail instance..."
    
    # Install required packages
    sudo apt update
    sudo apt install -y python3-venv python3-pip
    
    # Set up Python virtual environment
    cd /home/ubuntu/cashcow
    python3 -m venv venv
    
    # Activate virtual environment and install dependencies
    source venv/bin/activate
    pip install -r requirements.txt
    
    # Make the trading script executable
    chmod +x /home/ubuntu/cashcow/xlm_usdc_trader.py
    
    # Update environment variables and network connectivity settings
    if [ ! -f "/home/ubuntu/cashcow/.env" ]; then
        echo "Creating .env file from example"
        cp /home/ubuntu/cashcow/.env.example /home/ubuntu/cashcow/.env
        echo "Please update the .env file with your Stellar credentials"
    fi
    
    # Ensure proper Stellar network settings
    sed -i 's|\(HORIZON_URL=\).*|\1"https://horizon.stellar.org"|' /home/ubuntu/cashcow/.env
    
    # Make sure we have a backup URL in case the primary fails
    if ! grep -q "HORIZON_URL_BACKUP" /home/ubuntu/cashcow/.env; then
        echo "HORIZON_URL_BACKUP=\"https://horizon-api.elliptic.co\"" >> /home/ubuntu/cashcow/.env
    fi
    
    # Make sure the logs directory exists
    mkdir -p /home/ubuntu/cashcow/logs
    
    # Configure connection retries for Stellar network connectivity issues
    cat > /home/ubuntu/cashcow/connection_retry.py << 'PYTHON'
#!/usr/bin/env python3
import time
import socket
import requests
from functools import wraps

def retry_on_network_error(max_retries=5, backoff_factor=1.5, max_backoff=60):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries = 0
            backoff = 1
            
            while retries <= max_retries:
                try:
                    return func(*args, **kwargs)
                except (requests.exceptions.RequestException, 
                        socket.gaierror, 
                        ConnectionError) as e:
                    retries += 1
                    if retries > max_retries:
                        raise
                    
                    # Calculate backoff time with exponential backoff
                    backoff = min(backoff * backoff_factor, max_backoff)
                    print(f"Network error: {str(e)}. Retrying in {backoff:.1f} seconds...")
                    time.sleep(backoff)
            
            return func(*args, **kwargs)
        return wrapper
    return decorator
PYTHON

    # Copy the retry module to the virtual environment
    cp /home/ubuntu/cashcow/connection_retry.py /home/ubuntu/cashcow/venv/lib/python3.*/site-packages/
    
    # Copy systemd service file for the trading bot
    sudo cp /home/ubuntu/cashcow/stellar-trading-bot.service /etc/systemd/system/
    
    # Reload systemd configuration
    sudo systemctl daemon-reload
    
    # Enable and start the trading bot service
    echo "Setting up trading bot service..."
    sudo systemctl enable stellar-trading-bot.service
    sudo systemctl start stellar-trading-bot.service
    echo "Trading bot service status:"
    sudo systemctl status stellar-trading-bot.service
EOF

echo
echo -e "${GREEN}Deployment complete!${NC}"
echo

echo -e "${YELLOW}To check the trading bot status on your AWS instance:${NC}"
echo "ssh -i \"$KEY_FILE\" ubuntu@\"$LIGHTSAIL_IP\" sudo systemctl status stellar-trading-bot.service"
echo
echo -e "${YELLOW}To view the trading bot logs:${NC}"
echo "ssh -i \"$KEY_FILE\" ubuntu@\"$LIGHTSAIL_IP\" sudo journalctl -u stellar-trading-bot.service -f"
echo

echo -e "${GREEN}Your Stellar Trading Bot has been deployed to your AWS Lightsail instance!${NC}"
echo -e "${YELLOW}Remember to check your .env file configuration if you encounter any connection issues.${NC}"
echo -e "${YELLOW}You can modify settings by editing /home/ubuntu/cashcow/.env on your AWS instance.${NC}"
