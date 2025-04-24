import atexit # For playing a sound when the program finishes
import importlib # For importing a module
import os # For running a command in the terminal
import platform # For getting the operating system name
import subprocess # Import subprocess for running commands
import sys # For getting the system path
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

# List of directories to exclude
EXCLUDE_DIRS = {"./.assets", "./venv"} # Directories to exclude

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

def is_package_installed(package_name):
   """
   Checks if the specified package is installed.

   :param package_name: Name of the package to check.
   :return: True if the package is installed, False otherwise.
   """

   try: # Try to import the package
      importlib.import_module(package_name) # Import the package
      return True # Return True if the package is installed
   except ImportError: # If the package is not installed
      return False # Return False if the package is not installed

def install_package_with_pipx(package_name):
   """
   Installs a package using pipx.

   :param package_name: Name of the package to install.
   :return: None
   """

   try: # Try to install the package using pipx
      subprocess.check_call([sys.executable, "-m", "pipx", "install", package_name]) # Install the package using pipx
      print(f"{BackgroundColors.GREEN}{package_name} installed successfully using pipx!{Style.RESET_ALL}") # Output the success message
   except subprocess.CalledProcessError: # If the process fails
      print(f"{BackgroundColors.RED}Failed to install {package_name} using pipx.{Style.RESET_ALL}") # Output the failure message

def install_package_with_pip(package_name):
   """
   Installs a package using pip.

   :param package_name: Name of the package to install.
   :return: None
   """

   try: # Try to install the package using pip
      subprocess.check_call([sys.executable, "-m", "pip", "install", package_name]) # Install the package using pip
      print(f"{BackgroundColors.GREEN}{package_name} installed successfully using pip!{Style.RESET_ALL}") # Output the success message
   except subprocess.CalledProcessError: # If the process fails
      print(f"{BackgroundColors.RED}Failed to install {package_name} using pip.{Style.RESET_ALL}") # Output the failure message

def check_and_install_package(package_name="subliminal"):
   """
   Checks if the specified package is installed and installs it if not.

   :param package_name: Name of the package to check and install.
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Checking if the package {BackgroundColors.CYAN}{package_name}{BackgroundColors.GREEN} is installed...{Style.RESET_ALL}") # Output the verbose message

   if is_package_installed(package_name): # Check if the package is installed
      verbose_output(f"{BackgroundColors.CYAN}{package_name}{BackgroundColors.GREEN} is already installed.{Style.RESET_ALL}") # Output the verbose message
   else:
      verbose_output(f"{BackgroundColors.CYAN}{package_name}{BackgroundColors.YELLOW} is not installed. Installing...{Style.RESET_ALL}")
      install_package_with_pipx(package_name) # Try installing with pipx
      if not is_package_installed(package_name): # If the package is not installed
         install_package_with_pip(package_name) # Fallback to pip if pipx fails

def get_directories():
   """
   Get all directories inside the input directory, excluding the specified ones.

   :return: List of directories
   """

   return [os.path.join(INPUT_DIRECTORY, d) for d in os.listdir(INPUT_DIRECTORY) if os.path.isdir(os.path.join(INPUT_DIRECTORY, d))] # Return a list of directories inside INPUT_DIRECTORY

def download_subtitles(directory):
   """
   Download subtitles for the specified directory in multiple languages.

   :param directory: The directory to download subtitles for
   :return: None
   """

   languages = ["pt-BR", "eng"] # Add any additional language codes here

   for lang in languages: # Loop through the languages
      print(f"{BackgroundColors.GREEN}Downloading subtitles in {BackgroundColors.YELLOW}{lang}{BackgroundColors.GREEN} for {BackgroundColors.CYAN}{directory}{BackgroundColors.GREEN}...{Style.RESET_ALL}")
      
      command = f'subliminal download -l {lang} -m 50 "{directory}"' # The command to download subtitles using subliminal
      
      try: # Try to run the command in the terminal
         subprocess.run(command, shell=True, check=True) # Run the command in the terminal
      except subprocess.CalledProcessError: # If the process fails
         print(f"{BackgroundColors.RED}Failed to download subtitles for {directory}{Style.RESET_ALL}")

def process_directories(dirs):
   """
   Process directories to download subtitles.

   :param dirs: List of directories to process
   :return: None
   """

   for directory in tqdm(dirs, desc=f"{BackgroundColors.GREEN}Processing directories to download subtitles{Style.RESET_ALL}", unit="dir"): # Loop through directories with a progress bar
      download_subtitles(directory) # Download subtitles for the directory

   print(f"{BackgroundColors.GREEN}All subtitles downloaded successfully!{Style.RESET_ALL}") # Output the success message

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

def main():
   """
   Main function.

   :return: None
   """

   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Subtitles Downloader{BackgroundColors.GREEN}!{Style.RESET_ALL}", end="\n\n") # Output the Welcome message

   check_and_install_package() # Check and install the subliminal package

   os.makedirs(INPUT_DIRECTORY, exist_ok=True) # Create the input directory if it does

   dirs = get_directories() # Get all directories in the current directory, excluding the specified ones

   if len(dirs) == 0: # If no directories are found
      print(f"{BackgroundColors.RED}No directories found in the {BackgroundColors.CYAN}Input{BackgroundColors.RED} directory. Please add directories to download subtitles.{Style.RESET_ALL}")
      return # Return if no directories are found

   process_directories(dirs) # Process directories to download subtitles

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output the end of the program message

   atexit.register(play_sound) # Register the function to play a sound when the program finishes

if __name__ == "__main__":
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """

   main() # Call the main function
