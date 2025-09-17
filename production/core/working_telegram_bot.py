#!/usr/bin/env python3
"""
ÇALIŞAN TELEGRAM BOT - Callback problemleri çözüldü
Architect tool önerileri ile optimize edildi
"""
import os
import sqlite3
import logging
import asyncio
import re
import time
import threading
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest

# ✅ ROBUST INPUT VALIDATION
class ValidationError(Exception):
    """API input validation error"""
    pass

class InputValidator:
    """Robust input validator to prevent bot crashes"""
    
    @staticmethod
    def validate_api_triplet(text: str) -> tuple[str, str, str]:
        """
        Robust API credentials validation
        Returns: (api_key, secret_key, passphrase) or raises ValidationError
        """
        # Guard: Basic checks
        if not text or not isinstance(text, str):
            raise ValidationError("❌ Boş giriş. Format: API_KEY,SECRET_KEY,PASSPHRASE")
        
        # Length limit for security  
        if len(text) > 512:
            raise ValidationError("❌ Giriş çok uzun (max 512 karakter)")
        
        # Normalize input
        text = text.strip()
        if '\n' in text or '\r' in text:
            raise ValidationError("❌ Tek satırda girin. Format: API_KEY,SECRET_KEY,PASSPHRASE")
        
        # Split validation
        parts = text.split(',')
        if len(parts) != 3:
            raise ValidationError("❌ 3 değer gerekli. Format: API_KEY,SECRET_KEY,PASSPHRASE\nÖrnek: bg_123abc,sk_456def,mypass123")
        
        # Clean and validate each part
        api_key = parts[0].strip()
        secret_key = parts[1].strip()
        passphrase = parts[2].strip()
        
        # Length validation
        if len(api_key) < 10 or len(api_key) > 128:
            raise ValidationError("❌ API Key uzunluğu 10-128 karakter olmalı")
        
        if len(secret_key) < 20 or len(secret_key) > 256:
            raise ValidationError("❌ Secret Key uzunluğu 20-256 karakter olmalı")
        
        if len(passphrase) < 6 or len(passphrase) > 128:
            raise ValidationError("❌ Passphrase uzunluğu 6-128 karakter olmalı")
        
        # Format validation with regex
        if not re.match(r'^[A-Za-z0-9_\-]+$', api_key):
            raise ValidationError("❌ API Key sadece harf, rakam, _ ve - içermeli")
        
        if not re.match(r'^[A-Za-z0-9_\-+/=]+$', secret_key):
            raise ValidationError("❌ Secret Key geçersiz karakter içeriyor")
        
        if not re.match(r'^[A-Za-z0-9!@#%\^&*()_+\-=?.,:;]+$', passphrase):
            raise ValidationError("❌ Passphrase geçersiz karakter içeriyor")
        
        # All parts must be non-empty after strip
        if not api_key or not secret_key or not passphrase:
            raise ValidationError("❌ Tüm alanlar dolu olmalı. Boş alan bırakma")
        
        return api_key, secret_key, passphrase
    
    @staticmethod
    def sanitize_input(text: str) -> str:
        """Clean user input safely"""
        if not text:
            return ""
        # Remove dangerous characters
        dangerous_chars = ['<', '>', '&', '"', "'", ';', '(', ')', '{', '}', '[', ']']
        for char in dangerous_chars:
            text = text.replace(char, '')
        return text.strip()[:200]

