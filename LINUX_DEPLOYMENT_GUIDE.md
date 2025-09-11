# 🚀 Kripto Ticaret Otomasyon Sistemi - Linux 22.04 Kurulum Rehberi

## 📋 Sistem Özellikleri

✅ **Upbit Duyuru Tarayıcısı**: React SPA desteği ile Selenium WebDriver  
✅ **Akıllı Coin Tespiti**: Parantez içi sembol çıkarma (örn: `Linea(LINEA)` → `LINEA`)  
✅ **Çifte Tetikleme Koruması**: Aynı coin iki kez işlenmez  
✅ **Telegram Bot Yönetimi**: Kullanıcı kaydı, API key yönetimi, bildirimler  
✅ **Güvenli Şifreleme**: API anahtarları Fernet ile şifrelenir  
✅ **Otomatik Bitget İşlemleri**: Leverage, miktar ve TP ayarları  
✅ **Acil Durdurma**: Telegram üzerinden anlık pozisyon kapatma  

---

## 🏗️ ADIM 1: Sistem Hazırlığı

### Temel Paket Kurulumu
```bash
# Sistem güncellemesi
sudo apt update && sudo apt upgrade -y

# Temel gereksinimler
sudo apt install -y git curl wget unzip software-properties-common \
    build-essential pkg-config libssl-dev libffi-dev python3-dev
```

### Python 3.11 Kurulumu
```bash
# Python 3.11 repository ekle
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update

# Python 3.11 kurulumu
sudo apt install -y python3.11 python3.11-pip python3.11-venv python3.11-dev

# Python alternatif ayarı
sudo update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1
sudo update-alternatives --install /usr/bin/pip3 pip3 /usr/bin/pip3.11 1

# Kontrol
python3 --version  # Python 3.11.x görmelisiniz
pip3 --version
```

---

## 🏗️ ADIM 2: Chrome/WebDriver Kurulumu

### Google Chrome Kurulumu
```bash
# Chrome repository ekle
curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | sudo apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" | sudo tee /etc/apt/sources.list.d/google-chrome.list

# Chrome kurulumu
sudo apt update
sudo apt install -y google-chrome-stable

# Versiyon kontrol
google-chrome --version
```

### ChromeDriver Kurulumu
```bash
# Chrome versiyonunu al
CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d. -f1)

# ChromeDriver indir ve kur
wget -O /tmp/chromedriver.zip "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}/chromedriver_linux64.zip"
sudo unzip /tmp/chromedriver.zip -d /usr/local/bin/
sudo chmod +x /usr/local/bin/chromedriver

# Path kontrolü
which chromedriver  # /usr/local/bin/chromedriver
chromedriver --version
```

---

## 🏗️ ADIM 3: Proje Kurulumu

### Çalışma Dizini Oluştur
```bash
# Ana dizin oluştur
sudo mkdir -p /opt/crypto-trading-bot
sudo chown $USER:$USER /opt/crypto-trading-bot
cd /opt/crypto-trading-bot

# GitHub'dan projeyi klonla (bu adımı GitHub'a upload sonrası yapacaksın)
# git clone https://github.com/YOUR_USERNAME/crypto-trading-bot.git .
```

### Python Sanal Ortam
```bash
# Virtual environment oluştur
python3 -m venv venv
source venv/bin/activate

# Pip güncelle
pip install --upgrade pip setuptools wheel
```

### Requirements.txt Oluştur
```bash
cat > requirements.txt << 'EOF'
beautifulsoup4==4.12.2
bitget-python-connector==1.0.0
cryptography==41.0.7
python-telegram-bot==20.7
requests==2.31.0
selenium==4.15.2
websocket-client==1.6.4
gate-api==4.25.0
python-bitget==1.1.0
pytz==2023.3
aiofiles==23.2.1
python-dotenv==1.0.0
sqlite3
EOF

# Paketleri kur
pip install -r requirements.txt
```

---

## 🏗️ ADIM 4: Environment Yapılandırması

