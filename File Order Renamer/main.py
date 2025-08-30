import atexit # For playing a sound when the program finishes
import os # For running a command in the terminal
import platform # For getting the operating system name
import re # For regular expression matching
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

# Ignored Files and Directories:
IGNORED_FILES = {"Makefile", "main.py", "requirements.txt"} # Files to be ignored
IGNORED_DIRS = {".assets", "venv"} # Directories to be ignored

# File Constants:
MOVIES_FILE_FORMAT = ["avi", "mkv", "mov", "mp4"] # The extensions of the movies
SUBTITLES_FILE_FORMAT = ["srt"] # The extensions of the subtitles
SUBTITLE_VARIATION = ["pt-BR", "en-US", "eng", "pt"] # The variations of the subtitles

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

def getFileFormat(file):
   """
   This function will return the file format of the file.
   
   :param file: The file to get the format from.
   :return: The file format.
   """

   return file[file.rfind(".") + 1:] # Return the file format

def is_two_digit_sequence(filename):
   """
   This function checks if the filename is already in the "two-digit sequence" format (e.g., 01.mkv, 02.s
   
   :param filename: The filename to check.
   :return: True if the filename is in the "two-digit sequence" format, False otherwise.
   """

   return bool(re.match(r'^\d{2}\.[a-zA-Z]+$', filename)) # Verify if the filename is in the "two-digit sequence" format

def all_files_properly_renamed(file_list):
   """
   This function checks if all files in the list are properly renamed.

   :param file_list: The list of files to check.
   :return: True if all files are properly renamed, False otherwise.
   """

   return all(is_two_digit_sequence(file) for file in file_list) # Check if all files are properly renamed

def getFileNameWithoutExtension(file):
   """
   This function will return the file name without the extension.
   
   :param file: The file to get the name from.
   :return: The file name without the extension.
   """

   return file[:file.rfind(".")] # Return the file name without the extension

def get_file_number(file_order):
   """
   Returns the formatted file number.

   :param file_order: The current file order.
   :return: Formatted file number as string.
   """

   return f"0{file_order}" if file_order < 10 else str(file_order) # Return the formatted file number

def extract_season_episode(file_name):
   """
   This function extracts the season and episode numbers from a file name.
   
   :param file_name: The file name to extract the season and episode from.
   :return: A tuple (season, episode) if found, otherwise None.
   """

   verbose_output(f"{BackgroundColors.YELLOW}Extracting the season and episode numbers from the file name: {BackgroundColors.CYAN}{file_name}{Style.RESET_ALL}") # Output the verbose message

   pattern = r"S(\d+)E(\d+)" # Pattern to match season and episode (e.g., S01E01)
   match = re.search(pattern, file_name, re.IGNORECASE) # Search for the pattern in the file name

   if match: # If the pattern is found
      season = int(match.group(1)) # Extract the season number
      episode = int(match.group(2)) # Extract the episode number
      return season, episode # Return the season and episode numbers as a tuple
   return None

def is_related_movie_subtitle(movie_file, subtitle_file):
   """
   This function checks if the movie name is a substring of the subtitle file name or
   if the season and episode numbers match in both the movie and subtitle files.
   
   :param movie_file: The movie file name.
   :param subtitle_file: The subtitle file name.
   :return: True if the movie and subtitle are related, False otherwise.
   """

   verbose_output(f"{BackgroundColors.YELLOW}Checking if the movie and subtitle are related:{Style.RESET_ALL}") # Output the verbose message

   movie_base_name = getFileNameWithoutExtension(movie_file) # Get the movie's base name
   subtitle_base_name = getFileNameWithoutExtension(subtitle_file) # Get the subtitle's base name

   if movie_base_name in subtitle_base_name: # If the movie's base name is a substring of the subtitle's base name
      return True # Return True if the movie and subtitle are related

   movie_season_episode = extract_season_episode(movie_base_name) # Extract the season and episode numbers from the movie base name
   subtitle_season_episode = extract_season_episode(subtitle_base_name) # Extract the season and episode numbers from the subtitle base name

   if movie_season_episode and subtitle_season_episode: # If both the movie and subtitle have season and episode numbers
      return movie_season_episode == subtitle_season_episode # Return True if the season and episode numbers match

   return False # Return False if no relation is found

def find_related_subtitle(file_list, i, number_of_files):
   """
   Finds the related subtitle for a movie file.

   :param file_list: The list of files in the directory.
   :param i: The index of the current movie file in the list.
   :param number_of_files: The total number of files in the list.
   :return: The related subtitle file if found, otherwise None.
   """

   for j in range(i + 1, number_of_files): # Loop through subsequent files to find a related subtitle
      if getFileFormat(file_list[j]) in SUBTITLES_FILE_FORMAT and is_related_movie_subtitle(file_list[i], file_list[j]): # If the file is a subtitle and is related to the movie
         return file_list[j] # Return the related subtitle file if found
   
   return None # Return None if no related subtitle is found

