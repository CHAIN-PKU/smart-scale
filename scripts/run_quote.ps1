# Recognize a stand-in image and print its unit price. No network.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$env:VISION_PROVIDER = "mock"
$env:PRODUCT_INFO_PROVIDER = "mock"
& "$Root\.venv\Scripts\python.exe" -m scale_host.quote
