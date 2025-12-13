import atexit # For playing a sound when the program finishes
import ctypes # For checking hidden/system attributes on Windows
import os # For running a command in the terminal and walking through the filesystem
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

# Execution Constants:
VERBOSE = False # Set to True to output verbose messages
WIPE_PATH_WITH_ZEROS = True # Set to True to wipe the path with zeros (only for empty paths)
TARGET_PATH = "E:\\" # The target path to scan

# RUN_FUNCTIONS:
RUN_FUNCTIONS = {
   "Play Sound": True, # Set to True to play a sound when the program finishes
}

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

   verbose_output(f"{BackgroundColors.GREEN}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}") # Output the verbose message

   return os.path.exists(filepath) # Return True if the file or folder exists, False otherwise

def is_hidden_or_system(filepath):
   """
   Cross-platform check if a file is hidden or a system file.

   On Unix-like systems, files starting with "." are considered hidden.
   On Windows, uses file attributes to detect hidden/system flags.

   :param filepath: Path to the file
   :return: True if file is hidden/system, False otherwise
   """

   verbose_output(f"{BackgroundColors.GREEN}Checking if the file is hidden or system: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}")

   filename = os.path.basename(filepath) # Get the file name from the path
   if filename.startswith("."): # If the file name starts with "."
      return True # Unix-like hidden file

   if os.name == "nt": # If the operating system is Windows
      try: # Try to get the file attributes 
         import ctypes # Import ctypes for Windows API calls
         attrs = ctypes.windll.kernel32.GetFileAttributesW(str(filepath)) # Get the file attributes
         return bool(attrs & 2 or attrs & 4) # FILE_ATTRIBUTE_HIDDEN or SYSTEM
      except Exception: # If an error occurs while getting the file attributes
         return False # Return False indicating the file is not hidden/system
   
   return False # Not hidden/system on non-Windows and doesn't start with "."

def analyze_path_content(target_path):
   """
   Walks through the path and collects information about files.

   :param target_path: Path to the directory to be analyzed
   :return: (int, int, list) - Total files, total size, list of suspicious files
   """

   verbose_output(f"{BackgroundColors.GREEN}Analyzing path contents at: {BackgroundColors.CYAN}{target_path}{Style.RESET_ALL}") # Output the analysis message

   total_files = 0 # Total number of files
   total_size = 0 # Total size of all files
   suspicious_files = [] # List of suspicious hidden or system files

   for root, _, files in os.walk(target_path): # Walk through the directory tree
      for file in files: # Loop over each file
         try: # Try to analyze the file
            file_path = os.path.join(root, file) # Get the full file path
            size = os.path.getsize(file_path) # Get the size of the file
            total_files += 1 # Increment total file count
            total_size += size # Increment total size

            if size > 0 and is_hidden_or_system(file_path): # If the file is hidden/system and not empty
               suspicious_files.append(file_path) # Add to suspicious file list

         except Exception as e: # If an error occurs while reading the file
            verbose_output(false_string=f"{BackgroundColors.YELLOW}Error reading file {file_path}: {e}{Style.RESET_ALL}") # Output the error message

   return total_files, total_size, suspicious_files # Return the analysis results

def bytes_to_readable_unit(num):
   """
   Converts a number of bytes to a human-readable string.

   :param num: Number of bytes
   :return: Readable string with appropriate unit
   """

   verbose_output(f"{BackgroundColors.GREEN}Converting bytes to readable format: {BackgroundColors.CYAN}{num}{Style.RESET_ALL}") # Output the conversion message

   for unit in ["B", "KB", "MB", "GB", "TB"]: # Loop over each unit
      if num < 1024: # If the number is less than 1024
         return f"{num:.2f} {unit}" # Return the formatted string with the appropriate unit
      num /= 1024 # Divide the number by 1024 to convert to the next unit

