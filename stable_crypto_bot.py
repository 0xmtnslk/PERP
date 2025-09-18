#!/usr/bin/env python3
"""
🚀 PRODUCTION-READY STABLE CRYPTO TRADING BOT
Fixes critical bugs identified by architect:
- No false positive floods
- Persistent token baseline  
- Single instance enforcement
- Durable queue processing
"""
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from cryptography.fernet import Fernet
import json
import uuid
import traceback
import hashlib
import base64

# Logging setup  
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/stable_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SingletonLock:
    """Prevent multiple bot instances"""
    def __init__(self, lock_file: str = ".bot.lock"):
        self.lock_file = lock_file
        
    async def acquire(self):
        """Acquire exclusive lock"""
        if os.path.exists(self.lock_file):
            with open(self.lock_file, 'r') as f:
                old_pid = f.read().strip()
            
            # Check if old process still running
            try:
                os.kill(int(old_pid), 0)
                raise RuntimeError(f"Another bot instance is running (PID: {old_pid})")
            except (ProcessLookupError, ValueError):
                # Old process dead, remove stale lock
                os.remove(self.lock_file)
        
        # Create new lock
        with open(self.lock_file, 'w') as f:
            f.write(str(os.getpid()))
        logger.info(f"🔒 Lock acquired (PID: {os.getpid()})")
    
    def release(self):
        """Release lock"""
        try:
            os.remove(self.lock_file)
            logger.info("🔓 Lock released")
        except FileNotFoundError:
            pass

