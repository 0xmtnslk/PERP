#!/usr/bin/env python3
import os
import subprocess
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DirectTradingBot:
    def __init__(self):
        self.user_states = {}  # State management for text input
        
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
            # Create symbol file for PERP/long.py - force clean write
            symbol_file = "PERP/new_coin_output.txt"
            symbol_content = f"{symbol}USDT_UMCBL"
            
            # Dosyayı sil ve yeniden oluştur (cache problemini önlemek için)
            if os.path.exists(symbol_file):
                os.remove(symbol_file)
            
            with open(symbol_file, "w") as f:
                f.write(symbol_content)
                f.flush()  # Buffer'ı zorla boşalt
                os.fsync(f.fileno())  # Disk'e zorla yaz
                
            # Doğrula
            with open(symbol_file, "r") as f:
                written_content = f.read().strip()
                
            logger.info(f"Created symbol file: {symbol_file} with {symbol_content}")
            logger.info(f"Verified content: {written_content}")
            
            if written_content != symbol_content:
                logger.error(f"File write mismatch! Expected: {symbol_content}, Got: {written_content}")
                return False, "", f"Dosya yazma hatası: {symbol_content} beklendi, {written_content} bulundu"
            
            # Execute the trading script directly with environment variable
            env = os.environ.copy()
            env['BITGET_OPEN_USDT'] = '1'  # 1 USDT test - daha düşük
            
            result = subprocess.run([
                "python3", "PERP/long.py"
            ], capture_output=True, text=True, timeout=60, env=env)
            
            logger.info(f"Trading script result: {result.returncode}")
            logger.info(f"Trading script stdout: {result.stdout}")
            if result.stderr:
                logger.error(f"Trading script stderr: {result.stderr}")
            
            # Detaylı hata mesajı döndür
            if result.returncode == 0:
                return True, result.stdout, result.stderr
            else:
                # stdout'dan hatayı çıkar
                error_msg = "Bilinmeyen hata"
                if result.stdout and "❌ İşlem hatası:" in result.stdout:
                    lines = result.stdout.split('\n')
                    for line in lines:
                        if "❌ İşlem hatası:" in line:
                            error_msg = line.replace("❌ İşlem hatası:", "").strip()
                            break
                elif result.stderr:
                    error_msg = result.stderr[:200]
                elif result.stdout:
                    error_msg = result.stdout[-200:]  # Son 200 karakter
                    
                return False, result.stdout, error_msg
            
        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            return False, "", str(e)
    
    def close_all_positions(self):
        """Close all positions using PERP/long.py close function"""
        try:
            import subprocess
            import os
            
            # Create a simple Python script to call close_all_positions
            close_script = """
import sys
sys.path.append('PERP')
from long import close_all_positions, load_api_credentials

# Load credentials
credentials = load_api_credentials()
api_key = credentials.get("api_key")
secret_key = credentials.get("secret_key")
passphrase = credentials.get("passphrase")

if api_key and secret_key and passphrase:
    print("🔴 Tüm pozisyonlar kapatılıyor...")
    close_all_positions(api_key, secret_key, passphrase)
    print("✅ Pozisyonlar kapatıldı!")
else:
    print("❌ API anahtarları bulunamadı!")
"""
            
            # Run the close script
            result = subprocess.run([
                "python3", "-c", close_script
            ], capture_output=True, text=True, timeout=30)
            
            logger.info(f"Close positions result: {result.returncode}")
            logger.info(f"Close positions stdout: {result.stdout}")
            
            return result.returncode == 0, result.stdout, result.stderr
            
        except Exception as e:
            logger.error(f"Close positions error: {e}")
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
                    [InlineKeyboardButton("BTC", callback_data="trade_BTC"), InlineKeyboardButton("ETH", callback_data="trade_ETH")],
                    [InlineKeyboardButton("SOL", callback_data="trade_SOL"), InlineKeyboardButton("ADA", callback_data="trade_ADA")],
                    [InlineKeyboardButton("✏️ Özel Symbol", callback_data="custom_symbol")],
                    [InlineKeyboardButton("◀️ Ana Menü", callback_data="main_menu")]
                ]
                await query.edit_message_text(
                    "📊 Manuel Trading\n\n"
                    "Hangi coin'i alacaksın?\n"
                    "(Doğrudan Bitget'te işlem açılacak)",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                
            elif query.data == "custom_symbol":
                self.user_states[user_id] = "waiting_custom_symbol"
                await query.edit_message_text(
                    "✏️ **Özel Symbol Girişi**\n\n"
                    "Hangi coin'i almak istiyorsun?\n"
                    "Sadece symbol'ü yaz (örnek: DOGE, MATIC, AVAX)\n\n"
                    "⚠️ Symbol'ün Bitget'te olduğundan emin ol!",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ İptal", callback_data="manual_trade")]])
                )
                
            elif query.data.startswith("trade_"):
                symbol = query.data.replace("trade_", "")
                logger.info(f"Executing trade: {symbol} for user {user_id}")
                
                await query.edit_message_text(
                    f"⏳ İşlem başlatılıyor...\n\n"
                    f"🪙 Coin: {symbol}\n"
                    f"💰 Miktar: 1 USDT (Test)\n"
                    f"🔄 Bitget API'ye gönderiliyor...",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Yeni İşlem", callback_data="manual_trade")]])
                )
                
                # Execute trade directly
                success, stdout, stderr = self.execute_trade(symbol)
                
                if success:
                    # Başarılı işlem sonrası pozisyon kapatma butonu ekle
                    keyboard = [
                        [InlineKeyboardButton("🔴 Pozisyonu Kapat", callback_data="close_positions")],
                        [InlineKeyboardButton("🔄 Yeni İşlem", callback_data="manual_trade")],
                        [InlineKeyboardButton("◀️ Ana Menü", callback_data="main_menu")]
                    ]
                    await query.edit_message_text(
                        f"🎉 İşlem Başarılı!\n\n"
                        f"🪙 Coin: {symbol}\n"
                        f"💰 Miktar: 1 USDT\n"
                        f"✅ Bitget'te açıldı\n"
                        f"📊 Sonuç: İşlem tamamlandı\n\n"
                        f"🔴 Pozisyonu kapatmak için butona bas\n"
                        f"Detaylar: {stdout[:100]}...",
                        reply_markup=InlineKeyboardMarkup(keyboard)
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
                
            elif query.data == "close_positions":
                await query.edit_message_text(
                    "🔴 **Pozisyon Kapatılıyor...**\n\n"
                    "Tüm açık pozisyonlar kapatılıyor...\n"
                    "Lütfen bekle...",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Ana Menü", callback_data="main_menu")]])
                )
                
                # Close all positions
                success, stdout, stderr = self.close_all_positions()
                
                if success:
                    await query.edit_message_text(
                        f"✅ **Pozisyonlar Kapatıldı!**\n\n"
                        f"🔴 Tüm açık pozisyonlar kapatıldı\n"
                        f"💰 Kar/zarar hesaplandı\n\n"
                        f"Detaylar: {stdout[:100] if stdout else 'İşlem tamamlandı'}",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Yeni İşlem", callback_data="manual_trade")]])
                    )
                else:
                    await query.edit_message_text(
                        f"❌ **Kapatma Hatası!**\n\n"
                        f"Hata: {stderr[:100] if stderr else 'Bilinmeyen hata'}\n\n"
                        f"Lütfen manuel olarak kontrol et",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Tekrar Dene", callback_data="close_positions")]])
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
    
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text input for custom symbol"""
        user_id = update.effective_user.id
        text = update.message.text.strip().upper()
        
        if user_id not in self.user_states:
            return
            
        state = self.user_states[user_id]
        
        if state == "waiting_custom_symbol":
            # Validate symbol format
            if len(text) > 1 and text.isalpha() and len(text) <= 10:
                # Remove user from state
                self.user_states.pop(user_id, None)
                
                await update.message.reply_text(
                    f"⏳ İşlem başlatılıyor...\n\n"
                    f"🪙 Coin: {text}\n"
                    f"💰 Miktar: 1 USDT (Test)\n"
                    f"🔄 Bitget API'ye gönderiliyor..."
                )
                
                # Execute trade with custom symbol
                success, stdout, stderr = self.execute_trade(text)
                
                if success:
                    keyboard = [
                        [InlineKeyboardButton("🔴 Pozisyonu Kapat", callback_data="close_positions")],
                        [InlineKeyboardButton("🔄 Yeni İşlem", callback_data="manual_trade")],
                        [InlineKeyboardButton("◀️ Ana Menü", callback_data="main_menu")]
                    ]
                    await update.message.reply_text(
                        f"🎉 İşlem Başarılı!\n\n"
                        f"🪙 Coin: {text}\n"
                        f"💰 Miktar: 1 USDT\n"
                        f"✅ Bitget'te açıldı\n"
                        f"📊 Sonuç: İşlem tamamlandı\n\n"
                        f"🔴 Pozisyonu kapatmak için butona bas\n"
                        f"Detaylar: {stdout[:100]}...",
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                else:
                    error_msg = stderr if stderr else "Bilinmeyen hata"
                    await update.message.reply_text(
                        f"❌ İşlem Hatası!\n\n"
                        f"🪙 Coin: {text}\n"
                        f"Hata: {error_msg[:200]}\n\n"
                        f"⚠️ Symbol doğru mu? Bitget'te var mı?",
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Tekrar Dene", callback_data="custom_symbol")]])
                    )
            else:
                await update.message.reply_text(
                    "❌ Geçersiz symbol!\n\n"
                    "Lütfen sadece harf kullan (2-10 karakter)\n"
                    "Örnek: DOGE, MATIC, AVAX",
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ İptal", callback_data="manual_trade")]])
                )

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
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    
    print("✅ Direct bot hazır!")
    try:
        app.run_polling()
    except Exception as e:
        logger.error(f"Bot error: {e}")

if __name__ == '__main__':
    main()