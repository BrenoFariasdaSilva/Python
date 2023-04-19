from itertools import count
import ppadb
import time
from ppadb.client import Client

adb = Client(host='127.0.0.1', port=5037) #Stops on one of these two lines 
devices = adb.devices()

if len(devices) == 0:
    print("No device found")
    quit()

device = devices[0]
race = 1
raceTime = 4

# Rep per match = 33
# Money per match = 2600
# Match duration = 40s

firstCarEnergy = 6
secondCarEnergy = 6
tickets = 1

while (tickets > 0): 
    device.shell("input tap 2081 939") # Play Button
    print("Play Button")
    time.sleep (1.0)
    
    device.shell("input tap 377 909") # Never Show Again Button
    device.shell("input tap 1357 874") # Play Anyway Button
    
    time.sleep (1.0)
    counter = 1

    while (counter <= 15): # 4.0 seconds per iteration // 60.0 seconds full cycle
        boost = 0
        while (boost < 3): # 3.0s
            device.shell("input tap 2044 826") # Boost Button
            time.sleep (0.2)
            device.shell("input tap 2044 826") # Boost Button
            time.sleep (0.8)
            boost += 1
            
        device.shell ("input touchscreen swipe 371 887 371 887 1000") # Drift Button for 1 second
        
        counter += 1
        if ((counter * raceTime) % 20 == 0):
            print("Match laping for {} seconds".format(counter * raceTime))
    
    counter = 0
    while (counter < 8): # 1.0 seconds per iteration // 8 seconds full cycle
        device.shell("input tap 2309 104") # Skip Add 
        time.sleep (0.25)
        device.shell("input tap 1973 948") # Next Button
        time.sleep (0.25)
        device.shell("input tap 1973 948") # Miss Out Button
        time.sleep (0.25)
        device.shell("input tap 2000 955") # Race Button
        time.sleep (0.25)
        counter += 1
        
    time.sleep (5.0) # Trade Coins Delay
    print("End of {} Race \n".format(race))
    race += 1
    tickets -= 1