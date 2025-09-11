#!/usr/bin/env python3
import os
import json
from datetime import datetime

print('🔧 YENİ COİN FİLTRELEME SİSTEMİ TEST')
print('=' * 40)

processed_coins_file = 'PERP/processed_coins.json'

def load_processed_coins():
    try:
        if os.path.exists(processed_coins_file):
            with open(processed_coins_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        return []

def save_processed_coin(symbol, title):
    try:
        processed_coins = load_processed_coins()
        
        new_entry = {
            'symbol': symbol,
            'title': title,
            'perp_symbol': symbol + 'USDT_UMCBL',
            'processed_at': datetime.now().isoformat()
        }
        
        processed_coins.append(new_entry)
        
        with open(processed_coins_file, 'w', encoding='utf-8') as f:
            json.dump(processed_coins, f, indent=2, ensure_ascii=False)
        
        print(f'💾 İşlenmiş coin kaydedildi: {symbol} -> {symbol}USDT_UMCBL')
        return True
        
    except Exception as e:
        print(f'❌ Kaydetme hatası: {e}')
        return False

def is_coin_already_processed(symbol):
    processed_coins = load_processed_coins()
    
    for entry in processed_coins:
        if entry.get('symbol') == symbol:
            processed_at = entry.get('processed_at', '')[:19]
            print(f'⚠️ {symbol} daha önce işlenmiş: {processed_at}')
            return True
    
    return False

def filter_new_coins_only(symbols):
    new_symbols = []
    
    for symbol in symbols:
        if not is_coin_already_processed(symbol):
            new_symbols.append(symbol)
            print(f'✅ YENİ: {symbol} (daha önce işlenmemiş)')
        else:
            print(f'🔄 ATLANIYOR: {symbol} (daha önce işlenmiş)')
    
    return new_symbols

# TEST SENARYOSU
print('📋 Test Senaryosu:')
test_symbols = ['PUMP', 'HOLO', 'LINEA', 'OPEN', 'WLD']

print('🔍 1. İlk filtreleme (hepsi yeni olmalı):')
new_symbols_1 = filter_new_coins_only(test_symbols)
print(f'✅ Sonuç: {len(new_symbols_1)}/{len(test_symbols)} yeni coin')

if new_symbols_1:
    # İlk 2 coini işlenmiş olarak işaretle
    test_coin_1 = new_symbols_1[0]
    test_coin_2 = new_symbols_1[1] if len(new_symbols_1) > 1 else new_symbols_1[0]
    
    print()
    print(f'📝 2. {test_coin_1} ve {test_coin_2} işlenmiş olarak kaydediliyor...')
    save_processed_coin(test_coin_1, f'Market Support for {test_coin_1}')
    save_processed_coin(test_coin_2, f'Market Support for {test_coin_2}')
    
    print()
    print('🔍 3. İkinci filtreleme (2 coin atlanmalı):')
    new_symbols_2 = filter_new_coins_only(test_symbols)
    print(f'✅ Sonuç: {len(new_symbols_2)}/{len(test_symbols)} yeni coin')
    
    expected_count = len(test_symbols) - 2
    if len(new_symbols_2) == expected_count:
        print('🎉 FİLTRELEME SİSTEMİ ÇALIŞIYOR!')
        print('✅ Daha önce işlenmiş coinler başarıyla atlandı')
    else:
        print('❌ Filtreleme sisteminde problem var')

print()
print('📊 İşlenmiş Coinler Listesi:')
processed_coins = load_processed_coins()
for coin in processed_coins:
    symbol = coin.get('symbol')
    processed_at = coin.get('processed_at', '')[:19]
    perp_symbol = coin.get('perp_symbol')
    print(f'  • {symbol} -> {perp_symbol} ({processed_at})')

print()
print('🎯 SİSTEM HAZIR!')
print('✅ Artık aynı coin iki kez işlenmeyecek')
print('✅ Sadece gerçek YENİ coinler için işlem açılacak')
