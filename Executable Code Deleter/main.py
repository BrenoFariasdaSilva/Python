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
EXECUTABLE_EXTENSIONS = [".exe", ".o", ".pyc", ".pyo"] # Add more extensions if you want
EXCEPTION_FILES = ["make.exe", "Make.exe", "Makefile", "makefile"] # Add more files if you want
IGNORE_FOLDERS = ["BusTracker", "UTFome"]

# This function will search for executable files in the directory
def search_executable_files(path):
	# Iterate over all the files in directory
	for root, dirs, files in os.walk(path):
		for file in files: # Iterate over all the files in the directory
			full_path = os.path.join(root, file) # Get the full path of the file

			# Verify if any of the ignore folders are in the full path
			if any(ignore_folder in full_path for ignore_folder in IGNORE_FOLDERS):
				continue # Ignore the folder
			# Verify if any of the exception files are in the full path
			elif any(exception_file in full_path for exception_file in EXCEPTION_FILES):
				continue # Ignore the file

			file_remover(full_path) # Delete the file if it is an executable file

# This function will delete the file
def file_remover(full_path):
	file_extension = os.path.splitext(full_path)[1] # Get the file extension

	# Verify if the file extension is in the executable extensions
	if file_extension in EXECUTABLE_EXTENSIONS:
		print(f"{BackgroundColors.CYAN}Deleted {BackgroundColors.CYAN}{full_path}{Style.RESET_ALL}") # Print the file path
		os.remove(full_path) # Delete the file
   
# This is the main function
def main():
	path = os.getcwd() # Get the current working directory
 
	# Check if path is a directory
	if os.path.isdir(path):
		search_executable_files(path) # List all the files in the directory

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
   main() # Call the main function
