# Run the fused board flow: OpenMV frame, YOLO name, short-table price, scale serial.
param(
    [string]$CameraPort = "COM5",
    [string]$ScalePort = "COM3"
)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:SCALE_DEVICE = "serial"
$env:SERIAL_PORT = $ScalePort
$env:OPENMV_PORT = $CameraPort
$env:VISION_PROVIDER = "yolo"
$env:PRODUCT_INFO_PROVIDER = "table"
$env:SCALE_FRAME = Join-Path $Root "data\live\last_frame.jpg"
$env:SCALE_FRAME_MAX_AGE_S = "2"
Write-Output "OpenMV $CameraPort, scale $ScalePort. Close the OpenMV IDE serial connection, then reset the camera."
& "$Root\.venv\Scripts\python.exe" -m scale_host
