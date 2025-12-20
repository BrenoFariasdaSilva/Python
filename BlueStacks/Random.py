import ppadb
import time
from datetime import datetime
from ppadb.client import Client

adb = Client(host="127.0.0.1", port=5037)  # Stops on one of these two lines
devices = adb.devices()

if len(devices) == 0:
    print("No device found")
    quit()

device = devices[0]

with open("screenshot.png", "wb") as fp:
    fp.write(device.screencap())


# input touchscreen swipe <x1> <y1> <x2> <y2> [duration(ms)] (Default: touchscreen)
