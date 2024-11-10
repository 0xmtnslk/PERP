# -*- coding: utf-8 -*-
import time
import json
import subprocess

# Dosya yolları
new_coin_file = "/root/PERP/new_coin_output.txt"
secret_file = "/root/PERP/secret.json"
long_script = "/root/PERP/long.py"

# secret.json dosyasını oku
with open(secret_file, 'r') as f:
    secrets = json.load(f)
    initial_symbol = secrets["bitget_example"]["initial_symbol"]

print(f"Başlangıç sembolü: {initial_symbol}")

# İlk değer kontrolü
while True:
    # new_coin_output.txt dosyasını oku
    with open(new_coin_file, 'r') as f:
        symbol = f.read().strip()

    print(f"Okunan sembol: {symbol}")

    # Değerleri karşılaştır
    if symbol != initial_symbol:
        print(f"Semboller farklı! '{symbol}' ile '{initial_symbol}' karşılaştırıldı.")
        # Farklı ise long.py scriptini çalıştır
        subprocess.run(["python3", long_script])
        break
    else:
        # Aynı ise mesaj yazdır ve 1 saniye bekle
        print("Upbit Yeni Coin Listelenmedi, Tekrar Kontrol Ediyorum...")
        time.sleep(1)
