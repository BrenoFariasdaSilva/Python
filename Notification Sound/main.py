import atexit  # For playing a sound when the program finishes
import os  # For running a command in the terminal
import platform  # For getting the operating system name
from colorama import Style  # For coloring the terminal

# Macros:
class BackgroundColors:  # Colors for the terminal
   CYAN = "\033[96m"  # Cyan
   GREEN = "\033[92m"  # Green
   YELLOW = "\033[93m"  # Yellow
   RED = "\033[91m"  # Red
   BOLD = "\033[1m"  # Bold
   UNDERLINE = "\033[4m"  # Underline
   CLEAR_TERMINAL = "\033[H\033[J"  # Clear the terminal

# Sound Constants:
# The sound commands for each operating system
SOUND_COMMANDS = {"Darwin": "afplay", "Linux": "aplay", "Windows": "start"}
SOUND_FILE = "./.assets/NotificationSound.wav"  # The path to the sound file

# @brief: This function defines the command to play a sound when the program finishes
# @param: None
# @return: None
def play_sound():
   if os.path.exists(SOUND_FILE):
      if platform.system() in SOUND_COMMANDS:  # if the platform.system() is in the SOUND_COMMANDS dictionary
         os.system(f"{SOUND_COMMANDS[platform.system()]} {SOUND_FILE}")
      else:  # if the platform.system() is not in the SOUND_COMMANDS dictionary
         print(f"{BackgroundColors.RED}The {BackgroundColors.CYAN}platform.system(){BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}")
   else:  # if the sound file does not exist
      print(f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}")

# Register the function to play a sound when the program finishes
atexit.register(play_sound)
