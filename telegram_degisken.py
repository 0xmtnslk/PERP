import time
import json
import os
import sys

# IPC sistemi ekle
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from ipc_system import send_new_coin_alert, ipc_queue, MessageType
from notification_config import notification_config

def read_symbol_from_file(file_path):
    with open(file_path, 'r') as file:
        return file.readline().strip()

def write_symbol_to_json(symbol, json_file_path):
    with open(json_file_path, 'w') as json_file:
        json.dump({"symbol": symbol}, json_file)

def handle_new_coin_message(message) -> bool:
    """IPC üzerinden gelen yeni coin mesajlarını işle"""
    try:
        symbol = message.data.get('symbol', '')
        if symbol:
            json_file_path = notification_config.new_coin_json_file
            write_symbol_to_json(symbol, json_file_path)
            print(f"🔄 IPC ile alınan sembol JSON'a yazıldı: {symbol}")
            return True
        return False
    except Exception as e:
        print(f"❌ IPC mesaj işleme hatası: {e}")
        return False

def main():
    BASE_DIR = os.getcwd()
    text_file_path = notification_config.new_coin_output_txt
    json_file_path = notification_config.new_coin_json_file
    
    # IPC handler kaydet
    ipc_queue.register_handler(MessageType.NEW_COIN_ALERT, handle_new_coin_message)
    ipc_queue.start()
    
    print("🚀 Telegram Converter started with IPC support")
    print(f"📁 Monitoring: {text_file_path}")
    print(f"📁 Writing to: {json_file_path}")
    
    last_symbol = ""
    
    try:
        while True:
            try:
                symbol = read_symbol_from_file(text_file_path)
                
                # Yeni sembol geldi mi kontrol et
                if symbol and symbol != last_symbol:
                    write_symbol_to_json(symbol, json_file_path)
                    # IPC üzerinden diğer bileşenlere bildir
                    send_new_coin_alert(symbol, "file_watcher", "telegram_converter")
                    print(f"🔄 Yeni sembol işlendi: {symbol}")
                    last_symbol = symbol
                
                time.sleep(1)  # Wait for 1 second before the next iteration
                
            except Exception as e:
                print(f"⚠️ Dosya okuma hatası: {e}")
                time.sleep(5)
                
    except KeyboardInterrupt:
        print("\n🛑 Telegram Converter durduruluyor...")
    finally:
        ipc_queue.stop()

if __name__ == "__main__":
    main()
