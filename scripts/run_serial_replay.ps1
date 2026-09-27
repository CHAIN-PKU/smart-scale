# Replay a stable weight line and print the priced result. No COM port is opened.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:VISION_PROVIDER = "mock"
$env:PRODUCT_INFO_PROVIDER = "mock"
& "$Root\.venv\Scripts\python.exe" -m scale_host.serial_replay
