"""
================================================================================
Video Audio Track Switcher
================================================================================
Author      : Breno Farias da Silva
Created     : 2025-10-26
Description :
   This script recursively searches for video files in the specified input directory
   and inverts their default audio track, making the non-default track the default.
   When more than two audio tracks are detected, the script prompts the user to
   manually select which one should become the default.

   Key features include:
      - Recursive search for video files with specified extensions
      - Automatic detection of audio tracks using ffprobe
      - Swapping the default and secondary audio track
      - Manual selection of default track for videos with more than two audio tracks
      - Progress bar visualization for processing
      - Integration with ffmpeg for audio track manipulation

Usage:
   1. Set the INPUT_DIR constant to the folder containing your video files.
   2. Execute the script:
         $ python swap_audio_tracks.py
   3. Select the desired audio track when prompted (if more than two exist).

Outputs:
   - Video files in the same directory with swapped or updated default audio track

TODOs:
   - Add a dry-run mode to preview changes without modifying files
   - Add logging of processed files and errors
   - Support automatic language-based selection (e.g., always set “eng” as default)
   - Optimize for batch operations without manual input

Dependencies:
   - Python >= 3.9
   - colorama
   - tqdm
   - ffmpeg and ffprobe installed and available in PATH

Assumptions & Notes:
   - Each video file has at least one audio track
   - Videos are writable in-place
   - Tested on macOS, Linux, and Windows with ffmpeg/ffprobe available
   - Original file is replaced by the processed file
"""

import atexit # For playing a sound when the program finishes
import json # For parsing JSON output from ffprobe
import os # For running a command in the terminal
import platform # For getting the operating system name
import shutil # For checking if a command exists
import subprocess # For running terminal commands
from colorama import Style # For coloring the terminal
from tqdm import tqdm # For displaying a progress bar

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
INPUT_DIR = "D:\Sem Backup\Download\Silicon Valley" # Root directory to search for videos
VIDEO_FILE_EXTENSIONS = [".mkv", ".mp4", ".avi"] # List of video file extensions to process

# Sound Constants:
SOUND_COMMANDS = {"Darwin": "afplay", "Linux": "aplay", "Windows": "start"} # The commands to play a sound for each operating system
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav" # The path to the sound file

# RUN_FUNCTIONS:
RUN_FUNCTIONS = {
   "Play Sound": True, # Set to True to play a sound when the program finishes
}

# Functions Definitions:

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

def install_ffmpeg_and_ffprobe():
   """
   Installs ffmpeg and ffprobe according to the OS.

   :param none
   :return: None
   """

   current_os = platform.system() # Get the current operating system

   verbose_output(f"{BackgroundColors.GREEN}Installing ffmpeg and ffprobe in the current operating system: {BackgroundColors.CYAN}{current_os}{Style.RESET_ALL}") # Output the verbose message

   if shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None: # If ffmpeg and ffprobe are already installed
      verbose_output(f"{BackgroundColors.GREEN}ffmpeg and ffprobe are already installed.{Style.RESET_ALL}") # Output the verbose message
      return # Exit the function

   if current_os == "Darwin": # MacOS
      print(f"{BackgroundColors.GREEN}Installing {BackgroundColors.CYAN}ffmpeg and ffprobe{BackgroundColors.GREEN} via {BackgroundColors.CYAN}Homebrew{BackgroundColors.GREEN}...{Style.RESET_ALL}")
      os.system("brew install ffmpeg") # Install ffmpeg (includes ffprobe) via Homebrew
   elif current_os == "Linux": # Linux
      print(f"{BackgroundColors.GREEN}Installing {BackgroundColors.CYAN}ffmpeg and ffprobe{BackgroundColors.GREEN} via {BackgroundColors.CYAN}apt{BackgroundColors.GREEN}...{Style.RESET_ALL}")
      os.system("sudo apt update -y && sudo apt install -y ffmpeg") # Install ffmpeg (includes ffprobe) via apt
   elif current_os == "Windows": # Windows via Chocolatey
      if shutil.which("choco") is None: # If Chocolatey is not installed
         install_chocolatey() # Install Chocolatey first
      print(f"{BackgroundColors.GREEN}Installing {BackgroundColors.CYAN}ffmpeg and ffprobe{BackgroundColors.GREEN} via {BackgroundColors.CYAN}Chocolatey{BackgroundColors.GREEN}...{Style.RESET_ALL}")
      subprocess.run(["choco", "install", "ffmpeg", "-y"], check=True) # Install ffmpeg (includes ffprobe) via Chocolatey
   else: # Unsupported OS
      print(f"{BackgroundColors.RED}Unsupported OS for automatic ffmpeg installation.{Style.RESET_ALL}") # Output the error message
      return # Exit the function

   if shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None: # If ffmpeg and ffprobe were successfully installed
      print(f"{BackgroundColors.GREEN}ffmpeg and ffprobe installed successfully.{Style.RESET_ALL}") # Output the success message
   else: # If the installation failed
      print(f"{BackgroundColors.RED}Failed to install ffmpeg and ffprobe. Please install them manually.{Style.RESET_ALL}") # Output the error message

