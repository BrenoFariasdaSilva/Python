import os # Import the os module for traversing the directory
from colorama import Style # For coloring the terminal

# Macros:
class backgroundColors: # Colors for the terminal
	CYAN = "\033[96m" # Cyan
	GREEN = "\033[92m" # Green
	YELLOW = "\033[93m" # Yellow
	RED = "\033[91m" # Red

DELETE_DUPLICATES = False # Set to True to delete duplicate files

# Function to check if there are duplicates
def get_duplicates_filenames(files):
	duplicates = {} # Dictionary to store the duplicates
	for filename in files: # Loop through the files
		# Check if the file is a duplicate
		if filename.endswith(")") and filename.find("(") != -1:
			print(f"{backgroundColors.CYAN}{filename}{backgroundColors.GREEN} is a duplicate.{Style.RESET_ALL}")
			# Get the original file name
			original_filename = filename[:filename.find("(")]
			# Check if the original file is in the dictionary.
			if original_filename in duplicates:
				duplicates[original_filename].append(filename) # Add the duplicate to the dictionary
			else:
				duplicates[original_filename] = [filename] # Add the original file to the dictionary
		
	# Return the dictionary of duplicates only the lines with more than one duplicate
	return {filename: filenames for filename, filenames in duplicates.items() if len(filenames) > 1}

# This function shows the duplicates
def show_duplicates(duplicates):
	# If the dictionary is not empty, print the duplicates
	if duplicates:
		print(f"{backgroundColors.GREEN}Duplicate files found:{Style.RESET_ALL}")
		for original_filename, filename in duplicates.items():
			print(f"{backgroundColors.GREEN}File: {backgroundColors.CYAN}{original_filename}{backgroundColors.GREEN} ({backgroundColors.CYAN}{filename}{backgroundColors.GREEN} copies){Style.RESET_ALL}")
	else:
		print(f"{backgroundColors.GREEN}No duplicate files found in the current directory.{Style.RESET_ALL}")

# This function deletes the duplicates
def delete_duplicates(duplicates):
	# Loop through the duplicates keys (file) and values (count)
	for original_filename, filename in duplicates.items():
		# Loop through the count and delete the duplicates
		for i in range(filename):
			os.remove(f"{original_filename}({i+1})")
		print(f"{backgroundColors.YELLOW}Deleted {backgroundColors.CYAN}{filename}{backgroundColors.GREEN} copies of {backgroundColors.CYAN}{original_filename}{backgroundColors.GREEN}.{Style.RESET_ALL}")

# This is the main function
def main():
	path = os.getcwd() # Get the current working directory

	# Check if the path exists
	if not os.path.exists(path):
		print(f"{backgroundColors.CYAN}{path}{backgroundColors.RED} does not exist.{Style.RESET_ALL}")
		
	files = os.listdir(path) # Get all the files in the path
	duplicates = get_duplicates_filenames(files) # Check for duplicates

	show_duplicates(duplicates) # Show the duplicates

	# Delete the duplicates if DELETE_DUPLICATES is True
	if DELETE_DUPLICATES: 
		delete_duplicates(duplicates)

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
	main() # Call the main function
