import html2text  # For convert html to text
from urllib.request import urlopen  # For open the url
from colorama import Style  # For coloring the terminal


# Macros:
class BackgroundColors:  # Colors for the terminal
    CYAN = "\033[96m"  # Cyan
    GREEN = "\033[92m"  # Green
    YELLOW = "\033[93m"  # Yellow
    RED = "\033[91m"  # Red
    BOLD = "\033[1m"  # Bold
    UNDERLINE = "\033[4m"  # Underline
    CLEAR_TERMINAL = "\033[H\033[J"  # Clear the terminal


# This function get the url from the user input
def user_input():
    print(f"{BackgroundColors.GREEN}Choose type of input:{Style.RESET_ALL}")
    print(f"{BackgroundColors.GREEN}1. Paste URL here{Style.RESET_ALL}")
    print(f"{BackgroundColors.GREEN}2. Insert URL on code{Style.RESET_ALL}")

    url = "https://www.google.com"  # Default url
    option = int(
        input(f"{BackgroundColors.GREEN}Selected Input: {Style.RESET_ALL}")
    )  # Get the option from the user input

    # Check if the option is valid
    while option != 1 and option != 2:
        print(f"{BackgroundColors.YELLOW}Invalid option. Try again.{Style.RESET_ALL}")

        # Check the option
    if option == 1:
        url = input(f"{BackgroundColors.GREEN}Enter a URL: {Style.RESET_ALL}")
    elif option == 2:  # If you choose the option "2" you need to change the url variable on the next line
        url = "https://github.com/BrenoFariasdaSilva/Word2Vector"

    return url  # Return the url


# This function get the html file from the url
def get_html_file(url):
    html_file = urlopen(url)  # Open the url
    html_as_text = html_file.read()  # Read the html file

    return html_as_text  # Return the html file


# This function search the string on the html file
def search_string(string):
    start_substring = "Algorithm i'm studying"  # Insert here the string that starts the text
    end_substring = "json file."  # Insert here the string that ends the text

    # Get the start and end index of the substring
    start = string.find(start_substring)
    end = string.find(end_substring)
    substring = string[start : end + len(end_substring)]

    return substring  # Return the substring


# This is the main function
def main():
    url = user_input()  # get the url from the user input
    html_file = get_html_file(url)  # get the html file from the url
    text_as_string = html2text.html2text(html_file.decode("utf-8"))
    substring = search_string(text_as_string)

    # Command to clear the terminal
    print(f"{BackgroundColors.CLEAR_TERMINAL}")

    print(f"{BackgroundColors.CYAN}{substring}{Style.RESET_ALL}")  # Print the Substring


# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
    main()  # Call the main function
