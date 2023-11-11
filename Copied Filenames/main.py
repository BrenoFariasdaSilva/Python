import os # Import the os module for traversing the directory
import re # Import the re module for regular expressions
from colorama import Style # For coloring the terminal

# Macros:
class backgroundColors: # Colors for the terminal
	CYAN = "\033[96m" # Cyan
	GREEN = "\033[92m" # Green
	YELLOW = "\033[93m" # Yellow
	RED = "\033[91m" # Red
	BOLD = "\033[1m" # Bold
	UNDERLINE = "\033[4m" # Underline
	CLEAR_TERMINAL = "\033[H\033[J" # Clear the terminal

# Constants:
SEARCHED_STRING = "copy" # The string to search for duplicates

# Function to verify if the filename has the copy parenthesis
def copy_parenthesis(filename):
	# Define the regular expression pattern to verify if there are digits between parenthesis
	pattern = r"\(\d+\)"
	# Search for the pattern in the filename
	match = re.search(pattern, filename)
	
	return match is not None # Return True if the pattern is found

def is_copy_filename(filename):
	return copy_parenthesis(filename) or SEARCHED_STRING in filename

# Function to verify if there are duplicates
def get_copied_filenames(files):
	for filename in files: # Loop through the files
		# Verify if the filename has the copy parenthesis or the searched string
		if is_copy_filename(filename):
			print(f"{backgroundColors.CYAN}{filename}{backgroundColors.GREEN} is a duplicate.{Style.RESET_ALL}")

# This is the main function
def main():
	current_path = os.getcwd() # Get the current path
	files = os.listdir(current_path) # Get all the files in the path
	get_copied_filenames(files) # Verify for duplicates

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
	main() # Call the main function
