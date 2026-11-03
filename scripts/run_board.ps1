# Run the fused board flow: OpenMV frame, YOLO name, short-table price, scale serial.
param(
    [string]$CameraPort = "COM5",
    [string]$ScalePort = "COM3",
    [string]$BluetoothPort = ""
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
$env:DESK = "1"
$env:DESK_HOST = "0.0.0.0"
$env:DESK_PORT = "8765"
if ($BluetoothPort) {
    $env:BT_PORT = $BluetoothPort
    $env:BT_BAUD = "9600"
}
Write-Output "OpenMV $CameraPort, scale $ScalePort. Close the OpenMV IDE serial connection, then reset the camera."
Write-Output "Live page http://127.0.0.1:8765 . A phone on the same Wi-Fi can open the address printed as desk_lan."
& "$Root\.venv\Scripts\python.exe" -m scale_host
