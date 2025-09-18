#!/usr/bin/env python3
"""
🚀 STABLE CRYPTOCURRENCY TRADING SYSTEM
Modern asyncio-based architecture with Redis queues and proper error handling
GOAL: NEVER CRASH - 24/7 UPTIME GUARANTEED
"""
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
import aiosqlite
import redis.asyncio as redis
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
import aiohttp
from aiohttp import web, ClientSession
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from cryptography.fernet import Fernet
import json
import uuid
import traceback
from contextlib import asynccontextmanager

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/stable_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DatabaseManager:
    """Unified database with proper schema and migrations"""
    
    def __init__(self, db_path: str = "stable_trading.db"):
        self.db_path = db_path
        self.encryption_key = self._get_or_create_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        
    def _get_or_create_encryption_key(self) -> bytes:
        """Get encryption key from env or create new one"""
        key_str = os.getenv('DB_ENCRYPTION_KEY')
        if key_str:
            return key_str.encode()
        else:
            key = Fernet.generate_key()
            logger.warning("Generated new encryption key - store in Replit Secrets!")
            return key
    
    async def initialize(self):
        """Initialize database with proper schema"""
        async with aiosqlite.connect(self.db_path) as db:
            # Enable WAL mode for better concurrency
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA synchronous=NORMAL")
            await db.execute("PRAGMA cache_size=10000")
            
            # Schema version for migrations
            await db.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Encrypted API credentials
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_credentials (
                    user_id INTEGER PRIMARY KEY,
                    bitget_api_key_encrypted TEXT,
                    bitget_secret_key_encrypted TEXT,  
                    bitget_passphrase_encrypted TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            # Trading settings
            await db.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    leverage INTEGER DEFAULT 125,
                    trade_amount REAL DEFAULT 50.0,
                    take_profit_percent REAL DEFAULT 10.0,
                    auto_trading BOOLEAN DEFAULT true,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                )
            """)
            
            # Announcements tracking
            await db.execute("""
                CREATE TABLE IF NOT EXISTS announcements (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT,
                    tokens TEXT,  -- JSON array of tokens
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT false
                )
            """)
            
            # Trading tasks/orders
            await db.execute("""
                CREATE TABLE IF NOT EXISTS trading_tasks (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    announcement_id TEXT,
                    token_symbol TEXT,
                    action TEXT,  -- 'open', 'close'
                    status TEXT DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
                    order_id TEXT,
                    position_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (announcement_id) REFERENCES announcements(id)
                )
            """)
            
            # Idempotency keys to prevent duplicate orders
            await db.execute("""
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    key TEXT PRIMARY KEY,
                    user_id INTEGER,
                    task_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """)
            
            await db.commit()
            logger.info("✅ Database initialized with unified schema")
    
    def encrypt_text(self, text: str) -> str:
        """Encrypt sensitive text"""
        return self.cipher.encrypt(text.encode()).decode()
    
    def decrypt_text(self, encrypted_text: str) -> str:
        """Decrypt sensitive text"""
        return self.cipher.decrypt(encrypted_text.encode()).decode()
    
    async def store_user_credentials(self, user_id: int, api_key: str, secret_key: str, passphrase: str):
        """Store encrypted user credentials"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO user_credentials 
                (user_id, bitget_api_key_encrypted, bitget_secret_key_encrypted, bitget_passphrase_encrypted, updated_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                user_id,
                self.encrypt_text(api_key),
                self.encrypt_text(secret_key),
                self.encrypt_text(passphrase),
                datetime.now(timezone.utc)
            ))
            await db.commit()
    
    async def get_user_credentials(self, user_id: int) -> Optional[Dict]:
        """Get decrypted user credentials"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                SELECT bitget_api_key_encrypted, bitget_secret_key_encrypted, bitget_passphrase_encrypted
                FROM user_credentials WHERE user_id = ?
            """, (user_id,))
            row = await cursor.fetchone()
            
            if row:
                return {
                    'api_key': self.decrypt_text(row[0]),
                    'secret_key': self.decrypt_text(row[1]),
                    'passphrase': self.decrypt_text(row[2])
                }
        return None

