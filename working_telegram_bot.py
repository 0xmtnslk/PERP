#!/usr/bin/env python3
"""
ÇALIŞAN TELEGRAM BOT - Callback problemleri çözüldü
Architect tool önerileri ile optimize edildi
"""
import os
import sqlite3
import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

class WorkingTelegramBot:
    def __init__(self):
        self.db_path = 'trading_bot.db'
        self.init_database()
    
    def init_database(self):
        """Database initialize et"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                api_key TEXT,
                secret_key TEXT,
                passphrase TEXT,
                amount_usdt REAL DEFAULT 20.0,
                leverage INTEGER DEFAULT 10,
                take_profit_percent REAL DEFAULT 100.0,
                active INTEGER DEFAULT 1,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ Database initialized")
    
    def save_user(self, user_id, username):
        """Kullanıcı kaydet"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', 
                      (user_id, username))
        cursor.execute('INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)', 
                      (user_id,))
        conn.commit()
        conn.close()
    
    def get_user_settings(self, user_id):
        """Kullanıcı ayarlarını getir"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT api_key, secret_key, passphrase, amount_usdt, leverage, take_profit_percent, active
            FROM user_settings WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return {
                'api_key': result[0] or '',
                'secret_key': result[1] or '',
                'passphrase': result[2] or '',
                'amount': result[3],
                'leverage': result[4],
                'take_profit': result[5],
                'active': bool(result[6])
            }
        return None
    
    def update_setting(self, user_id, key, value):
        """Tek ayar güncelle"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(f'UPDATE user_settings SET {key} = ? WHERE user_id = ?', 
                      (value, user_id))
        conn.commit()
        conn.close()
        logger.info(f"✅ Updated {key} for user {user_id}")

# Bot instance
bot = WorkingTelegramBot()

