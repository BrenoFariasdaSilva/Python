import atexit # For playing a sound when the program finishes
import ffmpeg # For decoding audio files
import os # For running a command in the terminal
import platform # For getting the operating system name
from colorama import Style # For coloring the terminal
from mutagen import File # For reading audio file metadata
from tqdm import tqdm # For creating a progress bar

# Macros:
class BackgroundColors: # Colors for the terminal
   CYAN = "\033[96m" # Cyan
   GREEN = "\033[92m" # Green
   YELLOW = "\033[93m" # Yellow
   RED = "\033[91m" # Red
   BOLD = "\033[1m" # Bold
   UNDERLINE = "\033[4m" # Underline
   CLEAR_TERMINAL = "\033[H\033[J" # Clear the terminal

# Execution Constants:
VERBOSE = False # Set to True to output verbose messages

# Sound Constants:
SOUND_COMMANDS = {"Darwin": "afplay", "Linux": "aplay", "Windows": "start"} # The commands to play a sound for each operating system
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav" # The path to the sound file

def verbose_output(true_string="", false_string=""):
   """
   Outputs a message if the VERBOSE constant is set to True.

   :param true_string: The string to be outputted if the VERBOSE constant is set to True.
   :param false_string: The string to be outputted if the VERBOSE constant is set to False.
   :return: None
   """

   if VERBOSE and true_string != "": # If the VERBOSE constant is set to True and the true_string is set
      print(true_string) # Output the true statement string
   elif false_string != "": # If the false_string is set
      print(false_string) # Output the false statement string

def verify_filepath_exists(filepath):
   """
   Verify if a file or folder exists at the specified path.

   :param filepath: Path to the file or folder
   :return: True if the file or folder exists, False otherwise
   """

   verbose_output(f"{BackgroundColors.YELLOW}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}") # Output the verbose message

   return os.path.exists(filepath) # Return True if the file or folder exists, False otherwise

def play_sound():
   """
   Plays a sound when the program finishes.

   :return: None
   """

   if verify_filepath_exists(SOUND_FILE): # If the sound file exists
      if platform.system() in SOUND_COMMANDS: # If the platform.system() is in the SOUND_COMMANDS dictionary
         os.system(f"{SOUND_COMMANDS[platform.system()]} {SOUND_FILE}") # Play the sound
      else: # If the platform.system() is not in the SOUND_COMMANDS dictionary
         print(f"{BackgroundColors.RED}The {BackgroundColors.CYAN}platform.system(){BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}")
   else: # If the sound file does not exist
      print(f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}")

def find_audio_files(directory):
   """
   Recursively find all audio files (any format supported by Mutagen) in the given directory.
   
   :param directory: The directory to search for audio files.
   :return: A list of audio files found in the directory.
   """

   verbose_output(f"{BackgroundColors.YELLOW}Finding audio files in the directory: {BackgroundColors.CYAN}{directory}{Style.RESET_ALL}") # Output the verbose message

   audio_files = [] # Initialize an empty list to store audio files

   for root, _, files in os.walk(directory): # Recursively walk through the directory
      for file in files: # Iterate over the files in the current directory
         if file.lower().endswith((".mp3", ".flac", ".ogg", ".aac", ".wav", ".m4a", ".wma")): # Check if the file is an audio file
            audio_files.append(os.path.join(root, file)) # Add the audio file to the list

   return audio_files # Return the list of audio files

def main():
   """
   Main function.

   :return: None
   """

   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Corrupted Audio Files Checker{BackgroundColors.GREEN}!{Style.RESET_ALL}", end="\n\n") # Output the Welcome message

   directory = os.getcwd() # Get the current working directory
   audio_files = find_audio_files(directory) # Find all audio files in the current directory

   if not audio_files: # If no audio files are found
      print(f"{BackgroundColors.RED}No audio files found in the directory: {BackgroundColors.CYAN}{directory}{Style.RESET_ALL}")
      return # Exit the program
   
   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output the end of the program message

   atexit.register(play_sound) # Register the function to play a sound when the program finishes

if __name__ == "__main__":
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """

   main() # Call the main function
