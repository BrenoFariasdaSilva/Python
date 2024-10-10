import atexit # For playing a sound when the program finishes
import os # For running a command in the terminal
import platform # For getting the operating system name
import csv # For writing to a CSV file
from colorama import Style # For coloring the terminal
from pydriller import Repository # PyDriller is a Python framework that helps developers in analyzing Git repositories.

# Filepaths Constants:
START_PATH = os.getcwd() # Get the current working directory
RELATIVE_OUTPUT_DIRECTORY_PATH = "output/" # The output directory path
FULL_OUTPUT_DIRECTORY_PATH = os.path.join(START_PATH, RELATIVE_OUTPUT_DIRECTORY_PATH) # The full output directory path

# Macros:
class BackgroundColors: # Colors for the terminal
   CYAN = "\033[96m" # Cyan
   GREEN = "\033[92m" # Green
   YELLOW = "\033[93m" # Yellow
   RED = "\033[91m" # Red
   BOLD = "\033[1m" # Bold
   UNDERLINE = "\033[4m" # Underline
   CLEAR_TERMINAL = "\033[H\033[J" # Clear the terminal

# Sound Constants:
SOUND_COMMANDS = {"Darwin": "afplay", "Linux": "aplay", "Windows": "start"} # The commands to play a sound for each operating system
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav" # The path to the sound file

def play_sound():
   """
   Plays a sound when the program finishes.
   :return: None
   """
   if os.path.exists(SOUND_FILE):
      if platform.system() in SOUND_COMMANDS: # If the platform.system() is in the SOUND_COMMANDS dictionary
         os.system(f"{SOUND_COMMANDS[platform.system()]} {SOUND_FILE}")
      else: # If the platform.system() is not in the SOUND_COMMANDS dictionary
         print(f"{BackgroundColors.RED}The {BackgroundColors.CYAN}platform.system(){BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}")
   else: # If the sound file does not exist
      print(f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}")

atexit.register(play_sound) # Register the function to play a sound when the program finishes

def get_commits_information(repo_url, from_tag=None, to_tag=None):
   """
   Generates a CSV file with commit dates and messages between specific tags in a GitHub repository.

   :param repo_url: URL of the GitHub repository
   :param from_tag: The starting tag
   :param to_tag: The ending tag
   :return: list of tuples with commit dates and messages
   """

   commits_list = [] # List to store the commit dates and messages
   for index, commit in enumerate(Repository(path_to_repo=repo_url, from_tag=from_tag, to_tag=to_tag).traverse_commits()): # Iterate over the commits
      commit_date = commit.committer_date.strftime("%Y-%m-%d %H:%M:%S") # Get the commit date
      commits_list.append((index + 1, commit.hash, commit_date, commit.msg)) # Append the index, commit date, and message to the list

   return commits_list # Return the list of tuples with commit dates and messages

def create_directory(full_directory_name, relative_directory_name):
   """
   Creates a directory.

   :param full_directory_name: Name of the directory to be created.
   :param relative_directory_name: Relative name of the directory to be created that will be shown in the terminal.
   :return: None
   """

   if os.path.isdir(full_directory_name): # Verify if the directory already exists
      return # Return if the directory already exists
   try: # Try to create the directory
      os.makedirs(full_directory_name) # Create the directory
   except OSError: # If the directory cannot be created
      print(f"{BackgroundColors.GREEN}The creation of the {BackgroundColors.CYAN}{relative_directory_name}{BackgroundColors.GREEN} directory failed.{Style.RESET_ALL}")

def add_header_to_csv(output_csv):
   """
   Adds a header to the CSV file.

   :param output_csv: The output CSV file path
   :return: None
   """

   with open(output_csv, mode="w", newline="") as csv_file: # Open the CSV file in write mode
      fieldnames = ["Commit Number", "Commit Hash", "Commit Date", "Commit Message"] # CSV header
      writer = csv.DictWriter(csv_file, fieldnames=fieldnames) # Create a CSV writer
      writer.writeheader() # Write the header to the CSV

def write_commits_to_csv(commits_list, output_csv):
   """
   Writes the commits list to a CSV file.

   :param commits_list: List of tuples with commit dates and messages
   :param output_csv: The output CSV file path
   :return: None
   """

   add_header_to_csv(output_csv) # Add a header to the CSV file

   with open(output_csv, mode="a", newline="") as csv_file: # Open the CSV file in append mode
      fieldnames = ["Commit Number", "Commit Hash", "Commit Date", "Commit Message"] # CSV header
      writer = csv.DictWriter(csv_file, fieldnames=fieldnames) # Create a CSV writer
      for commit in commits_list: # Iterate over the commits list
         writer.writerow({"Commit Number": commit[0], "Commit Hash": commit[1], "Commit Date": commit[2], "Commit Message": commit[3]})

def main():
   """
   Main function to generate the CSV for the repository.
   :return: None
   """

   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Commits List Between Tags Generator{BackgroundColors.GREEN}!{Style.RESET_ALL}")

   repo_url = "https://github.com/BrenoFariasdaSilva/Worked-Example-Miner" # The URL of the GitHub repository
   repo_name = repo_url.split("/")[-1] # Get the repository name
   from_tag = "v1.0" # The starting tag
   to_tag = "v8.0" # The ending tag

   print(f"{BackgroundColors.GREEN}Generating commit CSV from {BackgroundColors.CYAN}{from_tag}{BackgroundColors.GREEN} to {BackgroundColors.CYAN}{to_tag}{BackgroundColors.GREEN} for the repository {BackgroundColors.CYAN}{repo_name}{BackgroundColors.GREEN}...{Style.RESET_ALL}")
   
   commits_tuple_list = get_commits_information(repo_url, from_tag, to_tag) # Get the commits information
   create_directory(FULL_OUTPUT_DIRECTORY_PATH, RELATIVE_OUTPUT_DIRECTORY_PATH) # Create the output directory
   output_csv = f"{RELATIVE_OUTPUT_DIRECTORY_PATH}{repo_name}-{from_tag}_to_{to_tag}-commits_list.csv" # The output CSV file path
   write_commits_to_csv(commits_tuple_list, output_csv) # Generate the CSV file

   print(f"{BackgroundColors.CYAN}Program finished.{Style.RESET_ALL}")

if __name__ == "__main__":
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """

   main() # Call the main function
