#!/usr/bin/env python3
import os
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

class FinalBot:
    def __init__(self):
        self.db_path = "trading_bot.db"
        self.init_db()
        
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users 
                     (user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT, 
                      api_key TEXT DEFAULT '', secret_key TEXT DEFAULT '', passphrase TEXT DEFAULT '',
                      amount REAL DEFAULT 50, is_active BOOLEAN DEFAULT 1)''')
        conn.commit()
        conn.close()
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        
        # Kullanıcı kaydet
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                 (user.id, user.username or "unknown", user.first_name))
        conn.commit()
        conn.close()
        
        keyboard = [
            [InlineKeyboardButton("🔑 API Kurulumu", callback_data="api_setup")],
            [InlineKeyboardButton("📊 Manuel Trading", callback_data="manual_trade")],
            [InlineKeyboardButton("ℹ️ Durum", callback_data="status")]
        ]
        
        await update.message.reply_text(
            f"🚀 **Kripto Trading Bot**\n\n"
            f"Hoş geldin {user.first_name}!\n\n"
            f"**Ne yapmak istiyorsun?**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        
        if query.data == "api_setup":
            await query.edit_message_text(
                "🔑 **API Kurulumu**\n\n"
                "Şimdilik API kurulumu manuel yapılacak.\n"
                "API anahtarların environment'a eklenmiş varsayılıyor.\n\n"
                "✅ Sistem hazır!",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Ana Menü", callback_data="main_menu")]]),
                parse_mode='Markdown'
            )
            
        elif query.data == "manual_trade":
            keyboard = [
                [InlineKeyboardButton("BTC", callback_data="trade_BTC")],
                [InlineKeyboardButton("ETH", callback_data="trade_ETH")],
                [InlineKeyboardButton("SOL", callback_data="trade_SOL")],
                [InlineKeyboardButton("ADA", callback_data="trade_ADA")],
                [InlineKeyboardButton("◀️ Ana Menü", callback_data="main_menu")]
            ]
            await query.edit_message_text(
                "📊 **Manuel Trading**\n\n"
                "Hangi coin'i alacaksın?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        elif query.data.startswith("trade_"):
            symbol = query.data.replace("trade_", "")
            
            # Trading dosyasını oluştur
            user_dir = f"PERP/users/{user_id}"
            os.makedirs(user_dir, exist_ok=True)
            
            perp_symbol = f"{symbol}USDT_UMCBL"
            with open(f"{user_dir}/manual_long_output.txt", "w") as f:
                f.write(perp_symbol)
                
            await query.edit_message_text(
                f"🚀 **İşlem Tetiklendi!**\n\n"
                f"🪙 **Coin:** {symbol}\n"
                f"💰 **Miktar:** 50 USDT\n"
                f"⚡ **Format:** {perp_symbol}\n\n"
                f"🔄 **Durum:** Bitget'te işlem açılıyor...\n"
                f"📱 **Bildirim:** Sonuç gelecek!\n\n"
                f"✅ **Dosya oluşturuldu:** PERP/users/{user_id}/manual_long_output.txt",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Yeni İşlem", callback_data="manual_trade")]]),
                parse_mode='Markdown'
            )
            
        elif query.data == "status":
            await query.edit_message_text(
                "ℹ️ **Sistem Durumu**\n\n"
                "🤖 **Bot:** Çalışıyor\n"
                "👀 **Upbit Takibi:** Aktif\n"
                "⚡ **Trading Engine:** Çalışıyor\n"
                "🔑 **API:** Environment'tan alınıyor\n\n"
                "✅ **Sistem hazır!**",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Ana Menü", callback_data="main_menu")]]),
                parse_mode='Markdown'
            )
            
        elif query.data == "main_menu":
            keyboard = [
                [InlineKeyboardButton("🔑 API Kurulumu", callback_data="api_setup")],
                [InlineKeyboardButton("📊 Manuel Trading", callback_data="manual_trade")],
                [InlineKeyboardButton("ℹ️ Durum", callback_data="status")]
            ]
            
            await query.edit_message_text(
                f"🚀 **Kripto Trading Bot**\n\n"
                f"**Ana Menü**\n\n"
                f"**Ne yapmak istiyorsun?**",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )

def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ TOKEN YOK!")
        return
        
    print("🚀 FINAL BOT BAŞLATIYOR...")
    
    bot = FinalBot()
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CallbackQueryHandler(bot.handle_callback))
    
    print("✅ Final bot hazır!")
    app.run_polling()

if __name__ == '__main__':
    main()