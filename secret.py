import json
import time

# Dosya yollarini tanimla
secret_file_path = '/root/secret.json'
bitget_file_path = '/root/PERP/secret.json'
gateio_file_path = '/root/gateio/secret.json'

# Sonsuz dongu
while True:
  try:
      # /root/secret.json dosyasini oku
      with open(secret_file_path, 'r') as file:
          data = json.load(file)

      # gateio_example verilerini gateio/secret.json dosyasina yaz
      gateio_data = data['gateio_example']
      with open(gateio_file_path, 'w') as file:
          json.dump({"gateio_example": gateio_data}, file, indent=4)

      # bitget_example verilerini PERP/secret.json dosyasina yaz
      bitget_data = data['bitget_example']
      with open(bitget_file_path, 'w') as file:
          json.dump({"bitget_example": bitget_data}, file, indent=4)

      print("Veriler basariyla guncellendi.")

  except FileNotFoundError:
      print("Hata: Belirtilen dosya bulunamadi.")
  except json.JSONDecodeError:
      print("Hata: JSON verisi cozulemedi.")
  except Exception as e:
      print(f"Beklenmeyen bir hata olustu: {e}")

  # Bir sonraki yinelemeden once 1 saniye bekle
  time.sleep(1)
