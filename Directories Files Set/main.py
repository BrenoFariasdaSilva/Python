import atexit # For playing a sound when the program finishes
import os # For running a command in the terminal
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

# This function gets the common files, files only in the first directory, and files only in the second directory
def get_common_files(first_dir, second_dir):
   files_dir1 = set(os.listdir(first_dir)) # Get the files in the first directory
   files_dir2 = set(os.listdir(second_dir)) # Get the files in the second directory

   common_files = files_dir1.intersection(files_dir2) # Get the common files
   files_only_in_dir1 = files_dir1 - files_dir2 # Get the files only in the first directory
   files_only_in_dir2 = files_dir2 - files_dir1 # Get the files only in the second directory

   # Return the common files, files only in the first directory, and files only in the second directory
   return common_files, files_only_in_dir1, files_only_in_dir2

# This function formats the files by sorting them alphabetically
def format_files(file_set):
   return sorted(file_set, key=lambda x: x.lower())

# This is the Main function
def main():
   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Directories Files Set{BackgroundColors.GREEN} program!{Style.RESET_ALL}") # Output the welcome message

   first_dir = f"."
   second_dir = f"."

   common_files, files_only_in_dir1, files_only_in_dir2 = get_common_files(first_dir, second_dir) # Get the common files, files only in the first directory, and files only in the second directory

   print(f"{BackgroundColors.GREEN}Common Files: {BackgroundColors.CYAN}{len(common_files)}{Style.RESET_ALL}", end="\n")
   print(f"{BackgroundColors.CYAN}" + "\n".join([f"{i+1:02d} - {file}" for i, file in enumerate(format_files(common_files))]) + f"{Style.RESET_ALL}\n")

   print(f"{BackgroundColors.GREEN}Files Only in the First Directory: {BackgroundColors.CYAN}{len(files_only_in_dir1)}{Style.RESET_ALL}", end="\n")
   print(f"{BackgroundColors.CYAN}" + "\n".join([f"{i+1:02d} - {file}" for i, file in enumerate(format_files(files_only_in_dir1))]) + f"{Style.RESET_ALL}\n")

   print(f"{BackgroundColors.GREEN}Files Only in the Second Directory: {BackgroundColors.CYAN}{len(files_only_in_dir2)}{Style.RESET_ALL}", end="\n")
   print(f"{BackgroundColors.CYAN}" + "\n".join([f"{i+1:02d} - {file}" for i, file in enumerate(format_files(files_only_in_dir2))]) + f"{Style.RESET_ALL}\n")

   print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output the end of the program message

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
	main() # Call the main function
