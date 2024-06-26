import atexit # For playing a sound when the program finishes
import csv # CSV (Comma Separated Values) is a simple file format used to store tabular data, such as a spreadsheet or database
import os # OS module in Python provides functions for interacting with the operating system
import pandas as pd # Pandas is a fast, powerful, flexible and easy to use open source data analysis and manipulation tool,
import platform # For getting the operating system name
import subprocess # The subprocess module allows you to spawn new processes, connect to their input/output/error pipes, and obtain their return codes
import threading # The threading module provides a high-level interface for running tasks in separate threads
import time # This module provides various time-related functions
from colorama import Style # For coloring the terminal
from pydriller import Repository # PyDriller is a Python framework that helps developers in analyzing Git repositories. 
from tqdm import tqdm # For Generating the Progress Bars

# Macros:
class BackgroundColors: # Colors for the terminal
   CYAN = "\033[96m" # Cyan
   GREEN = "\033[92m" # Green
   YELLOW = "\033[93m" # Yellow
   RED = "\033[91m" # Red
   BOLD = "\033[1m" # Bold
   UNDERLINE = "\033[4m" # Underline
   CLEAR_TERMINAL = "\033[H\033[J" # Clear the terminal

# Default values that can be changed:
DEFAULT_REPOSITORIES = {"zookeeper": "https://github.com/apache/zookeeper"} # The dicitonary of the repositories to be analyzed (repository name: repository URL)
VERBOSE = False # Verbose mode. If set to True, it will output messages at the start/call of each function (Note: It will output a lot of messages).

# Default paths:
START_PATH = os.getcwd() # Get the current working directory

# Extensions:
CSV_FILE_EXTENSION = ".csv" # The extension of the file that contains the commit hashes
DIFF_FILE_EXTENSION = ".diff" # The diff file extension

# CK Generated Files:
CK_METRICS_FILES = ["class.csv", "method.csv"] # The files that are generated by CK

# Constants:
SOUND_COMMANDS = {"Darwin": "afplay", "Linux": "aplay", "Windows": "start"} # The sound commands for each operating system

# Time units:
TIME_UNITS = [60, 3600, 86400] # Seconds in a minute, seconds in an hour, seconds in a day
 
# Relative paths:
SOUND_FILE = "../.assets/Sounds/NotificationSound.wav" # The path to the sound file
RELATIVE_CK_JAR_PATH = "/ck/ck-0.7.1-SNAPSHOT-jar-with-dependencies.jar" # The relative path of the CK JAR file
RELATIVE_CK_METRICS_DIRECTORY_PATH = "/ck_metrics" # The relative path of the directory that contains the CK generated files
RELATIVE_DIFFS_DIRECTORY_PATH = "/diffs" # The relative path of the directory that contains the diffs
RELATIVE_PROGRESS_DIRECTORY_PATH = "/progress" # The relative path of the progress file
RELATIVE_REFACTORINGS_DIRECTORY_PATH = "/refactorings" # The relative path of the directory that contains the refactorings
RELATIVE_REPOSITORIES_DIRECTORY_PATH = "/repositories" # The relative path of the directory that contains the repositories

# Full paths (Start Path + Relative Paths):
FULL_CK_METRICS_DIRECTORY_PATH = START_PATH + RELATIVE_CK_METRICS_DIRECTORY_PATH # The full path of the directory that contains the CK generated files
FULL_PROGRESS_DIRECTORY_PATH = START_PATH + RELATIVE_PROGRESS_DIRECTORY_PATH # The full path of the progress file
FULL_REFACTORINGS_DIRECTORY_PATH = START_PATH + RELATIVE_REFACTORINGS_DIRECTORY_PATH # The full path of the directory that contains the refactorings
FULL_REPOSITORIES_DIRECTORY_PATH = START_PATH + RELATIVE_REPOSITORIES_DIRECTORY_PATH # The full path of the directory that contains the repositories
FULL_CK_JAR_PATH = START_PATH + RELATIVE_CK_JAR_PATH # The full path of the CK JAR file