### .env Dosyası Oluştur
```bash
cat > .env << 'EOF'
# Telegram Bot Token (BotFather'dan alacaksın)
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here

# Chrome/Chromium ayarları
CHROME_EXECUTABLE_PATH=/usr/bin/google-chrome-stable
CHROMEDRIVER_PATH=/usr/local/bin/chromedriver

# Debugging (isteğe bağlı)
# DEBUG=1

# Bitget API (İsteğe bağlı - Telegram bot üzerinden de eklenebilir)
# BITGET_API_KEY=your_bitget_api_key
# BITGET_SECRET_KEY=your_bitget_secret_key  
# BITGET_PASSPHRASE=your_bitget_passphrase
EOF

# Environment variables'ı profile ekle
echo 'cd /opt/crypto-trading-bot && source venv/bin/activate' >> ~/.bashrc
echo 'export $(cat /opt/crypto-trading-bot/.env | xargs)' >> ~/.bashrc
source ~/.bashrc
```

### Dizin Yapısı Oluştur
```bash
# Gerekli dizinler
mkdir -p PERP gateio logs ipc_queues

# Temel dosyaları oluştur
echo '[]' > PERP/processed_coins.json
echo '{}' > PERP/last_announcement_check.json  
echo 'BITCOINUSDT_UMCBL' > PERP/new_coin_output.txt

# İzinleri ayarla
chmod 755 logs
touch logs/main.log
chmod 644 logs/main.log
```

---

## 🏗️ ADIM 5: systemd Service Kurulumu

### Ana Servis Dosyası
```bash
sudo tee /etc/systemd/system/crypto-trading-bot.service << 'EOF'
[Unit]
Description=Crypto Trading Bot - Main Coordinator
After=network.target network-online.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=15
User=YOUR_USERNAME_HERE
WorkingDirectory=/opt/crypto-trading-bot
Environment=PATH=/opt/crypto-trading-bot/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStartPre=/bin/bash -c 'source /opt/crypto-trading-bot/venv/bin/activate'
ExecStart=/opt/crypto-trading-bot/venv/bin/python main_coordinator.py
StandardOutput=append:/opt/crypto-trading-bot/logs/main.log
StandardError=append:/opt/crypto-trading-bot/logs/main.log

# Environment variables
EnvironmentFile=/opt/crypto-trading-bot/.env

# Security settings
NoNewPrivileges=yes
PrivateTmp=yes
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
ProtectHome=no
ProtectSystem=strict
ReadWritePaths=/opt/crypto-trading-bot

# Chrome/Selenium için gerekli
Environment=DISPLAY=:99

[Install]
WantedBy=multi-user.target
EOF

# Username'i değiştir
sudo sed -i "s/YOUR_USERNAME_HERE/$USER/g" /etc/systemd/system/crypto-trading-bot.service

# Servisleri yükle
sudo systemctl daemon-reload
sudo systemctl enable crypto-trading-bot.service
```

### X11 Display Kurulumu (Headless Chrome İçin)
```bash
# Xvfb kurulumu
sudo apt install -y xvfb

# Xvfb servis dosyası
sudo tee /etc/systemd/system/xvfb.service << 'EOF'
[Unit]
Description=X Virtual Framebuffer Service
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/bin/Xvfb :99 -screen 0 1024x768x24 -nolisten tcp
Restart=always
User=nobody

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable xvfb.service
sudo systemctl start xvfb.service
```

---

## 🏗️ ADIM 6: İzinler ve Güvenlik

### Dosya İzinleri
```bash
# Proje dizini izinleri
sudo chown -R $USER:$USER /opt/crypto-trading-bot
chmod -R 755 /opt/crypto-trading-bot

# Güvenli dosyalar
chmod 600 /opt/crypto-trading-bot/.env
chmod 600 /opt/crypto-trading-bot/PERP/secret.json 2>/dev/null || true

# Çalıştırılabilir dosyalar
chmod +x /opt/crypto-trading-bot/*.py
chmod +x /opt/crypto-trading-bot/PERP/*.py
chmod +x /opt/crypto-trading-bot/gateio/*.py 2>/dev/null || true

# Log dizini izinleri
chmod 755 /opt/crypto-trading-bot/logs
```

### Güvenlik Duvarı (İsteğe Bağlı)
```bash
# UFW etkinleştir
sudo ufw enable

# Sadece SSH'a izin ver
sudo ufw allow ssh

# Web trafiği (gerekirse)
# sudo ufw allow 80
# sudo ufw allow 443

# Durum kontrol
sudo ufw status
```

---

## 🏗️ ADIM 7: Telegram Bot Kurulumu

### Bot Token Alma
1. Telegram'da @BotFather'a git
2. `/newbot` komutunu gönder
3. Bot adı gir (örn: "My Crypto Trading Bot")
4. Username gir (örn: "MyCryptoTradingBot")
5. Verilen token'ı kopyala

