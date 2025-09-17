#!/usr/bin/env python3
"""
🔄 AUTO-RESTART SUPERVISOR BOT
Sürekli çalışır bot supervisor - crash olursa otomatik restart
Upbit monitoring + Telegram bot'u sürekli canlı tutar
"""
import os
import sys
import time
import json
import subprocess
import logging
import threading
from datetime import datetime, timedelta

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('supervisor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SupervisorBot:
    def __init__(self):
        self.processes = {}
        self.restart_counts = {}
        self.last_health_check = {}
        self.restart_delays = {}  # Exponential backoff delays
        
        # Services to monitor
        self.services = {
            "telegram_bot": {
                "command": ["python3", "working_telegram_bot.py"],
                "description": "🤖 Telegram Bot",
                "max_restarts": 10,  # Max 10 restart per hour
                "restart_window": 3600,  # 1 hour window
                "health_file": "telegram_bot_health.txt"
            },
            "upbit_monitor": {
                "command": ["python3", "upbit_announcement_scraper.py"],
                "description": "👀 Upbit Monitor",
                "max_restarts": 5,
                "restart_window": 3600,
                "health_file": "upbit_monitor_health.txt"
            },
            "market_tracker": {
                "command": ["python3", "PERP/upbit_market_tracker.py"],
                "description": "📊 Market Tracker",
                "max_restarts": 5,
                "restart_window": 3600,
                "health_file": "market_tracker_health.txt"
            }
        }
        
        # Create health check files
        self.init_health_files()
        
    def init_health_files(self):
        """Initialize health check files"""
        for service_name, config in self.services.items():
            health_file = config.get("health_file")
            if health_file:
                try:
                    with open(health_file, 'w') as f:
                        f.write(f"{datetime.now().isoformat()}\n")
                except Exception as e:
                    logger.error(f"❌ Could not create health file {health_file}: {e}")
    
    def start_service(self, service_name):
        """Start a service"""
        if service_name not in self.services:
            logger.error(f"❌ Unknown service: {service_name}")
            return False
            
        config = self.services[service_name]
        
        # Check restart limits
        if not self.check_restart_limit(service_name):
            logger.error(f"❌ Service {service_name} exceeded restart limit")
            return False
            
        try:
            logger.info(f"🚀 Starting {config['description']}...")
            
            # Create log files for service output (prevents PIPE deadlock)
            stdout_file = f"logs/{service_name}_stdout.log"
            stderr_file = f"logs/{service_name}_stderr.log"
            
            # Ensure logs directory exists
            os.makedirs("logs", exist_ok=True)
            
            # Open files for output redirection
            with open(stdout_file, 'a') as stdout_f, open(stderr_file, 'a') as stderr_f:
                process = subprocess.Popen(
                    config["command"],
                    stdout=stdout_f,
                    stderr=stderr_f,
                    cwd=os.getcwd()
                )
            
            self.processes[service_name] = process
            self.record_restart(service_name)
            
            logger.info(f"✅ {config['description']} started (PID: {process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start {service_name}: {e}")
            return False
    
    def check_restart_limit(self, service_name):
        """Check if service can be restarted (rate limiting)"""
        if service_name not in self.restart_counts:
            return True
            
        config = self.services[service_name]
        max_restarts = config.get("max_restarts", 5)
        restart_window = config.get("restart_window", 3600)
        
        # Clean old restart records
        now = datetime.now()
        cutoff = now - timedelta(seconds=restart_window)
        
        self.restart_counts[service_name] = [
            restart_time for restart_time in self.restart_counts[service_name]
            if restart_time > cutoff
        ]
        
        return len(self.restart_counts[service_name]) < max_restarts
    
    def record_restart(self, service_name):
        """Record restart timestamp and update exponential backoff"""
        if service_name not in self.restart_counts:
            self.restart_counts[service_name] = []
        
        self.restart_counts[service_name].append(datetime.now())
        
        # Exponential backoff: increase delay after each restart
        if service_name not in self.restart_delays:
            self.restart_delays[service_name] = 1  # Start with 1 second
        else:
            # Double the delay, max 60 seconds
            self.restart_delays[service_name] = min(self.restart_delays[service_name] * 2, 60)
    
    def reset_restart_delay(self, service_name):
        """Reset restart delay after successful run"""
        if service_name in self.restart_delays:
            self.restart_delays[service_name] = 1
    
    def is_service_running(self, service_name):
        """Check if service is running"""
        if service_name not in self.processes:
            return False
            
        process = self.processes[service_name]
        return process.poll() is None
    
    def stop_service(self, service_name):
        """Stop a service"""
        if service_name not in self.processes:
            return
            
        process = self.processes[service_name]
        if process.poll() is None:
            logger.info(f"🛑 Stopping {service_name}...")
            process.terminate()
            
            # Wait 5 seconds for graceful shutdown
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning(f"⚠️ Force killing {service_name}...")
                process.kill()
                
        del self.processes[service_name]
    
    def health_check(self, service_name):
        """Check service health via health file"""
        config = self.services[service_name]
        health_file = config.get("health_file")
        
        if not health_file or not os.path.exists(health_file):
            return False
            
        try:
            with open(health_file, 'r') as f:
                last_update = f.read().strip()
                last_time = datetime.fromisoformat(last_update)
                
            # Health check: file updated within last 5 minutes
            if datetime.now() - last_time < timedelta(minutes=5):
                return True
            else:
                logger.warning(f"⚠️ {service_name} health check stale (last: {last_time})")
                return False
                
        except Exception as e:
            logger.error(f"❌ Health check failed for {service_name}: {e}")
            return False
    
    def monitor_services(self):
        """Monitor all services and restart if needed"""
        while True:
            try:
                for service_name in self.services.keys():
                    if not self.is_service_running(service_name):
                        logger.warning(f"⚠️ Service {service_name} is not running")
                        
                        # Apply exponential backoff before restart
                        delay = self.restart_delays.get(service_name, 1)
                        logger.info(f"⏳ Applying exponential backoff: {delay}s before restarting {service_name}")
                        time.sleep(delay)
                        
                        self.start_service(service_name)
                    else:
                        # Service is running successfully - reset delay
                        self.reset_restart_delay(service_name)
                        
                        # Check health
                        if not self.health_check(service_name):
                            logger.warning(f"⚠️ Service {service_name} failed health check, restarting...")
                            self.stop_service(service_name)
                            
                            # Apply exponential backoff before restart
                            delay = self.restart_delays.get(service_name, 1)
                            logger.info(f"⏳ Health check failed, applying backoff: {delay}s before restarting {service_name}")
                            time.sleep(delay)
                            
                            self.start_service(service_name)
                
                # Send periodic status update
                self.send_status_update()
                
            except Exception as e:
                logger.error(f"❌ Monitor error: {e}")
            
            # Check every 60 seconds
            time.sleep(60)
    
    def send_status_update(self):
        """Send periodic status update (every 30 minutes)"""
        try:
            # Only send update every 30 minutes
            if not hasattr(self, 'last_status_update'):
                self.last_status_update = datetime.now()
                return
                
            if datetime.now() - self.last_status_update < timedelta(minutes=30):
                return
            
            self.last_status_update = datetime.now()
            
            # Create status message
            running_services = []
            failed_services = []
            
            for service_name, config in self.services.items():
                if self.is_service_running(service_name):
                    running_services.append(config['description'])
                else:
                    failed_services.append(config['description'])
            
            status_msg = f"""
🤖 **AUTO-SUPERVISOR STATUS**

✅ **Running:** {', '.join(running_services) if running_services else 'None'}
❌ **Failed:** {', '.join(failed_services) if failed_services else 'None'}

📊 **Uptime:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
🔄 **Auto-restart:** Active
"""
            
            # Write status to file (Telegram bot can read this)
            with open('supervisor_status.txt', 'w') as f:
                f.write(status_msg)
            
            logger.info(f"📊 Status update: {len(running_services)} running, {len(failed_services)} failed")
            
        except Exception as e:
            logger.error(f"❌ Status update error: {e}")
    
    def start_all_services(self):
        """Start all services"""
        logger.info("🚀 AUTO-RESTART SUPERVISOR STARTING...")
        logger.info("=" * 50)
        
        for service_name in self.services.keys():
            self.start_service(service_name)
            time.sleep(2)  # Stagger startup
        
        logger.info("✅ All services started")
        logger.info("🔍 Monitoring enabled - services will auto-restart")
    
    def stop_all_services(self):
        """Stop all services"""
        logger.info("🛑 Stopping all services...")
        for service_name in list(self.processes.keys()):
            self.stop_service(service_name)
        logger.info("✅ All services stopped")

def main():
    supervisor = SupervisorBot()
    
    try:
        # Start all services
        supervisor.start_all_services()
        
        # Start monitoring in background
        monitor_thread = threading.Thread(target=supervisor.monitor_services, daemon=True)
        monitor_thread.start()
        
        # Keep main thread alive
        logger.info("🔄 AUTO-RESTART SUPERVISOR RUNNING")
        logger.info("⚡ Bot'lar sürekli canlı tutulacak!")
        
        while True:
            time.sleep(60)
            
    except KeyboardInterrupt:
        logger.info("🛑 Shutdown signal received")
        supervisor.stop_all_services()
        
    except Exception as e:
        logger.error(f"💥 Supervisor crashed: {e}")
        supervisor.stop_all_services()
        raise

if __name__ == "__main__":
    main()