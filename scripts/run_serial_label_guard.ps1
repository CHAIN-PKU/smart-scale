# A scripted stable weight is not priced when the two labels disagree.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
& "$Root\.venv\Scripts\python.exe" -m scale_host.serial_label_guard
