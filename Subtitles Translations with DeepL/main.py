"""
================================================================================
Subtitle (SRT) Translation using DeepL API
================================================================================
Author      : Breno Farias da Silva
Created     : 2025-12-13
Description :
   This script translates subtitle files (SRT) from English to Brazilian Portuguese
   using the DeepL API. It processes all .srt files in the specified input directory,
   respecting API usage limits, and saves the translated files with a '_ptBR' suffix.

   Key features include:
      - Automatic loading of SRT files from a directory
      - Integration with DeepL API for translation
      - Respect for API free plan usage limits
      - Logging output to both terminal and file
      - Optional notification sound upon completion

Usage:
   1. Configure the INPUT_DIR and ensure DEEPL_API_KEY is set in the .env file.
   2. Execute the script using Python:
      $ python <script_name>.py
   3. Translated SRT files are saved in the same directory with '_ptBR' appended.

Outputs:
   - Translated SRT files in the input directory, e.g., 01_ptBR.srt
   - Log file for script execution, e.g., Logs/translate_srt.log

TODOs:
   - Implement CLI argument parsing for input/output directories
   - Add support for batch translation with subdirectories
   - Improve handling of very large SRT files to avoid API limit issues
   - Extend support for additional languages

Dependencies:
   - Python >= 3.8
   - deepl
   - python-dotenv
   - colorama
   - Logger (custom logging module)
   - pathlib
   - datetime
   - atexit
   - os
   - sys
   - platform

Assumptions & Notes:
   - All input files must have a .srt extension
   - Input directory must exist and contain valid SRT files
   - DeepL API key must be set in a .env file as DEEPL_API_KEY
   - Platform-specific notes: notification sound may be disabled on Windows
"""

import atexit # For playing a sound when the program finishes
import datetime # For getting the current date and time
import deepl # For DeepL API
import os # For running a command in the terminal
import platform # For getting the operating system name
import sys # For system-specific parameters and functions
from colorama import Style # For coloring the terminal
from dotenv import load_dotenv # For loading environment variables from .env file
from Logger import Logger # For logging output to both terminal and file
from pathlib import Path # For handling file paths
from shutil import copyfile # For copying files
from tqdm import tqdm # For progress bars

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
DESCRIPTIVE_SUBTITLES_REMOVAL = True # Set to True to remove descriptive lines (e.g., [music], (laughs)) from SRT before translation
DEEPL_API_KEY = "" # DeepL API key (will be loaded in load_dotenv function)
INPUT_DIR = f"./Input" # Directory containing the input SRT files
OUTPUT_DIR = Path("./Output") # Base output directory

# Logger Setup:
logger = Logger(f"./Logs/{Path(__file__).stem}.log", clean=True) # Create a Logger instance
sys.stdout = logger # Redirect stdout to the logger
sys.stderr = logger # Redirect stderr to the logger

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

def ensure_env_file():
   """
   Ensures that a .env file exists. If not, creates it by copying .env.example
   and clears the DEEPL_API_KEY value, prompting the user to fill it.

   :return: True if .env already existed, False if it was created.
   """
   
   if os.path.exists(".env"): # Check if .env file exists
      return True # .env exists

   copyfile(".env.example", ".env") # Copy .env.example to .env

   with open(".env", "r") as f: # Open .env file for reading
      lines = f.readlines() # Read all lines
   
   with open(".env", "w") as f: # Open .env file for writing
      for line in lines: # Iterate through each line
         if line.startswith("DEEPL_API_KEY="): # If the line contains the DEEPL_API_KEY
            f.write("DEEPL_API_KEY=\n") # Clear the DEEPL_API_KEY value
         else: # If the line does not contain the DEEPL_API_KEY
            f.write(line) # Write the line as is

   return False # .env was created

def get_api_key():
   """
   Loads environment variables from a .env file and retrieves the DeepL API key.

   :return: DeepL API key as a string
   """

   verbose_output(f"{BackgroundColors.GREEN}Loading environment variables from {BackgroundColors.CYAN}.env{BackgroundColors.GREEN} file...{Style.RESET_ALL}") # Output the verbose message

   global DEEPL_API_KEY # Use the global DEEPL_API_KEY variable

   load_dotenv() # Load environment variables from .env file
   DEEPL_API_KEY = os.getenv("DEEPL_API_KEY") # Get DeepL API key from environment variables

   if not DEEPL_API_KEY: # If the DeepL API key is not found
      return False # Return False
   return True # Return True

def verify_filepath_exists(filepath):
   """
   Verify if a file or folder exists at the specified path.

   :param filepath: Path to the file or folder
   :return: True if the file or folder exists, False otherwise
   """

   verbose_output(f"{BackgroundColors.GREEN}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}") # Output the verbose message

   return os.path.exists(filepath) # Return True if the file or folder exists, False otherwise

