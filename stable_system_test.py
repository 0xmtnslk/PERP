#!/usr/bin/env python3
"""
🚀 STABLE SYSTEM TEST - Without Redis Dependency
Testing the core stable architecture with in-memory queues
"""
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
import aiosqlite
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import Command
import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from tenacity import retry, stop_after_attempt, wait_exponential
import json
import uuid
import traceback
from queue import Queue
import threading

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/stable_test.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class InMemoryQueue:
    """Simple in-memory queue for testing"""
    def __init__(self):
        self._queues = {}
        self._lock = threading.Lock()
    
    def put(self, queue_name: str, data: dict):
        with self._lock:
            if queue_name not in self._queues:
                self._queues[queue_name] = []
            self._queues[queue_name].append(data)
            logger.debug(f"📝 Queued to {queue_name}: {data}")
    
    def get(self, queue_name: str) -> Optional[dict]:
        with self._lock:
            if queue_name in self._queues and self._queues[queue_name]:
                return self._queues[queue_name].pop(0)
        return None
    
    def get_all(self, queue_name: str) -> List[dict]:
        with self._lock:
            if queue_name in self._queues:
                items = self._queues[queue_name].copy()
                self._queues[queue_name].clear()
                return items
        return []

class DatabaseManager:
    """Simplified database manager"""
    
    def __init__(self, db_path: str = "stable_test.db"):
        self.db_path = db_path
    
    async def initialize(self):
        """Initialize test database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            
            # Simple users table
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    auto_trading BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Announcements
            await db.execute("""
                CREATE TABLE IF NOT EXISTS announcements (
                    id TEXT PRIMARY KEY,
                    token TEXT NOT NULL,
                    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT false
                )
            """)
            
            await db.commit()
            logger.info("✅ Test database initialized")
    
    async def add_test_user(self, user_id: int, username: str = "test_user"):
        """Add test user"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO users (user_id, username, auto_trading)
                VALUES (?, ?, ?)
            """, (user_id, username, True))
            await db.commit()
            logger.info(f"✅ Test user {user_id} added")
    
    async def get_active_users(self) -> List[int]:
        """Get users with auto-trading enabled"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT user_id FROM users WHERE auto_trading = true")
            users = await cursor.fetchall()
            return [row[0] for row in users]

class StableUpbitMonitor:
    """Stable Upbit monitor - simplified version"""
    
    def __init__(self, queue_manager: InMemoryQueue, db_manager: DatabaseManager):
        self.queue_manager = queue_manager
        self.db_manager = db_manager
        self.session = None
        self.last_known_tokens = set()
    
    async def start(self):
        """Start monitoring"""
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10))
        logger.info("🔍 Stable Upbit Monitor started")
    
    async def stop(self):
        """Stop monitoring"""
        if self.session:
            await self.session.close()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=5)
    )
    async def check_new_listings(self):
        """Check for new KRW listings"""
        if not self.session:
            return
        
        try:
            url = "https://api.upbit.com/v1/market/all"
            async with self.session.get(url) as response:
                if response.status != 200:
                    raise Exception(f"HTTP {response.status}")
                
                markets = await response.json()
                krw_tokens = {
                    market['market'].replace('KRW-', '') 
                    for market in markets 
                    if market['market'].startswith('KRW-')
                }
                
                # Find new tokens
                new_tokens = krw_tokens - self.last_known_tokens
                
                if new_tokens:
                    logger.info(f"🚨 NEW TOKENS DETECTED: {new_tokens}")
                    
                    for token in new_tokens:
                        # Store in database
                        announcement_id = f"listing_{token}_{int(datetime.now().timestamp())}"
                        
                        async with aiosqlite.connect(self.db_manager.db_path) as db:
                            await db.execute("""
                                INSERT INTO announcements (id, token, discovered_at)
                                VALUES (?, ?, ?)
                            """, (
                                announcement_id, 
                                token, 
                                datetime.now(timezone.utc)
                            ))
                            await db.commit()
                        
                        # Queue for processing
                        self.queue_manager.put("new_listings", {
                            "announcement_id": announcement_id,
                            "token": token,
                            "timestamp": datetime.now().isoformat()
                        })
                
                # Update last known tokens (first run)
                if not self.last_known_tokens:
                    self.last_known_tokens = krw_tokens
                    logger.info(f"📊 Initialized with {len(krw_tokens)} KRW tokens")
                else:
                    self.last_known_tokens = krw_tokens
                
                logger.info(f"✅ Upbit check completed - {len(krw_tokens)} KRW tokens monitored")
                
        except Exception as e:
            logger.error(f"❌ Upbit monitor error: {e}")
            raise

