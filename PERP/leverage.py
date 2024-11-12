import time
import hmac
import hashlib
import base64
import requests
import json

# JSON dosyasindan API bilgilerini okuma
def load_api_credentials(file_path):
  try:
      with open(file_path, 'r') as file:
          data = json.load(file)
          return data.get("bitget_example", {})
  except FileNotFoundError:
      print(f"Dosya bulunamadi: {file_path}")
      return {}

# Dosyadan symbol okuma
def get_symbol_from_file(file_path):
  try:
      with open(file_path, 'r') as file:
          symbol = file.read().strip()
          return symbol
  except FileNotFoundError:
      print(f"Dosya bulunamadi: {file_path}")
      return None

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

# API bilgilerini yukle
credentials = load_api_credentials("/root/PERP/secret.json")
api_key = credentials.get("api_key")
secret_key = credentials.get("secret_key")
passphrase = credentials.get("passphrase")

# Zaman damgasi
timestamp = str(int(time.time() * 1000))

# Symbol dosyasinin yolu
file_path = "/root/PERP/new_coin_output.txt"
symbol = get_symbol_from_file(file_path)

if symbol and api_key and secret_key and passphrase:
  # Max leverage degerini al
  leveragemax = get_max_leverage(symbol)
  
  if leveragemax:
      # Istek bilgileri
      method = "POST"
      request_path = "/api/mix/v1/account/setLeverage"
      body = f'{{"symbol": "{symbol}", "marginCoin": "USDT", "leverage": "{leveragemax}"}}'

      # Imza olusturma
      message = timestamp + method + request_path + body
      signature = hmac.new(secret_key.encode('utf-8'), message.encode('utf-8'), hashlib.sha256).digest()
      signature_b64 = base64.b64encode(signature).decode()

      # Basliklar
      headers = {
          "ACCESS-KEY": api_key,
          "ACCESS-SIGN": signature_b64,
          "ACCESS-PASSPHRASE": passphrase,
          "ACCESS-TIMESTAMP": timestamp,
          "Content-Type": "application/json"
      }

      # Istek gonder
      url = "https://api.bitget.com" + request_path
      response = requests.post(url, headers=headers, data=body)

      # Yaniti yazdir
      print("Durum Kodu:", response.status_code)
      print("Yanit:", response.json())
  else:
      print("Max leverage degeri alinamadi.")
else:
  print("Gerekli bilgiler eksik veya dosyalar bulunamadi.")
