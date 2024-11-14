import requests
import json
import time
import hashlib
import hmac
import subprocess

host = "https://api.gateio.ws"
prefix = "/api/v4"
headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}

# secret.json dosyasini oku
with open('/root/gateio/secret.json', 'r') as file:
  gateio_secrets = json.load(file)['gateio_example']

# Degiskenleri tanimla
gateio_api = gateio_secrets['api_key']
gateio_secret = gateio_secrets['secret_key']
gateio_open_USDT = float(gateio_secrets['open_USDT'])  # Burada float() ile donusturme yapiliyor
gateio_initial_symbol = gateio_secrets['initial_symbol']

# Yeni sembol dosyasindan oku
with open('/root/gateio/new_coin_output.txt', 'r') as file:
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
  "mark_price_round": gateio_mark_price_round  # Yeni alanÃ„Â± ekle
}

with open('/root/gateio/perp_sorgu.json', 'w') as json_file:
  json.dump(output_data, json_file, indent=4)

# /root/gateio/perp_sorgu.json dosyasindan verileri oku
with open('/root/gateio/perp_sorgu.json', 'r') as json_file:
  perp_data = json.load(json_file)
  gateio_symbol = perp_data['symbol']
  gateio_leverage = perp_data['leverage']
  gateio_mark_price_round = perp_data['mark_price_round']  # Yeni alanÃ„Â± oku

# Coin fiyatini %1 arttir
coin_price_long = gateio_price * 1.03

# Coin boyutunu hesapla
gateio_coin_size = gateio_open_USDT * gateio_leverage

# /root/gateio/round_gate.txt dosyasindan yuvarlama hassasiyetini oku
with open('/root/gateio/round_gate.txt', 'r') as file:
  round_gate = int(file.read().strip())  # Dosyadan okunan deÄŸeri tam sayÄ±ya Ã§evir

# Coin boyutunu uygun hassasiyete yuvarla
coin_price_long = round(coin_price_long, round_gate)  # Dinamik hassasiyete yuvarla

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
with open('/root/gateio/order_gateio.json', 'w') as json_file:
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
  with open('/root/gateio/order_gateio.json', 'r') as json_file:
      order_data = json.load(json_file)
      gate_finish_as = order_data.get('finish_as')
      gate_label = order_data.get('label', '')

  if gate_label == 'LIQUIDATE_IMMEDIATELY':
      time.sleep(1)
      continue  # En basa don

  if gate_finish_as != "filled":
      subprocess.run(["python3", "/root/gateio/kapat.py"])
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

      with open('/root/gateio/newprice_gateio.json', 'w') as json_file:
          json.dump(new_price_data, json_file, indent=4)

      # Yuzde hesapla
      yuzde = round(gate_new_price / gate_fill_price, 3)

      # Yuzdeyi zaman etiketli olarak yaz
      yuzde_data = {
          "time": time.time(),
          "yuzde": yuzde
      }

      with open('/root/gateio/yuzde.json', 'w') as json_file:
          json.dump(yuzde_data, json_file, indent=4)

      # "close_yuzde" degerini oku
      with open('/root/gateio/secret.json', 'r') as file:
          perp_secrets = json.load(file)
          close_yuzde = float(perp_secrets['gateio_example']['close_yuzde'])

      # Yuzde degerini karsilastir
      if yuzde >= close_yuzde:
          subprocess.run(["python3", "/root/gateio/kapat.py"])
          break  # Hedef gerceklesti, donguden cik

      # Hedef gerceklesmedi, 1 saniye bekle ve tekrar dene
      time.sleep(1)

  # Eger 'label' 'LIQUIDATE_IMMEDIATELY' ise 1 saniye bekle ve basa don
  if order_response.get('label') == 'LIQUIDATE_IMMEDIATELY':
      time.sleep(1)
      continue  # En basa don
