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

while True:
    print("Start of {}º PvP Match".format(i))
    print("Clicked Play button")
    device.shell("input tap 1075 681")  # Play Button
    time.sleep(180)
    print("Clicked Next button")
    device.shell("input tap 1075 681")  # Next Button
    time.sleep(2)
    print("Clicked Next button")
    device.shell("input tap 1075 681")  # Play Button
    time.sleep(2)
    print("Clicked Open Crate button")
    device.shell("input tap 640 605")  # Open Crate Button
    time.sleep(5)
    device.shell("input tap 640 605")  # Open Crate Button
    time.sleep(5)
    device.shell("input tap 640 605")  # Open Crate Button
    time.sleep(5)
    print("Clicked PvP button")
    device.shell("input tap 455 375")
    time.sleep(2)
    print("Clicked Play button")
    device.shell("input tap 1075 681")  # Play Button
    print()
    i += 1
