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

# Set deployment flag for trading bot
DEPLOY_TRADER=true
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
scp -i "$KEY_FILE" -r "$(pwd)" ec2-user@"$LIGHTSAIL_IP":/home/ec2-user/tradebot

echo -e "${YELLOW}Step 2: Setting up the environment on AWS Lightsail...${NC}"
# Execute setup commands on the remote instance
ssh -i "$KEY_FILE" ec2-user@"$LIGHTSAIL_IP" << 'EOF'
    # Print start message
    echo "Setting up on AWS Lightsail instance..."
    
    # Install required packages
    sudo amazon-linux-extras install postgresql14 -y
    sudo yum install postgresql postgresql-server postgresql-devel python3 python3-pip -y
    
    # Initialize PostgreSQL
    sudo postgresql-setup initdb
    
    # Start PostgreSQL
    sudo systemctl enable postgresql
    sudo systemctl start postgresql
    
    # Configure PostgreSQL
    sudo -u postgres psql << PSQL
        CREATE DATABASE stellar_trading;
        CREATE USER ec2_user WITH PASSWORD '';
        GRANT ALL PRIVILEGES ON DATABASE stellar_trading TO ec2_user;
        \q
PSQL
    
    # Allow local connections
    sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = 'localhost'/g" /var/lib/pgsql/data/postgresql.conf
    echo "host    stellar_trading    ec2_user    127.0.0.1/32    trust" | sudo tee -a /var/lib/pgsql/data/pg_hba.conf
    
    # Restart PostgreSQL to apply changes
    sudo systemctl restart postgresql
    
    # Install Python dependencies
    cd /home/ec2-user/tradebot
    pip3 install -r requirements.txt --user
    
    # Make sure psycopg2 is installed
    pip3 install psycopg2-binary --user
    
    # Update environment variables and network connectivity settings
    if [ -f "/home/ec2-user/tradebot/.env" ]; then
        # Update database user
        sed -i "s/DB_USER=toshi/DB_USER=ec2_user/g" /home/ec2-user/tradebot/.env
        
        # Ensure proper Stellar network settings
        # Check and fix any RPC URL issues
        if grep -q "invalid uri character" /home/ec2-user/tradebot/.env; then
            echo "Fixing invalid RPC URL characters in .env file"
            sed -i 's|\(HORIZON_URL=\).*|\1"https://horizon.stellar.org"|' /home/ec2-user/tradebot/.env
        fi
        
        # Make sure we have a backup URL in case the primary fails
        if ! grep -q "HORIZON_URL_BACKUP" /home/ec2-user/tradebot/.env; then
            echo "HORIZON_URL_BACKUP=\"https://horizon-api.elliptic.co\"" >> /home/ec2-user/tradebot/.env
        fi
    else
        echo "Warning: .env file not found. You may need to create it manually."
    fi
    
    # Make sure the deployment directory exists
    mkdir -p /home/ec2-user/tradebot/deployment
    
    # Configure connection retries for Stellar network connectivity issues
    cat > /home/ec2-user/tradebot/deployment/connection_retry.py << 'PYTHON'
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

    # Install the retry module at system level so all services can use it
    sudo cp /home/ec2-user/tradebot/deployment/connection_retry.py /usr/local/lib/python3.7/site-packages/
    
    # Copy systemd service file for the trading bot
    sudo cp /home/ec2-user/tradebot/stellar-trading-bot.service /etc/systemd/system/
    
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
echo "ssh -i \"$KEY_FILE\" ec2-user@\"$LIGHTSAIL_IP\" sudo systemctl status stellar-trading-bot.service"
echo
echo -e "${YELLOW}To view the trading bot logs:${NC}"
echo "ssh -i \"$KEY_FILE\" ec2-user@\"$LIGHTSAIL_IP\" sudo journalctl -u stellar-trading-bot.service -f"
echo

echo -e "${GREEN}Your Stellar Trading Bot has been deployed to your AWS Lightsail instance!${NC}"
echo -e "${YELLOW}Remember to check your .env file configuration if you encounter any connection issues.${NC}"
echo -e "${YELLOW}You can modify settings by editing /home/ec2-user/tradebot/.env on your AWS instance.${NC}"
