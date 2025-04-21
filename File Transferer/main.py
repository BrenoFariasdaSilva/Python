import atexit # For playing a sound when the program finishes
import datetime # For generating timestamped filenames
import matplotlib.pyplot as plt # For plotting speed graph
import os # For running a command in the terminal and handling file paths
import platform # For getting the operating system name
import shutil # For copying files and preserving metadata
import time # For measuring time spent
from colorama import Style # For coloring the terminal
from tqdm import tqdm # For the progress bar

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
SOUND_COMMANDS = {"Darwin": "afplay", "Linux": "aplay", "Windows": "start"}
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav"

# Paths
SRC_DIR = r"D:\Backup" # Source directory to copy files from
DST_DIR = r"E:\My Files\Backup" # Destination directory to copy files to

# List of directories to ignore (add any other directories here)
IGNORE_DIRS = {
   "Linux": [".boxsync", "venv", ".git", "node_modules"], # Linux Ignore directories
   "Windows": [".boxsync", "GitHub", "TeraBox", "venv", ".git", "node_modules"], # Windows Ignore directories
   "Darwin": [".boxsync", "venv", ".git", "node_modules"] # MacOS Ignore directories
}

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

def validate_inputs(src_dir=SRC_DIR, dst_dir=DST_DIR):
   """
   Validate the source and destination directories.

   :param src_dir: Source directory to copy files from
   :param dst_dir: Destination directory to copy files to
   :return: True if both directories are valid, False otherwise
   """

   verbose_output(f"{BackgroundColors.GREEN}Validating the source and destination directories{Style.RESET_ALL}") # Output the verbose message

   valid_inputs = True # Initialize valid inputs to True

   if not verify_filepath_exists(src_dir): # Verify if the source directory exists
      print(f"{BackgroundColors.RED}Source directory does not exist: {src_dir}{Style.RESET_ALL}") # Output the error message
      valid_inputs = False # Set valid inputs to False
   
   if not verify_filepath_exists(dst_dir): # Verify if the destination directory exists
      print(f"{BackgroundColors.YELLOW}Destination directory does not exist: {dst_dir}{Style.RESET_ALL}")
      try: # Try to create the destination directory
         os.makedirs(dst_dir, exist_ok=True) # Create the destination directory if it doesn't exist
         print(f"{BackgroundColors.GREEN}Destination directory created: {dst_dir}{Style.RESET_ALL}") # Output the success message
      except Exception as e: # If an error occurs (e.g., permission denied)
         print(f"{BackgroundColors.RED}Error creating destination directory: {e}{Style.RESET_ALL}") # Output the error message
         valid_inputs = False # Set valid inputs to False
      
   if src_dir == dst_dir: # Verify if the source and destination directories are the same
      print(f"{BackgroundColors.RED}Source and destination directories cannot be the same.{Style.RESET_ALL}")
      valid_inputs = False # Set valid inputs to False
   
   if not src_dir or not dst_dir: # Verify if the source and destination directories are empty
      print(f"{BackgroundColors.RED}Source and destination directories cannot be empty.{Style.RESET_ALL}")
      valid_inputs = False # Set valid inputs to False
   
   return valid_inputs # Return True if both directories are valid

def verify_filepath_exists(filepath):
   """
   Verify if a file or folder exists at the specified path.

   :param filepath: Path to the file or folder
   :return: True if the file or folder exists, False otherwise
   """

   verbose_output(f"{BackgroundColors.GREEN}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}") # Output the verbose message

   return os.path.exists(filepath) # Return True if the file or folder exists, False otherwise

def get_platform_ignore_dirs():
   """
   Get the list of directories to ignore based on the current platform.
   
   :return: List of directories to ignore
   """

   verbose_output(f"{BackgroundColors.GREEN}Getting the ignored directories for the current platform: {BackgroundColors.CYAN}{platform.system()}{Style.RESET_ALL}") # Output the verbose message

   current_platform = platform.system() # Get the current platform (Linux, Windows, Darwin)
   return IGNORE_DIRS.get(current_platform, []) # Get the ignored directories for the current platform

def get_files_to_copy(src_dir):
   """
   Get a list of all files in the source directory, excluding ignored directories.

   :param src_dir: Source directory to copy files from
   :return: List of files to copy
   """

   verbose_output(f"{BackgroundColors.GREEN}Getting all files to copy from the source directory: {BackgroundColors.CYAN}{src_dir}{Style.RESET_ALL}") # Output the verbose message

   all_files = [] # List to store all files to copy
   ignore_dirs_lower = [name.lower() for name in get_platform_ignore_dirs()] # Get the ignored directories for the current platform

   for root, dirs, files in os.walk(src_dir): # Walk through the source directory
      parts = [part.lower() for part in root.split(os.sep)] # Split the path into parts and convert to lowercase
      if any(ignored in parts for ignored in ignore_dirs_lower): # Verify if any ignored directory is in the path parts
         continue # Skip this directory if it contains an ignored directory

      for file in files: # Iterate through all files in the directory
         all_files.append(os.path.join(root, file)) # Append the full path of the file to the list

   return all_files # Return the list of all files to copy

