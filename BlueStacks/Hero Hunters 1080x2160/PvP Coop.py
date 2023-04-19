import ppadb
import time
from ppadb.client import Client


adb = Client(host='127.0.0.1', port=5037) #Stops on one of these two lines 
devices = adb.devices()

if len(devices) == 0:
    print("No device found")
    quit()

device = devices[0]

while True: 
    print("Start of PvP Coop Match")
    
    print("Clicked Ready button")
    device.shell("input tap 630 650") #Ready Button
    time.sleep (1)
    
    print("Clicked Invite Player button")
    device.shell("input tap 160 680") #Invite Player Button
    time.sleep (4)
    print()