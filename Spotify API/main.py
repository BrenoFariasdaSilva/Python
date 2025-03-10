import atexit # For playing a sound when the program finishes
import json # For JSON operations
import os # For running a command in the terminal
import platform # For getting the operating system name
import re # For regular expressions
import string # For string operations
import unicodedata # For normalizing text
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

# Directories Constants:
INPUT_DIRECTORY = f"./Inputs" # Input directory
OUTPUT_DIRECTORY = f"./Outputs" # Output directory

# Filepath Constants:
SPOTIFY_LIKED_SONGS = f"{INPUT_DIRECTORY}/spotify_liked_songs.json" # Spotify liked songs JSON file
LOCAL_SONGS = f"{INPUT_DIRECTORY}/local_songs.json" # Local songs JSON file
LOCAL_SONGS_NOT_IN_SPOTIFY = f"{OUTPUT_DIRECTORY}/local_not_in_spotify.txt" # Local songs not in Spotify text file
SPOTIFY_SONGS_NOT_IN_LOCAL = f"{OUTPUT_DIRECTORY}/spotify_not_in_local.txt" # Spotify songs not in local text file

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

   verbose_output(f"{BackgroundColors.YELLOW}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}") # Output the verbose message

   return os.path.exists(filepath) # Return True if the file or folder exists, False otherwise

def create_directory(directory):
   """
   Create a directory if it does not exist.

   :param directory: Directory to create
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Creating the directory: {BackgroundColors.CYAN}{directory}{Style.RESET_ALL}") # Output the verbose message

   if not os.path.exists(directory): # If the directory does not exist
      os.makedirs(directory) # Create the directory

def normalize(text):
   """
   Normalize text: lowercase, remove accents, replace dashes/underscores, remove punctuation.

   :param text: Text to normalize
   :return: Normalized text
   """

   verbose_output(f"{BackgroundColors.GREEN}Normalizing the text: {BackgroundColors.CYAN}{text}{Style.RESET_ALL}") # Output the verbose message

   text = text.lower() # Lowercase the text
   text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8") # Remove accents
   text = re.sub(r"[-_]+", " ", text) # Replace - and _ with space 
   text = text.translate(str.maketrans("", "", string.punctuation)) # Remove punctuation

   return text.strip() # Return the normalized text

def load_json(filename):
   """
   Load JSON file and normalize keys and values.

   :param filename: JSON file to load
   :return: Dictionary with normalized keys and values
   """

   verbose_output(f"{BackgroundColors.GREEN}Loading the JSON file: {BackgroundColors.CYAN}{filename}{Style.RESET_ALL}") # Output the verbose message

   try: # Try to load the JSON file
      with open(filename, "r", encoding="utf-8") as f: # Open the JSON file
         data = json.load(f) # Load the JSON data
      return {normalize(artist): {normalize(song) for song in songs} for artist, songs in data.items()} # Normalize the keys and values
   except FileNotFoundError: # If the file is not found
      print(f"{BackgroundColors.RED}File not found: {BackgroundColors.CYAN}{filename}{Style.RESET_ALL}")
      return {} # Return an empty dictionary

def songs_in_first_not_in_second(first, second):
   """
   Find songs in the first dictionary that are not in the second dictionary.

   :param first: First dictionary
   :param second: Second dictionary
   :return: Set of songs in the first dictionary that are not in the second dictionary
   """

   verbose_output(f"{BackgroundColors.GREEN}Finding songs in the first dictionary that are not in the second dictionary.{Style.RESET_ALL}") # Output the verbose message

   return {f"{artist} - {song}" for artist, songs in first.items() for song in songs if artist not in second or song not in second[artist]} # Return the set of songs in the first dictionary that are not in the second dictionary

def write_to_file(filename, data):
   """
   Write data to a file.

   :param filename: File to write to
   :param data: Data to write
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Writing data to the file: {BackgroundColors.CYAN}{filename}{Style.RESET_ALL}") # Output the verbose message

   with open(filename, "w", encoding="utf-8") as f: # Open the file to write
      f.write(data) # Write the data to the file

def compare_songs(spotify_file=SPOTIFY_LIKED_SONGS, local_file=LOCAL_SONGS):
   """
   Compare Spotify liked songs with local songs and generate difference reports.

   :param spotify_file: Spotify liked songs JSON file
   :param local_file: Local songs JSON file
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Comparing Spotify liked songs with local songs.{Style.RESET_ALL}") # Output the verbose message

   spotify_songs = load_json(spotify_file) # Load Spotify liked songs
   local_songs = load_json(local_file) # Load local songs
   
   local_not_in_spotify = set() # Songs in local that are not in Spotify
   spotify_not_in_local = set() # Songs in Spotify that are not in local
   
   local_not_in_spotify = songs_in_first_not_in_second(local_songs, spotify_songs) # Find songs in local that are not in Spotify
   spotify_not_in_local = songs_in_first_not_in_second(spotify_songs, local_songs) # Find songs in Spotify that are not in local
   
   write_to_file(LOCAL_SONGS_NOT_IN_SPOTIFY, "\n".join(local_not_in_spotify)) # Write songs in local that are not in Spotify to a file
   write_to_file(SPOTIFY_SONGS_NOT_IN_LOCAL, "\n".join(spotify_not_in_local)) # Write songs in Spotify that are not in local to a file
   
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

   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Spotify API{BackgroundColors.GREEN} program!{Style.RESET_ALL}") # Output the welcome message

   create_directory(INPUT_DIRECTORY) # Create the input directory
   create_directory(OUTPUT_DIRECTORY) # Create the output directory
   
   compare_songs(SPOTIFY_LIKED_SONGS, LOCAL_SONGS) # Compare Spotify liked songs with local songs

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output the end of the program message

   atexit.register(play_sound) # Register the function to play a sound when the program finishes

if __name__ == "__main__":
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """

   main() # Call the main function
