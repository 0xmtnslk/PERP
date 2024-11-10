# 1. Python ve pip Kurulumu
```
sudo apt-get update && sudo apt-get upgrade -y
```
```
sudo apt install -y python3 python3-pip
```

# 2. Sanal Ortam Oluşturma
```
sudo apt install -y python3-venv
```
```
python3 -m venv myprojectenv
```
```
source myprojectenv/bin/activate
```

# 3. Gerekli Python Kütüphanelerini Yükleme
```
pip install python-bitget
```
```
pip install bitget-python-connector
```
```
pip install requests
```
```
pip install websocket-client
```

# 4.PERP klasörü içinde secret.json dosya içinde API bilgilerinizi değiştirin

api_key = ""
secret_key = ""
passphrase = ""
initial_symbol = ""


## Çalıştırma

// Bir screen içinde "/root/PERP/upbit_market_tracker.py" çalıştırıyoruz sürekli upbit yeni coin taraması yapacak

```
screen -S API_tara
```
```
python3 /root/PERP/upbit_market_tracker.py
```
// Bir screen içinde "bitget_perp_order.py" çalıştırıyoruz bu bizim otomasyon dosyamız
```
screen -S bitget_islem
```
```
python3 bitget_perp_order.py
```

// Her 2 dosya sürekli çalışır durumda olacak screen içinde.
