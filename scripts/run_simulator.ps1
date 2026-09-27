# Replay a scale scenario with the project virtual environment.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
$Scenario = "banana"
if ($args.Count -gt 0) {
    $Scenario = $args[0]
}
& "$Root\.venv\Scripts\python.exe" -m simulator --scenario $Scenario
