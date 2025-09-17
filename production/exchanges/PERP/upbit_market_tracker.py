# -*- coding: utf-8 -*-
import requests
import json
import time
import os
import sys
import threading
from datetime import datetime, timedelta

# notification_config import etmek için production/core dizinini sys.path'e ekle
current_file_path = os.path.abspath(__file__)
production_dir = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))  # production/
core_dir = os.path.join(production_dir, 'core')
sys.path.append(core_dir)
from notification_config import notification_config

# PERP dizini - yeni directory structure ile uyumlu
# Eğer production/exchanges/PERP içindeyse, bu dizini kullan
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir.endswith('production/exchanges/PERP'):
    BASE_DIR = current_dir
else:
    # Backward compatibility için PERP dizinini kullan
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

def heartbeat_writer():
  """Health file'ını her 60 saniyede bir günceller"""
  health_file = "production/monitoring/market_tracker_health.txt"
  while True:
    try:
      with open(health_file, 'w') as f:
        f.write(f"{datetime.now().isoformat()}\n")
    except Exception as e:
      print(f"❌ Health file yazma hatası: {e}")
    time.sleep(60)

def start_heartbeat():
  """Heartbeat thread'ini başlat"""
  heartbeat_thread = threading.Thread(target=heartbeat_writer, daemon=True)
  heartbeat_thread.start()
  print("💓 Market Tracker heartbeat başlatıldı")

def check_announcement_coins():
  """Announcement scraper'dan gelen yeni coin tespitlerini kontrol et"""
  try:
    announcement_file = notification_config.announcement_coins_file
    if os.path.exists(announcement_file):
      with open(announcement_file, 'r', encoding='utf-8') as f:
        announcements = json.load(f)
      
      # Son 10 dakika içindeki duyuruları kontrol et
      cutoff_time = datetime.now() - timedelta(minutes=10)
      
      new_coins_from_announcements = []
      for announcement in announcements:
        try:
          announcement_time = datetime.fromisoformat(announcement['timestamp'])
          if announcement_time > cutoff_time:
            coin_data = announcement['coin_data']
            if 'symbols' in coin_data:
              for symbol in coin_data['symbols']:
                # USDT market formatına çevir
                market_name = f'USDT-{symbol}'
                new_coins_from_announcements.append({
                  'market': market_name,
                  'korean_name': coin_data.get('title', ''),
                  'english_name': symbol,
                  'source': 'announcement_scraper',
                  'detection_time': announcement['timestamp']
                })
                print(f"📢 Announcement'dan yeni coin: {market_name}")
        except Exception as e:
          print(f"⚠️ Announcement parsing hatası: {e}")
          continue
      
      return new_coins_from_announcements
  except Exception as e:
    print(f"⚠️ Announcement dosyası okuma hatası: {e}")
  
  return []

def main():
  # Durum dosyalarını kontrollü olarak başlat
  initialize_state_files()
  
  # Heartbeat başlat
  start_heartbeat()
  
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
          
          # Announcement scraper'dan gelen yeni coinleri de kontrol et
          announcement_coins = check_announcement_coins()
          for coin in announcement_coins:
            market = coin['market']
            if market not in old_markets_set and market not in seen_markets:
              if market not in truly_new_markets:
                truly_new_markets.append(market)
                print(f"📢 Announcement'dan ek yeni coin: {market}")
          
          if truly_new_markets:
              # Yeni market'ların full data'sını al (API + Announcement)
              api_new_pairs = [pair for pair in new_data if pair['market'] in truly_new_markets]
              
              # Announcement coins için de pair data oluştur
              combined_new_pairs = api_new_pairs.copy()
              for coin in announcement_coins:
                if coin['market'] in truly_new_markets:
                  # API'de bulunamazsa announcement data'sından pair oluştur
                  if not any(p['market'] == coin['market'] for p in api_new_pairs):
                    combined_new_pairs.append({
                      'market': coin['market'],
                      'korean_name': coin['korean_name'],
                      'english_name': coin['english_name']
                    })
              
              if combined_new_pairs:
                append_new_pairs_to_file([combined_new_pairs[-1]])
                print(f"{datetime.now()}: YENİ COIN TESPİT EDİLDİ!")
                print(f"API'den: {[p['market'] for p in api_new_pairs]}")
                print(f"Announcement'dan: {[c['market'] for c in announcement_coins if c['market'] in truly_new_markets]}")
                
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
