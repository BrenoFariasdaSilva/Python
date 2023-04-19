from itertools import count
import ppadb
import time
from datetime import datetime
from ppadb.client import Client
import os
import re

# Smartphone Resources:
# Time: 10:55h
# Battery: 54%

# Game Resources
# PvP Coins: 9660
# Heronium: 550
# Gold: 2492
# Money: 1.030.000

adb = Client(host='127.0.0.1', port=5037) #Stops on one of these two lines 
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
		print(f'{i}: {devicelist[i]}')
	return devicelist[int(input())].split(" ")[0]

deviceID = select_device()

def get_screen_size():
    output = device.shell (f'wm size')
    m = re.search(r'(\d+)x(\d+)', output)
    
    if m:
        return {'width': int(m.group(2)), 'height': int(m.group(1))}
    return None

phoneResolution = get_screen_size()
print(f"Current Screen Resolution: {phoneResolution['width']} x {phoneResolution['height']}")

# width = x = 2400
# height = y = 1080

coords = {
    'btnPlayPVPMatch' : {
        'x' : 0.8425,
        'y' : 0.92962963
    },
    'btnHeroUnselect' : {
        'xStart' : 0.0875,
        'xEnd' : 0.520833333,
        'xDelta' : 0.0658333333,
        'y' : 0.259259259
    },
    'btnHeroSelect' : {
        'xStart' : 0.104166667,
        'xEnd' : 0.940416667,
        'xDelta' : 0.0758333333,
        'yStart' : 0.506481481,
        'yEnd' : 0.723148148,
        'yDelta' : 0.215740741
    },
    'btnAvoidAction' : {
        'x' : 0.52125,
        'y' : 0.0388888889
    },
    'btnSwipeToPreviousPage' : {
        'xStart' : 0.0291666667,
        'xEnd' : 0.492916667,
        'y' : 0.62962963
    },
    'btnSwipeToNextPage' : {
        'xStart' : 0.916666667,
        'xEnd' : 0.25,
        'y' : 0.509259259
    },
    'btnNext' : {
        'x' : 0.8425,
        'y' : 0.92962963
    },
    'btnPVPFreePlay' : {
        'x' : 0.22125,
        'y' : 0.511111111
    },
    'btnOpenPVPCrate' : {
        'x' : 0.52625, # 1136.7
        'y' : 0.87962963 # 950
    },
}

i = 1
now = datetime.now()
current_time = now.strftime("%H:%M:%S")

matchDuration = 150 
nextResetHour = 0
nextResetMinute = 55
heroesLives = 3
amountOfHeroes = 102
remainingHeroes = heroesLives * amountOfHeroes
amountOfHeroesPages = 5

if (now.hour >= 0 and now.minute >= 1) and (now.hour <= 10 and now.minute <= 55):
    nextResetHour = 10
elif (now.hour >= 10 and now.minute >= 1) and (now.hour <= 23 and now.minute <= 55):
    nextResetHour = 22
    
print("Next Reset- {}:{}".format(nextResetHour, nextResetMinute))

while (remainingHeroes >= 5): # ((now.hour <= nextResetHour) and (now.minute <= nextResetMinute)): 
    print(f"Line 204 - btnPlayPVPMatch")
    xNextButton = int ((coords['btnPlayPVPMatch']['x']) * (phoneResolution['width']))
    yNextButton = int ((coords['btnPlayPVPMatch']['y']) * (phoneResolution['height']))
    device.shell (f"input tap {xNextButton} {yNextButton}") # Next Button == Play PVP Button
    time.sleep (3)
    
    print(f"Line 210 - btnPVPFreePlay Tap")
    xPVPFreePlay = int ((coords['btnPVPFreePlay']['x']) * (phoneResolution['width']))
    yPVPFreePlay = int ((coords['btnPVPFreePlay']['y']) * (phoneResolution['height']))
    device.shell (f"input tap {xPVPFreePlay} {yPVPFreePlay}") # Free Play Button
    time.sleep (3)
    
    print(f"Line 216 - btnPlayPVPMatch")
    device.shell (f"input tap {xNextButton} {yNextButton}") # Next Button == Play PVP Button
    time.sleep (3) #0.5
    
    print(f"Added Button at Line 138 - btnPVPFreePlay Tap")
    xPVPFreePlay = int ((coords['btnPVPFreePlay']['x']) * (phoneResolution['width']))
    yPVPFreePlay = int ((coords['btnPVPFreePlay']['y']) * (phoneResolution['height']))
    device.shell (f"input tap {xPVPFreePlay} {yPVPFreePlay}") # Free Play Button
    time.sleep (3)
    
    print(f"Line 220 - btnOpenPVPCrate")
    xPVPCrate = int ((coords['btnOpenPVPCrate']['x']) * (phoneResolution['width']))
    yPVPCrate = int ((coords['btnOpenPVPCrate']['y']) * (phoneResolution['height']))
    device.shell (f"input tap {xPVPCrate} {yPVPCrate}") # Claim PVP Crate Button for Winning 5 Matches
    time.sleep (3)
    
    matchTime = 0
    while (matchTime <= 4): # 3
        print(f"Line 228.{matchTime} - btnPVPFreePlay")
        device.shell (f"input tap {xPVPFreePlay} {yPVPFreePlay}") # Claim Crate Rewards or Open Free Play 
        time.sleep (1)# 0.2
        matchTime += 1 # 0.2
        
    print(f"Line 233 - btnPVPFreePlay")
    device.shell (f"input tap {xPVPFreePlay} {yPVPFreePlay}") # Free Play Button
    print("")