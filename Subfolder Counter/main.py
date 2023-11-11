import os # Import the os module for interacting with the operating system
from colorama import Style # For coloring the terminal

# Macros:
class backgroundColors: # Colors for the terminal
	CYAN = "\033[96m" # Cyan
	GREEN = "\033[92m" # Green
	YELLOW = "\033[93m" # Yellow
	RED = "\033[91m" # Red
	CLEAR_TERMINAL = "\033[H\033[J" # Clear the terminal

# This is the main function
def main():
	while True: 
		# Ask user to enter paths to verify
		path = input(f"{backgroundColors.GREEN}Enter path to verify: {Style.RESET_ALL}")
		if path == "exit":
			break # Break the loop

	# Verify if the path exists
	for folder_name, subfolders, filenames in os.walk(path):
		# Ignore the path that is already in the path
		if folder_name == path:
			continue # Continue to the next iteration

		# Print the path, subfolders and files
		if len(subfolders) > 0:
			print(f"{backgroundColors.GREEN}Folder: {backgroundColors.CYAN}{folder_name}{Style.RESET_ALL}")
			print(f"{backgroundColors.GREEN}Subfolders: {backgroundColors.CYAN}{subfolders}{Style.RESET_ALL}")
			print(f"{backgroundColors.GREEN}Files: {backgroundColors.CYAN}{filenames}{Style.RESET_ALL}")
			print(f"{backgroundColors.GREEN}")

# This is the standard boilerplate that calls the main() function.
if __name__ == '__main__':
	main() # Call the main() function
