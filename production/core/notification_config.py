#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Centralized Notification Configuration
Tüm bildirim ve IPC dosya yollarını merkezi olarak yönetir
"""
import os
from pathlib import Path
from typing import Dict

class NotificationConfig:
    """Bildirim dosyalarının yollarını merkezi olarak yöneten sınıf"""
    
    def __init__(self, base_dir: str = None):
        self.BASE_DIR = base_dir or os.getcwd()
        self.PERP_DIR = os.path.join(self.BASE_DIR, "PERP")
        self.GATEIO_DIR = os.path.join(self.BASE_DIR, "gateio")
        
        # Dizinleri oluştur
        self._ensure_directories()
    
    def _ensure_directories(self):
        """Gerekli dizinleri oluştur"""
        for directory in [self.PERP_DIR, self.GATEIO_DIR]:
            os.makedirs(directory, exist_ok=True)
    
    @property
    def telegram_notifications_file(self) -> str:
        """Telegram bot bildirimleri için ana dosya"""
        return os.path.join(self.BASE_DIR, 'telegram_notifications.json')
    
    @property
    def new_coin_output_txt(self) -> str:
        """Yeni coin sembolleri için metin dosyası (PERP formatında)"""
        return os.path.join(self.PERP_DIR, 'new_coin_output.txt')
    
    @property
    def new_coin_output_json(self) -> str:
        """Yeni coin sembolleri için JSON dosyası (PERP formatında)"""
        return os.path.join(self.PERP_DIR, 'new_coin_output.json')
    
    @property
    def gateio_new_coin_txt(self) -> str:
        """Gate.io için coin sembolleri metin dosyası"""
        return os.path.join(self.GATEIO_DIR, 'new_coin_output.txt')
    
    @property
    def gateio_new_coin_json(self) -> str:
        """Gate.io için coin sembolleri JSON dosyası"""
        return os.path.join(self.GATEIO_DIR, 'new_coin_output.json')
    
    @property
    def announcement_coins_file(self) -> str:
        """Upbit duyuru coin kayıtları"""
        return os.path.join(self.PERP_DIR, 'announcement_coins.json')
    
    @property
    def last_announcement_check_file(self) -> str:
        """Son duyuru kontrol zamanı"""
        return os.path.join(self.PERP_DIR, 'last_announcement_check.json')
    
    @property
    def main_secret_file(self) -> str:
        """Ana secret.json dosyası"""
        return os.path.join(self.BASE_DIR, 'secret.json')
    
    @property
    def perp_secret_file(self) -> str:
        """PERP/Bitget secret.json dosyası"""
        return os.path.join(self.PERP_DIR, 'secret.json')
    
    @property
    def gateio_secret_file(self) -> str:
        """Gate.io secret.json dosyası"""
        return os.path.join(self.GATEIO_DIR, 'secret.json')
    
    def get_all_notification_files(self) -> Dict[str, str]:
        """Tüm bildirim dosyalarının yollarını döndür"""
        return {
            'telegram_notifications': self.telegram_notifications_file,
            'new_coin_output_txt': self.new_coin_output_txt,
            'new_coin_output_json': self.new_coin_output_json,
            'gateio_new_coin_txt': self.gateio_new_coin_txt,
            'gateio_new_coin_json': self.gateio_new_coin_json,
            'announcement_coins': self.announcement_coins_file,
            'last_announcement_check': self.last_announcement_check_file
        }
    
    def verify_file_permissions(self) -> Dict[str, bool]:
        """Dosya izinlerini kontrol et"""
        results = {}
        for name, path in self.get_all_notification_files().items():
            try:
                # Dosya yazılabilir mi kontrol et
                directory = os.path.dirname(path)
                results[name] = os.access(directory, os.W_OK)
            except Exception:
                results[name] = False
        return results
    
    def clean_old_notifications(self, max_age_hours: int = 24):
        """Eski bildirim dosyalarını temizle"""
        import time
        from datetime import datetime, timedelta
        
        cutoff_time = time.time() - (max_age_hours * 3600)
        cleaned_files = []
        
        for name, path in self.get_all_notification_files().items():
            try:
                if os.path.exists(path):
                    file_mtime = os.path.getmtime(path)
                    if file_mtime < cutoff_time:
                        # Telegram notifications hariç eski dosyaları sil
                        if 'telegram_notifications' not in name:
                            os.remove(path)
                            cleaned_files.append(path)
            except Exception as e:
                print(f"⚠️ Dosya temizleme hatası {path}: {e}")
        
        return cleaned_files

# Global configuration instance
notification_config = NotificationConfig()

# Backward compatibility için kısayollar
def get_telegram_notifications_file() -> str:
    """Telegram bildirim dosyası yolu"""
    return notification_config.telegram_notifications_file

def get_new_coin_output_file() -> str:
    """PERP yeni coin dosyası yolu"""
    return notification_config.new_coin_output_txt

def get_new_coin_json_file() -> str:
    """PERP yeni coin JSON dosyası yolu"""
    return notification_config.new_coin_output_json

def get_announcement_coins_file() -> str:
    """Duyuru coin kayıtları dosyası yolu"""
    return notification_config.announcement_coins_file

if __name__ == "__main__":
    # Test configuration
    config = NotificationConfig()
    print("🔧 Notification Configuration Test")
    print("=" * 50)
    
    for name, path in config.get_all_notification_files().items():
        exists = "✅" if os.path.exists(path) else "❌"
        print(f"{exists} {name}: {path}")
    
    print("\n📁 Directory Permissions:")
    permissions = config.verify_file_permissions()
    for name, writable in permissions.items():
        status = "✅ Writable" if writable else "❌ Not writable"
        print(f"  {name}: {status}")