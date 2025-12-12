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

def get_commits_information(repo_url):
   """
   Generates a CSV file with commit dates and messages in a GitHub repository.

   :param repo_url: URL of the GitHub repository
   :return: list of tuples with commit dates and messages
   """

   commits_list = [] # List to store the commit dates, messages and files changed
   for index, commit in enumerate(Repository(path_to_repo=repo_url).traverse_commits()): # Iterate over the commits
      commit_date = commit.committer_date.strftime("%Y-%m-%d %H:%M:%S") # Get the commit date
      files_changed = [] # List to store modified file paths for this commit
      for mf in commit.modified_files: # Iterate over modified files for this commit
         path = mf.new_path if getattr(mf, "new_path", None) else getattr(mf, "old_path", None) # Prefer new_path, fall back to old_path
         if path: # If a path exists, add it to the list
            files_changed.append(path) # Append the file path to the list
      files_changed_str = "; ".join(files_changed) # Join file paths into a single string separated by semicolons
      commits_list.append((index + 1, commit.hash, commit_date, commit.msg, files_changed_str)) # Append index, hash, date, message and files changed to the list

   return commits_list # Return the list of tuples with commit dates, messages and files changed

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
      fieldnames = ["Commit Number", "Commit Hash", "Commit Date", "Commit Message", "Files Changed"] # CSV header (added Files Changed)
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
      fieldnames = ["Commit Number", "Commit Hash", "Commit Date", "Commit Message", "Files Changed"] # CSV header (added Files Changed)
      writer = csv.DictWriter(csv_file, fieldnames=fieldnames) # Create a CSV writer
      for commit in commits_list: # Iterate over the commits list
         writer.writerow({ # Write a row to the CSV file
            "Commit Number": commit[0], # Commit Number
            "Commit Hash": commit[1], # Commit Hash
            "Commit Date": commit[2], # Commit Date
            "Commit Message": commit[3], # Commit Message
            "Files Changed": commit[4] if len(commit) > 4 else "", # Include files changed if available
         })

def main():
   """
   Main function to generate the CSV for the repository.
   :return: None
   """

   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Commits List from Repository{BackgroundColors.GREEN}!{Style.RESET_ALL}")

   repo_url = "https://github.com/BrenoFariasdaSilva/DDoS-Detector" # The URL of the GitHub repository
   repo_name = repo_url.split("/")[-1] # Get the repository name

   print(f"{BackgroundColors.GREEN}Generating commits list for the repository {BackgroundColors.CYAN}{repo_name}{BackgroundColors.GREEN} in a CSV File...{Style.RESET_ALL}")
   
   commits_tuple_list = get_commits_information(repo_url) # Get the commits information
   create_directory(FULL_OUTPUT_DIRECTORY_PATH, RELATIVE_OUTPUT_DIRECTORY_PATH) # Create the output directory
   output_csv = f"{RELATIVE_OUTPUT_DIRECTORY_PATH}{repo_name}-commits_list.csv" # The output CSV file path
   write_commits_to_csv(commits_tuple_list, output_csv) # Generate the CSV file

   print(f"{BackgroundColors.CYAN}Program finished.{Style.RESET_ALL}")

if __name__ == "__main__":
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """

   main() # Call the main function
