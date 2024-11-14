import json
import time
import os

# Define the mapping of mark_price_round to round_gate
round_gate_mapping = {
  0.1: 1,
  0.01: 2,
  0.001: 3,
  0.0001: 4,
  0.00001: 5,
  1e-05: 5,
  0.000001: 6,
  1e-06: 6,
  0.0000001: 7,
  1e-07: 7,
  0.00000001: 8,
  1e-08: 8,
  0.000000001: 9,
  1e-09: 9
}

# Dosya yollarÄ±
secret_file_path = '/root/secret.json'
bitget_file_path = '/root/PERP/secret.json'
gateio_file_path = '/root/gateio/secret.json'

# Infinite loop to continuously read the JSON file
while True:
  try:
      # secret.json dosyasÄ±nÄ± oku ve verileri kopyala
      with open(secret_file_path, 'r') as file:
          data = json.load(file)

      # bitget_example verilerini PERP/secret.json dosyasÄ±na yaz
      bitget_data = data['bitget_example']
      with open(bitget_file_path, 'w') as file:
          json.dump({"bitget_example": bitget_data}, file, indent=4)

      # gateio_example verilerini gateio/secret.json dosyasÄ±na yaz
      gateio_data = data['gateio_example']
      with open(gateio_file_path, 'w') as file:
          json.dump({"gateio_example": gateio_data}, file, indent=4)

      # JSON dosyasÄ±nÄ± oku
      with open('/root/gateio/perp_sorgu.json', 'r') as json_file:
          perp_data = json.load(json_file)
          print(perp_data)  # Print the entire JSON data for debugging
          gateio_mark_price_round = float(perp_data['mark_price_round'])  # Convert to float
          print(f"mark_price_round: {gateio_mark_price_round}")  # Print the value

      # Determine the round_gate value
      rounded_value = round(gateio_mark_price_round, 10)  # Adjust precision as needed
      round_gate = round_gate_mapping.get(rounded_value, None)

      # Check if round_gate is None
      if round_gate is None:
          print(f"Warning: No matching round_gate found for mark_price_round: {gateio_mark_price_round}")

      # Write the round_gate value to a file
      if round_gate is not None:
          with open('/root/gateio/round_gate.txt', 'w') as file:
              file.write(str(round_gate))

      # Print the round_gate value
      print(f"round_gate: {round_gate}")

  except FileNotFoundError:
      print("Error: The specified JSON file was not found.")
  except json.JSONDecodeError:
      print("Error: Failed to decode JSON from the file.")
  except Exception as e:
      print(f"An unexpected error occurred: {e}")

  # Wait for 1 second before the next iteration
  time.sleep(1)
