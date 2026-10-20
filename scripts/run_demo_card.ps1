# Print the defense card from the recognized banana and the simulated weight.
# No scale and no network.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
& "$Root\.venv\Scripts\python.exe" -m scale_host.demo_card
