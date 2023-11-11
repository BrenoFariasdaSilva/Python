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
   
# This function will get all the directories names in the path
def get_directories(path):
	directories_list = [] # List of all the directories

	# Iterate over all the files in directory
	for root, dirs, files in os.walk(path):
		for directory in dirs: # Iterate over all the directories in the directory
			directories_list.append(directory) # Add the directory to the list

	return directories_list # Return the list

# This function will verify if there are duplicates in the list
def search_duplicates(directories_list):
	list_size = len(directories_list) - len(set(directories_list)) # Get the number of duplicates

	current_index = 0 # Current index of the list
	duplicates = 0 # Number of duplicates

	while current_index < list_size:
		if directories_list[current_index] == directories_list[current_index + 1] and current_index + 1 < list_size:
			print(f"{BackgroundColors.GREEN}Duplicate: {BackgroundColors.CYAN}{directories_list[current_index]}{Style.RESET_ALL}")

		current_index += 1 # Increment the current index

	if duplicates == 0:
		print(f"{BackgroundColors.CYAN}No duplicates found!{Style.RESET_ALL}")
	
# This is the main function
def main():
	print(f"{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Duplicated Directories Finder{BackgroundColors.GREEN}!{Style.RESET_ALL}") # Print a welcome message

	path = os.getcwd() # Get the current working directory
	directories_list = get_directories(path) # Get all the files in the path
	directories_list.sort() # Sort the list
	search_duplicates(directories_list) # List all the files in the directory
   
# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
   main() # Call the main function
