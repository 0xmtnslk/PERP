#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import json
import time
import threading
import subprocess
from datetime import datetime
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
import logging

# Logging ayarları
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class CryptoTradingBot:
    def __init__(self):
        self.BASE_DIR = os.getcwd()
        self.running_processes = {}
        self.system_status = "STOPPED"
        
        # Dosya yolları
        self.secret_file = os.path.join(self.BASE_DIR, "secret.json")
        self.status_file = os.path.join(self.BASE_DIR, "bot_status.json")
        
    def get_system_status(self):
        """Sistem durumunu kontrol et"""
        try:
            with open(self.status_file, 'r') as f:
                status_data = json.load(f)
            return status_data
        except:
            return {
                "system_status": "STOPPED",
                "last_update": datetime.now().isoformat(),
                "active_scripts": [],
                "last_trade": None
            }
    
    def save_system_status(self, status_data):
        """Sistem durumunu kaydet"""
        try:
            with open(self.status_file, 'w') as f:
                json.dump(status_data, f, indent=2)
        except Exception as e:
            logger.error(f"Status kaydetme hatası: {e}")
    
    def read_latest_data(self):
        """En son verileri oku"""
        data = {}
        try:
            # PERP verileri
            perp_new_coin = os.path.join(self.BASE_DIR, "PERP", "new_coin_output.txt")
            if os.path.exists(perp_new_coin):
                with open(perp_new_coin, 'r') as f:
                    data["perp_symbol"] = f.read().strip()
            
            # GateIO verileri  
            gateio_new_coin = os.path.join(self.BASE_DIR, "gateio", "new_coin_output.txt")
            if os.path.exists(gateio_new_coin):
                with open(gateio_new_coin, 'r') as f:
                    data["gateio_symbol"] = f.read().strip()
            
            # Yüzde verileri
            perp_yuzde = os.path.join(self.BASE_DIR, "PERP", "yuzde.json")
            if os.path.exists(perp_yuzde):
                with open(perp_yuzde, 'r') as f:
                    data["perp_yuzde"] = json.load(f)
                    
            gateio_yuzde = os.path.join(self.BASE_DIR, "gateio", "yuzde.json")
            if os.path.exists(gateio_yuzde):
                with open(gateio_yuzde, 'r') as f:
                    data["gateio_yuzde"] = json.load(f)
                    
        except Exception as e:
            logger.error(f"Veri okuma hatası: {e}")
            
        return data

# Bot komutları
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot başlatma komutu"""
    welcome_message = """
🚀 **Kripto Ticaret Bot Kontrolü**

Mevcut komutlar:
/status - Sistem durumu
/start_trading - Ticareti başlat
/stop_trading - Ticareti durdur
/get_data - Güncel verileri göster
/emergency_stop - Acil durdurma
/help - Yardım

⚠️ Bu bot sadece yetkili kullanıcılar içindir.
    """
    await update.message.reply_text(welcome_message, parse_mode='Markdown')

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sistem durumunu göster"""
    bot_instance = context.bot_data.get('bot_instance')
    if not bot_instance:
        await update.message.reply_text("❌ Bot instance bulunamadı!")
        return
        
    status_data = bot_instance.get_system_status()
    current_data = bot_instance.read_latest_data()
    
    status_message = f"""
📊 **Sistem Durumu**

🔄 **Ana Durum:** {status_data.get('system_status', 'UNKNOWN')}
⏰ **Son Güncelleme:** {status_data.get('last_update', 'N/A')}

📈 **Güncel Veriler:**
• Bitget Symbol: {current_data.get('perp_symbol', 'N/A')}
• Gate.io Symbol: {current_data.get('gateio_symbol', 'N/A')}

💰 **Kar Durumu:**
• Bitget Yüzde: {current_data.get('perp_yuzde', {}).get('yuzde', 'N/A')}
• Gate.io Yüzde: {current_data.get('gateio_yuzde', {}).get('yuzde', 'N/A')}

🔧 **Aktif Scriptler:** {len(status_data.get('active_scripts', []))}
    """
    
    await update.message.reply_text(status_message, parse_mode='Markdown')