def verify_filepath_exists(filepath):
   """
   Verify if a file or folder exists at the specified path.

   :param filepath: Path to the file or folder
   :return: True if the file or folder exists, False otherwise
   """

   verbose_output(f"{BackgroundColors.GREEN}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}") # Output the verbose message

   return os.path.exists(filepath) # Return True if the file or folder exists, False otherwise

def find_videos(input_dir, extensions):
   """
   Recursively find all videos in the input directory with specified extensions.

   :param input_dir: Root directory
   :param extensions: List of video file extensions
   :return: List of video file paths
   """
   
   verbose_output(f"{BackgroundColors.GREEN}Searching for video files in the directory: {BackgroundColors.CYAN}{input_dir}{Style.RESET_ALL}") # Output the verbose message
   
   videos = [] # List to store video file paths

   for root, dirs, files in os.walk(input_dir): # Walk through the directory
      for file in files: # For each file in the directory
         if any(file.lower().endswith(ext) for ext in extensions): # If the file has a valid video extension
            videos.append(os.path.join(root, file)) # Add the video file path to the list
   
   return videos # Return the list of video file paths

def get_audio_tracks(video_path):
   """
   Retrieve a list of audio tracks in the video using ffprobe.

   :param video_path: Path to the video file
   :return: List of dictionaries containing track index, language, and codec
   """
   
   verbose_output(f"{BackgroundColors.GREEN}Retrieving audio tracks for video: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}") # Output the verbose message
   
   cmd = [
      "ffprobe", # Command to run ffprobe
      "-v", "error", # Suppress unnecessary output
      "-select_streams", "a", # Select audio streams
      "-show_entries", "stream=index:stream_tags=language", # Show stream index and language tags
      "-of", "json", # Output format as JSON
      video_path # Video file path
   ]

   result = subprocess.run(cmd, capture_output=True, text=True) # Run the ffprobe command
   data = json.loads(result.stdout) if result.stdout else {} # Parse the JSON output
   streams = data.get("streams", []) # Get the list of audio streams

   tracks = [] # List to store audio track information
   for stream in streams: # For each audio stream
      index = stream.get("index", None) # Get the stream index
      language = stream.get("tags", {}).get("language", "und") # Get the language tag, default to "und" (undefined)
      tracks.append({"index": index, "language": language}) # Add the track information to the list

   return tracks # Return the list of audio tracks

def select_audio_track(tracks):
   """
   Display available audio tracks and prompt the user to select one as default.

   :param tracks: List of audio track dictionaries
   :return: Selected track index
   """
   
   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.CYAN}Available audio tracks:{Style.RESET_ALL}")
   for i, track in enumerate(tracks): # For each audio track
      print(f"   {BackgroundColors.YELLOW}[{i}] Index {track['index']} | Language: {track['language']}{Style.RESET_ALL}")

   while True: # Loop until a valid selection is made
      choice = input(f"{BackgroundColors.GREEN}Select the track number to set as default:{Style.RESET_ALL} ")
      if choice.isdigit() and 0 <= int(choice) < len(tracks): # If the choice is valid
         return tracks[int(choice)]["index"] # Return the selected track index
      print(f"{BackgroundColors.RED}Invalid selection. Please try again.{Style.RESET_ALL}")

