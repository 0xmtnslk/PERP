import time
import json

def read_symbol_from_file(file_path):
    with open(file_path, 'r') as file:
        return file.readline().strip()

def write_symbol_to_json(symbol, json_file_path):
    with open(json_file_path, 'w') as json_file:
        json.dump({"symbol": symbol}, json_file)

def main():
    text_file_path = '/root/PERP/new_coin_output.txt'
    json_file_path = '/root/PERP/new_coin_output.json'
    
    while True:
        symbol = read_symbol_from_file(text_file_path)
        write_symbol_to_json(symbol, json_file_path)
        time.sleep(1)  # Wait for 1 second before the next iteration

if __name__ == "__main__":
    main()
