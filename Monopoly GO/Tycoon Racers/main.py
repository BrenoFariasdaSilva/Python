import atexit # For playing a sound when the program finishes
import os # For running a command in the terminal
import platform # For getting the operating system name
from colorama import init, Fore, Style # For coloring the terminal
from itertools import permutations # For generating permutations of team positions

# Initialize colorama
init(autoreset=True) # Autoreset colors after each print

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

def play_sound():
   """
   Plays a sound when the program finishes.

   :return: None
   """

   if os.path.exists(SOUND_FILE):
      if platform.system() in SOUND_COMMANDS: # If the platform.system() is in the SOUND_COMMANDS dictionary
         os.system(f"{SOUND_COMMANDS[platform.system()]} {SOUND_FILE}")
      else: # If the platform.system() is not in the SOUND_COMMANDS dictionary
         print(f"{BackgroundColors.RED}The {BackgroundColors.CYAN}platform.system(){BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}")
   else: # If the sound file does not exist
      print(f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}")

# Register the function to play a sound when the program finishes
atexit.register(play_sound)

# Function to calculate total points based on race results
def calculate_total_points(initial_points, race2_positions, race3_positions):
   normal_points = [10, 8, 7, 5] # Points for normal races
   double_points = [2 * points for points in normal_points] # Points for double points race
   total_points = initial_points.copy()

   # Add points from race 2
   for i, team in enumerate(race2_positions):
      total_points[team] += normal_points[i]

   # Add points from race 3 (double points)
   for i, team in enumerate(race3_positions):
      total_points[team] += double_points[i]

   return total_points

# Function to filter winning cases where user's team has the highest score
def filter_winning_cases(winning_cases, user_team):
   filtered_cases = []

   for case in winning_cases:
      _, _, _, user_team_points = case
      if all(user_team_points >= other_points for _, _, _, other_points in winning_cases):
         filtered_cases.append(case)

   return filtered_cases

# Function to determine if races have happened
def determine_happened_races(race1_positions, race2_positions):
   happened_races = [True if race1_positions else False, True if race2_positions else False]
   return happened_races

# Function to calculate initial points from race results
def calculate_initial_points(race1_positions):
   initial_points = {
      "yellow": 0,
      "blue": 0,
      "red": 0,
      "purple": 0
   }

   if race1_positions:
      for i, team in enumerate(race1_positions):
         initial_points[team] += [10, 8, 7, 5][i]

   return initial_points

# Function to generate permutations of team positions for races
def generate_permutations():
   teams = ["yellow", "blue", "red", "purple"]
   permutations_positions = list(permutations(teams))
   return permutations_positions

# Function to evaluate winning cases based on permutations and initial points
def evaluate_winning_cases(permutations_positions, initial_points, race1_positions, race2_positions, user_team):
   winning_cases = []

   for race2_perm in (permutations_positions if not race2_positions else [tuple(race2_positions)]):
      for race3_perm in permutations_positions:
         total_points = calculate_total_points(initial_points, race2_perm, race3_perm)

         max_points = max(total_points.values())
         teams_with_max_points = [team for team, points in total_points.items() if points == max_points]

         if user_team in teams_with_max_points:
            sorted_teams = sorted(teams_with_max_points, key=lambda team: total_points[team], reverse=True)
            if sorted_teams[0] == user_team:
               winning_cases.append((tuple(race1_positions), race2_perm, race3_perm, total_points[user_team]))

   return winning_cases

# Function to display results
def display_results(winning_cases, happened_races, user_team):
   for case in winning_cases:
      race1_positions, race2_positions, race3_positions, user_team_points = case
      output = f"{BackgroundColors.CYAN}{user_team.capitalize()}{BackgroundColors.GREEN} won with {BackgroundColors.CYAN}{user_team_points}{BackgroundColors.GREEN} points. "

      if not happened_races[0]:
         output += f"\n{BackgroundColors.GREEN}Race 1 positions: {BackgroundColors.CYAN}{race1_positions}{BackgroundColors.GREEN}, "
      if not happened_races[1]:
         output += f"{BackgroundColors.GREEN}Race 2 positions: {BackgroundColors.CYAN}{race2_positions}{BackgroundColors.GREEN}, "

      output += f"{BackgroundColors.GREEN}Race 3 positions: {BackgroundColors.CYAN}{race3_positions}{BackgroundColors.GREEN}"
      print(output)

# Main function orchestrating the entire program
def main():
   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}Welcome to the {BackgroundColors.CYAN}Tyccon Racers Results Calculation Program{BackgroundColors.GREEN}!{Style.RESET_ALL}\n")

   # Default user team
   user_team = "yellow"

   # Race results (for demonstration, replace with actual input)
   race1_positions = ["yellow", "blue", "red", "purple"]
   race2_positions = ["red", "yellow", "purple", "blue"]

   # Determine which races have happened
   happened_races = determine_happened_races(race1_positions, race2_positions)

   # Calculate initial points from race 1
   initial_points = calculate_initial_points(race1_positions)

   # Generate permutations of team positions for races 2 and 3
   permutations_positions = generate_permutations()

   # Evaluate winning cases based on permutations and initial points
   winning_cases = evaluate_winning_cases(permutations_positions, initial_points, race1_positions, race2_positions, user_team)

   # Filter winning cases to keep only where user's team has the highest score
   winning_cases = filter_winning_cases(winning_cases, user_team)

   # Sort winning cases by the points of the user's team in descending order
   winning_cases = sorted(winning_cases, key=lambda x: x[3], reverse=True)

   # Display the results
   display_results(winning_cases, happened_races, user_team)

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}")

if __name__ == "__main__":
   """
   This is the standard boilerplate that calls the main() function.

   :return: None
   """

   main() # Call the main function
