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

while i <= 3:
    print("Start of Solo Raid {} Loop".format(i))
    print("    Play")
    device.shell("input tap 1075 681")
    time.sleep(2)

    print("    Go Anyway")
    device.shell("input tap 650 535")
    time.sleep(124)

    print("    Replay")
    device.shell("input tap 215 681")
    time.sleep(2)

    print("    Continue")
    device.shell("input tap 1075 681")
    time.sleep(2)
    print()

    i += 1
