# Refuse a display line when the scripted scale reports overload.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
& "$Root\.venv\Scripts\python.exe" -m scale_host.overload_guard