### Token'ı Sisteme Ekle
```bash
# .env dosyasını düzenle
nano /opt/crypto-trading-bot/.env

# Bu satırı güncelle:
TELEGRAM_BOT_TOKEN=1234567890:ABCDEF-YourRealBotTokenHere

# Dosyayı kaydet (Ctrl+X, Y, Enter)
```

---

## 🏗️ ADIM 8: İlk Başlatma ve Test

### Servis Başlatma
```bash
# Tüm servisleri başlat
sudo systemctl start xvfb.service
sudo systemctl start crypto-trading-bot.service

# Durum kontrol
sudo systemctl status crypto-trading-bot.service
sudo systemctl status xvfb.service
```

### Log İzleme
```bash
# Gerçek zamanlı log izleme
tail -f /opt/crypto-trading-bot/logs/main.log

# Servis logları
journalctl -u crypto-trading-bot.service -f

# Son 50 satır
journalctl -u crypto-trading-bot.service -n 50
```

### Manuel Test
```bash
cd /opt/crypto-trading-bot
source venv/bin/activate

# Bileşen testleri
python3 -c "
from upbit_announcement_scraper import UpbitAnnouncementScraper
scraper = UpbitAnnouncementScraper()
print('✅ Upbit scraper başarıyla yüklendi')
"

python3 -c "
from advanced_telegram_bot import TradingBot
print('✅ Telegram bot başarıyla yüklendi')
"

python3 -c "
import secret
print('✅ Secret manager başarıyla yüklendi')
"
```

---

## 🏗️ ADIM 9: GitHub Hazırlığı

### Gerekli Dosyaları Temizle
```bash
# Hassas dosyaları .gitignore'a ekle
cat > .gitignore << 'EOF'
# Environment variables
.env
*.env

# API Keys and secrets
secret.json
PERP/secret.json
gateio/secret.json

# Database files
*.db
*.sqlite
*.sqlite3

# Logs
logs/
*.log

# Cache
__pycache__/
*.pyc
*.pyo
.cache/

# Virtual environment
venv/
env/

# OS files
.DS_Store
Thumbs.db

# IDE files
.vscode/
.idea/
*.swp
*.swo

# Temporary files
*.tmp
temp/

# Output files (isteğe bağlı - proje gereksinimlerine göre)
PERP/new_coin_output.txt
PERP/order_*.json
PERP/processed_coins.json
ipc_queues/

# Chrome driver files
chromedriver
EOF

# Git reposu başlat
git init
git add .
git commit -m "Initial commit: Crypto trading automation system"
```

### GitHub'a Yükleme
```bash
# GitHub repository oluştur (github.com'da)
# Sonra buradan bağla:

git remote add origin https://github.com/YOUR_USERNAME/crypto-trading-bot.git
git branch -M main
git push -u origin main
```

---

## 🏗️ ADIM 10: Sistem Monitörü Kurulumu

### İzleme Scriptleri
```bash
# Sistem durumu kontrolü
cat > /opt/crypto-trading-bot/health_check.sh << 'EOF'
#!/bin/bash

echo "=== CRYPTO TRADING BOT HEALTH CHECK ==="
echo "Tarih: $(date)"
echo

# Servis durumu
echo "📊 SERVİS DURUMU:"
systemctl is-active crypto-trading-bot.service && echo "✅ Ana servis: ÇALIŞIYOR" || echo "❌ Ana servis: DURDU"
systemctl is-active xvfb.service && echo "✅ Display servis: ÇALIŞIYOR" || echo "❌ Display servis: DURDU"
echo

# Process durumu  
echo "🔄 PROCESS DURUMU:"
MAIN_PID=$(pgrep -f "main_coordinator.py")
if [ ! -z "$MAIN_PID" ]; then
    echo "✅ Ana koordinatör: PID $MAIN_PID"
    ps -p $MAIN_PID -o pid,ppid,pcpu,pmem,cmd --no-headers
else
    echo "❌ Ana koordinatör çalışmıyor"
fi
echo

# Log durumu
echo "📋 SON LOGLAR (Son 5 satır):"
tail -n 5 /opt/crypto-trading-bot/logs/main.log
echo

# Disk kullanımı
echo "💾 DİSK KULLANIMI:"
df -h /opt/crypto-trading-bot | tail -n 1
echo

# Memory kullanımı
echo "🧠 MEMORY KULLANIMI:"
free -h | grep -E "Mem|Swap"
echo

# Processed coins
echo "🪙 İŞLENMİŞ COİNLER:"
if [ -f "/opt/crypto-trading-bot/PERP/processed_coins.json" ]; then
    COIN_COUNT=$(cat /opt/crypto-trading-bot/PERP/processed_coins.json | grep -o '"symbol"' | wc -l)
    echo "Toplam işlenmiş coin: $COIN_COUNT"
else
    echo "Processed coins dosyası bulunamadı"
fi

echo "=================================="
EOF

chmod +x /opt/crypto-trading-bot/health_check.sh
```

