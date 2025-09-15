#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
STABIL TELEGRAM BOT - Basit ve çalışır versiyonu
"""
import os
import json
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Optional, List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Logging konfigürasyonu
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleTradingBot:
    """Basit ve stabil Telegram bot"""
    
    def __init__(self):
        self.db_path = "trading_bot.db"
        self.init_database()
        logger.info("✅ Basit Trading Bot başlatıldı")
    
    def init_database(self):
        """Basit veritabanı başlatma"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("🗄️ Basit veritabanı hazır")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start komutu"""
        user = update.effective_user
        
        # Kullanıcıyı kaydet
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, username, first_name)
            VALUES (?, ?, ?)
        ''', (user.id, user.username or "unknown", user.first_name))
        conn.commit()
        conn.close()
        
        welcome_text = f"""🚀 **Kripto Trading Bot'a Hoş Geldin, {user.first_name}!**

Bu bot ile:
• 🔑 API anahtarlarını yönet
• 💰 İşlem miktarlarını ayarla  
• 📊 Manuel trading yap
• 🚨 Otomatik işlemleri kontrol et

Başlamak için aşağıdaki menüyü kullan:"""
        
        keyboard = [
            [InlineKeyboardButton("🎛️ Bot Ayarları", callback_data="main_menu")],
            [InlineKeyboardButton("📊 İşlem Durumu", callback_data="trade_status")],
            [InlineKeyboardButton("🆘 Yardım", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def main_menu_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ana menü"""
        query = update.callback_query
        await query.answer()
        
        menu_text = """🎛️ **Bot Ayarları**

Hangi işlemi yapmak istiyorsun?"""
        
        keyboard = [
            [InlineKeyboardButton("🔑 API Anahtarları", callback_data="setup_api")],
            [InlineKeyboardButton("💰 İşlem Miktarı", callback_data="set_amount")],
            [InlineKeyboardButton("📈 Take Profit", callback_data="set_tp")],
            [InlineKeyboardButton("🤖 Oto Ticaret", callback_data="toggle_auto")],
            [InlineKeyboardButton("📊 Manuel Long", callback_data="manual_long")],
            [InlineKeyboardButton("🔔 Bildirimler", callback_data="toggle_notifications")],
            [InlineKeyboardButton("🚨 ACİL DURDUR", callback_data="emergency_stop")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            menu_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def manual_long_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Manuel long işlemi"""
        query = update.callback_query
        await query.answer()
        
        manual_text = """📊 **Manuel Long İşlemi**

🎯 **Mevcut Ayarların:**
💰 İşlem Miktarı: 50 USDT (varsayılan)
📈 Take Profit: %500 (varsayılan)
⚡ Leverage: Maksimum (Bitget otomatik)

🪙 **Coin Seçimi:**
Popüler coinlerden birini seç veya kendi symbol'ünü gir."""
        
        # Popüler coinler
        keyboard = [
            [
                InlineKeyboardButton("BTC", callback_data="long_BTC"),
                InlineKeyboardButton("ETH", callback_data="long_ETH"),
                InlineKeyboardButton("BNB", callback_data="long_BNB"),
                InlineKeyboardButton("SOL", callback_data="long_SOL")
            ],
            [
                InlineKeyboardButton("ADA", callback_data="long_ADA"),
                InlineKeyboardButton("XRP", callback_data="long_XRP"),
                InlineKeyboardButton("DOT", callback_data="long_DOT"),
                InlineKeyboardButton("MATIC", callback_data="long_MATIC")
            ],
            [
                InlineKeyboardButton("LINK", callback_data="long_LINK"),
                InlineKeyboardButton("AVAX", callback_data="long_AVAX"),
                InlineKeyboardButton("LTC", callback_data="long_LTC"),
                InlineKeyboardButton("UNI", callback_data="long_UNI")
            ],
            [InlineKeyboardButton("✏️ Özel Symbol Gir", callback_data="custom_symbol")],
            [InlineKeyboardButton("◀️ Geri", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            manual_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def coin_selection_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Coin seçimi onayı"""
        query = update.callback_query
        await query.answer()
        
        coin_symbol = query.data.replace("long_", "")
        
        confirm_text = f"""🚀 **Long İşlemi Onayı**

🪙 **Coin:** {coin_symbol}USDT_UMCBL
💰 **Miktar:** 50 USDT
📈 **Take Profit:** %500
⚡ **Leverage:** Maksimum
🎯 **İşlem Türü:** Long (Yükseliş bahsi)

⚠️ **DİKKAT:** Bu gerçek para ile işlem açacak!

Bu ayarlarla {coin_symbol} long işlemi açmak istediğinden emin misin?"""
        
        keyboard = [
            [
                InlineKeyboardButton("✅ EVET, AÇ", callback_data=f"confirm_{coin_symbol}"),
                InlineKeyboardButton("❌ HAYIR", callback_data="manual_long")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            confirm_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def confirm_trade_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """İşlemi onayla ve başlat"""
        query = update.callback_query
        await query.answer()
        
        coin_symbol = query.data.replace("confirm_", "")
        user_id = query.from_user.id
        
        try:
            # Manuel long dosyasını oluştur
            user_dir = os.path.join("PERP", "users", str(user_id))
            os.makedirs(user_dir, exist_ok=True)
            
            perp_symbol = f"{coin_symbol}USDT_UMCBL"
            perp_file = os.path.join(user_dir, "manual_long_output.txt")
            
            with open(perp_file, 'w') as f:
                f.write(perp_symbol)
            
            success_text = f"""🚀 **Manuel Long İşlemi Tetiklendi!**

🪙 **Coin:** {coin_symbol}
💰 **Miktar:** 50 USDT
📈 **Take Profit:** %500
⚡ **Format:** {perp_symbol}

🔄 İşlem Bitget'te açılıyor...
📱 Sonuç bildirimi gelecek!

⚠️ Pozisyon durumunu takip edin."""
            
            keyboard = [
                [InlineKeyboardButton("📊 İşlem Durumu", callback_data="trade_status")],
                [InlineKeyboardButton("🚨 ACİL DURDUR", callback_data="emergency_stop")],
                [InlineKeyboardButton("🎛️ Bot Ayarları", callback_data="main_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                success_text,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            
            logger.info(f"✅ Manuel long tetiklendi: {coin_symbol} by user {user_id}")
            
        except Exception as e:
            logger.error(f"❌ Manuel long hatası: {e}")
            await query.edit_message_text(
                f"❌ **İşlem Hatası!**\n\nHata: {str(e)}\n\nLütfen tekrar deneyin.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Tekrar Dene", callback_data="manual_long")]
                ]),
                parse_mode='Markdown'
            )
    
    async def emergency_stop_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Acil durdurma"""
        query = update.callback_query
        await query.answer()
        
        emergency_text = """🚨 **ACİL DURDUR**

⚠️ **UYARI:** Bu işlem tüm açık pozisyonlarınızı kapatacak!

Emin misin?"""
        
        keyboard = [
            [
                InlineKeyboardButton("🚨 EVET, TÜM POZİSYONLARI KAPAT", callback_data="confirm_emergency"),
                InlineKeyboardButton("❌ HAYIR", callback_data="main_menu")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            emergency_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    async def generic_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Genel callback handler - diğer butonlar için"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "setup_api":
            await query.edit_message_text(
                "🔑 **API Kurulumu**\n\nAPI anahtarı kurulumu yakında aktif olacak!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="main_menu")]]),
                parse_mode='Markdown'
            )
        elif query.data == "trade_status":
            await query.edit_message_text(
                "📊 **İşlem Durumu**\n\nŞu anda açık pozisyonunuz bulunmuyor.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="main_menu")]]),
                parse_mode='Markdown'
            )
        elif query.data == "help":
            await query.edit_message_text(
                "🆘 **Yardım**\n\nBot kullanımı:\n1. API anahtarlarını ekle\n2. İşlem miktarını ayarla\n3. Manuel veya otomatik trading yap",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Ana Menü", callback_data="main_menu")]]),
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                f"⚠️ **Geliştirme Aşamasında**\n\n`{query.data}` özelliği yakında aktif olacak!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Geri", callback_data="main_menu")]]),
                parse_mode='Markdown'
            )

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback router - tüm buton tıklamalarını yönlendir"""
    query = update.callback_query
    data = query.data
    
    bot_instance = context.bot_data.get('trading_bot')
    if not bot_instance:
        await query.answer("❌ Bot hatası!")
        return
    
    try:
        # Ana menü
        if data == "main_menu":
            await bot_instance.main_menu_callback(update, context)
        # Manuel long menüsü
        elif data == "manual_long":
            await bot_instance.manual_long_callback(update, context)
        # Coin seçimi
        elif data.startswith("long_"):
            await bot_instance.coin_selection_callback(update, context)
        # İşlem onayı
        elif data.startswith("confirm_"):
            await bot_instance.confirm_trade_callback(update, context)
        # Acil durdur
        elif data == "emergency_stop":
            await bot_instance.emergency_stop_callback(update, context)
        # Diğer tüm butonlar
        else:
            await bot_instance.generic_callback(update, context)
            
    except Exception as e:
        logger.error(f"❌ Callback hatası: {e}")
        await query.answer("⚠️ Bir hata oluştu, tekrar deneyin.")

def main():
    """Bot başlatma"""
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN bulunamadı!")
        return
    
    print("🚀 STABIL TELEGRAM BOT BAŞLATIYOR...")
    
    # Bot instance
    trading_bot = SimpleTradingBot()
    
    # Application
    application = Application.builder().token(BOT_TOKEN).build()
    application.bot_data['trading_bot'] = trading_bot
    
    # Handler'lar
    application.add_handler(CommandHandler("start", trading_bot.start_command))
    application.add_handler(CallbackQueryHandler(callback_router))
    
    print("✅ Bot hazır - çalışıyor...")
    print("📱 Telegram'dan /start yazın")
    
    # Bot'u çalıştır
    application.run_polling()

if __name__ == '__main__':
    main()