import os

def main():
   # ask user to enter paths to verify
	while True:
		path = input("Enter path to verify: ")
		if path == "exit":
			break
		
   
	
	for folder_name, subfolders, filenames in os.walk(path):
		# ignore the path that is already in the path
		if folder_name == path:
			continue
		if len(subfolders) > 0:
			print(f"Folder: {folder_name}")
			print(f"Subfolders: {subfolders}")
			print(f"Files: {filenames}")
			print()

if __name__ == '__main__':
	main()
	 