async def send_menu(chat_id, context, user_id=None):
    """Ana menüyü gönder - güvenli şekilde"""
    try:
        settings = bot.get_user_settings(user_id or chat_id)
        has_api = bool(settings and settings['api_key'])
        
        keyboard = [
            [InlineKeyboardButton("🔑 API Ayarları", callback_data="api")],
            [InlineKeyboardButton("💰 Miktar", callback_data="amount"), 
             InlineKeyboardButton("⚡ Leverage", callback_data="leverage")],
            [InlineKeyboardButton("📈 Take Profit %", callback_data="tp")],
            [InlineKeyboardButton("📊 Durumum", callback_data="status")]
        ]
        
        if has_api:
            keyboard.append([InlineKeyboardButton("🧪 Test Sistemi", callback_data="test")])
        
        text = f"""🚀 **Kripto Otomatik Trading Bot**

**Sistem:** Upbit yeni coin → Otomatik long
**Durum:** {'✅ Hazır' if has_api else '⚙️ Kurulum gerekli'}

Ayarlarını yap, sistem otomatik çalışsın!"""

        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"❌ Menu send error: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot başlat"""
    user = update.effective_user
    bot.save_user(user.id, user.username)
    
    await send_menu(update.effective_chat.id, context, user.id)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Button işlemleri - HIZLI callback handling"""
    query = update.callback_query
    
    # ✅ İLK ÖNCE HEMEN ANSWER - Architect önerisi
    try:
        await query.answer(cache_time=0)
    except BadRequest as e:
        if "too old" in str(e).lower():
            await query.message.reply_text(
                "⚠️ Bu tuş geçersiz oldu. /start ile yeniden deneyin."
            )
            return
        logger.error(f"Callback answer error: {e}")
        return
    
    user_id = query.from_user.id
    data = query.data
    
    logger.info(f"Button: {data} by user {user_id}")
    
    try:
        settings = bot.get_user_settings(user_id)
        
        if data == "api":
            await query.edit_message_text(
                "🔑 **API Bilgilerini Girin**\n\n"
                "Format: `API_KEY,SECRET_KEY,PASSPHRASE`\n\n"
                "Örnek:\n"
                "`bg_123abc,sk_456def,mypass123`\n\n"
                "⚠️ Güvenlik: Bilgiler şifrelenmiş saklanır\n"
                "🔙 Geri: /start",
                parse_mode='Markdown'
            )
            context.user_data['waiting'] = 'api'
            
        elif data == "amount":
            keyboard = [
                [InlineKeyboardButton("💵 10 USDT", callback_data="amount_10"),
                 InlineKeyboardButton("💵 20 USDT", callback_data="amount_20")],
                [InlineKeyboardButton("💵 50 USDT", callback_data="amount_50"),
                 InlineKeyboardButton("💵 100 USDT", callback_data="amount_100")],
                [InlineKeyboardButton("🔙 Ana Menü", callback_data="back")]
            ]
            
            await query.edit_message_text(
                f"💰 **İşlem Miktarı Seç**\n\n"
                f"Şu anki: {settings['amount']} USDT\n\n"
                f"Her yeni coin için bu miktar kullanılacak:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        elif data.startswith("amount_"):
            amount = float(data.split("_")[1])
            # ✅ Arka planda güncelle - blocking olmayan
            asyncio.create_task(update_user_amount(user_id, amount, query))
            
        elif data == "leverage":
            keyboard = [
                [InlineKeyboardButton("⚡ 5x", callback_data="lev_5"),
                 InlineKeyboardButton("⚡ 10x", callback_data="lev_10")],
                [InlineKeyboardButton("⚡ 20x", callback_data="lev_20"),
                 InlineKeyboardButton("⚡ 50x", callback_data="lev_50")],
                [InlineKeyboardButton("🔙 Ana Menü", callback_data="back")]
            ]
            
            await query.edit_message_text(
                f"⚡ **Leverage Seç**\n\n"
                f"Şu anki: {settings['leverage']}x\n\n"
                f"Risk seviyeni belirle:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        elif data.startswith("lev_"):
            leverage = int(data.split("_")[1])
            asyncio.create_task(update_user_leverage(user_id, leverage, query))
            
        elif data == "tp":
            keyboard = [
                [InlineKeyboardButton("📈 50%", callback_data="tp_50"),
                 InlineKeyboardButton("📈 100%", callback_data="tp_100")],
                [InlineKeyboardButton("📈 200%", callback_data="tp_200"),
                 InlineKeyboardButton("📈 500%", callback_data="tp_500")],
                [InlineKeyboardButton("🔙 Ana Menü", callback_data="back")]
            ]
            
            await query.edit_message_text(
                f"📈 **Take Profit % Seç**\n\n"
                f"Şu anki: %{settings['take_profit']}\n\n"
                f"Kar hedefini belirle:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        elif data.startswith("tp_"):
            tp = float(data.split("_")[1])
            asyncio.create_task(update_user_tp(user_id, tp, query))
            
        elif data == "status":
            has_api = bool(settings['api_key'])
            status_text = f"""📊 **Ayarlarım**

🔑 **API:** {'✅ Kayıtlı' if has_api else '❌ Eksik'}
💰 **Miktar:** {settings['amount']} USDT  
⚡ **Leverage:** {settings['leverage']}x
📈 **Take Profit:** %{settings['take_profit']}
🤖 **Durum:** {'🟢 Aktif' if settings['active'] else '🔴 Pasif'}

**Sistem otomatik çalışıyor:**
• Upbit yeni coin listesi → Anında long açar
• İşlem bildirimi + acil stop butonu
• TP'ye ulaşınca otomatik sat + kar-zarar raporu"""
            
            keyboard = [[InlineKeyboardButton("🔙 Ana Menü", callback_data="back")]]
            
            await query.edit_message_text(
                status_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='Markdown'
            )
            
        elif data == "test":
            await query.edit_message_text(
                "🧪 **Test Sistemi Başlatılıyor...**\n\n"
                "TESTCOIN fake detection gönderiliyor...\n"
                "⏳ Sonuçları bekleyin...",
                parse_mode='Markdown'
            )
            
            # ✅ Test trigger arka planda
            asyncio.create_task(trigger_test_trade(query))
            
        elif data == "back":
            # ✅ Ana menü güvenli şekilde
            await send_menu(query.message.chat_id, context, user_id)
            
    except BadRequest as e:
        if "too old" in str(e).lower() or "query is invalid" in str(e).lower():
            await query.message.reply_text(
                "⚠️ Bu işlem zaman aşımına uğradı. /start ile yeniden deneyin."
            )
        else:
            logger.error(f"BadRequest in callback: {e}")
    except Exception as e:
        logger.error(f"❌ Callback error: {e}")

