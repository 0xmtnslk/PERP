#!/usr/bin/env python3
import os
import json
import sqlite3
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WorkingTradingBot:
    def __init__(self):
        self.db_path = "trading_bot.db"
        self.user_states = {}
        self.setup_db()
        
    def setup_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, 
                      api_key TEXT, secret_key TEXT, passphrase TEXT, 
                      amount REAL DEFAULT 50, is_active BOOLEAN DEFAULT 1)''')
        conn.commit()
        conn.close()
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        # User kaydet
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                 (user.id, user.username, user.first_name))
        conn.commit()
        conn.close()
        
        keyboard = [
            [InlineKeyboardButton("🎛️ Ayarlar", callback_data="settings")],
            [InlineKeyboardButton("📊 Manuel İşlem", callback_data="manual")],
            [InlineKeyboardButton("ℹ️ Durum", callback_data="status")]
        ]
        
        await update.message.reply_text(
            f"🚀 Hoş geldin {user.first_name}!\n\n"
            "• Otomatik Upbit takibi aktif\n"
            "• Manuel işlem yapabilirsin\n"
            "• API anahtarlarını ekle\n\n"
            "Ne yapmak istiyorsun?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        if query.data == "settings":
            keyboard = [
                [InlineKeyboardButton("🔑 API Anahtarları", callback_data="setup_api")],
                [InlineKeyboardButton("💰 İşlem Miktarı", callback_data="set_amount")],
                [InlineKeyboardButton("◀️ Ana Menü", callback_data="main")]
            ]
            await query.edit_message_text(
                "🎛️ **Ayarlar**\n\nNeyi ayarlamak istiyorsun?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        elif query.data == "manual":
            self.user_states[query.from_user.id] = "waiting_symbol"
            await query.edit_message_text(
                "📊 **Manuel İşlem**\n\n"
                "Hangi coin'i alacaksın? (Örnek: BTC, ETH, SOL)\n"
                "Symbol'ü yaz:",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ İptal", callback_data="main")]])
            )
            
        elif query.data == "setup_api":
            self.user_states[query.from_user.id] = "waiting_api_key"
            await query.edit_message_text(
                "🔑 **API Kurulumu**\n\n"
                "1. Adım: Bitget API Key'ini gönder\n"
                "(Bitget'ten aldığın API anahtarını yaz)",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ İptal", callback_data="settings")]])
            )
            
        elif query.data == "status":
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT api_key, amount FROM users WHERE user_id=?", (query.from_user.id,))
            result = c.fetchone()
            conn.close()
            
            if result and result[0]:
                status_text = f"✅ **Sistem Durumu**\n\n" \
                             f"🔑 API: Kurulu\n" \
                             f"💰 Miktar: {result[1]} USDT\n" \
                             f"🤖 Otomatik: Aktif\n" \
                             f"👀 Upbit Takibi: Çalışıyor"
            else:
                status_text = "⚠️ **API anahtarları eksik**\n\nÖnce ayarlardan API'yi kur"
                
            await query.edit_message_text(
                status_text,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Ana Menü", callback_data="main")]]),
                parse_mode='Markdown'
            )
            
        elif query.data == "main":
            keyboard = [
                [InlineKeyboardButton("🎛️ Ayarlar", callback_data="settings")],
                [InlineKeyboardButton("📊 Manuel İşlem", callback_data="manual")],
                [InlineKeyboardButton("ℹ️ Durum", callback_data="status")]
            ]
            await query.edit_message_text(
                f"🚀 Ana Menü\n\n"
                "• Otomatik Upbit takibi aktif\n"
                "• Manuel işlem yapabilirsin\n"
                "• API anahtarlarını ekle\n\n"
                "Ne yapmak istiyorsun?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        text = update.message.text.strip()
        
        if user_id not in self.user_states:
            return
            
        state = self.user_states[user_id]
        
        if state == "waiting_symbol":
            # Manuel işlem
            symbol = text.upper()
            if len(symbol) > 1 and symbol.isalpha():
                # İşlem dosyasını oluştur
                user_dir = f"PERP/users/{user_id}"
                os.makedirs(user_dir, exist_ok=True)
                
                perp_symbol = f"{symbol}USDT_UMCBL"
                with open(f"{user_dir}/manual_long_output.txt", "w") as f:
                    f.write(perp_symbol)
                
                await update.message.reply_text(
                    f"🚀 **İşlem Başlatıldı!**\n\n"
                    f"🪙 Coin: {symbol}\n"
                    f"⚡ Format: {perp_symbol}\n"
                    f"🔄 Bitget'te açılıyor...\n\n"
                    f"📱 Bildirim gelecek!",
                    parse_mode='Markdown'
                )
                
                self.user_states.pop(user_id, None)
                logger.info(f"Manuel trade: {symbol} by user {user_id}")
            else:
                await update.message.reply_text("❌ Geçersiz symbol! (Örnek: BTC, ETH)")
                
        elif state == "waiting_api_key":
            # API key kaydet
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("UPDATE users SET api_key=? WHERE user_id=?", (text, user_id))
            conn.commit()
            conn.close()
            
            self.user_states[user_id] = "waiting_secret_key"
            await update.message.reply_text(
                "✅ API Key kaydedildi!\n\n"
                "2. Adım: Secret Key'ini gönder"
            )
            
        elif state == "waiting_secret_key":
            # Secret key kaydet
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("UPDATE users SET secret_key=? WHERE user_id=?", (text, user_id))
            conn.commit()
            conn.close()
            
            self.user_states[user_id] = "waiting_passphrase"
            await update.message.reply_text(
                "✅ Secret Key kaydedildi!\n\n"
                "3. Adım: Passphrase'ini gönder"
            )
            
        elif state == "waiting_passphrase":
            # Passphrase kaydet
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("UPDATE users SET passphrase=? WHERE user_id=?", (text, user_id))
            conn.commit()
            conn.close()
            
            # Environment variable'lara da ekle
            os.environ['BITGET_API_KEY'] = text  # Geçici
            
            self.user_states.pop(user_id, None)
            await update.message.reply_text(
                "🎉 **API Kurulumu Tamamlandı!**\n\n"
                "✅ Tüm anahtarlar kaydedildi\n"
                "✅ Otomatik işlemler aktif\n"
                "✅ Manuel işlem yapabilirsin\n\n"
                "🚀 Sistem hazır!"
            )

def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ TELEGRAM_BOT_TOKEN yok!")
        return
        
    print("🚀 ÇALIŞAN BOT BAŞLATIYOR...")
    
    bot = WorkingTradingBot()
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CallbackQueryHandler(bot.handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    
    print("✅ Bot çalışıyor...")
    app.run_polling()

if __name__ == '__main__':
    main()