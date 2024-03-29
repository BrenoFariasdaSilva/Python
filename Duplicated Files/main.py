import os # Import the os module for traversing the directory
from collections import defaultdict # Import defaultdict to store the filenames
from colorama import Style # For coloring the terminal
from tqdm import tqdm # For the progress bar

# Macros:
class BackgroundColors: # Colors for the terminal
   CYAN = "\033[96m" # Cyan
   GREEN = "\033[92m" # Green
   YELLOW = "\033[93m" # Yellow
   RED = "\033[91m" # Red
   BOLD = "\033[1m" # Bold
   UNDERLINE = "\033[4m" # Underline
   CLEAR_TERMINAL = "\033[H\033[J" # Clear the terminal

# Set to True to delete duplicate files
DELETE_DUPLICATES = False

# Function to find duplicate files in a directory
def find_duplicate_files(directory):
   file_dict = defaultdict(list) # Create a dictionary to store the filenames

   # Traverse the directory and record filenames in a dictionary
   for foldername, subfolders, filenames in tqdm(os.walk(directory), desc="Searching For Duplicated Files", unit="file"):
      for filename in filenames: # Loop through the files in the current folder
         full_path = os.path.join(foldername, filename) # Get the full path of the file
         file_dict[filename].append(full_path) # Add the filename to the dictionary

   # Filter out files with only one occurrence
   duplicate_files = {filename: paths for filename, paths in file_dict.items() if len(paths) > 1}

   # Return the dictionary of duplicate files
   return duplicate_files 

# Main function
def main():
   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to {BackgroundColors.CYAN}Duplicated Files{BackgroundColors.GREEN}!{Style.RESET_ALL}") # Print a welcome message

   current_directory = os.getcwd() # Get the current working directory
   duplicate_files = find_duplicate_files(current_directory) # Find duplicate files in the current directory

   # Show the duplicate files
   if duplicate_files:
      print(f"{BackgroundColors.GREEN}Duplicate files found:{Style.RESET_ALL}")
      for filename, paths in tqdm(duplicate_files.items(), desc="Processing Duplicate files", unit="file"): # Loop through the duplicate files
         print(f"{BackgroundColors.GREEN}File: {BackgroundColors.CYAN}{filename}{Style.RESET_ALL}")
         for path in paths: # Loop through the paths of the file
            print(f"{BackgroundColors.GREEN}  - {BackgroundColors.CYAN}{path}{Style.RESET_ALL}")
         print(f"")
         
   if DELETE_DUPLICATES: # Delete the duplicate files
      for filename, paths in tqdm(duplicate_files.items(), desc="Deleting the Files Duplicates", unit="file"):
         for path in paths[1:]: # Delete all but the first file
            os.remove(path) # Delete the file
         print(f"{BackgroundColors.YELLOW}Deleted {BackgroundColors.CYAN}{len(paths)-1}{BackgroundColors.GREEN} copies of {BackgroundColors.CYAN}{filename}{BackgroundColors.GREEN}.{Style.RESET_ALL}")
   else:
      print(f"{BackgroundColors.GREEN}No duplicate files found in the current directory.{Style.RESET_ALL}")

   print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Execution finished.{Style.RESET_ALL}")

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
   main() # Call the main function
