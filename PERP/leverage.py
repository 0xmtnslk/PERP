import time
import hmac
import hashlib
import base64
import requests
import json
import os
import sys

def get_symbol():
    """Get symbol from environment or user-specific file"""
    # Prefer TRADE_SYMBOL environment variable
    symbol = os.getenv("TRADE_SYMBOL")
    if symbol:
        return symbol
    
    # Fallback to user-specific file
    user_id = os.getenv("USER_ID")
    if user_id:
        user_symbol_file = os.path.join(os.getcwd(), "PERP", "users", user_id, "current_symbol.txt")
        try:
            with open(user_symbol_file, 'r') as f:
                symbol = f.read().strip()
                if symbol:
                    return symbol
        except FileNotFoundError:
            pass
    
    # Final fallback to global file
    try:
        with open(os.path.join(os.getcwd(), "PERP", "new_coin_output.txt"), 'r') as f:
            symbol = f.read().strip()
            if symbol:
                return symbol
    except FileNotFoundError:
        pass
    
    return None

def load_api_credentials():
    """Load API credentials from environment variables"""
    api_key = os.getenv("BITGET_API_KEY")
    secret_key = os.getenv("BITGET_SECRET_KEY") 
    passphrase = os.getenv("BITGET_PASSPHRASE")
    
    if not all([api_key, secret_key, passphrase]):
        print("ERROR: Missing API credentials in environment variables", file=sys.stderr)
        return None, None, None
        
    return api_key, secret_key, passphrase

def get_max_leverage(symbol):
    """Get maximum leverage for symbol from Bitget API"""
    url = f"https://api.bitget.com/api/mix/v1/market/symbol-leverage?symbol={symbol}"
    
    try:
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data['code'] == '00000':
                max_leverage = data['data']['maxLeverage']
                print(f"Max leverage for {symbol}: {max_leverage}")
                return max_leverage
            else:
                print(f"ERROR: API error getting max leverage: {data['msg']}", file=sys.stderr)
                return None
        else:
            print(f"ERROR: HTTP error getting max leverage: {response.status_code}", file=sys.stderr)
            return None
            
    except requests.RequestException as e:
        print(f"ERROR: Request failed getting max leverage: {e}", file=sys.stderr)
        return None

def set_leverage(api_key, secret_key, passphrase, symbol, leverage):
    """Set leverage for symbol using Bitget API"""
    timestamp = str(int(time.time() * 1000))
    method = "POST"
    request_path = "/api/mix/v1/account/setLeverage"
    body = f'{{"symbol": "{symbol}", "marginCoin": "USDT", "leverage": "{leverage}"}}'

    # Create signature
    message = timestamp + method + request_path + body
    signature = hmac.new(secret_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()
    signature_b64 = base64.b64encode(signature).decode()

    # Headers
    headers = {
        "ACCESS-KEY": api_key,
        "ACCESS-SIGN": signature_b64,
        "ACCESS-PASSPHRASE": passphrase,
        "ACCESS-TIMESTAMP": timestamp,
        "Content-Type": "application/json"
    }

    # Send request
    url = "https://api.bitget.com" + request_path
    
    try:
        response = requests.post(url, headers=headers, data=body, timeout=10)
        
        print(f"Leverage API Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Leverage API Response: {data}")
            
            if data['code'] == '00000':
                print(f"✅ Leverage set successfully to {leverage}x for {symbol}")
                return True
            else:
                print(f"ERROR: API error setting leverage: {data['msg']}", file=sys.stderr)
                return False
        else:
            print(f"ERROR: HTTP error setting leverage: {response.status_code}", file=sys.stderr)
            return False
            
    except requests.RequestException as e:
        print(f"ERROR: Request failed setting leverage: {e}", file=sys.stderr)
        return False

# NOTE: set_margin_mode() function moved to PERP/long.py to avoid conflicts
# The main implementation is in PERP/long.py with proper fail-safe logic

def main():
    """Main leverage setting function"""
    print("🔧 Starting leverage setting script...")
    
    # Get symbol
    symbol = get_symbol()
    if not symbol:
        print("ERROR: No symbol found in environment or files", file=sys.stderr)
        sys.exit(1)
    
    print(f"📊 Setting leverage for symbol: {symbol}")
    
    # Get API credentials
    api_key, secret_key, passphrase = load_api_credentials()
    if not all([api_key, secret_key, passphrase]):
        print("ERROR: Failed to load API credentials", file=sys.stderr)
        sys.exit(1)
    
    # Get max leverage
    max_leverage = get_max_leverage(symbol)
    if not max_leverage:
        print("ERROR: Failed to get max leverage", file=sys.stderr)
        sys.exit(1)
    
    # Set leverage to maximum
    success = set_leverage(api_key, secret_key, passphrase, symbol, max_leverage)
    if not success:
        print("ERROR: Failed to set leverage", file=sys.stderr)
        sys.exit(1)
    
    print("✅ Leverage setting completed successfully")

if __name__ == "__main__":
    main()