def get_file_size(file_path):
   """
   Get the size of the file.

   :param file_path: Path to the file
   :return: Size of the file in bytes
   """

   verbose_output(f"{BackgroundColors.GREEN}Getting the size of the file: {BackgroundColors.CYAN}{file_path}{Style.RESET_ALL}") # Output the verbose message

   return os.path.getsize(file_path) # Get the size of the file in bytes

def copy_file(src_file, dst_file):
   """
   Copy a file from the source to the destination.

   :param src_file: Source file path
   :param dst_file: Destination file path
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Copying file from {BackgroundColors.CYAN}{src_file}{BackgroundColors.GREEN} to {BackgroundColors.CYAN}{dst_file}{Style.RESET_ALL}") # Output the verbose message

   os.makedirs(os.path.dirname(dst_file), exist_ok=True) # Create the destination directory if it doesn't exist

   shutil.copy2(src_file, dst_file) # Copy the file and preserve metadata

def calculate_speed(file_size, elapsed_time):
   """
   Calculate the speed of the file copy in MB/s.

   :param file_size: Size of the file in bytes
   :param elapsed_time: Time taken to copy the file in seconds
   :return: Speed in MB/s
   """

   verbose_output(f"{BackgroundColors.GREEN}Calculating the speed of the file copy: {BackgroundColors.CYAN}{file_size}{BackgroundColors.GREEN} bytes in {BackgroundColors.CYAN}{elapsed_time}{BackgroundColors.GREEN} seconds{Style.RESET_ALL}") # Output the verbose message

   return (file_size / (1024 * 1024)) / elapsed_time if elapsed_time > 0 else 0 # Avoid division by zero

def list_top_level_dirs(base_dir):
   """
   List top-level directories in the base directory, excluding ignored ones.

   :param base_dir: Base directory to list directories from
   :return: List of top-level directories
   """

   verbose_output(f"{BackgroundColors.GREEN}Listing top-level directories in the base directory: {BackgroundColors.CYAN}{base_dir}{Style.RESET_ALL}") # Output the verbose message

   ignore_dirs = [name.lower() for name in get_platform_ignore_dirs()] # Get the ignored directories for the current platform
   try: # Try to list the directories
      entries = os.listdir(base_dir) # List all entries in the base directory
      dirs = [entry for entry in entries if os.path.isdir(os.path.join(base_dir, entry))] # Filter only directories
      filtered_dirs = [d for d in dirs if d.lower() not in ignore_dirs] # Filter out ignored directories
      return filtered_dirs # Return the filtered list of directories
   except Exception as e: # If an error occurs (e.g., permission denied)
      print(f"{BackgroundColors.RED}Error reading directories in {base_dir}: {e}{Style.RESET_ALL}") # Output the error message
      return [] # Return an empty list
   
def get_dir_size(directory):
   """
   Returns the total size of a directory, including all its subdirectories and files.

   :param directory: Path to the directory
   :return: Total size in bytes
   """

   verbose_output(f"{BackgroundColors.GREEN}Calculating the size of the directory: {BackgroundColors.CYAN}{directory}{Style.RESET_ALL}") # Output the verbose message

   total_size = 0 # Initialize total size to 0

   for dirpath, dirnames, filenames in os.walk(directory): # Walk through the directory
      for filename in filenames: # Iterate through all files in the directory
         filepath = os.path.join(dirpath, filename) # Get the full path of the file
         total_size += os.path.getsize(filepath) # Add the size of the file to the total size
   
   return total_size # Return the total size of the directory in bytes

def print_top_level_dirs_to_copy(base_dir):
   """
   Prints the top-level directories in base_dir that will be copied, excluding ignored ones,
   and shows their sizes and a total size at the end.

   :param base_dir: Base directory to list directories from
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Printing top-level directories to copy from: {BackgroundColors.CYAN}{base_dir}{Style.RESET_ALL}") # Output the verbose message

   top_dirs = list_top_level_dirs(base_dir) # Assuming list_top_level_dirs is defined elsewhere
   total_size = 0 # Initialize total size to 0

   if top_dirs: # If there are directories to copy
      print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Directories to be copied:{Style.RESET_ALL}") # Output the header
      for dir_name in top_dirs: # Iterate through all top-level directories
         dir_path = os.path.join(base_dir, dir_name) # Get the full path of the directory
         dir_size = get_dir_size(dir_path) # Get the size of the directory
         total_size += dir_size # Add the size of the directory to the total size
         print(f"{BackgroundColors.CYAN}- {dir_name} ({format_size(dir_size)}){Style.RESET_ALL}") # Output the directory name and size
      
      print(f"{BackgroundColors.GREEN}Total size: {BackgroundColors.CYAN}{format_size(total_size)}{Style.RESET_ALL}\n") # Output the total size of all directories
   else: # If there are no directories to copy
      print(f"\n{BackgroundColors.RED}No valid directories found to copy.{Style.RESET_ALL}") # Output the error message

