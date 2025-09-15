#!/usr/bin/env python3
import os
import subprocess
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DirectTradingBot:
    def __init__(self):
        pass
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            user = update.effective_user
            logger.info(f"Start command from user {user.id} ({user.first_name})")
            
            keyboard = [
                [InlineKeyboardButton("🔑 API Durumu", callback_data="api_status")],
                [InlineKeyboardButton("📊 Manuel Trading", callback_data="manual_trade")],
                [InlineKeyboardButton("ℹ️ Sistem Durumu", callback_data="status")]
            ]
            
            await update.message.reply_text(
                f"🚀 Kripto Trading Bot\n\n"
                f"Hoş geldin {user.first_name}!\n\n"
                f"Doğrudan Bitget API ile çalışıyor",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            logger.error(f"Error in start: {e}")
    
    def execute_trade(self, symbol):
        """Execute trade directly using PERP/long.py with environment variables"""
        try:
            # Create symbol file for PERP/long.py  
            symbol_file = "PERP/new_coin_output.txt"
            with open(symbol_file, "w") as f:
                f.write(f"{symbol}USDT_UMCBL")
                
            logger.info(f"Created symbol file: {symbol_file} with {symbol}USDT_UMCBL")
            
            # Execute the trading script directly
            result = subprocess.run([
                "python3", "PERP/long.py"
            ], capture_output=True, text=True, timeout=60)
            
            logger.info(f"Trading script result: {result.returncode}")
            logger.info(f"Trading script stdout: {result.stdout}")
            if result.stderr:
                logger.error(f"Trading script stderr: {result.stderr}")
                
            return result.returncode == 0, result.stdout, result.stderr
            
        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            return False, "", str(e)
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            query = update.callback_query
            await query.answer()
            user_id = query.from_user.id
            
            logger.info(f"Callback received: {query.data} from user {user_id}")
            
            if query.data == "api_status":
                # Check environment variables
                api_key = os.getenv('BITGET_API_KEY', '')[:10] + "..." if os.getenv('BITGET_API_KEY') else "❌ Yok"
                secret_key = "✅ Var" if os.getenv('BITGET_SECRET_KEY') else "❌ Yok"  
                passphrase = "✅ Var" if os.getenv('BITGET_PASSPHRASE') else "❌ Yok"
                
                await query.edit_message_text(
                    f"🔑 API Durumu\n\n"
                    f"API Key: {api_key}\n"
                    f"Secret Key: {secret_key}\n"
                    f"Passphrase: {passphrase}\n\n"
                    f"Environment Variable'lardan alınıyor",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Ana Menü", callback_data="main_menu")]])
                )
                
            elif query.data == "manual_trade":
                keyboard = [
                    [InlineKeyboardButton("BTC", callback_data="trade_BTC")],
                    [InlineKeyboardButton("ETH", callback_data="trade_ETH")],
                    [InlineKeyboardButton("SOL", callback_data="trade_SOL")],
                    [InlineKeyboardButton("◀️ Ana Menü", callback_data="main_menu")]
                ]
                await query.edit_message_text(
                    "📊 Manuel Trading\n\n"
                    "Hangi coin'i alacaksın?\n"
                    "(Doğrudan Bitget'te işlem açılacak)",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
            elif query.data.startswith("trade_"):
                symbol = query.data.replace("trade_", "")
                logger.info(f"Executing trade: {symbol} for user {user_id}")
                
                await query.edit_message_text(
                    f"⏳ İşlem başlatılıyor...\n\n"
                    f"🪙 Coin: {symbol}\n"
                    f"💰 Miktar: 5 USDT (Test)\n"
                    f"🔄 Bitget API'ye gönderiliyor...",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Yeni İşlem", callback_data="manual_trade")]])
                )
                
                # Execute trade directly
                success, stdout, stderr = self.execute_trade(symbol)
                
                if success:
                    await query.edit_message_text(
                        f"🎉 İşlem Başarılı!\n\n"
                        f"🪙 Coin: {symbol}\n"
                        f"💰 Miktar: 5 USDT\n"
                        f"✅ Bitget'te açıldı\n"
                        f"📊 Sonuç: İşlem tamamlandı\n\n"
                        f"Detaylar: {stdout[:100]}...",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Yeni İşlem", callback_data="manual_trade")]])
                    )
                else:
                    await query.edit_message_text(
                        f"❌ İşlem Hatası!\n\n"
                        f"🪙 Coin: {symbol}\n"
                        f"Hata: {stderr[:100] if stderr else 'Bilinmeyen hata'}\n\n"
                        f"Lütfen API anahtarlarını kontrol et",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Tekrar Dene", callback_data="manual_trade")]])
                    )
                
            elif query.data == "status":
                await query.edit_message_text(
                    "ℹ️ Sistem Durumu\n\n"
                    "🤖 Bot: Çalışıyor\n"
                    "👀 Upbit: Aktif\n"
                    "⚡ Trading: PERP/long.py\n"
                    "🔑 API: Environment\n\n"
                    "✅ Doğrudan işlem sistemi!",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Ana Menü", callback_data="main_menu")]])
                )
                
            elif query.data == "main_menu":
                keyboard = [
                    [InlineKeyboardButton("🔑 API Durumu", callback_data="api_status")],
                    [InlineKeyboardButton("📊 Manuel Trading", callback_data="manual_trade")],
                    [InlineKeyboardButton("ℹ️ Sistem Durumu", callback_data="status")]
                ]
                
                await query.edit_message_text(
                    f"🚀 Kripto Trading Bot\n\n"
                    f"Ana Menü\n\n"
                    f"Doğrudan Bitget API ile çalışıyor",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
        except Exception as e:
            logger.error(f"Error in callback: {e}")
            try:
                await query.edit_message_text(
                    f"❌ Hata oluştu!\n\n"
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
        
    print("🚀 DIRECT TRADING BOT BAŞLATIYOR...")
    
    bot = DirectTradingBot()
    app = Application.builder().token(token).build()
    
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CallbackQueryHandler(bot.handle_callback))
    
    print("✅ Direct bot hazır!")
    try:
        app.run_polling()
    except Exception as e:
        logger.error(f"Bot error: {e}")

if __name__ == '__main__':
    main()