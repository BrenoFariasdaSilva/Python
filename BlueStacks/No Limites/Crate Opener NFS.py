import ppadb
import time
from ppadb.client import Client


adb = Client(host='127.0.0.1', port=5037) #Stops on one of these two lines 
devices = adb.devices()

if len(devices) == 0:
    print("No device found")
    quit()

device = devices[0]

i = 1

while i <= 3: 
    print("Wait for Crate Unlock Cooldown")
    time.sleep (605)
    print("Start of {}º Defined Crate Openning Loop".format(i))

    if (i == 0) :    
        print("    Upgrade Crate")
        device.shell("input tap 622 383")
        time.sleep (5)

    print("    Get 1 - Free")
    device.shell("input tap 333 650")
    time.sleep (5)

    print("    Tap to Open Crate")
    device.shell("input tap 340 645")
    time.sleep (5)

    print("    Flip Card")
    device.shell("input tap 634 340")
    time.sleep (5)

    print("    Continue")
    device.shell("input tap 1140 662")
    time.sleep (5)

    print()

    i+=1

print("    Finished Open Crates Loop")