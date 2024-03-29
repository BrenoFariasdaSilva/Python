from itertools import combinations # Import the combinations function from the itertools module
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
    
# Constants:
ATTRIBUTES = [
   "Age",
   "Gender",
   "Height",
   "Weight",
   "Hair Color",
   "Eye Color",
   "Skin Tone",
   "Ethnicity",
   "Nationality",
   "Income",
   "QI",
   "Occupation",
]

# This function outputs the attributes
def show_attributes(attributes):
   print(f"{BackgroundColors.GREEN}Attributes: {BackgroundColors.CYAN}{len(attributes)}{Style.RESET_ALL}")
   print(f"{BackgroundColors.CYAN}{attributes}{Style.RESET_ALL}")

# This function generates the non repetitive combinations
def generate_combinations(attributes):
   non_repetitive_combinations = [] # Non repetitive combinations
   # Loop through the range of 1 to the length of the attributes + 1
   for r in range(1, len(attributes) + 1):
      # Extend the non_repetitive_combinations with the combinations of the attributes and r
      non_repetitive_combinations.extend(combinations(attributes, r))
   
   # Convert the combinations to a list
   non_repetitive_combinations = [list(combination) for combination in non_repetitive_combinations]

   return non_repetitive_combinations # Return the non repetitive combinations

# This function saves the combinations to a file
def save_combinations_to_file(combinations, filename="non_repetitive_combinations.txt"):
   # Open the file
   with open(filename, "w") as file:
      for combination in combinations: # For each combination in the combinations
         file.write(f"{combination}\n") # Write the combination to the file

# This is the main function
def main():
   # Show the attributes
   show_attributes(ATTRIBUTES)

   # Generate the non repetitive combinations
   non_repetitive_combinations = generate_combinations(ATTRIBUTES)

   # Save the non repetitive combinations to a file
   save_combinations_to_file(non_repetitive_combinations)

   # Print the number of combinations
   print(f"{BackgroundColors.GREEN}Completed the generation of {BackgroundColors.CYAN}{len(non_repetitive_combinations)}{BackgroundColors.GREEN} combinations!{Style.RESET_ALL}")

# This is the standard boilerplate that calls the main() function
if __name__ == "__main__":
   main() # Call the main function
