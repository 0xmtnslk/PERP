import requests
import time
import hashlib
import hmac
import json

host = "https://api.gateio.ws"
prefix = "/api/v4"
headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}

# secret.json dosyasini oku
import os
BASE_DIR = os.getcwd()
with open(os.path.join(BASE_DIR, 'gateio', 'secret.json'), 'r') as file:
  gateio_secrets = json.load(file)['gateio_example']

# Degiskenleri tanimla
gateio_api = gateio_secrets['api_key']
gateio_secret = gateio_secrets['secret_key']

# order_gateio.json dosyasindan bilgileri oku
with open(os.path.join(BASE_DIR, 'gateio', 'order_gateio.json'), 'r') as f:
  order_data = json.load(f)
  gate_contract = order_data['contract']
  gate_id = order_data['id']
  gate_fill_price = order_data['fill_price']
  gate_size = order_data['size']

# order_id'yi ve diÄŸer bilgileri ekrana yazdir
print(f"Order ID: {gate_id}")
print(f"Contract: {gate_contract}")
print(f"Fill Price: {gate_fill_price}")
print(f"Size: {gate_size}")

# Imza olusturma fonksiyonu
def gen_sign(method, url, query_string=None, payload_string=None):
  t = time.time()
  m = hashlib.sha512()
  m.update((payload_string or "").encode('utf-8'))
  hashed_payload = m.hexdigest()
  s = '%s\n%s\n%s\n%s\n%s' % (method, url, query_string or "", hashed_payload, t)
  sign = hmac.new(gateio_secret.encode('utf-8'), s.encode('utf-8'), hashlib.sha512).hexdigest()
  return {'KEY': gateio_api, 'Timestamp': str(t), 'SIGN': sign}

# Pozisyonu kapatmak icin emir ver
url = f'/futures/usdt/orders'
body = {
  "contract": gate_contract,
  "size": -gate_size,  # Pozisyonu kapatmak icin ters yonde emir ver
  "price": "0",  # Piyasa fiyatindan kapatmak icin 0 kullanilir
  "tif": "ioc",  # Immediate or Cancel
  "reduce_only": True  # Pozisyonu kapatmak icin
}

body_string = json.dumps(body)
sign_headers = gen_sign('POST', prefix + url, '', body_string)
headers.update(sign_headers)

# API istegi yap
r = requests.post(host + prefix + url, headers=headers, data=body_string)
print(r.json())
