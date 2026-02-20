#!/usr/bin/env python3
"""Setup Alpaca API keys for paper trading."""

import os
import sys
from pathlib import Path

def setup_alpaca_keys():
    """Set up Alpaca API keys in environment and .env file."""
    
    # Your provided keys
    api_key_id = "PK7JBKSXV6T77AZ3L3FK2NW4W4"
    secret_key = "pnsD5mboH3wDQSyJsDbr6Z69bwrFojv9Kkwrf3XFDMx"
    
    # Set environment variables for current session
    os.environ["APCA_API_KEY_ID"] = api_key_id
    os.environ["APCA_API_SECRET_KEY"] = secret_key
    os.environ["APCA_PAPER"] = "true"
    
    print("✅ Environment variables set for current session")
    
    # Update .env file for persistence
    env_path = Path(".env")
    env_content = []
    
    # Read existing .env content
    if env_path.exists():
        with open(env_path, 'r') as f:
            env_content = f.readlines()
    
    # Remove existing Alpaca entries if they exist
    env_content = [line for line in env_content if not line.startswith(('APCA_', 'ALPACA_'))]
    
    # Add new Alpaca configuration
    alpaca_config = [
        "# Alpaca Configuration\n",
        f"APCA_API_KEY_ID={api_key_id}\n",
        f"APCA_API_SECRET_KEY={secret_key}\n",
        "APCA_PAPER=true\n",
        "\n"
    ]
    
    # Write updated .env file
    with open(env_path, 'w') as f:
        f.writelines(env_content + alpaca_config)
    
    print("✅ .env file updated with Alpaca configuration")
    print(f"📄 .env location: {env_path.absolute()}")
    
    return api_key_id, secret_key

if __name__ == "__main__":
    try:
        api_key, secret = setup_alpaca_keys()
        print("\n🚀 Alpaca setup complete!")
        print(f"🔑 API Key ID: {api_key[:10]}...")
        print(f"🔐 Secret Key: {secret[:10]}...")
        print("\n📋 Next steps:")
        print("1. Install alpaca-py: pip install alpaca-py")
        print("2. Deploy paper trading: python deploy_paper_trading.py --tickers NVDA,AMD --capital 100000")
        
    except Exception as e:
        print(f"❌ Setup failed: {e}")
        sys.exit(1)
