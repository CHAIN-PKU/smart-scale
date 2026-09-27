# Run the tests that do not need a physical STM32.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
& "$Root\.venv\Scripts\python.exe" -m pytest "$Root\tests"
