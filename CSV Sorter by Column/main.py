import atexit # For playing a sound when the program finishes
import csv # For reading and writing CSV files
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
SOUND_COMMANDS = {"Darwin": "afplay", "Linux": "aplay", "Windows": "start"}
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav" # The path to the sound file

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

# Function to sort CSV lines by a specific column
def sort_csv(input_file, sorting_column):
   print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Sorting CSV file {BackgroundColors.CYAN}{input_file}{BackgroundColors.GREEN} by column {BackgroundColors.CYAN}{sorting_column}{BackgroundColors.GREEN}...{Style.RESET_ALL}") # Output the sorting message

   # Open the CSV file
   with open(input_file, "r", newline="") as infile:
      reader = csv.reader(infile) # Create a CSV reader
      header = next(reader) # Read the header

      # Find the index of the sorting column
      sorting_column_index = header.index(sorting_column)

      # Sort the CSV lines based on the sorting column
      sorted_lines = sorted(reader, key=lambda x: x[sorting_column_index])

      return header, sorted_lines # Return the header and sorted lines

# Function to write the sorted CSV
def write_csv(output_file, header, sorted_lines):
   # Open the CSV file
   with open(output_file, "w", newline="") as outfile:
      writer = csv.writer(outfile) # Create a CSV writer

      # Write the header
      writer.writerow(header)

      # Write the sorted lines
      writer.writerows(sorted_lines)

   print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}CSV file {BackgroundColors.CYAN}{output_file}{BackgroundColors.GREEN} written.{Style.RESET_ALL}") # Output the writing message

# This is the Main function
def main():
   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the CSV Sorter by Specific Column program!{Style.RESET_ALL}", end="\n\n") # Output the welcome message

   # Input and output file names
   input_filename = "input.csv"
   output_filename = "sorted.csv"
   sorting_column = "Name"

   # Call the function to sort the CSV
   header, sorted_lines = sort_csv(input_filename, sorting_column)

   # Call the function to write the sorted CSV
   write_csv(output_filename, header, sorted_lines)

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output the end of the program message

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
	main() # Call the main function
