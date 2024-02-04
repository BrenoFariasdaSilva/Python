import atexit # For playing a sound when the program finishes
import csv # For reading and writing CSV files
import os # For running a command in the terminal
import platform # For getting the operating system name
import requests # For making HTTP requests
import xml.etree.ElementTree as ET # For parsing XML
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

# Sound Constants:
SOUND_COMMANDS = {"Darwin": "afplay", "Linux": "aplay", "Windows": "start"} # The commands to play a sound for each operating system
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav" # The path to the sound file

# Data Constants:
STEAM_ACCOUNTS = ["BrenoVicioGamer", "BrenoVicioEurope", "ParzivalPsycho"]

# Output Constants:
OUTPUT_DIRECTORY = "Steam Games"

# Functions:

# This function creates a directory if it does not exist
def create_directories(directory_name):
	if not os.path.exists(directory_name): # If the directory does not exist
		os.makedirs(directory_name) # Create the directory

# This function downloads the XML file from the Steam Community
def download_xml(steam_account):
	url = f"https://steamcommunity.com/id/{steam_account}/games?xml=1" # The URL to download the XML file
	response = requests.get(url) # Send a GET request to the URL

	if response.status_code == 200: # If the request was successful (status code 200 - OK)
		return response.text # Return the content of the response
	else: # If the request was not successful
		raise Exception(f"{BackgroundColors.RED}Failed to {BackgroundColors.CYAN}{steam_account}{BackgroundColors.RED} download XML. Status code: {BackgroundColors.YELLOW}{response.status_code}{Style.RESET_ALL}") # Raise an exception

# This function gets the game list from the XML content
def get_game_list(xml_content):
	root = ET.fromstring(xml_content) # Parse the XML content
	games = root.findall(".//games/game") # Find all the games in the XML content

	total_games = 0 # The number of total games
	game_info = [] # The list of game information
	
	for game in games: # For each game in the list of games
		app_name_element = game.find("name") # Find the name of the game
		app_id_element = game.find("appID") # Find the AppID of the game
		hours_played_element = game.find("hoursOnRecord") # Find the hours played of the game

      # Verify if the app_name and app_id elements are not None
		if app_name_element is not None and app_id_element is not None:
			total_games += 1 # Increment the number of total games
			app_name = app_name_element.text # Get the name of the game
			app_id = app_id_element.text # Get the AppID of the game
			
			if hours_played_element is not None: # If the hours played element is not None, get the hours played
					hours_played = float(hours_played_element.text.replace(",", "")) # Get the hours played of the game
					game_info.append({"appName": app_name, "appID": app_id, "hoursPlayed": hours_played}) # Append the game information to the list
			else: # If the hours played element is None, append the game information with 0 hours played
					game_info.append({"appName": app_name, "appID": app_id, "hoursPlayed": 0})

	# Sort game_info list in descending order based on hours played
	game_info.sort(key=lambda x: x["hoursPlayed"], reverse=True)

	if total_games != len(game_info): # If the number of total games and the length of the game info list do not match, print a warning
		print(f"{BackgroundColors.RED}Warning: Total Games {BackgroundColors.CYAN}({total_games}){BackgroundColors.RED} and Gathered Games {BackgroundColors.CYAN}({len(game_info)}){BackgroundColors.RED} do not match!{Style.RESET_ALL}")

	return game_info # Return the list of game information

# This function creates a CSV file with the game list
def create_csv(game_list, csv_filename):
	# Open the CSV file in write mode
	with open(csv_filename, mode="w", newline="", encoding="utf-8") as file:
		fieldnames = ["Number", "Game Name", "AppID", "Hours Played"] # The field names for the CSV file
		writer = csv.DictWriter(file, fieldnames=fieldnames) # Create a CSV writer
		
		writer.writeheader() # Write the header to the CSV file
		for index, game in enumerate(game_list, start=1): # For each game in the list of games
			# Write the game information to the CSV file
			writer.writerow({"Number": index, "Game Name": game["appName"], "AppID": game["appID"], "Hours Played": game["hoursPlayed"]})

# This function defines the command to play a sound when the program finishes
def play_sound():
   if os.path.exists(SOUND_FILE):
      if platform.system() in SOUND_COMMANDS: # If the platform.system() is in the SOUND_COMMANDS dictionary
         os.system(f"{SOUND_COMMANDS[platform.system()]} {SOUND_FILE}")
      else: # If the platform.system() is not in the SOUND_COMMANDS dictionary
         print(f"{BackgroundColors.RED}The {BackgroundColors.CYAN}platform.system(){BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}")
   else: # If the sound file does not exist
      print(f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}")

# Register the function to play a sound when the program finishes
atexit.register(play_sound)

# This is the Main function
def main():
   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Steam AppIDs{BackgroundColors.GREEN} program!{Style.RESET_ALL}\n") # Output the welcome message

   create_directories(OUTPUT_DIRECTORY) # Create the output directory

   for steam_account in STEAM_ACCOUNTS: # For each Steam account in the list of Steam accounts
      xml_filename = f"{OUTPUT_DIRECTORY}/{steam_account}-Games.xml" # The XML filename
      csv_filename = f"{OUTPUT_DIRECTORY}/{steam_account}-Games.csv" # The CSV filename

      try: # Try to download the XML file and create the CSV file
         xml_content = download_xml(steam_account) # Download the XML file
         with open(xml_filename, "w", encoding="utf-8") as xml_file: # Open the XML file in write mode
            xml_file.write(xml_content) # Write the XML content to the file

         games_list = get_game_list(xml_content) # Get the game list from the XML content
         create_csv(games_list, csv_filename) # Create the CSV file with the game list
               
         os.remove(xml_filename) # Delete the XML file

         print(f"{BackgroundColors.GREEN}Downloaded and created {BackgroundColors.CYAN}{csv_filename}{BackgroundColors.GREEN} with {BackgroundColors.CYAN}{len(games_list)}{BackgroundColors.GREEN} games.{Style.RESET_ALL}") # Output the success message
      except Exception as e: # If an exception occurs
         print(f"{BackgroundColors.RED}Error: {BackgroundColors.CYAN}{e}{Style.RESET_ALL}") # Output the error message

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output the end of the program message

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
	main() # Call the main function
