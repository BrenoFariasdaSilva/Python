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
   "Linux": [".boxsync", "TeraBox/Downloads/", "venv", "node_modules"], # Linux Ignore directories
   "Windows": [".boxsync", "GitHub", "TeraBox/Downloads/", "venv", "node_modules"], # Windows Ignore directories
   "Darwin": [".boxsync", "TeraBox/Downloads/", "venv", "node_modules"] # MacOS Ignore directories
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
   Get a list of all files in the source directory, excluding ignored directories and subdirectories.
   Also includes empty directories to be recreated at the destination.

   :param src_dir: Source directory to copy files from
   :return: List of files and empty directories to copy
   """

   verbose_output(f"{BackgroundColors.GREEN}Getting all files to copy from the source directory: {BackgroundColors.CYAN}{src_dir}{Style.RESET_ALL}") # Output the verbose message

   all_paths = [] # List to store all file and empty directory paths
   ignore_paths = [os.path.normpath(os.path.join(src_dir, path)) for path in get_platform_ignore_dirs()] # Get the ignored directories for the current platform
   
   for root, dirs, files in os.walk(src_dir): # Walk through the source directory
      root_normalized = os.path.normpath(root) # Normalize the path of the current directory

      if any(root_normalized.startswith(ignore_dir) for ignore_dir in ignore_paths): # Verify if the current directory is in the ignored directories
         verbose_output(f"{BackgroundColors.YELLOW}Skipping ignored directory: {BackgroundColors.CYAN}{root}{Style.RESET_ALL}")
         continue # Skip this directory if it contains an ignored directory
      
      if not files and not dirs: # If the directory is empty (no files and no subdirectories)
         all_paths.append(root_normalized) # Add the empty directory to the list

      for file in files: # Iterate through all files in the directory
         all_paths.append(os.path.join(root, file)) # Get the full path of the file and add it to the list

   return all_paths # Return the list of all file and empty directory paths

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
   Returns the total size of a directory, excluding ignored subdirectories and their files.

   :param directory: Path to the directory
   :return: Total size in bytes
   """

   verbose_output(f"{BackgroundColors.GREEN}Calculating the size of the directory: {BackgroundColors.CYAN}{directory}{Style.RESET_ALL}") # Output the verbose message

   total_size = 0 # Initialize total size to 0
   ignore_paths = [os.path.normpath(os.path.join(SRC_DIR, path)) for path in get_platform_ignore_dirs()] # Get the ignored directories for the current platform

   for dirpath, dirnames, filenames in os.walk(directory): # Walk through the directory
      dirpath_normalized = os.path.normpath(dirpath) # Normalize the path of the current directory

      if any(dirpath_normalized.startswith(ignore_dir) for ignore_dir in ignore_paths): # Verify if the current directory is in the ignored directories
         continue # Skip this directory if it contains an ignored directory

      for filename in filenames: # Iterate through all files in the directory
         filepath = os.path.join(dirpath, filename) # Get the full path of the file
         try: # Try to get the size of the file
            total_size += os.path.getsize(filepath) # Add the size of the file to the total size
         except OSError: # If an error occurs (e.g., permission denied)
            verbose_output(f"{BackgroundColors.RED}Could not access file: {filepath}{Style.RESET_ALL}")

   return total_size # Return the total size of the directory

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
   :return: Tuple containing (total_time_minutes, total_bytes_copied, avg_speed_Bps, file_speeds)

   :param src_dir: Source directory to copy files from
   :param dst_dir: Destination directory to copy files to
   :return: Tuple containing (total_time_minutes, total_bytes_copied, avg_speed_Bps, file_speeds)
   """

   verbose_output(f"{BackgroundColors.GREEN}Copying files from {BackgroundColors.CYAN}{src_dir}{BackgroundColors.GREEN} to {BackgroundColors.CYAN}{dst_dir}{Style.RESET_ALL}") # Output the verbose message

   file_speeds = [] # (timestamp_since_start, speed_Bps)
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
            pbar.set_description(f"{BackgroundColors.GREEN}Copying: {BackgroundColors.CYAN}{current_top_dir or 'root'}{Style.RESET_ALL}") # Update the progress bar description

         dst_file = os.path.join(dst_dir, relative_path) # Get the destination file path

         try: # Try to copy the file
            file_size = get_file_size(src_file) # Get the size of the file
            file_start = time.time() # Start time of the file copy

            copy_file(src_file, dst_file) # Copy the file

            file_end = time.time() # End time of the file copy
            elapsed = file_end - file_start # Elapsed time of the file copy
            speed_Bps = file_size / elapsed if elapsed > 0 else 0 # Calculate the speed in Bytes/s

            file_speeds.append((file_end - start_time, speed_Bps)) # Append the speed to the list
            total_bytes_copied += file_size # Add the size of the file to the total bytes copied

            pbar.set_postfix({"Speed": format_size(speed_Bps) + "/s"}) # Update the progress bar postfix with the formatted speed
            pbar.update(1) # Update the progress bar
         except Exception as e: # If an error occurs (e.g., permission denied)
            print(f"{BackgroundColors.RED}Error copying {src_file}: {e}{Style.RESET_ALL}") # Output the error message

   end_time = time.time() # End time of the copy process
   total_time_minutes = (end_time - start_time) / 60 # Total time in minutes
   avg_speed_Bps = total_bytes_copied / (end_time - start_time) # Average speed in Bytes/s

   return total_time_minutes, total_bytes_copied, avg_speed_Bps, file_speeds # Return the total time, total bytes copied, average speed, and file speeds

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
   print(f"{BackgroundColors.GREEN}- Total Time:{BackgroundColors.CYAN} {format_duration(total_time)}{Style.RESET_ALL}") # Output the total time taken for the copy operation
   print(f"{BackgroundColors.GREEN}- Total Data:{Style.RESET_ALL} {format_size(total_bytes)}") # Output the total data copied
   print(f"{BackgroundColors.CYAN}- Average Write Speed: {BackgroundColors.GREEN}{format_size(avg_speed)}{Style.RESET_ALL}") # Output the average speed of the copy operation

def ensure_output_directory(path="./Output"):
   """
   Creates the output directory if it doesn't exist.

   :param path: Path to the output directory
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Ensuring the output directory exists at: {BackgroundColors.CYAN}{path}{Style.RESET_ALL}") # Output the verbose message

   os.makedirs(path, exist_ok=True) # Create the output directory if it doesn't exist

