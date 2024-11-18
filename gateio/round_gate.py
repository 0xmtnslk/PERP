import json
import time
import os
import requests

# mark_price_round ile round_gate eslesmesini tanimla
round_gate_mapping = {
  0.1: 1,
  0.01: 2,
  0.001: 3,
  0.0001: 4,
  0.00001: 5,
  1e-05: 5,
  0.000001: 6,
  1e-06: 6,
  0.0000001: 7,
  1e-07: 7,
  0.00000001: 8,
  1e-08: 8,
  0.000000001: 9,
  1e-09: 9
}

# Dosya yollari
secret_file_path = '/root/secret.json'
bitget_file_path = '/root/PERP/secret.json'
gateio_file_path = '/root/gateio/secret.json'
new_coin_file_path = '/root/gateio/new_coin_output.txt'
round_gate_file_path = '/root/gateio/round_gate.txt'

# Sonsuz dongu
while True:
  try:
      # new_coin_output.txt dosyasindan sembolu oku
      with open(new_coin_file_path, 'r') as file:
          round_symbol = file.read().strip()

      # API'den veri cek
      api_url = f"https://api.gateio.ws/api/v4/futures/usdt/contracts/{round_symbol}"
      response = requests.get(api_url)
      response.raise_for_status()
      contract_data = response.json()

      # mark_price_round degerini al
      gateio_mark_price_round = float(contract_data.get('mark_price_round', 0))
      print(f"round_symbol: {round_symbol}, mark_price_round: {gateio_mark_price_round}")

      # round_gate degerini belirle
      rounded_value = round(gateio_mark_price_round, 10)
      round_gate = round_gate_mapping.get(rounded_value, None)

      # round_gate degerini dosyaya yaz
      if round_gate is not None:
          with open(round_gate_file_path, 'w') as file:
              file.write(str(round_gate))
          print(f"round_gate: {round_gate}")
      else:
          print(f"Uyari: mark_price_round icin eslesen round_gate bulunamadi: {gateio_mark_price_round}")

  except FileNotFoundError:
      print("Hata: Belirtilen dosya bulunamadi.")
  except json.JSONDecodeError:
      print("Hata: JSON verisi cozulemedi.")
  except requests.exceptions.RequestException as e:
      print(f"API hatasi: {e}")
  except Exception as e:
      print(f"Beklenmeyen bir hata olustu: {e}")

  # Bir sonraki yinelemeden once 1 saniye bekle
  time.sleep(1)
