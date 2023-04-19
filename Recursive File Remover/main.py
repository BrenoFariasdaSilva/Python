# create a program that ask for a path.
# Inside that path, the program will enter every folder and subfolder and will search for a file and will delete it.

import os 

def deleteDesktopIni(path, filename):
	for folderName, subfolders, filenames in os.walk(path):
		for filename in filenames:
			if filename == 'desktop.ini':
					os.remove(os.path.join(folderName, filename))
		
def main():
	path = input('Enter the path: ')
	filename = input('Enter the filename: ')
	deleteDesktopIni(path, filename)
  
if __name__ == '__main__':
	main()