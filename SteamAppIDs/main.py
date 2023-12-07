# This program extracts the appids from the Steam URL file and writes them to a text file.

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

# This function reads the URL file and returns the lines
def read_url_file(file_path):
   # Read the URL file
   with open(file_path, encoding="utf8") as file:
      lines = file.readlines() # Read the lines
   return lines # Return the lines

# This function extracts the appids from the lines
def extract_appids(lines, start_string, end_string, stop_string, play_games_limit):
   total_games_found = 0 # Total games found
   appids = [] # List of appids

   # Extract the appids from the lines
   for line in lines:
      start = line.find(start_string) # Find the start string
      end = line.find(end_string) # Find the end string

      if start != -1 and end != -1: # If the start and end strings are found
         total_games_found += 1 # Increment the total games found
         appid = line[start + len(start_string):end] # Extract the appid
         appids.append(appid) # Append the appid to the list

         # If the total games found is equal to the play games limit
         if total_games_found % play_games_limit == 0 and total_games_found != 1:
               yield ",".join(appids) # Yield the appids
               appids = [] # Reset the list of appids

      # If the stop string is found
      if line.find(stop_string) != -1:
         break # Break the loop

   return total_games_found # Return the total games found

# This function writes the appids to a file
def write_appids_to_file(appids, file_path):
   with open(file_path, "w") as appids_file: # Open the file
      appids_file.write("\n".join(appids)) # Write the appids to the file

# This is the main function
def main():
   url_file_path = "url.txt"
   appids_file_path = "appid.txt"
   start_string = '<a href="https://steamcommunity.com/app/'
   end_string = '">'
   stop_string = '>12.0h<'
   play_games_limit = 32

   # Read the URL file
   lines = read_url_file(url_file_path)
   # Extract the appids from the lines
   total_games_found = extract_appids(lines, start_string, end_string, stop_string, play_games_limit)

   # Print the total games found
   if total_games_found > 0:
      print(f"{BackgroundColors.GREEN}Total Games Found: {BackgroundColors.CYAN}{total_games_found}{Style.RESET_ALL}")
   else:
      print(f"{BackgroundColors.GREEN}No games found in the provided URL file.{Style.RESET_ALL}")

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
	main() # Call the main function
