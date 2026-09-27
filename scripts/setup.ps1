# Recreate the project virtual environment. Does not install into the global Python.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Python = "C:\Users\wantinghe\AppData\Local\Programs\Python\Python310\python.exe"
if (-not (Test-Path $Python)) {
    throw "Python 3.10 was not found at $Python"
}

if (-not (Test-Path "$Root\.venv\Scripts\python.exe")) {
    & $Python -m venv "$Root\.venv"
}

& "$Root\.venv\Scripts\python.exe" -m pip install -U pip
& "$Root\.venv\Scripts\python.exe" -m pip install -e ".[dev]"
