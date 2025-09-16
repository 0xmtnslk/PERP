import hmac
import base64
import json
import time
import requests
import subprocess
import os
import math # Tam sayiya yuvarlamak icin math modulunu ekle


def get_timestamp():
  return int(time.time() * 1000)

def create_signature(message, secret_key):
  mac = hmac.new(bytes(secret_key, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
  d = mac.digest()
  return base64.b64encode(d).decode('utf-8')

def pre_hash(timestamp, method, request_path, body):
  return str(timestamp) + str.upper(method) + request_path + body

def parse_params_to_str(params):
  url = '?'
  for key, value in params.items():
      url += f"{key}={value}&"
  return url[:-1]

def get_symbol_from_file(file_path):
  try:
      with open(file_path, 'r') as file:
          symbol = file.read().strip()
          return symbol
  except FileNotFoundError:
      print(f"Dosya bulunamadi: {file_path}")
      return None

def load_api_credentials():
    """Environment variable'lardan API bilgilerini al"""
    return {
        "api_key": os.getenv("BITGET_API_KEY"),
        "secret_key": os.getenv("BITGET_SECRET_KEY"), 
        "passphrase": os.getenv("BITGET_PASSPHRASE"),
        "open_USDT": os.getenv("BITGET_OPEN_USDT", "5"),
        "close_yuzde": os.getenv("BITGET_CLOSE_YUZDE", "1.2"),
        "leverage": os.getenv("BITGET_LEVERAGE", "0"),
        "user_id": os.getenv("USER_ID", "0")
    }

def get_futures_price(symbol):
  url = f"https://api.bitget.com/api/mix/v1/market/ticker?symbol={symbol}"
  response = requests.get(url)
  
  if response.status_code == 200:
      data = response.json()
      coin_data = data.get("data", {})
      coin_price = coin_data.get("last")
      best_ask = coin_data.get("bestAsk")
      best_bid = coin_data.get("bestBid")
      high_24h = coin_data.get("high24h")
      low_24h = coin_data.get("low24h")
      
      return {
          "last_price": coin_price,
          "best_ask": best_ask,
          "best_bid": best_bid,
          "high_24h": high_24h,
          "low_24h": low_24h
      }
  else:
      print("Veri cekme hatasi:", response.status_code)
      return None

def save_order_id_to_file(order_response, file_path):
  try:
      with open(file_path, 'w') as file:
          json.dump(order_response, file, indent=4)
      print(f"Order bilgileri {file_path} dosyasina kaydedildi.")
  except IOError as e:
      print(f"Dosya yazma hatasi: {e}")

def save_order_fills_to_file(order_fills_response, file_path):
  try:
      with open(file_path, 'w') as file:
          json.dump(order_fills_response, file, indent=4)
      print(f"Order fills bilgileri {file_path} dosyasina kaydedildi.")
  except IOError as e:
      print(f"Dosya yazma hatasi: {e}")

def get_all_positions(api_key, api_secret_key, passphrase):
  """Tüm açık pozisyonları getir - kar/zarar hesabı için"""
  timestamp = str(get_timestamp())
  request_path = "/api/mix/v1/position/allPosition"
  
  # Query parameters 
  params = {"productType": "umcbl"}
  query_string = parse_params_to_str(params)
  
  sign = create_signature(pre_hash(timestamp, "GET", request_path + query_string, ""), api_secret_key)

  headers = {
      "ACCESS-KEY": api_key,
      "ACCESS-SIGN": sign,
      "ACCESS-PASSPHRASE": passphrase,
      "ACCESS-TIMESTAMP": timestamp,
      "Content-Type": "application/json"
  }

  url = "https://api.bitget.com" + request_path + query_string
  response = requests.get(url, headers=headers)

  if response.status_code == 200:
      try:
          data = response.json()
          if data['code'] == '00000':
              return data['data']
          else:
              print(f"API hatası: {data['msg']}")
              return []
      except json.JSONDecodeError:
          print("Pozisyon verisi JSON formatında değil")
          return []
  else:
      print(f"Pozisyon alma hatası: {response.status_code}")
      return []

def close_all_positions(api_key, api_secret_key, passphrase):
  # Önce pozisyonları al - kar/zarar hesabı için
  positions = get_all_positions(api_key, api_secret_key, passphrase)
  
  total_pnl = 0.0
  active_positions = []
  
  if positions:
      for position in positions:
          # Sadece açık pozisyonları say (size > 0)
          size = float(position.get('size', 0))
          if size > 0:
              unrealized_pnl = float(position.get('unrealizedPL', 0))
              total_pnl += unrealized_pnl
              active_positions.append({
                  'symbol': position.get('symbol', 'N/A'),
                  'size': size,
                  'side': position.get('side', 'N/A'),
                  'unrealizedPL': unrealized_pnl,
                  'markPrice': position.get('markPrice', 'N/A')
              })
      
      print(f"📊 Kapatılacak Pozisyonlar: {len(active_positions)}")
      print(f"💰 Toplam Kar/Zarar: {total_pnl:.2f} USDT")
      for pos in active_positions:
          pnl_status = "🟢" if pos['unrealizedPL'] > 0 else "🔴"
          print(f"  {pnl_status} {pos['symbol']}: {pos['unrealizedPL']:.2f} USDT")
  
  # Şimdi pozisyonları kapat
  timestamp = str(get_timestamp())
  request_path = "/api/mix/v1/order/close-all-positions"
  
  body = json.dumps({"productType": "umcbl"})
  
  sign = create_signature(pre_hash(timestamp, "POST", request_path, body), api_secret_key)

  headers = {
      "ACCESS-KEY": api_key,
      "ACCESS-SIGN": sign,
      "ACCESS-PASSPHRASE": passphrase,
      "ACCESS-TIMESTAMP": timestamp,
      "Content-Type": "application/json"
  }

  url = "https://api.bitget.com" + request_path
  response = requests.post(url, headers=headers, data=body)

  print("Kapama Istegi Durum Kodu:", response.status_code)
  try:
      result = response.json()
      print("Kapama Yaniti:", result)
      
      # Kar/zarar bilgilerini de döndür
      return {
          'status_code': response.status_code,
          'response': result,
          'total_pnl': total_pnl,
          'positions_count': len(active_positions),
          'positions': active_positions
      }
  except json.JSONDecodeError:
      print("Yanit JSON formatinda degil:", response.text)
      return {
          'status_code': response.status_code,
          'response': response.text,
          'total_pnl': total_pnl,
          'positions_count': len(active_positions),
          'positions': active_positions
      }

# API'den maxLeverage degerini al
def get_max_leverage(symbol):
  url = f"https://api.bitget.com/api/mix/v1/market/symbol-leverage?symbol={symbol}"
  response = requests.get(url)
  
  if response.status_code == 200:
      data = response.json()
      if data['code'] == '00000':
          max_leverage = data['data']['maxLeverage']
          return max_leverage
      else:
          print(f"API hatasi: {data['msg']}")
  else:
      print(f"HTTP hatasi: {response.status_code}")
  
  return None

if __name__ == '__main__':
  # Dosya yollarini tanimla - script konumundan bağımsız çalıştır
  script_dir = os.path.dirname(os.path.abspath(__file__))  # PERP klasörü
  BASE_DIR = os.path.dirname(script_dir)  # workspace klasörü 
  
  secret_file_path = os.path.join(script_dir, "secret.json")
  symbol_file_path = os.path.join(script_dir, "new_coin_output.txt")
  order_id_file_path = os.path.join(script_dir, "order_id.json")
  order_fills_file_path = os.path.join(script_dir, "order_fills.json")
  yuzde_file_path = os.path.join(script_dir, "yuzde.json")
  
  # API bilgilerini environment variable'lardan al
  credentials = load_api_credentials()
  API_KEY = credentials.get("api_key")
  API_SECRET_KEY = credentials.get("secret_key")
  PASS_PHRASE = credentials.get("passphrase")
  close_yuzde = float(credentials.get("close_yuzde", 1.2))
  
  # API anahtarlarını kontrol et
  if not all([API_KEY, API_SECRET_KEY, PASS_PHRASE]):
      print("❌ HATA: Bitget API anahtarları environment variable'larda bulunamadı!")
      print("📋 Gerekli environment variable'lar:")
      print("   - BITGET_API_KEY")
      print("   - BITGET_SECRET_KEY") 
      print("   - BITGET_PASSPHRASE")
      exit(1)

  # Symbol dosyasindan oku
  symbol = get_symbol_from_file(symbol_file_path)
  
  if symbol and API_KEY and API_SECRET_KEY and PASS_PHRASE:
      # Coin fiyatini al
      coin_price = get_futures_price(symbol)
      
      if coin_price:
          print(f"Anlik Coin Fiyati: {coin_price['last_price']}")  # Coin fiyatini ekrana yaz
          
          # Leverage değerini belirle - DATABASE FIRST (Telegram bot integration)
          import sqlite3
          import os
          
          user_leverage = 0
          try:
              # User ID from user_trading_engine.py context (625972998)
              user_id = 625972998  # Main user
              db_path = os.path.join(os.getcwd(), "trading_bot.db")
              conn = sqlite3.connect(db_path)
              cursor = conn.cursor()
              
              cursor.execute("SELECT leverage FROM users WHERE user_id = ?", (user_id,))
              result = cursor.fetchone()
              conn.close()
              
              if result:
                  user_leverage = int(result[0])
                  print(f"🎯 Database leverage: {user_leverage}x (from Telegram)")
              else:
                  print("🔍 No database leverage found, checking config...")
                  user_leverage = int(credentials.get("leverage", 0))
          except Exception as e:
              print(f"⚠️ Database leverage error: {e}, using config...")
              user_leverage = int(credentials.get("leverage", 0))
          
          if user_leverage > 0:
              leverage = user_leverage
              print(f"🎯 Using user leverage: {leverage}x")
          else:
              # Fallback to max leverage
              maxLeverage = get_max_leverage(symbol)
              if maxLeverage is None:
                  print("Max leverage alinamadi.")
                  exit()
              leverage = float(maxLeverage)
              print(f"📊 Fallback max leverage: {leverage}x")

          # ARCHITECT FIX: Define api_symbol BEFORE using it!
          api_symbol = symbol.replace("_UMCBL", "")
          print(f"🔧 V2 API Symbol: {symbol} → {api_symbol}")

          # SET LEVERAGE FIRST (Bitget API v2) - BEFORE ORDER!
          print(f"🎯 Setting leverage to {leverage}x for {api_symbol}...")
          leverage_timestamp = str(get_timestamp())
          leverage_request_path = "/api/v2/mix/account/set-leverage"
          
          leverage_params = {
              "symbol": api_symbol,  # Now properly defined!
              "productType": "USDT-FUTURES",
              "marginCoin": "USDT", 
              "leverage": str(int(leverage)),  # Convert to string
              "holdSide": "long"
          }
          leverage_body = json.dumps(leverage_params)
          leverage_sign = create_signature(pre_hash(leverage_timestamp, "POST", leverage_request_path, leverage_body), API_SECRET_KEY)
          
          leverage_headers = {
              "ACCESS-KEY": API_KEY,
              "ACCESS-SIGN": leverage_sign,
              "ACCESS-PASSPHRASE": PASS_PHRASE,
              "ACCESS-TIMESTAMP": leverage_timestamp,
              "Content-Type": "application/json"
          }
          
          leverage_url = "https://api.bitget.com" + leverage_request_path
          leverage_response = requests.post(leverage_url, headers=leverage_headers, data=leverage_body)
          leverage_result = leverage_response.json()
          print(f"🔧 Leverage API Response: {leverage_result}")
          
          if leverage_result.get('code') == '00000':
              print(f"✅ Leverage set to {leverage}x successfully!")
          else:
              print(f"⚠️ Leverage setting failed: {leverage_result.get('msg', 'Unknown error')}")
              # Continue anyway - order placement might still work
              
          # Coin fiyatini %1.5 arttir
          coin_price_long = float(coin_price['last_price']) * 1.015
          
          # REAL-TIME BALANCE CHECK (Architect's fix)
          print("🔍 Fetching real-time available balance...")
          balance_timestamp = str(get_timestamp())
          balance_request_path = "/api/v2/mix/account/accounts"
          balance_params = {"productType": "USDT-FUTURES"}  # V2 consistent format
          balance_request_path += parse_params_to_str(balance_params)
          balance_sign = create_signature(pre_hash(balance_timestamp, "GET", balance_request_path, ""), API_SECRET_KEY)
          
          balance_headers = {
              "ACCESS-KEY": API_KEY,
              "ACCESS-SIGN": balance_sign,
              "ACCESS-PASSPHRASE": PASS_PHRASE,
              "ACCESS-TIMESTAMP": balance_timestamp,
              "Content-Type": "application/json"
          }
          balance_url = "https://api.bitget.com" + balance_request_path
          balance_response = requests.get(balance_url, headers=balance_headers)
          print(f"🔍 Balance API Response: {balance_response.json()}")
          
          balance_data = balance_response.json()
          if balance_data.get('code') == '00000' and balance_data.get('data'):
              # ARCHITECT FIX: V2 returns array, use data[0]['available']
              available_usdt = float(balance_data['data'][0]['available'])
              print(f"💰 Available USDT: {available_usdt}")
              
              # Apply safety buffer (0.985) for fees/slippage
              usable_usdt = available_usdt * 0.985
              print(f"💰 Usable USDT (with buffer): {usable_usdt}")
              
              # RESTORE USER'S CONFIGURED AMOUNT (gerçek $10 alım için)
              configured_open_USDT = float(credentials.get("open_USDT", 10))  # User's $10 setting
              actual_open_USDT = min(configured_open_USDT, usable_usdt)
              print(f"💰 User configured: ${configured_open_USDT}, Available: ${usable_usdt}, Using: ${actual_open_USDT}")
              
              # Ensure we have enough balance (minimum 1 USDT)
              if actual_open_USDT < 1.0:
                  print(f"❌ INSUFFICIENT BALANCE: Need minimum $1, have ${actual_open_USDT}")
                  exit(1)
                  
              coin_size = actual_open_USDT * leverage / float(coin_price['last_price'])
              print(f"🔍 SAFE coin_size={coin_size} (balance-checked)")
          else:
              print(f"❌ Balance check failed: {balance_data}")
              exit(1)

          # Bitget fiyat formatı: 0.01'in katları olmalı (2 decimal)
          coin_price_long = round(coin_price_long, 2)  # Bitget için 2 decimal
          print(f"🔍 DEBUG: coin_price_long={coin_price_long} (2 decimal)")
          coin_size = round(coin_size, 4)  # Floor yerine 4 decimal'e yuvarla (Bitget için uygun)
          print(f"🔍 DEBUG: Final coin_size={coin_size}")
          
          # Size 0 kontrolü ekle
          if coin_size <= 0:
              print(f"❌ HATA: Coin size 0 veya negatif: {coin_size}")
              print(f"   open_USDT: {open_USDT}")
              print(f"   maxLeverage: {maxLeverage}")  
              print(f"   coin_price: {coin_price['last_price']}")
              exit(1)
 

          # POST istegi icin imza olusturma - NEW API V2 + MARKET ORDER
          timestamp = str(get_timestamp())
          request_path = "/api/v2/mix/order/place-order"
          # V2 API: Remove _UMCBL suffix from symbol (per release notes)
          api_symbol = symbol.replace("_UMCBL", "")
          print(f"🔧 V2 API Symbol: {symbol} → {api_symbol}")
          
          params = {
              "symbol": api_symbol,
              "productType": "USDT-FUTURES",
              "marginMode": "crossed",
              "marginCoin": "USDT",
              "size": coin_size,
              "side": "buy",
              "tradeSide": "open",
              "orderType": "market",
              "clientOid": f"auto_trade_{get_timestamp()}"
          }
          body = json.dumps(params)
          post_sign = create_signature(pre_hash(timestamp, "POST", request_path, body), API_SECRET_KEY)

          # POST istegi gonderme
          headers = {
              "ACCESS-KEY": API_KEY,
              "ACCESS-SIGN": post_sign,
              "ACCESS-PASSPHRASE": PASS_PHRASE,
              "ACCESS-TIMESTAMP": timestamp,
              "Content-Type": "application/json"
          }
          url = "https://api.bitget.com" + request_path
          response = requests.post(url, headers=headers, data=body)
          print("POST Istegi Durum Kodu:", response.status_code)
          post_response = response.json()
          print("POST Yaniti:", post_response)

          # Order ID'yi dosyaya kaydet
          save_order_id_to_file(post_response, order_id_file_path)

          # Order ID'yi degiskene ata - hata kontrolü ekle
          if post_response.get('code') == '00000' and post_response.get('data'):
              order_id = post_response['data'].get('orderId')
              print(f"Order ID: {order_id}")
          else:
              print(f"❌ İşlem hatası: {post_response.get('msg', 'Bilinmeyen hata')}")
              exit(1)

          # GET istegi icin imza olusturma
          timestamp = str(get_timestamp())  # Zaman damgasini guncelle
          body = ""
          request_path = "/api/mix/v1/account/account"
          params = {
              "symbol": symbol,
              "marginCoin": "USDT"
          }
          request_path += parse_params_to_str(params)
          get_sign = create_signature(pre_hash(timestamp, "GET", request_path, body), API_SECRET_KEY)

          # GET istegi gonderme
          headers = {
              "ACCESS-KEY": API_KEY,
              "ACCESS-SIGN": get_sign,
              "ACCESS-PASSPHRASE": PASS_PHRASE,
              "ACCESS-TIMESTAMP": timestamp,
              "Content-Type": "application/json"
          }
          url = "https://api.bitget.com" + request_path
          response = requests.get(url, headers=headers)
          print("GET Istegi Durum Kodu:", response.status_code)
          print("GET Yaniti:", response.json())

          # Order fills bilgilerini almak icin yeni bir GET istegi
          request_path = f"/api/mix/v1/order/fills?symbol={symbol}&orderId={order_id}"
          get_sign = create_signature(pre_hash(timestamp, "GET", request_path, body), API_SECRET_KEY)

          headers = {
              "ACCESS-KEY": API_KEY,
              "ACCESS-SIGN": get_sign,
              "ACCESS-PASSPHRASE": PASS_PHRASE,
              "ACCESS-TIMESTAMP": timestamp,
              "locale": "en-US",
              "Content-Type": "application/json"
          }
          url = "https://api.bitget.com" + request_path
          response = requests.get(url, headers=headers)
          print("Order Fills Istegi Durum Kodu:", response.status_code)
          order_fills_response = response.json()
          print("Order Fills Yaniti:", order_fills_response)

          # Order fills bilgilerini dosyaya kaydet
          save_order_fills_to_file(order_fills_response, order_fills_file_path)

          # Ilk fiyat degerini degiskene ata
          fills_price = float(order_fills_response['data'][0]['price'])
          print(f"Order Fills Price : {fills_price}")

          # ISLEM BASARILI mesajini yaz
          print("ISLEM BASARILI")

          # Son fiyat bilgisini al ve yazdir
          coin_info = get_futures_price(symbol)
          if coin_info:
              print(f"Son Fiyat: {coin_info['last_price']}")
              
              # Yuzde hesaplama
              yuzde = round(float(coin_info['last_price']) / fills_price, 3)

              # Yuzdeyi dosyaya kaydet
              timestamp = get_timestamp()
              with open(yuzde_file_path, 'w') as file:
                  json.dump({"timestamp": timestamp, "yuzde": yuzde}, file)
              
              # Yuzdeyi close_yuzde ile karsilastir
              if yuzde >= close_yuzde:
                  print("Hedef gerceklesti, pozisyon kapatiliyor...")
                  close_all_positions(API_KEY, API_SECRET_KEY, PASS_PHRASE)
              else:
                  # Test için infinite loop'u kaldır, sadece işlem aç ve çık
                  print(f"İşlem açıldı, target: {close_yuzde}x")
                  print("Test modunda - infinite loop devre dışı")
          else:
              print("Coin fiyat bilgisi alinamadi.")
      else:
          print("Coin fiyati alinamadi.")
  else:
      print("Gerekli bilgiler eksik veya dosyalar bulunamadi.")
