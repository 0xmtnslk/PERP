#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upbit Duyuru Sayfası Tarayıcısı
Upbit'in duyuru sayfasından yeni coin listeleme duyurularını takip eder
"""
import os
import json
import time
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import re

class UpbitAnnouncementScraper:
    def __init__(self):
        self.BASE_DIR = os.getcwd()
        self.announcement_url = "https://upbit.com/service_center/notice"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Dosya yolları
        self.announcement_file = os.path.join(self.BASE_DIR, "PERP", "announcement_coins.json")
        self.last_check_file = os.path.join(self.BASE_DIR, "PERP", "last_announcement_check.json")
        
        # Yeni coin patternleri (Korece ve İngilizce)
        self.new_coin_patterns = [
            r'신규.*상장',  # 신규 상장
            r'원화.*마켓.*추가',  # 원화 마켓 추가  
            r'USDT.*마켓.*추가',  # USDT 마켓 추가
            r'new.*listing',  # new listing
            r'market.*launch',  # market launch
            r'trading.*support',  # trading support
        ]
        
    def get_announcements(self):
        """Upbit duyuru sayfasından son duyuruları al"""
        try:
            response = requests.get(self.announcement_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Duyuru listesini bul (Upbit'in yapısına göre)
            announcements = []
            
            # Başlık ve tarih bilgilerini çek
            notice_items = soup.find_all('tr', class_='notice-item') or soup.find_all('div', class_='notice-list-item')
            
            if not notice_items:
                # Alternatif selector'lar dene
                notice_items = soup.find_all('a', href=re.compile(r'/service_center/notice/\d+'))
            
            for item in notice_items[:10]:  # Son 10 duyuru
                try:
                    # Başlık
                    title_elem = item.find('td', class_='title') or item.find('div', class_='title') or item.find('span', class_='title')
                    if not title_elem:
                        title_elem = item
                    
                    title = title_elem.get_text(strip=True) if title_elem else ""
                    
                    # Tarih
                    date_elem = item.find('td', class_='date') or item.find('div', class_='date') or item.find('span', class_='date')
                    date_text = date_elem.get_text(strip=True) if date_elem else ""
                    
                    # Link
                    link_elem = item.find('a') or item
                    link = link_elem.get('href', '') if hasattr(link_elem, 'get') else ''
                    if link and not link.startswith('http'):
                        link = 'https://upbit.com' + link
                    
                    if title:
                        announcements.append({
                            'title': title,
                            'date': date_text,
                            'link': link,
                            'timestamp': datetime.now().isoformat()
                        })
                        
                except Exception as e:
                    print(f"⚠️ Duyuru parse hatası: {e}")
                    continue
            
            return announcements
            
        except requests.RequestException as e:
            print(f"❌ Upbit duyuru sayfası erişim hatası: {e}")
            return []
        except Exception as e:
            print(f"❌ Beklenmeyen hata: {e}")
            return []
    
    def extract_coin_symbols(self, title, announcement_text=""):
        """Duyuru başlığından coin sembollerini çıkar"""
        symbols = []
        
        # Yaygın coin sembolleri pattern'i
        coin_pattern = r'\b([A-Z]{3,8})\b'
        
        # Başlık ve metinleri birleştir
        full_text = f"{title} {announcement_text}".upper()
        
        # Coin sembollerini bul
        potential_symbols = re.findall(coin_pattern, full_text)
        
        # Filtreleme - yaygın olmayan kelimeleri çıkar
        exclude_words = {
            'UPBIT', 'KRW', 'BTC', 'ETH', 'USDT', 'API', 'NEW', 'THE', 'AND', 'FOR', 'WITH',
            'FROM', 'MARKET', 'TRADING', 'SERVICE', 'NOTICE', 'UPDATE', 'SYSTEM'
        }
        
        for symbol in potential_symbols:
            if symbol not in exclude_words and len(symbol) >= 3:
                symbols.append(symbol)
        
        return list(set(symbols))  # Duplicateları kaldır
    
    def is_new_coin_announcement(self, title):
        """Duyurunun yeni coin listeleme duyurusu olup olmadığını kontrol et"""
        title_lower = title.lower()
        
        for pattern in self.new_coin_patterns:
            if re.search(pattern, title_lower, re.IGNORECASE):
                return True
        
        return False
    
    def get_last_check_time(self):
        """Son kontrol zamanını al"""
        try:
            if os.path.exists(self.last_check_file):
                with open(self.last_check_file, 'r') as f:
                    data = json.load(f)
                return datetime.fromisoformat(data.get('last_check', ''))
        except:
            pass
        
        # İlk çalıştırma için 1 saat öncesi
        return datetime.now() - timedelta(hours=1)
    
    def save_last_check_time(self):
        """Son kontrol zamanını kaydet"""
        try:
            data = {'last_check': datetime.now().isoformat()}
            with open(self.last_check_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"⚠️ Son kontrol zamanı kaydetme hatası: {e}")
    
    def save_new_coins(self, coins):
        """Bulunan yeni coinleri kaydet"""
        if not coins:
            return
            
        try:
            # Mevcut verileri oku
            existing_data = []
            if os.path.exists(self.announcement_file):
                with open(self.announcement_file, 'r') as f:
                    existing_data = json.load(f)
            
            # Yeni verileri ekle
            for coin in coins:
                existing_data.append({
                    'timestamp': datetime.now().isoformat(),
                    'source': 'announcement_scraper',
                    'coin_data': coin
                })
            
            # Dosyaya kaydet
            with open(self.announcement_file, 'w') as f:
                json.dump(existing_data, f, indent=2, ensure_ascii=False)
            
            print(f"💾 {len(coins)} yeni coin announcement kaydedildi")
            
        except Exception as e:
            print(f"❌ Coin kaydetme hatası: {e}")
    
    def process_announcements(self, announcements):
        """Duyuruları işle ve yeni coinleri tespit et"""
        new_coins = []
        last_check = self.get_last_check_time()
        
        for announcement in announcements:
            try:
                # Yeni coin duyurusu mu kontrol et
                if self.is_new_coin_announcement(announcement['title']):
                    print(f"🔍 Yeni coin duyurusu tespit edildi: {announcement['title']}")
                    
                    # Coin sembollerini çıkar
                    symbols = self.extract_coin_symbols(announcement['title'])
                    
                    if symbols:
                        coin_data = {
                            'symbols': symbols,
                            'title': announcement['title'],
                            'date': announcement['date'],
                            'link': announcement['link'],
                            'detection_time': datetime.now().isoformat()
                        }
                        new_coins.append(coin_data)
                        print(f"🪙 Tespit edilen semboller: {', '.join(symbols)}")
                        
                        # En son sembolü PERP formatında kaydet (mevcut sisteme entegre için)
                        if symbols:
                            latest_symbol = symbols[-1] + "USDT_UMCBL"
                            perp_file = os.path.join(self.BASE_DIR, "PERP", "new_coin_output.txt")
                            try:
                                with open(perp_file, 'w') as f:
                                    f.write(latest_symbol)
                                print(f"📝 PERP formatında kaydedildi: {latest_symbol}")
                            except Exception as e:
                                print(f"⚠️ PERP dosya yazma hatası: {e}")
                
            except Exception as e:
                print(f"⚠️ Duyuru işleme hatası: {e}")
        
        return new_coins
    
    def run_continuous(self):
        """Sürekli tarama çalıştır"""
        print("🔍 Upbit Duyuru Tarayıcısı başlatıldı")
        print(f"📡 Tarama URL'i: {self.announcement_url}")
        
        while True:
            try:
                print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Duyuru kontrolü...")
                
                # Duyuruları al
                announcements = self.get_announcements()
                
                if announcements:
                    print(f"📢 {len(announcements)} duyuru alındı")
                    
                    # Yeni coinleri işle
                    new_coins = self.process_announcements(announcements)
                    
                    if new_coins:
                        self.save_new_coins(new_coins)
                        print(f"🎉 {len(new_coins)} yeni coin tespit edildi!")
                    else:
                        print("⭕ Yeni coin duyurusu bulunamadı")
                else:
                    print("⚠️ Duyuru alınamadı")
                
                # Son kontrol zamanını güncelle
                self.save_last_check_time()
                
                # 60 saniye bekle
                print("💤 60 saniye bekleniyor...")
                time.sleep(60)
                
            except KeyboardInterrupt:
                print("\n👋 Duyuru tarayıcısı durduruldu")
                break
            except Exception as e:
                print(f"❌ Beklenmeyen hata: {e}")
                print("⏳ 30 saniye bekleyip tekrar deneniyor...")
                time.sleep(30)

def main():
    """Ana fonksiyon"""
    scraper = UpbitAnnouncementScraper()
    scraper.run_continuous()

if __name__ == "__main__":
    main()