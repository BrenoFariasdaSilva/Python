import atexit # For playing a sound when the program finishes
import os # For running a command in the terminal
import platform # For getting the operating system name
import re # For regular expressions
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

# Functions:

# This function removes duplicated blank lines from the given content
def remove_duplicated_blank_lines(content):
   # This regex replaces two or more newline characters with just two
   return re.sub(r"\n{3,}", "\n\n", content)

# This function removes duplicate Makefile rules, keeping only the first occurrence
def remove_duplicate_rules(content):
   lines = content.split("\n") # Split the content into lines
   seen_rules = set() # Create a set to store the rules that have been seen
   new_lines = [] # Create a list to store the new lines
   for line in lines: # For each line in the content
      # Identify potential Makefile rules (simplified detection)
      match = re.match(r"^([a-zA-Z0-9_-]+):.*", line)
      if match: # If the line is a potential Makefile rule
         rule_name = match.group(1) # Get the name of the rule
         if rule_name not in seen_rules: # If the rule has not been seen
            seen_rules.add(rule_name) # Add the rule to the set of seen rules
            new_lines.append(line) # Add the line to the list of new lines
         else: # If the rule has been seen
            new_lines.append(line) # Add the line to the list of new lines
   return "\n".join(new_lines), seen_rules # Return the new content and the set of seen rules

# This function extracts the original "all" rule dependencies from the given content
def extract_original_all_dependencies(content):
   match = re.search(r"^all: (.*)$", content, re.MULTILINE)
   if match: # If the "all" rule is found
      return match.group(1).strip().split() # Return the dependencies of the "all" rule
   return [] # Return an empty list if the "all" rule is not found

# This function updates the contents of a Makefile to use a Python virtual environment
def update_makefile_contents(original_content):
   if "VENV :=" in original_content:
      return original_content # Return as is if venv setup is present

   venv_setup = """# Name of the virtual environment directory
VENV := venv
# Python command to use
PYTHON := python3

$(VENV)/bin/activate:
\t$(PYTHON) -m venv $(VENV)
\t$(VENV)/bin/pip install --upgrade pip
\ttouch $(VENV)/bin/activate

"""

   # Extract the original "all" rule dependencies
   original_all_dependencies = extract_original_all_dependencies(original_content)

   # Update the Makefile content
   modified_content = venv_setup + re.sub(r"\bpip install", "$(VENV)/bin/pip install", original_content)
   modified_content = re.sub(r"\bpython3\b", "$(VENV)/bin/python", modified_content)

   # Remove duplicate rules and get the set of rule names
   no_duplicate_content, rule_names = remove_duplicate_rules(modified_content)
   all_dependencies = "venv " + " ".join(original_all_dependencies)
   phony_line = ".PHONY: " + " ".join(rule_names | set(original_all_dependencies))

   # Reconstruct the "all" rule with its original dependencies
   all_rule_pattern = re.compile(r"^all:.*$", re.MULTILINE)
   if all_rule_pattern.search(no_duplicate_content):
      no_duplicate_content = all_rule_pattern.sub(f"all: {all_dependencies}", no_duplicate_content)
   else:
      no_duplicate_content = f"all: {all_dependencies}\n" + no_duplicate_content

   final_content = f"{phony_line}\n{no_duplicate_content}"
   final_content = remove_duplicated_blank_lines(final_content)

   return final_content # Return the final content

# This function updates the given Makefile to use a Python virtual environment
def update_makefile(makefile_path):
   with open(makefile_path, "r") as file: # Open the Makefile for reading
      original_content = file.read() # Read the contents of the Makefile

   updated_content = update_makefile_contents(original_content) # Update the contents of the Makefile
   
   if updated_content != original_content: # Only write if changes were made
      with open(makefile_path, "w") as file: # Open the Makefile for writing
         file.write(updated_content) # Write the updated contents to the Makefile
      return True # Return True if changes were made
   return False # Return False if no changes were made

# This function finds and modifies all Makefiles in the current directory and its subdirectories
def find_makefiles(start_dir):
   modified_files = 0 # The number of modified files
   # Walk through the directory and its subdirectories
   for root, dirs, files in os.walk(start_dir):
      for name in files: # For each file in the directory
         if name.lower() == "makefile": # If the file is a Makefile
            full_path = os.path.join(root, name) # Get the full path of the Makefile
            if update_makefile(full_path): # If the Makefile was updated
               modified_files += 1
   print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Modified {modified_files} Makefiles.{Style.RESET_ALL}") # Output the number of modified files

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
   print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Makefile Venv Adder{BackgroundColors.GREEN} program!{Style.RESET_ALL}", end="\n\n") # Output the welcome message

   current_directory = os.getcwd() # Get the current directory
   find_makefiles(current_directory) # Find and modify all Makefiles in the current directory and its subdirectories

   print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}") # Output the end of the program message

# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
	main() # Call the main function