def path_contains_whitespaces():
   """
   Verifies if the PATH constant contains whitespaces.

   :return: True if the PATH constant contains whitespaces, False otherwise.
   """

   if VERBOSE: # If the VERBOSE constant is set to True
      print(f"{BackgroundColors.GREEN}Verifying if the {BackgroundColors.CYAN}PATH{BackgroundColors.GREEN} constant contains whitespaces...{Style.RESET_ALL}")
   
   # Verify if the PATH constant contains whitespaces
   if " " in START_PATH: # If the PATH constant contains whitespaces
      return True # Return True if the PATH constant contains whitespaces
   return False # Return False if the PATH constant does not contain whitespaces

def output_time(output_string, time):
   """
   Outputs time, considering the appropriate time unit.

   :param output_string: String to be outputted.
   :param time: Time to be outputted.
   :return: None
   """

   if VERBOSE: # If the VERBOSE constant is set to True
      print(f"{BackgroundColors.GREEN}Outputting the time in the most appropriate time unit...{Style.RESET_ALL}")

   if float(time) < int(TIME_UNITS[0]): # If the time is less than 60 seconds
      time_unit = "seconds" # Set the time unit to seconds
      time_value = time # Set the time value to time
   elif float(time) < float(TIME_UNITS[1]): # If the time is less than 3600 seconds
      time_unit = "minutes" # Set the time unit to minutes
      time_value = time / TIME_UNITS[0] # Set the time value to time divided by 60
   elif float(time) < float(TIME_UNITS[2]): # If the time is less than 86400 seconds
      time_unit = "hours" # Set the time unit to hours
      time_value = time / TIME_UNITS[1] # Set the time value to time divided by 3600
   else: # If the time is greater than or equal to 86400 seconds
      time_unit = "days" # Set the time unit to days
      time_value = time / TIME_UNITS[2] # Set the time value to time divided by 86400

   rounded_time = round(time_value, 2) # Round the time value to two decimal places
   print(f"{BackgroundColors.GREEN}{output_string}{BackgroundColors.CYAN}{rounded_time} {time_unit}{BackgroundColors.GREEN}.{Style.RESET_ALL}")

def verify_ck_metrics_folder(repository_name):
   """
   Verifies if all the metrics are already calculated by opening the commit hashes file and checking if every commit hash in the file is a folder in the repository folder.

   :param repository_name: Name of the repository to be analyzed.
   :return: True if all the metrics are already calculated, False otherwise.
   """

   if VERBOSE: # If the VERBOSE constant is set to True
      print(f"{BackgroundColors.GREEN}Verifying if the metrics for {BackgroundColors.CYAN}{repository_name}{BackgroundColors.GREEN} were already calculated...{Style.RESET_ALL}")

   data_path = os.path.join(START_PATH, RELATIVE_CK_METRICS_DIRECTORY_PATH[1:]) # Join the PATH with the relative path of the ck metrics directory
   repo_path = os.path.join(data_path, repository_name) # Join the data path with the repository name
   commit_file = f"{repository_name}-commits_list{CSV_FILE_EXTENSION}" # The name of the commit hashes file
   commit_file_path = os.path.join(data_path, commit_file) # Join the data path with the commit hashes file

   # Verify if the repository exists
   if not os.path.exists(commit_file_path):
      return False # Return False because the repository commit list does not exist

   # Read the commit hashes csv file and get the commit_hashes column, but ignore the first line
   commit_hashes = pd.read_csv(commit_file_path, sep=",", usecols=["Commit Hash"], header=0).values.tolist()

   # Verify if the repository exists
   for commit_hash in commit_hashes: # Loop through the commit hashes
      commit_file_filename = commit_hash[0] # This removes the brackets from the commit hash
      folder_path = os.path.join(repo_path, commit_file_filename) # Join the repo path with the folder name

      if os.path.exists(folder_path): # Verify if the folder exists
         for ck_metric_file in CK_METRICS_FILES: # Verify if all the ck metrics files exist inside the folder
            ck_metric_file_path = os.path.join(folder_path, ck_metric_file) # Join the folder path with the ck metric file
            if not os.path.exists(ck_metric_file_path): # If the file does not exist
               return False # If the file does not exist, then the metrics are not calculated
   return True # If all the metrics are already calculated

