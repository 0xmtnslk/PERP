#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Robust Inter-Process Communication System
Kripto ticaret sistemi bileşenleri arasında güvenli ve güvenilir mesajlaşma
"""
import os
import json
import time
import uuid
import fcntl
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class MessageType:
    """Mesaj tipleri enum'u"""
    NEW_COIN_ALERT = "new_coin_alert"
    TELEGRAM_NOTIFICATION = "telegram_notification"
    TRADING_COMMAND = "trading_command"
    EMERGENCY_STOP = "emergency_stop"
    API_KEY_UPDATE = "api_key_update"
    SYSTEM_STATUS = "system_status"
    HEARTBEAT = "heartbeat"

class Message:
    """IPC mesaj sınıfı"""
    
    def __init__(self, message_type: str, data: Dict[str, Any], 
                 sender: str = "unknown", priority: int = 5):
        self.id = str(uuid.uuid4())
        self.type = message_type
        self.data = data
        self.sender = sender
        self.priority = priority  # 1=highest, 10=lowest
        self.timestamp = datetime.now().isoformat()
        self.processed = False
        self.attempts = 0
        self.max_attempts = 3
    
    def to_dict(self) -> Dict:
        """Mesajı dictionary'ye çevir"""
        return {
            'id': self.id,
            'type': self.type,
            'data': self.data,
            'sender': self.sender,
            'priority': self.priority,
            'timestamp': self.timestamp,
            'processed': self.processed,
            'attempts': self.attempts,
            'max_attempts': self.max_attempts
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Message':
        """Dictionary'den mesaj oluştur"""
        msg = cls(
            message_type=data['type'],
            data=data['data'],
            sender=data['sender'],
            priority=data['priority']
        )
        msg.id = data['id']
        msg.timestamp = data['timestamp']
        msg.processed = data.get('processed', False)
        msg.attempts = data.get('attempts', 0)
        msg.max_attempts = data.get('max_attempts', 3)
        return msg

class IPCQueue:
    """Thread-safe IPC mesaj kuyruğu"""
    
    def __init__(self, queue_dir: str = "ipc_queues"):
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(exist_ok=True)
        self.lock_timeout = 5.0  # saniye
        self.message_handlers: Dict[str, List[Callable]] = {}
        self.running = False
        self.worker_thread = None
        
        # Alt dizinler
        (self.queue_dir / "pending").mkdir(exist_ok=True)
        (self.queue_dir / "processing").mkdir(exist_ok=True)
        (self.queue_dir / "completed").mkdir(exist_ok=True)
        (self.queue_dir / "failed").mkdir(exist_ok=True)
        
        logger.info(f"🔄 IPC Queue initialized: {self.queue_dir}")
    
    def _get_lock_file(self, message_id: str) -> Path:
        """Mesaj için lock dosyası yolu"""
        return self.queue_dir / f"{message_id}.lock"
    
    def _acquire_lock(self, message_id: str) -> Optional[object]:
        """Mesaj için lock al"""
        lock_file = self._get_lock_file(message_id)
        try:
            lock_fd = open(lock_file, 'w')
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            lock_fd.write(f"{os.getpid()}\\n{datetime.now().isoformat()}")
            lock_fd.flush()
            return lock_fd
        except (IOError, OSError):
            return None
    
    def _release_lock(self, lock_fd):
        """Lock'u serbest bırak"""
        if lock_fd:
            try:
                fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
                lock_fd.close()
                # Lock dosyasını sil
                lock_file = Path(lock_fd.name)
                if lock_file.exists():
                    lock_file.unlink()
            except:
                pass
    
    def send_message(self, message: Message) -> bool:
        """Mesaj gönder"""
        try:
            # Öncelik bazlı dosya adı (düşük sayı = yüksek öncelik)
            priority_prefix = f"{message.priority:02d}"
            timestamp_ms = int(time.time() * 1000)
            filename = f"{priority_prefix}_{timestamp_ms}_{message.id}.json"
            
            message_file = self.queue_dir / "pending" / filename
            
            # Atomik yazma için geçici dosya kullan
            temp_file = message_file.with_suffix('.tmp')
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(message.to_dict(), f, indent=2, ensure_ascii=False)
            
            # Atomik rename
            temp_file.rename(message_file)
            
            logger.info(f"📤 Message sent: {message.type} from {message.sender} (ID: {message.id[:8]})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send message: {e}")
            return False
    
    def register_handler(self, message_type: str, handler: Callable[[Message], bool]):
        """Mesaj tipi için handler kaydet"""
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []
        self.message_handlers[message_type].append(handler)
        logger.info(f"🔧 Handler registered for message type: {message_type}")
    
    def _process_message(self, message: Message) -> bool:
        """Tek mesajı işle"""
        handlers = self.message_handlers.get(message.type, [])
        if not handlers:
            logger.warning(f"⚠️ No handlers for message type: {message.type}")
            return False
        
        success = True
        for handler in handlers:
            try:
                result = handler(message)
                if not result:
                    success = False
                    logger.warning(f"⚠️ Handler failed for message {message.id[:8]}")
            except Exception as e:
                logger.error(f"❌ Handler error for message {message.id[:8]}: {e}")
                success = False
        
        return success
    
    def _worker_loop(self):
        """Ana işleyici döngüsü"""
        while self.running:
            try:
                # Pending mesajları al (öncelik sırasına göre)
                pending_files = sorted(self.queue_dir.glob("pending/*.json"))
                
                for message_file in pending_files:
                    if not self.running:
                        break
                    
                    try:
                        # Mesajı oku
                        with open(message_file, 'r', encoding='utf-8') as f:
                            message_data = json.load(f)
                        
                        message = Message.from_dict(message_data)
                        
                        # Lock al
                        lock_fd = self._acquire_lock(message.id)
                        if not lock_fd:
                            continue  # Başka process işliyor
                        
                        try:
                            # Processing klasörüne taşı
                            processing_file = self.queue_dir / "processing" / message_file.name
                            message_file.rename(processing_file)
                            
                            # Mesajı işle
                            message.attempts += 1
                            success = self._process_message(message)
                            
                            if success:
                                # Başarılı - completed'a taşı
                                message.processed = True
                                completed_file = self.queue_dir / "completed" / message_file.name
                                with open(completed_file, 'w', encoding='utf-8') as f:
                                    json.dump(message.to_dict(), f, indent=2, ensure_ascii=False)
                                processing_file.unlink()
                                logger.info(f"✅ Message processed successfully: {message.id[:8]}")
                                
                            else:
                                # Başarısız - yeniden dene veya failed'a taşı
                                if message.attempts >= message.max_attempts:
                                    failed_file = self.queue_dir / "failed" / message_file.name
                                    with open(failed_file, 'w', encoding='utf-8') as f:
                                        json.dump(message.to_dict(), f, indent=2, ensure_ascii=False)
                                    processing_file.unlink()
                                    logger.error(f"❌ Message failed permanently: {message.id[:8]}")
                                else:
                                    # Yeniden pending'e al
                                    with open(message_file, 'w', encoding='utf-8') as f:
                                        json.dump(message.to_dict(), f, indent=2, ensure_ascii=False)
                                    processing_file.unlink()
                                    logger.warning(f"🔄 Message retry {message.attempts}/{message.max_attempts}: {message.id[:8]}")
                        
                        finally:
                            self._release_lock(lock_fd)
                    
                    except Exception as e:
                        logger.error(f"❌ Error processing message {message_file}: {e}")
                
                # Kısa bekleme
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"❌ Worker loop error: {e}")
                time.sleep(1)
    
    def start(self):
        """IPC sistemini başlat"""
        if self.running:
            return
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self.worker_thread.start()
        logger.info("🚀 IPC Queue started")
    
    def stop(self):
        """IPC sistemini durdur"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("🛑 IPC Queue stopped")
    
    def cleanup_old_messages(self, max_age_hours: int = 24):
        """Eski mesajları temizle"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        cleaned_count = 0
        
        for directory in ["completed", "failed"]:
            for message_file in (self.queue_dir / directory).glob("*.json"):
                try:
                    if message_file.stat().st_mtime < cutoff_time:
                        message_file.unlink()
                        cleaned_count += 1
                except:
                    pass
        
        logger.info(f"🧹 Cleaned {cleaned_count} old messages")
        return cleaned_count
    
    def get_queue_stats(self) -> Dict[str, int]:
        """Kuyruk istatistiklerini getir"""
        stats = {}
        for directory in ["pending", "processing", "completed", "failed"]:
            count = len(list((self.queue_dir / directory).glob("*.json")))
            stats[directory] = count
        return stats

