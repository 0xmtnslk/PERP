# -*- coding: utf-8 -*-
import requests
import json
import time
import os
from datetime import datetime

# Kullanicinin ev dizininde bir alt dizin olustur
BASE_DIR = os.path.expanduser("~/PERP/")

# Dizinin var olup olmadigini kontrol et, yoksa olustur
if not os.path.exists(BASE_DIR):
  os.makedirs(BASE_DIR)

def get_market_data():
  """Upbit API'den market verilerini ceker"""
  url = "https://api.upbit.com/v1/market/all"
  response = requests.get(url)
  if response.status_code == 200:
      return response.json()
  else:
      print(f"API Hatasi: {response.status_code}")
      return []

def save_to_file(data, filename):
  """Veriyi JSON formatinda dosyaya kaydeder"""
  full_path = os.path.join(BASE_DIR, filename)
  with open(full_path, 'w', encoding='utf-8') as f:
      json.dump(data, f, indent=4, ensure_ascii=False)
  print(f"{filename} dosyasina yazildi.")

def read_from_file(filename):
  """Dosyadan veriyi okur"""
  full_path = os.path.join(BASE_DIR, filename)
  try:
      with open(full_path, 'r', encoding='utf-8') as f:
          return json.load(f)
  except FileNotFoundError:
      return []
  except json.JSONDecodeError:
      return []

def append_new_pairs_to_file(new_pairs):
  """Yeni ciftleri upbit_new_list.json dosyasina ekler"""
  if not new_pairs:
      return

  timestamp = datetime.now().isoformat()
  new_entry = {
      "timestamp": timestamp,
      "new_pairs": new_pairs
  }
  
  existing_data = read_from_file("upbit_new_list.json")
  existing_data.append(new_entry)
  save_to_file(existing_data, "upbit_new_list.json")
  
  # Son eklenen USDT coinini SAFEUSDT_UMCBL formatinda yaz
  last_new_coin = new_pairs[-1]['market'].split('-')[1] + "USDT_UMCBL"
  with open(os.path.join(BASE_DIR, "new_coin_output.txt"), 'w', encoding='utf-8') as file:
      file.write(last_new_coin)

def main():
  # Ilk calistirmada dosyalari bos olarak baslat
  save_to_file([], "upbit_ciftler_1.json")
  save_to_file([], "upbit_ciftler_2.json")

  toggle = True  # Dosya yazma sirasini kontrol etmek icin

  while True:
      try:
          # Yeni veriyi cek
          new_data = get_market_data()
          if not new_data:
              time.sleep(1)
              continue

          # Dosya sirasina gore yazma islemi
          if toggle:
              old_data = read_from_file("upbit_ciftler_1.json")
              save_to_file(new_data, "upbit_ciftler_2.json")
          else:
              old_data = read_from_file("upbit_ciftler_2.json")
              save_to_file(new_data, "upbit_ciftler_1.json")

          # Yeni ciftleri bul
          new_pairs = [pair for pair in new_data if pair not in old_data and pair['market'].startswith('USDT-')]
          if new_pairs:
              # Sadece USDT paritesi olan yeni ciftleri ekle
              append_new_pairs_to_file([new_pairs[-1]])
              print(f"{datetime.now()}: Yeni ciftler tespit edildi ve kaydedildi")
              print("Yeni eklenen ciftler:", new_pairs)

          # Toggle degiskenini degistir
          toggle = not toggle

          # 1 saniye bekle
          time.sleep(1)

      except Exception as e:
          print(f"Hata olustu: {e}")
          time.sleep(5)  # Hata durumunda 5 saniye bekle

if __name__ == "__main__":
  main()
