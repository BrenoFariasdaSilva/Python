import atexit # For playing a sound when the program finishes
import os # For running a command in the terminal
import platform # For getting the operating system name
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

# Input/Output Constants:
INPUT_FILE = "Free Games List.txt" # The input file name
OUTPUT_FILE = "Add Games Command.txt" # The output file name

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

# This functions reads the input file and sorts the games by what comes after the dash and space
def sort_games(input_file, output_file):
   games = {} # Dictionary of games

   # Read the input file
   with open(input_file, "r") as file:
      for line in file: # For each line in the file
         parts = line.strip().split(" - ") # Split the line into parts
         if len(parts) == 2: # If the length of the parts is 2
            game_name = parts[1] # Get the game
            appID = parts[0] # Get the appID
            if game_name in games: # If the game is in the games dictionary
               print(f"{BackgroundColors.RED}Duplicate game {BackgroundColors.CYAN}{game_name}{BackgroundColors.RED} found!{Style.RESET_ALL}") # Output the duplicate game message
            else: # If the game is not in the games dictionary
               games[game_name] = appID

   # Sort the games by the game name
   sorted_games = {k: v for k, v in sorted(games.items(), key=lambda item: item[0])}

   # Write the sorted games to the output file
   with open(output_file, "w") as file:
      for game_name, appID in sorted_games.items():
         file.write(f"{appID} - {game_name}\n")

   print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Games sorted and written to {BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}")

   return sorted_games # Return the sorted games

# This function generates ASF commands from the appids and writes them to the output file
def generate_asf_command(appids, output_file):
   # Generate ASF add commands
   asf_commands = ["!addlicense ASF a/" + ", a/".join(appids[i:i+50]) for i in range(0, len(appids), 50)]

   # Append ASF commands to the end of the input file
   with open(output_file, "w") as file:
      file.write("\n".join(asf_commands))

   print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}ASF commands generated and written to {BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}")

# This is the Main function
def main():
   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}ASF Command Generator{BackgroundColors.GREEN} program!{Style.RESET_ALL}\n") # Output the welcome message

   sorted_games = sort_games(INPUT_FILE, OUTPUT_FILE) # Sort the games
   appids = list(sorted_games.values())
   generate_asf_command(appids, OUTPUT_FILE) # Generate ASF commands

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output the end of the program message

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
	main() # Call the main function
