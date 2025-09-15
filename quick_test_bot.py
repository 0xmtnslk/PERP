#!/usr/bin/env python3
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot başlatma komutu"""
    user = update.effective_user
    logger.info(f"Start from user {user.id}")
    
    keyboard = [
        [InlineKeyboardButton("🔧 API Ayarları", callback_data="api_setup")],
        [InlineKeyboardButton("💰 Miktar Ayarı", callback_data="amount_setup")],
        [InlineKeyboardButton("📈 Test Trading", callback_data="test_trade")]
    ]
    
    await update.message.reply_text(
        f"🚀 **Hızlı Test Bot**\n\n"
        f"Merhaba {user.first_name}!\n\n"
        f"Test için gerekli ayarları yapalım:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Button tıklamalarını işle"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    logger.info(f"Button clicked: {data} by user {user_id}")
    
    if data == "api_setup":
        await query.edit_message_text(
            "🔑 **API Kurulumu**\n\n"
            "Bitget API bilgilerinizi gönderin:\n"
            "Format: API_KEY,SECRET_KEY,PASSPHRASE\n\n"
            "Örnek: abc123,def456,mypass\n\n"
            "❌ İptal için /start",
            parse_mode='Markdown'
        )
        context.user_data['state'] = 'waiting_api'
        
    elif data == "amount_setup":
        keyboard = [
            [InlineKeyboardButton("💵 10 USDT", callback_data="amount_10")],
            [InlineKeyboardButton("💵 20 USDT", callback_data="amount_20")],
            [InlineKeyboardButton("💵 50 USDT", callback_data="amount_50")],
            [InlineKeyboardButton("🔙 Geri", callback_data="back")]
        ]
        
        await query.edit_message_text(
            "💰 **İşlem Miktarı Seçin:**",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    elif data.startswith("amount_"):
        amount = data.split("_")[1]
        # Amount'u environment variable olarak ayarla
        os.environ['BITGET_OPEN_USDT'] = amount
        
        await query.edit_message_text(
            f"✅ **Miktar Ayarlandı: {amount} USDT**\n\n"
            f"Artık test trading yapabilirsiniz!\n\n"
            f"🎯 Sonraki: Test Trading",
            parse_mode='Markdown'
        )
        
    elif data == "test_trade":
        await query.edit_message_text(
            "🧪 **Test Trading**\n\n"
            "Fake coin detection simülasyonu başlatılıyor...\n"
            "TESTCOIN olarak işlem açılacak!\n\n"
            "⏳ Lütfen bekleyin...",
            parse_mode='Markdown'
        )
        
        # Test coin detection trigger
        try:
            with open("PERP/new_coin_output.txt", "w") as f:
                f.write("TESTCOINUSDT_UMCBL")
            
            await query.message.reply_text(
                "✅ **Test Trigger Gönderildi!**\n\n"
                "TESTCOIN detection simülasyonu başlatıldı.\n"
                "Sistem şimdi otomatik işlem açmaya çalışacak.\n\n"
                "📱 Sonuçları konsol loglarından takip edin!",
                parse_mode='Markdown'
            )
        except Exception as e:
            await query.message.reply_text(f"❌ Test hatası: {e}")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Metin mesajlarını işle"""
    if context.user_data.get('state') == 'waiting_api':
        text = update.message.text
        
        if ',' in text and len(text.split(',')) == 3:
            api_key, secret_key, passphrase = text.split(',')
            
            # API credentials'ları environment'a kaydet
            os.environ['BITGET_API_KEY'] = api_key.strip()
            os.environ['BITGET_SECRET_KEY'] = secret_key.strip()
            os.environ['BITGET_PASSPHRASE'] = passphrase.strip()
            
            await update.message.reply_text(
                "✅ **API Bilgileri Kaydedildi!**\n\n"
                "Bitget API credentials başarıyla ayarlandı.\n"
                "Şimdi miktar ayarına geçebilirsiniz.\n\n"
                "🎯 Sonraki: /start → Miktar Ayarı",
                parse_mode='Markdown'
            )
            context.user_data['state'] = None
        else:
            await update.message.reply_text(
                "❌ **Hatalı Format!**\n\n"
                "Doğru format: API_KEY,SECRET_KEY,PASSPHRASE\n"
                "Virgül ile ayırarak gönderin."
            )

def main():
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN bulunamadı!")
        return
        
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("🚀 Hızlı Test Bot başlatılıyor...")
    print("🔧 API ayarları, miktar seçimi ve test trading aktif")
    
    application.run_polling()

if __name__ == '__main__':
    main()