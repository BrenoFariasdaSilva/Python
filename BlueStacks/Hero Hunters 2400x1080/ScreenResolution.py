from itertools import count
from datetime import datetime
from ppadb.client import Client
import os
import re

adb = Client(host="127.0.0.1", port=5037)  # Stops on one of these two lines
devices = adb.devices()

if len(devices) == 0:
    print("No device found")
    quit()

device = devices[0]


def select_device():
    process = os.popen("adb devices -l")
    output = process.read()
    devicelist = [i for i in output.split("\n") if i]
    devicelist.pop(0)

    print("Choose your device: ")
    for i in range(len(devicelist)):
        print(f"{i}: {devicelist[i]}")
    return devicelist[int(input())].split(" ")[0]


deviceID = select_device()


def get_screen_size():
    output = device.shell(f"wm size")
    m = re.search(r"(\d+)x(\d+)", output)

    if m:
        return {"width": int(m.group(2)), "height": int(m.group(1))}
    return None


# width = x = 2400
# height = y = 1080

phoneResolution = get_screen_size()
print(f"Current Screen Resolution: {phoneResolution['width']} x {phoneResolution['height']}")
