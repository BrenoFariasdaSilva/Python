import atexit # For playing a sound when the program finishes
import csv # For writing to a CSV file
import os # For running a command in the terminal
import platform # For getting the operating system name
import re # For regular expressions
import subprocess # For running git commands
from colorama import Style # For coloring the terminal
from pydriller import Repository # PyDriller is a Python framework that helps developers in analyzing Git repositories.

# Execution Constant:
REPO_URL = "https://github.com/BrenoFariasdaSilva/DDoS-Detector" # The URL of the GitHub repository
SPLIT_ALL = True # If both tags are empty and SPLIT_ALL == True, split by all tags instead of single run

# Filepaths Constants:
START_PATH = os.getcwd() # Get the current working directory
RELATIVE_OUTPUT_DIRECTORY_PATH = "Output/" # The output directory path
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

def verify_git_installed():
   """
   Verifies if git is installed on the system.

   :return: True if git is installed, False otherwise
   """
   try:
      proc = subprocess.run(["git", "--version"], capture_output=True, text=True, check=False) # Run the git command

      if proc.returncode != 0: # Check if the git command was successful
         return False # Git is not installed

      return True # Git is installed

   except Exception: # If an error occurs during the process
      return False # Git is not installed

def _tag_sort_key(t):
   """
   Key function for sorting tags in a human-friendly way.
   
   :param t: Tag name
   :return: List of strings and integers for sorting
   """
   
   parts = re.split(r"(\d+)", t) # Split the tag into parts of digits and non-digits
   return [int(p) if p.isdigit() else p.lower() for p in parts] # Convert digit parts to integers for proper sorting

def get_repository_tags(repo_url):
   """
   Retrieves all tag names from a remote Git repository using native git commands.

   :param repo_url: URL of the Git repository
   :return: list of tag names
   """
   
   if not verify_git_installed(): # Verify if git is installed
      print(f"{BackgroundColors.RED}Git is not installed on this system. Please install Git to retrieve repository tags.{Style.RESET_ALL}")
      exit(1) # Exit the program
   
   tags_list = [] # List to store the tag names

   try: # Try to retrieve the tags using git ls-remote
      proc = subprocess.run(["git", "ls-remote", "--tags", repo_url], capture_output=True, text=True, check=False) # Run the git command

      if proc.returncode != 0: # Check if the git command was successful
         raise RuntimeError(proc.stderr.strip() or f"git exited with code {proc.returncode}") # Raise an error if the command failed

      lines = proc.stdout.splitlines() # Split the output into lines
      extracted = [] # Temporary list to store extracted tag names
      
      for line in lines: # Iterate over each line of the output
         if not line.strip(): # Skip empty lines
            continue # Continue to the next line
         
         parts = line.split() # Split the line into parts
         if len(parts) < 2: # Ensure there are at least two parts
            continue # Skip lines that don't have enough parts
         
         ref = parts[1] # Get the reference part
         if ref.startswith("refs/tags/"): # Check if the reference is a tag
            tag_part = ref[len("refs/tags/"):] # Extract the tag name
            
            if tag_part.endswith("^{}"): # Handle annotated tags
               tag_part = tag_part[:-3] # Remove the ^{} suffix
               
            extracted.append(tag_part) # Add the tag name to the temporary list

      seen = {} # Dictionary to track seen tags
      for t in extracted: # Iterate over the extracted tag names
         if t not in seen: # If the tag has not been seen yet
            seen[t] = True # Mark the tag as seen
            tags_list.append(t) # Add the tag name to the final list

   except Exception as e: # If an error occurs during the process
      print(f"{BackgroundColors.RED}Failed to retrieve tags: {BackgroundColors.CYAN}{e}{Style.RESET_ALL}")

   tags_list = sorted(tags_list, key=_tag_sort_key) # Sort tags from lowest → highest

   return tags_list # Return the list of tag names

def get_commits_information(repo_url, from_tag=None, to_tag=None):
   """
   Generates a CSV file with commit dates and messages between specific tags in a GitHub repository.

   :param repo_url: URL of the GitHub repository
   :param from_tag: The starting tag
   :param to_tag: The ending tag
   :return: list of tuples with commit dates and messages
   """

   from_tag = None if from_tag in ("", None) else from_tag # Normalize the starting tag
   to_tag = None if to_tag in ("", None) else to_tag # Normalize the ending tag

   if from_tag is None and to_tag is None: # Check if both tags are missing
      repo = Repository(path_to_repo=repo_url) # Analyze entire repository
   elif from_tag is None and to_tag is not None: # Check if only to_tag exists
      repo = Repository(path_to_repo=repo_url, to_tag=to_tag) # Analyze from beginning to to_tag
   elif from_tag is not None and to_tag is None: # Check if only from_tag exists
      repo = Repository(path_to_repo=repo_url, from_tag=from_tag) # Analyze from from_tag to HEAD
   else: # Both tags exist
      repo = Repository(path_to_repo=repo_url, from_tag=from_tag, to_tag=to_tag) # Analyze between both tags

   commits_list = [] # List to store the commit dates and messages

   for index, commit in enumerate(repo.traverse_commits()): # Iterate over the commits
      commit_date = commit.committer_date.strftime("%Y-%m-%d %H:%M:%S") # Format the commit date
      commits_list.append((index + 1, commit.hash, commit_date, commit.msg)) # Append commit data to the list

   return commits_list # Return the list of commit tuples

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

