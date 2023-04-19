import os

def diff(paths):
	first_path = paths[0]
	second_path = paths[1]
 
	first_path_folders = os.listdir(first_path)
	second_path_folders = os.listdir(second_path)
 
	diff_folders = []
 
	for folder in first_path_folders:
		if folder not in second_path_folders:
			diff_folders.append(folder)
   
	return diff_folders

def main():
	paths = []
 
	for i in range(2):
		path = input("Enter path: ")
		paths.append(path)
  
	diff_folders = diff(paths)
 
	[ print(f"{diff_folders[i]}: not in {paths[2]}") for i in range(len(diff_folders)) ]

if __name__ == "__main__":
	main()