import ppadb
import time
from ppadb.client import Client

adb = Client(host="127.0.0.1", port=5037)  # Stops on one of these two lines
devices = adb.devices()

if len(devices) == 0:
    print("No device found")
    quit()

device = devices[0]

print("START OF BOUNTY MATCHES")
print()

i = 1

while True:
    print("Start of {}º Bounty Loop".format(i))

    print("    Missions")
    for x in range(0, 3):
        device.shell("input tap 1090 1040")  # Update Coordinates
        time.sleep(0.5)

    print("    Events")
    device.shell("input tap 822 777")  # Update Coordinates
    time.sleep(1)

    print("    Join Hunt")
    device.shell("input tap 514 567")  # Update Coordinates
    time.sleep(1)

    print("    Continue Activity Log")
    device.shell("input tap 696 860")
    time.sleep(1)

    print("    Select Bounty Match")
    device.shell("input tap 777 874")  # Select Bounty Button
    time.sleep(1)

    print("    Start Hunt")
    device.shell("input tap 1833 1008")
    time.sleep(1)

    print("    Unselecting Heroes")
    for x in range(135, 925, 170):  # Unselect Heroes
        device.shell(f"input tap {x} 182")  # Hero Unselect

    print("    Swipe to Start")
    for x in range(74, 615, 130):  # Swipe all back
        device.shell("input touchscreen swipe 70 359 1183 359 500")

    time.sleep(1)

    print("    Selecting Heroes")
    for z in range(0, 6):
        for x in range(111, 1183, 130):
            for y in range(359, 476, 116):
                device.shell(f"input tap {x} {y}")  # Hero Select
                time.sleep(0.3)

                device.shell("input tap 229 95")  # Click fora 113 242

        if z != 0:
            print(f"    {z}º Swipe then Start Bounty Match")

        device.shell("input tap 1075 681")  # Start Bounty Button
        time.sleep(1)

        print("    Go Anyway")
        device.shell("input tap 1328 675")
        time.sleep(1)

        device.shell("input tap 229 95")  # Click fora 113 242

        device.shell("input touchscreen swipe 1183 359 70 359 2750")
        time.sleep(2)

    print("    Start of Bounty Match")
    device.shell("input tap 1833 1008")  # Start Bounty Button
    time.sleep(1)

    print("    Go Anyway")
    device.shell("input tap 1328 675")
    time.sleep(70)

    print("    Continue")
    device.shell("input tap 1135 677")
    time.sleep(1)

    print("    Continue Activity Log")
    device.shell("input tap 635 660")  # Update Coordinates
    time.sleep(1)

    print("    Dismiss Bounty")
    for x in range(0, 5):
        device.shell("input tap 1117 681")  # Update Coordinates
        time.sleep(0.3)

    print("    Continue Activity Log")
    device.shell("input tap 637 626")
    time.sleep(1)

    print("    Back")
    for x in range(0, 2):
        device.shell("input tap 94 39")
        time.sleep(0.5)

    print()
    i += 1


# input touchscreen swipe <x1> <y1> <x2> <y2> [duration(ms)] (Default: touchscreen)
