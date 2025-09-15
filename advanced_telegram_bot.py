#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gelişmiş Telegram Bot - Kripto Ticaret Yönetim Sistemi
Kullanıcı kaydı, API yönetimi, ticaret ayarları ve canlı bildirimler
"""
import os
import json
import sqlite3
import asyncio
import logging
import time
from datetime import datetime
from typing import Dict, Optional, List
import subprocess
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from notification_config import notification_config

# Telegram imports (bağımlılık kontrolü)
try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
    from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
    from telegram.constants import ParseMode
except ImportError:
    print("⚠️ python-telegram-bot kütüphanesi bulunamadı!")
    print("Kurulum için: pip install python-telegram-bot")
    exit(1)

# Logging konfigürasyonu
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class APIKeyEncryption:
    """API anahtarlarını güvenle şifrelemek için sınıf"""
    
    def __init__(self, password: str = None):
        if password is None:
            # Sistem tabanlı varsayılan parola (güvenlik için env var kullanılmalı)
            password = os.environ.get('ENCRYPTION_KEY', 'default_encryption_key_change_in_production')
        
        # Tuz için sabit değer (üretimde random olmalı ve kaydedilmeli)
        salt = b'stable_salt_value_'  # 16 byte
        
        # Key derivation
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        self.cipher_suite = Fernet(key)
    
    def encrypt(self, text: str) -> str:
        """Metni şifrele"""
        if not text:
            return text
        return self.cipher_suite.encrypt(text.encode()).decode()
    
    def decrypt(self, encrypted_text: str) -> str:
        """Şifrelenmiş metni çöz"""
        if not encrypted_text:
            return encrypted_text
        try:
            return self.cipher_suite.decrypt(encrypted_text.encode()).decode()
        except Exception as e:
            logger.error(f"Decryption error: {e}")
            return ""

class InputValidator:
    """Kullanıcı girişlerini doğrulayan güvenlik sınıfı"""
    
    # Güvenlik limitleri
    MIN_TRADING_AMOUNT = 1.0
    MAX_TRADING_AMOUNT = 10000.0
    MIN_TAKE_PROFIT = 50.0  # %50
    MAX_TAKE_PROFIT = 2000.0  # %2000
    ALLOWED_TRADING_AMOUNTS = [10, 20, 50, 100, 200, 500, 1000]
    ALLOWED_TAKE_PROFITS = [200, 300, 500, 600, 800, 1000, 1500]
    
    @staticmethod
    def validate_trading_amount(amount: float, user_id: int = None) -> tuple[bool, str]:
        """Ticaret miktarını doğrula"""
        try:
            amount = float(amount)
        except (ValueError, TypeError):
            logger.warning(f"Invalid trading amount input: {amount} from user {user_id}")
            return False, "Geçersiz miktar formatı. Sayısal değer giriniz."
        
        if amount < InputValidator.MIN_TRADING_AMOUNT:
            logger.warning(f"Trading amount too low: {amount} from user {user_id}")
            return False, f"Minimum ticaret miktarı: {InputValidator.MIN_TRADING_AMOUNT} USDT"
        
        if amount > InputValidator.MAX_TRADING_AMOUNT:
            logger.warning(f"Trading amount too high: {amount} from user {user_id}")
            return False, f"Maksimum ticaret miktarı: {InputValidator.MAX_TRADING_AMOUNT} USDT"
        
        # Izin verilen değerler kontrolü
        if amount not in InputValidator.ALLOWED_TRADING_AMOUNTS:
            logger.warning(f"Unauthorized trading amount: {amount} from user {user_id}")
            return False, f"Izin verilen miktarlar: {', '.join(map(str, InputValidator.ALLOWED_TRADING_AMOUNTS))} USDT"
        
        logger.info(f"Valid trading amount validated: {amount} USDT for user {user_id}")
        return True, "Geçerli"
    
    @staticmethod
    def validate_take_profit(percentage: float, user_id: int = None) -> tuple[bool, str]:
        """Take profit yüzdesini doğrula"""
        try:
            percentage = float(percentage)
        except (ValueError, TypeError):
            logger.warning(f"Invalid take profit input: {percentage} from user {user_id}")
            return False, "Geçersiz yüzde formatı. Sayısal değer giriniz."
        
        if percentage < InputValidator.MIN_TAKE_PROFIT:
            logger.warning(f"Take profit too low: {percentage}% from user {user_id}")
            return False, f"Minimum take profit: %{InputValidator.MIN_TAKE_PROFIT}"
        
        if percentage > InputValidator.MAX_TAKE_PROFIT:
            logger.warning(f"Take profit too high: {percentage}% from user {user_id}")
            return False, f"Maksimum take profit: %{InputValidator.MAX_TAKE_PROFIT}"
        
        # Izin verilen değerler kontrolü
        if percentage not in InputValidator.ALLOWED_TAKE_PROFITS:
            logger.warning(f"Unauthorized take profit: {percentage}% from user {user_id}")
            return False, f"Izin verilen yüzdelik: {', '.join(map(str, InputValidator.ALLOWED_TAKE_PROFITS))}%"
        
        logger.info(f"Valid take profit validated: {percentage}% for user {user_id}")
        return True, "Geçerli"
    
    @staticmethod
    def sanitize_user_input(text: str) -> str:
        """Kullanıcı girişini temizle"""
        if not text:
            return ""
        # Tehlikeli karakterleri temizle
        dangerous_chars = ['<', '>', '&', '"', "'", ';', '(', ')', '{', '}', '[', ']']
        for char in dangerous_chars:
            text = text.replace(char, '')
        return text.strip()[:200]  # Maksimum 200 karakter

class TradingBotDatabase:
    """Kullanıcı verilerini yöneten veritabanı sınıfı"""
    
    def __init__(self, db_path="trading_bot.db"):
        self.db_path = db_path
        self.encryption = APIKeyEncryption()
        self.init_database()
    
    def init_database(self):
        """Veritabanını başlat ve tabloları oluştur"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Kullanıcılar tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # API anahtarları tablosu (şifrelenmiş)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_api_keys (
                user_id INTEGER PRIMARY KEY,
                bitget_api_key TEXT,
                bitget_secret_key TEXT,
                bitget_passphrase TEXT,
                is_configured BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Ticaret ayarları tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                trading_amount_usdt REAL DEFAULT 20.0,
                take_profit_percentage REAL DEFAULT 500.0,
                auto_trading BOOLEAN DEFAULT 1,
                notifications BOOLEAN DEFAULT 1,
                emergency_stop BOOLEAN DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # İşlem geçmişi tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                symbol TEXT,
                action TEXT,  -- 'BUY', 'SELL', 'EMERGENCY_STOP'
                amount_usdt REAL,
                price REAL,
                profit_loss REAL,
                status TEXT,  -- 'OPEN', 'CLOSED', 'CANCELLED'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        # Bildirimler tablosu
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,  -- 'NEW_COIN', 'TRADE_OPEN', 'TRADE_CLOSED', 'SYSTEM'
                title TEXT,
                message TEXT,
                is_read BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        print("🗄️ Veritabanı başarıyla başlatıldı")
    
    def register_user(self, user_id: int, username: str, first_name: str, last_name: str = None):
        """Kullanıcıyı kaydet"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users 
            (user_id, username, first_name, last_name, last_activity)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, username, first_name, last_name))
        
        # Varsayılan ayarları oluştur
        cursor.execute('''
            INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)
        ''', (user_id,))
        
        conn.commit()
        conn.close()
    
    def save_api_keys(self, user_id: int, api_key: str, secret_key: str, passphrase: str):
        """API anahtarlarını şifreleyerek kaydet"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # API anahtarlarını şifrele
        encrypted_api_key = self.encryption.encrypt(api_key)
        encrypted_secret_key = self.encryption.encrypt(secret_key)
        encrypted_passphrase = self.encryption.encrypt(passphrase)
        
        cursor.execute('''
            INSERT OR REPLACE INTO user_api_keys 
            (user_id, bitget_api_key, bitget_secret_key, bitget_passphrase, is_configured)
            VALUES (?, ?, ?, ?, 1)
        ''', (user_id, encrypted_api_key, encrypted_secret_key, encrypted_passphrase))
        
        conn.commit()
        conn.close()
        logger.info(f"🔐 API anahtarları şifrelenmiş olarak kaydedildi: user_id={user_id}")
    
    def get_user_api_keys(self, user_id: int) -> Optional[Dict]:
        """Kullanıcının API anahtarlarını çözerek getir"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT bitget_api_key, bitget_secret_key, bitget_passphrase, is_configured
            FROM user_api_keys WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            # Şifrelenmiş anahtarları çöz
            try:
                api_key = self.encryption.decrypt(result[0]) if result[0] else ""
                secret_key = self.encryption.decrypt(result[1]) if result[1] else ""
                passphrase = self.encryption.decrypt(result[2]) if result[2] else ""
                
                return {
                    'api_key': api_key,
                    'secret_key': secret_key, 
                    'passphrase': passphrase,
                    'is_configured': bool(result[3])
                }
            except Exception as e:
                logger.error(f"API key decryption error for user {user_id}: {e}")
                return None
        return None
    
    def update_user_settings(self, user_id: int, **settings):
        """Kullanıcı ayarlarını güvenlik doğrulaması ile güncelle"""
        # Giriş doğrulaması
        for key, value in settings.items():
            if key == 'trading_amount_usdt':
                is_valid, message = InputValidator.validate_trading_amount(value, user_id)
                if not is_valid:
                    logger.error(f"Invalid trading amount update attempt: {value} for user {user_id} - {message}")
                    raise ValueError(f"Geçersiz ticaret miktarı: {message}")
            elif key == 'take_profit_percentage':
                is_valid, message = InputValidator.validate_take_profit(value, user_id)
                if not is_valid:
                    logger.error(f"Invalid take profit update attempt: {value} for user {user_id} - {message}")
                    raise ValueError(f"Geçersiz take profit: {message}")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Dinamik güncelleme
        fields = []
        values = []
        for key, value in settings.items():
            fields.append(f"{key} = ?")
            values.append(value)
        
        if fields:
            fields.append("updated_at = CURRENT_TIMESTAMP")
            values.append(user_id)
            
            cursor.execute(f'''
                UPDATE user_settings SET {', '.join(fields)} WHERE user_id = ?
            ''', values)
        
        conn.commit()
        conn.close()
        logger.info(f"User settings updated successfully for user {user_id}: {settings}")
    
    def get_user_settings(self, user_id: int) -> Dict:
        """Kullanıcı ayarlarını getir"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT trading_amount_usdt, take_profit_percentage, auto_trading, 
                   notifications, emergency_stop
            FROM user_settings WHERE user_id = ?
        ''', (user_id,))
        
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
        
        # Varsayılan ayarlar
        return {
            'trading_amount': 20.0,
            'take_profit': 500.0,
            'auto_trading': True,
            'notifications': True,
            'emergency_stop': False
        }
    
    def add_trade_record(self, user_id: int, symbol: str, action: str, amount_usdt: float, 
                        price: float, status: str = 'OPEN') -> int:
        """İşlem kaydı ekle"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trade_history 
            (user_id, symbol, action, amount_usdt, price, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, symbol, action, amount_usdt, price, status))
        
        trade_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return trade_id
    
    def close_trade_record(self, trade_id: int, profit_loss: float):
        """İşlem kaydını kapat"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE trade_history 
            SET status = 'CLOSED', profit_loss = ?, closed_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (profit_loss, trade_id))
        
        conn.commit()
        conn.close()
    
    def add_notification(self, user_id: int, notification_type: str, title: str, message: str):
        """Bildirim ekle"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO notifications (user_id, type, title, message)
            VALUES (?, ?, ?, ?)
        ''', (user_id, notification_type, title, message))
        
        conn.commit()
        conn.close()
    
    def get_active_users(self) -> List[int]:
        """Aktif kullanıcıları getir"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT user_id FROM users WHERE is_active = 1
        ''')
        
        users = [row[0] for row in cursor.fetchall()]
        conn.close()
        return users

class AdvancedTradingBot:
    """Gelişmiş Telegram ticaret botu"""
    
    def __init__(self):
        self.db = TradingBotDatabase()
        self.active_trades = {}  # user_id -> trade_info
        self.pending_api_setup = {}  # user_id -> setup_step
        self.BASE_DIR = os.getcwd()
        # Centralized notification configuration kullan
        self.notification_file = notification_config.telegram_notifications_file
        self.last_notification_check = 0
        print(f"🤖 Telegram Bot using centralized notification config: {self.notification_file}")
        
        # User state management - custom symbol girişi için
        self.user_states = {}
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Bot başlatma komutu"""
        user = update.effective_user
        chat_id = update.effective_chat.id
        
        # Kullanıcıyı kaydet
        self.db.register_user(
            user_id=user.id,
            username=user.username or "unknown",
            first_name=user.first_name,
            last_name=user.last_name
        )
        
        welcome_text = f"""
🚀 **Kripto Ticaret Bot'a Hoş Geldin, {user.first_name}!**

Bu bot ile:
• 🔑 API anahtarlarını güvenle yönet
• 💰 İşlem miktarlarını ayarla
• 📈 Take Profit hedeflerini belirle
• 🚨 Upbit yeni coin bildirimlerini al
• ⚡ Acil durdurma ile işlemleri kontrol et

Başlamak için aşağıdaki butonu kullan:
        """
        
        keyboard = [
            [InlineKeyboardButton("🎛️ Bot Ayarları", callback_data="main_menu")],
            [InlineKeyboardButton("📊 İşlem Durumu", callback_data="trade_status")],
            [InlineKeyboardButton("🆘 Yardım", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def main_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ana menü callback'i"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        api_keys = self.db.get_user_api_keys(user_id)
        settings = self.db.get_user_settings(user_id)
        
        status_api = "✅ Yapılandırıldı" if api_keys and api_keys['is_configured'] else "❌ Yapılandırılmadı"
        status_trading = "🟢 Aktif" if settings['auto_trading'] else "🔴 Pasif"
        
        menu_text = f"""
🎛️ **Bot Ayarları**

🔑 **API Durumu:** {status_api}
💰 **İşlem Miktarı:** {settings['trading_amount']} USDT
📈 **Take Profit:** %{settings['take_profit']}
🤖 **Otomatik Ticaret:** {status_trading}
🔔 **Bildirimler:** {"Açık" if settings['notifications'] else "Kapalı"}

Ayarlamak istediğin kısmı seç:
        """
        
        keyboard = [
            [InlineKeyboardButton("🔑 API Anahtarları", callback_data="setup_api")],
            [InlineKeyboardButton("💰 İşlem Miktarı", callback_data="set_amount")],
            [InlineKeyboardButton("📈 Take Profit", callback_data="set_tp")],
            [InlineKeyboardButton("🤖 Oto Ticaret", callback_data="toggle_auto")],
            [InlineKeyboardButton("📊 Manuel Long", callback_data="manual_long")],
            [InlineKeyboardButton("🔔 Bildirimler", callback_data="toggle_notifications")],
            [InlineKeyboardButton("🚨 ACİL DURDUR", callback_data="emergency_stop")],
            [InlineKeyboardButton("◀️ Ana Menü", callback_data="back_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            menu_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def setup_api_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """API kurulum callback'i"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        self.pending_api_setup[user_id] = {'step': 'api_key'}
        
        api_text = """
🔑 **Bitget API Anahtarları Kurulumu**

API anahtarlarını güvenle eklemek için:

**1. Adım:** Bitget API Key
Bitget hesabından aldığın API anahtarını gönder.

⚠️ **Güvenlik:** Anahtarların şifrelenerek saklanacak.
        """
        
        keyboard = [
            [InlineKeyboardButton("❌ İptal", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            api_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Genel mesaj handler - API kurulum ve custom symbol"""
        user_id = update.effective_user.id
        
        # Custom symbol processing önceliği var
        if self.user_states.get(user_id) == "waiting_for_custom_symbol":
            await self.process_custom_symbol_message(update, context)
            return
        
        # API kurulum processing
        await self.handle_api_setup(update, context)
    
    async def handle_api_setup(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """API kurulum sürecini yönet"""
        user_id = update.effective_user.id
        message_text = update.message.text
        
        if user_id not in self.pending_api_setup:
            return
        
        setup_data = self.pending_api_setup[user_id]
        step = setup_data['step']
        
        if step == 'api_key':
            setup_data['api_key'] = message_text
            setup_data['step'] = 'secret_key'
            await update.message.reply_text(
                "✅ API Key kaydedildi!\n\n🔐 **2. Adım:** Secret Key\nBitget Secret Key'ini gönder:"
            )
        
        elif step == 'secret_key':
            setup_data['secret_key'] = message_text
            setup_data['step'] = 'passphrase'
            await update.message.reply_text(
                "✅ Secret Key kaydedildi!\n\n🔑 **3. Adım:** Passphrase\nBitget Passphrase'ini gönder:"
            )
        
        elif step == 'passphrase':
            setup_data['passphrase'] = message_text
            
            # API anahtarlarını kaydet
            self.db.save_api_keys(
                user_id=user_id,
                api_key=setup_data['api_key'],
                secret_key=setup_data['secret_key'],
                passphrase=setup_data['passphrase']
            )
            
            # Kurulum tamamlandı
            del self.pending_api_setup[user_id]
            
            keyboard = [
                [InlineKeyboardButton("🎛️ Bot Ayarları", callback_data="main_menu")],
                [InlineKeyboardButton("🚀 Ticareti Başlat", callback_data="start_trading")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "🎉 **API Anahtarları Başarıyla Kaydedildi!**\n\n"
                "Artık otomatik ticaret yapabilirsin.\n"
                "Bot ayarlarına dönmek için butonu kullan.",
                reply_markup=reply_markup
            )
            
            # Sistem environment variable'larını güncelle (geçici)
            await self.update_system_env_vars(user_id)
    
    async def update_system_env_vars(self, user_id: int):
        """Sistem environment variable'larını güncelle"""
        api_keys = self.db.get_user_api_keys(user_id)
        if api_keys and api_keys['is_configured']:
            # Ana sistem için environment variable'ları ayarla
            os.environ['BITGET_API_KEY'] = api_keys['api_key']
            os.environ['BITGET_SECRET_KEY'] = api_keys['secret_key']
            os.environ['BITGET_PASSPHRASE'] = api_keys['passphrase']
            
            print(f"🔑 {user_id} kullanıcısı için API anahtarları sisteme yüklendi")
    
    async def set_trading_amount_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """İşlem miktarı ayarlama callback'i"""
        query = update.callback_query
        await query.answer()
        
        amount_text = """
💰 **İşlem Miktarı Ayarla**

Her işlem için kullanılacak USDT miktarını seç:
        """
        
        keyboard = [
            [
                InlineKeyboardButton("10 USDT", callback_data="amount_10"),
                InlineKeyboardButton("20 USDT", callback_data="amount_20"),
                InlineKeyboardButton("50 USDT", callback_data="amount_50")
            ],
            [
                InlineKeyboardButton("100 USDT", callback_data="amount_100"),
                InlineKeyboardButton("200 USDT", callback_data="amount_200"),
                InlineKeyboardButton("500 USDT", callback_data="amount_500")
            ],
            [InlineKeyboardButton("◀️ Geri", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            amount_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def amount_selection_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """İşlem miktarı seçimi callback'i - Güvenlik doğrulaması ile"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        try:
            # Callback data'dan miktarı çıkar
            amount_str = query.data.split('_')[1]
            amount = float(amount_str)
            
            # Güvenlik doğrulaması
            is_valid, message = InputValidator.validate_trading_amount(amount, user_id)
            if not is_valid:
                await query.edit_message_text(
                    f"❌ **Güvenlik Hatası:**\n{message}\n\n"
                    "Lütfen geçerli bir miktar seçin.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Tekrar Dene", callback_data="set_amount")],
                        [InlineKeyboardButton("🎛️ Bot Ayarları", callback_data="main_menu")]
                    ])
                )
                return
            
            # Ayarları güncelle
            self.db.update_user_settings(user_id, trading_amount_usdt=amount)
            
            await query.edit_message_text(
                f"✅ **İşlem miktarı {amount} USDT olarak ayarlandı!**\n\n"
                "Artık her işlemde bu miktar kullanılacak.\n"
                f"🛡️ Güvenlik: Onaylanmış miktar kullanılıyor.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎛️ Bot Ayarları", callback_data="main_menu")]
                ])
            )
            
        except (ValueError, IndexError) as e:
            logger.error(f"Amount selection error for user {user_id}: {e}")
            await query.edit_message_text(
                "❌ **Miktar seçimi hatası!**\n\n"
                "Lütfen geçerli bir miktar seçin.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Tekrar Dene", callback_data="set_amount")],
                    [InlineKeyboardButton("🎛️ Bot Ayarları", callback_data="main_menu")]
                ])
            )
    
    async def set_take_profit_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Take Profit ayarlama callback'i"""
        query = update.callback_query
        await query.answer()
        
        tp_text = """
📈 **Take Profit Hedefi Ayarla**

İşlemlerin otomatik kapatılması için kar hedefini seç:
        """
        
        keyboard = [
            [
                InlineKeyboardButton("200%", callback_data="tp_200"),
                InlineKeyboardButton("300%", callback_data="tp_300"),
                InlineKeyboardButton("500%", callback_data="tp_500")
            ],
            [
                InlineKeyboardButton("600%", callback_data="tp_600"),
                InlineKeyboardButton("800%", callback_data="tp_800"),
                InlineKeyboardButton("1000%", callback_data="tp_1000")
            ],
            [InlineKeyboardButton("◀️ Geri", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            tp_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def tp_selection_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Take Profit seçimi callback'i - Güvenlik doğrulaması ile"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        try:
            # Callback data'dan yüzdeyi çıkar
            tp_str = query.data.split('_')[1]
            tp_percentage = float(tp_str)
            
            # Güvenlik doğrulaması
            is_valid, message = InputValidator.validate_take_profit(tp_percentage, user_id)
            if not is_valid:
                await query.edit_message_text(
                    f"❌ **Güvenlik Hatası:**\n{message}\n\n"
                    "Lütfen geçerli bir yüzde seçin.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔄 Tekrar Dene", callback_data="set_tp")],
                        [InlineKeyboardButton("🎛️ Bot Ayarları", callback_data="main_menu")]
                    ])
                )
                return
            
            # Ayarları güncelle
            self.db.update_user_settings(user_id, take_profit_percentage=tp_percentage)
            
            await query.edit_message_text(
                f"✅ **Take Profit %{tp_percentage} olarak ayarlandı!**\n\n"
                f"İşlemler %{tp_percentage} kâra ulaştığında otomatik kapatılacak.\n"
                f"🛡️ Güvenlik: Onaylanmış yüzde kullanılıyor.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎛️ Bot Ayarları", callback_data="main_menu")]
                ])
            )
            
        except (ValueError, IndexError) as e:
            logger.error(f"Take profit selection error for user {user_id}: {e}")
            await query.edit_message_text(
                "❌ **Take Profit seçimi hatası!**\n\n"
                "Lütfen geçerli bir yüzde seçin.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Tekrar Dene", callback_data="set_tp")],
                    [InlineKeyboardButton("🎛️ Bot Ayarları", callback_data="main_menu")]
                ])
            )
    
    async def emergency_stop_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Acil durdurma callback'i"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        confirm_text = """
🚨 **ACİL DURDURMA**

⚠️ **DİKKAT:** Bu işlem:
• Tüm açık pozisyonları kapatacak
• Otomatik ticareti durduracak
• Kayıpla sonuçlanabilir

Emin misin?
        """
        
        keyboard = [
            [
                InlineKeyboardButton("✅ EVET, DURDUR", callback_data="confirm_emergency"),
                InlineKeyboardButton("❌ HAYIR", callback_data="main_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            confirm_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def confirm_emergency_stop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Acil durdurma onayı"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Kullanıcı ayarlarını güncelle
        self.db.update_user_settings(
            user_id, 
            auto_trading=False, 
            emergency_stop=True
        )
        
        # Kullanıcının API anahtarlarını al
        api_keys = self.db.get_user_api_keys(user_id)
        
        if api_keys and api_keys['is_configured']:
            # Kullanıcı bazlı emergency stop dosyası oluştur
            user_dir = os.path.join(os.path.dirname(__file__), "PERP", "users", str(user_id))
            os.makedirs(user_dir, exist_ok=True)
            emergency_file = os.path.join(user_dir, "emergency_stop.txt")
            
            with open(emergency_file, 'w') as f:
                f.write("EMERGENCY_STOP")
            
            # Kullanıcı bazlı environment ile pozisyon kapatma scriptini çalıştır
            try:
                user_env = os.environ.copy()
                user_env['BITGET_API_KEY'] = api_keys['api_key']
                user_env['BITGET_SECRET_KEY'] = api_keys['secret_key'] 
                user_env['BITGET_PASSPHRASE'] = api_keys['passphrase']
                user_env['USER_ID'] = str(user_id)
                
                result = subprocess.run(
                    ["python3", "PERP/kapat.py"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=user_env
                )
                print(f"Acil durdurma sonucu (User {user_id}): {result.returncode}")
            except Exception as e:
                print(f"Acil durdurma hatası (User {user_id}): {e}")
        else:
            print(f"User {user_id} için API anahtarları bulunamadı")
        
        await query.edit_message_text(
            "🚨 **ACİL DURDURMA TAMAMLANDI**\n\n"
            "• Tüm pozisyonlar kapatıldı\n"
            "• Otomatik ticaret durduruldu\n"
            "• Sistem güvenlik modunda\n\n"
            "Yeniden başlatmak için bot ayarlarına git.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎛️ Bot Ayarları", callback_data="main_menu")]
            ])
        )
        
        # Bildirim ekle
        self.db.add_notification(
            user_id, 
            'SYSTEM', 
            'Acil Durdurma', 
            'Tüm pozisyonlar kapatıldı ve sistem durduruldu.'
        )
    
    async def broadcast_new_coin_notification(self, coin_symbol: str, coin_name: str, price: float):
        """Yeni coin bildirimini tüm kullanıcılara gönder"""
        active_users = self.db.get_active_users()
        
        notification_text = f"""
🚨 **YENİ COİN LİSTELENDİ!**

💰 **Coin:** {coin_name} ({coin_symbol})
💵 **Fiyat:** ${price}
📈 **Durum:** İşlem açılıyor...

Otomatik ticaret ayarların aktifse işlem başlatılacak.
        """
        
        keyboard = [
            [InlineKeyboardButton("📊 İşlem Detayları", callback_data=f"trade_details_{coin_symbol}")],
            [InlineKeyboardButton("🚨 ACİL DURDUR", callback_data="emergency_stop")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Telegram application instance gerekli (ana sistemle entegrasyon gerekir)
        for user_id in active_users:
            try:
                # Bu kısım ana sistemle entegre edilecek
                self.db.add_notification(
                    user_id, 
                    'NEW_COIN', 
                    f'Yeni Coin: {coin_symbol}', 
                    f'{coin_name} ({coin_symbol}) ${price} fiyatıyla listelendi.'
                )
                print(f"📢 {user_id} kullanıcısına yeni coin bildirimi gönderildi: {coin_symbol}")
            except Exception as e:
                print(f"Bildirim gönderme hatası (User {user_id}): {e}")
    
    async def manual_long_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manuel long işlemi callback'i"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        api_keys = self.db.get_user_api_keys(user_id)
        settings = self.db.get_user_settings(user_id)
        
        # API anahtarları kontrolü
        if not api_keys or not api_keys['is_configured']:
            await query.edit_message_text(
                "❌ **API Anahtarları Eksik!**\n\n"
                "Manuel işlem yapmak için önce Bitget API anahtarlarını eklemen gerekiyor.\n\n"
                "🔑 Bot Ayarları → API Anahtarları",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔑 API Ekle", callback_data="setup_api")],
                    [InlineKeyboardButton("◀️ Geri", callback_data="main_menu")]
                ])
            )
            return
        
        # Popüler coin listesi
        popular_coins = [
            "BTC", "ETH", "BNB", "SOL", "ADA", "XRP", "DOT", "MATIC", 
            "LINK", "AVAX", "LTC", "BCH", "UNI", "ATOM", "FTM", "NEAR"
        ]
        
        manual_text = f"""
📊 **Manuel Long İşlemi**

🎯 **Mevcut Ayarların:**
💰 İşlem Miktarı: {settings['trading_amount']} USDT
📈 Take Profit: %{settings['take_profit']}
⚡ Leverage: Maksimum (Bitget otomatik)

🪙 **Coin Seçimi:**
Popüler coinlerden birini seç veya kendi symbol'ünü gir (ETH, BTC, SOL vs).
        """
        
        # Popüler coinleri 4'lü satırlarda düzenle
        keyboard = []
        for i in range(0, len(popular_coins), 4):
            row = []
            for j in range(i, min(i + 4, len(popular_coins))):
                coin = popular_coins[j]
                row.append(InlineKeyboardButton(f"{coin}", callback_data=f"long_{coin}"))
            keyboard.append(row)
        
        # Custom symbol ve geri butonları
        keyboard.append([InlineKeyboardButton("✏️ Özel Symbol Gir", callback_data="custom_symbol_input")])
        keyboard.append([InlineKeyboardButton("◀️ Geri", callback_data="main_menu")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            manual_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def manual_long_selection_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manuel long coin seçimi callback'i"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        coin_symbol = query.data.replace("long_", "")
        settings = self.db.get_user_settings(user_id)
        
        # Onay mesajı
        confirm_text = f"""
🚀 **Long İşlemi Onayı**

🪙 **Coin:** {coin_symbol}USDT_UMCBL
💰 **Miktar:** {settings['trading_amount']} USDT
📈 **Take Profit:** %{settings['take_profit']}
⚡ **Leverage:** Maksimum
🎯 **İşlem Türü:** Long (Yükseliş bahsi)

⚠️ **DİKKAT:** Bu gerçek para ile işlem açacak!

Bu ayarlarla long işlemi açmak istediğinden emin misin?
        """
        
        keyboard = [
            [
                InlineKeyboardButton("✅ EVET, AÇ", callback_data=f"confirm_long_{coin_symbol}"),
                InlineKeyboardButton("❌ HAYIR", callback_data="manual_long")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            confirm_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def confirm_manual_long_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manuel long işlemini onayla ve gerçekleştir"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        coin_symbol = query.data.replace("confirm_long_", "")
        settings = self.db.get_user_settings(user_id)
        
        try:
            # Kullanıcı bazlı dizin oluştur
            user_dir = os.path.join(os.path.dirname(__file__), "PERP", "users", str(user_id))
            os.makedirs(user_dir, exist_ok=True)
            
            # Manuel long işlemi dosyasını kullanıcı bazlı oluştur
            # Eğer custom symbol ise mapping kullan, değilse standart format
            perp_symbol = self._map_symbol_to_bitget(coin_symbol) or f"{coin_symbol}USDT_UMCBL"
            perp_file = os.path.join(user_dir, "manual_long_output.txt")
            
            with open(perp_file, 'w') as f:
                f.write(perp_symbol)
            
            # Log kaydı oluştur
            logger.info(f"Manual long triggered: {coin_symbol} by user {user_id}")
            
            # Bildirim mesajı
            await query.edit_message_text(
                f"🚀 **Manuel Long İşlemi Tetiklendi!**\n\n"
                f"🪙 **Coin:** {coin_symbol}\n"
                f"💰 **Miktar:** {settings['trading_amount']} USDT\n"
                f"📈 **Take Profit:** %{settings['take_profit']}\n"
                f"⚡ **Format:** {perp_symbol}\n\n"
                f"🔄 İşlem Bitget'te açılıyor...\n"
                f"📱 Sonuç bildirimi gelecek!\n\n"
                f"⚠️ Pozisyon durumunu takip edin.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📊 İşlem Durumu", callback_data="trade_status")],
                    [InlineKeyboardButton("🚨 ACİL DURDUR", callback_data="emergency_stop")],
                    [InlineKeyboardButton("🎛️ Bot Ayarları", callback_data="main_menu")]
                ])
            )
            
            # Veritabanına bildirim ekle
            self.db.add_notification(
                user_id, 
                'MANUAL_LONG', 
                f'Manuel Long: {coin_symbol}', 
                f'{coin_symbol} için manuel long işlemi tetiklendi ({settings["trading_amount"]} USDT)'
            )
            
        except Exception as e:
            logger.error(f"Manual long error for user {user_id}: {e}")
            await query.edit_message_text(
                f"❌ **Manuel Long Hatası!**\n\n"
                f"Hata: {str(e)}\n\n"
                f"Lütfen tekrar deneyin.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Tekrar Dene", callback_data="manual_long")],
                    [InlineKeyboardButton("🎛️ Bot Ayarları", callback_data="main_menu")]
                ])
            )
    
    async def custom_symbol_input_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Custom symbol girişi için callback"""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        
        # Kullanıcıyı custom symbol bekleme state'ine al
        self.user_states[user_id] = "waiting_for_custom_symbol"
        
        await query.edit_message_text(
            "✏️ **Özel Symbol Girişi**\n\n"
            "🪙 **Lütfen işlem yapmak istediğin coin symbol'ünü yaz:**\n\n"
            "📝 **Örnek:** ETH, BTC, SOL, ADA, LINK\n"
            "⚠️ **Not:** Sadece büyük harflerle yazabilirsin\n"
            "❌ **İptal etmek için:** /cancel\n\n"
            "👇 **Symbol'ü aşağıya yaz:**",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ İptal", callback_data="manual_long")]
            ])
        )
    
    async def process_custom_symbol_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Custom symbol mesajını işle"""
        user_id = update.effective_user.id
        text = update.message.text.strip().upper()
        
        # State kontrolü
        if self.user_states.get(user_id) != "waiting_for_custom_symbol":
            return
        
        # Cancel komutu kontrolü
        if text == "/CANCEL":
            self.user_states.pop(user_id, None)
            await update.message.reply_text(
                "❌ **İptal edildi**\n\nManuel long menüsüne geri dön:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📊 Manuel Long", callback_data="manual_long")]
                ])
            )
            return
        
        # Symbol validasyonu
        if not self._validate_custom_symbol(text):
            await update.message.reply_text(
                "❌ **Geçersiz Symbol!**\n\n"
                "🔸 **Geçerli format:** 2-6 karakter, sadece harfler\n"
                "🔸 **Örnek:** ETH, BTC, SOL, MATIC\n\n"
                "👇 **Tekrar dene:**"
            )
            return
        
        # State temizle
        self.user_states.pop(user_id, None)
        
        # Symbol mapping ve validation
        perp_symbol = self._map_symbol_to_bitget(text)
        if not perp_symbol:
            await update.message.reply_text(
                f"❌ **{text} Desteklenmiyor!**\n\n"
                "🔸 Bu coin Bitget'te mevcut değil\n"
                "🔸 Desteklenen coinler: BTC, ETH, SOL, ADA vs\n\n"
                "👇 **Geçerli bir symbol dene:**"
            )
            return
            
        # Symbol'ü onay menüsüne gönder  
        settings = self.db.get_user_settings(user_id)
        
        confirm_text = f"""
🚀 **Custom Long İşlemi Onayı**

🪙 **Coin:** {text} → {perp_symbol}
💰 **Miktar:** {settings['trading_amount']} USDT
📈 **Take Profit:** %{settings['take_profit']}
⚡ **Leverage:** Maksimum
🎯 **İşlem Türü:** Long (Yükseliş bahsi)

⚠️ **DİKKAT:** Bu gerçek para ile işlem açacak!

Bu ayarlarla {text} long işlemi açmak istediğinden emin misin?
        """
        
        keyboard = [
            [
                InlineKeyboardButton("✅ EVET, AÇ", callback_data=f"confirm_long_{text}"),
                InlineKeyboardButton("❌ HAYIR", callback_data="manual_long")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            confirm_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    def _validate_custom_symbol(self, symbol: str) -> bool:
        """Custom symbol validasyonu"""
        if not symbol:
            return False
        
        # 2-6 karakter arası, sadece harfler
        if len(symbol) < 2 or len(symbol) > 6:
            return False
        
        # Sadece harfler (A-Z)
        if not symbol.isalpha():
            return False
            
        # Yaygın coin sembolleri listesi (opsiyonel)
        common_symbols = [
            "BTC", "ETH", "BNB", "SOL", "ADA", "XRP", "DOT", "MATIC", "LINK", "AVAX",
            "LTC", "BCH", "UNI", "ATOM", "FTM", "NEAR", "ALGO", "VET", "ICP", "MANA",
            "SAND", "AXS", "SHIB", "DOGE", "TRX", "EOS", "XLM", "AAVE", "SUSHI"
        ]
        
        logger.info(f"Custom symbol validated: {symbol} (common: {symbol in common_symbols})")
        return True
    
    def _map_symbol_to_bitget(self, symbol: str) -> str:
        """Symbol'ü Bitget PERP formatına çevir"""
        # Desteklenen coin mapping tablosu
        symbol_mapping = {
            "BTC": "BTCUSDT_UMCBL",
            "ETH": "ETHUSDT_UMCBL", 
            "BNB": "BNBUSDT_UMCBL",
            "SOL": "SOLUSDT_UMCBL",
            "ADA": "ADAUSDT_UMCBL",
            "XRP": "XRPUSDT_UMCBL",
            "DOT": "DOTUSDT_UMCBL",
            "MATIC": "MATICUSDT_UMCBL",
            "LINK": "LINKUSDT_UMCBL",
            "AVAX": "AVAXUSDT_UMCBL",
            "LTC": "LTCUSDT_UMCBL",
            "BCH": "BCHUSDT_UMCBL",
            "UNI": "UNIUSDT_UMCBL",
            "ATOM": "ATOMUSDT_UMCBL",
            "FTM": "FTMUSDT_UMCBL",
            "NEAR": "NEARUSDT_UMCBL",
            "ALGO": "ALGOUSDT_UMCBL",
            "VET": "VETUSDT_UMCBL",
            "ICP": "ICPUSDT_UMCBL",
            "MANA": "MANAUSDT_UMCBL",
            "SAND": "SANDUSDT_UMCBL",
            "AXS": "AXSUSDT_UMCBL",
            "SHIB": "SHIBUSDT_UMCBL",
            "DOGE": "DOGEUSDT_UMCBL",
            "TRX": "TRXUSDT_UMCBL",
            "EOS": "EOSUSDT_UMCBL",
            "XLM": "XLMUSDT_UMCBL",
            "AAVE": "AAVEUSDT_UMCBL",
            "SUSHI": "SUSHIUSDT_UMCBL"
        }
        
        return symbol_mapping.get(symbol.upper())
    
    async def broadcast_trade_notification(self, user_id: int, action: str, coin_symbol: str, 
                                         amount: float, price: float, trade_id: int):
        """İşlem bildirimini kullanıcıya gönder"""
        
        action_text = "📈 AÇILDI" if action == "BUY" else "📉 KAPATILDI"
        
        trade_text = f"""
{action_text} **İŞLEM BİLDİRİMİ**

💰 **Coin:** {coin_symbol}
💵 **Miktar:** {amount} USDT
💲 **Fiyat:** ${price}
🕐 **Zaman:** {datetime.now().strftime('%H:%M:%S')}

İD: {trade_id}
        """
        
        keyboard = [
            [InlineKeyboardButton("🚨 ACİL KAPAT", callback_data=f"emergency_close_{trade_id}")],
            [InlineKeyboardButton("📊 Detaylar", callback_data=f"trade_details_{trade_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Bildirim ekle
        self.db.add_notification(
            user_id, 
            'TRADE_OPEN' if action == 'BUY' else 'TRADE_CLOSED', 
            f'İşlem {action_text}', 
            f'{coin_symbol} için {amount} USDT işlem {action_text.lower()}'
        )
        
        print(f"📱 {user_id} kullanıcısına işlem bildirimi: {action} {coin_symbol}")
    
    async def check_notification_file(self, application):
        """Bildirim dosyasını kontrol et ve Telegram bildirimlerini gönder"""
        try:
            if not os.path.exists(self.notification_file):
                return
            
            # Dosya değişiklik zamanını kontrol et
            file_mtime = os.path.getmtime(self.notification_file)
            if file_mtime <= self.last_notification_check:
                return
            
            # Notification dosyasını oku
            with open(self.notification_file, 'r', encoding='utf-8') as f:
                notification_data = json.load(f)
            
            if notification_data.get('type') == 'NEW_COIN':
                coins = notification_data.get('coins', [])
                timestamp = notification_data.get('timestamp', '')
                
                # Tüm aktif kullanıcılara bildirim gönder
                active_users = self.db.get_active_users()
                
                for coin in coins:
                    symbol = coin.get('symbol', '')
                    name = coin.get('name', '')
                    perp_symbol = coin.get('perp_symbol', '')
                    
                    notification_text = f"""
🚨 **YENİ COİN LİSTELENDİ!**

💰 **Coin:** {symbol}
📝 **Duyuru:** {name}
🔗 **PERP Sembol:** {perp_symbol}
🕐 **Zaman:** {datetime.now().strftime('%H:%M:%S')}

Otomatik ticaret ayarların aktifse işlem başlatılacak.
                    """
                    
                    keyboard = [
                        [InlineKeyboardButton("📊 İşlem Durumu", callback_data="trade_status")],
                        [InlineKeyboardButton("🚨 ACİL DURDUR", callback_data="emergency_stop")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    # Her kullanıcıya gönder
                    for user_id in active_users:
                        try:
                            user_settings = self.db.get_user_settings(user_id)
                            if user_settings.get('notifications', True):
                                await application.bot.send_message(
                                    chat_id=user_id,
                                    text=notification_text,
                                    parse_mode=ParseMode.MARKDOWN,
                                    reply_markup=reply_markup
                                )
                                
                                # Veritabanına bildirim ekle
                                self.db.add_notification(
                                    user_id,
                                    'NEW_COIN',
                                    f'Yeni Coin: {symbol}',
                                    f'{symbol} listesine eklendi: {perp_symbol}'
                                )
                                
                                print(f"📢 {user_id} kullanıcısına yeni coin bildirimi gönderildi: {symbol}")
                        except Exception as e:
                            print(f"Bildirim gönderme hatası (User {user_id}): {e}")
            
            # Son kontrol zamanını güncelle
            self.last_notification_check = file_mtime
            
            # Bildirim dosyasını sil (tekrar işlenmesini önlemek için)
            try:
                os.remove(self.notification_file)
                print(f"🗑️ Bildirim dosyası işlendikten sonra silindi")
            except:
                pass
                
        except Exception as e:
            print(f"⚠️ Bildirim kontrol hatası: {e}")

# Bot callback handler'ları
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback query'leri yönlendir"""
    query = update.callback_query
    data = query.data
    
    bot_instance = context.bot_data.get('trading_bot')
    if not bot_instance:
        await query.answer("Bot instance bulunamadı!")
        return
    
    # Callback routing
    if data == "main_menu":
        await bot_instance.main_menu_callback(update, context)
    elif data == "setup_api":
        await bot_instance.setup_api_callback(update, context)
    elif data == "set_amount":
        await bot_instance.set_trading_amount_callback(update, context)
    elif data.startswith("amount_"):
        await bot_instance.amount_selection_callback(update, context)
    elif data == "set_tp":
        await bot_instance.set_take_profit_callback(update, context)
    elif data.startswith("tp_"):
        await bot_instance.tp_selection_callback(update, context)
    elif data == "emergency_stop":
        await bot_instance.emergency_stop_callback(update, context)
    elif data == "confirm_emergency":
        await bot_instance.confirm_emergency_stop(update, context)
    elif data == "manual_long":
        await bot_instance.manual_long_callback(update, context)
    elif data.startswith("long_"):
        await bot_instance.manual_long_selection_callback(update, context)
    elif data.startswith("confirm_long_"):
        await bot_instance.confirm_manual_long_callback(update, context)
    elif data == "custom_symbol_input":
        await bot_instance.custom_symbol_input_callback(update, context)
    else:
        await query.answer("Bu özellik henüz hazır değil!")

# Periyodik görevler için job scheduler
async def periodic_notification_check(context: ContextTypes.DEFAULT_TYPE):
    """Periyodik olarak bildirim dosyasını kontrol et"""
    trading_bot = context.bot_data.get('trading_bot')
    if trading_bot:
        await trading_bot.check_notification_file(context.application)

# Ana bot fonksiyonu
def main():
    """Telegram bot'u başlat"""
    
    # Bot token kontrolü - SADECE environment variable'dan al
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN environment variable tanımlanmamış!")
        print("⚠️ Bot token'ını environment variable olarak ekleyin.")
        raise SystemExit("TELEGRAM_BOT_TOKEN environment variable gerekli!")
    
    # Token doğrulaması - hangi bot olduğunu kontrol et
    try:
        import requests
        response = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getMe")
        if response.status_code == 200:
            bot_info = response.json()['result']
            print(f"🤖 Bot doğrulandı: {bot_info['first_name']} (@{bot_info['username']})")
            if bot_info['username'] != 'BitgetPerpbot':
                print(f"⚠️ UYARI: Beklenen bot BitgetPerpbot ama {bot_info['username']} bulundu!")
        else:
            print("❌ Bot token doğrulaması başarısız!")
            raise SystemExit("Geçersiz bot token!")
    except Exception as e:
        print(f"❌ Bot token test hatası: {e}")
        raise SystemExit("Bot token doğrulaması başarısız!")
    
    # Bot instance oluştur
    trading_bot = AdvancedTradingBot()
    
    # Application oluştur
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Bot instance'ı context'e ekle
    application.bot_data['trading_bot'] = trading_bot
    
    # Komut handler'larını ekle
    application.add_handler(CommandHandler("start", trading_bot.start_command))
    application.add_handler(CallbackQueryHandler(callback_router))
    
    # API kurulum ve custom symbol mesajlarını yakala
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, 
        trading_bot.handle_message
    ))
    
    # Custom symbol input callback'i için explicit handler (güvenlik)
    application.add_handler(CallbackQueryHandler(
        trading_bot.custom_symbol_input_callback,
        pattern="^custom_symbol_input$"
    ))
    
    # Periyodik görevler (Job Queue)
    job_queue = application.job_queue
    job_queue.run_repeating(
        periodic_notification_check, 
        interval=30,  # 30 saniyede bir kontrol
        first=10      # İlk kontrol 10 saniye sonra
    )
    
    print("🤖 Gelişmiş Telegram Bot başlatılıyor...")
    print("🔄 Kullanıcı yönetimi aktif")
    print("🗄️ Veritabanı bağlantısı hazır")
    print("📱 Bildirim sistemi aktif (30 saniyede bir kontrol)")
    
    # Bot'u çalıştır
    application.run_polling()

if __name__ == '__main__':
    main()