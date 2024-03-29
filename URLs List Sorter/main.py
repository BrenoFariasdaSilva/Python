from colorama import Style # For coloring the terminal

# Macros:
class BackgroundColors: # Colors for the terminal
	CYAN = "\033[96m" # Cyan
	GREEN = "\033[92m" # Green
	YELLOW = "\033[93m" # Yellow
	RED = "\033[91m" # Red
	BOLD = "\033[1m" # Bold
	UNDERLINE = "\033[4m" # Underline
	CLEAR_TERMINAL = "\033[H\033[J" # Clear the terminal

INPUT_FILE = "URLs.txt" # Input file with the URLs
OUTPUT_FILE = "URLs.txt" # Output file with the sorted and cleaned URLs

# Description: This function reads a file with a list of URLs, remove the empty lines and the new line characters,
def sort_and_clean_urls():
	with open(INPUT_FILE, "r") as file: # Open the file with the URLs
		lines = file.readlines() # Read the lines of the file
		lines = [line.strip() for line in lines if line.strip()] # Remove the empty lines and the new line characters
		lines = [line[:line.rfind("/") + 1] + line[line.rfind("/") + 1:].title() for line in lines]
		lines.sort(key=lambda line: line[line.rfind("/") + 1:]) # Sort the URLs by the substring after the last slash until the end of the URL

	return lines # Return the sorted and cleaned URLs

# Description: This function receives a list of URLs and rewrite the file with the sorted and cleaned URLs
def rewrite_file(clean_urls):
	with open(OUTPUT_FILE, "w") as file: # Open the file with the URLs
		for url in clean_urls: # Iterate over the URLs
			file.write(url + '\n') # Write the URL to the file

# Description: 
def process_urls(clean_urls, url_substring_counts):
	for url in clean_urls: # Iterate over the URLs
		parts = url.split("/") # Split the URL by the slash character
		if len(parts) > 2: # Check if the URL has more than 2 parts
			substring = "/".join(parts[2:-1]) # Extract the substring between the second and the last slash
			
			# Increment the count of the extracted substring in the dictionary
			url_substring_counts[substring] = url_substring_counts.get(substring, 0) + 1

	return url_substring_counts # Return the dictionary with the extracted substrings and their counts

# Description: 
def show_repeated_substrings(url_substring_counts):
	# Filter and display the repeated substrings
	repeated_substrings = {substring: count for substring, count in url_substring_counts.items() if count > 1}
	for substring, count in repeated_substrings.items():
		print(f"{BackgroundColors.GREEN}Substring: {BackgroundColors.CYAN}{substring}{BackgroundColors.GREEN}, Count: {BackgroundColors.CYAN}{count}{Style.RESET_ALL}")
	return repeated_substrings

# Description: This is the main function.
def main():
	print(f"{BackgroundColors.GREEN}This program reads a file with a list of URLs, remove the empty lines and the new line characters, sort the URLs by the substring after the last slash until the end of the URL, extract the substring between the second and the last slash, count the repeated substrings and display them.{Style.RESET_ALL}")

	# Dictionary to store the extracted substrings and their counts
	url_substring_counts = {}

	# Sort and clean the URLs
	clean_urls = sort_and_clean_urls()

	# Rewrite the file with the sorted and cleaned URLs
	rewrite_file(clean_urls)

	# Process the sorted and cleaned URLs and count the repeated substrings
	url_substring_counts = process_urls(clean_urls, url_substring_counts)

	# Filter and display the repeated substrings
	show_repeated_substrings(url_substring_counts)

	print(f"{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}")

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
   main() # Call the main function