def rename_with_subtitle(file_list, i, file_number, dir_path, current_file_format, related_subtitle):
   """
   Renames the movie and subtitle files when a related subtitle is found.

   :param file_list: The list of files to rename.
   :param i: The index of the movie file in the list.
   :param file_number: The formatted file number to be used in the renaming.
   :param dir_path: The directory path where the files are located.
   :param current_file_format: The format of the movie file.
   :param related_subtitle: The related subtitle file.
   :return: None
   """

   print(f"Renaming with Subtitle: {BackgroundColors.CYAN}{file_list[i]}{BackgroundColors.GREEN} -> {BackgroundColors.CYAN}{file_number}.{current_file_format}{Style.RESET_ALL}")
   print(f"Renaming with Subtitle: {BackgroundColors.CYAN}{related_subtitle}{BackgroundColors.GREEN} -> {BackgroundColors.CYAN}{file_number}.srt{Style.RESET_ALL}")

   os.rename(os.path.join(dir_path, file_list[i]), os.path.join(dir_path, f"{file_number}.{current_file_format}")) # Rename the movie file
   os.rename(os.path.join(dir_path, related_subtitle), os.path.join(dir_path, f"{file_number}.srt")) # Rename the related subtitle file

def rename_file(file_list, i, dir_path, current_file_format, file_number):
   """
   Renames a movie file when no related subtitle is found.

   :param file_list: The list of files to rename.
   :param i: The index of the movie file in the list.
   :param dir_path: The directory path where the files are located.
   :param current_file_format: The format of the movie file.
   :param file_number: The formatted file number to be used in the renaming.
   :return: None
   """

   print(f"Renaming: {BackgroundColors.CYAN}{file_list[i]}{BackgroundColors.GREEN} -> {BackgroundColors.CYAN}{file_number}.{current_file_format}{Style.RESET_ALL}")

   os.rename(os.path.join(dir_path, file_list[i]), os.path.join(dir_path, f"{file_number}.{current_file_format}")) # Rename the movie file

def rename_movies(file_list, dir_path):
   """
   This function renames the movies and subtitles in the directory.

   :param file_list: The list of files to rename.
   :param dir_path: The directory path.
   :return: None
   """
   
   verbose_output(f"{BackgroundColors.YELLOW}Renaming the files in the directory: {BackgroundColors.CYAN}{dir_path}{Style.RESET_ALL}")
   
   movie_files = [file for file in file_list if getFileFormat(file) not in SUBTITLES_FILE_FORMAT] # Get the movie files
   subtitle_files = [file for file in file_list if getFileFormat(file) in SUBTITLES_FILE_FORMAT] # Get the subtitle files

   movie_files.sort() # Sort the movie files
   subtitle_files.sort() # Sort the subtitle files

   file_order = 1 # Initialize the file order for renaming

   for movie_file in movie_files: # Loop through the movie files to rename them
      current_file_format = getFileFormat(movie_file) # Get the format of the current movie file
      file_number = get_file_number(file_order) # Get the formatted file number

      related_subtitle = find_related_subtitle(file_list, file_list.index(movie_file), len(file_list)) # Find related subtitle
      
      if related_subtitle: # If a related subtitle is found
         rename_with_subtitle(file_list, file_list.index(movie_file), file_number, dir_path, current_file_format, related_subtitle) # Rename both movie and subtitle files
         file_order += 1 # Increment the file order for the next renaming
         continue # Skip incrementing "file_order" here since the subtitle is handled

      else: # If no related subtitle is found
         rename_file(file_list, file_list.index(movie_file), dir_path, current_file_format, file_number) # Rename the movie file
         file_order += 1 # Increment the file order for the next renaming

   subtitle_file_order = 1 # For subtitle files, we can start fresh
   for subtitle_file in subtitle_files: # Loop through the subtitle files to rename them
      current_file_format = getFileFormat(subtitle_file) # Get the format of the current subtitle file
      file_number = get_file_number(subtitle_file_order) # Get the formatted file number

      rename_file(file_list, file_list.index(subtitle_file), dir_path, current_file_format, file_number) # Rename the subtitle file
      subtitle_file_order += 1 # Increment the subtitle file order for the next renaming

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

   print(f"{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}File Order Renamer{BackgroundColors.GREEN}!{Style.RESET_ALL}", end="\n\n")

   current_path = os.getcwd() # Get the current path

   for dir_path, subdirs, files in os.walk(current_path): # Walk through the current path
      if any(ignored_dir in dir_path for ignored_dir in IGNORED_DIRS): # If the directory is in the ignored directories
         continue # Skip the directory if it is in the ignored directories

      file_list = [file for file in files if file not in IGNORED_FILES and (getFileFormat(file) in MOVIES_FILE_FORMAT or getFileFormat(file) in SUBTITLES_FILE_FORMAT)] # Get the list of files in the directory
      file_list.sort() # Sort the list of files

      if len(file_list) == 0: # If there are no files in the directory
         print(f"{BackgroundColors.CYAN}No files found in the directory: {dir_path}{Style.RESET_ALL}") # Output the message
      else: # If there are files in the directory
         print(f"{BackgroundColors.GREEN}Processing directory: {dir_path}{Style.RESET_ALL}") # Output the message
         if all_files_properly_renamed(file_list): # If all files are already properly renamed
            print(f"{BackgroundColors.CYAN}All files are already properly renamed in this directory.{Style.RESET_ALL}") # Output the message
         else: # If not all files are properly renamed
            rename_movies(file_list, dir_path) # Rename the files

   print(f"\n{BackgroundColors.GREEN}Finished renaming the files!{Style.RESET_ALL}")

   atexit.register(play_sound) # Register the function to play a sound when the program finishes

if __name__ == "__main__":
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """

   main() # Call the main function
