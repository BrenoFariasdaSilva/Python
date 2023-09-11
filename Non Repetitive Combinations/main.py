from itertools import combinations # For generating combinations
from colorama import Style # For coloring the terminal

# Macros:
class backgroundColors: # Colors for the terminal
	CYAN = "\033[96m" # Cyan
	GREEN = "\033[92m" # Green
	YELLOW = "\033[93m" # Yellow
	RED = "\033[91m" # Red

# List of attributes
attributes = [
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

# Print the attributes list
print(f"{backgroundColors.GREEN}Attributes: {backgroundColors.CYAN}{len(attributes)}{Style.RESET_ALL}")
print(f"{backgroundColors.CYAN}{attributes}{Style.RESET_ALL}")

# Generate non-repetitive combinations
non_repetitive_combinations = [] # List of non-repetitive combinations

# Loop the number of attributes, increasing the number of attributes per combination
for r in range(1, len(attributes) + 1): 
    # Extend (add) the combinations to the list of non-repetitive combinations
    non_repetitive_combinations.extend(combinations(attributes, r))

# Convert the combinations to lists for readability
non_repetitive_combinations = [list(combination) for combination in non_repetitive_combinations]


# Save the combinations to a file
with open("non_repetitive_combinations.txt", "w") as file:
    for combination in non_repetitive_combinations:
        file.write(f"{combination}\n")

print(f"{backgroundColors.GREEN}Completed the generation of {backgroundColors.CYAN}{len(non_repetitive_combinations)}{backgroundColors.GREEN} combinations!{Style.RESET_ALL}")