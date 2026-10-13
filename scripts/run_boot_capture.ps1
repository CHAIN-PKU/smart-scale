# Replay the 2026-10-11 BOOT, READY, ERROR lines and one debug line. No COM port is opened.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
& "$Root\.venv\Scripts\python.exe" -m scale_host.boot_capture
