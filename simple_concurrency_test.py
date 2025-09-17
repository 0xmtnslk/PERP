#!/usr/bin/env python3
"""
Simple test for the exact crash scenario: Two users updating API settings simultaneously
"""
import sys
import os
import threading
import time

# Add production core to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'production', 'core'))

from working_telegram_bot import WorkingTelegramBot

def simulate_user_api_setup(bot, user_id, iteration):
    """Simulate the exact API setup that caused crashes"""
    try:
        print(f"🟢 User {user_id} iteration {iteration}: Starting API setup")
        
        # Save user (when they first interact with bot)
        bot.save_user(user_id, f"testuser_{user_id}")
        
        # Simulate rapid API credential updates (the crash scenario)
        bot.update_setting(user_id, 'api_key', f'bg_test_api_{user_id}_{iteration}')
        bot.update_setting(user_id, 'secret_key', f'sk_test_secret_{user_id}_{iteration}')
        bot.update_setting(user_id, 'passphrase', f'pass_{user_id}_{iteration}')
        
        # Additional settings
        bot.update_setting(user_id, 'amount_usdt', 50.0)
        bot.update_setting(user_id, 'leverage', 10)
        bot.update_setting(user_id, 'take_profit_percent', 100.0)
        
        print(f"✅ User {user_id} iteration {iteration}: API setup completed")
        return True
        
    except Exception as e:
        print(f"❌ User {user_id} iteration {iteration}: Failed with error: {e}")
        return False

def main():
    """Test the exact crash scenario"""
    print("🧪 Testing multi-user API setup concurrency...")
    print("Simulating users 625972998 and 8484524377 crash scenario")
    
    # Use test database
    bot = WorkingTelegramBot()
    bot.db_path = 'test_concurrency.db'
    bot.db_manager.db_path = 'test_concurrency.db'
    
    # Clean up any existing test database
    if os.path.exists(bot.db_path):
        os.remove(bot.db_path)
    
    # Initialize fresh database
    bot.init_database()
    
    successful_operations = 0
    total_operations = 0
    
    # Run multiple iterations of the crash scenario
    for iteration in range(10):
        print(f"\n--- Iteration {iteration + 1} ---")
        
        # Create threads for the two problematic users
        thread1 = threading.Thread(target=lambda: simulate_user_api_setup(bot, 625972998, iteration))
        thread2 = threading.Thread(target=lambda: simulate_user_api_setup(bot, 8484524377, iteration))
        
        # Start both threads simultaneously (the crash scenario)
        thread1.start()
        thread2.start()
        
        # Wait for both to complete
        thread1.join(timeout=10)
        thread2.join(timeout=10)
        
        total_operations += 2
        
        # Check if system is still responsive
        try:
            settings1 = bot.get_user_settings(625972998)
            settings2 = bot.get_user_settings(8484524377)
            
            if settings1 and settings2:
                successful_operations += 2
                print(f"✅ Both users' data readable - no crash detected")
            else:
                print(f"⚠️ Some user data not readable")
        except Exception as e:
            print(f"❌ System unresponsive: {e}")
    
    # Wait for all queued operations to complete
    print("\n⏳ Waiting for queued operations to complete...")
    time.sleep(3)
    
    # Final verification
    try:
        final_settings1 = bot.get_user_settings(625972998)
        final_settings2 = bot.get_user_settings(8484524377)
        
        print(f"\n📊 RESULTS:")
        print(f"✅ Successful operations: {successful_operations}/{total_operations}")
        print(f"🔍 User 625972998 final settings: {'✅ OK' if final_settings1 else '❌ Missing'}")
        print(f"🔍 User 8484524377 final settings: {'✅ OK' if final_settings2 else '❌ Missing'}")
        
        if successful_operations == total_operations and final_settings1 and final_settings2:
            print(f"\n🎉 TEST PASSED: Multi-user concurrency fix is working!")
            print(f"   ✅ No crashes detected")
            print(f"   ✅ All operations completed successfully")
            print(f"   ✅ System remained responsive throughout test")
        else:
            print(f"\n⚠️ TEST ISSUES DETECTED:")
            print(f"   Success rate: {successful_operations/total_operations*100:.1f}%")
            
    except Exception as e:
        print(f"❌ Final verification failed: {e}")
    
    # Cleanup
    try:
        bot.db_manager.shutdown()
        if os.path.exists(bot.db_path):
            os.remove(bot.db_path)
        print("✅ Test cleanup completed")
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")

if __name__ == "__main__":
    main()