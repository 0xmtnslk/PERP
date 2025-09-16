#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Take Profit Monitoring System
Kullanıcıların açık pozisyonlarını izler ve TP hedefine ulaştığında otomatik satar
"""

import os
import sys
import time
import sqlite3
import json
import subprocess
import threading
from datetime import datetime
import logging

# Base directory setup
BASE_DIR = os.getcwd()
sys.path.append(BASE_DIR)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TakeProfitMonitor:
    def __init__(self):
        self.BASE_DIR = BASE_DIR
        self.db_path = os.path.join(self.BASE_DIR, "trading_bot.db")
        self.running = False
        self.monitor_threads = {}
        
    def get_active_trades(self):
        """Açık pozisyonları olan kullanıcıları getir"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT u.user_id 
                FROM users u
                JOIN user_settings s ON u.user_id = s.user_id  
                JOIN user_api_keys a ON u.user_id = a.user_id
                WHERE s.emergency_stop = 0 AND a.is_configured = 1
            """)
            
            users = [row[0] for row in cursor.fetchall()]
            conn.close()
            return users
            
        except Exception as e:
            logger.error(f"Error getting active trades: {e}")
            return []
    
    def get_user_api_keys(self, user_id: int):
        """Kullanıcının API anahtarlarını al - working_telegram_bot plain text format"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT api_key, secret_key, passphrase, is_configured 
                FROM user_api_keys WHERE user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                # API keys are stored in plain text by working_telegram_bot.py
                return {
                    'api_key': result[0] if result[0] else "",
                    'secret_key': result[1] if result[1] else "", 
                    'passphrase': result[2] if result[2] else "",
                    'is_configured': bool(result[3])
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting API keys for user {user_id}: {e}")
            return None
    
    def get_user_settings(self, user_id: int):
        """Kullanıcının ayarlarını al"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT amount_usdt, take_profit_percent, leverage, auto_trading, emergency_stop 
                FROM user_settings WHERE user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'trading_amount': result[0],
                    'take_profit': result[1],
                    'leverage': result[2],
                    'auto_trading': bool(result[3]),
                    'emergency_stop': bool(result[4])
                }
            return None
            
        except Exception as e:
            logger.error(f"Error getting settings for user {user_id}: {e}")
            return None
    
    def check_user_positions(self, user_id: int):
        """Kullanıcının pozisyonlarını kontrol et ve TP hedefe ulaştıysa kapat"""
        try:
            api_keys = self.get_user_api_keys(user_id)
            settings = self.get_user_settings(user_id)
            
            if not api_keys or not settings or settings['emergency_stop']:
                return
            
            # Python script to check positions and TP
            check_script = f"""
import sys
import os
sys.path.append('{self.BASE_DIR}/PERP')
from long import get_all_positions, close_all_positions

api_key = "{api_keys['api_key']}"
secret_key = "{api_keys['secret_key']}"
passphrase = "{api_keys['passphrase']}"
tp_target = {settings['take_profit'] / 100 + 1}

try:
    positions = get_all_positions(api_key, secret_key, passphrase)
    if positions:
        total_pnl = 0.0
        should_close = False
        
        for position in positions:
            size = float(position.get('size', 0))
            if size > 0:
                unrealized_pnl = float(position.get('unrealizedPL', 0))
                total_pnl += unrealized_pnl
                
                # Check if TP target reached
                entry_price = float(position.get('averageOpenPrice', 0))
                mark_price = float(position.get('markPrice', 0))
                
                if entry_price > 0:
                    pnl_percentage = ((mark_price - entry_price) / entry_price) + 1
                    print(f"Position PnL: {{pnl_percentage:.4f}}x, Target: {{tp_target}}x")
                    
                    if pnl_percentage >= tp_target:
                        should_close = True
                        break
        
        if should_close:
            print(f"TP Target reached! Closing all positions for user {user_id}")
            result = close_all_positions(api_key, secret_key, passphrase)
            print(f"CLOSE_RESULT:{{total_pnl:.2f}}")
        else:
            print(f"Monitoring user {user_id}: {{total_pnl:.2f}} USDT (no TP yet)")
            
except Exception as e:
    print(f"Error monitoring user {user_id}: {{e}}")
"""
            
            result = subprocess.run(
                ["python3", "-c", check_script],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Check if positions were closed
            if "CLOSE_RESULT:" in result.stdout:
                pnl = result.stdout.split("CLOSE_RESULT:")[1].strip()
                logger.info(f"✅ TP reached for user {user_id}: {pnl} USDT")
                self.notify_tp_reached(user_id, pnl)
            
        except Exception as e:
            logger.error(f"Error checking positions for user {user_id}: {e}")
    
    def notify_tp_reached(self, user_id: int, pnl: str):
        """TP'ye ulaştığında kullanıcıya bildirim gönder"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO notifications (user_id, type, title, message)
                VALUES (?, ?, ?, ?)
            ''', (user_id, 'TP_REACHED', 'Take Profit Hedefi!', f'Pozisyonlar kapatıldı. Kar/Zarar: {pnl} USDT'))
            
            conn.commit()
            conn.close()
            
            logger.info(f"📢 TP notification sent to user {user_id}")
            
        except Exception as e:
            logger.error(f"Error sending TP notification: {e}")
    
    def monitor_user_loop(self, user_id: int):
        """Tek kullanıcı için sürekli monitoring döngüsü"""
        logger.info(f"Starting TP monitor for user {user_id}")
        
        while self.running:
            try:
                self.check_user_positions(user_id)
                time.sleep(30)  # 30 saniyede bir kontrol
            except Exception as e:
                logger.error(f"Error in monitor loop for user {user_id}: {e}")
                time.sleep(60)  # Hata durumunda 1 dakika bekle
    
    def start_monitoring(self):
        """Tüm kullanıcılar için monitoring başlat"""
        self.running = True
        logger.info("🎯 Take Profit Monitor başlatılıyor...")
        
        while self.running:
            try:
                # Aktif kullanıcıları al
                active_users = self.get_active_trades()
                
                # Yeni kullanıcılar için thread başlat
                for user_id in active_users:
                    if user_id not in self.monitor_threads or not self.monitor_threads[user_id].is_alive():
                        thread = threading.Thread(
                            target=self.monitor_user_loop,
                            args=(user_id,),
                            daemon=True
                        )
                        thread.start()
                        self.monitor_threads[user_id] = thread
                        logger.info(f"📊 TP monitor started for user {user_id}")
                
                # Dead thread'leri temizle
                dead_threads = [uid for uid, thread in self.monitor_threads.items() if not thread.is_alive()]
                for uid in dead_threads:
                    del self.monitor_threads[uid]
                
                time.sleep(60)  # 1 dakikada bir kullanıcı listesini yenile
                
            except Exception as e:
                logger.error(f"Error in main monitoring loop: {e}")
                time.sleep(60)
    
    def stop_monitoring(self):
        """Monitoring'i durdur"""
        self.running = False
        logger.info("🛑 Take Profit Monitor durduruluyor...")

def main():
    """Ana fonksiyon"""
    tp_monitor = TakeProfitMonitor()
    
    try:
        tp_monitor.start_monitoring()
    except KeyboardInterrupt:
        print("\n🛑 Take Profit Monitor manuel olarak durduruldu")
    finally:
        tp_monitor.stop_monitoring()

if __name__ == "__main__":
    main()