def display_scan_summary(total_files, total_size, suspicious_files):
   """
   Prints the summary of the scan, including suspicious files if found.

   :param total_files: Number of files found
   :param total_size: Total size in bytes
   :param suspicious_files: List of hidden or system files
   :return: None
   """

   print(f"{BackgroundColors.GREEN}Displaying scan summary:{Style.RESET_ALL}") # Output the summary message
   print(f"\n{BackgroundColors.GREEN}- Total files found: {BackgroundColors.CYAN}{total_files}{Style.RESET_ALL}") # Output the total files found
   print(f"{BackgroundColors.GREEN}- Total size used: {BackgroundColors.CYAN}{bytes_to_readable_unit(total_size)}{Style.RESET_ALL}") # Output the total size used

   if suspicious_files: # If suspicious files were found
      print(f"\n{BackgroundColors.YELLOW}Hidden or system files found:{Style.RESET_ALL}") # Output the warning
      for path in suspicious_files: # Loop through suspicious files
         print(f" - {path}") # Print each suspicious file path
   else: # If no suspicious files were found
      print(f"\n{BackgroundColors.GREEN}No hidden or system files found.{Style.RESET_ALL}") # Output confirmation

def is_path_clean(total_files, total_size):
   """
   Determines if the path is clean based on the scan results.

   :param total_files: Number of files found
   :param total_size: Total size in bytes
   :return: bool - True if clean, False if not
   """

   verbose_output(f"{BackgroundColors.GREEN}Checking if the path is clean...{Style.RESET_ALL}") # Output the check message

   if total_files == 0 and total_size == 0: # If no files were found
      print(f"\n{BackgroundColors.GREEN}✅ Path appears to be clean (no files found).{Style.RESET_ALL}") # Output that the path is clean
      return True # Return True indicating the path is clean
   else: # If files were found
      print(f"\n{BackgroundColors.RED}⚠️ Path is NOT empty. You may want to securely wipe it before selling or trashing.{Style.RESET_ALL}") # Output that the path is not clean
      return False # Return False indicating the path contains data

def scan_path(target_path=TARGET_PATH):
   """
   Scans a given path for files and reports if it's clean or contains data.

   :param target_path: Path to the directory to be scanned
   :return: bool - True if the path is clean, False otherwise
   """

   verbose_output(f"{BackgroundColors.GREEN}Scanning path: {BackgroundColors.CYAN}{target_path}{Style.RESET_ALL}") # Output the scanning message

   total_files, total_size, suspicious_files = analyze_path_content(target_path) # Analyze contents of the path

   display_scan_summary(total_files, total_size, suspicious_files) # Display the summary of the scan

   return is_path_clean(total_files, total_size) # Return whether the path is clean

def is_raw_device_path(path):
   """
   Detects whether the given path is a raw device path.
   Works for both Windows and Unix-like systems.

   :param path: Path to check
   :return: bool - True if it's a raw device path, False otherwise
   """

   verbose_output(f"{BackgroundColors.GREEN}Checking if the path is a raw device: {BackgroundColors.CYAN}{path}{Style.RESET_ALL}") # Output the check message

   system = platform.system() # Get the current operating system
   
   if system == "Windows": # If the operating system is Windows
      return path.startswith("\\\\.\\") and len(path) == 7 and path[4].isalpha() and path[5] == ":" # Windows raw device path: starts with "\\.\\" and has a drive letter (e.g., "\\.\E:")
   else: # If the operating system is not Windows (Linux or macOS)
      return path.startswith("/dev/") and os.path.exists(path) # Linux/macOS: Common raw devices like /dev/sdX, /dev/nvme0n1, /dev/diskX

