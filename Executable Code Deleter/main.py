import os

executable_extensions = [".exe", ".o", ".pyc", ".pyo"] # Add more extensions if you want
exception_files = ["make.exe", "Make.exe", "Makefile", "makefile"] # Add more files if you want
ignore_folders = ["BusTracker", "UTFome"]

def main():
	path = "D:\Backup\Mega Sync\Code"
 
	# Check if path is a directory
	if os.path.isdir(path):
		file_list(path)
    
def file_list(path):
	# Iterate over all the files in directory
	for root, dirs, files in os.walk(path):
		# Check if the folder is an exception or if the current folder is a subfolder of an exception folder
		if os.path.basename(root) not in ignore_folders and not any(folder in root for folder in ignore_folders):
			for file in files:
				# Get the file extension
				file_extension = os.path.splitext(file)[1]
				# Check if the file is an executable file
				file_remover(root, file, file_extension)
   
def file_remover(root, file, file_extension):
	if file_extension in executable_extensions:
		# Check if the file is an exception
		if file not in exception_files:
			# Delete the file
			os.remove(os.path.join(root, file))
			print("Deleted: " + os.path.join(root, file))
   
if __name__ == "__main__":
   main()