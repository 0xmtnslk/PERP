#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
User-aware Trading Engine
Handles per-user trading operations with proper isolation
"""

import time
import json
import os
import subprocess
import threading
import sqlite3
from typing import Dict, Any
import logging
import hashlib
import base64
from cryptography.fernet import Fernet

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UserTradingEngine:
    def __init__(self):
        self.BASE_DIR = os.getcwd()
        self.users_dir = os.path.join(self.BASE_DIR, "PERP", "users")
        self.db_path = os.path.join(self.BASE_DIR, "trading_bot.db")
        self.running = False
        self.user_threads = {}
        
        # Ensure users directory exists
        os.makedirs(self.users_dir, exist_ok=True)
        
        # Setup encryption for API keys (same as advanced_telegram_bot.py)
        password = os.environ.get('ENCRYPTION_KEY', 'default_encryption_key_change_in_production')
        salt = b'stable_salt_value_'  # Same salt as in advanced_telegram_bot.py (16 bytes)
        kdf_key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
        self.encryption_key = base64.urlsafe_b64encode(kdf_key)
        self.cipher = Fernet(self.encryption_key)
        
    def get_user_api_keys(self, user_id: int) -> Dict[str, Any]:
        """Get user's API keys from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT bitget_api_key, bitget_secret_key, bitget_passphrase, is_configured 
                FROM user_api_keys WHERE user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                # Decrypt the API keys
                try:
                    api_key = self.cipher.decrypt(result[0].encode()).decode() if result[0] else ""
                    secret_key = self.cipher.decrypt(result[1].encode()).decode() if result[1] else ""
                    passphrase = self.cipher.decrypt(result[2].encode()).decode() if result[2] else ""
                    
                    return {
                        'api_key': api_key,
                        'secret_key': secret_key, 
                        'passphrase': passphrase,
                        'is_configured': bool(result[3])
                    }
                except Exception as e:
                    logger.error(f"Error decrypting API keys for user {user_id}: {e}")
                    return None
            return None
            
        except Exception as e:
            logger.error(f"Error getting API keys for user {user_id}: {e}")
            return None
    
    def get_user_settings(self, user_id: int) -> Dict[str, Any]:
        """Get user's trading settings from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT trading_amount_usdt, take_profit_percentage, auto_trading, notifications, emergency_stop 
                FROM user_settings WHERE user_id = ?
            """, (user_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return {
                    'trading_amount': result[0],
                    'take_profit': result[1],
                    'auto_trading': bool(result[2]),
                    'notifications': bool(result[3]),
                    'emergency_stop': bool(result[4])
                }
            return {
                'trading_amount': 50,
                'take_profit': 500,
                'auto_trading': False,
                'notifications': True,
                'emergency_stop': False
            }
            
        except Exception as e:
            logger.error(f"Error getting settings for user {user_id}: {e}")
            return {
                'trading_amount': 50,
                'take_profit': 500,
                'auto_trading': False,
                'notifications': True,
                'emergency_stop': False
            }
    
    def get_active_users(self) -> list:
        """Get list of users with auto trading enabled"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT DISTINCT u.user_id 
                FROM users u
                JOIN user_settings s ON u.user_id = s.user_id  
                JOIN user_api_keys a ON u.user_id = a.user_id
                WHERE s.auto_trading = 1 AND s.emergency_stop = 0 AND a.is_configured = 1
            """)
            
            users = [row[0] for row in cursor.fetchall()]
            conn.close()
            return users
            
        except Exception as e:
            logger.error(f"Error getting active users: {e}")
            return []
    
    def monitor_user_files(self, user_id: int):
        """Monitor user-specific files for trading signals"""
        user_dir = os.path.join(self.users_dir, str(user_id))
        manual_long_file = os.path.join(user_dir, "manual_long_output.txt")
        emergency_stop_file = os.path.join(user_dir, "emergency_stop.txt")
        
        # Create user directory if not exists
        os.makedirs(user_dir, exist_ok=True)
        
        logger.info(f"Starting monitor for user {user_id}")
        
        while self.running:
            try:
                # Check for manual long signal
                if os.path.exists(manual_long_file):
                    with open(manual_long_file, 'r') as f:
                        symbol = f.read().strip()
                    
                    if symbol:
                        logger.info(f"Manual long signal detected for user {user_id}: {symbol}")
                        self.execute_user_trade(user_id, symbol, "MANUAL_LONG")
                        
                        # Remove the signal file after processing
                        os.remove(manual_long_file)
                
                # Check for emergency stop signal
                if os.path.exists(emergency_stop_file):
                    logger.info(f"Emergency stop signal detected for user {user_id}")
                    self.execute_user_emergency_stop(user_id)
                    
                    # Remove the signal file after processing
                    os.remove(emergency_stop_file)
                    
                # Check for global new coin signals (only for auto trading users)
                settings = self.get_user_settings(user_id)
                if settings['auto_trading'] and not settings['emergency_stop']:
                    self.check_new_coin_signal(user_id)
                    
                time.sleep(2)  # Check every 2 seconds
                
            except Exception as e:
                logger.error(f"Error monitoring user {user_id}: {e}")
                time.sleep(5)
    
    def check_new_coin_signal(self, user_id: int):
        """Check for new coin signals from Upbit scraper"""
        new_coin_file = os.path.join(self.BASE_DIR, "PERP", "new_coin_output.txt")
        
        if not os.path.exists(new_coin_file):
            return
            
        try:
            with open(new_coin_file, 'r') as f:
                symbol = f.read().strip()
                
            # Check if this is a new symbol (not initial)
            with open(os.path.join(self.BASE_DIR, "PERP", "secret.json"), 'r') as f:
                secrets = json.load(f)
                initial_symbol = secrets["bitget_example"]["initial_symbol"]
            
            if symbol and symbol != initial_symbol:
                # Check if we already processed this symbol for this user
                user_dir = os.path.join(self.users_dir, str(user_id))
                processed_file = os.path.join(user_dir, "last_processed_symbol.txt")
                
                last_processed = ""
                if os.path.exists(processed_file):
                    with open(processed_file, 'r') as f:
                        last_processed = f.read().strip()
                
                if symbol != last_processed:
                    logger.info(f"New coin detected for user {user_id}: {symbol}")
                    self.execute_user_trade(user_id, symbol, "AUTO_NEW_COIN")
                    
                    # Mark as processed for this user
                    with open(processed_file, 'w') as f:
                        f.write(symbol)
                        
        except Exception as e:
            logger.error(f"Error checking new coin signal for user {user_id}: {e}")
    
    def execute_user_trade(self, user_id: int, symbol: str, trade_type: str):
        """Execute trade for specific user with their credentials"""
        try:
            # Get user's API keys and settings
            api_keys = self.get_user_api_keys(user_id)
            settings = self.get_user_settings(user_id)
            
            if not api_keys or not api_keys['is_configured']:
                logger.error(f"No API keys configured for user {user_id}")
                return
                
            # Create user-specific environment
            user_env = os.environ.copy()
            user_env['BITGET_API_KEY'] = api_keys['api_key']
            user_env['BITGET_SECRET_KEY'] = api_keys['secret_key']
            user_env['BITGET_PASSPHRASE'] = api_keys['passphrase']
            user_env['BITGET_OPEN_USDT'] = str(settings['trading_amount'])
            user_env['BITGET_CLOSE_YUZDE'] = str(settings['take_profit'] / 100 + 1)
            user_env['USER_ID'] = str(user_id)
            user_env['TRADE_TYPE'] = trade_type
            
            # Create user-specific symbol file
            user_dir = os.path.join(self.users_dir, str(user_id))
            user_symbol_file = os.path.join(user_dir, "current_symbol.txt")
            
            with open(user_symbol_file, 'w') as f:
                f.write(symbol)
            
            logger.info(f"Executing {trade_type} trade for user {user_id}: {symbol}")
            
            # Execute leverage script first
            leverage_script = os.path.join(self.BASE_DIR, "PERP", "leverage.py")
            result = subprocess.run(
                ["python3", leverage_script],
                capture_output=True,
                text=True,
                timeout=60,
                env=user_env,
                cwd=self.BASE_DIR
            )
            
            if result.returncode != 0:
                logger.error(f"Leverage script failed for user {user_id}: {result.stderr}")
                return
            
            # Execute long script
            long_script = os.path.join(self.BASE_DIR, "PERP", "long.py")
            result = subprocess.run(
                ["python3", long_script],
                capture_output=True,
                text=True,
                timeout=60,
                env=user_env,
                cwd=self.BASE_DIR
            )
            
            if result.returncode == 0:
                logger.info(f"Trade executed successfully for user {user_id}: {symbol}")
            else:
                logger.error(f"Long script failed for user {user_id}: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Error executing trade for user {user_id}: {e}")
    
    def execute_user_emergency_stop(self, user_id: int):
        """Execute emergency stop for specific user"""
        try:
            # Get user's API keys
            api_keys = self.get_user_api_keys(user_id)
            
            if not api_keys or not api_keys['is_configured']:
                logger.error(f"No API keys configured for user {user_id}")
                return
                
            # Create user-specific environment
            user_env = os.environ.copy()
            user_env['BITGET_API_KEY'] = api_keys['api_key']
            user_env['BITGET_SECRET_KEY'] = api_keys['secret_key']
            user_env['BITGET_PASSPHRASE'] = api_keys['passphrase']
            user_env['USER_ID'] = str(user_id)
            
            logger.info(f"Executing emergency stop for user {user_id}")
            
            # Execute close positions script
            close_script = os.path.join(self.BASE_DIR, "PERP", "kapat.py")
            result = subprocess.run(
                ["python3", close_script],
                capture_output=True,
                text=True,
                timeout=60,
                env=user_env,
                cwd=self.BASE_DIR
            )
            
            if result.returncode == 0:
                logger.info(f"Emergency stop executed successfully for user {user_id}")
            else:
                logger.error(f"Emergency stop failed for user {user_id}: {result.stderr}")
                
        except Exception as e:
            logger.error(f"Error executing emergency stop for user {user_id}: {e}")
    
    def start(self):
        """Start the user trading engine"""
        self.running = True
        logger.info("Starting User Trading Engine...")
        
        while self.running:
            try:
                # Get current active users
                active_users = self.get_active_users()
                
                # Start monitoring threads for new users
                for user_id in active_users:
                    if user_id not in self.user_threads or not self.user_threads[user_id].is_alive():
                        logger.info(f"Starting monitor thread for user {user_id}")
                        thread = threading.Thread(
                            target=self.monitor_user_files,
                            args=(user_id,),
                            daemon=True
                        )
                        thread.start()
                        self.user_threads[user_id] = thread
                
                # Remove threads for inactive users
                inactive_users = set(self.user_threads.keys()) - set(active_users)
                for user_id in inactive_users:
                    logger.info(f"User {user_id} became inactive")
                    if user_id in self.user_threads:
                        del self.user_threads[user_id]
                
                time.sleep(30)  # Check for new/removed users every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in main trading engine loop: {e}")
                time.sleep(10)
    
    def stop(self):
        """Stop the user trading engine"""
        self.running = False
        logger.info("Stopping User Trading Engine...")

if __name__ == "__main__":
    engine = UserTradingEngine()
    try:
        engine.start()
    except KeyboardInterrupt:
        engine.stop()
        print("\nUser Trading Engine stopped.")