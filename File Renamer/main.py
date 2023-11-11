# ToDo: Implement logic for the possibility of a srt file be in the folder

import os
from colorama import Style # For coloring the terminal

# Macros:
class backgroundColors: # Colors for the terminal
	CYAN = "\033[96m" # Cyan
	GREEN = "\033[92m" # Green
	YELLOW = "\033[93m" # Yellow
	RED = "\033[91m" # Red
	CLEAR_TERMINAL = "\033[H\033[J" # Clear the terminal

movies_extensions = ["mp4", "mkv", "avi", "mov"]
subtitles_extension = ["srt"]

def getFileFormat(file_list, i):
	file_format = file_list[i][file_list[i].rfind(".") + 1:]
	return file_format

def find_same_name_files(file_list):
	same_name_files = []
	for file_name in file_list:
		if file_name[:file_name.rfind(".")] in file_list:
			same_name_files.append(file_name)

	return same_name_files

def rename_movie_files(path_input):
	# r"" is used to escape the backslashes
	file_list = os.listdir(r"" + path_input)
	saved_path = os.getcwd()  # Get the current working directory
	# Change the current working directory to the path_input
	os.chdir(r"" + path_input)

	i = 1
	for file_name in file_list:
		file_format = getFileFormat(file_list, i - 1)  # Get the file format
		if i < 10:
			# Rename the file using a 0 before the number if it's less than 10
			os.rename(file_name, "0" + str(i) + "." + file_format)
		else:
			# Rename the file using i as the number
			os.rename(file_name, str(i) + "." + file_format)
		i += 1

	# Change the current working directory back to the original path
	os.chdir(saved_path)

def rename_movies_with_subtitles(path_input):
	file_list = os.listdir(r"" + path_input)
	saved_path = os.getcwd() 
	os.chdir(r"" + path_input)

	same_name_files = find_same_name_files(file_list)

	print("The files with the same name are: ")
	print(same_name_files)

	# now search for the movie file and the srt file with the name in the same_name_files list and rename them with the same number
	# i = 1
	# for file_name in file_list:
	# 	file_format = getFileFormat(file_list, i - 1)

def main():
	print("Welcome to the file renamer!")
	while True:
		print("Enter the path to the folder: ")
		path_input = input()
		if os.path.exists(path_input):
			break
		else:
			print("The path doesn't exist!")

	file_list = os.listdir(r"" + path_input)
	if find_same_name_files(file_list):
		rename_movies_with_subtitles(path_input)
	else:
		rename_movie_files(path_input)

if __name__ == '__main__':
    main()