def read_srt(file_path):
   """
   Reads the SRT file into a list of lines.

   :param file_path: Path to the SRT file
   :return: List of strings representing each line
   """

   verbose_output(f"Reading SRT file from: {file_path}") # Output the verbose message

   with open(file_path, "r", encoding="utf-8") as f: # Open the SRT file for reading
      return f.readlines() # Read all lines and return as a list

def remove_descriptive_subtitles(file_path):
   """
   Removes descriptive lines from the SRT file, such as text within brackets or parentheses.
   Overwrites the original SRT file with cleaned lines.
   These cleaned lines are used for translation.

   :param file_path: Path to the SRT file
   :return: List of cleaned lines
   """

   verbose_output(f"{BackgroundColors.GREEN}Removing descriptive subtitles from: {BackgroundColors.CYAN}{file_path}{Style.RESET_ALL}") # Verbose message

   cleaned_lines = [] # Store cleaned lines

   with open(file_path, "r", encoding="utf-8") as f: # Open SRT for reading
      for line in f: # Iterate through each line
         stripped = line.strip() # Remove leading/trailing whitespace

         if stripped == "" or stripped.replace(":", "").replace(",", "").isdigit() or "-->" in line: # If line is empty, timing, or index
            cleaned_lines.append(line.rstrip("\n")) # Keep timing/index/empty lines as is
            continue # Skip further checks

         if stripped.startswith("[") and stripped.endswith("]"): # If line is descriptive (in brackets)
            continue # Skip descriptive lines
         if stripped.startswith("(") and stripped.endswith(")"): # If line is descriptive (in parentheses)
            continue # Skip descriptive lines
         
         cleaned_lines.append(stripped) # Keep normal text lines

   with open(file_path, "w", encoding="utf-8") as f: # Open SRT for writing
      f.write("\n".join(cleaned_lines)) # Overwrite SRT with cleaned lines

   return cleaned_lines # Return cleaned lines for translation

def get_remaining_characters(translator):
   """
   Checks remaining characters available in DeepL free API plan.

   :param translator: DeepL translator client
   :return: Number of remaining characters or None if unlimited/unknown
   """

   verbose_output(f"{BackgroundColors.GREEN}Checking remaining characters in DeepL API...{Style.RESET_ALL}") # Output the verbose message

   usage = translator.get_usage() # Get usage information from DeepL API

   if usage.character.valid: # If character usage information is valid
      remaining = usage.character.limit - usage.character.count # Calculate remaining characters
      return remaining # Return remaining characters

   return None # Return None if unlimited/unknown

def translate_text_block(text_block, translator):
   """
   Translates a block of text using the DeepL API, respecting remaining characters limit.

   :param text_block: String containing multiple lines to translate
   :param translator: DeepLClient instance
   :return: List of translated lines or original lines if limit exceeded
   """

   verbose_output(f"{BackgroundColors.GREEN}Translating text block...{Style.RESET_ALL}") # Output the verbose message

   remaining_chars = get_remaining_characters(translator) # Check remaining characters

   if remaining_chars is not None: # If there is a limit on remaining characters
      print(f"{BackgroundColors.GREEN}Current remaining characters in DeepL API: {BackgroundColors.CYAN}{remaining_chars}{BackgroundColors.GREEN} characters{Style.RESET_ALL}") # Output remaining characters
      if len(text_block) > remaining_chars: # Exceeding limit
         print(f"{BackgroundColors.YELLOW}Warning: Translation limit would be exceeded. Current block size: {BackgroundColors.CYAN}{len(text_block)}{BackgroundColors.YELLOW}. Exceeding limit by: {BackgroundColors.CYAN}{len(text_block) - remaining_chars}{BackgroundColors.YELLOW} characters. Skipping translation for this block.{Style.RESET_ALL}") # Output warning message
         return text_block.split("\n") # Return original lines
   else: # Perform translation
      result = translator.translate_text(text_block, source_lang="EN", target_lang="PT-BR") # Translate text block
      return result.text.split("\n") # Return translated lines

