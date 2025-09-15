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
        "close_yuzde": os.getenv("BITGET_CLOSE_YUZDE", "1.2")
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

def close_all_positions(api_key, api_secret_key, passphrase):
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
      print("Kapama Yaniti:", response.json())
  except json.JSONDecodeError:
      print("Yanit JSON formatinda degil:", response.text)

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
          
          # Max leverage degerini al
          maxLeverage = get_max_leverage(symbol)
          if maxLeverage is None:
              print("Max leverage alinamadi.")
              exit()

          # Max leverage degerini float'a cevir
          maxLeverage = float(maxLeverage)

          # Coin fiyatini %1.5 arttir
          coin_price_long = float(coin_price['last_price']) * 1.015
          
          # Coin boyutunu hesapla
          open_USDT = float(credentials.get("open_USDT", 5))  # Default 5 USDT
          print(f"🔍 DEBUG: open_USDT={open_USDT}, maxLeverage={maxLeverage}")
          coin_size = open_USDT * maxLeverage / float(coin_price['last_price'])
          print(f"🔍 DEBUG: Hesaplanan coin_size={coin_size} (floor öncesi)")

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
 

          # POST istegi icin imza olusturma
          timestamp = str(get_timestamp())
          request_path = "/api/mix/v1/order/placeOrder"
          params = {
              "symbol": symbol,
              "marginCoin": "USDT",
              "price": coin_price_long,
              "size": coin_size,
              "side": "open_long",
              "orderType": "limit",
              "timeInForceValue": "normal"
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
