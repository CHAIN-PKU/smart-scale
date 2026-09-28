# Price the stable weight that follows a sensor error. No COM port is opened.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
& "$Root\.venv\Scripts\python.exe" -m scale_host.error_then_stable