def process_all_splits(repo_url, repo_name):
   """
   Handles the SPLIT_ALL feature:
   Retrieves tags, builds ranges, runs analysis, writes separate CSV files.
   """

   print(f"{BackgroundColors.CYAN}SPLIT_ALL{BackgroundColors.GREEN} is enabled. Fetching repository tags...{Style.RESET_ALL}")
   
   tags = get_repository_tags(repo_url) # Retrieve all tags from the repository

   if not tags: # If no tags are found
      print(f"{BackgroundColors.RED}No tags found. Cannot perform SPLIT_ALL.{Style.RESET_ALL}")
      return # Exit the function

   print(f"{BackgroundColors.GREEN}Found {BackgroundColors.CYAN}{len(tags)}{BackgroundColors.GREEN} tags. Generating split CSVs...{Style.RESET_ALL}\n")

   segments = [] # List to store the tag segments
   previous = None # Initialize the previous tag as None

   for tag in tags: # Iterate over each tag
      segments.append((previous, tag)) # Append the segment (previous_tag, current_tag)
      previous = tag # Update the previous tag to the current tag

   segments.append((previous, None)) # Last_tag → HEAD

   total_segments = len(segments) # Total number of segments
   width = max(2, len(str(total_segments))) # Minimum 2 digits of padding

   create_directory(FULL_OUTPUT_DIRECTORY_PATH, RELATIVE_OUTPUT_DIRECTORY_PATH) # Create the output directory

   for index, (from_tag, to_tag) in enumerate(segments, start=1): # Iterate over each segment
      label_from = from_tag if from_tag is not None else "start" # Label for the starting tag
      label_to = to_tag if to_tag is not None else "HEAD" # Label for the ending tag

      print(f"{BackgroundColors.GREEN}Processing split {BackgroundColors.CYAN}{index}{BackgroundColors.GREEN}: {BackgroundColors.CYAN}{label_from}{BackgroundColors.GREEN} to {BackgroundColors.CYAN}{label_to}{Style.RESET_ALL}")

      commits_tuple_list = get_commits_information(repo_url, from_tag, to_tag) # Get the commits information for the segment

      output_csv = f"{RELATIVE_OUTPUT_DIRECTORY_PATH}{index:0{width}d}.{repo_name}-{label_from}_to_{label_to}-commits_list.csv" # The output CSV file path for the segment
      write_commits_to_csv(commits_tuple_list, output_csv) # Generate the CSV file for the segment

   print(f"\n{BackgroundColors.GREEN}All SPLIT_ALL CSV files generated successfully.{Style.RESET_ALL}")

def main():
   """
   Main function to generate the CSV for the repository.
   :return: None
   """

   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Commits List Between Tags Generator{BackgroundColors.GREEN}!{Style.RESET_ALL}")
   print(f"{BackgroundColors.GREEN}If you don't have the repository tags, you can generate them using the {BackgroundColors.CYAN}Repository Tags Lister{BackgroundColors.GREEN} program.{Style.RESET_ALL}\n")
   
   repo_url = REPO_URL # The URL of the GitHub repository
   repo_name = repo_url.split("/")[-1] # Get the repository name
   
   from_tag = "" # The starting tag. if set to None or "", it will start from the beginning
   to_tag = "" # The ending tag. if set to None or "", it will go until the latest commit

   if (from_tag in ("", None)) and (to_tag in ("", None)) and SPLIT_ALL: # If both tags are missing and SPLIT_ALL is enabled
      process_all_splits(repo_url, repo_name) # Process all splits
      print(f"\n{BackgroundColors.CYAN}Program finished.{Style.RESET_ALL}") # Indicate program completion
      return # Exit the main function

   print(f"{BackgroundColors.GREEN}Generating commit CSV from {BackgroundColors.CYAN}{from_tag}{BackgroundColors.GREEN} to {BackgroundColors.CYAN}{to_tag}{BackgroundColors.GREEN} for the repository {BackgroundColors.CYAN}{repo_name}{BackgroundColors.GREEN}...{Style.RESET_ALL}")
   
   commits_tuple_list = get_commits_information(repo_url, from_tag, to_tag) # Get the commits information
   create_directory(FULL_OUTPUT_DIRECTORY_PATH, RELATIVE_OUTPUT_DIRECTORY_PATH) # Create the output directory
   output_csv = f"{RELATIVE_OUTPUT_DIRECTORY_PATH}{repo_name}-{from_tag}_to_{to_tag}-commits_list.csv" # The output CSV file path
   write_commits_to_csv(commits_tuple_list, output_csv) # Generate the CSV file

   print(f"\n{BackgroundColors.CYAN}Program finished.{Style.RESET_ALL}")

if __name__ == "__main__":
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """

   main() # Call the main function
