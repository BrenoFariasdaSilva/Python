import atexit # For playing a sound when the program finishes
import json # For saving the songs as a JSON file
import os # For running a command in the terminal
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

# Directories Constants:
INPUT_DIRECTORY = f"./Inputs" # Input directory

# Filepath Constants:
MUSIC_DIRECTORY = f"D:\\Backup\\Box Sync\\My Musics" # The directory containing the music files
LOCAL_SONGS_FILE = f"{INPUT_DIRECTORY}/local_songs.json" # Local songs JSON file

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

def get_artist_name_from_path(relative_path):
   """
   Extract the artist name from the relative path.

   :param relative_path: The relative path from the base music directory
   :return: The artist/band name
   """

   artist_name = relative_path.split(os.sep)[0].strip() # Get the artist name from the relative path
   return artist_name if artist_name else None # Return the artist name if it exists, None otherwise

def is_music_file(file):
   """
   Check if the file is a valid music file based on its extension.

   :param file: The file name
   :return: True if the file is a music file, False otherwise
   """

   return file.lower().endswith((".mp3", ".flac", ".wav", ".aac", ".m4a"))

def scan_music_directory(music_dir):
   """
   Scan the directory and yield artist names and their songs.

   :param music_dir: The directory containing the music files
   :yield: Tuple of artist name and song name
   """

   verbose_output(f"{BackgroundColors.GREEN}Scanning directory: {BackgroundColors.CYAN}{music_dir}{Style.RESET_ALL}")

   for root, _, files in os.walk(music_dir): # Walk through the directory
      relative_path = os.path.relpath(root, music_dir) # Get the relative path from the base music directory
      artist_name = get_artist_name_from_path(relative_path) # Get the artist name from the relative path
      
      if not artist_name: # Skip if no valid artist name
         continue # Skip the iteration
      
      for file in files: # Iterate through the files
         if is_music_file(file): # If the file is a music file
            song_name, _ = os.path.splitext(file) # Remove file extension
            yield artist_name, song_name.strip() # Yield the artist name and song name

def organize_songs_by_artist(music_dir):
   """
   Organize songs by artist/band name from the given music directory.

   :param music_dir: The directory containing the music files
   :return: Dictionary of songs organized by artist
   """

   verbose_output(f"{BackgroundColors.GREEN}Organizing songs by artist...{Style.RESET_ALL}")

   songs_by_artist = {} # Initialize the dictionary to store songs by artist

   for artist, song in scan_music_directory(music_dir): # Iterate through the artists and songs
      if artist not in songs_by_artist: # If the artist is not in the dictionary
         songs_by_artist[artist] = set() # Initialize the set for the artist
      songs_by_artist[artist].add(song) # Add the song to the artist's set
   
   songs_by_artist = {artist: sorted(list(songs)) for artist, songs in songs_by_artist.items()} # Sort the songs by artist
   
   return songs_by_artist # Return the songs organized by artist

def save_songs_to_file(songs_by_artist, output_file):
   """
   Save the organized songs to a JSON file.

   :param songs_by_artist: The dictionary containing songs organized by artist
   :param output_file: The file path to save the JSON data
   :return: None
   """

   with open(output_file, "w", encoding="utf-8") as f: # Open the output file
      json.dump(songs_by_artist, f, indent=4, ensure_ascii=False) # Save the songs as JSON

def get_local_songs(music_dir=MUSIC_DIRECTORY, output_file=LOCAL_SONGS_FILE):
   """
   Scans the given directory and organizes songs by artist/band name with a progress bar.

   :param music_dir: The directory containing the music files
   :param output_file: The output file to save the songs in JSON format
   :return: None
   """

   verbose_output(f"{BackgroundColors.GREEN}Scanning directory: {BackgroundColors.CYAN}{music_dir}{Style.RESET_ALL}")
   
   songs_by_artist = organize_songs_by_artist(music_dir) # Scan and organize songs by artist
   
   if songs_by_artist: # If the songs by artist dictionary is not empty
      os.makedirs(INPUT_DIRECTORY, exist_ok=True) # Create the directory if it does not exist
      save_songs_to_file(songs_by_artist, output_file) # Save the results to the output file
   
   total_song_count = sum(len(songs) for songs in songs_by_artist.values()) # Calculate the total number of songs
   
   print(f"{BackgroundColors.GREEN}Total songs found: {BackgroundColors.CYAN}{total_song_count}{Style.RESET_ALL}")

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

   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Local Songs{BackgroundColors.GREEN} program!{Style.RESET_ALL}", end="\n\n") # Output the Welcome message

   get_local_songs(MUSIC_DIRECTORY, LOCAL_SONGS_FILE) # Get the local songs

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output the end of the program message

   atexit.register(play_sound) # Register the function to play a sound when the program finishes

if __name__ == "__main__":
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """

   main() # Call the main function
