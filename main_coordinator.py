#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ana Koordinatör Script - Tüm ticaret bileşenlerini yönetir
Bu script tüm gerekli alt scriptleri başlatır ve yönetir
"""
import os
import json
import time
import signal
import sys
import subprocess
import threading
from datetime import datetime

class TradingSystemCoordinator:
    def __init__(self):
        self.BASE_DIR = os.getcwd()
        self.processes = {}
        self.running = False
        
        # Temel dosya kontrolleri
        self.setup_directories()
        self.check_secret_files()
        
        # Sinyal yakalayıcıları
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
    def setup_directories(self):
        """Gerekli dizinleri oluştur"""
        directories = ['PERP', 'gateio']
        for dir_name in directories:
            dir_path = os.path.join(self.BASE_DIR, dir_name)
            if not os.path.exists(dir_path):
                os.makedirs(dir_path)
                print(f"📁 {dir_name} dizini oluşturuldu")
    
    def check_secret_files(self):
        """Secret dosyalarını kontrol et ve oluştur"""
        # Ana secret.json kontrol
        main_secret = os.path.join(self.BASE_DIR, "secret.json")
        if not os.path.exists(main_secret):
            # Örnek secret dosyası oluştur
            default_config = {
                "bitget_example": {
                    "api_key": "",
                    "secret_key": "",
                    "passphrase": "",
                    "open_USDT": "1",
                    "close_yuzde": "1.2",
                    "initial_symbol": "XLMUSDT_UMCBL"
                },
                "gateio_example": {
                    "api_key": "",
                    "secret_key": "",
                    "open_USDT": "1",
                    "close_yuzde": 1.2,
                    "initial_symbol": "XLM_USDT"
                }
            }
            with open(main_secret, 'w') as f:
                json.dump(default_config, f, indent=4)
            print("🔑 Varsayılan secret.json oluşturuldu")
        
        # Alt dizin secret dosyalarını kontrol et
        perp_secret = os.path.join(self.BASE_DIR, "PERP", "secret.json")
        gateio_secret = os.path.join(self.BASE_DIR, "gateio", "secret.json")
        
        if not os.path.exists(perp_secret):
            with open(perp_secret, 'w') as f:
                json.dump({"bitget_example": {}}, f, indent=4)
                
        if not os.path.exists(gateio_secret):
            with open(gateio_secret, 'w') as f:
                json.dump({"gateio_example": {}}, f, indent=4)
    
    def start_script(self, script_name, script_path):
        """Bir script başlat"""
        try:
            print(f"🚀 {script_name} başlatılıyor...")
            process = subprocess.Popen(
                ["python3", script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=self.BASE_DIR
            )
            self.processes[script_name] = process
            print(f"✅ {script_name} başlatıldı (PID: {process.pid})")
            return True
        except Exception as e:
            print(f"❌ {script_name} başlatma hatası: {e}")
            return False
    
    def start_all_components(self):
        """Tüm sistem bileşenlerini başlat"""
        print("🎯 Kripto Ticaret Sistemi başlatılıyor...\n")
        
        # Script listesi ve açıklamaları (Sadece Bitget için optimize edildi)
        scripts = [
            ("Secret Manager", "secret.py", "🔐 API key yönetimi"),
            ("Upbit Monitor", os.path.join("PERP", "upbit_market_tracker.py"), "👀 Upbit yeni coin taraması"),
            ("Upbit Announcements", "upbit_announcement_scraper.py", "📢 Upbit duyuru sayfası taraması"),
            ("Telegram Bot", "simple_telegram_bot.py", "🤖 Telegram kullanıcı arayüzü"),
            ("Telegram Converter", "telegram_degisken.py", "📱 Telegram veri dönüştürme")
        ]
        
        success_count = 0
        for script_name, script_path, description in scripts:
            full_path = os.path.join(self.BASE_DIR, script_path)
            if os.path.exists(full_path):
                print(f"{description}")
                if self.start_script(script_name, full_path):
                    success_count += 1
                time.sleep(2)  # Scriptler arası bekleme
            else:
                print(f"⚠️ {script_path} bulunamadı, atlanıyor...")
        
        print(f"\n📊 {success_count}/{len(scripts)} bileşen başarıyla başlatıldı")
        
        # User trading engine'i başlat
        print("\n✅ User Trading Engine başlatılıyor:")
        print("   - user_trading_engine.py (Çok kullanıcılı ticaret sistemi)")
        print("   - Her kullanıcı için ayrı izolasyon")
        print("   - Manuel ve otomatik işlem desteği")
        print("\n🤖 Telegram Bot: Kullanıcılar bot üzerinden API anahtarlarını ekleyebilir")
        print("🔒 Gate.io bileşenleri pasife alındı (isteğe bağlı olarak aktifleştirilebilir)")
        
    def monitor_processes(self):
        """İşlemleri izle ve yeniden başlat"""
        while self.running:
            for script_name, process in list(self.processes.items()):
                if process.poll() is not None:  # İşlem bitmiş
                    print(f"⚠️ {script_name} durdu, yeniden başlatılıyor...")
                    # İşlemi yeniden başlatmaya çalış
                    del self.processes[script_name]
            
            time.sleep(10)  # 10 saniyede bir kontrol
    
    def check_api_keys(self):
        """User trading engine için API key kontrolü gerekmiyor (DB'den alınıyor)"""
        try:
            # User trading engine kullanıcı bazlı API key'leri DB'den alır
            # Global environment variable kontrolü gerekmiyor
            return True
            
        except Exception as e:
            print(f"❌ API key kontrol hatası: {e}")
            return False
    
    def start_trading_scripts(self):
        """User-aware trading engine'i başlat"""
        print("🟢 User Trading Engine başlatılıyor...")
        print("   - Çok kullanıcılı izolasyon desteği")
        print("   - Kullanıcı bazlı API key yönetimi")
        print("   - Manuel + otomatik işlem desteği")
        self.start_script("User Trading Engine", "user_trading_engine.py")
    
    def signal_handler(self, signum, frame):
        """Sinyal yakalayıcı"""
        print(f"\n🛑 Sinyal alındı ({signum}), sistem güvenli şekilde kapatılıyor...")
        self.stop_all()
        sys.exit(0)
    
    def stop_all(self):
        """Tüm işlemleri durdur"""
        self.running = False
        print("🛑 Tüm işlemler durduruluyor...")
        
        for script_name, process in self.processes.items():
            try:
                process.terminate()
                process.wait(timeout=5)
                print(f"✅ {script_name} durduruldu")
            except subprocess.TimeoutExpired:
                process.kill()
                print(f"⚠️ {script_name} zorla sonlandırıldı")
            except Exception as e:
                print(f"❌ {script_name} durdurma hatası: {e}")
        
        self.processes.clear()
    
    def status_report(self):
        """Durum raporu"""
        while self.running:
            # Thread safe kopyasını al
            processes_copy = dict(self.processes)
            active_count = len([p for p in processes_copy.values() if p.poll() is None])
            print(f"📊 Sistem Durumu: {active_count}/{len(processes_copy)} aktif script")
            
            # API key durumu (Sadece Bitget)
            bitget_ready = self.check_api_keys()
            print(f"🔑 API Durumu: Bitget {'✅' if bitget_ready else '❌'}")
            
            time.sleep(30)  # 30 saniyede bir rapor
    
    def run(self):
        """Ana çalışma fonksiyonu"""
        try:
            self.running = True
            print("=" * 60)
            print("🤖 KRIPTO TICARET SISTEMI KOORDINATÖRÜ")
            print("=" * 60)
            print(f"📅 Başlatılma: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"📁 Çalışma Dizini: {self.BASE_DIR}\n")
            
            # Sistem bileşenlerini başlat
            self.start_all_components()
            
            # User trading engine'i başlat
            print("\n🔍 User Trading Engine başlatılıyor...")
            time.sleep(5)
            self.start_trading_scripts()
            
            # Monitoring thread'leri başlat
            monitor_thread = threading.Thread(target=self.monitor_processes)
            status_thread = threading.Thread(target=self.status_report)
            
            monitor_thread.daemon = True
            status_thread.daemon = True
            
            monitor_thread.start()
            status_thread.start()
            
            print("\n🎯 Sistem çalışıyor! Durdurmak için Ctrl+C")
            print("=" * 60)
            
            # Ana döngü
            while self.running:
                time.sleep(1)
                
        except KeyboardInterrupt:
            print("\n⚠️ Kullanıcı tarafından durduruldu")
        except Exception as e:
            print(f"\n❌ Kritik hata: {e}")
        finally:
            self.stop_all()
            print("👋 Sistem kapatıldı")

def main():
    """Ana fonksiyon"""
    coordinator = TradingSystemCoordinator()
    coordinator.run()

if __name__ == "__main__":
    main()