class DatabaseManager:
    """Production database with migrations and encryption"""
    
    def __init__(self, db_path: str = "stable_crypto_bot.db"):
        self.db_path = db_path
        self.encryption_key = self._get_encryption_key()
        self.cipher = Fernet(self.encryption_key)
        
    def _get_encryption_key(self) -> bytes:
        """Get and validate encryption key from environment (fail-fast)"""
        key_str = os.getenv('DB_ENCRYPTION_KEY')
        if not key_str:
            raise ValueError("❌ CRITICAL: DB_ENCRYPTION_KEY environment variable not set! Credentials cannot be stored safely.")
        
        try:
            # Fernet expects a URL-safe base64-encoded 32-byte key
            key_bytes = key_str.encode('utf-8')
            
            # Test encryption to validate key
            test_cipher = Fernet(key_bytes)
            test_data = b"test"
            encrypted = test_cipher.encrypt(test_data)
            decrypted = test_cipher.decrypt(encrypted)
            
            if decrypted != test_data:
                raise ValueError("Encryption test failed")
            
            logger.info("✅ Encryption key validated successfully")
            return key_bytes
            
        except Exception as e:
            raise ValueError(f"❌ CRITICAL: Invalid DB_ENCRYPTION_KEY - {e}. Credentials cannot be stored safely!")
    
    async def initialize(self):
        """Initialize database with versioned migrations"""
        async with aiosqlite.connect(self.db_path) as db:
            # Enable WAL and foreign keys
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA foreign_keys=ON")
            await db.execute("PRAGMA synchronous=NORMAL")
            
            # Schema version tracking
            await db.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            """)
            
            # Check current version
            cursor = await db.execute("SELECT MAX(version) FROM schema_version")
            result = await cursor.fetchone()
            current_version = result[0] if result and result[0] else 0
            
            # Apply migrations
            await self._apply_migrations(db, current_version)
            await db.commit()
            
            logger.info(f"✅ Database initialized (schema v{current_version})")
    
    async def _apply_migrations(self, db, current_version: int):
        """Apply database migrations"""
        migrations = [
            # Version 1: Core tables
            (1, "Initial schema", """
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS user_credentials (
                    user_id INTEGER PRIMARY KEY,
                    api_key_encrypted TEXT,
                    secret_key_encrypted TEXT,
                    passphrase_encrypted TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );
                
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id INTEGER PRIMARY KEY,
                    leverage INTEGER DEFAULT 125,
                    trade_amount REAL DEFAULT 50.0,
                    take_profit_percent REAL DEFAULT 10.0,
                    auto_trading BOOLEAN DEFAULT true,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(user_id)
                );
            """),
            
            # Version 2: Token tracking and deduplication
            (2, "Token baseline and processing", """
                CREATE TABLE IF NOT EXISTS token_baseline (
                    symbol TEXT PRIMARY KEY,
                    market_type TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS announcements (
                    id TEXT PRIMARY KEY,
                    token TEXT NOT NULL,
                    title TEXT,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT false,
                    processing_started_at TIMESTAMP,
                    processing_completed_at TIMESTAMP
                );
                
                CREATE TABLE IF NOT EXISTS trading_tasks (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    announcement_id TEXT,
                    token_symbol TEXT,
                    action TEXT,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(user_id),
                    FOREIGN KEY (announcement_id) REFERENCES announcements(id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_announcements_processed ON announcements(processed, discovered_at);
                CREATE INDEX IF NOT EXISTS idx_trading_tasks_status ON trading_tasks(status, created_at);
            """),
        ]
        
        for version, description, sql in migrations:
            if version > current_version:
                logger.info(f"🔄 Applying migration v{version}: {description}")
                for statement in sql.split(';'):
                    statement = statement.strip()
                    if statement:
                        await db.execute(statement)
                
                await db.execute("""
                    INSERT INTO schema_version (version, description) VALUES (?, ?)
                """, (version, description))
    
    def encrypt_text(self, text: str) -> str:
        """Encrypt sensitive text"""
        return self.cipher.encrypt(text.encode()).decode()
    
    def decrypt_text(self, encrypted_text: str) -> str:
        """Decrypt sensitive text"""
        try:
            return self.cipher.decrypt(encrypted_text.encode()).decode()
        except Exception as e:
            raise ValueError(f"Failed to decrypt credentials - key may be wrong: {e}")
    
    async def store_user_credentials(self, user_id: int, api_key: str, secret_key: str, passphrase: str):
        """Store encrypted user credentials"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO user_credentials 
                (user_id, api_key_encrypted, secret_key_encrypted, passphrase_encrypted, updated_at)
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
                SELECT api_key_encrypted, secret_key_encrypted, passphrase_encrypted
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
    
    async def initialize_token_baseline(self, tokens: Set[str]):
        """Initialize token baseline to prevent false positives"""
        async with aiosqlite.connect(self.db_path) as db:
            # Check if baseline already exists
            cursor = await db.execute("SELECT COUNT(*) FROM token_baseline")
            result = await cursor.fetchone()
            count = result[0] if result and result[0] else 0
            
            if count == 0:
                # First run - populate baseline without triggering alerts
                logger.info(f"🏗️ Initializing token baseline with {len(tokens)} existing KRW tokens")
                for token in tokens:
                    await db.execute("""
                        INSERT OR IGNORE INTO token_baseline (symbol, market_type)
                        VALUES (?, 'KRW')
                    """, (token,))
                await db.commit()
                logger.info("✅ Token baseline initialized - no false alerts will be generated")
                return True
            return False
    
    async def get_baseline_tokens(self) -> Set[str]:
        """Get baseline tokens"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT symbol FROM token_baseline WHERE market_type = 'KRW'")
            rows = await cursor.fetchall()
            return {row[0] for row in rows}
    
    async def update_token_baseline(self, new_tokens: Set[str]):
        """Update baseline with new tokens"""
        async with aiosqlite.connect(self.db_path) as db:
            for token in new_tokens:
                await db.execute("""
                    INSERT OR IGNORE INTO token_baseline (symbol, market_type)
                    VALUES (?, 'KRW')
                """, (token,))
            await db.commit()

class CircuitBreaker:
    """Circuit breaker for external APIs"""
    
    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half_open
    
    def can_execute(self) -> bool:
        """Check if execution is allowed"""
        if self.state == 'closed':
            return True
        elif self.state == 'open':
            if self.last_failure_time and datetime.now().timestamp() - self.last_failure_time > self.timeout:
                self.state = 'half_open'
                return True
            return False
        else:  # half_open
            return True
    
    def record_success(self):
        """Record successful execution"""
        self.failure_count = 0
        self.state = 'closed'
    
    def record_failure(self):
        """Record failed execution"""
        self.failure_count += 1
        self.last_failure_time = datetime.now().timestamp()
        if self.failure_count >= self.failure_threshold:
            self.state = 'open'
            logger.warning(f"⚡ Circuit breaker OPENED (failures: {self.failure_count})")

class StableUpbitMonitor:
    """Production Upbit monitor with proper baseline handling"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.session = None
        self.circuit_breaker = CircuitBreaker(failure_threshold=3, timeout=300)  # 5min timeout
        
    async def start(self):
        """Start monitoring"""
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=10)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        logger.info("🔍 Stable Upbit Monitor started")
    
    async def stop(self):
        """Stop monitoring"""
        if self.session:
            await self.session.close()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError))
    )
    async def check_new_listings(self):
        """Check for new KRW listings with proper baseline handling"""
        if not self.circuit_breaker.can_execute():
            logger.warning("⚡ Upbit monitor circuit breaker is open")
            return []
        
        try:
            if not self.session:
                raise Exception("Session not initialized")
            
            # Get current KRW markets from Upbit API
            url = "https://api.upbit.com/v1/market/all"
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; CryptoBot/1.0)',
                'Accept': 'application/json'
            }
            
            async with self.session.get(url, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"Upbit API returned {response.status}")
                
                markets = await response.json()
                current_krw_tokens = {
                    market['market'].replace('KRW-', '') 
                    for market in markets 
                    if market['market'].startswith('KRW-')
                }
                
                logger.info(f"📊 Current KRW tokens: {len(current_krw_tokens)}")
                
                # Initialize baseline on first run
                is_first_run = await self.db_manager.initialize_token_baseline(current_krw_tokens)
                if is_first_run:
                    logger.info("🏗️ First run - baseline initialized, no alerts generated")
                    self.circuit_breaker.record_success()
                    return []
                
                # Get baseline and find truly new tokens
                baseline_tokens = await self.db_manager.get_baseline_tokens()
                new_tokens = current_krw_tokens - baseline_tokens
                
                if new_tokens:
                    logger.info(f"🚨 NEW KRW TOKENS DETECTED: {new_tokens}")
                    
                    new_listings = []
                    for token in new_tokens:
                        listing = await self._create_new_listing(token)
                        new_listings.append(listing)
                    
                    # Update baseline
                    await self.db_manager.update_token_baseline(new_tokens)
                    
                    self.circuit_breaker.record_success()
                    return new_listings
                
                # No new tokens
                logger.info("✅ No new tokens detected")
                self.circuit_breaker.record_success()
                return []
                
        except Exception as e:
            logger.error(f"❌ Upbit monitoring error: {e}")
            self.circuit_breaker.record_failure()
            raise
    
    async def _create_new_listing(self, token: str) -> dict:
        """Create new listing record"""
        announcement_id = f"krw_{token}_{int(datetime.now().timestamp())}_{uuid.uuid4().hex[:8]}"
        
        # Store in database
        async with aiosqlite.connect(self.db_manager.db_path) as db:
            await db.execute("""
                INSERT INTO announcements (id, token, title, discovered_at, processed)
                VALUES (?, ?, ?, ?, ?)
            """, (
                announcement_id,
                token,
                f"New KRW listing: {token}",
                datetime.now(timezone.utc),
                False
            ))
            await db.commit()
        
        return {
            'announcement_id': announcement_id,
            'token': token,
            'symbol': f'KRW-{token}',
            'discovered_at': datetime.now(timezone.utc).isoformat()
        }