class SimpleTelegramBot:
    """Simplified Telegram bot for testing"""
    
    def __init__(self, token: str, queue_manager: InMemoryQueue, db_manager: DatabaseManager):
        self.bot = Bot(token=token)
        self.dp = Dispatcher()
        self.queue_manager = queue_manager
        self.db_manager = db_manager
        self._register_handlers()
    
    def _register_handlers(self):
        """Register handlers"""
        self.dp.message.register(self.start_command, Command("start"))
        self.dp.message.register(self.status_command, Command("status"))
        self.dp.message.register(self.test_command, Command("test"))
    
    async def start_command(self, message: Message):
        """Handle /start"""
        user_id = message.from_user.id if message.from_user else 0
        username = message.from_user.username if message.from_user and message.from_user.username else "unknown"
        
        # Add to database
        await self.db_manager.add_test_user(user_id, username)
        
        await message.reply(
            "🚀 **Stable Crypto Trading Bot - TEST MODE**\n\n"
            "✅ You are now registered for auto-trading\n"
            "🤖 System will detect new Upbit KRW listings\n\n"
            "Commands:\n"
            "/status - Check system status\n"
            "/test - Simulate new token detection"
        )
    
    async def status_command(self, message: Message):
        """Handle /status"""
        active_users = await self.db_manager.get_active_users()
        
        await message.reply(
            f"📊 **System Status**\n\n"
            f"👥 Active users: {len(active_users)}\n"
            f"🔍 Monitoring: Upbit KRW markets\n"
            f"🚀 System: STABLE & RUNNING\n"
            f"⏱️ Check interval: 1 minute"
        )
    
    async def test_command(self, message: Message):
        """Simulate token detection for testing"""
        test_token = f"TEST{datetime.now().strftime('%M%S')}"
        
        # Simulate new listing
        self.queue_manager.put("new_listings", {
            "announcement_id": f"test_{test_token}_{int(datetime.now().timestamp())}",
            "token": test_token,
            "timestamp": datetime.now().isoformat()
        })
        
        await message.reply(f"🧪 **Test triggered**\n\nSimulated new token: {test_token}")
        
        logger.info(f"🧪 Test token simulation: {test_token}")