# Global IPC instance
ipc_queue = IPCQueue()

# Convenience functions
def send_new_coin_alert(symbol: str, exchange: str = "upbit", sender: str = "scraper") -> bool:
    """Yeni coin uyarısı gönder"""
    message = Message(
        message_type=MessageType.NEW_COIN_ALERT,
        data={
            'symbol': symbol,
            'exchange': exchange,
            'timestamp': datetime.now().isoformat()
        },
        sender=sender,
        priority=2  # Yüksek öncelik
    )
    return ipc_queue.send_message(message)

def send_telegram_notification(notification_data: Dict, sender: str = "system") -> bool:
    """Telegram bildirimi gönder"""
    message = Message(
        message_type=MessageType.TELEGRAM_NOTIFICATION,
        data=notification_data,
        sender=sender,
        priority=3
    )
    return ipc_queue.send_message(message)

def send_emergency_stop(reason: str, sender: str = "system") -> bool:
    """Acil durdurma komutu gönder"""
    message = Message(
        message_type=MessageType.EMERGENCY_STOP,
        data={'reason': reason, 'timestamp': datetime.now().isoformat()},
        sender=sender,
        priority=1  # En yüksek öncelik
    )
    return ipc_queue.send_message(message)

def send_system_status(status_data: Dict, sender: str = "coordinator") -> bool:
    """Sistem durumu gönder"""
    message = Message(
        message_type=MessageType.SYSTEM_STATUS,
        data=status_data,
        sender=sender,
        priority=8  # Düşük öncelik
    )
    return ipc_queue.send_message(message)

