import os
import time

movies_type = ["Dual", "Dublado", "Nacional", "Legendado"]

def misplaced_folder(path_input):
	initial_path = os.getcwd()
	folder_list = os.listdir(r"" + path_input)
 
	found = False

	for folder_name in folder_list:
		if folder_name not in movies_type:
			continue

		os.chdir(path_input + "/" + folder_name)
		file_list = os.listdir(r"" + path_input + "/" + folder_name)
  
		for file_name in file_list:
			if folder_name not in file_name:
				print(file_name + " is misplaced" + " in " + path_input + "\\" + folder_name)
				os.rename(file_name, path_input + "/" + file_name)
				found = True
				while not os.path.exists(path_input + "/" + file_name):
					time.sleep(1.0)
		
	if found:
		print()
	os.chdir(initial_path)
 
def verify_folder(path_input):
	for folder_name in movies_type:
		if not os.path.exists(path_input + "/" + folder_name):
			os.mkdir(path_input + "/" + folder_name)

def move_files(path_input):
	file_list = os.listdir(r"" + path_input) # r"" is used to escape the backslashes
	saved_path = os.getcwd() # Get the current working directory
	os.chdir(r"" + path_input) # Change the current working directory to the path_input
 
	verify_folder(path_input)
 
	number_of_files = [0, 0, 0, 0]
 
	for file_name in file_list:
		if file_name in movies_type:
			continue
		for i in range(len(movies_type)):
			if movies_type[i] in file_name:
				os.rename(file_name, path_input + "/" + movies_type[i] + "/" + file_name)
				while not os.path.exists(path_input + "/" + movies_type[i] + "/" + file_name):
					time.sleep(1.0)
				number_of_files[i] += 1
				break
	 
	os.chdir(saved_path) # Change the current working directory back to the original path
	return number_of_files

def result(number_of_files):
	print(f"Total of files moved: {sum(number_of_files)}")
	for i in range(len(movies_type)):
		print(f"Total of {movies_type[i]} files moved: {number_of_files[i]}")
	
def main():
	path_input = input("Enter the path of the folder: ")
	misplaced_folder(path_input)
	number_of_files = move_files(path_input)
	result(number_of_files)
	
if __name__ == '__main__':
	main()