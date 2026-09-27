# Skip rising scripted weights, then price the stable line from the text reply.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
& "$Root\.venv\Scripts\python.exe" -m scale_host.serial_reply_sequence
