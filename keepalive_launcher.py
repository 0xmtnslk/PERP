#!/usr/bin/env python3
"""
🔄 SELF-RESTARTING KEEPALIVE LAUNCHER
Replit workflow kapansa bile kendini restart eder
"""
import os
import sys
import time
import subprocess
import logging
import signal
from datetime import datetime
import threading

# Minimal logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - KEEPALIVE - %(message)s')
logger = logging.getLogger('KEEPALIVE')

class KeepaliveLauncher:
    def __init__(self):
        self.running = True
        self.main_process = None
        
        # Signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
    def signal_handler(self, signum, frame):
        logger.info(f"🛑 Received signal {signum}")
        self.running = False
        if self.main_process:
            try:
                self.main_process.terminate()
                self.main_process.wait(timeout=5)
            except:
                pass
        sys.exit(0)
    
    def restart_workflow(self):
        """Force restart the Replit workflow"""
        try:
            logger.info("🔄 Restarting workflow...")
            
            # Kill existing launcher processes
            subprocess.run(["pkill", "-f", "launcher.py"], check=False)
            time.sleep(2)
            
            # Restart workflow using Replit's workflow system
            subprocess.run([
                "python3", "-c", 
                """
import subprocess
import time

# Start our main launcher
subprocess.Popen(['python3', 'launcher.py'], 
                 stdout=open('launcher.log', 'a'),
                 stderr=subprocess.STDOUT)
                """
            ], check=False)
            
            logger.info("✅ Workflow restart attempted")
            return True
            
        except Exception as e:
            logger.error(f"❌ Workflow restart failed: {e}")
            return False
    
    def check_system_health(self):
        """Check if main launcher and services are running"""
        try:
            # Check if launcher.py process exists
            result = subprocess.run(["pgrep", "-f", "launcher.py"], 
                                  capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.warning("⚠️ Main launcher not found")
                return False
                
            # Check if services are running by checking health files
            health_files = [
                "production/monitoring/supervisor_heartbeat.txt",
                "production/monitoring/telegram_bot_health.txt", 
                "production/monitoring/upbit_monitor_health.txt",
                "production/monitoring/market_tracker_health.txt",
                "production/monitoring/user_trading_engine_health.txt"
            ]
            
            current_time = time.time()
            stale_count = 0
            
            for health_file in health_files:
                if os.path.exists(health_file):
                    file_age = current_time - os.path.getmtime(health_file)
                    if file_age > 300:  # 5 minutes old
                        stale_count += 1
                else:
                    stale_count += 1
            
            if stale_count > 2:  # More than 2 services unhealthy
                logger.warning(f"⚠️ {stale_count}/{len(health_files)} services unhealthy")
                return False
                
            return True
            
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            return False
    
    def run(self):
        """Main keepalive loop"""
        logger.info("🔄 KEEPALIVE LAUNCHER STARTING")
        logger.info("🎯 Mission: Keep system alive even if Replit kills workflow")
        
        check_interval = 60  # Check every minute
        restart_count = 0
        
        while self.running:
            try:
                is_healthy = self.check_system_health()
                
                if not is_healthy:
                    restart_count += 1
                    logger.warning(f"💔 System unhealthy, restarting (attempt #{restart_count})")
                    
                    if self.restart_workflow():
                        logger.info("✅ Restart successful")
                        # Wait longer after restart
                        time.sleep(120)  # 2 minutes
                    else:
                        logger.error("❌ Restart failed, waiting 5 minutes")
                        time.sleep(300)  # 5 minutes
                        
                else:
                    # System healthy
                    if restart_count > 0:
                        logger.info(f"✅ System healthy after {restart_count} restarts")
                        restart_count = 0
                    
                    time.sleep(check_interval)
                    
            except Exception as e:
                logger.error(f"❌ Keepalive error: {e}")
                time.sleep(60)
        
        logger.info("🛑 KEEPALIVE LAUNCHER STOPPED")

if __name__ == "__main__":
    try:
        # Also start a background thread that restarts this script every 6 hours
        def self_restart_thread():
            time.sleep(6 * 3600)  # 6 hours
            logger.info("🔄 6-hour self-restart")
            os.execv(sys.executable, ['python'] + sys.argv)
        
        threading.Thread(target=self_restart_thread, daemon=True).start()
        
        # Start main keepalive
        launcher = KeepaliveLauncher()
        launcher.run()
        
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt")
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)