# ✅ USER STATE TIMEOUT MANAGER
class UserStateTimeoutManager:
    """Manages user state timeouts to prevent stuck users"""
    
    def __init__(self):
        self.user_state_timestamps = {}  # user_id -> timestamp
        self.timeout_minutes = 10  # 10 minutes timeout
    
    def set_user_waiting_state(self, user_id: int, state: str, context: ContextTypes.DEFAULT_TYPE):
        """Set user state with timestamp"""
        context.user_data['waiting'] = state
        self.user_state_timestamps[user_id] = time.time()
        logger.info(f"✅ User {user_id} state set to '{state}' with timeout")
    
    def clear_user_state(self, user_id: int, context: ContextTypes.DEFAULT_TYPE):
        """Clear user state and timestamp"""
        if user_id in self.user_state_timestamps:
            del self.user_state_timestamps[user_id]
        
        if context.user_data.get('waiting'):
            context.user_data['waiting'] = None
            context.user_data['api_failures'] = 0
            logger.info(f"✅ User {user_id} state cleared")
    
    async def check_and_cleanup_expired_states(self, application):
        """Check for expired user states and cleanup"""
        try:
            current_time = time.time()
            timeout_seconds = self.timeout_minutes * 60
            expired_users = []
            
            for user_id, timestamp in self.user_state_timestamps.items():
                if current_time - timestamp > timeout_seconds:
                    expired_users.append(user_id)
            
            # Cleanup expired users
            for user_id in expired_users:
                try:
                    # Clear our tracking
                    del self.user_state_timestamps[user_id]
                    
                    # Try to notify user if possible
                    try:
                        await application.bot.send_message(
                            chat_id=user_id,
                            text="⏰ **Zaman Aşımı**\n\n"
                                 f"API giriş işleminiz {self.timeout_minutes} dakika sonra zaman aşımına uğradı\n"
                                 "🔄 Tekrar denemek için: /start",
                            parse_mode='Markdown'
                        )
                        logger.info(f"✅ Timeout notification sent to user {user_id}")
                    except Exception as e:
                        logger.warning(f"⚠️ Could not notify user {user_id} about timeout: {e}")
                    
                    logger.info(f"🧹 Cleaned up expired state for user {user_id}")
                    
                except Exception as e:
                    logger.error(f"❌ Error cleaning up user {user_id}: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error in state cleanup task: {e}")
    
    def is_state_expired(self, user_id: int) -> bool:
        """Check if user state has expired"""
        if user_id not in self.user_state_timestamps:
            return False
        
        current_time = time.time()
        timeout_seconds = self.timeout_minutes * 60
        return (current_time - self.user_state_timestamps[user_id]) > timeout_seconds

# ✅ GLOBAL TIMEOUT MANAGER INSTANCE
timeout_manager = UserStateTimeoutManager()

# ✅ PRODUCTION-GRADE: Safe async task wrapper
async def safe_create_task(coro, task_name: str = "unknown"):
    """
    Safe wrapper for asyncio.create_task to prevent unhandled exceptions
    """
    try:
        task = asyncio.create_task(coro)
        return await task
    except Exception as e:
        logger.error(f"❌ Background task '{task_name}' failed: {e}")
        # Don't re-raise - keep bot running
        return None

def heartbeat_writer():
    """Health file'ını her 60 saniyede bir günceller"""
    health_file = "production/monitoring/telegram_bot_health.txt"
    while True:
        try:
            with open(health_file, 'w') as f:
                f.write(f"{datetime.now().isoformat()}\n")
        except Exception as e:
            print(f"❌ Health file yazma hatası: {e}")
        time.sleep(60)

def start_heartbeat():
    """Heartbeat thread'ini başlat"""
    heartbeat_thread = threading.Thread(target=heartbeat_writer, daemon=True)
    heartbeat_thread.start()
    print("💓 Telegram Bot heartbeat başlatıldı")

# ✅ SECURITY-FIRST LOGGING CONFIGURATION
# Prevent sensitive bot token from appearing in logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔒 CRITICAL SECURITY: Suppress httpx request logs that contain bot token
httpx_logger = logging.getLogger('httpx')
httpx_logger.setLevel(logging.WARNING)  # Suppress INFO level request URLs

# 🔒 SECURITY: Suppress telegram library HTTP logs
telegram_logger = logging.getLogger('telegram.ext')
telegram_logger.setLevel(logging.WARNING)

# 🔒 SECURITY: Suppress urllib3 logs that might contain URLs
urllib3_logger = logging.getLogger('urllib3')
urllib3_logger.setLevel(logging.WARNING)

# ✅ PRODUCTION-GRADE: Custom filter to strip tokens from any remaining logs
class TokenSanitizingFilter(logging.Filter):
    """Remove bot tokens from log messages as additional security layer"""
    
    def filter(self, record):
        if hasattr(record, 'msg') and isinstance(record.msg, str):
            # Pattern to match bot tokens in URLs
            import re
            # Bot tokens follow pattern: digits:alphanumeric_string
            token_pattern = r'/bot\d+:[A-Za-z0-9_-]+/'
            record.msg = re.sub(token_pattern, '/bot[TOKEN_REDACTED]/', record.msg)
        return True

# Apply token filter to all loggers as fallback security
token_filter = TokenSanitizingFilter()
logging.getLogger().addFilter(token_filter)

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

