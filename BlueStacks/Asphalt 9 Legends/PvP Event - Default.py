from itertools import count
import ppadb
import time
from ppadb.client import Client

adb = Client(host="127.0.0.1", port=5037)  # Stops on one of these two lines
devices = adb.devices()

if len(devices) == 0:
    print("No device found")
    quit()

device = devices[0]
loop = 1

# Money = 959.000
# Tokens = 3481
# Time = 13:34
# Rating = 1196
# Score = 750
# Postion = 6864
# Battery = 55%

while True:
    print("Start of {} loop".format(loop))
    device.shell("input tap 1552 977")  # Play Button
    device.shell("input tap 1552 977")  # Play Button
    print("Clicked Play button")
    time.sleep(2)
    device.shell("input tap 2081 939")  # Play Button
    device.shell("input tap 1552 977")  # Play Button
    print("Clicked Play button on Car Selection")
    counter = 0

    while counter < 20:
        boost = 0
        while boost < 3:
            device.shell("input tap 2044 826")  # Boost Button
            time.sleep(0.2)
            device.shell("input tap 2044 826")  # Boost Button
            time.sleep(1.0)
            boost += 1
        device.shell("input touchscreen swipe 371 887 371 887 1000")  # Drift Button for 1 second
        if counter % 10 == 0:
            print("Match laping for {} seconds".format(counter * 4))
        counter += 1

    print("Match laping for {} seconds \n".format(counter * 4))

    counter = 0
    while counter < 10:
        device.shell("input tap 2281 156")  # Skip Add
        time.sleep(0.5)
        device.shell("input tap 1973 948")  # Next Button
        time.sleep(0.5)
        device.shell("input tap 1973 948")  # Miss Out Button
        time.sleep(0.5)
        counter += 1
    loop += 1