async def start_trading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ticareti başlat"""
    await update.message.reply_text("🚀 Ticaret sistemi başlatılıyor...\n\n⚠️ API anahtarlarınızı kontrol edin!")
    
    # Ana koordinatör scripti başlat (bu script henüz oluşturulacak)
    # subprocess.Popen(["python3", "main_coordinator.py"])
    
    await update.message.reply_text("✅ Ticaret sistemi başlatıldı!")

async def stop_trading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ticareti durdur"""
    await update.message.reply_text("🛑 Ticaret sistemi durduruluyor...")
    
    # Tüm işlemleri durdur
    bot_instance = context.bot_data.get('bot_instance')
    if bot_instance:
        for proc_name, proc in bot_instance.running_processes.items():
            try:
                proc.terminate()
                logger.info(f"{proc_name} durduruldu")
            except:
                pass
        bot_instance.running_processes.clear()
    
    await update.message.reply_text("✅ Ticaret sistemi durduruldu!")

async def get_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Güncel verileri göster"""
    bot_instance = context.bot_data.get('bot_instance')
    if not bot_instance:
        await update.message.reply_text("❌ Bot instance bulunamadı!")
        return
        
    current_data = bot_instance.read_latest_data()
    
    data_message = f"""
📊 **Güncel Market Verileri**

🔸 **Bitget**
Symbol: {current_data.get('perp_symbol', 'N/A')}
Kar Oranı: {current_data.get('perp_yuzde', {}).get('yuzde', 'N/A')}

🔸 **Gate.io**
Symbol: {current_data.get('gateio_symbol', 'N/A')}
Kar Oranı: {current_data.get('gateio_yuzde', {}).get('yuzde', 'N/A')}

⏰ Son güncelleme: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """
    
    await update.message.reply_text(data_message, parse_mode='Markdown')

async def emergency_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Acil durdurma - tüm pozisyonları kapat"""
    await update.message.reply_text("🚨 ACİL DURDURMA BAŞLATILIYOR...")
    
    try:
        # Bitget pozisyonlarını kapat
        subprocess.run(["python3", os.path.join(os.getcwd(), "PERP", "kapat.py")])
        
        # Gate.io pozisyonlarını kapat  
        subprocess.run(["python3", os.path.join(os.getcwd(), "gateio", "kapat.py")])
        
        await update.message.reply_text("✅ Tüm pozisyonlar kapatılmaya çalışıldı!")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Acil durdurma hatası: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Yardım komutu"""
    help_text = """
🆘 **Yardım - Bot Komutları**

**Temel Komutlar:**
/start - Botu başlat
/status - Sistem durumunu göster
/help - Bu yardım menüsü

**Ticaret Komutları:**
/start_trading - Otomatik ticareti başlat
/stop_trading - Otomatik ticareti durdur
/get_data - Güncel fiyat ve kar verilerini göster

**Acil Durum:**
/emergency_stop - Tüm pozisyonları kapat

**Not:** Bu bot sadece yetkili kullanıcılar için tasarlanmıştır.
API anahtarlarınızı güvenli bir şekilde sakladığınızdan emin olun.
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main():
    """Ana bot fonksiyonu"""
    # Bot token kontrolü
    BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable tanımlanmamış!")
        print("⚠️ Telegram bot token'ı tanımlanmamış. Bot çalışamayacak.")
        return
    
    # Bot instance oluştur
    bot_instance = CryptoTradingBot()
    
    # Application oluştur
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Bot instance'ı context'e ekle
    application.bot_data['bot_instance'] = bot_instance
    
    # Komut handler'larını ekle
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("start_trading", start_trading))
    application.add_handler(CommandHandler("stop_trading", stop_trading))
    application.add_handler(CommandHandler("get_data", get_data))
    application.add_handler(CommandHandler("emergency_stop", emergency_stop))
    application.add_handler(CommandHandler("help", help_command))
    
    logger.info("Telegram bot başlatılıyor...")
    print("🤖 Telegram bot başlatıldı!")
    
    # Bot'u çalıştır
    application.run_polling()

if __name__ == '__main__':
    main()