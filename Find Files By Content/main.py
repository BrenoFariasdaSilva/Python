import atexit # For playing a sound when the program finishes
import os # For walking through the directory
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
SOUND_FILE = "./.assets/NotificationSound.wav" # The path to the sound file

# Constants:
NON_INCLUDED_STRING = "# This is the standard boilerplate that calls the main() function"
INCLUDED_STRING = "def main():"
FILE_FORMATS = [".py"] # The file formats to search for

# Functions:

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

# This function searches for the specified strings in the files in the specified directory
def search_strings_in_files(directory, non_included_string, included_string):
   filenames = [] # Create an empty list for the filenames

   # Walk through the directory
   for root, dirs, files in os.walk(directory):
      for file in files: # For each file in the directory
         # If the file ends with one of the file formats
         if file.endswith(tuple(FILE_FORMATS)):
               file_path = os.path.join(root, file) # Get the file path

               with open(file_path, 'r') as f: # Open the file
                  content = f.read() # Read the file
                  if non_included_string not in content and included_string in content:
                     filenames.append(file_path)

   return filenames # Return the filenames

# This is the Main function
def main():
   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Find Files By Content{BackgroundColors.GREEN} program!{Style.RESET_ALL}")

   current_directory = os.getcwd() # Get the current directory

   # Call the search_strings_in_files function
   filenames = search_strings_in_files(current_directory, NON_INCLUDED_STRING, INCLUDED_STRING)
   number_of_files = len(filenames) # Get the number of files

   if number_of_files > 0: # If there are files that contain the specified strings
      print(f"{BackgroundColors.GREEN}Found the following {BackgroundColors.BOLD}{BackgroundColors.CYAN}{number_of_files}{Style.RESET_ALL}{BackgroundColors.GREEN} files: {Style.RESET_ALL}")
      for filename in filenames: # For each filename
         print(f"{BackgroundColors.BOLD}{BackgroundColors.CYAN}{filename}{Style.RESET_ALL}")
   else: # If there are no files that contain the specified strings
      print(f"{BackgroundColors.GREEN}No files were found according to the specified strings.{Style.RESET_ALL}")

   print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Execution Complete!{Style.RESET_ALL}")

# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
	main() # Call the main function
