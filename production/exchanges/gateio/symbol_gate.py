import json
import time

def gateio_read_symbol_from_file(gateio_file_path):
  with open(gateio_file_path, 'r') as gateio_file:
      return gateio_file.readline().strip()

def gateio_format_symbol(gateio_symbol):
  if '_UMCBL' in gateio_symbol:
      gateio_symbol = gateio_symbol.replace('_UMCBL', '')
      gateio_symbol = gateio_symbol.replace('USDT', '_USDT')
  return gateio_symbol

def gateio_write_symbol_to_files(gateio_symbol, gateio_json_file_path, gateio_text_file_path):
  with open(gateio_json_file_path, 'w') as gateio_json_file:
      json.dump({"symbol": gateio_symbol}, gateio_json_file)
  
  with open(gateio_text_file_path, 'w') as gateio_text_file:
      gateio_text_file.write(gateio_symbol)

def main():
  import os
  BASE_DIR = os.getcwd()
  gateio_input_file_path = os.path.join(BASE_DIR, 'PERP', 'new_coin_output.txt')
  gateio_text_file_path = os.path.join(BASE_DIR, 'gateio', 'new_coin_output.txt')
  gateio_json_file_path = os.path.join(BASE_DIR, 'gateio', 'new_coin_output.json')
  
  while True:
      gateio_symbol = gateio_read_symbol_from_file(gateio_input_file_path)
      print(f"Read symbol: {gateio_symbol}")  # Hata ayiklama icin
      gateio_formatted_symbol = gateio_format_symbol(gateio_symbol)
      print(f"Formatted symbol: {gateio_formatted_symbol}")  # Hata ayiklama icin
      gateio_write_symbol_to_files(gateio_formatted_symbol, gateio_json_file_path, gateio_text_file_path)
      print("Symbol written to files.")  # Hata ayiklama icin
      time.sleep(1)

if __name__ == "__main__":
  main()