if __name__ == "__main__":
    # Test the IPC system
    import signal
    import sys
    
    def signal_handler(sig, frame):
        print("\\n🛑 Stopping IPC system...")
        ipc_queue.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Test handlers
    def test_new_coin_handler(message: Message) -> bool:
        print(f"🪙 New coin alert: {message.data['symbol']} from {message.data['exchange']}")
        return True
    
    def test_telegram_handler(message: Message) -> bool:
        print(f"📱 Telegram notification: {message.data}")
        return True
    
    # Register test handlers
    ipc_queue.register_handler(MessageType.NEW_COIN_ALERT, test_new_coin_handler)
    ipc_queue.register_handler(MessageType.TELEGRAM_NOTIFICATION, test_telegram_handler)
    
    # Start IPC system
    ipc_queue.start()
    
    print("🔄 IPC System Test Started")
    print("Queue stats:", ipc_queue.get_queue_stats())
    
    # Send test messages
    send_new_coin_alert("TESTUSDT_UMCBL", "upbit", "test_scraper")
    send_telegram_notification({"title": "Test", "message": "Hello World"}, "test_bot")
    
    print("💤 Waiting for messages to process... (Press Ctrl+C to exit)")
    
    try:
        while True:
            time.sleep(5)
            stats = ipc_queue.get_queue_stats()
            print(f"📊 Queue stats: {stats}")
    except KeyboardInterrupt:
        pass