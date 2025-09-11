import json
import time

# Dosya yollarini tanimla
import os
BASE_DIR = os.getcwd()
secret_file_path = os.path.join(BASE_DIR, 'secret.json')
bitget_file_path = os.path.join(BASE_DIR, 'PERP', 'secret.json')
gateio_file_path = os.path.join(BASE_DIR, 'gateio', 'secret.json')

# Güvenli environment variable yönetimi
print("🔐 Environment variable tabanlı güvenlik sistemi aktif")
print("⚠️ API anahtarları artık environment variable'lardan alınacak")
print("📋 Gerekli environment variable'lar:")
print("   - BITGET_API_KEY")
print("   - BITGET_SECRET_KEY") 
print("   - BITGET_PASSPHRASE")
print("   - GATEIO_API_KEY")
print("   - GATEIO_SECRET_KEY")

# Environment variable'ları kontrol et
required_vars = {
    "bitget": ["BITGET_API_KEY", "BITGET_SECRET_KEY", "BITGET_PASSPHRASE"],
    "gateio": ["GATEIO_API_KEY", "GATEIO_SECRET_KEY"]
}

while True:
    try:
        # Environment variable durumunu kontrol et
        bitget_status = all(os.getenv(var) for var in required_vars["bitget"])
        gateio_status = all(os.getenv(var) for var in required_vars["gateio"])
        
        status_message = f"Bitget: {'✅' if bitget_status else '❌'} | Gate.io: {'✅' if gateio_status else '❌'}"
        print(f"🔑 API Status: {status_message}")
        
        # Temporary JSON dosyalarını güncelle (mevcut scriptlerle uyumluluk için)
        # NOT: Bu geçici bir çözüm, ana scriptler environment variable kullanacak şekilde güncellenecek
        if bitget_status or gateio_status:
            # Sadece environment variable'lar mevcutsa JSON oluştur
            temp_data = {}
            
            if bitget_status:
                temp_data["bitget_example"] = {
                    "api_key": "FROM_ENV",
                    "secret_key": "FROM_ENV", 
                    "passphrase": "FROM_ENV",
                    "open_USDT": "1",
                    "close_yuzde": "1.2",
                    "initial_symbol": "XLMUSDT_UMCBL"
                }
            
            if gateio_status:
                temp_data["gateio_example"] = {
                    "api_key": "FROM_ENV",
                    "secret_key": "FROM_ENV",
                    "open_USDT": "1",
                    "close_yuzde": 1.2,
                    "initial_symbol": "XLM_USDT"
                }
            
            # Geçici JSON dosyalarını oluştur (sadece placeholder verilerle)
            if temp_data:
                with open(secret_file_path, 'w') as file:
                    json.dump(temp_data, file, indent=4)
                
                if bitget_status:
                    with open(bitget_file_path, 'w') as file:
                        json.dump({"bitget_example": temp_data.get("bitget_example", {})}, file, indent=4)
                        
                if gateio_status:
                    with open(gateio_file_path, 'w') as file:
                        json.dump({"gateio_example": temp_data.get("gateio_example", {})}, file, indent=4)
        
        print("🔄 Environment variable sistem çalışıyor...")

    except Exception as e:
        print(f"❌ Environment variable kontrol hatası: {e}")

    time.sleep(10)  # 10 saniyede bir kontrol
