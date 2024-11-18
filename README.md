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
pip install python-bitget gate-api
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
```
{
        "bitget_example": {
        "api_key":"",
        "secret_key":"",
        "passphrase":"",                   # Bitget api key oluştururken girdiğiniz şifre
        "open_USDT": "100",                # İşlem açılacak bitget futures bakiyeniz   
        "close_yuzde": "1.20",             # İşlem açıldığında otomatik kapatılması için kar hedefi 1.20 ( %20 kar demek)
        "initial_symbol" : "XLMUSDT_UMCBL" # Upbit API'deki son USDT paritesindeki coin sembolü bitget formatında yazılacak
    },
        "gateio_example": {
        "api_key":"",
        "secret_key":"",
        "open_USDT": "100",                # İşlem açılacak gate.io futures bakiyeniz 
        "close_yuzde": 1.20,               # İşlem açıldığında otomatik kapatılması için kar hedefi 1.20 ( %20 kar demek)
        "initial_symbol" : "XLM_USDT"      # Upbit API'deki son USDT paritesindeki coin sembolü gate.io formatında yazılacak
    }
}
```

# Çalıştırma

## 1- Bir screen içinde "/root/PERP/upbit_market_tracker.py" çalıştırıyoruz sürekli upbit yeni coin taraması yapacak

```
screen -S API_tara
```
```
python3 /root/PERP/upbit_market_tracker.py
```


## 2- Bir screen içinde "symbol_gate.py" çalıştırıyoruz bu bizim upbit için tarama yaptığımız işlem çiftini gate.io formatına çevirecek.

```
screen -S API_gateio_symbol
```
```
python3 /root/gateio/symbol_gate.py
```

## 3- Bir screen içinde "secret.py" çalıştırıyoruz bunun görevi merkezi "secret.json" dosyasını ilgili jsonlara aktarmak. 
```
screen -S API_gateio_round
```
```
python3 /root/secret.py
```

## 4- Bir screen içinde "round_gate.py" çalıştırıyoruz  gate.io emir girmek için kaç kademeli yuvarlama yapacağını çekip formuluze eder.
```
screen -S API_gateio_round
```
```
python3 /root/gateio/round_gate.py
```

## 5- Bir screen içinde "bitget_perp_order.py" çalıştırıyoruz bu bizim otomasyon dosyamız.

```
screen -S API_bitget
```
```
python3 /root/bitget_perp_order.py
```

##  Acil durumlarda işlem durdurmak için CTRL+C ile  bitget_perp_order.py durdurup aşağıdaki komudu girin.

```
python3 /root/PERP/kapat.py
```

## 6- Bir screen içinde "gateio_perp_order.py" çalıştırıyoruz bu bizim otomasyon dosyamız.

```
screen -S API_gateio
```
```
python3 /root/gateio_perp_order.py
```

##  Acil durumlarda işlem durdurmak için CTRL+C ile  gateio_perp_order.py durdurup aşağıdaki komudu girin.

```
python3 /root/gateio/kapat.py
```


## Telegram bot için veri aktarmak istediğimiz için Bir screen içinde "telegram_degisken.py" çalıştırıyoruz bu txt uzantılı dosyamızın aynısını json olarak yazar.

```
screen -S API_Telegram_json
```
```
python3 /root/telegram_degisken.py
```

## Her Altı (6) python script sürekli çalışır durumda olacak screen içinde çalışacak. ( Not: telegram kısmı devreye alındığında çalışabilir)
