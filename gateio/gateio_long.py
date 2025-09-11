import requests
import json
import time
import hashlib
import hmac
import subprocess
import os
import math # Tam sayiya yuvarlamak icin math modulunu ekle

host = "https://api.gateio.ws"
prefix = "/api/v4"
headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}

# Environment variable'lardan gateio bilgilerini al
BASE_DIR = os.getcwd()

# Degiskenleri environment variable'lardan al
gateio_api = os.getenv('GATEIO_API_KEY')
gateio_secret = os.getenv('GATEIO_SECRET_KEY')
gateio_open_USDT = float(os.getenv('GATEIO_OPEN_USDT', '1'))
gateio_initial_symbol = os.getenv('GATEIO_INITIAL_SYMBOL', 'XLM_USDT')

# API anahtarlarını kontrol et ve type safety sağla
if not gateio_api or not gateio_secret:
    print("❌ HATA: Gate.io API anahtarları environment variable'larda bulunamadı!")
    print("📋 Gerekli environment variable'lar:")
    print("   - GATEIO_API_KEY")
    print("   - GATEIO_SECRET_KEY")
    exit(1)

# Type safety için assert
assert gateio_api is not None and gateio_secret is not None, "API keys must not be None"

# Yeni sembol dosyasindan oku
with open(os.path.join(BASE_DIR, 'gateio', 'new_coin_output.txt'), 'r') as file:
  gateio_symbol = file.read().strip()

# API istegi yap
url = f"https://api.gateio.ws/api/v4/futures/usdt/contracts/{gateio_symbol}"
response = requests.get(url)
data = response.json()

# Gerekli bilgileri al
gateio_leverage = float(data['leverage_max'])  # Burada float() ile donusturme yapiliyor
gateio_price = float(data['last_price'])  # Burada float() ile donusturme yapiliyor
gateio_mark_price_round = float(data['mark_price_round'])  # Mark price al

# Sonuclari yazdir
print(f"{gateio_symbol} : {gateio_price} , leverage: {gateio_leverage} , mark_price_round: {gateio_mark_price_round}")

# Sonuclari JSON formatinda yaz
output_data = {
  "symbol": gateio_symbol,
  "price": gateio_price,
  "leverage": gateio_leverage,
  "mark_price_round": gateio_mark_price_round  # Yeni alani ekle
}

with open(os.path.join(BASE_DIR, 'gateio', 'perp_sorgu.json'), 'w') as json_file:
  json.dump(output_data, json_file, indent=4)

# gateio/perp_sorgu.json dosyasindan verileri oku
with open(os.path.join(BASE_DIR, 'gateio', 'perp_sorgu.json'), 'r') as json_file:
  perp_data = json.load(json_file)
  gateio_symbol = perp_data['symbol']
  gateio_leverage = perp_data['leverage']
  gateio_mark_price_round = perp_data['mark_price_round']  # Yeni alani oku

# Coin fiyatini %3 arttir
coin_price_long = gateio_price * 1.03

# Coin boyutunu hesapla
gateio_coin_size = gateio_open_USDT * gateio_leverage / gateio_price # Girinti duzeltildi

# gateio/round_gate.txt dosyasindan yuvarlama hassasiyetini oku
with open(os.path.join(BASE_DIR, 'gateio', 'round_gate.txt'), 'r') as file:
  round_gate = int(file.read().strip())  # Dosyadan okunan degeri tam sayiya cevir

# Coin boyutunu uygun hassasiyete yuvarla
coin_price_long = round(coin_price_long, round_gate)  # Dinamik hassasiyete yuvarla
gateio_coin_size = math.floor(gateio_coin_size) # Degeri asagi yuvarla

# Imza olusturma fonksiyonu
def gen_sign(method, url, query_string=None, payload_string=None):
  t = time.time()
  m = hashlib.sha512()
  m.update((payload_string or "").encode('utf-8'))
  hashed_payload = m.hexdigest()
  s = '%s\n%s\n%s\n%s\n%s' % (method, url, query_string or "", hashed_payload, t)
  sign = hmac.new(gateio_secret.encode('utf-8'), s.encode('utf-8'), hashlib.sha512).hexdigest()
  return {'KEY': gateio_api, 'Timestamp': str(t), 'SIGN': sign}

