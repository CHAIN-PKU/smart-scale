# Price a scripted serial weight from the text reply. No COM port is opened.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
& "$Root\.venv\Scripts\python.exe" -m scale_host.serial_reply
