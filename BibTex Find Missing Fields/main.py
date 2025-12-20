"""
================================================================================
BibTex Find Missing Fields
================================================================================
Author      : Breno Farias da Silva
Created     : 2025-11-03
Description :
   This script analyzes a BibTeX file and detects entries missing required fields.
   It allows the user to define which fields should be checked for completeness
   (e.g., author, title, year), helping ensure bibliographic consistency.

   Key features include:
      - Automatic parsing of BibTeX entries
      - Generic field validation through a configurable constant
      - Clear reporting of missing fields per entry
      - Lightweight and portable (no external dependencies)
      - Integration-ready with publication management systems

Usage:
   1. Update the variable `bibtex_file` with the path to your `.bib` file.
   2. Define which fields to validate in the `FIELDS` constant.
   3. Run the script via terminal:
         $ python detect_missing_fields.py
   4. The script will print which entries are missing any of the specified fields.

Outputs:
   - Console output listing entries and their missing fields.

TODOs:
   - Add CLI argument parsing for BibTeX file path and fields
   - Add optional export to text or CSV for missing entries
   - Extend parsing robustness for edge-case BibTeX formats
   - Integrate into continuous reference validation pipelines

Dependencies:
   - Python >= 3.8
   - re (standard library)

Assumptions & Notes:
   - Input file must follow valid BibTeX syntax.
   - Script assumes each entry starts with "@" and follows standard formatting.
   - Designed for macOS, Linux, and Windows systems.
   - Uses ANSI terminal colors for improved readability.

"""

import atexit  # For playing a sound when the program finishes
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For regular expression parsing of BibTeX entries
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


# Execution Constants:
VERBOSE = False  # Set to True to output verbose messages

# Sound Constants:
SOUND_COMMANDS = {
    "Darwin": "afplay",
    "Linux": "aplay",
    "Windows": "start",
}  # The commands to play a sound for each operating system
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav"  # The path to the sound file

# RUN_FUNCTIONS:
RUN_FUNCTIONS = {
    "Play Sound": True,  # Set to True to play a sound when the program finishes
}

# Validation Constants:
FIELDS = ["author", "title", "year"]  # Fields to check for completeness in each BibTeX entry

# Functions Definitions:


def verbose_output(true_string="", false_string=""):
    """
    Outputs a message if the VERBOSE constant is set to True.

    :param true_string: The string to be outputted if the VERBOSE constant is set to True.
    :param false_string: The string to be outputted if the VERBOSE constant is set to False.
    :return: None
    """

    if VERBOSE and true_string != "":  # If the VERBOSE constant is set to True and the true_string is set
        print(true_string)  # Output the true statement string
    elif false_string != "":  # If the false_string is set
        print(false_string)  # Output the false statement string


def verify_filepath_exists(filepath):
    """
    Verify if a file or folder exists at the specified path.

    :param filepath: Path to the file or folder
    :return: True if the file or folder exists, False otherwise
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}"
    )  # Output the verbose message

    return os.path.exists(filepath)  # Return True if the file or folder exists, False otherwise


def play_sound():
    """
    Plays a sound when the program finishes and skips if the operating system is Windows.

    :param: None
    :return: None
    """

    current_os = platform.system()  # Get the current operating system
    if current_os == "Windows":  # If the current operating system is Windows
        return  # Do nothing

    if verify_filepath_exists(SOUND_FILE):  # If the sound file exists
        if current_os in SOUND_COMMANDS:  # If the platform.system() is in the SOUND_COMMANDS dictionary
            os.system(f"{SOUND_COMMANDS[current_os]} {SOUND_FILE}")  # Play the sound
        else:  # If the platform.system() is not in the SOUND_COMMANDS dictionary
            print(
                f"{BackgroundColors.RED}The {BackgroundColors.CYAN}{current_os}{BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}"
            )
    else:  # If the sound file does not exist
        print(
            f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}"
        )


def detect_missing_fields(bibtex_file):
    """
    Detect entries in a BibTeX file that are missing any of the specified fields.

    :param bibtex_file: Path to the BibTeX (.bib) file
    :return: None
    """

    if not verify_filepath_exists(bibtex_file):  # Check if the provided file exists
        print(
            f"{BackgroundColors.RED}Error: File not found at path {BackgroundColors.CYAN}{bibtex_file}{Style.RESET_ALL}"
        )
        return

    with open(bibtex_file, "r", encoding="utf-8") as file:  # Open the file for reading
        bibtex_content = file.read()  # Read the content of the file

    entries = re.split(r"@", bibtex_content)[1:]  # Split the file into entries, ignoring the first empty split
    missing_field_entries = {}  # Dictionary to store entries and their missing fields

    for entry in entries:  # Iterate through each BibTeX entry
        missing_fields = []  # List of missing fields for this entry
        for field in FIELDS:  # Check each required field
            if field.lower() not in entry.lower():  # If the field is missing
                missing_fields.append(field)

        if missing_fields:  # If any fields are missing
            match = re.search(r"(\w+)\s*{([^,]+),", entry)  # Extract entry type and citation key
            if match:
                entry_type, citation_key = match.groups()  # Get entry type and key
                missing_field_entries[f"{entry_type} {citation_key}"] = missing_fields

    if missing_field_entries:  # If there are entries with missing fields
        print(f"{BackgroundColors.YELLOW}Entries missing required fields:{Style.RESET_ALL}")
        for entry, fields in missing_field_entries.items():
            print(
                f" - {BackgroundColors.CYAN}{entry}{Style.RESET_ALL}: missing {BackgroundColors.RED}{", ".join(fields)}{Style.RESET_ALL}"
            )
    else:
        print(
            f"{BackgroundColors.GREEN}All entries contain the required fields: {BackgroundColors.CYAN}{", ".join(FIELDS)}{Style.RESET_ALL}"
        )


def main():
    """
    Main function.

    :param: None
    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}BibTex Find Missing Fields{BackgroundColors.GREEN}!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the welcome message

    bibtex_file = "main.bib"  # Replace with your BibTeX file path
    detect_missing_fields(bibtex_file)  # Run the detection function

    print(
        f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
    )  # Output the end of the program message

    (
        atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None
    )  # Register the play_sound function to be called when the program finishes


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
