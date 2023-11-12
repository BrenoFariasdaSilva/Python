import os # For walking through the directory tree
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

# Constants:
SEARCH_STRINGS = [".DS_Store"] # Strings to search for in the Gitignore file
TARGET_FILE = ".gitignore" # Name of the file to search for

# @brief: Finds all the Gitignore files in the current directory and its subdirectories
# @param directory: The directory to search in
# @return: A list of all the Gitignore files found
def find_gitignore_files(directory):
	gitignore_files = [] # List to store the Gitignore files

	for root, _, files in os.walk(directory): # Walk through the directory tree
		if TARGET_FILE in files: # Check if the Gitignore file is present in the current directory
			gitignore_files.append(os.path.join(root, TARGET_FILE)) # Add the Gitignore file to the list

	return gitignore_files # Return the list of Gitignore files

# @brief: Updates the Gitignore file
# @param file_path: The path to the Gitignore file
# @param relative_path: The relative path to the Gitignore file
# @return: None
def update_gitignore(file_path, relative_path):
	# Read the Gitignore file
	with open(file_path, "r") as f:
		lines = f.readlines() # Read all the lines

	for line in lines: # Iterate through all the lines
		for search_string in SEARCH_STRINGS: # Iterate through all the search strings
			if search_string not in line: # Check if the search string is not present in the Gitignore file
				with open(file_path, "a") as f: # Open the Gitignore file in append mode
					f.write(f"{search_string}\n") # Add the search string to the Gitignore file
				print(f"{BackgroundColors.GREEN}Added {BackgroundColors.CYAN}{search_string}{BackgroundColors.GREEN} to {BackgroundColors.CYAN}{relative_path}{Style.RESET_ALL}")

# @brief: The main function
# @param: None
# @return: None
def main():
	current_directory = os.getcwd() # Get the current directory
	gitignore_files = find_gitignore_files(current_directory) # Find all the Gitignore files in the current directory and its subdirectories

	# Check if there are any Gitignore files 
	if not gitignore_files:
		print(f"{BackgroundColors.RED}No {BackgroundColors.CYAN}{TARGET_FILE} files found {BackgroundColors.RED}in the {BackgroundColors.CYAN}{current_directory}{BackgroundColors.RED} directory or its subdirectories.{Style.RESET_ALL}")
	else:
		# Update all the Gitignore files
		for gitignore_file in gitignore_files:
			relative_path = os.path.relpath(gitignore_file, current_directory)
			update_gitignore(gitignore_file, relative_path) # Update the Gitignore file

# This is the standard boilerplate that calls the main() function
if __name__ == '__main__':
	main() # Call the main function
