import os # Import the os module
from colorama import Style # For coloring the terminal

# Macros:
class backgroundColors: # Colors for the terminal
	CYAN = "\033[96m" # Cyan
	GREEN = "\033[92m" # Green
	YELLOW = "\033[93m" # Yellow
	RED = "\033[91m" # Red
	CLEAR_TERMINAL = "\033[H\033[J" # Clear the terminal

# List of folders to ignore
ignore_folders = ["docs", ".git", "makefile", "my softwares", "node_modules", ".tmp"]

# Function to find files without extension
def find_files_without_extension(directory):
	count = 0 # Counter to count the number of files without extension

	# Loop through all the files in the directory
	for root, dirs, files in os.walk(directory):
		for file in files: # Loop through all the files in the directory
			full_file_path = os.path.join(root, file) # Get the full path of the file
			relative_file_path = os.path.relpath(full_file_path, directory) # Get the relative path of the file
			
			# Verify if any of the folders in the ignore_folders list is in the full_file_path
			if any(folder in full_file_path.lower() for folder in ignore_folders):
				continue # Skip the file if any of the folders in the ignore_folders list is in the full_file_path

			# Verify if the file has an extension
			if not "." in file:
				count += 1 # Increment the counter
    			# write the file path to a txt file
				with open("files_without_extension.txt", "a") as f:
					f.write(f"{count} - {relative_file_path}\n") # Write the file path to the txt file
		
	return count # Return the number of files without extension

# Main function
def main():
	# Clear the file before writing
	with open("files_without_extension.txt", "w") as f:
		f.write("") # Write nothing to the file

	directory_path = os.getcwd() # Get the current working directory
	count = find_files_without_extension(directory_path) # Call the function to find files without extension

	# Print the number of files without extension
	if count == 0:
		print(f"No files without extension found in {directory_path}")
	else:
		print(f"{count} files without extension found in {directory_path}")

if __name__ == "__main__":
	main() # Call the main function