def translate_srt_lines(lines):
   """
   Translates lines from an SRT file using DeepL API.
   Timing and index lines remain unchanged.

   :param lines: List of SRT lines
   :return: List of translated lines
   """

   verbose_output(f"{BackgroundColors.GREEN}Translating SRT lines...{Style.RESET_ALL}") # Output the verbose message
   
   translator = deepl.DeepLClient(auth_key=DEEPL_API_KEY) # Create a DeepL client
   translated_lines = [] # List to store translated lines
   buffer = [] # Buffer to store text lines for translation

   for line in lines: # Iterate through each line in the SRT file
      stripped = line.strip() # Remove leading and trailing whitespace

      if stripped == "" or stripped.replace(":", "").replace(",", "").isdigit() or "-->" in line: # If line is empty, timing, or index
         if buffer: # If buffer contains text to translate
            translated_lines.extend(translate_text_block("\n".join(buffer), translator)) # Translate buffer
            buffer = [] # Clear buffer
            translated_lines.append(line.rstrip("\n")) # Keep timing/index/empty line as is
      else: # Line is text to be translated
         buffer.append(stripped) # Add line to buffer

   if buffer: # Translate any remaining text in buffer
      translated_lines.extend(translate_text_block("\n".join(buffer), translator))

   return translated_lines # Return all translated lines

def save_srt(lines, output_file):
   """
   Saves translated lines to an output SRT file.

   :param lines: List of translated lines
   :param output_file: Path to save the output SRT
   :return: None
   """

   with open(output_file, "w", encoding="utf-8") as f: # Open the output SRT file for writing
      f.write("\n".join(lines)) # Write translated lines to the file

   print(f"{BackgroundColors.GREEN}Translated SRT saved as: {BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}") # Output the saved file message

def calculate_execution_time(start_time, finish_time):
   """
   Calculates the execution time between start and finish times and formats it as hh:mm:ss.

   :param start_time: The start datetime object
   :param finish_time: The finish datetime object
   :return: String formatted as hh:mm:ss representing the execution time
   """

   delta = finish_time - start_time # Calculate the time difference

   hours, remainder = divmod(delta.seconds, 3600) # Calculate the hours, minutes and seconds
   minutes, seconds = divmod(remainder, 60) # Calculate the minutes and seconds

   return f"{hours:02d}:{minutes:02d}:{seconds:02d}" # Format the execution time

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

   Processes all .srt files in the INPUT_DIR. Each file is translated using DeepL API
   from English to Brazilian Portuguese. Translated files are saved in the same directory
   with '_ptBR' appended to the filename.

   :param: None
   :return: None
   """

   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Subtitle (SRT) translation using DeepL API{BackgroundColors.GREEN} program!{Style.RESET_ALL}\n") # Output the welcome message
   start_time = datetime.datetime.now() # Get the start time of the program
   
   ensure_env_file() # Ensure .env file exists
   
   if not get_api_key(): # Load .env and get DeepL API key
      print(f"{BackgroundColors.RED}DEEPL_API_KEY not found in .env file. Please set it before running the program.{Style.RESET_ALL}") # Output error message
      return # Exit the program

   if not os.path.exists(INPUT_DIR): # If the input directory does not exist
      os.makedirs(INPUT_DIR) # Create the input directory
      print(f"Input directory does not exist: {INPUT_DIR}") # Output the error message
      return # Exit the program
   
   if not os.path.exists(OUTPUT_DIR): # If the output directory does not exist
      os.makedirs(OUTPUT_DIR) # Create the output directory

   srt_files = [f for f in Path(INPUT_DIR).glob("*.srt") if f.is_file()] # List of SRT file paths

   if not srt_files: # If no SRT files were found
      print(f"No .srt files found in directory: {INPUT_DIR}") # Output message
      return # Exit the program

   with tqdm(srt_files, desc=f"{BackgroundColors.GREEN}Translating SRT files", unit="file") as progress_bar: # Progress bar for SRT files
      for srt_file in progress_bar: # Iterate through each SRT file
         progress_bar.set_description(f"{BackgroundColors.GREEN}Processing: {BackgroundColors.CYAN}{srt_file.name}{BackgroundColors.GREEN}")
      
         srt_lines = read_srt(srt_file) # Read SRT
         
         if DESCRIPTIVE_SUBTITLES_REMOVAL: # Remove descriptive subtitles if enabled
            srt_lines = remove_descriptive_subtitles(srt_file) # Clean SRT lines
         
         translated_lines = translate_srt_lines(srt_lines) # Translate
         
         relative_path = srt_file.relative_to(INPUT_DIR).parent # Get relative path
         output_subdir = OUTPUT_DIR / relative_path # Create output subdirectory path
         output_subdir.mkdir(parents=True, exist_ok=True) # Ensure output subdir exists
         
         output_file = output_subdir / f"{srt_file.stem}_ptBR.srt" # Build output file path
         save_srt(translated_lines, output_file) # Save translated SRT

   finish_time = datetime.datetime.now() # Get the finish time of the program
   print(f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}") # Output start, finish, and execution times
   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output end of program message

   atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None # Register the play_sound function to be called when the program finishes

if __name__ == "__main__":
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """

   main() # Call the main function
