#!/usr/bin/env python3
"""Test Alpaca configuration."""

from config.settings import settings
import os

def test_alpaca_config():
    print("🔧 Testing Alpaca Configuration...")
    print(f"📋 Settings API Key: {settings.alpaca_api_key_id[:10] if settings.alpaca_api_key_id else 'None'}...")
    print(f"📋 Settings Secret Key: {settings.alpaca_api_secret_key[:10] if settings.alpaca_api_secret_key else 'None'}...")
    print(f"📋 Settings Paper Mode: {settings.alpaca_paper}")
    
    print(f"\n🌍 Environment API Key: {os.environ.get('APCA_API_KEY_ID', 'None')[:10] if os.environ.get('APCA_API_KEY_ID') else 'None'}...")
    print(f"🌍 Environment Secret Key: {os.environ.get('APCA_API_SECRET_KEY', 'None')[:10] if os.environ.get('APCA_API_SECRET_KEY') else 'None'}...")
    print(f"🌍 Environment Paper Mode: {os.environ.get('APCA_PAPER', 'None')}")
    
    if settings.alpaca_api_key_id:
        print("\n✅ Alpaca configuration loaded successfully!")
        return True
    else:
        print("\n❌ Alpaca configuration not found")
        return False

if __name__ == "__main__":
    test_alpaca_config()
