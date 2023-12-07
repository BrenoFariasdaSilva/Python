import os # Import the os module for interacting with the operating system
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

# This is the main function
def main():
	while True: 
		# Ask user to enter paths to verify
		path = input(f"{BackgroundColors.GREEN}Enter path to verify: {Style.RESET_ALL}")
		if path == "exit":
			break # Break the loop

	# Verify if the path exists
	for folder_name, subfolders, filenames in os.walk(path):
		# Ignore the path that is already in the path
		if folder_name == path:
			continue # Continue to the next iteration

		# Print the path, subfolders and files
		if len(subfolders) > 0:
			print(f"{BackgroundColors.GREEN}Folder: {BackgroundColors.CYAN}{folder_name}{Style.RESET_ALL}")
			print(f"{BackgroundColors.GREEN}Subfolders: {BackgroundColors.CYAN}{subfolders}{Style.RESET_ALL}")
			print(f"{BackgroundColors.GREEN}Files: {BackgroundColors.CYAN}{filenames}{Style.RESET_ALL}")
			print(f"{BackgroundColors.GREEN}")

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
	main() # Call the main function
