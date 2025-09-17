#!/usr/bin/env python3
"""
🛡️ OUTER WATCHDOG LAUNCHER 
Keeps production supervisor alive forever - crash-proof system
"""
import os
import sys
import time
import subprocess
import logging
import signal
from datetime import datetime, timedelta

# Minimal logging for launcher
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - LAUNCHER - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('launcher.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('LAUNCHER')

class LauncherWatchdog:
    def __init__(self):
        self.supervisor_process = None
        self.running = True
        self.restart_count = 0
        self.last_restart = None
        self.supervisor_heartbeat_file = "production/monitoring/supervisor_heartbeat.txt"
        
        # Create monitoring directory
        os.makedirs('production/monitoring', exist_ok=True)
        
        # Signal handlers
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        logger.info("🛡️ OUTER WATCHDOG LAUNCHER INITIALIZED")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"📡 Launcher received signal {signum}, shutting down...")
        self.running = False
        self.stop_supervisor()
        sys.exit(0)
    
    def stop_supervisor(self):
        """Stop supervisor process gracefully"""
        if self.supervisor_process:
            try:
                logger.info("🛑 Stopping supervisor process...")
                self.supervisor_process.terminate()
                
                # Wait up to 10 seconds for graceful shutdown
                try:
                    self.supervisor_process.wait(timeout=10)
                    logger.info("✅ Supervisor stopped gracefully")
                except subprocess.TimeoutExpired:
                    logger.warning("⏰ Supervisor didn't stop gracefully, force killing...")
                    self.supervisor_process.kill()
                    self.supervisor_process.wait()
                    logger.info("✅ Supervisor force stopped")
                    
            except Exception as e:
                logger.error(f"❌ Error stopping supervisor: {e}")
    
    def is_supervisor_healthy(self):
        """Check if supervisor is responsive via heartbeat"""
        try:
            if not os.path.exists(self.supervisor_heartbeat_file):
                return False
                
            # Check heartbeat file age
            mtime = os.path.getmtime(self.supervisor_heartbeat_file)
            age = time.time() - mtime
            
            # Heartbeat should be updated every 30 seconds
            return age < 60  # Give 60 seconds tolerance
            
        except Exception as e:
            logger.error(f"❌ Error checking supervisor health: {e}")
            return False
    
    def start_supervisor(self):
        """Start supervisor process"""
        try:
            logger.info("🚀 Starting production supervisor...")
            
            self.supervisor_process = subprocess.Popen(
                ["python3", "production_supervisor.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                universal_newlines=True,
                preexec_fn=os.setsid  # Create process group for clean kills
            )
            
            self.restart_count += 1
            self.last_restart = datetime.now()
            
            logger.info(f"✅ Supervisor started (PID: {self.supervisor_process.pid}, restart #{self.restart_count})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start supervisor: {e}")
            return False
    
    def get_restart_delay(self):
        """Calculate exponential backoff delay"""
        if self.restart_count <= 3:
            return 5  # Quick restart for first few attempts
        elif self.restart_count <= 10:
            return min(30, 5 * (self.restart_count - 3))  # Progressive delay
        else:
            return 60  # Max delay after many failures
    
    def run(self):
        """Main launcher loop - keep supervisor alive forever"""
        logger.info("🛡️ OUTER WATCHDOG LAUNCHER STARTING")
        logger.info("🎯 Mission: Keep production supervisor alive 24/7")
        
        while self.running:
            try:
                # Check if supervisor process exists and is running
                if not self.supervisor_process or self.supervisor_process.poll() is not None:
                    if self.supervisor_process:
                        exit_code = self.supervisor_process.returncode
                        logger.warning(f"⚠️ Supervisor process died (exit code: {exit_code})")
                    
                    # Calculate restart delay
                    delay = self.get_restart_delay()
                    if self.last_restart:
                        time_since_restart = (datetime.now() - self.last_restart).total_seconds()
                        if time_since_restart < delay:
                            wait_time = delay - time_since_restart
                            logger.info(f"⏰ Waiting {wait_time:.1f}s before restart (backoff)")
                            time.sleep(wait_time)
                    
                    # Start supervisor
                    if not self.start_supervisor():
                        logger.error("❌ Failed to start supervisor, retrying in 30s...")
                        time.sleep(30)
                        continue
                    
                    # Give supervisor 60 seconds to initialize before checking heartbeat
                    logger.info("⏳ Giving supervisor 60s to initialize...")
                    time.sleep(60)
                
                # Check supervisor health via heartbeat (only after initialization)
                if not self.is_supervisor_healthy():
                    logger.warning("💔 Supervisor heartbeat stale, restarting...")
                    self.stop_supervisor()
                    continue
                
                # All good, sleep and check again  
                time.sleep(60)  # Check less frequently
                
            except Exception as e:
                logger.error(f"❌ Launcher error: {e}")
                time.sleep(10)
        
        logger.info("🛑 OUTER WATCHDOG LAUNCHER STOPPED")

if __name__ == "__main__":
    launcher = LauncherWatchdog()
    try:
        launcher.run()
    except KeyboardInterrupt:
        logger.info("🛑 Keyboard interrupt received")
        launcher.stop_supervisor()
    except Exception as e:
        logger.error(f"❌ Fatal launcher error: {e}")
        launcher.stop_supervisor()
        sys.exit(1)