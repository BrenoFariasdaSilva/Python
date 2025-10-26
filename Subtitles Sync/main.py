import atexit # For playing a sound when the program finishes
import glob # For getting files in a directory
import os # For running a command in the terminal
import platform # For getting the operating system name
import shutil # For checking if a command exists
import subprocess # For running terminal commands
import sys # For running terminal commands
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
VIDEO_EXTENSIONS = [".mkv", ".mp4", ".avi"] # List of video file extensions to process

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

def install_chocolatey():
   """
   Installs Chocolatey on Windows if it is not already installed.

   :param none
   :return: None
   """

   if shutil.which("choco") is not None: # Chocolatey already installed
      verbose_output(f"{BackgroundColors.GREEN}Chocolatey is already installed.{Style.RESET_ALL}")
      return

   print(f"{BackgroundColors.GREEN}Installing {BackgroundColors.CYAN}Chocolatey{BackgroundColors.GREEN} via {BackgroundColors.CYAN}PowerShell{BackgroundColors.GREEN}...{Style.RESET_ALL}")

   command = ( # PowerShell command to install Chocolatey
      'powershell -NoProfile -InputFormat None -ExecutionPolicy Bypass -Command '
      '"Set-ExecutionPolicy Bypass -Scope Process -Force; '
      '[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; '
      'iex ((New-Object System.Net.WebClient).DownloadString(\'https://community.chocolatey.org/install.ps1\'))"'
   )

   os.system(command) # Run the command to install Chocolatey

def install_ffmpeg():
   """
   Installs ffmpeg according to the OS.

   :param none
   :return: None
   """

   current_os = platform.system() # Get the current operating system

   verbose_output(f"{BackgroundColors.GREEN}Installing ffmpeg in the current operating system: {BackgroundColors.CYAN}{current_os}{Style.RESET_ALL}") # Output the verbose message

   if shutil.which("ffmpeg") is not None: # If ffmpeg is already installed
      verbose_output(f"{BackgroundColors.GREEN}ffmpeg is already installed.{Style.RESET_ALL}")
      return

   if current_os == "Darwin": # MacOS
      print(f"{BackgroundColors.GREEN}Installing {BackgroundColors.CYAN}ffmpeg{BackgroundColors.GREEN} via {BackgroundColors.CYAN}Homebrew{BackgroundColors.GREEN}...{Style.RESET_ALL}")
      os.system("brew install ffmpeg")
   elif current_os == "Linux": # Linux
      print(f"{BackgroundColors.GREEN}Installing {BackgroundColors.CYAN}ffmpeg{BackgroundColors.GREEN} via {BackgroundColors.CYAN}apt{BackgroundColors.GREEN}...{Style.RESET_ALL}")
      os.system("sudo apt update && sudo apt install -y ffmpeg")
   elif current_os == "Windows": # Windows via Chocolatey
      if shutil.which("choco") is None: # If Chocolatey is not installed
         install_chocolatey() # Install Chocolatey first
      print(f"{BackgroundColors.GREEN}Installing {BackgroundColors.CYAN}ffmpeg{BackgroundColors.GREEN} via {BackgroundColors.CYAN}Chocolatey{BackgroundColors.GREEN}...{Style.RESET_ALL}")
      os.system("choco install ffmpeg -y") # Install ffmpeg via Chocolatey
   else:
      print(f"{BackgroundColors.RED}Unsupported OS for automatic ffmpeg installation.{Style.RESET_ALL}")

def install_ffsubsync():
   """
   Installs ffsubsync via pip.

   :param none
   :return: None
   """

   current_os = platform.system() # Get the current operating system

   verbose_output(f"{BackgroundColors.GREEN}Installing ffsubsync in the current operating system: {BackgroundColors.CYAN}{current_os}{Style.RESET_ALL}") # Output the verbose message

   print(f"{BackgroundColors.GREEN}Installing ffsubsync via pip...{Style.RESET_ALL}") 
   os.system(f"{sys.executable} -m pip install ffsubsync") # Install ffsubsync via pip

