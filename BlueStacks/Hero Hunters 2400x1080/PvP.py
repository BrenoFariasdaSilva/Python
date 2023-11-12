from itertools import count
import ppadb
import time
from datetime import datetime
from ppadb.client import Client
import os
import re

# Smartphone Resources:
# Time: 18:40h
# Battery: 45%
# Lives: 240
# Total Played Matches: 0

# Game Resources
# PvP Coins: 8600
# Heronium: 750
# Gold: 2806
# Money: 845.000

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
        'x' : 0.887037037,
        'y' : 0.92962963
    },
    'btnPVPFreePlay' : {
        'x' : 0.29, # Modifiquei mais para a direita para evitar de abrir o piggy bank
        'y' : 0.511111111
    },
    'btnOpenPVPCrate' : {
        'x' : 0.52625,
        'y' : 0.87962963
    },
    'btnReadyPvPCoop' : {
        'x' : 0.520833333,
        'y' : 0.87962963
    },
    'btnPlayAgainPvPCoop' : {
        'x' : 0.158333333,
        'y' : 0.925925926
    },
}

i = 1
now = datetime.now()
current_time = now.strftime("%H:%M:%S")

matchDuration = 200 
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
 
while (True): # ((now.hour <= nextResetHour) and (now.minute <= nextResetMinute)): 
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    print("Start of {} PvP Loop - {}".format(i, current_time))
    
    print("Unselecting Heroes")
    xStartUnselectHeroes = int ((coords['btnHeroUnselect']['xStart']) * (phoneResolution['width']))
    xEndUnselectHeroes = int ((coords['btnHeroUnselect']['xEnd']) * (phoneResolution['width']))
    xDeltaUnselectHeroes = int ((coords['btnHeroUnselect']['xDelta']) * (phoneResolution['width']))
    yValueUnselectHeroes = int ((coords['btnHeroUnselect']['y']) * (phoneResolution['height']))
    
    for unselectHeroXCoordinate in range (xStartUnselectHeroes, xEndUnselectHeroes, xDeltaUnselectHeroes) : # Unselect Heroes
        device.shell (f"input touchscreen swipe {unselectHeroXCoordinate} {yValueUnselectHeroes} {unselectHeroXCoordinate} {yValueUnselectHeroes} 100") # Hero Unselect
        
    print("Swipe to Start") 
    xStartSwipeToStart = int ((coords['btnSwipeToPreviousPage']['xStart']) * (phoneResolution['width']))
    xEndSwipeToStart = int ((coords['btnSwipeToPreviousPage']['xEnd']) * (phoneResolution['width']))
    yValueSwipeToStart = int ((coords['btnSwipeToPreviousPage']['y']) * (phoneResolution['height']))
    swipeToStartDuration = 100 # time in milliseconds
    
    for pagesSwipeCounter in range (0, amountOfHeroesPages - 2): # Swipe all back to left
        device.shell (f"input touchscreen swipe {xStartSwipeToStart} {yValueSwipeToStart} {xEndSwipeToStart} {yValueSwipeToStart} {swipeToStartDuration}")
    time.sleep (1.0) 
      
    print("Selecting Heroes")
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    print("Start of Heroes Select - {}".format(current_time))
    xStartHeroSelect = int ((coords['btnHeroSelect']['xStart']) * (phoneResolution['width']))
    xEndHeroSelect = int ((coords['btnHeroSelect']['xEnd']) * (phoneResolution['width']))
    xDeltaHeroSelect = int ((coords['btnHeroSelect']['xDelta']) * (phoneResolution['width']))
    yStartHeroSelect = int ((coords['btnHeroSelect']['yStart']) * (phoneResolution['height']))	
    yEndHeroSelect = int ((coords['btnHeroSelect']['yEnd']) * (phoneResolution['height']))
    yDeltaHeroSelect = int ((coords['btnHeroSelect']['yDelta']) * (phoneResolution['height']))
    
    for pagesSwipeCounter in range (0, amountOfHeroesPages) : 
        for columnCoordinates in range (xStartHeroSelect, xEndHeroSelect, xDeltaHeroSelect) : # Change column
            for lineCoordinates in range (yStartHeroSelect, yEndHeroSelect, yDeltaHeroSelect) : # Change line
                device.shell (f"input touchscreen swipe {columnCoordinates} {lineCoordinates} {columnCoordinates} {lineCoordinates} 100") # Hero Select
                time.sleep (0.1) # default: 0.3
                xAvoidAction = int ((coords['btnAvoidAction']['x']) * (phoneResolution['width']))
                yAvoidAction = int ((coords['btnAvoidAction']['y']) * (phoneResolution['height']))
                device.shell (f"input touchscreen swipe {xAvoidAction} {yAvoidAction} {xAvoidAction} {yAvoidAction} 100") # Avoid "Revive Hero Lives"
        
        xStartSwipeToNextPage = int ((coords['btnSwipeToNextPage']['xStart']) * (phoneResolution['width'])	)
        xEndSwipeToNextPage = int ((coords['btnSwipeToNextPage']['xEnd']) * (phoneResolution['width']))
        yValueSwipeToNextPage = int ((coords['btnSwipeToNextPage']['y']) * (phoneResolution['height']))
        swipeToNextPageDuration = 1700 # time in milliseconds
        device.shell (f"input touchscreen swipe {xStartSwipeToNextPage} {yValueSwipeToNextPage} {xEndSwipeToNextPage} {yValueSwipeToNextPage} {swipeToNextPageDuration}") # Swipe to next heroes page
        time.sleep (1.5)
      
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    print("End of Heroes Select - {}".format(current_time))
    xStartPVPMatchButton = int ((coords['btnPlayPVPMatch']['x']) * (phoneResolution['width']))
    yStartPVPMatchButton = int ((coords['btnPlayPVPMatch']['y']) * (phoneResolution['height']))
    device.shell (f"input touchscreen swipe {xStartPVPMatchButton} {yStartPVPMatchButton} {xStartPVPMatchButton} {yStartPVPMatchButton} 500") #  PVP Match - Play Button
    
    xAvoidAction = int ((coords['btnAvoidAction']['x']) * (phoneResolution['width']))
    yAvoidAction = int ((coords['btnAvoidAction']['y']) * (phoneResolution['height']))
    device.shell (f"input touchscreen swipe {xAvoidAction} {yAvoidAction} {xAvoidAction} {yAvoidAction} 500") # Avoid "Go Anyway"
        
    matchTime = 0
    now = datetime.now()
    current_time = now.strftime("%H:%M:%S")
    print("Start of Match - {}".format(current_time))
    while matchTime < matchDuration:
        time.sleep (60)
        matchTime += 60
        device.shell (f"input touchscreen swipe {xAvoidAction} {yAvoidAction} {xAvoidAction} {yAvoidAction} 500") # Avoid "Screen Lock" for inactivity
        now = datetime.now()
        current_time = now.strftime("%H:%M:%S")
        print("   {} seconds passed - {}".format(matchTime, current_time))
       
    print("End of Match - {}".format(current_time))
    
    print(f"Line 204 - btnPlayPVPMatch")
    xNextButton = int ((coords['btnPlayPVPMatch']['x']) * (phoneResolution['width']))
    yNextButton = int ((coords['btnPlayPVPMatch']['y']) * (phoneResolution['height']))
    device.shell (f"input touchscreen swipe {xNextButton} {yNextButton} {xNextButton} {yNextButton} 500") # Next Button == Play PVP Button
    time.sleep (1) # 1
    
    print(f"Line 210 - btnPVPFreePlay Tap")
    xPVPFreePlay = int ((coords['btnPVPFreePlay']['x']) * (phoneResolution['width']))
    yPVPFreePlay = int ((coords['btnPVPFreePlay']['y']) * (phoneResolution['height']))
    device.shell (f"input touchscreen swipe {xPVPFreePlay} {yPVPFreePlay} {xPVPFreePlay} {yPVPFreePlay} 500") # Free Play Button
    time.sleep (1) # 1
    
    print(f"Line 216 - btnPlayPVPMatch")
    device.shell (f"input touchscreen swipe {xNextButton} {yNextButton} {xNextButton} {yNextButton} 500") # Next Button == Play PVP Button
    time.sleep (1) #0.5
    
    print(f"Added Button at Line 220 - btnPVPFreePlay Tap")
    device.shell (f"input touchscreen swipe {xPVPFreePlay} {yPVPFreePlay} {xPVPFreePlay} {yPVPFreePlay} 500") # Free Play Button
    time.sleep (1) # 1
    
    print(f"Line 220 - btnOpenPVPCrate")
    xPVPCrate = int ((coords['btnOpenPVPCrate']['x']) * (phoneResolution['width']))
    yPVPCrate = int ((coords['btnOpenPVPCrate']['y']) * (phoneResolution['height']))
    device.shell (f"input touchscreen swipe {xPVPCrate} {yPVPCrate} {xPVPCrate} {yPVPCrate} 500") # Claim PVP Crate Button for Winning 5 Matches
    time.sleep (1) # 1
    
    print(f"Line 232 - btnPVPFreePlay")
    device.shell (f"input touchscreen swipe {xPVPFreePlay} {yPVPFreePlay} {xPVPFreePlay} {yPVPFreePlay} 500") # Free Play Button
    
    matchTime = 0
    while (matchTime <= 2): # 4
        print(f"Line 241 - btnPVPFreePlay")
        device.shell (f"input touchscreen swipe {xPVPFreePlay} {yPVPFreePlay} {xPVPFreePlay} {yPVPFreePlay} 500") # Claim PVP Rewards Crate by tapping on Free Play 
        time.sleep (0.4)# 0.2
        matchTime += 0.5 # 0.2
        
    time.sleep (2) #
    print(f"Line 236 - btnPVPFreePlay")
    device.shell (f"input touchscreen swipe {xPVPFreePlay} {yPVPFreePlay} {xPVPFreePlay} {yPVPFreePlay} 500") # Free Play Button
    
    ## Add Route: 2 Taps on Back Button, 2 Taps on Missions, PVP, Free Play
    # remainingHeroes -= 5
    i+= 1