from itertools import count
import time
from ppadb.client import Client
import os
import re

adb = Client(host='127.0.0.1', port=5037) # Stops on one of these two lines 
devices = adb.devices()

if len(devices) == 0:
    print("No device found")
    quit()
    
# width = x = 2400 or 2160
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
        'x' : 0.52625,
        'y' : 0.87962963
    },
}