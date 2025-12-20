import ppadb
import time
from ppadb.client import Client


adb = Client(host="127.0.0.1", port=5037)  # Stops on one of these two lines
devices = adb.devices()

if len(devices) == 0:
    print("No device found")
    quit()

device = devices[0]

i = 1

while i < 8:
    print("Wait for Stamine Recharge")
    time.sleep(1200)

    print("Start of Mission Loop")
    print("Clicked Play button")
    device.shell("input tap 1075 681")
    time.sleep(2)

    print("Clicked Go Anyway button")
    device.shell("input tap 650 535")
    time.sleep(248)

    print("Clicked Replay button")
    device.shell("input tap 215 681")
    time.sleep(5)

    print("Clicked Continue button")
    device.shell("input tap 1075 681")
    print()

    i += 1
