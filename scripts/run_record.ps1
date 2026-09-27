# Store one simulated banana sale, then print the row read back from SQLite.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:VISION_PROVIDER = "mock"
$env:PRODUCT_INFO_PROVIDER = "mock"
& "$Root\.venv\Scripts\python.exe" -m scale_host.pipeline
