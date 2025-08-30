import atexit # For playing a sound when the program finishes
import os # For running a command in the terminal
import platform # For getting the operating system name
import pyheif # For reading HEIC files
from colorama import Style # For coloring the terminal
from PIL import Image # For reading and writing images

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
OUTPUT_FILE_EXTENSION = ".png" # The output file extension to save as

# Path Constants:
START_PATH = os.getcwd() # The path where the program is executed
RELATIVE_INPUT_FOLDER = "Inputs" # The relative path to the input folder
RELATIVE_OUTPUT_FOLDER = "Outputs" # The relative path to the output folder
FULL_INPUT_FOLDER = os.path.join(START_PATH, RELATIVE_INPUT_FOLDER) # The full path to the input folder
FULL_OUTPUT_FOLDER = os.path.join(START_PATH, RELATIVE_OUTPUT_FOLDER) # The full path to the output folder

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

def create_directory(full_directory_name, relative_directory_name):
   """
   Creates a directory.

   :param full_directory_name: Name of the directory to be created.
   :param relative_directory_name: Relative name of the directory to be created that will be shown in the terminal.
   :return: None
   """

   verbose_output(true_string=f"{BackgroundColors.GREEN}Creating the {BackgroundColors.CYAN}{relative_directory_name}{BackgroundColors.GREEN} directory...{Style.RESET_ALL}")

   if os.path.isdir(full_directory_name): # Verify if the directory already exists
      return # Return if the directory already exists
   try: # Try to create the directory
      os.makedirs(full_directory_name) # Create the directory
   except OSError: # If the directory cannot be created
      print(f"{BackgroundColors.GREEN}The creation of the {BackgroundColors.CYAN}{relative_directory_name}{BackgroundColors.GREEN} directory failed.{Style.RESET_ALL}")

def convert_heic_to_specified_format(input_folder=FULL_INPUT_FOLDER, output_folder=FULL_OUTPUT_FOLDER, file_extension=OUTPUT_FILE_EXTENSION):
   """
   Converts HEIC files to the specified target format (e.g., PNG, JPEG).

   :param input_folder: The folder containing the HEIC files.
   :param output_folder: The folder to save the converted files.
   :param target_format: The target image format (e.g., "PNG", "JPEG").
   :return: Number of files converted.
   """

   verbose_output(f"{BackgroundColors.YELLOW}Converting HEIC files to PNG files in the folder: {BackgroundColors.CYAN}{input_folder}{Style.RESET_ALL}") # Output the verbose message

   file_count = 0 # The number of files converted

   for filename in os.listdir(input_folder): # For each file in the input folder
      if filename.lower().endswith(".heic"): # If the file is a HEIC file
         file_count += 1 # Increment the file count
         print(f"{BackgroundColors.GREEN}{file_count:.02d} - Converting {BackgroundColors.CYAN}{filename}{BackgroundColors.GREEN} to a PNG file...{Style.RESET_ALL}") # Output the message
         heif_file = pyheif.read(os.path.join(input_folder, filename)) # Read the HEIC file
         image = Image.frombytes( # Create an image from the HEIC file
            heif_file.mode, # The mode of the image
            heif_file.size, # The size of the image
            heif_file.data, # The data of the image
            "raw", # The raw mode
            heif_file.mode, # The mode of the image
            heif_file.stride, # The stride of the image
         )
         output_path = os.path.join(output_folder, f"{os.path.splitext(filename)[0]}.{file_extension.lower()}") # The path to save the converted file
         image.save(output_path, file_extension.lower()) # Save the image in the specified format

   return file_count # Return the number of files converted

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

   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CLEAR_TERMINAL}HEIC to PNG Converter{BackgroundColors.GREEN}!{Style.RESET_ALL}", end="\n\n") # Output the welcome message

   create_directory(FULL_INPUT_FOLDER, RELATIVE_INPUT_FOLDER) # Create the input directory
   create_directory(FULL_OUTPUT_FOLDER, RELATIVE_OUTPUT_FOLDER) # Create the output directory
   converted_files_count = convert_heic_to_specified_format(FULL_INPUT_FOLDER, FULL_OUTPUT_FOLDER, OUTPUT_FILE_EXTENSION) # Convert the HEIC files to the specified

   if converted_files_count == 0: # If no files were converted
      print(f"{BackgroundColors.RED}No HEIC files found in the folder: {BackgroundColors.CYAN}{RELATIVE_INPUT_FOLDER}{Style.RESET_ALL}")
   else: # If files were converted
      print(f"{BackgroundColors.GREEN}Successfully converted {converted_files_count} HEIC file(s) to {OUTPUT_FILE_EXTENSION.lower()} format.{Style.RESET_ALL}")

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output the end of the program message

   atexit.register(play_sound) # Register the function to play a sound when the program finishes

if __name__ == "__main__":
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """

   main() # Call the main function