### Crontab Kurulumu (Otomatik Backup)
```bash
# Crontab düzenle
crontab -e

# Bu satırları ekle:
# Her gün 03:00'da processed coins backup'ı
0 3 * * * cp /opt/crypto-trading-bot/PERP/processed_coins.json /opt/crypto-trading-bot/processed_coins_backup_$(date +\%Y\%m\%d).json

# Her saat health check
0 * * * * /opt/crypto-trading-bot/health_check.sh >> /opt/crypto-trading-bot/logs/health.log 2>&1

# Her gün eski log dosyalarını temizle (7 günden eski)
0 2 * * * find /opt/crypto-trading-bot/logs -name "*.log" -mtime +7 -delete
```

---

## 🧪 ADIM 11: Kapsamlı Test Süreçleri

### Test 1: Sistem Bütünlüğü
```bash
cd /opt/crypto-trading-bot
./health_check.sh
```

### Test 2: Upbit Scraper Testi
```bash
source venv/bin/activate
python3 -c "
import os
os.environ['DISPLAY'] = ':99'
from upbit_announcement_scraper import UpbitAnnouncementScraper

scraper = UpbitAnnouncementScraper()
print('🔍 Upbit duyuru sayfasına bağlanıyor...')

try:
    announcements = scraper.get_announcements()
    print(f'✅ Başarı! {len(announcements)} duyuru alındı')
    
    if announcements:
        first_announcement = announcements[0]
        print(f'📋 İlk duyuru: {first_announcement[\"title\"][:50]}...')
    
    # Coin detection test
    test_title = 'Market Support for Testcoin(TEST) and Others'
    symbols = scraper.extract_coin_symbols(test_title)
    print(f'🪙 Coin tespiti testi: {symbols}')
    
except Exception as e:
    print(f'❌ Hata: {e}')
"
```

### Test 3: Telegram Bot Testi
```bash
python3 -c "
from advanced_telegram_bot import TradingBot
import os

# Bot token kontrolü
token = os.getenv('TELEGRAM_BOT_TOKEN')
if token and len(token) > 10:
    print('✅ Telegram bot token mevcut')
    print(f'Token uzunluğu: {len(token)} karakter')
else:
    print('❌ Telegram bot token eksik veya hatalı')

try:
    bot = TradingBot()
    print('✅ Telegram bot başlatıldı')
except Exception as e:
    print(f'❌ Telegram bot hatası: {e}')
"
```

### Test 4: Filtering Sistemi Testi
```bash
python3 -c "
import json
from datetime import datetime

# Test coinleri
test_coins = ['TEST1', 'TEST2', 'TEST3']
processed_file = 'PERP/processed_coins.json'

print('🧪 FİLTRELEME SİSTEMİ TESTİ')
print('=' * 35)

# Mevcut processed coinleri yükle
try:
    with open(processed_file, 'r') as f:
        processed_coins = json.load(f)
except:
    processed_coins = []

print(f'📊 Mevcut işlenmiş coin sayısı: {len(processed_coins)}')

# Yeni coin kontrolü simülasyonu
for coin in test_coins:
    is_processed = any(entry.get('symbol') == coin for entry in processed_coins)
    status = '🔄 İşlenmiş' if is_processed else '✅ Yeni'
    print(f'{status}: {coin}')
"
```

---

## 🚀 ADIM 12: Canlı Ortam Deployment

### Production Ayarları
```bash
# Production environment dosyası
cp .env .env.production

# Production için düzenle
nano .env.production

# Bu ayarları ekle/güncelle:
DEBUG=0
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### SSL ve Domain (Opsiyonel)
```bash
# Nginx kurulumu (web arayüzü için gerekirse)
sudo apt install -y nginx

