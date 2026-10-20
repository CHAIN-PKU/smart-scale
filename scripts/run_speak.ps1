# Say the simulated banana price on this computer's speaker.
# No scale and no network. A failed speaker still leaves the price printed.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
& "$Root\.venv\Scripts\python.exe" -m scale_host.speech