# Yeni API istegi icin URL ve query parametreleri
url = '/futures/usdt/orders'
query_param = ''
body = json.dumps({
  "contract": gateio_symbol,
  "size": gateio_coin_size,
  "iceberg": 0,
  "price": coin_price_long,
  "tif": "gtc",
  "text": "t-my-custom-id",
  "stp_act": "-"
})

# Imza basliklarini olustur ve istegi gonder
sign_headers = gen_sign('POST', prefix + url, query_param, body)
headers.update(sign_headers)
r = requests.request('POST', host + prefix + url, headers=headers, data=body)
order_response = r.json()
print(order_response)

# "order check" kismi
with open(os.path.join(BASE_DIR, 'gateio', 'order_gateio.json'), 'w') as json_file:
  json.dump(order_response, json_file, indent=4)

# Dinamik degiskenleri ata ve yazdir
gate_id = order_response.get('id')
gate_contrat = order_response.get('contract')
gate_fill_price = float(order_response.get('fill_price'))
gate_size = order_response.get('size')
gate_finish_as = order_response.get('finish_as')
gate_update_time = order_response.get('update_time')
gate_finish_time = order_response.get('finish_time')
gate_label = order_response.get('label', '')

print(f"{gate_id} {gate_contrat} {gate_fill_price} {gate_size} {gate_finish_as}")

# "order check" dongusu
while True:
  with open(os.path.join(BASE_DIR, 'gateio', 'order_gateio.json'), 'r') as json_file:
      order_data = json.load(json_file)
      gate_finish_as = order_data.get('finish_as')
      gate_label = order_data.get('label', '')

  if gate_label == 'LIQUIDATE_IMMEDIATELY':
      time.sleep(1)
      continue  # En basa don

  if gate_finish_as != "filled":
      subprocess.run(["python3", os.path.join(BASE_DIR, "gateio", "kapat.py")])
      time.sleep(0.5)
      continue  # En basa don

  # "yuzde hesapla" adimi
  while True:
      # Yeni fiyat bilgilerini al
      response = requests.get(f"https://api.gateio.ws/api/v4/futures/usdt/contracts/{gateio_symbol}")
      data = response.json()
      gate_new_price = float(data['last_price'])

      # Sonuclari yazdir
      print(f"{gateio_symbol} : {gate_new_price}")

      # Yeni fiyat bilgilerini JSON formatinda yaz
      new_price_data = {
          "name": gateio_symbol,
          "last_price": gate_new_price,
          "leverage_max": data['leverage_max']
      }

      with open(os.path.join(BASE_DIR, 'gateio', 'newprice_gateio.json'), 'w') as json_file:
          json.dump(new_price_data, json_file, indent=4)

      # Yuzde hesapla
      yuzde = round(gate_new_price / gate_fill_price, 3)

      # Yuzdeyi zaman etiketli olarak yaz
      yuzde_data = {
          "time": time.time(),
          "yuzde": yuzde
      }

      with open(os.path.join(BASE_DIR, 'gateio', 'yuzde.json'), 'w') as json_file:
          json.dump(yuzde_data, json_file, indent=4)

      # "close_yuzde" degerini oku
      with open(os.path.join(BASE_DIR, 'gateio', 'secret.json'), 'r') as file:
          perp_secrets = json.load(file)
          close_yuzde = float(perp_secrets['gateio_example']['close_yuzde'])

      # Yuzde degerini karsilastir
      if yuzde >= close_yuzde:
          subprocess.run(["python3", os.path.join(BASE_DIR, "gateio", "kapat.py")])
          break  # Hedef gerceklesti, donguden cik

      # Hedef gerceklesmedi, 1 saniye bekle ve tekrar dene
      time.sleep(1)

  # Eger 'label' 'LIQUIDATE_IMMEDIATELY' ise 1 saniye bekle ve basa don
  if order_response.get('label') == 'LIQUIDATE_IMMEDIATELY':
      time.sleep(1)
      continue  # En basa don
