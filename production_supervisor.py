#!/usr/bin/env python3
"""
🔄 PRODUCTION-GRADE SUPERVISOR
Gerçek 7/24 uptime için industrial-strength process manager
✅ Single-instance guarantee (409 conflict önleme)
✅ Exponential backoff + circuit breaker 
✅ Process cleanup + resource management
✅ Health monitoring + auto-recovery
"""
import os
import sys
import time
import json
import subprocess
import logging
import threading
import signal
from datetime import datetime, timedelta

# Production logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('production_supervisor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('SUPERVISOR')

class ProductionSupervisor:
    def __init__(self):
        self.processes = {}
        self.restart_counts = {}
        self.restart_delays = {}
        self.last_health_check = {}
        self.running = True
        
        # Production services configuration
        self.services = {
            "telegram_bot": {
                "command": ["python3", "production/core/working_telegram_bot.py"],
                "description": "🤖 Telegram Bot",
                "max_restarts": 5,
                "restart_window": 3600,
                "health_file": "production/monitoring/telegram_bot_health.txt",
                "critical": True
            },
            "upbit_monitor": {
                "command": ["python3", "production/core/upbit_announcement_scraper.py"],
                "description": "👀 Upbit Monitor",
                "max_restarts": 3,
                "restart_window": 3600,
                "health_file": "production/monitoring/upbit_monitor_health.txt",
                "critical": True
            },
            "market_tracker": {
                "command": ["python3", "production/exchanges/PERP/upbit_market_tracker.py"],
                "description": "📊 Market Tracker",
                "max_restarts": 3,
                "restart_window": 3600,
                "health_file": "production/monitoring/market_tracker_health.txt",
                "critical": True
            },
            "user_trading_engine": {
                "command": ["python3", "production/core/user_trading_engine.py"],
                "description": "🚀 Auto-Trading Engine",
                "max_restarts": 3,
                "restart_window": 3600,
                "health_file": "production/monitoring/user_trading_engine_health.txt",
                "critical": True
            }
        }
        
        # Create necessary directories
        os.makedirs('logs', exist_ok=True)
        
        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self.signal_handler)
        signal.signal(signal.SIGINT, self.signal_handler)
        
        # Supervisor heartbeat for outer watchdog
        self.heartbeat_file = "production/monitoring/supervisor_heartbeat.txt"
        self.start_heartbeat()
        
        logger.info("🚀 PRODUCTION SUPERVISOR INITIALIZED")
    
    def start_heartbeat(self):
        """Start heartbeat thread for outer watchdog"""
        import threading
        heartbeat_thread = threading.Thread(target=self.heartbeat_writer, daemon=True)
        heartbeat_thread.start()
        logger.info("💓 Supervisor heartbeat started")
    
    def heartbeat_writer(self):
        """Write heartbeat file every 30 seconds"""
        while self.running:
            try:
                with open(self.heartbeat_file, 'w') as f:
                    f.write(f"{datetime.now().isoformat()}\n")
            except Exception as e:
                logger.error(f"❌ Heartbeat write error: {e}")
            time.sleep(30)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"📡 Received signal {signum}, shutting down gracefully...")
        self.running = False
        self.stop_all_services()
        sys.exit(0)
    
    def kill_existing_instances(self, service_name):
        """CRITICAL: Kill existing instances to prevent 409 conflicts"""
        try:
            config = self.services[service_name]
            script_name = config["command"][1] if len(config["command"]) > 1 else ""
            
            if script_name:
                # Find all processes running this script
                result = subprocess.run(
                    ["pgrep", "-f", script_name],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    pids = [pid.strip() for pid in result.stdout.split('\n') if pid.strip()]
                    
                    for pid in pids:
                        try:
                            # Check if it's not this supervisor process
                            ps_result = subprocess.run(
                                ["ps", "-p", pid, "-o", "cmd="],
                                capture_output=True,
                                text=True
                            )
                            
                            if "production_supervisor.py" not in ps_result.stdout:
                                logger.info(f"🔪 Killing existing instance PID: {pid}")
                                subprocess.run(["kill", "-TERM", pid], timeout=3)
                        except Exception as e:
                            logger.warning(f"⚠️ Could not kill PID {pid}: {e}")
                    
                    # Wait for graceful shutdown
                    time.sleep(2)
                    
                    # Force kill if still running
                    result = subprocess.run(
                        ["pgrep", "-f", script_name],
                        capture_output=True,
                        text=True
                    )
                    
                    if result.returncode == 0:
                        pids = [pid.strip() for pid in result.stdout.split('\n') if pid.strip()]
                        for pid in pids:
                            try:
                                ps_result = subprocess.run(
                                    ["ps", "-p", pid, "-o", "cmd="],
                                    capture_output=True,
                                    text=True
                                )
                                
                                if "production_supervisor.py" not in ps_result.stdout:
                                    logger.warning(f"🔥 Force killing PID: {pid}")
                                    subprocess.run(["kill", "-KILL", pid], timeout=3)
                            except Exception as e:
                                logger.error(f"❌ Could not force kill PID {pid}: {e}")
                    
        except Exception as e:
            logger.error(f"❌ Error killing existing instances: {e}")
    
    def apply_restart_delay(self, service_name):
        """Apply exponential backoff to prevent restart storms"""
        if service_name not in self.restart_delays:
            self.restart_delays[service_name] = 1
        
        delay = self.restart_delays[service_name]
        if delay > 1:
            logger.info(f"⏱️ Backoff delay: {delay}s for {service_name}")
            time.sleep(delay)
        
        # Exponential backoff (max 60 seconds)
        self.restart_delays[service_name] = min(delay * 2, 60)
    
    def reset_restart_delay(self, service_name):
        """Reset delay when service runs successfully"""
        if service_name in self.restart_delays:
            self.restart_delays[service_name] = 1
    
    def check_restart_limit(self, service_name):
        """Check if service can be restarted (circuit breaker)"""
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
        
        if len(self.restart_counts[service_name]) >= max_restarts:
            logger.error(f"🚨 Circuit breaker: {service_name} exceeded {max_restarts} restarts in {restart_window}s")
            return False
            
        return True
    
    def record_restart(self, service_name):
        """Record restart timestamp"""
        if service_name not in self.restart_counts:
            self.restart_counts[service_name] = []
        
        self.restart_counts[service_name].append(datetime.now())
    
    def start_service(self, service_name):
        """Start service with production-grade guarantees"""
        if service_name not in self.services:
            logger.error(f"❌ Unknown service: {service_name}")
            return False
            
        config = self.services[service_name]
        
        # CRITICAL: Kill existing instances first
        self.kill_existing_instances(service_name)
        
        # Check circuit breaker
        if not self.check_restart_limit(service_name):
            return False
        
        # Apply exponential backoff
        self.apply_restart_delay(service_name)
        
        try:
            logger.info(f"🚀 Starting {config['description']}")
            
            # Open log files
            stdout_file = open(f"logs/{service_name}_stdout.log", "w")
            stderr_file = open(f"logs/{service_name}_stderr.log", "w")
            
            # Start process with proper isolation
            process = subprocess.Popen(
                config["command"],
                stdout=stdout_file,
                stderr=stderr_file,
                cwd=os.getcwd(),
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            self.processes[service_name] = {
                'process': process,
                'stdout_file': stdout_file,
                'stderr_file': stderr_file,
                'start_time': datetime.now()
            }
            
            self.record_restart(service_name)
            
            logger.info(f"✅ {config['description']} started (PID: {process.pid})")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start {service_name}: {e}")
            return False
    
    def stop_service(self, service_name):
        """Stop service and cleanup resources"""
        if service_name not in self.processes:
            return
            
        logger.info(f"🛑 Stopping {service_name}")
        
        process_info = self.processes[service_name]
        process = process_info['process']
        
        try:
            # Graceful shutdown
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            logger.warning(f"⚡ Force killing {service_name}")
            process.kill()
        except Exception as e:
            logger.error(f"❌ Error stopping {service_name}: {e}")
        
        # Cleanup file handles
        for file_key in ['stdout_file', 'stderr_file']:
            if file_key in process_info:
                try:
                    process_info[file_key].close()
                except Exception as e:
                    logger.warning(f"⚠️ Error closing {file_key}: {e}")
        
        del self.processes[service_name]
        logger.info(f"✅ {service_name} stopped and cleaned up")
    
    def is_service_running(self, service_name):
        """Check if service is running"""
        if service_name not in self.processes:
            return False
            
        process = self.processes[service_name]['process']
        return process.poll() is None
    
    def health_check(self, service_name):
        """Check service health via heartbeat file"""
        config = self.services[service_name]
        health_file = config.get("health_file")
        
        if not health_file or not os.path.exists(health_file):
            logger.warning(f"⚠️ No health file for {service_name}")
            return False
            
        try:
            with open(health_file, 'r') as f:
                last_update = f.read().strip()
                last_time = datetime.fromisoformat(last_update)
                
            # Health check: updated within last 2 minutes
            if datetime.now() - last_time < timedelta(minutes=2):
                return True
            else:
                logger.warning(f"⚠️ {service_name} health stale (last: {last_time})")
                return False
                
        except Exception as e:
            logger.error(f"❌ Health check failed for {service_name}: {e}")
            return False
    
    def monitor_services(self):
        """Main monitoring loop"""
        logger.info("🔍 Production monitoring started")
        
        while self.running:
            try:
                all_healthy = True
                
                for service_name, config in self.services.items():
                    if not self.is_service_running(service_name):
                        logger.warning(f"⚠️ Service {service_name} not running")
                        if self.start_service(service_name):
                            # Reset delay on successful start
                            time.sleep(5)  # Let it start up
                            if self.is_service_running(service_name):
                                self.reset_restart_delay(service_name)
                        all_healthy = False
                    else:
                        # Check health if running
                        if not self.health_check(service_name):
                            logger.warning(f"⚠️ {service_name} failed health check, restarting")
                            self.stop_service(service_name)
                            time.sleep(2)
                            self.start_service(service_name)
                            all_healthy = False
                
                # Log status every 10 minutes
                if not hasattr(self, 'last_status_log'):
                    self.last_status_log = datetime.now()
                
                if datetime.now() - self.last_status_log > timedelta(minutes=10):
                    self.log_system_status()
                    self.last_status_log = datetime.now()
                
            except Exception as e:
                logger.error(f"❌ Monitor error: {e}")
            
            # Check every 30 seconds (faster than old system)
            time.sleep(30)
    
    def log_system_status(self):
        """Log comprehensive system status"""
        running_services = []
        failed_services = []
        
        for service_name, config in self.services.items():
            if self.is_service_running(service_name):
                running_services.append(config['description'])
            else:
                failed_services.append(config['description'])
        
        status = f"""
🏭 PRODUCTION STATUS:
✅ Running: {', '.join(running_services) if running_services else 'None'}
❌ Failed: {', '.join(failed_services) if failed_services else 'None'}
📊 Uptime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        logger.info(status)
        
        # Write status file for external monitoring
        try:
            with open('system_status.json', 'w') as f:
                json.dump({
                    'timestamp': datetime.now().isoformat(),
                    'running_services': running_services,
                    'failed_services': failed_services,
                    'total_services': len(self.services)
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"⚠️ Could not write status file: {e}")
    
    def start_all_services(self):
        """Start all services with staggered startup"""
        logger.info("🚀 PRODUCTION SUPERVISOR STARTING ALL SERVICES")
        logger.info("=" * 60)
        
        for service_name in self.services.keys():
            if self.start_service(service_name):
                time.sleep(3)  # Stagger startup to avoid resource conflicts
            else:
                logger.error(f"❌ Failed to start critical service: {service_name}")
        
        logger.info("✅ All services startup attempted")
        logger.info("🔍 Continuous monitoring enabled")
    
    def stop_all_services(self):
        """Stop all services gracefully"""
        logger.info("🛑 Stopping all services")
        for service_name in list(self.processes.keys()):
            self.stop_service(service_name)
        logger.info("✅ All services stopped")

def main():
    supervisor = ProductionSupervisor()
    
    try:
        # Start all services
        supervisor.start_all_services()
        
        # Start monitoring thread
        monitor_thread = threading.Thread(target=supervisor.monitor_services, daemon=False)
        monitor_thread.start()
        
        logger.info("🏭 PRODUCTION SUPERVISOR RUNNING")
        logger.info("🔄 7/24 auto-restart + monitoring active")
        logger.info("🚨 System ready for production deployment")
        
        # Keep main thread alive
        monitor_thread.join()
        
    except KeyboardInterrupt:
        logger.info("🛑 Graceful shutdown requested")
        supervisor.stop_all_services()
        
    except Exception as e:
        logger.error(f"💥 Supervisor crashed: {e}")
        supervisor.stop_all_services()
        raise

if __name__ == "__main__":
    main()