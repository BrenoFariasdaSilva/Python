import os # Import the os module for interacting with the operating system
import time # For sleeping
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
movies_type = ["Dual", "Dublado", "English", "Legendado", "Nacional"]

# This function verifies if there is any misplaced file
def misplaced_folder(path_input):
	initial_path = os.getcwd() # Get the current working directory
	folder_list = os.listdir(rf"{path_input}") # List of folders in the path_input and rf is used to escape the backslashes
 
	found = False # If there is any misplaced file

	# Verify if there is any misplaced file
	for folder_name in folder_list:
		if folder_name not in movies_type: # If the folder name is not in the movies type
			continue # Continue to the next iteration

		# Change the current working directory to the folder name
		os.chdir(f"{path_input}/{folder_name}")
		# List of files in the folder name and rf is used to escape the backslashes
		file_list = os.listdir(rf"{path_input}/{folder_name}")
  
		# Verify if there is any misplaced file
		for file_name in file_list:
			if folder_name not in file_name: # If the folder name is not in the file name
				print(f"{BackgroundColors.CYAN}{file_name}{BackgroundColors.GREEN} is misplaced in {BackgroundColors.CYAN}{path_input}\{folder_name}{Style.RESET_ALL}")
				os.rename(file_name, f"{path_input}/{file_name}") # Move the file to the path_input
				found = True # There is a misplaced file
				while not os.path.exists(f"{path_input}/{file_name}"):
					time.sleep(1.0) # Sleep for 1 second
	
	if found: # If there is a misplaced file
		print() # Print a new line
	os.chdir(initial_path) # Change the current working directory back to the original path

# This function verifies if the folders exist and create them if they don't
def verify_folder(path_input):
	for folder_name in movies_type: # For each folder name in the movies type
		if not os.path.exists(f"{path_input}/{folder_name}"): # If the folder doesn't exist
			os.mkdir(f"{path_input}/{folder_name}") # Create the folder

def move_files(path_input):
	file_list = os.listdir(rf"{path_input}") # r"" is used to escape the backslashes
	saved_path = os.getcwd() # Get the current working directory
	os.chdir(r"" + path_input) # Change the current working directory to the path_input
 
	verify_folder(path_input) # Verify if the folders exist and create them if they don't
 
	number_of_files = [0, 0, 0, 0, 0] # Related to the movies type, in that case, Dual, Dublado, Nacional, Legendado and English
 
	# Move the files
	for file_name in file_list:
		if file_name in movies_type: # If the file name is in the movies type
			continue # Continue to the next iteration

		# Verify if the file name is in the movies type
		for i in range(len(movies_type)):
			if movies_type[i] in file_name: # If the movies type is in the file name
				os.rename(file_name, f"{path_input}/{movies_type[i]}/{file_name}") # Move the file to the movies type
				while not os.path.exists(f"{path_input}/{movies_type[i]}/{file_name}"): # While the file doesn't exist
					time.sleep(1.0) # Sleep for 1 second
				number_of_files[i] += 1 # Increment the number of files
				break # Break the loop
	 
	os.chdir(saved_path) # Change the current working directory back to the original path
	return number_of_files # Return the number of files

# This function shows the result
def show_result(number_of_files):
	print(f"{BackgroundColors.GREEN}Total of files moved: {BackgroundColors.CYAN}{sum(number_of_files)}{Style.RESET_ALL}")
	for i in range(len(movies_type)):
		print(f"{BackgroundColors.GREEN}Total of {BackgroundColors.CYAN}{movies_type[i]}{BackgroundColors.GREEN} files moved: {BackgroundColors.CYAN}{number_of_files[i]}{Style.RESET_ALL}")

# This is the main function	
def main():
	path_input = input(f"{BackgroundColors.GREEN}Enter the path of the folder: {Style.RESET_ALL}") # Get the path of the folder
	misplaced_folder(path_input) # Verify if there is any misplaced file
	number_of_files = move_files(path_input) # Move the files
	show_result(number_of_files) # Show the result

# This is the standard boilerplate that calls the main() function.	
if __name__ == "__main__":
	main() # Call the main function
