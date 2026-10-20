# Price the simulated banana from the local table and print this portion.
# No photo and no network. Does not open a COM port.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:SCALE_DEVICE = "simulator"
$env:VISION_PROVIDER = "mock"
$env:PRODUCT_INFO_PROVIDER = "table"
Set-Location $Root
& "$Root\.venv\Scripts\python.exe" -m scale_host
