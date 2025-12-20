import ppadb
import time
from ppadb.client import Client


adb = Client(host="127.0.0.1", port=5037)  # Stops on one of these two lines
devices = adb.devices()

if len(devices) == 0:
    print("No device found")
    quit()

device = devices[0]

while True:
    print("Start of Race Loop")

    print("Clicked on Race")
    device.shell("input tap 1050 316")
    time.sleep(2)

    print("Clicked Car Select button")
    device.shell("input tap 1075 622")
    time.sleep(2)

    print("Clicked Race button")
    device.shell("input tap 1075 622")
    time.sleep(10)

    # Accelerator and Boost comands to include

    print("Clicked Race Stats button")
    device.shell("input tap 1075 681")
    time.sleep(2)

    print("Clicked Continue button")
    device.shell("input tap 1075 681")
    time.sleep(5)

    print("Clicked Prize Select button")
    device.shell("input tap 640 360")
    time.sleep(2)

    print("Clicked Continue button")
    device.shell("input tap 1075 681")
    time.sleep(3)

    print()
