# Price one simulated banana placement from the local table. No photo and no network.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
& "$Root\.venv\Scripts\python.exe" -c @"
from scale_host.catalog import TableProductInfo
from scale_host.domain import ScaleStatus, WeightReading
from scale_host.fusion import PlacementPricer
from scale_host.quote import identify_and_price
from scale_host.vision import MockVision

quote = identify_and_price('banana.jpg', MockVision(), TableProductInfo())
pricer = PlacementPricer()
first = pricer.consider(WeightReading(seq=1, timestamp_ms=1000, weight_g=326.4, stable=True, tare_g=0.0, status='ok', state=ScaleStatus.WEIGHT_STABLE), quote)
second = pricer.consider(WeightReading(seq=2, timestamp_ms=2000, weight_g=327.0, stable=True, tare_g=0.0, status='ok', state=ScaleStatus.WEIGHT_STABLE), quote)
print(f'label: {first.label}')
print(f'weight_g: {first.weight_g}')
print(f'amount_yuan: {first.amount_yuan:.2f}')
print(f'portion_kcal: {first.portion_kcal}')
print(f'portion_carb_g: {first.portion_carb_g}')
print('second_price: yes' if second is not None else 'second_price: no')
print('sent_to_internet: no')
"@
