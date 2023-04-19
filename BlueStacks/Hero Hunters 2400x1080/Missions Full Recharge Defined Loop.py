import ppadb
import time
from ppadb.client import Client


adb = Client(host='127.0.0.1', port=5037) #Stops on one of these two lines 
devices = adb.devices()

if len(devices) == 0:
    print("No device found")
    quit()

device = devices[0]

print("Waiting for Full Recharge.")
time.sleep (18000)

i = 1

while i <= 10: 
    print("Start of {}º Defined Missions Loop".format(i))
    print("Clicked Play button")
    device.shell (f"input tap 1075 681")
    time.sleep (2)

    print("Clicked Go Anyway button")
    device.shell (f"input tap 650 535")
    time.sleep (54)

    print("Clicked Replay button")
    device.shell (f"input tap 215 681")
    time.sleep (2)

    print("Clicked Continue button")
    device.shell (f"input tap 1075 681")
    time.sleep (2)
    
    print()

    i+=1