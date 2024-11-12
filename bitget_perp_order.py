# -*- coding: utf-8 -*-
import time
import json
import subprocess

# Dosya yollari
new_coin_file = "/root/PERP/new_coin_output.txt"
secret_file = "/root/PERP/secret.json"
long_script = "/root/PERP/long.py"
leverage_script = "/root/PERP/leverage.py"  # leverage.py dosyasinin yolunu ekledim

# secret.json dosyasini oku
with open(secret_file, 'r') as f:
  secrets = json.load(f)
  initial_symbol = secrets["bitget_example"]["initial_symbol"]

print(f"Baslangic sembolu: {initial_symbol}")

# Ilk deger kontrolu
while True:
  # new_coin_output.txt dosyasini oku
  with open(new_coin_file, 'r') as f:
      symbol = f.read().strip()

  print(f"Okunan sembol: {symbol}")

  # Degerleri karsilastir
  if symbol != initial_symbol:
      print(f"Semboller farkli! '{symbol}' ile '{initial_symbol}' karsilastirildi.")
      # Farkli ise once leverage.py ve ardindan long.py scriptini calistir
      subprocess.run(["python3", leverage_script])
      subprocess.run(["python3", long_script])
      break
  else:
      # Ayni ise mesaj yazdir ve 1 saniye bekle
      print("Upbit Yeni Coin Listelenmedi, Tekrar Kontrol Ediyorum...")
      time.sleep(1)
