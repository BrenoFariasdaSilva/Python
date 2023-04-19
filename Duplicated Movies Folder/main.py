# Create a program that ask for path input
# and then get all the folders in the path and save it in a list
# and then print the number of duplicates deleted and the name of the duplicated folders

# Status: Uncompleted 
import os

def main():
   path = input("Enter the path: ")
   
   if os.path.exists(path):
      get_files(path)
   
def get_files(path):
	# get all the files in the path and save it in a list
	# and then check if there are duplicates
	files = os.listdir(path)
	check_duplicates(files)

def check_duplicates(files):
	duplicates = 0
	for file in files:
		if files.count(file) > 1:
			duplicates += 1
			print(file)
   
if __name__ == "__main__":
	main()