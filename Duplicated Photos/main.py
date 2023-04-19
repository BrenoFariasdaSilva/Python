# Create a program that ask for path input
# and then get all the files in that path and check if there are duplicates, if there are, then delete them
# and then print the number of duplicates deleted
# example of how to delete if there are duplicates:
# if the file name is "20220808_111303(1)", and there is another file with the name "20220808_111303", then delete the file with the name "20220808_111303(1)"

# Status: Uncompleted 
import os

def main():
   path = input("Enter the path: ")
   
   if os.path.exists(path):
      get_files(path)
   
def get_files(path):
	# get all the files in the path
	files = os.listdir(path)
	check_duplicates(files)

def check_duplicates(files):
	# check if there are duplicates
	# if there are, then delete them
	# and then print the number of duplicates deleted	
	duplicates = 0
	for file in files:
		# if in the end of the file name there is ({any number inside here}), then delete it
		if file.endswith(")") and file.find("(") != -1:
			os.remove(file)
			duplicates += 1
 