def verify_ffsubsync_installed():
   """
   Verifies if 'ffsubsync' (ffs command) is installed and accessible.
   Automatically installs ffmpeg and ffsubsync if missing.

   :param none
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Verifying if 'ffsubsync' command is installed and accessible...{Style.RESET_ALL}") # Output the verbose message

   if shutil.which("ffsubsync") is None: # If ffsubsync is not installed
      print(f"{BackgroundColors.RED}The 'ffsubsync' command is not installed or not in PATH.{Style.RESET_ALL}")
      install_ffmpeg() # Install ffmpeg first
      install_ffsubsync() # Then install ffsubsync

      if shutil.which("ffsubsync") is None: # If ffsubsync is still not installed
         print(f"{BackgroundColors.RED}Installation failed. 'ffsubsync' is still not accessible. Exiting.{Style.RESET_ALL}")
         sys.exit(1) # Exit the program with an error code

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

   :param none
   :return: List of directories in absolute paths
   """

   input_dir_abs = os.path.abspath(INPUT_DIRECTORY) # Ensure input directory is absolute and normalized

   return [os.path.normpath(os.path.join(input_dir_abs, d)) for d in os.listdir(input_dir_abs) if os.path.isdir(os.path.join(input_dir_abs, d))] # Return a list of directories inside INPUT_DIRECTORY

def get_video_files(directory):
   """
   Returns a list of video files (as defined in VIDEO_EXTENSIONS) in a directory, excluding specified files.

   :param directory: The directory to search for video files.
   :return: List of video files
   """

   directory_abs = os.path.abspath(directory) # Get the absolute path of the directory
   verbose_output(f"{BackgroundColors.GREEN}Getting all video files ({', '.join(VIDEO_EXTENSIONS)}) in the directory: {BackgroundColors.CYAN}{directory_abs}{Style.RESET_ALL}") # Output the verbose message

   files = [] # List to store video files
   for ext in VIDEO_EXTENSIONS: # Collect files for each configured extension
      pattern = os.path.join(directory_abs, f"*{ext}") # Pattern to match files with the current extension
      files.extend([os.path.normpath(f) for f in glob.glob(pattern)]) # Add matched files to the list


   exclude_abs = {os.path.normpath(os.path.abspath(f)) for f in EXCLUDE_FILES} # Set of absolute paths to exclude

   seen = set() # Set to track seen files to remove duplicates
   result = [] # List to store the final video files
   for f in files: # For each file found
      if f in seen: # If the file has already been seen
         continue
      seen.add(f) # Mark the file as seen
      if f not in exclude_abs: # If the file is not in the exclude list
         result.append(f) # Add the file to the result list

   return result # Return a list of video files in the directory

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
   Runs the ffsubsync command to synchronize the subtitle.
   
   :param mkv_file: The .mkv file to synchronize the subtitle with
   :param srt_file: The subtitle file to synchronize
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Synchronizing the subtitle file: {BackgroundColors.CYAN}{srt_file}{BackgroundColors.GREEN} with the .mkv file: {BackgroundColors.CYAN}{mkv_file}{Style.RESET_ALL}") # Output the verbose message
   
   synced_srt_file = srt_file.replace(".srt", "-synced.srt") # Create a new synced subtitle file name
   command = f'ffsubsync "{mkv_file}" -i "{srt_file}" -o "{synced_srt_file}"' # Create the command to synchronize the subtitle
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

   directory_abs = os.path.normpath(os.path.abspath(directory)) # Ensure we operate using absolute, normalized directory paths and print the absolute directory

   video_files = get_video_files(directory_abs) # Get all video files in the directory
   for video_file in tqdm(video_files, desc=f"{BackgroundColors.GREEN}Processing video files in {BackgroundColors.CYAN}{os.path.basename(directory_abs)}", unit="file"): # For each video file in the directory
      base_name = os.path.splitext(os.path.basename(video_file))[0] # Use basename
      srt_file = get_srt_file(os.path.join(directory_abs, base_name)) # Get the appropriate subtitle file
      if srt_file: # If a subtitle file is found
         sync_subtitle(video_file, srt_file) # Synchronize the subtitle
   
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

   verify_ffsubsync_installed() # Verify if ffsubsync is installed

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
