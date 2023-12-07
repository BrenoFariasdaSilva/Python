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
MOVIES_FILE_FORMAT = ["avi", "mkv", "mov", "mp4"] # The extensions of the movies
SUBTITLES_FILE_FORMAT = ["srt"] # The extensions of the subtitles

# This function will return the file format
def getFileFormat(file):
	return file[file.rfind(".") + 1:] # Return the file format

# This function will return the file name without the extension
def getFileNameWithoutExtension(file):
	return file[:file.rfind(".")] # Return the file name without the extension

# This function will rename the movies and the subtitles that have the same name but different extensions with the same number and different extensions
def rename_movies(file_list):
	number_of_files = len(file_list) # Get the number of files in the file list
	i = 0 # The index of the current file
	file_order = 1 # The order of the file

	# Loop from 0 to the number of files in the file list
	while i < number_of_files:
		print(f"{BackgroundColors.YELLOW}File number: {file_order}{Style.RESET_ALL}") # Print the file number
		current_file_format = getFileFormat(file_list[i]) # Get the current file format

		file_number = f"0{file_order}" if file_order < 10 else f"{file_order}" # If the file number is less than 10, add a 0 before the number

		# If the current file and the next file have the same name but different extensions
		if ((i != number_of_files - 1) and (getFileNameWithoutExtension(file_list[i]) == getFileNameWithoutExtension(file_list[i + 1]) and (getFileFormat(file_list[i]) != getFileFormat(file_list[i + 1])))):
			print(f"  {BackgroundColors.CYAN}{file_list[i]}{BackgroundColors.GREEN} -> {BackgroundColors.CYAN}{file_number}.{current_file_format}{Style.RESET_ALL}")
			print(f"  {BackgroundColors.CYAN}{file_list[i + 1]}{BackgroundColors.GREEN} -> {BackgroundColors.CYAN}{file_number}.{getFileFormat(file_list[i + 1])}{Style.RESET_ALL}")
			os.rename(file_list[i], f"{file_number}.{current_file_format}")
			os.rename(file_list[i + 1], f"{file_number}.{getFileFormat(file_list[i + 1])}")
			i += 2 # Increment i by 2, as we have renamed 2 files
		else: # If the next file has a different name
			print(f"  {BackgroundColors.CYAN}{file_list[i]}{BackgroundColors.GREEN} -> {BackgroundColors.CYAN}{file_number}.{current_file_format}{Style.RESET_ALL}")
			os.rename(file_list[i], f"{file_number}.{current_file_format}")
			i += 1 # Increment i by 1, as we have renamed 1 file

		file_order += 1 # Increment the file order by 1

# This is the main function
def main():
	print(f"{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}File Renamer{BackgroundColors.GREEN}!{Style.RESET_ALL}", end="\n\n")

	current_path = os.getcwd() # Get the current working directory
	file_list = os.listdir(rf"{current_path}") # Get the files in the current_path
	
	# Filter the files_list to only include the movies and the subtitles
	file_list = [file for file in file_list if getFileFormat(file) in MOVIES_FILE_FORMAT or getFileFormat(file) in SUBTITLES_FILE_FORMAT]
	file_list.sort() # Sort the file_list alphabetically

	# If there are no files in the current_path
	if len(file_list) == 0:
		print(f"{BackgroundColors.RED}There are no files in this directory!{Style.RESET_ALL}")
	else:
		rename_movies(file_list) # Rename the movies

	print(f"\n{BackgroundColors.GREEN}Finished renaming the files!{Style.RESET_ALL}")

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
	main() # Call the main function
