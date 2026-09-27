# Replay rising weights and price only the stable line. No COM port is opened.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:VISION_PROVIDER = "mock"
$env:PRODUCT_INFO_PROVIDER = "mock"
& "$Root\.venv\Scripts\python.exe" -m scale_host.serial_sequence