def create_directory(full_directory_name, relative_directory_name):
   """
   Creates a directory.

   :param full_directory_name: Name of the directory to be created.
   :param relative_directory_name: Relative name of the directory to be created that will be shown in the terminal.
   :return: None
   """

   if VERBOSE: # If the VERBOSE constant is set to True
      print(f"{BackgroundColors.GREEN}Creating the {BackgroundColors.CYAN}{relative_directory_name}{BackgroundColors.GREEN} directory...{Style.RESET_ALL}")

   if os.path.isdir(full_directory_name): # Verify if the directory already exists
      return # Return if the directory already exists
   try: # Try to create the directory
      os.makedirs(full_directory_name) # Create the directory
   except OSError: # If the directory cannot be created
      print(f"{BackgroundColors.GREEN}The creation of the {BackgroundColors.CYAN}{relative_directory_name}{BackgroundColors.GREEN} directory failed.{Style.RESET_ALL}")

def update_repository(repository_name):
   """
   Updates the repository using "git pull".

   :param repository_name: Name of the repository to be analyzed.
   :return: None
   """

   if VERBOSE: # If the VERBOSE constant is set to True
      print(f"{BackgroundColors.GREEN}Updating the {BackgroundColors.CYAN}{repository_name}{BackgroundColors.GREEN} repository...{Style.RESET_ALL}")

   repository_directory_path = f"{FULL_REPOSITORIES_DIRECTORY_PATH}/{repository_name}" # The path to the repository directory
   os.chdir(repository_directory_path) # Change the current working directory to the repository directory
   
   # Create a thread to update the repository located in f"{RELATIVE_REPOSITORY_DIRECTORY}/{repository_name}"
   update_thread = subprocess.Popen(["git", "pull"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
   update_thread.wait() # Wait for the thread to finish
   os.chdir(START_PATH) # Change the current working directory to the default one

def clone_repository(repository_name, repository_url):
   """
   Clones the repository to the repository directory.

   :param repository_name: Name of the repository to be analyzed.
   :param repository_url: URL of the repository to be analyzed.

   :return: None
   """

   if VERBOSE: # If the VERBOSE constant is set to True
      print(f"{BackgroundColors.GREEN}Cloning the {BackgroundColors.CYAN}{repository_name}{BackgroundColors.GREEN} repository...{Style.RESET_ALL}")

   repository_directory_path = f"{FULL_REPOSITORIES_DIRECTORY_PATH}/{repository_name}" # The path to the repository directory

   # Verify if the repository directory already exists and if it is not empty
   if os.path.isdir(repository_directory_path) and os.listdir(repository_directory_path):
      update_repository(repository_name) # Update the repository
      return # Return if the repository directory already exists and if it is not empty
   else:
      print(f"{BackgroundColors.GREEN}Cloning the {BackgroundColors.CYAN}{repository_name}{BackgroundColors.GREEN} repository...{Style.RESET_ALL}")
      # Create a thread to clone the repository
      thread = subprocess.Popen(["git", "clone", repository_url, repository_directory_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      thread.wait() # Wait for the thread to finish
      print(f"{BackgroundColors.GREEN}Successfully cloned the {BackgroundColors.CYAN}{repository_name}{BackgroundColors.GREEN} repository.{Style.RESET_ALL}")

def get_last_execution_progress(repository_name, saved_progress_file, number_of_commits):
   """
   Gets the last execution progress of the repository.

   :param repository_name: Name of the repository to be analyzed.
   :param saved_progress_file: Name of the file that contains the saved progress.
   :param number_of_commits: Number of commits to be analyzed.
   :return: The commits_info and last_commit_number.
   """

   if VERBOSE: # If the VERBOSE constant is set to True
      print(f"{BackgroundColors.GREEN}Getting the last execution progress of the {BackgroundColors.CYAN}{repository_name}{BackgroundColors.GREEN} repository...{Style.RESET_ALL}")

   commits_info = [] # The commit information list containing the commit hashes, commit messages and commit dates
   last_commit_number = 0 # The last commit number

   # Verify if there is a saved progress file
   if os.path.exists(saved_progress_file):
      # Open the saved progress file
      with open(saved_progress_file, "r") as progress_file:
         lines = progress_file.readlines() # Read the lines of the progress file
         lines = lines[:-2] # Remove the last two lines

         # Clear the saved progress file
         with open(saved_progress_file, "w") as progress_file:
            progress_file.write("Commit Number,Commit Hash,Commit Message,Commit Date\n")

         # If there are more than 3 lines in the progress file, then there is at least one commit that was already processed
         if len(lines) > 3:
            last_commit_number = int(lines[-1].split(",")[0]) # Get the last commit number
            last_commit_hash = 0 # The last commit hash
            
            with open(saved_progress_file, "w") as progress_file: # Open the saved progress file
               for line in lines: # Loop through the lines
                  progress_file.write(line) # Write the line to the progress file
            
            # Fill the commit_hashes list with the commits that were already processed
            for line in lines[1:]: # Loop through the lines
               current_tuple = (line.split(",")[1], line.split(",")[2], line.split(",")[3]) # Store the commit hash, commit message and commit date in one line of the list, separated by commas
               last_commit_hash = line.split(",")[1] # Get the last commit hash
               commits_info.append(current_tuple) # Append the current tuple to the commit_hashes list
            percentage_progress = round((last_commit_number / number_of_commits) * 100, 2) # Calculate the percentage progress
            
            print(f"{BackgroundColors.GREEN}{BackgroundColors.CYAN}{repository_name.capitalize()}{BackgroundColors.GREEN} stopped executing in {BackgroundColors.CYAN}{percentage_progress}%{BackgroundColors.GREEN} of it's progress in the {BackgroundColors.CYAN}{last_commit_number}º{BackgroundColors.GREEN} commit: {BackgroundColors.CYAN}{last_commit_hash}{BackgroundColors.GREEN}.{Style.RESET_ALL}")

            execution_time = f"Estimated time for running the remaining iterations in {BackgroundColors.CYAN}{repository_name}{BackgroundColors.GREEN}: {Style.RESET_ALL}"
            output_time(execution_time, round(((number_of_commits / 1000) * (number_of_commits - last_commit_number)), 2)) # Output the estimated time for running the remaining iterations for the repository
            
   else: # If there is no saved progress file, create one and write the header
      with open(saved_progress_file, "w") as progress_file: # Open the saved progress file
         progress_file.write("Commit Number,Commit Hash,Commit Message,Commit Date\n") # Write the header to the progress file

   return commits_info, last_commit_number # Return the commit_hashes list and the last commit number

def generate_diffs(repository_name, commit, commit_number):
   """
   Generates the diffs for the commits of a repository.

   :param repository_name: Name of the repository to be analyzed.
   :param commit: The commit object to be analyzed.
   :param commit_number: Number of the commit to be analyzed.
   :return: None
   """

   if VERBOSE: # If the VERBOSE constant is set to True
      print(f"{BackgroundColors.GREEN}Generating the diffs for the {BackgroundColors.CYAN}{commit_number}º{BackgroundColors.GREEN} commit of the {BackgroundColors.CYAN}{repository_name}{BackgroundColors.GREEN} repository...{Style.RESET_ALL}")

   for modified_file in commit.modified_files: # Loop through the modified files of the commit
      file_diff = modified_file.diff # Get the diff of the modified file

      diff_file_directory = f"{START_PATH}{RELATIVE_DIFFS_DIRECTORY_PATH}/{repository_name}/{commit_number}-{commit.hash}/" # Define the directory to save the diff file

      # Validate if the directory exists, if not, create it
      if not os.path.exists(diff_file_directory):
         os.makedirs(diff_file_directory, exist_ok=True) # Create the directory]

      # Open the diff file to write the diff
      with open(f"{diff_file_directory}{modified_file.filename}{DIFF_FILE_EXTENSION}", "w", encoding="utf-8", errors="ignore") as diff_file:
         diff_file.write(file_diff) # Write the diff to the file

def checkout_branch(branch_name):
   """
   Checks out a specific branch.

   :param branch_name: Name of the branch to be checked out.
   :return: None
   """

   if VERBOSE: # If the VERBOSE constant is set to True
      print(f"{BackgroundColors.GREEN}Checking out the {BackgroundColors.CYAN}{branch_name}{BackgroundColors.GREEN} branch...{Style.RESET_ALL}")

   # Create a thread to checkout the branch
   checkout_thread = subprocess.Popen(["git", "checkout", branch_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
   checkout_thread.wait() # Wait for the thread to finish

def generate_output_directory_paths(repository_name, commit_hash, commit_number):
   """
   Generates the output directory path for the CK metrics generator.

   :param repository_name: Name of the repository to be analyzed.
   :param commit_hash: Commit hash of the commit to be analyzed.
   :param commit_number: Number of the commit to be analyzed.
   :return: The output_directory and relative_output_directory paths.
   """

   if VERBOSE: # If the VERBOSE constant is set to True
      print(f"{BackgroundColors.GREEN}Generating the output directory paths...{Style.RESET_ALL}")

   output_directory = f"{FULL_CK_METRICS_DIRECTORY_PATH}/{repository_name}/{commit_number}-{commit_hash}/"
   relative_output_directory = f"{RELATIVE_CK_METRICS_DIRECTORY_PATH}/{repository_name}/{commit_number}-{commit_hash}/"

   return output_directory, relative_output_directory # Return the output_directory and relative_output_directory paths
   
def run_ck_metrics_generator(cmd):
   """
   Runs the CK metrics generator in a subprocess.

   :param cmd: Command to be executed.
   :return: None
   """

   if VERBOSE: # If the VERBOSE constant is set to True
      print(f"{BackgroundColors.GREEN}Running the CK Metrics Generator Command...{Style.RESET_ALL}")

   # Create a thread to run the cmd command
   thread = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE, stderr=subprocess.PIPE) # Run the cmd command in a subprocess
   stdout, stderr = thread.communicate() # Get the stdout and stderr of the thread

def show_execution_time(first_iteration_duration, elapsed_time, number_of_commits, repository_name):
   """
   Shows the execution time of the CK metrics generator.

   :param first_iteration_duration: Duration of the first iteration.
   :param elapsed_time: Elapsed time of the execution.
   :param number_of_commits: Number of commits to be analyzed.
   :param repository_name: Name of the repository to be analyzed.
   :return: None
   """

   if VERBOSE: # If the VERBOSE constant is set to True
      print(f"{BackgroundColors.GREEN}Showing the execution time of the CK metrics generator...{Style.RESET_ALL}")

   estimated_time_string = f"Estimated time for running all the of the iterations in {BackgroundColors.CYAN}{repository_name}{BackgroundColors.GREEN}: "
   output_time(estimated_time_string, round(first_iteration_duration * number_of_commits, 2)) # Output the estimated time for running all of the iterations for the repository
   time_taken_string = f"Time taken to generate CK metrics for {BackgroundColors.CYAN}{number_of_commits}{BackgroundColors.GREEN} commits in {BackgroundColors.CYAN}{repository_name}{BackgroundColors.GREEN} repository: "
   output_time(time_taken_string, round(elapsed_time, 2)) # Output the time taken to generate CK metrics for the commits in the repository

def traverse_repository(repository_name, repository_url, number_of_commits):
   """
   Traverses the repository to run CK for every commit hash in the repository.

   :param repository_name: Name of the repository to be analyzed.
   :param repository_url: URL of the repository to be analyzed.
   :param number_of_commits: Number of commits to be analyzed.
   :return: The commit information of the repository.
   """

   if VERBOSE: # If the VERBOSE constant is set to True
      print(f"{BackgroundColors.GREEN}Traversing the {BackgroundColors.CYAN}{repository_name}{BackgroundColors.GREEN} repository to run CK for every commit hash...{Style.RESET_ALL}")

   start_time = time.time() # Start measuring time
   first_iteration_duration = 0 # Duration of the first iteration
   commit_number = 1 # The current commit number
   saved_progress_file = f"{FULL_PROGRESS_DIRECTORY_PATH}/{repository_name}-progress.csv"

   # Get the last execution progress of the repository
   commits_info, last_commit = get_last_execution_progress(repository_name, saved_progress_file, number_of_commits)

   # Create a progress bar with the total number of commits
   with tqdm(total=number_of_commits-last_commit, unit=f"{BackgroundColors.GREEN}Traversing the {BackgroundColors.CYAN}{repository_name}{BackgroundColors.GREEN} commit tree{Style.RESET_ALL}", unit_scale=True) as pbar:
      for commit in Repository(repository_url).traverse_commits(): # Loop through the commits of the repository
         if commit_number < last_commit: # If the current commit number is less than the last commit number
            commit_number += 1 # Increment the commit number
            pbar.update(1) # Update the progress bar
            continue # Jump to the next iteration

         # Store the commit hash, commit message and commit date in one line of the list, separated by commas
         current_tuple = (f"{commit_number}-{commit.hash}", commit.msg.split("\n")[0], commit.committer_date)
         commits_info.append(current_tuple) # Append the current tuple to the commit_hashes list

         # Save the diff of the modified files of the current commit
         generate_diffs(repository_name, commit, commit_number)

         workdir = f"{FULL_REPOSITORIES_DIRECTORY_PATH}/{repository_name}" # The path to the repository directory
         os.chdir(workdir) # Change working directory to the repository directory

         # Checkout the current commit hash branch to run ck
         checkout_branch(commit.hash)

         # Create the ck_metrics directory paths
         output_directory, relative_output_directory = generate_output_directory_paths(repository_name, commit.hash, commit_number)
         # Create the ck_metrics directory
         create_directory(output_directory, relative_output_directory)

         os.chdir(output_directory) # Change working directory to the repository directory

         # Run ck metrics for the current commit hash
         cmd = f"java -jar {FULL_CK_JAR_PATH} {workdir} false 0 false {output_directory}"
         run_ck_metrics_generator(cmd) # Run the CK metrics generator

         if commit_number == 1: # If it is the first iteration
            first_iteration_duration = time.time() - start_time # Calculate the duration of the first iteration

         # Append the commit hash, commit message and commit date to the progress file
         with open(saved_progress_file, "a") as progress_file:
            progress_file.write(f"{commit_number},{commit.hash},{current_tuple[1]},{current_tuple[2]}\n")

         commit_number += 1 # Increment the commit number
         pbar.update(1) # Update the progress bar

   # Remove the saved progress file when processing is complete
   os.remove(saved_progress_file)

   # Show the execution time of the CK metrics generator
   elapsed_time = time.time() - start_time # Calculate elapsed time
   show_execution_time(first_iteration_duration, elapsed_time, number_of_commits, repository_name)

   return commits_info # Return the commits information list

def write_commits_information_to_csv(repository_name, commit_info):
   """
   Writes the commit information to a csv file.

   :param repository_name: Name of the repository to be analyzed.
   :param commit_info: List of tuples containing the commit hashes, commit messages and commit dates.
   :return: None
   """

   if VERBOSE: # If the VERBOSE constant is set to True
      print(f"{BackgroundColors.GREEN}Writing the commit information to a csv file...{Style.RESET_ALL}")
   
   file_path = f"{FULL_CK_METRICS_DIRECTORY_PATH}/{repository_name}-commits_list{CSV_FILE_EXTENSION}"
   with open(file_path, "w", newline="") as csv_file:
      writer = csv.writer(csv_file) # Create a csv writer
      writer.writerow(["Commit Hash", "Commit Message", "Commit Date"]) # Write the header
      writer.writerows(commit_info) # Write the commit hashes

def process_repository(repository_name, repository_url):
   """
   Processes the repository.

   :param repository_name: Name of the repository to be analyzed.
   :param repository_url: URL of the repository to be analyzed.
   :return: None
   """

   print(f"{BackgroundColors.GREEN}Processing the {BackgroundColors.CYAN}{repository_name}{BackgroundColors.GREEN} repository...{Style.RESET_ALL}")

   # Verify if the metrics were already calculated
   if verify_ck_metrics_folder(repository_name):
      print(f"{BackgroundColors.GREEN}The metrics for {BackgroundColors.CYAN}{repository_name}{BackgroundColors.GREEN} were already calculated!{Style.RESET_ALL}")
      return

   # Create the ck metrics directory
   create_directory(FULL_CK_METRICS_DIRECTORY_PATH, RELATIVE_CK_METRICS_DIRECTORY_PATH)
   # Create the progress directory
   create_directory(FULL_PROGRESS_DIRECTORY_PATH, RELATIVE_PROGRESS_DIRECTORY_PATH)
   # Create the repositories directory
   create_directory(FULL_REPOSITORIES_DIRECTORY_PATH, RELATIVE_REPOSITORIES_DIRECTORY_PATH)

   # Clone the repository
   clone_repository(repository_name, repository_url)

   # Get the number of commits, which is needed to traverse the repository
   number_of_commits = len(list(Repository(repository_url).traverse_commits()))
   # Traverse the repository to run ck for every commit hash in the repository
   commits_info = traverse_repository(repository_name, repository_url, number_of_commits)

   # Write the commits information to a csv file
   write_commits_information_to_csv(repository_name, commits_info)

   # Checkout the main branch
   checkout_branch("main")

def process_repositories_in_parallel():
   """
   Processes each repository in the DEFAULT_REPOSITORIES dictionary in parallel, using threads.

   :return: None
   """

   print(f"{BackgroundColors.GREEN}Processing each of the repositories in parallel using threads...{Style.RESET_ALL}")

   threads = [] # The threads list
   # Loop through the default repositories
   for repository_name, repository_url in DEFAULT_REPOSITORIES.items():
      estimated_time_string = f"Estimated time for running all of the iterations for {BackgroundColors.CYAN}{repository_name}{BackgroundColors.GREEN}: "
      commits_number = len(list(Repository(repository_url).traverse_commits())) # Get the number of commits
      output_time(estimated_time_string, round(((commits_number / 1000) * commits_number), 2)) # Output the estimated time for running all of the iterations for the repository
      thread = threading.Thread(target=process_repository, args=(repository_name, repository_url,)) # Create a thread to process the repository
      threads.append(thread) # Append the thread to the threads list
      thread.start() # Start the thread

   # Wait for all threads to finish
   for thread in threads:
      thread.join() # Wait for the thread to finish

def play_sound():
   """
   Plays a sound when the program finishes.

   :return: None
   """

   if VERBOSE: # If the VERBOSE constant is set to True
      print(f"{BackgroundColors.GREEN}Playing a sound when the program finishes...{Style.RESET_ALL}")
   
   if os.path.exists(SOUND_FILE):
      if platform.system() in SOUND_COMMANDS: # if the platform.system() is in the SOUND_COMMANDS dictionary
         os.system(f"{SOUND_COMMANDS[platform.system()]} {SOUND_FILE}")
      else: # if the platform.system() is not in the SOUND_COMMANDS dictionary
         print(f"{BackgroundColors.RED}The {BackgroundColors.CYAN}platform.system(){BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}")
   else: # if the sound file does not exist
      print(f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}")

# Register the function to play a sound when the program finishes
atexit.register(play_sound)

def main():
   """
   Main function.

   :return: None
   """
   
   # Verify if the path constants contains whitespaces
   if path_contains_whitespaces():
      print(f"{BackgroundColors.RED}The {START_PATH} constant contains whitespaces. Please remove them!{Style.RESET_ALL}")
      return
   
   # Verify if the CK JAR file exists
   if not os.path.exists(FULL_CK_JAR_PATH):
      print(f"{BackgroundColors.RED}The CK JAR file does not exist. Please download it and place it in {BackgroundColors.CYAN}{RELATIVE_CK_JAR_PATH[0:RELATIVE_CK_JAR_PATH.find('/', 1)]}/{BackgroundColors.RED}.{Style.RESET_ALL}")
      return

   # Print the welcome message
   print(f"{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}CK Metrics Generator{BackgroundColors.GREEN}! This script is a key component of the {BackgroundColors.CYAN}Worked Example Miner (WEM) Project{BackgroundColors.GREEN}.{Style.RESET_ALL}")
   print(f"{BackgroundColors.GREEN}This script will process the repositories: {BackgroundColors.CYAN}{list(DEFAULT_REPOSITORIES.keys())}{BackgroundColors.GREEN} in parallel using threads.{Style.RESET_ALL}")
   print(f"{BackgroundColors.GREEN}The files that this script will generate are the {BackgroundColors.CYAN}ck metrics files, the commit hashes list file and the diffs of each commit{BackgroundColors.GREEN}, in which are used by the {BackgroundColors.CYAN}Metrics Changes{BackgroundColors.GREEN} Python script.{Style.RESET_ALL}", end="\n\n")   

   process_repositories_in_parallel() # Process each of the repositories in parallel

   # Print the message that the CK metrics generator has finished processing the repositories
   print(f"\n{BackgroundColors.GREEN}The {BackgroundColors.CYAN}CK Metrics Generator{BackgroundColors.GREEN} has finished processing the repositories.{Style.RESET_ALL}", end="\n\n")
		
if __name__ == '__main__':
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """

   main() # Call the main function
