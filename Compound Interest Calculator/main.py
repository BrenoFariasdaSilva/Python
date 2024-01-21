import atexit # For playing a sound when the program finishes
import os # For running a command in the terminal
import matplotlib.pyplot as plt # For plotting graphs
import platform # For getting the operating system name
from colorama import Style # For coloring the terminal

# Macros:
class BackgroundColors: # Colors for the terminal
   CYAN = "\033[96m" # Cyan
   GREEN = "\033[92m" # Green
   YELLOW = "\033[93m" # Yellow
   RED = "\033[91m" # Red
   BOLD = "\033[1m" # Bold
   UNDERLINE = "\033[4m" # Underline
   CLEAR_TERMINAL = "\033[H\033[J" # Clear the terminal

# Sound Constants:
SOUND_COMMANDS = {"Darwin": "afplay", "Linux": "aplay", "Windows": "start"}
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav" # The path to the sound file

# Input Constants:
PERIOD_TYPES = ["Years", "Months", "Days"] # The types of the period
STR_PERIOD_TYPES = str(tuple(PERIOD_TYPES))[1:-1].replace("'", "") # The types of the period as a string list

# This function defines the command to play a sound when the program finishes
def play_sound():
   if os.path.exists(SOUND_FILE):
      if platform.system() in SOUND_COMMANDS: # If the platform.system() is in the SOUND_COMMANDS dictionary
         os.system(f"{SOUND_COMMANDS[platform.system()]} {SOUND_FILE}")
      else: # If the platform.system() is not in the SOUND_COMMANDS dictionary
         print(f"{BackgroundColors.RED}The {BackgroundColors.CYAN}platform.system(){BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}")
   else: # If the sound file does not exist
      print(f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}")

# Register the function to play a sound when the program finishes
atexit.register(play_sound)

# This function get for the type of the period from the user
def get_period_type():
   period_type = '' # Initialize the period type

   while period_type.capitalize() not in PERIOD_TYPES: # While the period type is not in the list of the period types
      period_type = input(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Please enter the type of the period {BackgroundColors.CYAN}({STR_PERIOD_TYPES}){BackgroundColors.GREEN}: {Style.RESET_ALL}")

   return period_type.capitalize() # Return the period type

# This is the Main function
def main():
   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Compound Interest Calculator {BackgroundColors.GREEN}Algorithm!{Style.RESET_ALL}", end="\n\n") # Output the Welcome message

   period_type = get_period_type() # Get the type of the period from the user

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output the end of the program message

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
	main() # Call the main function
