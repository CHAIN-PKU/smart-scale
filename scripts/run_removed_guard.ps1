# Refuse a display line when the scripted scale reports the item was removed.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
& "$Root\.venv\Scripts\python.exe" -m scale_host.removed_guard
