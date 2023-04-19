from itertools import count
import ppadb
import time
from datetime import datetime
from ppadb.client import Client

adb = Client(host='127.0.0.1', port=5037) #Stops on one of these two lines 
devices = adb.devices()

if len(devices) == 0:
    print("No device found")
    quit()

device = devices[0]

# Screen Resolution: 2400 x 1080

# Logic:
# 1º Select Heroes
# 2º Play Button
# 3º For 180s -> tap skill buttons
# 4º Next Button (End of match)
# 5º Next Button (crate count)
# 6º Open Crate Button (Tap like 5 times)
# 7º Free Play Button

# Smartphone Resources:
# Time: 15:35h
# Battery: 86%

# Game Resources
# PvP Coins: 5680
# Heronium: 3350
# Gold: 2330
# Money: 1.764.728

i = 1
now = datetime.now()
current_time = now.strftime("%H:%M:%S")

matchDuration = 150 
nextResetHour = 0
nextResetMinute = 55
heroesLives = 3
amountOfHeroes = 102
remainingHeroes = heroesLives * amountOfHeroes

if (now.hour >= 0 and now.minute >= 1) and (now.hour <= 10 and now.minute <= 55):
    nextResetHour = 10
elif (now.hour >= 10 and now.minute >= 1) and (now.hour <= 23 and now.minute <= 55):
    nextResetHour = 22
    
print("Next Reset- {}:{}".format(nextResetHour, nextResetMinute))

while (remainingHeroes >= 5): # ((now.hour <= nextResetHour) and (now.minute <= nextResetMinute)): 
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    print("Start of {} PvP Loop {}".format(i, current_time))
    
    print("Unselecting Heroes")
    for x in range (210, 1250, 158) : # Unselect Heroes
        device.shell (f"input tap {x} 280") # Hero Unselect
        
    print("Swipe to Start") 
    for x in range (74, 615, 130) : # Swipe all back
        device.shell (f"input touchscreen swipe 70 680 1183 680 100")
    time.sleep (1.0) 
      
    print("Selecting Heroes")
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    print("Start of Heroes Select: {}".format(current_time))
    
    for z in range (0, 3) : 
        device.shell (f"input touchscreen swipe 2258 550 550 550 1700") # Swipe to next heroes page
        time.sleep (1.5)
        
    for z in range (0, 2) : 
        for x in range (250, 2257, 182) : # Change x (Pick Line Heros)
            for y in range (547, 781, 233): # Change y (Pick Column Heroes) 
                device.shell (f"input tap {x} {y}") # Hero Select on 1º line
                time.sleep (0.3)
                device.shell (f"input tap 1252 42") # Inoffensive touch for avoiding "Revive Hero Lives"
         
        device.shell (f"input tap 2022 1004") # Maybe here it will start a PVP Match - Play Button
        device.shell (f"input tap 1252 42") # Inoffensive touch for avoiding "Go Anyway"
        device.shell (f"input touchscreen swipe 2258 550 550 550 1700") # Swipe to next heroes page
        time.sleep (1.5)
      
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    print("End of Heroes Select: {}".format(current_time))
    device.shell (f"input tap 2022 1004") # Start PVP Match - Play Button
    device.shell (f"input tap 1252 42") # Inoffensive touch for avoiding "Go Anyway"
        
    matchTime = 1
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    print("Start of Match - {}".format(current_time))
    while matchTime <= matchDuration:
        time.sleep (1)
        matchTime += 1
        if (matchTime % 30 == 0):
            device.shell (f"input tap 1252 42") # Inoffensive touch for avoiding Screen Lock
            now = datetime.now()
            current_time = now.strftime("%H:%M:%S")
            print("   {} seconds passed - {}".format(matchTime, current_time))
       
    print("End of Match - {}".format(current_time))
    device.shell (f"input tap 2222 1014") # Next Button
    time.sleep (1)
    device.shell (f"input tap 782 577") # Free Play Button
    time.sleep (1)
    device.shell (f"input tap 2222 1014") # Next Button
    time.sleep (0.5)
    device.shell (f"input tap 1263 950") # Claim Button 5/5
    time.sleep (1)
    
    matchTime = 0
    while (matchTime <= 3):
        device.shell (f"input tap 556 552") # Open Crate - Free Play Coordinates
        time.sleep (0.2)
        matchTime += 0.2
        
    device.shell (f"input tap 782 577") # Free Play Button
    print("")
    
    remainingHeroes -= 5
    i+= 1