def copy_and_track_files(src_dir, dst_dir):
   """
   Copies all files from src_dir to dst_dir while tracking the copy speed with a progress bar.
   :return: Tuple containing (total_time_minutes, total_bytes_copied, avg_speed_MBps, file_speeds)

   :param src_dir: Source directory to copy files from
   :param dst_dir: Destination directory to copy files to
   :return: Tuple containing (total_time_minutes, total_bytes_copied, avg_speed_MBps, file_speeds)
   """

   verbose_output(f"{BackgroundColors.GREEN}Copying files from {BackgroundColors.CYAN}{src_dir}{BackgroundColors.GREEN} to {BackgroundColors.CYAN}{dst_dir}{Style.RESET_ALL}") # Output the verbose message

   file_speeds = [] # (timestamp_since_start, speed_MBps)
   total_bytes_copied = 0 # Total bytes copied
   start_time = time.time() # Start time of the copy process

   all_files = get_files_to_copy(src_dir) # Get all files to copy from the source directory

   print_top_level_dirs_to_copy(src_dir) # Print the top-level directories to copy

   current_top_dir = None # Current top-level directory being copied

   with tqdm(total=len(all_files), unit="file", desc=f"{BackgroundColors.GREEN}Copying Files{Style.RESET_ALL}") as pbar: # Initialize the progress bar
      for src_file in all_files: # Iterate through all files to copy
         relative_path = os.path.relpath(src_file, src_dir) # Get the relative path of the file
         top_dir = relative_path.split(os.sep)[0] if os.sep in relative_path else "" # Get the top-level directory of the file

         if top_dir != current_top_dir: # If the top-level directory has changed
            current_top_dir = top_dir # Update the current top-level directory
            pbar.set_description(f"{BackgroundColors.GREEN}Copying: {BackgroundColors.CYAN}{current_top_dir or "root"}{Style.RESET_ALL}") # Update the progress bar description

         dst_file = os.path.join(dst_dir, relative_path) # Get the destination file path

         try: # Try to copy the file
            file_size = get_file_size(src_file) # Get the size of the file
            file_start = time.time() # Start time of the file copy

            copy_file(src_file, dst_file) # Copy the file

            file_end = time.time() # End time of the file copy
            elapsed = file_end - file_start # Elapsed time of the file copy
            speed_MBps = calculate_speed(file_size, elapsed) # Calculate the speed of the file copy

            file_speeds.append((file_end - start_time, speed_MBps)) # Append the speed to the list
            total_bytes_copied += file_size # Add the size of the file to the total bytes copied

            pbar.set_postfix({"Speed (MB/s)": f"{speed_MBps:.2f}"}) # Update the progress bar postfix with the speed
            pbar.update(1) # Update the progress bar
         except Exception as e: # If an error occurs (e.g., permission denied)
            print(f"{BackgroundColors.RED}Error copying {src_file}: {e}{Style.RESET_ALL}") # Output the error message

   end_time = time.time() # End time of the copy process
   total_time_minutes = (end_time - start_time) / 60 # Total time in minutes
   avg_speed_MBps = (total_bytes_copied / (1024 * 1024)) / (end_time - start_time) # Average speed in MB/s

   return total_time_minutes, total_bytes_copied, avg_speed_MBps, file_speeds # Return the total time, total bytes copied, average speed, and file speeds

def format_duration(minutes):
   """
   Formats duration from minutes to a human-readable string.

   :param minutes: Duration in minutes
   :return: Formatted duration string
   """

   verbose_output(f"{BackgroundColors.GREEN}Formatting duration from {BackgroundColors.CYAN}{minutes}{BackgroundColors.GREEN} minutes to a human-readable string{Style.RESET_ALL}") # Output the verbose message

   seconds = int(minutes * 60) # Convert minutes to seconds
   days, seconds = divmod(seconds, 86400) # Get the number of days and remaining seconds
   hours, seconds = divmod(seconds, 3600) # Get the number of hours and remaining seconds
   mins, seconds = divmod(seconds, 60) # Get the number of minutes and remaining seconds

   parts = [] # List to store the formatted parts of the duration
   
   if days: parts.append(f"{days}d") # If there are days, add them to the list
   if hours: parts.append(f"{hours}h") # If there are hours, add them to the list
   if mins: parts.append(f"{mins}m") # If there are minutes, add them to the list
   if not parts or seconds: parts.append(f"{seconds}s") # If there are no parts or there are seconds, add them to the list

   return " ".join(parts) # Join the parts with spaces