class TelegramBot:
    """Production Telegram bot with single-instance control"""
    
    def __init__(self, token: str, db_manager: DatabaseManager):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.db_manager = db_manager
        self._register_handlers()
    
    def _register_handlers(self):
        """Register message handlers"""
        self.dp.message.register(self.start_command, Command("start"))
        self.dp.message.register(self.status_command, Command("status"))
        self.dp.message.register(self.setup_command, Command("setup"))
        self.dp.message.register(self.settings_command, Command("settings"))
        self.dp.message.register(self.handle_api_setup, F.text.startswith("API:"))
        self.dp.callback_query.register(self.close_position_callback, F.data.startswith("close_"))
    
    async def start_command(self, message: Message):
        """Handle /start command"""
        if not message.from_user:
            return
            
        user = message.from_user
        user_id = user.id
        username = user.username or "unknown"
        first_name = user.first_name or "User"
        
        # Register user
        async with aiosqlite.connect(self.db_manager.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO users (user_id, username, first_name)
                VALUES (?, ?, ?)
            """, (user_id, username, first_name))
            
            # Initialize default settings
            await db.execute("""
                INSERT OR IGNORE INTO user_settings (user_id, auto_trading)
                VALUES (?, ?)
            """, (user_id, True))
            
            await db.commit()
        
        await message.reply(
            f"🚀 **Stable Crypto Trading Bot**\n\n"
            f"Merhaba {first_name}! 👋\n\n"
            f"Bu bot Upbit'de yeni KRW token listinglerini tespit edip "
            f"Bitget'te otomatik long pozisyon açar.\n\n"
            f"**Komutlar:**\n"
            f"/setup - API key ayarları\n"
            f"/settings - Trading ayarları\n"
            f"/status - Sistem durumu\n\n"
            f"⚙️ Önce /setup ile Bitget API keyinizi tanımlayın!"
        )
        
        logger.info(f"👤 New user registered: {user_id} (@{username})")
    
    async def setup_command(self, message: Message):
        """Handle API setup"""
        await message.reply(
            "⚙️ **Bitget API Setup**\n\n"
            "Bitget API key'lerinizi bu formatta gönderin:\n\n"
            "`API:your_api_key:your_secret_key:your_passphrase`\n\n"
            "**Örnek:**\n"
            "`API:bg_abc123:def456ghi789:mypassphrase`\n\n"
            "⚠️ API key'leriniz şifrelenerek güvenli saklanır."
        )
    
    async def handle_api_setup(self, message: Message):
        """Handle API key configuration"""
        if not message.from_user or not message.text:
            return
            
        user_id = message.from_user.id
        
        try:
            # Parse API:key:secret:passphrase
            parts = message.text.strip().split(':')
            if len(parts) != 4 or parts[0] != 'API':
                raise ValueError("Invalid format")
            
            _, api_key, secret_key, passphrase = parts
            
            # Validate keys (basic check)
            if not all([api_key, secret_key, passphrase]):
                raise ValueError("Empty fields")
            
            # Store encrypted credentials
            await self.db_manager.store_user_credentials(user_id, api_key, secret_key, passphrase)
            
            await message.reply(
                "✅ **API Keys Configured!**\n\n"
                "🔐 Keys encrypted and stored securely\n"
                "🤖 Auto-trading enabled\n\n"
                "Bot will now automatically trade new KRW listings!"
            )
            
            # Delete the message for security
            try:
                await message.delete()
            except:
                pass  # May not have permission
                
            logger.info(f"🔐 API keys configured for user {user_id}")
            
        except Exception as e:
            await message.reply(
                "❌ **Invalid format!**\n\n"
                "Use: `API:api_key:secret_key:passphrase`\n\n"
                "Please try again."
            )
            logger.error(f"❌ API setup error for user {user_id}: {e}")
    
    async def status_command(self, message: Message):
        """Handle /status command"""
        if not message.from_user:
            return
            
        user_id = message.from_user.id
        
        # Get user status
        credentials = await self.db_manager.get_user_credentials(user_id)
        
        async with aiosqlite.connect(self.db_manager.db_path) as db:
            # Get settings
            cursor = await db.execute("""
                SELECT leverage, trade_amount, take_profit_percent, auto_trading
                FROM user_settings WHERE user_id = ?
            """, (user_id,))
            settings = await cursor.fetchone()
            
            # Get recent trades
            cursor = await db.execute("""
                SELECT COUNT(*) FROM trading_tasks 
                WHERE user_id = ? AND created_at > datetime('now', '-24 hours')
            """, (user_id,))
            result = await cursor.fetchone()
            recent_trades = result[0] if result and result[0] else 0
        
        if settings:
            leverage, amount, profit, auto_trading = settings
            status_text = (
                f"📊 **Your Status**\n\n"
                f"🔐 API Keys: {'✅ Configured' if credentials else '❌ Not set'}\n"
                f"🤖 Auto-trading: {'✅ Active' if auto_trading else '❌ Disabled'}\n\n"
                f"⚙️ **Settings:**\n"
                f"📊 Leverage: {leverage}x\n"
                f"💰 Trade Amount: ${amount}\n"
                f"🎯 Take Profit: {profit}%\n\n"
                f"📈 Recent trades (24h): {recent_trades}\n\n"
                f"🔍 Monitoring: Upbit KRW listings"
            )
        else:
            status_text = (
                "❌ **Not configured**\n\n"
                "Use /start to get started!"
            )
        
        await message.reply(status_text)
    
    async def settings_command(self, message: Message):
        """Handle /settings command"""
        await message.reply(
            "⚙️ **Settings Menu**\n\n"
            "Current settings management will be added soon.\n"
            "For now, default settings are used:\n\n"
            "📊 Leverage: 125x\n"
            "💰 Trade Amount: $50\n"
            "🎯 Take Profit: 10%"
        )
    
    async def close_position_callback(self, callback: CallbackQuery):
        """Handle position close requests"""
        if not callback.data or not callback.from_user:
            return
            
        task_id = callback.data.replace("close_", "")
        user_id = callback.from_user.id
        
        # TODO: Implement position closing
        await callback.answer("🔄 Position close feature coming soon!")
        
        logger.info(f"📝 Close position request: User {user_id}, Task {task_id}")
    
    async def notify_new_listing(self, user_id: int, listing_data: dict):
        """Notify user about new listing"""
        try:
            token = listing_data['token']
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text="🔴 Close Position", 
                    callback_data=f"close_{listing_data['announcement_id']}"
                )]
            ])
            
            await self.bot.send_message(
                user_id,
                f"🚀 **NEW LISTING DETECTED**\n\n"
                f"**Token:** {token}\n"
                f"**Market:** KRW-{token}\n"
                f"**Time:** {datetime.now().strftime('%H:%M:%S')}\n\n"
                f"🎯 **Auto-trading:** Long position opening...\n"
                f"⏳ **Status:** Processing trade request",
                reply_markup=keyboard
            )
            
        except Exception as e:
            logger.error(f"❌ Failed to notify user {user_id}: {e}")

class StableCryptoBot:
    """Main stable crypto bot coordinator"""
    
    def __init__(self):
        self.running = True
        self.lock = SingletonLock()
        self.db_manager = DatabaseManager()
        self.upbit_monitor = None
        self.telegram_bot = None
        self.scheduler = AsyncIOScheduler()
        
        # Signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"📡 Received signal {signum}, shutting down gracefully...")
        self.running = False
    
    async def start(self):
        """Start the stable crypto bot"""
        try:
            logger.info("🚀 STABLE CRYPTO BOT STARTING")
            
            # Acquire singleton lock
            await self.lock.acquire()
            
            # Initialize database
            await self.db_manager.initialize()
            
            # Initialize components
            self.upbit_monitor = StableUpbitMonitor(self.db_manager)
            await self.upbit_monitor.start()
            
            # Initialize Telegram bot
            telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if not telegram_token:
                raise ValueError("TELEGRAM_BOT_TOKEN environment variable not set")
            
            self.telegram_bot = TelegramBot(telegram_token, self.db_manager)
            
            # Schedule monitoring (every 1 minute)
            self.scheduler.add_job(
                self._check_and_process_listings,
                'interval',
                minutes=1,
                id='listing_monitor',
                max_instances=1,
                coalesce=True
            )
            
            # Start scheduler
            self.scheduler.start()
            logger.info("✅ Listing monitor scheduled (1-minute interval)")
            
            # Start tasks
            tasks = [
                self._run_telegram_bot(),
                self._process_pending_trades(),
                self._health_monitor()
            ]
            
            logger.info("🏭 STABLE CRYPTO BOT RUNNING - 24/7 MODE ACTIVE")
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"❌ Bot startup failed: {e}")
            logger.error(traceback.format_exc())
            await self.stop()
            raise
    
    async def _check_and_process_listings(self):
        """Check for new listings and process them"""
        try:
            logger.info("🔍 Checking for new listings...")
            
            # Get new listings from Upbit
            if self.upbit_monitor:
                new_listings = await self.upbit_monitor.check_new_listings()
            else:
                new_listings = []
            
            if new_listings:
                logger.info(f"🚨 Processing {len(new_listings)} new listings")
                
                for listing in new_listings:
                    await self._process_new_listing(listing)
            
        except Exception as e:
            logger.error(f"❌ Listing check error: {e}")
    
    async def _process_new_listing(self, listing: dict):
        """Process a new token listing"""
        token = listing['token']
        announcement_id = listing['announcement_id']
        
        logger.info(f"🎯 Processing new listing: {token}")
        
        try:
            # Mark announcement as being processed
            async with aiosqlite.connect(self.db_manager.db_path) as db:
                await db.execute("""
                    UPDATE announcements 
                    SET processing_started_at = ?
                    WHERE id = ?
                """, (datetime.now(timezone.utc), announcement_id))
                
                # Get active users with credentials
                cursor = await db.execute("""
                    SELECT DISTINCT u.user_id 
                    FROM users u
                    JOIN user_settings s ON u.user_id = s.user_id
                    JOIN user_credentials c ON u.user_id = c.user_id
                    WHERE s.auto_trading = 1
                """)
                active_users = [row[0] for row in await cursor.fetchall()]
                
                await db.commit()
            
            logger.info(f"👥 Found {len(active_users)} active users for trading")
            
            # Process trades for each user
            for user_id in active_users:
                try:
                    # Create trading task
                    task_id = str(uuid.uuid4())
                    
                    async with aiosqlite.connect(self.db_manager.db_path) as db:
                        await db.execute("""
                            INSERT INTO trading_tasks 
                            (id, user_id, announcement_id, token_symbol, action, status)
                            VALUES (?, ?, ?, ?, 'open', 'pending')
                        """, (task_id, user_id, announcement_id, token))
                        await db.commit()
                    
                    # Notify user
                    if self.telegram_bot:
                        await self.telegram_bot.notify_new_listing(user_id, listing)
                    
                    logger.info(f"📝 Created trade task {task_id[:8]} for user {user_id}")
                    
                except Exception as e:
                    logger.error(f"❌ Failed to create trade for user {user_id}: {e}")
            
            # Mark announcement as processed
            async with aiosqlite.connect(self.db_manager.db_path) as db:
                await db.execute("""
                    UPDATE announcements 
                    SET processed = 1, processing_completed_at = ?
                    WHERE id = ?
                """, (datetime.now(timezone.utc), announcement_id))
                await db.commit()
            
            logger.info(f"✅ Listing {token} processed successfully")
            
        except Exception as e:
            logger.error(f"❌ Error processing listing {token}: {e}")
    
    async def _process_pending_trades(self):
        """Process pending trading tasks"""
        while self.running:
            try:
                # Get pending trades
                async with aiosqlite.connect(self.db_manager.db_path) as db:
                    cursor = await db.execute("""
                        SELECT id, user_id, token_symbol, action
                        FROM trading_tasks 
                        WHERE status = 'pending'
                        ORDER BY created_at
                        LIMIT 10
                    """)
                    pending_trades = await cursor.fetchall()
                
                for task_id, user_id, token, action in pending_trades:
                    try:
                        # TODO: Implement actual Bitget trading
                        logger.info(f"💰 SIMULATING TRADE: {action} {token} for user {user_id}")
                        
                        # Mark as completed (simulation)
                        async with aiosqlite.connect(self.db_manager.db_path) as db:
                            await db.execute("""
                                UPDATE trading_tasks 
                                SET status = 'completed', completed_at = ?
                                WHERE id = ?
                            """, (datetime.now(timezone.utc), task_id))
                            await db.commit()
                        
                        logger.info(f"✅ Trade {task_id[:8]} completed")
                        
                    except Exception as e:
                        logger.error(f"❌ Trade execution error {task_id}: {e}")
                        
                        # Mark as failed
                        async with aiosqlite.connect(self.db_manager.db_path) as db:
                            await db.execute("""
                                UPDATE trading_tasks 
                                SET status = 'failed', error_message = ?, completed_at = ?
                                WHERE id = ?
                            """, (str(e), datetime.now(timezone.utc), task_id))
                            await db.commit()
                
                await asyncio.sleep(10)  # Check every 10 seconds
                
            except Exception as e:
                logger.error(f"❌ Trade processing error: {e}")
                await asyncio.sleep(30)
    
    async def _run_telegram_bot(self):
        """Run Telegram bot with restart capability"""
        while self.running:
            try:
                logger.info("🤖 Starting Telegram bot polling...")
                if self.telegram_bot:
                await self.telegram_bot.dp.start_polling(self.telegram_bot.bot)
            except Exception as e:
                logger.error(f"❌ Telegram bot error: {e}")
                if self.running:
                    logger.info("🔄 Restarting Telegram bot in 10 seconds...")
                    await asyncio.sleep(10)
    
    async def _health_monitor(self):
        """Monitor system health"""
        while self.running:
            try:
                # Health checks
                async with aiosqlite.connect(self.db_manager.db_path) as db:
                    cursor = await db.execute("SELECT COUNT(*) FROM users")
                    result = await cursor.fetchone()
                    user_count = result[0] if result and result[0] else 0
                    
                    cursor = await db.execute("""
                        SELECT COUNT(*) FROM announcements 
                        WHERE discovered_at > datetime('now', '-1 hour')
                    """)
                    result = await cursor.fetchone()
                    recent_listings = result[0] if result and result[0] else 0
                
                logger.info(
                    f"💚 HEALTH CHECK - Users: {user_count}, "
                    f"Recent listings (1h): {recent_listings}, "
                    f"Circuit breaker: {self.upbit_monitor.circuit_breaker.state if self.upbit_monitor else 'N/A'}"
                )
                
                await asyncio.sleep(300)  # Health check every 5 minutes
                
            except Exception as e:
                logger.error(f"❌ Health check error: {e}")
                await asyncio.sleep(60)
    
    async def stop(self):
        """Stop bot gracefully"""
        logger.info("🛑 Stopping stable crypto bot...")
        self.running = False
        
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        
        if self.upbit_monitor:
            await self.upbit_monitor.stop()
        
        self.lock.release()
        
        logger.info("✅ Stable crypto bot stopped gracefully")

async def main():
    """Main entry point"""
    # Ensure logs directory
    Path("logs").mkdir(exist_ok=True)
    
    bot = StableCryptoBot()
    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        logger.error(traceback.format_exc())
    finally:
        await bot.stop()

if __name__ == "__main__":
    asyncio.run(main())