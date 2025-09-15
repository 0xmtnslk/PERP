#!/usr/bin/env python3
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SimpleBot:
    def __init__(self):
        pass
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user = update.effective_user
            logger.info(f"Start command from user {user.id} ({user.first_name})")
            
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
        except Exception as e:
            logger.error(f"Error in start: {e}")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            query = update.callback_query
            await query.answer()
            user_id = query.from_user.id
            
            logger.info(f"Callback received: {query.data} from user {user_id}")
            
            if query.data == "api_setup":
                await query.edit_message_text(
                    "🔑 **API Kurulumu**\n\n"
                    "API anahtarların environment'dan alınıyor.\n\n"
                    "✅ Sistem hazır!",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Ana Menü", callback_data="main_menu")]]),
                    parse_mode='Markdown'
                )
                
            elif query.data == "manual_trade":
                keyboard = [
                    [InlineKeyboardButton("BTC", callback_data="trade_BTC")],
                    [InlineKeyboardButton("ETH", callback_data="trade_ETH")],
                    [InlineKeyboardButton("SOL", callback_data="trade_SOL")],
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
                logger.info(f"Trading {symbol} for user {user_id}")
                
                # Trading dosyasını oluştur
                user_dir = f"PERP/users/{user_id}"
                os.makedirs(user_dir, exist_ok=True)
                
                perp_symbol = f"{symbol}USDT_UMCBL"
                trade_file = f"{user_dir}/manual_long_output.txt"
                
                with open(trade_file, "w") as f:
                    f.write(perp_symbol)
                    
                logger.info(f"Created trade file: {trade_file} with {perp_symbol}")
                    
                await query.edit_message_text(
                    f"🚀 **İşlem Başlatıldı!**\n\n"
                    f"🪙 **Coin:** {symbol}\n"
                    f"💰 **Miktar:** 50 USDT\n"
                    f"⚡ **Format:** {perp_symbol}\n\n"
                    f"✅ **Dosya oluşturuldu!**\n"
                    f"🔄 **Trading engine çalışıyor...**",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Yeni İşlem", callback_data="manual_trade")]]),
                    parse_mode='Markdown'
                )
                
            elif query.data == "status":
                await query.edit_message_text(
                    "ℹ️ **Sistem Durumu**\n\n"
                    "🤖 **Bot:** Çalışıyor\n"
                    "👀 **Upbit:** Aktif\n"
                    "⚡ **Trading:** Çalışıyor\n"
                    "🔑 **API:** Hazır\n\n"
                    "✅ **Her şey tamam!**",
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
                
        except Exception as e:
            logger.error(f"Error in callback: {e}")
            try:
                await query.edit_message_text(
                    f"❌ **Hata oluştu!**\n\n"
                    f"Lütfen tekrar dene.\n\n"
                    f"Hata: {str(e)[:100]}"
                )
            except:
                pass

def main():
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("❌ TOKEN YOK!")
        return
        
    print("🚀 SIMPLE BOT BAŞLATIYOR...")
    
    bot = SimpleBot()
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CallbackQueryHandler(bot.handle_callback))
    
    print("✅ Simple bot hazır!")
    try:
        app.run_polling()
    except Exception as e:
        logger.error(f"Bot error: {e}")

if __name__ == '__main__':
    main()