# Print the V1 display line for the loopback banana sale. No COM port is opened.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
& "$Root\.venv\Scripts\python.exe" -m scale_host.display_line
