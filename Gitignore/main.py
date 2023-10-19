# TODO: The levels are important, being only passing through 3 levels: example: /Public/ProjetName/.gitignore or Private/ProjectName/.gitignore

import os # For walking through the directory tree
from colorama import Style # For coloring the terminal

# Macros:
class backgroundColors: # Colors for the terminal
	CYAN = "\033[96m" # Cyan
	GREEN = "\033[92m" # Green
	YELLOW = "\033[93m" # Yellow
	RED = "\033[91m" # Red

def find_gitignore_files(directory):
	gitignore_files = []
	for root, _, files in os.walk(directory):
		if '.gitignore' in files:
			gitignore_files.append(os.path.join(root, '.gitignore'))
	return gitignore_files

def update_gitignore(file_path, relative_path):
	with open(file_path, 'r') as f:
		lines = f.readlines()

	# Check if ".DS_Store" is not already present in the Gitignore file
	if not any(line.strip() == ".DS_Store" for line in lines):
		# lines.append(".DS_Store\n")
		# with open(file_path, 'w') as f:
		# 	# f.writelines(lines)
		print(f"{backgroundColors.CYAN}.DS_Store{backgroundColors.GREEN} added to {backgroundColors.CYAN}{relative_path}{Style.RESET_ALL}")

if __name__ == "__main__":
	current_directory = os.getcwd()
	gitignore_files = find_gitignore_files(current_directory)

	if not gitignore_files:
		print(f"{backgroundColors.RED}No {backgroundColors.CYAN}.gitignore files found {backgroundColors.RED}in the {backgroundColors.CYAN}{current_directory}{backgroundColors.RED} directory or its subdirectories.{Style.RESET_ALL}")
	else:
		for gitignore_file in gitignore_files:
			relative_path = os.path.relpath(gitignore_file, current_directory)
			update_gitignore(gitignore_file, relative_path)
