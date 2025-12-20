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

while i <= 2:
    print("Wait for Crate Unlock Cooldown")
    time.sleep(605)

    print("Start of {}º Defined Crate Openning Loop".format(i))
    print("Clicked Open Crate button")
    device.shell("input tap 1090 548")
    time.sleep(10)

    print("Clicked To Skip Prize button")
    device.shell("input tap 1090 548")

    print()

    i += 1
