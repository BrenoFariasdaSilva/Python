import atexit # For playing a sound when the program finishes
import glob # For getting files in a directory
import os # For running a command in the terminal
import platform # For getting the operating system name
import subprocess # For running terminal commands
from colorama import Style # For coloring the terminal
from tqdm import tqdm # Import tqdm for progress bar

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

# List of directories and files to exclude
EXCLUDE_DIRS = {"..assets", ".venv"} # Directories to exclude
EXCLUDE_FILES = {"./main.py", "./Makefile", "./requirements.txt"} # Files to exclude

# Input Direectory:
INPUT_DIRECTORY = "./Input" # The input directory

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

   verbose_output(f"{BackgroundColors.GREEN}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}") # Output the verbose message

   return os.path.exists(filepath) # Return True if the file or folder exists, False otherwise

def get_directories():
   """
   Get all directories inside the input directory, excluding the specified ones.

   :return: List of directories
   """

   return [os.path.join(INPUT_DIRECTORY, d) for d in os.listdir(INPUT_DIRECTORY) if os.path.isdir(os.path.join(INPUT_DIRECTORY, d))] # Return a list of directories inside INPUT_DIRECTORY

def get_mkv_files(directory):
   """
   Returns a list of .mkv files in a directory, excluding specified files.

   :param directory: The directory to search for .mkv files.
   :return: List of .mkv files
   """

   verbose_output(f"{BackgroundColors.GREEN}Getting all .mkv files in the directory: {BackgroundColors.CYAN}{directory}{Style.RESET_ALL}") # Output the verbose message

   return [f for f in glob.glob(os.path.join(directory, "*.mkv")) if f not in EXCLUDE_FILES] # Return a list of .mkv files in the directory

def get_srt_file(base_name):
   """
   Returns the appropriate subtitle file name if it exists.
   
   :param base_name: The base name of the .mkv file
   :return: The subtitle file name if it exists, None otherwise
   """

   verbose_output(f"{BackgroundColors.GREEN}Getting the appropriate subtitle file for the base name: {BackgroundColors.CYAN}{base_name}{Style.RESET_ALL}") # Output the verbose message
   
   srt_options = [f"{base_name}.srt", f"{base_name}.pt-BR.srt"] # List of possible subtitle files

   return next((srt for srt in srt_options if os.path.exists(srt)), None) # Return the first existing subtitle file

def sync_subtitle(mkv_file, srt_file):
   """
   Runs the ffs command to synchronize the subtitle.
   
   :param mkv_file: The .mkv file to synchronize the subtitle with
   :param srt_file: The subtitle file to synchronize
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Synchronizing the subtitle file: {BackgroundColors.CYAN}{srt_file}{BackgroundColors.GREEN} with the .mkv file: {BackgroundColors.CYAN}{mkv_file}{Style.RESET_ALL}") # Output the verbose message
   
   synced_srt_file = srt_file.replace(".srt", "-synced.srt") # Create a new synced subtitle file name
   command = f'ffs "{mkv_file}" -i "{srt_file}" -o "{synced_srt_file}"' # Create the command to synchronize the subtitle
   subprocess.run(command, shell=True) # Run the command

def cleanup_subtitles(directory):
   """
   Deletes non-synced subtitles and renames synced ones.
   
   :param directory: The directory to cleanup the subtitles
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Cleaning up the subtitles in the directory: {BackgroundColors.CYAN}{directory}{Style.RESET_ALL}") # Output the verbose message

   for srt_file in glob.glob(os.path.join(directory, "*.srt")): # For each .srt file in the directory
      if "synced" not in srt_file: # If the file is not synced
         os.remove(srt_file) # Remove the file
   
   for srt_file in glob.glob(os.path.join(directory, "*.srt")): # For each .srt file in the directory
      if "synced" in srt_file: # If the file is synced
         new_name = srt_file.replace("-synced", "") # Remove the "-synced" part from the file name
         os.rename(srt_file, new_name) # Rename the file

def process_directory(directory):
   """
   Processes a single directory, handling subtitle synchronization.
   
   :param directory: The directory to process
   :return: None
   """
   
   print(f"{BackgroundColors.GREEN}Processing the directory: {BackgroundColors.CYAN}{directory}{Style.RESET_ALL}") # Output the verbose message

   os.chdir(directory) # Change to the directory
   
   mkv_files = get_mkv_files(directory) # Get all .mkv files in the directory

   for mkv_file in mkv_files: # For each .mkv file
      base_name = os.path.splitext(mkv_file)[0] # Get the base name of the file
      srt_file = get_srt_file(base_name) # Get the appropriate subtitle file
      
      if srt_file: # If the subtitle file exists
         sync_subtitle(mkv_file, srt_file) # Synchronize the subtitle
   
   cleanup_subtitles(directory) # Cleanup the subtitles
   os.chdir("..") # Change back to the parent directory

def process_all_directories(directories):
   """
   Processes all directories in the current path, excluding specified ones.
   
   :param directories: List of directories to process
   :return: None
   """

   for directory in tqdm(directories, desc=f"{BackgroundColors.GREEN}Processing Directories", unit="dir"): # Loop through each directory
      process_directory(directory) # Process the directory

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}All Directories Subtitle Synchronization Completed.{Style.RESET_ALL}") # Output the end of the program message

def play_sound():
   """
   Plays a sound when the program finishes and skips if the operating system is Windows.
   :return: None
   """

   current_os = platform.system() # Get the current operating system
   if current_os == "Windows": # If the current operating system is Windows
      return # Do nothing

   if verify_filepath_exists(SOUND_FILE): # If the sound file exists
      if current_os in SOUND_COMMANDS: # If the platform.system() is in the SOUND_COMMANDS dictionary
         os.system(f"{SOUND_COMMANDS[current_os]} {SOUND_FILE}") # Play the sound
      else: # If the platform.system() is not in the SOUND_COMMANDS dictionary
         print(f"{BackgroundColors.RED}The {BackgroundColors.CYAN}{current_os}{BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}")
   else: # If the sound file does not exist
      print(f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}")

def main():
   """
   Main function.

   :return: None
   """

   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Subtitles Sync{BackgroundColors.GREEN} program!{Style.RESET_ALL}") # Output the welcome message

   os.makedirs(INPUT_DIRECTORY, exist_ok=True) # Create the input directory if it does

   dirs = get_directories() # Get all directories in the current directory, excluding the specified ones

   if not dirs: # If no directories are found
      print(f"{BackgroundColors.RED}No directories found in the {BackgroundColors.CYAN}Input{BackgroundColors.RED} directory. Please add directories to synchronize subtitles.{Style.RESET_ALL}")
      return # Return if no directories are found

   process_all_directories(dirs) # Process all directories

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output the end of the program message

   atexit.register(play_sound) # Register the function to play a sound when the program finishes

if __name__ == "__main__":
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """

   main() # Call the main function