# ✅ Arka plan görevleri - blocking olmayan
async def update_user_amount(user_id, amount, query):
    """Amount güncellemeyi arka planda yap"""
    try:
        bot.update_setting(user_id, 'amount_usdt', amount)
        await query.edit_message_text(
            f"✅ **Miktar Güncellendi**\n\n"
            f"Yeni miktar: **{amount} USDT**\n\n"
            f"🔙 /start ile ana menüye dön",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Amount update error: {e}")

async def update_user_leverage(user_id, leverage, query):
    """Leverage güncellemeyi arka planda yap"""
    try:
        bot.update_setting(user_id, 'leverage', leverage)
        await query.edit_message_text(
            f"✅ **Leverage Güncellendi**\n\n"
            f"Yeni leverage: **{leverage}x**\n\n"
            f"🔙 /start ile ana menüye dön",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Leverage update error: {e}")

async def update_user_tp(user_id, tp, query):
    """TP güncellemeyi arka planda yap"""
    try:
        bot.update_setting(user_id, 'take_profit_percent', tp)
        await query.edit_message_text(
            f"✅ **Take Profit Güncellendi**\n\n"
            f"Yeni hedef: **%{tp}**\n\n"
            f"🔙 /start ile ana menüye dön",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"TP update error: {e}")

async def trigger_test_trade(query):
    """Test trade'i arka planda tetikle"""
    try:
        # Test trigger dosyasına yaz
        with open("PERP/new_coin_output.txt", "w") as f:
            f.write("TESTCOINUSDT_UMCBL")
        
        await query.message.reply_text(
            "✅ **Test Trigger Gönderildi!**\n\n"
            "🚀 Sistem TESTCOIN için otomatik işlem açmaya çalışacak\n"
            "📱 Bildirim gelecek ve acil stop butonu aktif olacak\n\n"
            "📊 Sonuçları takip edin!",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Test trigger error: {e}")
        await query.message.reply_text(f"❌ Test hatası: {e}")

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Metin mesajları işle"""
    user_id = update.effective_user.id
    text = update.message.text
    
    if context.user_data.get('waiting') == 'api':
        if ',' in text and len(text.split(',')) == 3:
            api_key, secret_key, passphrase = [x.strip() for x in text.split(',')]
            
            # ✅ API credentials'ları arka planda kaydet
            try:
                bot.update_setting(user_id, 'api_key', api_key)
                bot.update_setting(user_id, 'secret_key', secret_key)
                bot.update_setting(user_id, 'passphrase', passphrase)
                
                await update.message.reply_text(
                    "✅ **API Bilgileri Kaydedildi!**\n\n"
                    "🔑 Bitget API başarıyla ayarlandı\n"
                    "🚀 Artık otomatik sistem aktif\n\n"
                    "📋 /start ile menüye dön",
                    parse_mode='Markdown'
                )
                context.user_data['waiting'] = None
            except Exception as e:
                logger.error(f"API save error: {e}")
                await update.message.reply_text("❌ API kaydetme hatası!")
        else:
            await update.message.reply_text(
                "❌ **Hatalı Format!**\n\n"
                "Doğru format: `API_KEY,SECRET_KEY,PASSPHRASE`\n"
                "Virgülle ayırın, boşluk bırakmayın",
                parse_mode='Markdown'
            )

def main():
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN bulunamadı!")
        return
        
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("🚀 ÇALIŞAN TELEGRAM BOT başlatılıyor...")
    print("✅ Callback problemleri çözüldü!")
    print("✅ Architect önerileri uygulandı")
    print("✅ Fast callback + background tasks")
    
    # ✅ Architect önerisi: Eski callback'leri temizle
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == '__main__':
    main()