def swap_audio_tracks(video_path):
   """
   Swap the default audio track in the video with the non-default track.
   Requires ffmpeg and ffprobe installed and available in PATH.

   :param video_path: Path to the video file
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Swapping audio tracks for video: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}") # Output the verbose message

   # Get audio track information using ffprobe
   probe_cmd = [
      "ffprobe",
      "-v", "error",
      "-select_streams", "a",
      "-show_entries", "stream=index:stream_tags=language",
      "-of", "csv=p=0",
      video_path
   ]

   result = subprocess.run(probe_cmd, capture_output=True, text=True) # Run ffprobe and capture output
   audio_tracks = result.stdout.strip().splitlines() # Get audio track info

   num_tracks = len(audio_tracks) # Number of audio tracks found
   if num_tracks == 0: # If no audio tracks found
      print(f"{BackgroundColors.YELLOW}No audio tracks found for: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}")
      return # Skip this file

   # Display audio tracks to the user if more than two
   if num_tracks > 2:
      print(f"\n{BackgroundColors.CYAN}Audio tracks found in:{BackgroundColors.GREEN} {video_path}{Style.RESET_ALL}")
      for i, track in enumerate(audio_tracks):
         print(f"   [{i}] {track}")
      try:
         default_track_index = int(input(f"{BackgroundColors.YELLOW}Select the track index to set as default:{Style.RESET_ALL} "))
      except ValueError:
         print(f"{BackgroundColors.RED}Invalid input. Skipping file.{Style.RESET_ALL}")
         return
      if default_track_index < 0 or default_track_index >= num_tracks:
         print(f"{BackgroundColors.RED}Invalid track index. Skipping file.{Style.RESET_ALL}")
         return
   else:
      default_track_index = 1 if num_tracks == 2 else 0 # Swap only if there are 2 tracks

   root, ext = os.path.splitext(video_path) # Split the file path and extension
   ext = ext.lower() # Ensure lowercase extension
   video_path = video_path if video_path.endswith(ext) else os.rename(video_path, root + ext) or (root + ext) # Rename if needed
   temp_file = root + ".tmp" + ext # Temporary file path with correct extension order

   cmd = ["ffmpeg", "-y", "-i", video_path, "-map", "0", "-c", "copy"] # Base ffmpeg command (with overwrite flag)

   for i in range(num_tracks): # For each audio track
      cmd += ["-disposition:a:" + str(i), "0"] # Clear all dispositions

   cmd += ["-disposition:a:" + str(default_track_index), "default", temp_file] # Set the selected track as default and define output file

   verbose_output(f"{BackgroundColors.GREEN}Executing ffmpeg command:{BackgroundColors.CYAN} {' '.join(cmd)}{Style.RESET_ALL}") # Output the ffmpeg command if verbose is True

   subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) # Run ffmpeg silently

   if not verify_filepath_exists(temp_file): # If the temporary file was not created
      print(f"{BackgroundColors.RED}Failed to create temporary file for: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}") # Output the error message
      print(f"{BackgroundColors.YELLOW}Retrying ffmpeg with error output enabled...{Style.RESET_ALL}") # Notify user of retry
      subprocess.run(cmd) # Retry with visible output for debugging
      return # Exit the function to prevent file replacement

   os.replace(temp_file, video_path) # Replace the original file with the modified file

def play_sound():
   """
   Plays a sound when the program finishes and skips if the operating system is Windows.

   :param: None
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

   :param: None
   :return: None
   """

   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Default Audio Track Switcher{BackgroundColors.GREEN}!{Style.RESET_ALL}\n")
   
   install_ffmpeg_and_ffprobe() # Ensure ffmpeg and ffprobe are installed

   if not verify_filepath_exists(INPUT_DIR): # If the input directory does not exist
      print(f"{BackgroundColors.RED}Input directory not found: {BackgroundColors.CYAN}{INPUT_DIR}{Style.RESET_ALL}")
      return # Exit the program

   videos = find_videos(INPUT_DIR, VIDEO_FILE_EXTENSIONS) # Find all videos in the input directory
   if not videos: # If no videos were found
      print(f"{BackgroundColors.YELLOW}No video files found in {INPUT_DIR}{Style.RESET_ALL}")
      return # Exit the program

   for video in tqdm(videos, desc=f"{BackgroundColors.GREEN}Processing Video Files from {BackgroundColors.CYAN}{INPUT_DIR}{BackgroundColors.GREEN}...{Style.RESET_ALL}"): # For each video found, display a progress bar
      swap_audio_tracks(video) # Swap the audio tracks

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}All videos processed successfully.{Style.RESET_ALL}")

   atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None # Register the play_sound function to be called when the program finishes

if __name__ == "__main__":
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """

   main() # Call the main function
