import os # For walking through the directory tree
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

# This function will return the difference between two folders
def diff(paths):
	first_path = paths[0] # The first path
	second_path = paths[1] # The second path
 
	first_path_folders = os.listdir(first_path) # Get the folders in the first path
	second_path_folders = os.listdir(second_path) # Get the folders in the second path
 
	diff_folders = [] # The difference between the folders
 
	# Get the difference between the folders
	for folder in first_path_folders:
		if folder not in second_path_folders: # If the folder is not in the second path
			diff_folders.append(folder) # Add the folder to the list
   
	return diff_folders # Return the difference between the folders

# This is the main function
def main():
	paths = [] # List of paths
 
	# Get the paths
	for i in range(2):
		path = input(f"{backgroundColors.GREEN}Enter path: {Style.RESET_ALL}") # Get the path
		paths.append(path) # Add the path to the list
  
	# Get the difference between the folders
	diff_folders = diff(paths)
 
	# Print the difference
	[ print(f"{backgroundColors.CYAN}{diff_folders[i]}{backgroundColors.GREEN}: not in {backgroundColors.CYAN}{paths[2]}{Style.RESET_ALL}") for i in range(len(diff_folders)) ]

# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
	main() # Call the main function
