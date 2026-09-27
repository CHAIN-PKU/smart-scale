# Price the rising banana line, then store a correction. No COM port and no network.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:VISION_PROVIDER = "mock"
$env:PRODUCT_INFO_PROVIDER = "mock"
& "$Root\.venv\Scripts\python.exe" -m scale_host.correct