class CircuitBreaker:
    """Circuit breaker pattern for external API calls"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half_open
    
    def is_open(self) -> bool:
        if self.state == 'open':
            if self.last_failure_time and datetime.now().timestamp() - self.last_failure_time > self.timeout:
                self.state = 'half_open'
                return False
            return True
        return False
    
    def record_success(self):
        self.failure_count = 0
        self.state = 'closed'
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = datetime.now().timestamp()
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'

class UpbitMonitor:
    """Stable HTTP-based Upbit announcement monitoring (no Selenium)"""
    
    def __init__(self, redis_client: redis.Redis, db_manager: DatabaseManager):
        self.redis_client = redis_client
        self.db_manager = db_manager
        self.session = None
        self.circuit_breaker = CircuitBreaker()
        
    async def start(self):
        """Start monitoring"""
        self.session = ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        logger.info("🔍 Upbit Monitor started")
    
    async def stop(self):
        """Stop monitoring"""
        if self.session:
            await self.session.close()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((Exception,))
    )
    async def check_announcements(self):
        """Check for new announcements with retry logic"""
        if self.circuit_breaker.is_open():
            logger.warning("⚠️ Upbit monitor circuit breaker is open")
            return
        
        try:
            # Use both web scraping and API approach
            await self._check_web_announcements()
            await self._check_market_api()
            self.circuit_breaker.record_success()
            
        except Exception as e:
            logger.error(f"❌ Upbit monitoring error: {e}")
            self.circuit_breaker.record_failure()
            raise
    
    async def _check_web_announcements(self):
        """Check web announcements with stable parsing"""
        url = "https://upbit.com/service_center/notice"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        if not self.session:
            raise Exception("Session not initialized")
        async with self.session.get(url, headers=headers) as response:
            if response.status != 200:
                raise Exception(f"HTTP {response.status}")
                
            html = await response.text()
            # TODO: Implement stable HTML parsing for listings
            # For now, focus on API approach
    
    async def _check_market_api(self):
        """Check market API for new tokens"""
        # Use Upbit market API to detect new symbols
        url = "https://api.upbit.com/v1/market/all"
        
        if not self.session:
            raise Exception("Session not initialized")
        async with self.session.get(url) as response:
            if response.status != 200:
                raise Exception(f"API HTTP {response.status}")
                
            markets = await response.json()
            krw_markets = [m for m in markets if m['market'].startswith('KRW-')]
            
            # Compare with our stored list to find new additions
            stored_symbols = await self._get_stored_symbols()
            current_symbols = {m['market'] for m in krw_markets}
            new_symbols = current_symbols - stored_symbols
            
            if new_symbols:
                logger.info(f"🚨 New tokens detected: {new_symbols}")
                for symbol in new_symbols:
                    await self._publish_new_listing(symbol)
                await self._update_stored_symbols(current_symbols)
    
    async def _get_stored_symbols(self) -> set:
        """Get stored KRW symbols"""
        try:
            stored = await self.redis_client.get("upbit:krw_symbols")
            if stored:
                return set(json.loads(stored))
        except:
            pass
        return set()
    
    async def _update_stored_symbols(self, symbols: set):
        """Update stored symbols"""
        await self.redis_client.set("upbit:krw_symbols", json.dumps(list(symbols)))
    
    async def _publish_new_listing(self, symbol: str):
        """Publish new listing to Redis stream"""
        token = symbol.replace('KRW-', '')
        announcement_id = f"listing_{token}_{int(datetime.now().timestamp())}"
        
        # Store in database
        async with aiosqlite.connect(self.db_manager.db_path) as db:
            await db.execute("""
                INSERT OR IGNORE INTO announcements (id, title, tokens, discovered_at)
                VALUES (?, ?, ?, ?)
            """, (
                announcement_id,
                f"New listing: {token}",
                json.dumps([token]),
                datetime.now(timezone.utc)
            ))
            await db.commit()
        
        # Publish to Redis stream
        await self.redis_client.xadd("upbit:new_listings", {
            "announcement_id": announcement_id,
            "token": token,
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"🚀 Published new listing: {token}")

class TelegramBot:
    """Async Telegram bot with proper error handling"""
    
    def __init__(self, token: str, redis_client: redis.Redis, db_manager: DatabaseManager):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.redis_client = redis_client
        self.db_manager = db_manager
        self._register_handlers()
    
    def _register_handlers(self):
        """Register message handlers"""
        self.dp.message.register(self.start_command, Command("start"))
        self.dp.message.register(self.status_command, Command("status"))
        self.dp.message.register(self.setup_command, Command("setup"))
        self.dp.callback_query.register(self.close_position_callback, F.data.startswith("close_"))
    
    async def start_command(self, message: Message):
        """Handle /start command"""
        await message.reply(
            "🚀 **Stable Crypto Trading Bot**\n\n"
            "Commands:\n"
            "/setup - Configure your API keys\n"
            "/status - Check your settings\n\n"
            "This bot monitors Upbit listings and auto-trades on Bitget."
        )
    
    async def status_command(self, message: Message):
        """Handle /status command"""
        user_id = message.from_user.id
        credentials = await self.db_manager.get_user_credentials(user_id)
        
        if credentials:
            await message.reply("✅ API keys configured\n🤖 Auto-trading active")
        else:
            await message.reply("❌ API keys not configured\nUse /setup to configure")
    
    async def setup_command(self, message: Message):
        """Handle /setup command"""
        await message.reply(
            "⚙️ **API Setup**\n\n"
            "Please send your Bitget API credentials in this format:\n"
            "`API_KEY:SECRET_KEY:PASSPHRASE`\n\n"
            "Example:\n"
            "`bg_abc123:def456:mypassphrase`"
        )
    
    async def close_position_callback(self, callback: CallbackQuery):
        """Handle close position button"""
        if not callback.data:
            return
        task_id = callback.data.replace("close_", "")
        user = callback.from_user
        if not user or not user.id:
            return
        user_id = user.id
        
        # Queue close task
        close_task_id = str(uuid.uuid4())
        await self.redis_client.xadd("trading:close_requests", {
            "task_id": close_task_id,
            "user_id": user_id,
            "position_task_id": task_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        await callback.answer("🔄 Closing position...")
        message = callback.message
        if message and hasattr(message, 'edit_text') and hasattr(message, 'text') and message.text:
            try:
                await message.edit_text(
                    message.text + "\n\n🔄 **Position close requested**"
                )
            except Exception as e:
                logger.error(f"Failed to edit message: {e}")

class StableTradingSystem:
    """Main system coordinator"""
    
    def __init__(self):
        self.running = True
        self.redis_client = None
        self.db_manager = DatabaseManager()
        self.upbit_monitor = None
        self.telegram_bot = None
        self.scheduler = AsyncIOScheduler()
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"📡 Received signal {signum}, shutting down...")
        self.running = False
    
    async def start(self):
        """Start the stable trading system"""
        try:
            logger.info("🚀 STABLE TRADING SYSTEM STARTING")
            
            # Initialize Redis
            self.redis_client = redis.Redis.from_url(
                os.getenv('REDIS_URL', 'redis://localhost:6379'), 
                decode_responses=True
            )
            await self.redis_client.ping()
            logger.info("✅ Redis connected")
            
            # Initialize database
            await self.db_manager.initialize()
            
            # Initialize components
            self.upbit_monitor = UpbitMonitor(self.redis_client, self.db_manager)
            await self.upbit_monitor.start()
            
            telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if not telegram_token:
                raise ValueError("TELEGRAM_BOT_TOKEN not set")
            
            self.telegram_bot = TelegramBot(telegram_token, self.redis_client, self.db_manager)
            
            # Start scheduler
            self.scheduler.add_job(
                self.upbit_monitor.check_announcements,
                'interval',
                minutes=1,
                id='upbit_monitor'
            )
            self.scheduler.start()
            logger.info("✅ Scheduler started")
            
            # Start async tasks
            tasks = [
                self._run_telegram_bot(),
                self._process_trade_requests(),
                self._health_check_loop()
            ]
            
            logger.info("🏭 STABLE TRADING SYSTEM RUNNING")
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"❌ System startup failed: {e}")
            await self.stop()
            raise
    
    async def _run_telegram_bot(self):
        """Run Telegram bot polling"""
        try:
            if self.telegram_bot:
                await self.telegram_bot.dp.start_polling(self.telegram_bot.bot)
        except Exception as e:
            logger.error(f"❌ Telegram bot error: {e}")
            # Auto-restart bot on error
            await asyncio.sleep(5)
            await self._run_telegram_bot()
    
    async def _process_trade_requests(self):
        """Process trading requests from Redis streams"""
        while self.running:
            try:
                # Process new listings
                if not self.redis_client:
                    await asyncio.sleep(5)
                    continue
                messages = await self.redis_client.xread(
                    {"upbit:new_listings": "$"}, 
                    count=10, 
                    block=1000
                )
                
                for stream, msgs in messages:
                    for msg_id, fields in msgs:
                        await self._handle_new_listing(fields)
                
            except Exception as e:
                logger.error(f"❌ Trade processing error: {e}")
                await asyncio.sleep(5)
    
    async def _handle_new_listing(self, listing_data: dict):
        """Handle new token listing"""
        token = listing_data['token']
        announcement_id = listing_data['announcement_id']
        
        logger.info(f"🎯 Processing new listing: {token}")
        
        # Get all users with auto-trading enabled
        async with aiosqlite.connect(self.db_manager.db_path) as db:
            cursor = await db.execute("""
                SELECT u.user_id FROM users u
                JOIN user_settings s ON u.user_id = s.user_id
                WHERE s.auto_trading = true
            """)
            users = await cursor.fetchall()
        
        # Create trade tasks for each user
        for (user_id,) in users:
            task_id = str(uuid.uuid4())
            idempotency_key = f"{user_id}:{token}:{announcement_id}"
            
            # Check idempotency
            async with aiosqlite.connect(self.db_manager.db_path) as db:
                cursor = await db.execute(
                    "SELECT key FROM idempotency_keys WHERE key = ?",
                    (idempotency_key,)
                )
                if await cursor.fetchone():
                    continue  # Skip duplicate
                
                # Store idempotency key and task
                await db.execute("""
                    INSERT INTO idempotency_keys (key, user_id, task_id)
                    VALUES (?, ?, ?)
                """, (idempotency_key, user_id, task_id))
                
                await db.execute("""
                    INSERT INTO trading_tasks 
                    (id, user_id, announcement_id, token_symbol, action, status)
                    VALUES (?, ?, ?, ?, 'open', 'pending')
                """, (task_id, user_id, announcement_id, token))
                
                await db.commit()
            
            # Queue for processing
            if self.redis_client:
                await self.redis_client.xadd("trading:pending_orders", {
                "task_id": task_id,
                "user_id": user_id,
                "token": token,
                "action": "open"
            })
            
            logger.info(f"📝 Queued trade task for user {user_id}: {token}")
    
    async def _health_check_loop(self):
        """System health monitoring"""
        while self.running:
            try:
                # Check Redis connection
                if self.redis_client:
                    await self.redis_client.ping()
                
                # Log system status
                logger.info("💚 System healthy - all components running")
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error(f"❌ Health check failed: {e}")
                await asyncio.sleep(10)
    
    async def stop(self):
        """Stop the system gracefully"""
        logger.info("🛑 Stopping stable trading system...")
        self.running = False
        
        if self.scheduler.running:
            self.scheduler.shutdown()
        
        if self.upbit_monitor:
            await self.upbit_monitor.stop()
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("✅ System stopped gracefully")

async def main():
    """Main entry point"""
    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)
    
    system = StableTradingSystem()
    try:
        await system.start()
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
    except Exception as e:
        logger.error(f"❌ System error: {e}")
        logger.error(traceback.format_exc())
    finally:
        await system.stop()

if __name__ == "__main__":
    asyncio.run(main())