# Answer one local question about the banana price or the latest weighing.
# No scale and no network. Example: .\scripts\run_ask.ps1 香蕉多少钱
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
& "$Root\.venv\Scripts\python.exe" -m scale_host.ask @args
