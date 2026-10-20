# Price the recognized OpenMV banana on the simulated scale.
# No new photo request and no COM port.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
& "$Root\.venv\Scripts\python.exe" -m scale_host.recognized_sale