# Let's Encrypt (SSL için gerekirse)  
sudo apt install -y certbot python3-certbot-nginx

# Domain yapılandırması (domain.com yerine gerçek domain)
# sudo certbot --nginx -d yourdomain.com
```

### Güvenlik Sıkılaştırması
```bash
# SSH key-only auth (password'u devre dışı bırak)
sudo nano /etc/ssh/sshd_config
# PasswordAuthentication no ekle

# Fail2ban kurulumu
sudo apt install -y fail2ban

# Otomatik güncellemeler
sudo apt install -y unattended-upgrades
echo 'Unattended-Upgrade::Automatic-Reboot "false";' | sudo tee -a /etc/apt/apt.conf.d/50unattended-upgrades
```

---

## 📊 ADIM 13: İzleme ve Alerting

### Telegram Alert Kurulumu
Botuna şu komutları ekle:

1. `/start` - Botu başlat
2. "🎛️ Bot Ayarları" butonu
3. API anahtarlarını ekle:
   - Bitget API Key
   - Bitget Secret Key  
   - Bitget Passphrase
4. İşlem ayarları:
   - Miktar: 10 USDT (test için küçük)
   - Take Profit: %5
   - Leverage: 10x

### Dashboard Kurulumu (Opsiyonel)
```bash
# Basit web dashboard için Flask
pip install flask

# Dashboard dosyası oluştur
cat > dashboard.py << 'EOF'
from flask import Flask, render_template, jsonify
import json
import os
from datetime import datetime

app = Flask(__name__)

@app.route('/')
def dashboard():
    return '''
    <h1>Crypto Trading Bot Dashboard</h1>
    <div id="status"></div>
    <div id="logs"></div>
    
    <script>
    setInterval(function() {
        fetch('/api/status')
            .then(response => response.json())
            .then(data => {
                document.getElementById('status').innerHTML = 
                    '<p>Status: ' + data.status + '</p>' +
                    '<p>Processed Coins: ' + data.processed_coins + '</p>' +
                    '<p>Last Check: ' + data.last_check + '</p>';
            });
    }, 30000);
    </script>
    '''

