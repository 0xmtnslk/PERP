#!/usr/bin/env python3
"""
⚡ IMMORTAL TRADING SYSTEM
Replit workflow sistemini bypass eder - asla durmaz!
"""
import os
import sys
import time
import subprocess
import signal
import threading
import logging
from datetime import datetime
import json

# Setup logging
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - IMMORTAL - %(message)s',
    handlers=[
        logging.FileHandler('logs/immortal_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('IMMORTAL')

class ImmortalTradingSystem:
    def __init__(self):
        self.running = True
        self.processes = {}
        self.restart_counts = {}
        self.services = {
            'telegram_bot': {
                'cmd': ['python3', 'production/core/working_telegram_bot.py'],
                'name': '🤖 Telegram Bot',
                'health_file': 'production/monitoring/telegram_bot_health.txt'
            },
            'upbit_monitor': {
                'cmd': ['python3', 'production/core/upbit_announcement_scraper.py'],
                'name': '👀 Upbit Monitor',
                'health_file': 'production/monitoring/upbit_monitor_health.txt'
            },
            'market_tracker': {
                'cmd': ['python3', 'production/exchanges/PERP/upbit_market_tracker.py'],
                'name': '📊 Market Tracker',
                'health_file': 'production/monitoring/market_tracker_health.txt'
            },
            'trading_engine': {
                'cmd': ['python3', 'production/core/user_trading_engine.py'],
                'name': '🚀 Trading Engine',
                'health_file': 'production/monitoring/user_trading_engine_health.txt'
            }
        }
        
        # Signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        logger.info("⚡ IMMORTAL TRADING SYSTEM INITIALIZED")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown gracefully"""
        logger.info(f"📡 Received signal {signum}, shutting down...")
        self.running = False
        self.stop_all_services()
        sys.exit(0)
    
    def start_service(self, service_name):
        """Start a service"""
        try:
            config = self.services[service_name]
            
            # Kill existing instances first
            self.kill_existing_instances(service_name)
            
            logger.info(f"🚀 Starting {config['name']}")
            
            # Create log files for service
            os.makedirs('logs/services', exist_ok=True)
            stdout_log = open(f'logs/services/{service_name}_stdout.log', 'a')
            stderr_log = open(f'logs/services/{service_name}_stderr.log', 'a')
            
            process = subprocess.Popen(
                config['cmd'],
                stdout=stdout_log,
                stderr=stderr_log,
                preexec_fn=os.setsid
            )
            
            self.processes[service_name] = {
                'process': process,
                'start_time': time.time(),
                'stdout_log': stdout_log,
                'stderr_log': stderr_log
            }
            
            self.restart_counts[service_name] = self.restart_counts.get(service_name, 0) + 1
            
            logger.info(f"✅ {config['name']} started (PID: {process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start {service_name}: {e}")
            return False
    
    def kill_existing_instances(self, service_name):
        """Kill existing instances of service"""
        try:
            config = self.services[service_name]
            script_path = config['cmd'][1]  # Get script path
            
            # Find processes running this script
            result = subprocess.run(
                ["pgrep", "-f", script_path],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                pids = [pid.strip() for pid in result.stdout.split('\n') if pid.strip()]
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                        time.sleep(2)
                        os.kill(int(pid), signal.SIGKILL)
                    except:
                        pass
                        
        except Exception as e:
            logger.error(f"❌ Error killing existing {service_name}: {e}")
    
    def is_service_healthy(self, service_name):
        """Check if service is healthy"""
        try:
            config = self.services[service_name]
            
            # Check if process is running
            if service_name not in self.processes:
                return False
                
            process_info = self.processes[service_name]
            process = process_info['process']
            
            if process.poll() is not None:
                return False
            
            # Check health file age
            health_file = config['health_file']
            if os.path.exists(health_file):
                file_age = time.time() - os.path.getmtime(health_file)
                return file_age < 300  # 5 minutes
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Health check error for {service_name}: {e}")
            return False
    
    def stop_service(self, service_name):
        """Stop a service gracefully"""
        try:
            if service_name not in self.processes:
                return
                
            process_info = self.processes[service_name]
            process = process_info['process']
            
            logger.info(f"🛑 Stopping {self.services[service_name]['name']}")
            
            # Try graceful termination first
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                process.wait()
            except ProcessLookupError:
                pass
            
            # Close log files
            process_info['stdout_log'].close()
            process_info['stderr_log'].close()
            
            del self.processes[service_name]
            logger.info(f"✅ {self.services[service_name]['name']} stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping {service_name}: {e}")
    
    def stop_all_services(self):
        """Stop all services"""
        for service_name in list(self.processes.keys()):
            self.stop_service(service_name)
    
    def start_all_services(self):
        """Start all services"""
        logger.info("🚀 STARTING ALL SERVICES")
        for service_name in self.services:
            self.start_service(service_name)
            time.sleep(3)  # Stagger starts
    
    def monitor_services(self):
        """Monitor and restart services as needed"""
        logger.info("🔍 SERVICE MONITORING STARTED")
        
        while self.running:
            try:
                status_report = []
                failed_services = []
                
                for service_name in self.services:
                    if self.is_service_healthy(service_name):
                        status_report.append(self.services[service_name]['name'])
                    else:
                        failed_services.append(service_name)
                
                if failed_services:
                    logger.warning(f"💔 Failed services: {[self.services[s]['name'] for s in failed_services]}")
                    for service_name in failed_services:
                        logger.info(f"🔄 Restarting {self.services[service_name]['name']}")
                        self.start_service(service_name)
                        time.sleep(5)
                
                # Status report every 10 minutes
                if int(time.time()) % 600 == 0:
                    logger.info(f"📊 RUNNING: {', '.join(status_report)}")
                    if failed_services:
                        logger.warning(f"📊 FAILED: {', '.join([self.services[s]['name'] for s in failed_services])}")
                
                time.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"❌ Monitor error: {e}")
                time.sleep(60)
    
    def self_restart_timer(self):
        """Self-restart every 12 hours to prevent memory leaks"""
        time.sleep(12 * 3600)  # 12 hours
        logger.info("🔄 12-hour self-restart")
        self.stop_all_services()
        os.execv(sys.executable, ['python3'] + sys.argv)
    
    def run(self):
        """Main run loop"""
        logger.info("⚡ IMMORTAL TRADING SYSTEM STARTING")
        logger.info("🎯 Mission: Never stop, regardless of Replit limitations")
        
        # Start self-restart timer
        threading.Thread(target=self.self_restart_timer, daemon=True).start()
        
        # Start all services
        self.start_all_services()
        
        # Start monitoring
        self.monitor_services()

if __name__ == "__main__":
    try:
        system = ImmortalTradingSystem()
        system.run()
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        # Auto-restart on crash
        time.sleep(5)
        os.execv(sys.executable, ['python3'] + sys.argv)