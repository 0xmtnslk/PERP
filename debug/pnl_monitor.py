#!/usr/bin/env python3
"""
P&L Monitor - Every 1 minute position monitoring with Telegram notifications
"""
import time
import json
import os
import requests
import hmac
import hashlib
import base64
import sqlite3
from datetime import datetime

def get_timestamp():
    return int(time.time() * 1000)

def create_signature(message, secret_key):
    mac = hmac.new(bytes(secret_key, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
    d = mac.digest()
    return base64.b64encode(d).decode('utf-8')

def pre_hash(timestamp, method, request_path, body):
    return str(timestamp) + str.upper(method) + request_path + body

def parse_params_to_str(params):
    url = '?'
    for key, value in params.items():
        url += f"{key}={value}&"
    return url[:-1]

def send_telegram_notification(message, user_id, reply_markup=None):
    """Send Telegram notification with optional inline keyboard"""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        print("⚠️ TELEGRAM_BOT_TOKEN not found")
        return False
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": user_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    if reply_markup:
        payload["reply_markup"] = reply_markup
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except:
        return False

def get_positions(api_key, secret_key, passphrase):
    """Get all open positions from Bitget API"""
    timestamp = str(get_timestamp())
    request_path = "/api/v2/mix/position/all-position"
    params = {"productType": "USDT-FUTURES"}
    request_path += parse_params_to_str(params)
    
    sign = create_signature(pre_hash(timestamp, "GET", request_path, ""), secret_key)
    
    headers = {
        "ACCESS-KEY": api_key,
        "ACCESS-SIGN": sign,
        "ACCESS-PASSPHRASE": passphrase,
        "ACCESS-TIMESTAMP": timestamp,
        "Content-Type": "application/json"
    }
    
    try:
        url = "https://api.bitget.com" + request_path
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == '00000':
                return data.get('data', [])
        
        print(f"❌ Position API error: {response.status_code}")
        return []
    except Exception as e:
        print(f"❌ Position API exception: {e}")
        return []

def calculate_pnl_percentage(position):
    """Calculate P&L percentage from position data"""
    try:
        unrealized_pnl = float(position.get('unrealizedPL', 0))
        margin = float(position.get('margin', 0))
        
        if margin > 0:
            pnl_percentage = (unrealized_pnl / margin) * 100
            return pnl_percentage
        return 0.0
    except:
        return 0.0

def format_pnl_message(positions):
    """Format P&L status message for Telegram"""
    if not positions:
        return "📊 <b>POZİSYON DURUMU</b>\n\n🔹 Açık pozisyon bulunamadı"
    
    message = "📊 <b>POZİSYON DURUMU</b>\n\n"
    total_pnl = 0.0
    
    for pos in positions:
        symbol = pos.get('symbol', 'Unknown')
        size = float(pos.get('total', 0))
        unrealized_pnl = float(pos.get('unrealizedPL', 0))
        pnl_percentage = calculate_pnl_percentage(pos)
        margin_mode = pos.get('marginMode', 'unknown')
        leverage = pos.get('leverage', '1')
        
        # P&L emoji
        pnl_emoji = "🟢" if unrealized_pnl >= 0 else "🔴"
        
        message += f"🔹 <b>{symbol}</b>\n"
        message += f"   📏 Boyut: {size:.4f}\n"
        message += f"   ⚡ Leverage: {leverage}x\n"
        message += f"   🔒 Margin: {margin_mode}\n"
        message += f"   {pnl_emoji} P&L: ${unrealized_pnl:.2f} ({pnl_percentage:+.2f}%)\n\n"
        
        total_pnl += unrealized_pnl
    
    # Total summary
    total_emoji = "🟢" if total_pnl >= 0 else "🔴"
    message += f"💰 <b>TOPLAM P&L: {total_emoji} ${total_pnl:.2f}</b>\n"
    message += f"🕐 <i>Güncelleme: {datetime.now().strftime('%H:%M:%S')}</i>"
    
    return message

def create_stop_button():
    """Create inline keyboard with stop button"""
    return {
        "inline_keyboard": [
            [{"text": "🛑 POZİSYONU KAPAT", "callback_data": "stop_position"}]
        ]
    }

def get_users_from_database():
    """Get active users from database"""
    try:
        conn = sqlite3.connect('PERP/trading_bot.db')
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE api_key IS NOT NULL")
        users = [row[0] for row in cursor.fetchall()]
        conn.close()
        return users
    except:
        return [625972998]  # Default user if database error

def monitor_positions():
    """Main monitoring loop"""
    print("🚀 P&L Monitor başlatılıyor...")
    
    # API credentials
    api_key = os.getenv("BITGET_API_KEY")
    secret_key = os.getenv("BITGET_SECRET_KEY")
    passphrase = os.getenv("BITGET_PASSPHRASE")
    
    if not all([api_key, secret_key, passphrase]):
        print("❌ HATA: Bitget API anahtarları bulunamadı!")
        return
    
    while True:
        try:
            print(f"📊 {datetime.now().strftime('%H:%M:%S')} - Pozisyonlar kontrol ediliyor...")
            
            # Get positions
            positions = get_positions(api_key, secret_key, passphrase)
            open_positions = [pos for pos in positions if float(pos.get('total', 0)) != 0]
            
            print(f"📍 {len(open_positions)} açık pozisyon bulundu")
            
            # Get users to notify
            users = get_users_from_database()
            
            if open_positions:
                # Format P&L message
                message = format_pnl_message(open_positions)
                stop_button = create_stop_button()
                
                # Send to all users
                for user_id in users:
                    if send_telegram_notification(message, user_id, stop_button):
                        print(f"✅ P&L bildirim gönderildi: User {user_id}")
                    else:
                        print(f"❌ P&L bildirim hatası: User {user_id}")
            else:
                print("📭 Açık pozisyon yok, bildirim gönderilmedi")
            
            # Wait 1 minute
            print("⏳ 60 saniye bekleniyor...\n")
            time.sleep(60)
            
        except KeyboardInterrupt:
            print("\n🛑 P&L Monitor durduruldu")
            break
        except Exception as e:
            print(f"❌ Monitoring error: {e}")
            time.sleep(60)  # Wait before retry

if __name__ == "__main__":
    monitor_positions()