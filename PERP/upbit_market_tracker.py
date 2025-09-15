# -*- coding: utf-8 -*-
import requests
import json
import time
import os
import sys
from datetime import datetime

# Ana dizini sys.path'e ekle (notification_config import etmek için)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from notification_config import notification_config

# Kullanicinin ev dizininde bir alt dizin olustur
BASE_DIR = os.path.join(os.getcwd(), "PERP")

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
  
  # Son eklenen USDT coinini SAFEUSDT_UMCBL formatinda yaz (centralized config kullanarak)
  last_new_coin = new_pairs[-1]['market'].split('-')[1] + "USDT_UMCBL"
  # Centralized notification config kullan
  new_coin_file = notification_config.new_coin_output_txt
  with open(new_coin_file, 'w', encoding='utf-8') as file:
      file.write(last_new_coin)
  print(f"📝 New coin yazıldı (centralized): {last_new_coin}")
  print(f"   📁 Path: {new_coin_file}")

def initialize_state_files():
  """Durum dosyalarını başlat - sadece yoksa boş oluştur, varsa koru"""
  files_to_check = ["upbit_ciftler_1.json", "upbit_ciftler_2.json", "seen_markets.json"]
  
  for filename in files_to_check:
    full_path = os.path.join(BASE_DIR, filename)
    if not os.path.exists(full_path):
      if filename == "seen_markets.json":
        # seen_markets için özel başlangıç yapısı
        initial_data = {
          "last_update": datetime.now().isoformat(),
          "usdt_markets": []
        }
      else:
        initial_data = []
      
      with open(full_path, 'w', encoding='utf-8') as f:
        json.dump(initial_data, f, indent=4, ensure_ascii=False)
      print(f"📁 {filename} başlangıç dosyası oluşturuldu")
    else:
      print(f"✅ {filename} mevcut - korundu")

def load_seen_markets():
  """Daha önce görülen USDT marketlerini yükle"""
  seen_markets_file = os.path.join(BASE_DIR, "seen_markets.json")
  try:
    with open(seen_markets_file, 'r', encoding='utf-8') as f:
      data = json.load(f)
    return set(data.get('usdt_markets', []))
  except (FileNotFoundError, json.JSONDecodeError):
    return set()

def save_seen_markets(markets_set):
  """Görülen USDT marketlerini kaydet"""
  seen_markets_file = os.path.join(BASE_DIR, "seen_markets.json")
  data = {
    "last_update": datetime.now().isoformat(),
    "usdt_markets": list(markets_set)
  }
  with open(seen_markets_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=4, ensure_ascii=False)

def main():
  # Durum dosyalarını kontrollü olarak başlat
  initialize_state_files()
  
  # Daha önce görülen marketleri yükle
  seen_markets = load_seen_markets()
  print(f"🔄 Daha önce görülen USDT marketleri: {len(seen_markets)}")

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

          # Yeni ciftleri bul - sadece USDT marketleri kontrol et
          old_usdt_markets = [pair['market'] for pair in old_data if pair['market'].startswith('USDT-')]
          new_usdt_markets = [pair['market'] for pair in new_data if pair['market'].startswith('USDT-')]
          
          # Seen markets ile kontrol et - hem eski data hem de persistent state
          current_markets_set = set(new_usdt_markets)
          old_markets_set = set(old_usdt_markets)
          
          # Gerçekten yeni olan marketleri bul - hem file comparison hem de seen_markets kontrolü
          truly_new_markets = []
          for market in new_usdt_markets:
            # Hem old_data'da hem de seen_markets'te yoksa gerçekten yeni
            if market not in old_markets_set and market not in seen_markets:
              truly_new_markets.append(market)
          
          if truly_new_markets:
              # Yeni market'ların full data'sını al
              new_pairs = [pair for pair in new_data if pair['market'] in truly_new_markets]
              append_new_pairs_to_file([new_pairs[-1]])
              print(f"{datetime.now()}: YENİ COIN TESPİT EDİLDİ!")
              print(f"Yeni eklenen ciftler: {[p['market'] for p in new_pairs]}")
              
              # Seen markets'e yeni marketleri ekle
              seen_markets.update(truly_new_markets)
              save_seen_markets(seen_markets)
              print(f"💾 Seen markets güncellendi: {len(seen_markets)} total")
          else:
              # Mevcut marketleri seen_markets'e ekle (ilk çalıştırmada persistence için)
              if current_markets_set:
                initial_size = len(seen_markets)
                seen_markets.update(current_markets_set)
                if len(seen_markets) > initial_size:
                  save_seen_markets(seen_markets)
                  print(f"🔄 Mevcut marketler persistence'e eklendi: {len(seen_markets)} total")
              
              # Debug için - hangi marketler var kontrol et
              print(f"{datetime.now()}: Kontrol - USDT marketleri: {len(new_usdt_markets)} (yeni yok)")

          # Toggle degiskenini degistir
          toggle = not toggle

          # 1 saniye bekle
          time.sleep(1)

      except Exception as e:
          print(f"Hata olustu: {e}")
          time.sleep(5)  # Hata durumunda 5 saniye bekle

if __name__ == "__main__":
  main()
