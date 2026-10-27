# OpenMV Cam H7 Plus real-time JPEG stream over USB VCP.
#
# Frame format, little endian:
#   A5 5A | uint32 JPEG length | JPEG bytes
#
# The PC receiver should always keep only the newest complete frame.

import sensor
import time
import struct
import pyb

sensor.reset()
sensor.set_pixformat(sensor.RGB565)
sensor.set_framesize(sensor.VGA)
sensor.skip_frames(time=2000)

usb = pyb.USB_VCP()
usb.setinterrupt(-1)

running_led = pyb.LED(1)
frame_led = pyb.LED(2)
running_led.on()

while True:
    img = sensor.snapshot()
    jpg = img.compress(quality=70)

    try:
        usb.send(struct.pack("<BBI", 0xA5, 0x5A, len(jpg)), timeout=1000)
        usb.send(jpg, timeout=3000)
        frame_led.toggle()
    except OSError:
        pass

    time.sleep_ms(300)