def format_size(bytes_size):
   """
   Formats bytes into the most suitable size unit.

   :param bytes_size: Size in bytes
   :return: Formatted size string
   """

   verbose_output(f"{BackgroundColors.GREEN}Formatting size from {BackgroundColors.CYAN}{bytes_size}{BackgroundColors.GREEN} bytes to a human-readable string{Style.RESET_ALL}") # Output the verbose message

   units = ["B", "KB", "MB", "GB", "TB"] # List of size units
   size = float(bytes_size) # Convert bytes size to float

   for unit in units: # Iterate through all size units
      if size < 1024.0: # If the size is less than 1024, return the formatted size
         return f"{size:.2f} {unit}" # Format the size with 2 decimal places and the unit
      size /= 1024.0 # Divide the size by 1024 to convert to the next unit
   
   return f"{size:.2f} PB" # If the size is larger than TB, return it in PB

def print_summary(total_time, total_bytes, avg_speed):
   """
   Prints a summary of the file copy operation.

   :param total_time: Total time taken for the copy operation in minutes
   :param total_bytes: Total bytes copied
   :param avg_speed: Average speed of the copy operation in MB/s
   :return: None
   """

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Summary:{Style.RESET_ALL}")
   print(f"{BackgroundColors.CYAN}Total time:{Style.RESET_ALL} {total_time:.2f} minutes")
   print(f"{BackgroundColors.CYAN}Total data:{Style.RESET_ALL} {total_bytes / (1024 * 1024):.2f} MB")
   print(f"{BackgroundColors.CYAN}Average speed:{Style.RESET_ALL} {avg_speed:.2f} MB/s")

def ensure_output_directory(path="./Output"):
   """
   Creates the output directory if it doesn't exist.

   :param path: Path to the output directory
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Ensuring the output directory exists at: {BackgroundColors.CYAN}{path}{Style.RESET_ALL}") # Output the verbose message

   os.makedirs(path, exist_ok=True) # Create the output directory if it doesn't exist

def plot_copy_speed(file_speeds, average_speed):
   """
   Plots the file copy speed over time, shows the average speed line,
   and saves the plot to ./Output with timestamped filename.

   :param file_speeds: List of tuples containing (timestamp_since_start, speed_MBps)
   :param average_speed: Average speed of the file copy in MB/s
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Plotting the file copy speed over time{Style.RESET_ALL}") # Output the verbose message

   if not file_speeds: # If there are no file speeds to plot
      print(f"{BackgroundColors.RED}No data to plot copy speed.{Style.RESET_ALL}") # Output the error message
      return # Return

   ensure_output_directory() # Ensure the output directory exists

   timestamp_str = datetime.datetime.now().strftime("%Y.%m.%d - %HH-%MM-%SS") # Generate a timestamp string for the filename
   filename = f"./Output/{timestamp_str}.png" # Filename for the plot

   timestamps, speeds = zip(*file_speeds) # Unzip the file speeds into timestamps and speeds

   plt.figure(figsize=(10, 5)) # Create a new figure for the plot
   plt.plot(timestamps, speeds, label="Copy Speed (MB/s)") # Plot the copy speed
   plt.axhline(average_speed, color="red", linestyle="--", label=f"Average: {average_speed:.2f} MB/s") # Plot the average speed line
   plt.xlabel("Time since start (s)") # X-axis label
   plt.ylabel("Speed (MB/s)") # Y-axis label
   plt.title("File Copy Speed Over Time") # Plot title
   plt.legend() # Show the legend
   plt.grid(True) # Show grid lines
   plt.tight_layout() # Adjust layout to fit the plot

   plt.savefig(filename) # Save the plot to the output directory
   print(f"{BackgroundColors.GREEN}Plot saved as: {filename}{Style.RESET_ALL}") # Output the filename
   plt.show() # Show the plot

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
   """

   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Copying files from {BackgroundColors.CYAN}{SRC_DIR}{BackgroundColors.GREEN} to {BackgroundColors.CYAN}{DST_DIR}{Style.RESET_ALL}\n")

   if not validate_inputs(SRC_DIR, DST_DIR): # Validate the source and destination directories
      return # Return if the inputs are not valid

   total_time, total_bytes, avg_speed, speeds = copy_and_track_files(SRC_DIR, DST_DIR) # Copy files and track the speed
   print_summary(total_time, total_bytes, avg_speed) # Print the summary of the copy operation
   plot_copy_speed(speeds, avg_speed) # Plot the copy speed over time

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}")

   atexit.register(play_sound) # Register the function to play a sound when the program finishes

if __name__ == "__main__":
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """
   
   main()