def perform_zero_fill_on_file(file_path):
   """
   Overwrites a file with zero bytes.

   :param file_path: Path to the file to be wiped
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Zero-filling file: {BackgroundColors.CYAN}{file_path}{Style.RESET_ALL}") # Output the zero-fill message

   try: # Try to open the file in binary read/write mode
      size = os.path.getsize(file_path) # Get the size of the file
      with open(file_path, "rb+") as f: # Open the file in binary read/write mode
         f.write(b"\x00" * size) # Overwrite the file with zero bytes
         print(f"{BackgroundColors.YELLOW}Zero-filled: {BackgroundColors.CYAN}{file_path}{Style.RESET_ALL}") if VERBOSE else None
   except Exception as e: # If an error occurs while opening or writing to the file
      print(f"{BackgroundColors.RED}Failed to wipe {file_path}: {e}{Style.RESET_ALL}") # Output the error message

def perform_zero_fill_on_raw_device(raw_device):
   """
   Performs the actual writing of zero bytes to the raw device.

   :param raw_device: Path to the raw device (e.g., "\\\\.\\E:" or "/dev/sda")
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Performing zero-fill on raw device: {BackgroundColors.CYAN}{raw_device}{Style.RESET_ALL}")
   
   try: # Try to open the raw device in binary read/write mode
      with open(raw_device, "rb+") as f: # Open the raw device in binary read/write mode
         block_size = 1024 * 1024 # 1 MB block size
         zero_block = b"\x00" * block_size # Create a block of zero bytes
         total_written = 0 # Total bytes written

         while True: # Loop indefinitely
            f.write(zero_block) # Write the zero block to the raw device
            total_written += block_size # Increment the total bytes written

            print(f"{BackgroundColors.YELLOW}Written: {BackgroundColors.CYAN}{bytes_to_readable_unit(total_written)}{Style.RESET_ALL}") if VERBOSE else None # Output the total bytes written if VERBOSE is set
   except Exception as e: # If an error occurs while writing to the raw device
      print(f"{BackgroundColors.RED}Stopping at {bytes_to_readable_unit(total_written)} due to: {e}{Style.RESET_ALL}") # Output the error message

def wipe_path(target_path):
   """
   Overwrites all data in a raw device or recursively wipes all files in a given directory.

   :param target_path: Path to wipe (e.g., "\\\\.\\E:" or "/dev/sda" or "/path/to/folder")
   """

   print(f"{BackgroundColors.BOLD}{BackgroundColors.RED}Wiping: {BackgroundColors.CYAN}{target_path}{Style.RESET_ALL}")

   if not os.path.exists(target_path) and not is_raw_device_path(target_path): # If the path does not exist and is not a raw device path
      print(f"{BackgroundColors.RED}Invalid path or device: {BackgroundColors.CYAN}{target_path}{Style.RESET_ALL}") # Output the error message
      return # Exit the function

   try: # Try to wipe the path
      if is_raw_device_path(target_path): # If the path is a raw device path
         perform_zero_fill_on_raw_device(target_path) # Call the function to perform zero-fill on the raw device
      elif os.path.isfile(target_path): # If the path is a file
         perform_zero_fill_on_file(target_path) # Call the function to perform zero-fill on the file
      else: # If the path is a directory
         for root, dirs, files in os.walk(target_path): # Walk through the directory tree
            for file in files: # Loop over each file
               file_path = os.path.join(root, file) # Get the full file path
               perform_zero_fill_on_file(file_path) # Call the function to perform zero-fill on the file

      print(f"{BackgroundColors.GREEN}✅ Wipe completed successfully.{Style.RESET_ALL}") # Output the success message
   except Exception as e: # If an error occurs while wiping the path
      print(f"{BackgroundColors.RED}Error wiping: {BackgroundColors.CYAN}{e}{Style.RESET_ALL}") # Output the error message

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

   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.CYAN}Path Content Scanner: {BackgroundColors.GREEN}Verifying if the entire path is filled with 0's{Style.RESET_ALL}", end="\n\n") # Output the welcome header

   if not verify_filepath_exists(TARGET_PATH): # If the path path does not exist
      print(f"{BackgroundColors.RED}Directory path {BackgroundColors.CYAN}{TARGET_PATH}{BackgroundColors.RED} does not exist.{Style.RESET_ALL}") # Output an error message
      return # Exit the function

   wiped_path = scan_path(TARGET_PATH) # Call the function to scan the path

   if not wiped_path and WIPE_PATH_WITH_ZEROS: # If the path is not clean and the WIPE_PATH_WITH_ZEROS constant is set to True
      wipe_path(TARGET_PATH) # Call the function to wipe the path

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output the end of the program message

   atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None # Register the play_sound function to be called when the program finishes

if __name__ == "__main__": 
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """

   main() # Call the main function
