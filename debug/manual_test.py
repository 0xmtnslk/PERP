#!/usr/bin/env python3
"""
Manuel Test Sistemi - Bot olmadan direkt test
"""
import os
import subprocess
import json

def setup_api_credentials():
    """API bilgilerini manuel gir"""
    print("🔑 BITGET API KURULUMU")
    print("=" * 40)
    
    api_key = input("API Key: ").strip()
    secret_key = input("Secret Key: ").strip()
    passphrase = input("Passphrase: ").strip()
    
    # Environment variables olarak ayarla
    os.environ['BITGET_API_KEY'] = api_key
    os.environ['BITGET_SECRET_KEY'] = secret_key
    os.environ['BITGET_PASSPHRASE'] = passphrase
    
    print("✅ API credentials kaydedildi!")
    return True

def setup_trading_amount():
    """İşlem miktarını ayarla"""
    print("\n💰 İŞLEM MİKTARI AYARI")
    print("=" * 40)
    
    amount = input("İşlem miktarı (USDT) [default: 20]: ").strip()
    if not amount:
        amount = "20"
    
    os.environ['BITGET_OPEN_USDT'] = amount
    print(f"✅ İşlem miktarı: {amount} USDT")
    return amount

def test_api_connection():
    """API bağlantısını test et"""
    print("\n🔍 API BAĞLANTI TESTİ")
    print("=" * 40)
    
    try:
        result = subprocess.run([
            "python3", "-c", 
            """
import os
import requests
import hmac
import base64
import time

api_key = os.environ.get('BITGET_API_KEY', '')
secret_key = os.environ.get('BITGET_SECRET_KEY', '')

if api_key and secret_key:
    timestamp = str(int(time.time() * 1000))
    request_path = '/api/mix/v1/account/accounts'
    method = 'GET'
    body = ''
    
    message = timestamp + method + request_path + body
    signature = base64.b64encode(
        hmac.new(secret_key.encode(), message.encode(), 'sha256').digest()
    ).decode()
    
    headers = {
        'ACCESS-KEY': api_key,
        'ACCESS-SIGN': signature,
        'ACCESS-TIMESTAMP': timestamp,
        'ACCESS-PASSPHRASE': os.environ.get('BITGET_PASSPHRASE', ''),
        'Content-Type': 'application/json'
    }
    
    response = requests.get('https://api.bitget.com' + request_path, headers=headers, timeout=10)
    print(f'API Test: {response.status_code}')
    if response.status_code == 200:
        print('✅ API bağlantısı başarılı!')
    else:
        print(f'❌ API hatası: {response.text}')
else:
    print('❌ API credentials eksik')
            """
        ], capture_output=True, text=True, timeout=15)
        
        print(result.stdout)
        if result.stderr:
            print(f"Hata: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Test hatası: {e}")

def trigger_fake_coin_detection():
    """Fake coin detection tetikle"""
    print("\n🧪 FAKE COIN DETECTION TEST")
    print("=" * 40)
    
    fake_symbol = input("Test coin symbol [default: TESTCOIN]: ").strip()
    if not fake_symbol:
        fake_symbol = "TESTCOIN"
    
    try:
        # new_coin_output.txt dosyasına yaz
        symbol_content = f"{fake_symbol}USDT_UMCBL"
        
        with open("PERP/new_coin_output.txt", "w") as f:
            f.write(symbol_content)
            
        print(f"✅ Fake detection trigger: {symbol_content}")
        print("📁 PERP/new_coin_output.txt dosyasına yazıldı")
        
        # Test long.py execution
        choice = input("\n🚀 Otomatik işlem testi çalıştırılsın mı? (y/n): ").strip().lower()
        if choice == 'y':
            print("⏳ İşlem testi başlatılıyor...")
            
            result = subprocess.run([
                "python3", "PERP/long.py"
            ], capture_output=True, text=True, timeout=60)
            
            print(f"📊 Çıkış kodu: {result.returncode}")
            print(f"📝 Çıktı: {result.stdout}")
            if result.stderr:
                print(f"⚠️ Hatalar: {result.stderr}")
        
    except Exception as e:
        print(f"❌ Test hatası: {e}")

def main():
    """Ana test menüsü"""
    print("🚀 MANUEL CRYPTO TRADING TEST SİSTEMİ")
    print("=" * 50)
    print("Bot problemleri yüzünden manuel test sistemi!")
    print()
    
    while True:
        print("\n📋 MENÜ:")
        print("1. 🔑 API Credentials Gir")
        print("2. 💰 İşlem Miktarı Ayarla")
        print("3. 🔍 API Bağlantı Testi")
        print("4. 🧪 Fake Coin Detection Test")
        print("5. 📊 Mevcut Ayarları Göster")
        print("6. ❌ Çıkış")
        
        choice = input("\nSeçiminiz (1-6): ").strip()
        
        if choice == "1":
            setup_api_credentials()
        elif choice == "2":
            setup_trading_amount()
        elif choice == "3":
            test_api_connection()
        elif choice == "4":
            trigger_fake_coin_detection()
        elif choice == "5":
            print("\n📊 MEVCUT AYARLAR:")
            print(f"🔑 API Key: {os.environ.get('BITGET_API_KEY', 'Yok')[:10]}...")
            print(f"💰 Miktar: {os.environ.get('BITGET_OPEN_USDT', 'Yok')} USDT")
            print(f"🔒 Passphrase: {'✅ Var' if os.environ.get('BITGET_PASSPHRASE') else '❌ Yok'}")
        elif choice == "6":
            print("👋 Test sistemi kapatılıyor...")
            break
        else:
            print("❌ Geçersiz seçim!")

if __name__ == "__main__":
    main()