import requests # Import the requests library
from bs4 import BeautifulSoup # Import the BeautifulSoup library
import re # Import the regular expression library
from colorama import Style # For coloring the terminal

# Macros:
class backgroundColors: # Colors for the terminal
	CYAN = "\033[96m" # Cyan
	GREEN = "\033[92m" # Green
	YELLOW = "\033[93m" # Yellow
	RED = "\033[91m" # Red

INPUT_FILENAME = "URLs_list.txt" # Name of the text file containing the URLs
OUTPUT_FILENAME = "magnet_urls.csv" # Name of the CSV file to write the magnet links to

# This function creates a CSV file and returns it
def create_csv(filename):
	with open(filename, "w") as csv: # Open the file in write mode
		csv.writer("Counter, Magnet Links, Size\n") # Write the header of the CSV file
		# Get the csv writer object
		csv_object = csv.writer(csv)
	return csv_object

# This function open a file and return the URLs
def open_file(filename, mode):
	with open(filename, mode) as file: # Open the file in read mode
		urls = [line.strip() for line in file.readlines()] # Read all lines and remove trailing whitespaces
	return urls # Return the URLs

# This function process the URLs, extract magnet links and write them to a CSV file
def process_urls(urls, magnets_csv):
	# Iterate through the URLs and extract magnet links
	for url in urls:
		print(f"{backgroundColors.YELLOW}Processing {backgroundColors.CYAN}{url}{Style.RESET_ALL}")
		magnet_links = extract_magnet_links(url) # Extract magnet links from the URL
		if magnet_links:
			print(f"{backgroundColors.GREEN} Magnet links from {backgroundColors.CYAN}{url}{backgroundColors.GREEN}:{Style.RESET_ALL}")
			for i, magnet_link in enumerate(magnet_links):
				if i > 0:
					print(f"{backgroundColors.GREEN}{i+1}º{backgroundColors.CYAN}{magnet_link}{Style.RESET_ALL}")
					magnets_csv.writerow([i+1, magnet_link, ""]) # Write the magnet link to the CSV file

# This function extract magnet links from a given URL
def extract_magnet_links(url):
	try:
		# Send an HTTP GET request to the URL
		response = requests.get(url)

		# Check if the request was successful (status code 200)
		if response.status_code == 200:
			# Parse the HTML content of the page
			soup = BeautifulSoup(response.text, "html.parser")

			magnet_links = [] # List to store the magnet links
			# Find all href tags and extract magnet links using a regular expression
			for a in soup.find_all("a", href=True):
					href = a["href"]
					magnet_match = re.search(r"magnet:\?xt=urn:[a-z0-9:]+", href)
					if magnet_match:
						magnet_links.append(magnet_match.group())

			return magnet_links # Return the magnet links
		else: # If the request was not successful
			print(f"{backgroundColors.RED}Failed to retrieve content from {backgroundColors.CYAN}{url}{backgroundColors.RED}. Status code: {backgroundColors.CYAN}{response.status_code}{Style.RESET_ALL}")
			return [] # Return an empty list
	except Exception as e: # If an error occurred
		print(f"{backgroundColors.RED}An error occurred while processing {backgroundColors.CYAN}{url}{backgroundColors.RED}: {backgroundColors.CYAN}{str(e)}{Style.RESET_ALL}")
		return [] # Return an empty list

# This is the main function
def main():
	# Open the file in read mode
	urls = open_file(INPUT_FILENAME, "r")

	# Create CSV file
	magnets_csv = create_csv(OUTPUT_FILENAME)

	# Process the URLs, extract magnet links and write them to a CSV file
	process_urls(urls, magnets_csv)
	 
# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
	main() # Call the main() function