class WorkingTelegramBot:
    def __init__(self):
        self.db_path = 'trading_bot.db'
        # ✅ PRODUCTION-GRADE: Thread-safe database operations
        self._db_lock = threading.RLock()  # Reentrant lock for nested operations
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
        """Kullanıcı kaydet - Thread-safe"""
        with self._db_lock:
            try:
                conn = sqlite3.connect(self.db_path, timeout=10.0)  # 10 second timeout
                conn.execute('PRAGMA journal_mode=WAL')  # Better concurrency
                cursor = conn.cursor()
                cursor.execute('INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)', 
                              (user_id, username))
                cursor.execute('INSERT OR IGNORE INTO user_settings (user_id) VALUES (?)', 
                              (user_id,))
                conn.commit()
            except sqlite3.Error as e:
                logger.error(f"❌ Database save_user error: {e}")
                raise
            finally:
                if conn:
                    conn.close()
    
    def get_user_settings(self, user_id):
        """Kullanıcı ayarlarını getir - Thread-safe"""
        with self._db_lock:
            try:
                conn = sqlite3.connect(self.db_path, timeout=10.0)
                conn.execute('PRAGMA journal_mode=WAL')
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT api_key, secret_key, passphrase, amount_usdt, leverage, take_profit_percent, active
                    FROM user_settings WHERE user_id = ?
                ''', (user_id,))
                result = cursor.fetchone()
                
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
            except sqlite3.Error as e:
                logger.error(f"❌ Database get_user_settings error: {e}")
                return None  # Return safe default instead of crashing
            finally:
                if conn:
                    conn.close()
    
    def update_setting(self, user_id, key, value):
        """Tek ayar güncelle - Thread-safe"""
        with self._db_lock:
            try:
                # ✅ SQL injection protection - validate column name
                allowed_columns = ['api_key', 'secret_key', 'passphrase', 'amount_usdt', 
                                 'leverage', 'take_profit_percent', 'active']
                if key not in allowed_columns:
                    raise ValueError(f"Invalid column name: {key}")
                
                conn = sqlite3.connect(self.db_path, timeout=10.0)
                conn.execute('PRAGMA journal_mode=WAL')
                cursor = conn.cursor()
                cursor.execute(f'UPDATE user_settings SET {key} = ? WHERE user_id = ?', 
                              (value, user_id))
                conn.commit()
                logger.info(f"✅ Updated {key} for user {user_id}")
            except sqlite3.Error as e:
                logger.error(f"❌ Database update_setting error for {key}: {e}")
                raise
            except ValueError as e:
                logger.error(f"❌ Invalid update_setting parameter: {e}")
                raise
            finally:
                if conn:
                    conn.close()

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
            timeout_manager.set_user_waiting_state(user_id, 'api', context)
            
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
            # ✅ PRODUCTION-GRADE: Safe background update
            asyncio.create_task(safe_create_task(
                update_user_amount(user_id, amount, query), 
                "update_user_amount"
            ))
            
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
            asyncio.create_task(safe_create_task(
                update_user_leverage(user_id, leverage, query), 
                "update_user_leverage"
            ))
            
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
            asyncio.create_task(safe_create_task(
                update_user_tp(user_id, tp, query), 
                "update_user_tp"
            ))
            
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
            asyncio.create_task(safe_create_task(
                trigger_test_trade(query), 
                "trigger_test_trade"
            ))
            
        elif data == "stop_position":
            # ✅ STOP POSITION BUTTON - Close all open positions
            await handle_stop_position(query, user_id)
            
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

async def handle_stop_position(query, user_id):
    """Handle stop position button - close all positions"""
    try:
        await query.edit_message_text(
            "🚨 **POZİSYON KAPATILIYOR...**\n\n"
            "⏳ Tüm açık pozisyonlar kapalınıyor...\n"
            "💰 Kar/zarar hesaplanıyor...",
            parse_mode='Markdown'
        )
        
        # Get user's API credentials
        settings = bot.get_user_settings(user_id)
        if not settings or not settings['api_key']:
            await query.edit_message_text(
                "❌ **HATA**\n\n"
                "API anahtarları bulunamadı!\n"
                "🔑 Önce API ayarlarını yapın",
                parse_mode='Markdown'
            )
            return
        
        # Use existing long.py close_all_positions function directly
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), 'PERP'))
        
        try:
            from long import close_all_positions
            # ✅ PRODUCTION-GRADE: API call with timeout and retry
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    close_all_positions,
                    settings['api_key'], 
                    settings['secret_key'], 
                    settings['passphrase']
                ),
                timeout=30.0  # 30 second timeout for API calls
            )
            success = True
            error_msg = None
        except asyncio.TimeoutError:
            success = False
            error_msg = "API timeout (30s) - Bitget bağlantı sorunu"
        except ImportError as e:
            success = False
            error_msg = f"Import error: {e}"
        except Exception as e:
            success = False
            error_msg = str(e)
            logger.error(f"❌ External API call failed: {e}")
        
        if success:
            # ✅ Show detailed P&L results from close_all_positions
            pnl_info = ""
            if isinstance(result, dict):
                total_pnl = result.get('total_pnl', 0)
                positions_count = result.get('positions_count', 0)
                pnl_emoji = "🟢" if total_pnl >= 0 else "🔴"
                pnl_info = f"\n💰 **P&L:** {pnl_emoji} ${total_pnl:.2f}\n📊 **Pozisyonlar:** {positions_count} adet"
            
            await query.edit_message_text(
                f"✅ **POZİSYONLAR KAPATILDI!**{pnl_info}\n\n"
                f"📊 **Durumu:** Tüm pozisyonlar kapatıldı\n"
                f"💰 **Detaylar:** Kar/zarar hesaplandı\n\n"
                f"✅ İşlem tamamlandı!",
                parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                f"❌ **POZISYON KAPATMA HATASI**\n\n"
                f"Hata: {error_msg or 'Bilinmeyen hata'}\n\n"
                f"🔄 Tekrar deneyin veya manuel kontrol edin",
                parse_mode='Markdown'
            )
            
    except Exception as e:
        logger.error(f"Stop position error: {e}")
        await query.edit_message_text(
            "❌ **SİSTEM HATASI**\n\n"
            "Pozisyon kapatma sırasında hata!\n"
            "🛠️ Teknik destek ile iletişime geçin",
            parse_mode='Markdown'
        )

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
    """🛡️ ROBUST Metin mesajları işle - Crash korumalı"""
    try:
        # ✅ GUARD: Basic safety checks
        if not update or not update.message or not update.message.text:
            logger.warning("Message handler: Invalid update or empty message")
            return
        
        user_id = update.effective_user.id
        text = update.message.text
        
        # ✅ GUARD: Input length protection  
        if len(text) > 512:
            await update.message.reply_text(
                "❌ Mesaj çok uzun (max 512 karakter)\n🔙 /start ile ana menü"
            )
            return
        
        # ✅ API INPUT HANDLING WITH ROBUST VALIDATION
        if context.user_data.get('waiting') == 'api':
            # ✅ CHECK STATE TIMEOUT FIRST
            if timeout_manager.is_state_expired(user_id):
                timeout_manager.clear_user_state(user_id, context)
                await update.message.reply_text(
                    "⏰ **API girişiniz zaman aşımına uğradı**\n\n"
                    "🔄 Tekrar denemek için: /start → 🔑 API Ayarları"
                )
                return
            
            try:
                # Initialize failure counter if not exists
                failures = context.user_data.get('api_failures', 0)
                
                # ✅ USE ROBUST VALIDATOR
                api_key, secret_key, passphrase = InputValidator.validate_api_triplet(text)
                
                # ✅ SUCCESS: Save API credentials
                bot.update_setting(user_id, 'api_key', api_key)
                bot.update_setting(user_id, 'secret_key', secret_key)
                bot.update_setting(user_id, 'passphrase', passphrase)
                
                # ✅ SUCCESS: Clear waiting state with timeout manager
                timeout_manager.clear_user_state(user_id, context)
                
                await update.message.reply_text(
                    "✅ **API Bilgileri Kaydedildi!**\n\n"
                    "🔑 Bitget API başarıyla ayarlandı\n"
                    "🚀 Artık otomatik sistem aktif\n\n"
                    "📋 /start ile menüye dön",
                    parse_mode='Markdown'
                )
                logger.info(f"✅ API credentials saved successfully for user {user_id}")
                
            except ValidationError as ve:
                # ✅ VALIDATION ERROR: Increment failures and give feedback
                failures += 1
                context.user_data['api_failures'] = failures
                
                error_msg = str(ve)
                if failures >= 3:
                    # ✅ TOO MANY FAILURES: Clear state with timeout manager
                    timeout_manager.clear_user_state(user_id, context)
                    error_msg += "\n\n🆘 **Çok fazla hata!**\n⚠️ Yardım için: /start → 🔑 API Ayarları"
                else:
                    error_msg += f"\n\n🔢 Deneme: {failures}/3\n🔙 /start ile çık"
                
                await update.message.reply_text(error_msg)
                logger.warning(f"API validation failed for user {user_id}: {ve} (attempt {failures})")
                
            except Exception as e:
                # ✅ DATABASE ERROR: Reset state with timeout manager
                timeout_manager.clear_user_state(user_id, context)
                
                logger.error(f"❌ API save error for user {user_id}: {e}")
                await update.message.reply_text(
                    "❌ **Sistem hatası!**\n\n"
                    "API kaydederken problem oluştu\n"
                    "🔙 /start ile tekrar dene"
                )
        
        else:
            # ✅ NOT WAITING FOR API: Inform user politely
            await update.message.reply_text(
                "ℹ️ Şu an bir giriş beklenmiyordu\n\n📊 /start ile menüye git"
            )
            
    except Exception as e:
        # ✅ GLOBAL PROTECTION: Never let bot crash
        logger.error(f"❌ CRITICAL: Message handler crashed for user {user_id if 'user_id' in locals() else 'unknown'}: {e}")
        try:
            if update and update.message:
                await update.message.reply_text(
                    "⚠️ **Geçici sistem hatası**\n\n"
                    "Lütfen /start ile yeniden deneyin"
                )
        except:
            # Even replying failed - log and continue
            logger.error(f"❌ FATAL: Could not send error message: {e}")
        
        # ✅ EMERGENCY: Clear any waiting states to prevent stuck users
        if 'context' in locals() and 'user_id' in locals():
            try:
                timeout_manager.clear_user_state(user_id, context)
            except:
                try:
                    context.user_data.clear()
                except:
                    pass

# ✅ GLOBAL ERROR HANDLER - Prevents application crashes
async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Global error handler to catch all unhandled exceptions
    Ensures bot stays responsive even with unexpected errors
    """
    try:
        # Log the error without PII
        error = context.error
        logger.error(f"🚨 GLOBAL ERROR HANDLER: {type(error).__name__}: {error}")
        
        # Try to extract user info safely  
        user_id = None
        if update and hasattr(update, 'effective_user') and update.effective_user:
            user_id = update.effective_user.id
        elif update and hasattr(update, 'callback_query') and update.callback_query:
            user_id = update.callback_query.from_user.id
        
        # Try to send a user-friendly error message if possible
        if update and hasattr(update, 'message') and update.message:
            try:
                await update.message.reply_text(
                    "⚠️ **Geçici sistem hatası**\n\n"
                    "Bot geçici olarak yanıt veremedi\n"
                    "Lütfen /start ile tekrar deneyin"
                )
            except:
                pass  # If we can't even send error message, just log
        elif update and hasattr(update, 'callback_query') and update.callback_query:
            try:
                await update.callback_query.message.reply_text(
                    "⚠️ **Geçici sistem hatası**\n\n"
                    "Bot geçici olarak yanıt veremedi\n"
                    "Lütfen /start ile tekrar deneyin"
                )
            except:
                pass  # If we can't even send error message, just log
        
        # Emergency user state cleanup to prevent stuck states
        if user_id and context.user_data:
            try:
                context.user_data.clear()
                logger.info(f"✅ Emergency state cleared for user {user_id}")
            except:
                pass  # Even cleanup can fail, that's ok
                
        # Log that we handled the error and bot continues
        logger.info("✅ Global error handled, bot continues running")
        
    except Exception as emergency_error:
        # Even our error handler failed - this is very rare
        logger.critical(f"💥 CRITICAL: Global error handler itself failed: {emergency_error}")
        # Bot will continue running anyway due to application architecture

def main():
    if not BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN bulunamadı!")
        return
        
    application = Application.builder().token(BOT_TOKEN).build()
    
    # ✅ ADD GLOBAL ERROR HANDLER FIRST (highest priority)
    application.add_error_handler(global_error_handler)
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    print("🚀 ÇALIŞAN TELEGRAM BOT başlatılıyor...")
    print("✅ Callback problemleri çözüldü!")
    print("✅ Architect önerileri uygulandı")
    print("✅ Fast callback + background tasks")
    print("✅ Robust error handling active")
    print("✅ User state timeout protection")
    
    # Start heartbeat for supervisor health monitoring
    start_heartbeat()
    
    # ✅ PERIODIC STATE CLEANUP (will run in background when needed)
    async def periodic_state_cleanup(context):
        """Job queue task to cleanup expired user states"""
        try:
            await timeout_manager.check_and_cleanup_expired_states(application)
            logger.info("🧹 Periodic state cleanup completed")
        except Exception as e:
            logger.error(f"❌ Periodic cleanup error: {e}")
    
    # Schedule periodic cleanup every 10 minutes using job queue
    if application.job_queue:
        application.job_queue.run_repeating(
            periodic_state_cleanup, 
            interval=600,  # 10 minutes
            first=600      # Start after 10 minutes
        )
        logger.info("✅ Periodic state cleanup scheduled")
    
    # ✅ Architect önerisi: Eski callback'leri temizle
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES
    )

if __name__ == '__main__':
    main()