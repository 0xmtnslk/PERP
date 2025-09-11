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
from notification_config import notification_config

class UpbitAnnouncementScraper:
    def __init__(self):
        self.BASE_DIR = os.getcwd()
        self.announcement_url = "https://upbit.com/service_center/notice"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Centralized notification configuration kullan
        self.announcement_file = notification_config.announcement_coins_file
        self.last_check_file = notification_config.last_announcement_check_file
        self.processed_coins_file = os.path.join(self.BASE_DIR, "PERP", "processed_coins.json")
        print(f"🔧 Upbit Scraper using centralized config:")
        print(f"   📁 Announcements: {self.announcement_file}")
        print(f"   📁 Last check: {self.last_check_file}")
        print(f"   📁 Processed coins: {self.processed_coins_file}")
        
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
        """Upbit duyuru sayfasından son duyuruları al (React SPA uyumlu)"""
        announcements = []
        
        # METHOD 1: Selenium WebDriver ile dinamik içerik yükleme
        try:
            announcements = self.get_announcements_selenium()
            if announcements:
                print(f"✅ Selenium ile {len(announcements)} duyuru alındı")
                return announcements
        except Exception as e:
            print(f"⚠️ Selenium hatası: {e}")
        
        # METHOD 2: Fallback - manuel test duyuruları (geliştirme için)
        try:
            announcements = self.get_test_announcements()
            if announcements:
                print(f"🔧 Test duyuruları kullanılıyor: {len(announcements)}")
                return announcements
        except Exception as e:
            print(f"⚠️ Test duyuruları hatası: {e}")
        
        # METHOD 3: Empty fallback
        print("❌ Hiçbir yöntem çalışmadı")
        return []
    
    def get_announcements_selenium(self):
        """Selenium WebDriver ile React SPA'dan duyuru çekme"""
        try:
            # Headless Chrome için selenium import
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.chrome.options import Options
            
            # Chrome seçenekleri
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            
            # WebDriver başlat
            driver = webdriver.Chrome(options=chrome_options)
            
            try:
                print("🌐 Upbit sayfası yükleniyor (Selenium)...")
                driver.get(self.announcement_url)
                
                # Sayfanın yüklenmesini bekle (max 15 saniye)
                WebDriverWait(driver, 15).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
                
                # React bileşenlerinin yüklenmesi için ek bekleme
                time.sleep(3)
                
                # Duyuru elementlerini farklı selector'larla dene
                announcement_selectors = [
                    # Modern React selectors
                    '[data-testid*="notice"]',
                    '[class*="notice"]',
                    '[class*="announcement"]',
                    '[class*="item"]',
                    'a[href*="/service_center/notice/"]',
                    # Generic selectors
                    'article',
                    'li',
                    '.list-item',
                    '[role="listitem"]'
                ]
                
                announcements = []
                
                for selector in announcement_selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        
                        if elements and len(elements) > 0:
                            print(f"📋 {selector}: {len(elements)} element bulundu")
                            
                            for i, element in enumerate(elements[:10]):  # İlk 10 element
                                try:
                                    # Element text'ini al
                                    title = element.text.strip()
                                    
                                    # Link varsa al
                                    link = ""
                                    try:
                                        link = element.get_attribute('href') or ""
                                        if not link and element.tag_name != 'a':
                                            # Parent'ta a tag'i ara
                                            parent_link = element.find_element(By.XPATH, './/a | ./ancestor::a[1]')
                                            if parent_link:
                                                link = parent_link.get_attribute('href') or ""
                                    except:
                                        pass
                                    
                                    if title and len(title) > 10:
                                        announcements.append({
                                            'title': title,
                                            'date': datetime.now().strftime('%Y-%m-%d'),
                                            'link': link,
                                            'timestamp': datetime.now().isoformat(),
                                            'method': 'selenium'
                                        })
                                        
                                        print(f"  📄 {i+1}. {title[:80]}...")
                                        
                                except Exception as e:
                                    continue
                            
                            if announcements:
                                break  # İlk başarılı selector'la devam et
                                
                    except Exception as e:
                        continue
                
                return announcements
                
            finally:
                driver.quit()
                
        except ImportError:
            print("⚠️ Selenium bulunamadı: pip install selenium")
            raise
        except Exception as e:
            print(f"❌ Selenium WebDriver hatası: {e}")
            raise
    
    def get_test_announcements(self):
        """Test amaçlı manuel duyurular (gerçek API olmadığında)"""
        # Gerçek Upbit duyuru formatlarını simüle et
        test_announcements = [
            {
                'title': 'Market Support for Arbitrum(ARB) (KRW, BTC, USDT Market)',
                'date': '2024-03-21',
                'link': 'https://upbit.com/service_center/notice/4829',
                'timestamp': datetime.now().isoformat(),
                'method': 'test'
            },
            {
                'title': 'Market Support for Optimism(OP) (KRW, BTC, USDT Market)', 
                'date': '2024-03-20',
                'link': 'https://upbit.com/service_center/notice/4828',
                'timestamp': datetime.now().isoformat(),
                'method': 'test'
            },
            {
                'title': 'Market Support for Polygon(MATIC) (KRW, BTC, USDT Market)',
                'date': '2024-03-19', 
                'link': 'https://upbit.com/service_center/notice/4827',
                'timestamp': datetime.now().isoformat(),
                'method': 'test'
            }
        ]
        
        print("🔧 TEST MOD: Simüle edilmiş duyurular kullanılıyor")
        print("⚠️ Gerçek zamanlı tarama için Selenium gerekli")
        
        return test_announcements
    
    def extract_coin_symbols(self, title, announcement_text=""):
        """Duyuru başlığından coin sembollerini çıkar - özellikle parantez içindeki sembolleri"""
        symbols = []
        
        # ÖNCELİK: Parantez içindeki semboller (Linea(LINEA) formatı)
        parenthesis_pattern = r'\(([A-Z]{2,10})\)'
        parenthesis_symbols = re.findall(parenthesis_pattern, title)
        
        print(f"🔍 Parantez içi arama: '{title}' -> Bulunan: {parenthesis_symbols}")
        
        # Parantez içi sembolleri ekle
        for symbol in parenthesis_symbols:
            if len(symbol) >= 2 and symbol not in ['KRW', 'BTC', 'USDT', 'ETH']:
                symbols.append(symbol)
                print(f"✅ Parantez içi sembol eklendi: {symbol}")
        
        # YEDEK: Normal pattern matching (parantez içi bulunamazsa)
        if not symbols:
            # Market Support pattern'i için özel regex
            market_support_pattern = r'Market Support for\s+(\w+)'
            market_symbols = re.findall(market_support_pattern, title, re.IGNORECASE)
            
            for symbol in market_symbols:
                if symbol.upper() not in ['MARKET', 'SUPPORT', 'FOR', 'UPDATE', 'KRW', 'BTC', 'USDT']:
                    symbols.append(symbol.upper())
                    print(f"✅ Market Support sembol eklendi: {symbol.upper()}")
        
        # Son çare: Genel coin pattern'i
        if not symbols:
            general_pattern = r'\b([A-Z]{3,8})\b'
            potential_symbols = re.findall(general_pattern, title.upper())
            
            exclude_words = {
                'UPBIT', 'KRW', 'BTC', 'ETH', 'USDT', 'API', 'NEW', 'THE', 'AND', 'FOR', 'WITH',
                'FROM', 'MARKET', 'TRADING', 'SERVICE', 'NOTICE', 'UPDATE', 'SYSTEM', 'SUPPORT'
            }
            
            for symbol in potential_symbols:
                if symbol not in exclude_words and len(symbol) >= 3:
                    symbols.append(symbol)
        
        unique_symbols = list(set(symbols))
        print(f"🎯 Final semboller: {unique_symbols}")
        return unique_symbols
    
    def is_new_coin_announcement(self, title):
        """Duyurunun yeni coin listeleme duyurusu olup olmadığını kontrol et"""
        title_lower = title.lower()
        
        # Spesifik Upbit pattern'leri
        upbit_patterns = [
            r'market support for.*\(.*market\)',  # Market Support for Linea(LINEA) (KRW, BTC, USDT Market)
            r'신규.*상장',  # 신규 상장  
            r'원화.*마켓.*추가',  # 원화 마켓 추가
            r'usdt.*마켓.*추가',  # USDT 마켓 추가
            r'new.*listing',  # new listing
            r'market.*launch',  # market launch
            r'trading.*support.*market',  # trading support market
        ]
        
        # Önce spesifik pattern'leri kontrol et
        for pattern in upbit_patterns:
            if re.search(pattern, title_lower, re.IGNORECASE):
                print(f"✅ Yeni coin pattern bulundu: '{pattern}' -> '{title}'")
                return True
        
        # Eski pattern'leri de kontrol et
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
    
    def load_processed_coins(self):
        """Daha önce işlenmiş coinleri yükle"""
        try:
            if os.path.exists(self.processed_coins_file):
                with open(self.processed_coins_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return []
        except Exception as e:
            print(f"⚠️ Processed coins yükleme hatası: {e}")
            return []
    
    def save_processed_coin(self, symbol, title, announcement_data):
        """Yeni işlenmiş coin'i kaydet"""
        try:
            processed_coins = self.load_processed_coins()
            
            new_entry = {
                'symbol': symbol,
                'title': title,
                'perp_symbol': symbol + 'USDT_UMCBL',
                'processed_at': datetime.now().isoformat(),
                'announcement_data': announcement_data
            }
            
            processed_coins.append(new_entry)
            
            with open(self.processed_coins_file, 'w', encoding='utf-8') as f:
                json.dump(processed_coins, f, indent=2, ensure_ascii=False)
            
            print(f"💾 İşlenmiş coin kaydedildi: {symbol} -> {symbol}USDT_UMCBL")
            
        except Exception as e:
            print(f"❌ Processed coin kaydetme hatası: {e}")
    
    def is_coin_already_processed(self, symbol):
        """Coin daha önce işlenmiş mi kontrol et"""
        processed_coins = self.load_processed_coins()
        
        for entry in processed_coins:
            if entry.get('symbol') == symbol:
                processed_at = entry.get('processed_at', '')
                print(f"⚠️ {symbol} daha önce işlenmiş: {processed_at}")
                return True
        
        return False
    
    def filter_new_coins_only(self, symbols, announcement_title):
        """Sadece daha önce işlenmemiş coinleri filtrele"""
        new_symbols = []
        
        for symbol in symbols:
            if not self.is_coin_already_processed(symbol):
                new_symbols.append(symbol)
                print(f"✅ YENİ COIN: {symbol} (daha önce işlenmemiş)")
            else:
                print(f"🔄 ATLANIYOR: {symbol} (daha önce işlenmiş)")
        
        return new_symbols
    
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
                        
                        # En son sembolü PERP formatında kaydet (centralized config kullanarak)
                        if symbols:
                            latest_symbol = symbols[-1] + "USDT_UMCBL"
                            perp_file = notification_config.new_coin_output_txt
                            try:
                                with open(perp_file, 'w') as f:
                                    f.write(latest_symbol)
                                print(f"📝 PERP formatında kaydedildi (centralized): {latest_symbol}")
                                print(f"   📁 Path: {perp_file}")
                            except Exception as e:
                                print(f"⚠️ PERP dosya yazma hatası: {e}")
                
            except Exception as e:
                print(f"⚠️ Duyuru işleme hatası: {e}")
        
        return new_coins
    
    def run_continuous(self):
        """Sürekli tarama çalıştır - rate limiting ile"""
        print("🔍 Upbit Duyuru Tarayıcısı başlatıldı")
        print(f"📡 Tarama URL'i: {self.announcement_url}")
        print("⚠️ Rate limiting aktif: 5 dakikada bir kontrol")
        
        # İlk kontrol
        consecutive_errors = 0
        
        while True:
            try:
                print(f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Duyuru kontrolü...")
                
                # Duyuruları al
                announcements = self.get_announcements()
                
                if announcements:
                    print(f"📢 {len(announcements)} duyuru alındı")
                    consecutive_errors = 0  # Başarılı istekte hata sayısını sıfırla
                    
                    # İlk 5 duyuruyu detaylı incele
                    for i, announcement in enumerate(announcements[:5], 1):
                        print(f"\n📋 Duyuru {i}: {announcement['title']}")
                        
                        # Yeni coin kontrolü
                        if self.is_new_coin_announcement(announcement['title']):
                            print(f"🚨 YENİ COİN DUYURUSU TESPİT EDİLDİ!")
                            
                            # Sembolleri çıkar
                            symbols = self.extract_coin_symbols(announcement['title'])
                            
                            if symbols:
                                print(f"🪙 Tespit edilen semboller: {symbols}")
                                
                                # SADECE YENİ COİNLERİ FİLTRELE
                                new_symbols = self.filter_new_coins_only(symbols, announcement['title'])
                                
                                if new_symbols:
                                    # İlk yeni sembolü kullan
                                    main_symbol = new_symbols[0]
                                    
                                    # PERP formatında kaydet
                                    perp_symbol = main_symbol + "USDT_UMCBL"
                                    perp_file = os.path.join(self.BASE_DIR, "PERP", "new_coin_output.txt")
                                    
                                    try:
                                        with open(perp_file, 'w') as f:
                                            f.write(perp_symbol)
                                        print(f"🚀 TETİKLENDİ! PERP formatında kaydedildi: {perp_symbol}")
                                        
                                        # İşlenmiş coin olarak kaydet
                                        self.save_processed_coin(main_symbol, announcement['title'], {
                                            'date': announcement['date'],
                                            'link': announcement['link']
                                        })
                                        
                                        # Kayıt dosyasına da ekle
                                        coin_data = [{
                                        'symbols': symbols,
                                        'title': announcement['title'],
                                        'date': announcement['date'],
                                        'link': announcement['link'],
                                        'detection_time': datetime.now().isoformat(),
                                        'triggered': True
                                    }]
                                    self.save_new_coins(coin_data)
                                    
                                    # Telegram bot için bildirim dosyası oluştur
                                    notification_data = {
                                        "type": "NEW_COIN",
                                        "timestamp": datetime.now().isoformat(),
                                        "coins": []
                                    }
                                    
                                    for symbol in symbols:
                                        notification_data["coins"].append({
                                            "symbol": symbol,
                                            "name": announcement['title'],
                                            "price": 0.0,  # Fiyat bilgisi için ayrı API call gerekebilir
                                            "perp_symbol": symbol + "USDT_UMCBL"
                                        })
                                    
                                    # Telegram bot için bildirim dosyası oluştur (centralized config)
                                    telegram_notification_file = notification_config.telegram_notifications_file
                                    try:
                                        with open(telegram_notification_file, 'w') as f:
                                            json.dump(notification_data, f, indent=2, ensure_ascii=False)
                                        print(f"📱 Telegram bildirimi hazırlandı (centralized): {len(symbols)} coin")
                                        print(f"   📁 Path: {telegram_notification_file}")
                                    except Exception as e:
                                        print(f"⚠️ Telegram bildirimi oluşturma hatası: {e}")
                                    
                                        print(f"🎯 OTOMASYON TETİKLENDİ: {main_symbol}")
                                        
                                    except Exception as e:
                                        print(f"❌ Dosya yazma hatası: {e}")
                                else:
                                    print("🔄 Tüm tespit edilen coinler daha önce işlenmiş, tetikleme yapılmadı")
                            else:
                                print("⚠️ Sembol çıkarılamadı")
                        else:
                            print("ℹ️ Normal duyuru")
                
                else:
                    print("⚠️ Duyuru alınamadı")
                    consecutive_errors += 1
                
                # Son kontrol zamanını güncelle
                self.save_last_check_time()
                
                # Rate limiting - banlama riskini azaltmak için
                if consecutive_errors > 3:
                    wait_time = 600  # 10 dakika bekle
                    print(f"⚠️ Çoklu hata nedeniyle {wait_time//60} dakika bekleniyor...")
                else:
                    wait_time = 300  # Normal: 5 dakikada bir kontrol
                    print(f"💤 {wait_time//60} dakika bekleniyor...")
                
                time.sleep(wait_time)
                
            except KeyboardInterrupt:
                print("\n👋 Duyuru tarayıcısı durduruldu")
                break
            except Exception as e:
                print(f"❌ Beklenmeyen hata: {e}")
                consecutive_errors += 1
                wait_time = min(300 + (consecutive_errors * 60), 900)  # Max 15 dakika
                print(f"⏳ {wait_time//60} dakika bekleyip tekrar deneniyor...")
                time.sleep(wait_time)

def main():
    """Ana fonksiyon"""
    scraper = UpbitAnnouncementScraper()
    scraper.run_continuous()

if __name__ == "__main__":
    main()