def generate_copy_speed_plot(file_speeds, average_speed): 
   """
   Generates and returns a matplotlib Figure showing file copy speed over time.

   :param file_speeds: List of tuples containing (timestamp_since_start, speed_Bps)
   :param average_speed: Average speed of the file copy in B/s
   :return: matplotlib.figure.Figure or None if no data
   """

   verbose_output(f"{BackgroundColors.GREEN}Plotting the file copy speed over time{Style.RESET_ALL}") # Output the verbose message

   if not file_speeds: # If there are no file speeds to plot
      print(f"{BackgroundColors.RED}No data to plot copy speed.{Style.RESET_ALL}") # Output the error message
      return # Return

   timestamps, speeds = zip(*file_speeds) # Unzip the file speeds into timestamps and speeds

   formatted_average_speed = format_size(average_speed) # Format the average speed into a human-readable string

   fig, ax = plt.subplots(figsize=(10, 5)) # Create a figure and axis for the plot
   ax.plot(timestamps, speeds, label="Copy Speed") # Plot the copy speed
   ax.axhline(average_speed, color="red", linestyle="--", label=f"Average: {formatted_average_speed}/s") # Plot the average speed using human-readable format
   ax.set_xlabel("Time since start (s)") # Set the x-axis label
   ax.set_ylabel("Speed") # Set the y-axis label
   ax.set_title("File Copy Speed Over Time") # Set the title of the plot
   ax.legend() # Add a legend to the plot
   ax.grid(True) # Add a grid to the plot
   fig.tight_layout() # Adjust the layout of the plot

   return fig # Return the figure object

def save_copy_speed_plot(fig):
   """
   Saves a given matplotlib Figure to ./Output with a timestamped filename.

   :param fig: matplotlib.figure.Figure to save
   """

   verbose_output(f"{BackgroundColors.GREEN}Saving the plot to {BackgroundColors.CYAN}./Output{Style.RESET_ALL}") # Output the verbose message

   if fig is None: # If there is no figure to save
      print(f"{BackgroundColors.RED}No figure to save.{Style.RESET_ALL}") # Output the error message
      return # Return

   ensure_output_directory() # Ensure the output directory exists
   timestamp_str = datetime.datetime.now().strftime("%Y.%m.%d - %HH-%MM-%SS") # Generate a timestamp string
   filename = f"./Output/{timestamp_str}.png" # Create a filename with the timestamp
   fig.savefig(filename) # Save the figure to the filename
   print(f"{BackgroundColors.GREEN}Plot saved as: {filename}{Style.RESET_ALL}") # Output the success message

def show_copy_speed_plot(fig):
   """
   Displays a given matplotlib Figure using plt.show().

   :param fig: matplotlib.figure.Figure to display
   """

   verbose_output(f"{BackgroundColors.GREEN}Displaying the plot{Style.RESET_ALL}") # Output the verbose message

   if fig is None: # If there is no figure to display
      print(f"{BackgroundColors.RED}No figure to display.{Style.RESET_ALL}") # Output the error message
      return # Return

   plt.show() # Display the figure

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

   fig = generate_copy_speed_plot(speeds, avg_speed) # Generate the copy speed plot
   save_copy_speed_plot(fig) # Save the copy speed plot if RUN_FUNCTIONS["Save Plot"] is True
   show_copy_speed_plot(fig) # Show the copy speed plot if RUN_FUNCTIONS["Plotting"] is True

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}")

   atexit.register(play_sound) # Register the function to play a sound when the program finishes

if __name__ == "__main__":
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """
   
   main()
