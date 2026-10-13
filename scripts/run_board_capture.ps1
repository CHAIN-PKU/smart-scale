# Replay Zeng Yan's captured placement on a fake port. No COM port and no network.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
& "$Root\.venv\Scripts\python.exe" -m scale_host.board_capture