@app.route('/api/status')
def api_status():
    try:
        # Processed coins sayısı
        with open('PERP/processed_coins.json', 'r') as f:
            processed_coins = len(json.load(f))
    except:
        processed_coins = 0
    
    return jsonify({
        'status': 'running',
        'processed_coins': processed_coins,
        'last_check': datetime.now().isoformat()
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
EOF

# Dashboard servisi (opsiyonel)
# python3 dashboard.py &
```

---

## 🎯 ADIM 14: Canlı Test Senaryoları

### Test Planı

1. **Sistem Stabilitesi** (24 saat)
   ```bash
   # 24 saat boyunca logları izle
   tail -f /opt/crypto-trading-bot/logs/main.log
   ```

2. **Upbit Scraping** (Gerçek duyuru bekleme)
   - Sistem 5 dakikada bir kontrol ediyor
   - Yeni duyuru geldiğinde otomatik tespit edilecek

3. **Telegram Bildirimleri**
   - Botuna mesaj at: "📊 Durum"
   - "🔄 Yeni Coin Kontrol Et" butonuna bas

4. **Acil Durma Testi**
   - "🚨 TÜM POZİSYONLARI KAPAT" butonunu test et
   - **KÜçük miktarlarla test yap!**

### Güvenlik Testleri

1. **API Key Şifreleme**
   ```bash
   # Şifrelenmiş dosyayı kontrol et
   file PERP/secret.json
   # Binary olmalı, human readable olmamalı
   ```

2. **Process Crash Recovery**
   ```bash
   # Ana süreci öldür (test amaçlı)
   sudo pkill -f main_coordinator.py
   
   # 15 saniye sonra tekrar başlamalı
   sleep 20
   ps aux | grep main_coordinator.py
   ```

3. **Log Rotation**
   ```bash
   # Log dosyası boyutunu kontrol et
   ls -lh logs/main.log
   
   # 1GB'dan büyükse rotation ayarı ekle
   ```

---

## 🚨 Sorun Giderme

### Yaygın Hatalar ve Çözümleri

#### 1. Chrome/ChromeDriver Hatası
```bash
# ChromeDriver versiyonunu Chrome ile eşitle
CHROME_VERSION=$(google-chrome --version | awk '{print $3}' | cut -d. -f1)
echo "Chrome version: $CHROME_VERSION"

# Eşleşmiyorsa yeni ChromeDriver indir
wget "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_${CHROME_VERSION}/chromedriver_linux64.zip"
```

#### 2. Selenium Timeout
```bash
# Display kontrolü
echo $DISPLAY  # :99 olmalı

# Xvfb kontrolü
sudo systemctl status xvfb.service

# Manuel Chrome testi
DISPLAY=:99 google-chrome --no-sandbox --headless --dump-dom https://google.com | head -10
```

#### 3. Permission Denied
```bash
# Tüm izinleri düzelt
sudo chown -R $USER:$USER /opt/crypto-trading-bot
chmod +x /opt/crypto-trading-bot/*.py
chmod +x /opt/crypto-trading-bot/PERP/*.py
chmod 600 /opt/crypto-trading-bot/.env
```

#### 4. Telegram Bot Token Hatası
```bash
# Token formatını kontrol et
grep TELEGRAM_BOT_TOKEN /opt/crypto-trading-bot/.env
# Format: 1234567890:ABCDEFghijklmnopqrstuvwxyz1234567890
```

#### 5. Bitget API Hatası
```bash
# API anahtarlarını Telegram bot üzerinden kontrol et
# Bot ayarlarından "API Durumu" bölümünü kontrol et
```

### Debug Komutları

```bash
# Manuel çalıştırma (debug)
cd /opt/crypto-trading-bot
source venv/bin/activate
export DEBUG=1
export DISPLAY=:99
python3 main_coordinator.py

# Verbose logging
tail -f logs/main.log | grep -E "(ERROR|WARN|DEBUG)"

# Network testi
curl -I https://upbit.com/service_center/notice
curl -I https://api.bitget.com

# Process tree
pstree -p $(pgrep -f main_coordinator.py)
```

---

## ✅ Son Kontrol Listesi

Canlı ortama almadan önce kontrol et:

- [ ] ✅ Python 3.11 kurulu ve çalışıyor
- [ ] ✅ Chrome + ChromeDriver eşleşiyor  
- [ ] ✅ Xvfb servisi çalışıyor (:99 display)
- [ ] ✅ Telegram bot token geçerli
- [ ] ✅ systemd servis dosyası kurulu
- [ ] ✅ .env dosyası güvenli izinlerde (600)
- [ ] ✅ Processed coins dosyası oluşturuldu
- [ ] ✅ Log dosyaları yazılabiliyor
- [ ] ✅ GitHub'a upload edildi (.gitignore ile)
- [ ] ✅ Health check scripti çalışıyor
- [ ] ✅ Upbit scraper test edildi
- [ ] ✅ Telegram bot test edildi
- [ ] ✅ İlk test küçük miktarla yapılacak

---

## 🎯 Canlı Test Prosedürü

1. **Küçük Miktar Ayarla**
   - Telegram bot → "🎛️ Bot Ayarları" 
   - İşlem miktarı: 5-10 USDT
   - Take Profit: %3-5
   - Leverage: 5x (düşük risk)

2. **İlk 24 Saat İzle**
   ```bash
   # Log izleme
   tail -f /opt/crypto-trading-bot/logs/main.log
   
   # Sistem durumu her saat kontrol et
   ./health_check.sh
   ```

3. **Gerçek Duyuru Bekle**
   - Upbit genelde Perşembe/Cuma yeni coin duyurusu yapar
   - İlk duyuruda sistem otomatik tetiklenecek
   - Telegram'dan bildirim gelecek

4. **Sonuçları Değerlendir**
   - İşlem açıldı mı?
   - Fiyat takibi doğru mu?
   - Take profit çalıştı mı?
   - Duplicate filtering çalışıyor mu?

**BAşarılar! Sisteminiz artık canlı ortam için hazır! 🚀💰**

---

## 📞 Acil Durum Komutları

```bash
# Servisi durdur
sudo systemctl stop crypto-trading-bot.service

# Tüm pozisyonları kapat (Telegram'dan)
# "🚨 TÜM POZİSYONLARI KAPAT" butonuna bas

# Sistem backup'ı
tar -czf crypto-bot-backup-$(date +%Y%m%d).tar.gz /opt/crypto-trading-bot

# Logları temizle
sudo truncate -s 0 /opt/crypto-trading-bot/logs/main.log
```

**Canlı ortamda her zaman dikkatli ol! İlk testleri küçük miktarlarla yap! 💡**