class StableTestSystem:
    """Main stable test system"""
    
    def __init__(self):
        self.running = True
        self.queue_manager = InMemoryQueue()
        self.db_manager = DatabaseManager()
        self.upbit_monitor = None
        self.telegram_bot = None
        self.scheduler = AsyncIOScheduler()
        
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"📡 Received signal {signum}, shutting down...")
        self.running = False
    
    async def start(self):
        """Start stable test system"""
        try:
            logger.info("🚀 STABLE TEST SYSTEM STARTING")
            
            # Initialize database
            await self.db_manager.initialize()
            
            # Initialize components
            self.upbit_monitor = StableUpbitMonitor(self.queue_manager, self.db_manager)
            await self.upbit_monitor.start()
            
            # Initialize Telegram bot if token available
            telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
            if telegram_token:
                self.telegram_bot = SimpleTelegramBot(telegram_token, self.queue_manager, self.db_manager)
                logger.info("✅ Telegram bot initialized")
            else:
                logger.warning("⚠️ No Telegram token - running without bot")
            
            # Schedule monitoring
            self.scheduler.add_job(
                self.upbit_monitor.check_new_listings,
                'interval',
                minutes=1,
                id='upbit_check'
            )
            self.scheduler.start()
            logger.info("✅ Scheduler started - checking every 1 minute")
            
            # Start tasks
            tasks = []
            
            if self.telegram_bot:
                tasks.append(self._run_telegram_bot())
            
            tasks.extend([
                self._process_new_listings(),
                self._system_health_monitor()
            ])
            
            logger.info("🏭 STABLE TEST SYSTEM RUNNING")
            await asyncio.gather(*tasks)
            
        except Exception as e:
            logger.error(f"❌ System error: {e}")
            logger.error(traceback.format_exc())
            await self.stop()
    
    async def _run_telegram_bot(self):
        """Run Telegram bot polling"""
        try:
            if self.telegram_bot:
                await self.telegram_bot.dp.start_polling(self.telegram_bot.bot)
        except Exception as e:
            logger.error(f"❌ Telegram bot error: {e}")
            # Auto restart after delay
            await asyncio.sleep(10)
            if self.running:
                await self._run_telegram_bot()
    
    async def _process_new_listings(self):
        """Process new listing notifications"""
        while self.running:
            try:
                # Get new listings from queue
                listings = self.queue_manager.get_all("new_listings")
                
                for listing in listings:
                    await self._handle_new_listing(listing)
                
                await asyncio.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"❌ Listing processing error: {e}")
                await asyncio.sleep(10)
    
    async def _handle_new_listing(self, listing: dict):
        """Handle new token listing"""
        token = listing['token']
        announcement_id = listing['announcement_id']
        
        logger.info(f"🎯 PROCESSING NEW LISTING: {token}")
        
        # Get active users
        active_users = await self.db_manager.get_active_users()
        
        if not active_users:
            logger.warning("⚠️ No active users for trading")
            return
        
        # Simulate trade creation for each user
        for user_id in active_users:
            trade_id = str(uuid.uuid4())
            
            # In real system, this would create Bitget orders
            logger.info(f"💰 WOULD CREATE TRADE: User {user_id} -> {token} (ID: {trade_id[:8]})")
            
            # Send notification if Telegram bot available
            if self.telegram_bot:
                try:
                    await self.telegram_bot.bot.send_message(
                        user_id,
                        f"🚀 **NEW LISTING DETECTED**\n\n"
                        f"Token: **{token}**\n"
                        f"Exchange: Upbit KRW\n"
                        f"Time: {datetime.now().strftime('%H:%M:%S')}\n\n"
                        f"💰 Trade simulation: LONG position would be opened\n"
                        f"📊 Trade ID: {trade_id[:8]}\n\n"
                        f"⚠️ TEST MODE - No real trades executed"
                    )
                except Exception as e:
                    logger.error(f"❌ Failed to send notification to {user_id}: {e}")
        
        logger.info(f"✅ Processed listing {token} for {len(active_users)} users")
    
    async def _system_health_monitor(self):
        """Monitor system health"""
        while self.running:
            try:
                # Health checks
                uptime = datetime.now().isoformat()
                active_users = await self.db_manager.get_active_users()
                
                logger.info(f"💚 SYSTEM HEALTHY - {len(active_users)} users, uptime: {uptime}")
                
                await asyncio.sleep(60)  # Health check every minute
                
            except Exception as e:
                logger.error(f"❌ Health check error: {e}")
                await asyncio.sleep(30)
    
    async def stop(self):
        """Stop system gracefully"""
        logger.info("🛑 Stopping stable test system...")
        self.running = False
        
        if self.scheduler.running:
            self.scheduler.shutdown()
        
        if self.upbit_monitor:
            await self.upbit_monitor.stop()
        
        logger.info("✅ System stopped gracefully")

async def main():
    """Main entry point"""
    Path("logs").mkdir(exist_ok=True)
    
    system = StableTestSystem()
    try:
        await system.start()
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        logger.error(traceback.format_exc())
    finally:
        await system.stop()

if __name__ == "__main__":
    asyncio.run(main())