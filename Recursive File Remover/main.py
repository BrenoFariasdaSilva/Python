import os # Import the os module
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
REMOVE_FILES = ["desktop.ini", ".DS_Store"] # Files to be removed

# This function deletes the desktop.ini file
def deleteFiles(path):
	counter = 0 # Counter of files removed
	# Walk through the path
	for folderName, subfolders, filenames in os.walk(path):
		for filename in filenames: # For each filename in the filenames
			if filename in REMOVE_FILES: # If the filename is in the REMOVE_FILES
				counter += 1 # Increment the counter
				complete_filename = os.path.join(folderName, filename) # Complete filename
				print(f"{backgroundColors.GREEN}Deleting: {backgroundColors.CYAN}{counter}{backgroundColors.GREEN}º - {backgroundColors.CYAN}{complete_filename}{Style.RESET_ALL}")
				os.remove(os.path.join(folderName, filename)) # Remove the file
		
# This function is the main function
def main():
	path = os.getcwd() # Get the current working directory
	deleteFiles(path) # Delete the files in REMOVE_FILES
  
# This is the standard boilerplate that calls the main() function
if __name__ == '__main__':
	main() # Call the main function
