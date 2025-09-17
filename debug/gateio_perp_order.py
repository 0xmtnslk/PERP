# -*- coding: utf-8 -*-
import time
import json
import subprocess

# Dosya yollari
import os
BASE_DIR = os.getcwd()
new_coin_file = os.path.join(BASE_DIR, "gateio", "new_coin_output.txt")
secret_file = os.path.join(BASE_DIR, "gateio", "secret.json")
long_script = os.path.join(BASE_DIR, "gateio", "gateio_long.py")


# secret.json dosyasini oku
with open(secret_file, 'r') as f:
  secrets = json.load(f)
  gateio_initial_symbol = secrets["gateio_example"]["initial_symbol"]

print(f"Baslangic sembolu: {gateio_initial_symbol}")

# Ilk deger kontrolu
while True:
  # new_coin_output.txt dosyasini oku
  with open(new_coin_file, 'r') as f:
      gateio_symbol = f.read().strip()

  print(f"Okunan sembol: {gateio_symbol}")

  # Degerleri karsilastir
  if gateio_symbol != gateio_initial_symbol:
      print(f"Semboller farkli! '{gateio_symbol}' ile '{gateio_initial_symbol}' karsilastirildi.")
      # Farkli ise long.py scriptini calistir
      subprocess.run(["python3", long_script])
      break
  else:
      # Ayni ise mesaj yazdir ve 1 saniye bekle
      print("Upbit Yeni Coin Listelenmedi, Tekrar Kontrol Ediyorum...")
      time.sleep(1)
