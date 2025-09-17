import hmac
import base64
import json
import time
import requests

def get_timestamp():
  return int(time.time() * 1000)

def create_signature(message, secret_key):
  mac = hmac.new(bytes(secret_key, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
  d = mac.digest()
  return base64.b64encode(d).decode('utf-8')

def pre_hash(timestamp, method, request_path, body):
  return str(timestamp) + str.upper(method) + request_path + body

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
      print("Yanıt JSON formatında degil:", response.text)

def load_api_credentials(file_path):
  try:
      with open(file_path, 'r') as file:
          data = json.load(file)
          bitget_data = data.get("bitget_example", {})
          api_key = bitget_data.get("api_key")
          secret_key = bitget_data.get("secret_key")
          passphrase = bitget_data.get("passphrase")
          
          if not api_key or not secret_key or not passphrase:
              print("API bilgileri eksik.")
              return None, None, None
          
          return api_key, secret_key, passphrase
  except FileNotFoundError:
      print(f"Dosya bulunamadi: {file_path}")
      return None, None, None
  except json.JSONDecodeError:
      print("JSON format hatasi: Dosya icerigi gecersiz.")
      return None, None, None

if __name__ == '__main__':
  import os
  BASE_DIR = os.getcwd()
  secret_file_path = os.path.join(BASE_DIR, "PERP", "secret.json")
  API_KEY, API_SECRET_KEY, PASS_PHRASE = load_api_credentials(secret_file_path)

  if API_KEY and API_SECRET_KEY and PASS_PHRASE:
      close_all_positions(API_KEY, API_SECRET_KEY, PASS_PHRASE)
  else:
      print("API bilgileri yuklenemedi.")
