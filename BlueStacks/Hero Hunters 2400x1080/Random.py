from itertools import count
import time
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

coords = {
    "btnPlayPVPMatch": {"x": 0.8425, "y": 0.92962963},
    "btnRetry": {"x": 0.54321, "y": 0.12345},
    "btnFreePlayPVP": {"x": 0.32583, "y": 0.53425},
    "btnOpenPVPCrateRewards": {"x": 0.23166, "y": 0.51111},
}

phoneResolution = get_screen_size()
print(get_screen_size())

while True:  # ((now.hour <= nextResetHour) and (now.minute <= nextResetMinute)):
    a = (coords["btnPlayPVPMatch"]["x"]) * (phoneResolution["width"])
    b = (coords["btnPlayPVPMatch"]["y"]) * (phoneResolution["height"])
    print(f"Smartphone btnPlayPVPMatch.x: {a:.2f}")
    print(f"Smartphone btnPlayPVPMatch.y: {b:.2f}")
    device.shell(f"input tap {a} {b}")  # Maybe here it will start a PVP Match - Play Button
    time.sleep(1.5)
