# Price a stable weight from loopback replies. The vision price is ignored.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
& "$Root\.venv\Scripts\python.exe" -m scale_host.reply_sale
