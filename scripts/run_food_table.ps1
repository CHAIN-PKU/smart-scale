# Print the demo banana row. No photo and no network.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
& "$Root\.venv\Scripts\python.exe" -c "from scale_host.catalog import build_product_info; info = build_product_info('table').lookup('banana'); print(f'label: {info.label}'); print(f'price_per_kg: {info.price_per_kg}'); print(f'kcal_per_100g: {info.kcal_per_100g}'); print(f'carb_per_100g: {info.carb_per_100g}'); print('sent_to_internet: no')"
