import html2text
from urllib.request import urlopen

def user_input():
	print(f"Choose type of input:")
	print(f"1. Paste URL here")
	print(f"2. Insert URL on code")
 
	url = "https://www.google.com" # Default url
	option = int(input("Selected Input: "))
	
	while option != 1 and option != 2:
		print("Invalid option. Try again.")
  
	if option == 1:
		url = input("Enter a URL: ")
	elif option == 2: # If you choose the option "2" you need to change the url variable on the next line
		url = "https://github.com/BrenoFariasdaSilva/Word2Vector"

	return url

def get_html_file(url):
	html_file = urlopen(url) # open the url
	html_as_text = html_file.read() # read the html file
	return html_as_text

def search_string(string):
	start_substring = "Algorithm i'm studying" # insert here the string that starts the text
	end_substring = "json file." # insert here the string that ends the text
 
	start = string.find(start_substring)
	end = string.find(end_substring)
	substring = string[start:end+len(end_substring)]
	return substring

def main():
	url = user_input() # get the url from the user input
	html_file = get_html_file(url) # get the html file from the url
	text_as_string = html2text.html2text(html_file.decode("utf-8"))
	substring = search_string(text_as_string)
 
	# command to clear the terminal
	print("\033[H\033[J")
 
	print (f"{substring}")

if __name__ == "__main__":
	main()