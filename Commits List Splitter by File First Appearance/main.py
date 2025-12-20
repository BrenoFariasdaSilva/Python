"""
================================================================================
Commits List Splitter by File First Appearance
================================================================================
Author      : Breno Farias da Silva
Created     : 2025-12-12
Description :
   Splits a commits-list CSV into multiple CSV files, one per filename
   referenced in the "Files Changed" column. Output CSVs are created in the
   order of first appearance of each file in the input list. Supports fnmatch
   wildcard tracking and ignore patterns.

   Key features include:
      - Parse commits CSV and extract and normalize "Files Changed" entries
      - Filter files using `FILES_TO_TRACK` and `FILES_TO_IGNORE` patterns
      - Produce ordered CSVs named "{counter}-{sanitized_filename}.csv"
      - Preserve original CSV field order (uses `FIELDNAMES`) in outputs
      - Optional verbose logging, colored terminal output, execution time
        measurement, and end-of-run sound notification

Usage:
   1. Update constants at the top of the file: `INPUT_CSV`, `OUTPUT_DIR`,
      `FILES_TO_TRACK`, `FILES_TO_IGNORE`, and `FIELDNAMES`.
   2. Run:
         $ python main.py
   3. Outputs are written to `OUTPUT_DIR` with filenames like:
         1-dataset_descriptor.py.csv

Defaults:
   - `INPUT_CSV` default: "output/DDoS-Detector-commits_list.csv"
   - `OUTPUT_DIR` default: "output/split_by_file"
   - `FIELDNAMES` default: ["Commit Number", "Commit Hash", "Commit Date",
       "Commit Message", "Files Changed"]
   - `FILES_TO_TRACK` default: ["*.py"]
   - `FILES_TO_IGNORE` default: []

TODOs:
   - Add CLI arguments parsing (input, output dir, patterns, verbose)
   - Support alternate input separators and quoted/escaped filenames
   - Add dry-run mode and verbosity levels
   - Add unit tests for parsing and pattern matching

Dependencies:
   - Python >= 3.8
   - colorama
   - Logger.py (project-local Logger implementation)
   - Standard library modules: csv, os, re, fnmatch, datetime, atexit,
     platform, sys, pathlib

Assumptions & Notes:
   - Input CSV must contain a "Files Changed" column; file lists may be
     separated by commas, semicolons or spaces. Entries are normalized
     and filtered using `normalize_file_list` and `should_track`.
   - If `FILES_TO_TRACK` is empty, all files are considered except those
     matching `FILES_TO_IGNORE`.
   - Output filenames are sanitized via `sanitize_filename` to be filesystem-safe.
"""

import atexit  # For playing a sound when the program finishes
import csv  # For reading and writing CSV files
import datetime  # For getting the current date and time
import fnmatch  # For wildcard pattern matching
import os  # For running a command in the terminal and file operations
import platform  # For getting the operating system name
import re  # For sanitizing filenames
import sys  # For system-specific parameters and functions
from colorama import Style  # For coloring the terminal
from Logger import Logger  # For logging output to both terminal and file
from pathlib import Path  # For handling file paths


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

# File Paths:
INPUT_CSV = "output/DDoS-Detector-commits_list.csv"  # Input CSV file path
OUTPUT_DIR = "output/split_by_file"  # Output directory for the split CSV files

# File Structure:
FIELDNAMES = [
    "Commit Number",
    "Commit Hash",
    "Commit Date",
    "Commit Message",
    "Files Changed",
]  # List of field names for the CSV files

# File Tracking Patterns:
FILES_TO_TRACK = ["*.py"]  # List of file patterns to track (fnmatch). Empty list means track all files.
FILES_TO_IGNORE = []  # List of file patterns to ignore (fnmatch). Empty list means ignore no files.

os.makedirs(OUTPUT_DIR, exist_ok=True)  # Ensure output directory exists

# Logger Setup:
logger = Logger(f"./Logs/{Path(__file__).stem}.log", clean=True)  # Create a Logger instance
sys.stdout = logger  # Redirect stdout to the logger
sys.stderr = logger  # Redirect stderr to the logger

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


def normalize_file_list(raw):
    """
    Normalize the Files Changed field into a list of file paths/names.

    :param raw: raw string from CSV "Files Changed"
    :return: list of file names (strings)
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Normalizing file list from raw string: {BackgroundColors.CYAN}{raw}{Style.RESET_ALL}"
    )  # Output the verbose message

    if not raw:  # If the raw string is empty
        return []  # Return an empty list

    raw = raw.replace(";", ",").replace(" ", ",")  # Normalize separators to commas
    parts = [p.strip() for p in raw.split(",")]  # Split and strip whitespace

    return [p for p in parts if p]  # Return non-empty parts


def file_matches_any(filename, patterns):
    """
    True if filename matches any pattern in the list using fnmatch.
    Supports matching against full path and basename.

    :param filename: file path or name
    :param patterns: list of fnmatch patterns or exact names
    :return: True/False
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Checking if file '{BackgroundColors.CYAN}{filename}{BackgroundColors.GREEN}' matches any of the patterns: {BackgroundColors.CYAN}{patterns}{Style.RESET_ALL}"
    )  # Output the verbose message

    if not patterns:  # If no patterns provided, match all
        return True  # Return True

    filename_lc = filename.lower()  # Lowercase filename for case-insensitive matching
    base = os.path.basename(filename_lc)  # Get the basename

    for pattern in patterns:  # Check each pattern
        pattern = pattern.lower().strip()  # Lowercase and strip pattern
        if not pattern:  # Skip empty patterns
            continue  # Continue to next pattern

        if fnmatch.fnmatch(filename_lc, pattern):  # Match full path
            return True  # Return True
        if fnmatch.fnmatch(base, pattern):  # Match basename
            return True  # Return True

    return False  # No patterns matched


def should_track(filename):
    """
    Apply FILES_TO_TRACK and FILES_TO_IGNORE logic.

    :param filename: file path or name
    :return: True if file should be tracked, False otherwise
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Determining if file '{BackgroundColors.CYAN}{filename}{BackgroundColors.GREEN}' should be tracked based on patterns.{Style.RESET_ALL}"
    )  # Output the verbose message

    filename_lc = filename.lower()  # Lowercase filename for case-insensitive matching

    if FILES_TO_IGNORE and file_matches_any(filename_lc, FILES_TO_IGNORE):  # Check ignore patterns
        return False  # Return False

    if FILES_TO_TRACK:  # Check track patterns
        return file_matches_any(filename_lc, FILES_TO_TRACK)  # Return True/False based on track patterns

    return True  # If no track patterns, track all files


def sanitize_filename(name):
    """
    Sanitize a filename to be safe for filesystem use.

    :param name: original file string
    :return: sanitized filename
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Sanitizing filename: {BackgroundColors.CYAN}{name}{Style.RESET_ALL}"
    )  # Output the verbose message

    return re.sub(r"[^A-Za-z0-9._-]", "_", name)  # Replace unsafe characters with underscores


def write_commits_to_csv(out_path, commits, fieldnames=FIELDNAMES):
    """
    Write a list of commit rows to a CSV file.

    :param out_path: path to output CSV
    :param commits: iterable of commit dicts
    :param fieldnames: list of CSV fieldnames
    :return: None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Writing {len(commits)} commits to CSV: {BackgroundColors.CYAN}{out_path}{Style.RESET_ALL}"
    )  # Log the action

    with open(out_path, "w", newline="", encoding="utf-8") as out:  # Open the output CSV file
        writer = csv.DictWriter(out, fieldnames=fieldnames)  # Create a CSV DictWriter
        writer.writeheader()  # Write the header row
        for commit in commits:  # Iterate through each commit for this file
            writer.writerow(commit)  # Write the commit row to the output CSV


def split_commits_by_first_file_appearance(csv_path):
    """
    Parse the commits CSV and split commits into per-file CSVs following the
    first-appearance ordering rule.

    :param csv_path: path to input CSV
    :return: list of files in first-appearance order
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Splitting commits by first file appearance from CSV: {BackgroundColors.CYAN}{csv_path}{Style.RESET_ALL}"
    )  # Output the verbose message

    file_to_commits = {}  # Mapping of file to list of commits
    file_order = []  # List of files in first-appearance order

    with open(csv_path, newline="", encoding="utf-8") as f:  # Open the input CSV file
        reader = csv.DictReader(f)  # Create a CSV DictReader

        for row in reader:  # Iterate through each row in the CSV
            changed_files = normalize_file_list(row["Files Changed"])  # Normalize the "Files Changed" field

            filtered_files = [ff for ff in changed_files if should_track(ff)]  # Apply tracking/ignoring logic

            for file in filtered_files:  # Iterate through each filtered file
                if file not in file_to_commits:  # If the file is seen for the first time
                    file_to_commits[file] = []  # Initialize the list of commits for this file
                    file_order.append(file)  # Record the first appearance order

                file_to_commits[file].append(row)  # Append the commit row to the file's list

    counter = 1  # Initialize counter for output files
    for file in file_order:  # Iterate through files in first-appearance order
        sanitized = sanitize_filename(file)  # Sanitize the filename
        out_path = os.path.join(OUTPUT_DIR, f"{counter}-{sanitized}.csv")  # Create the output file path

        write_commits_to_csv(out_path, file_to_commits[file], FIELDNAMES)  # Write the commits to the output CSV

        counter += 1  # Increment the counter for the next output file

    return file_order, file_to_commits  # Return the list of files and the mapping of file to commits


def calculate_execution_time(start_time, finish_time):
    """
    Calculates the execution time between start and finish times and formats it as hh:mm:ss.

    :param start_time: The start datetime object
    :param finish_time: The finish datetime object
    :return: String formatted as hh:mm:ss representing the execution time
    """

    delta = finish_time - start_time  # Calculate the time difference
    hours, remainder = divmod(int(delta.total_seconds()), 3600)  # Calculate the hours, minutes and seconds
    minutes, seconds = divmod(remainder, 60)  # Calculate the minutes and seconds
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"  # Format the execution time


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


def main():
    """
    Main function.

    :param: None
    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Commits List Splitter by File First Appearance{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the welcome message
    print(
        f"{BackgroundColors.GREEN}You can generate the commits list using the {BackgroundColors.CYAN}Commits List from Repository{BackgroundColors.GREEN} program.{Style.RESET_ALL}\n"
    )  # Output the information message

    start_time = datetime.datetime.now()  # Get the start time of the program

    if not verify_filepath_exists(INPUT_CSV):  # Ensure input exists
        print(
            f"{BackgroundColors.RED}Input CSV not found: {BackgroundColors.CYAN}{INPUT_CSV}{BackgroundColors.RED}{Style.RESET_ALL}"
        )
        print(
            f"{BackgroundColors.RED}Please make sure to generate the commits list using the {BackgroundColors.CYAN}Commits List from Repository{BackgroundColors.RED} program before running this script.{Style.RESET_ALL}"
        )
        return  # Exit the program

    files, file_to_commits = split_commits_by_first_file_appearance(INPUT_CSV)  # Split commits by first file appearance

    if not files:
        print(
            f"{BackgroundColors.YELLOW}No files matched the tracking criteria. No CSV files were created.{Style.RESET_ALL}"
        )  # Output no files created message
        return  # Exit the program

    print(f"{BackgroundColors.GREEN}Created CSV files for:{Style.RESET_ALL}")
    for idx, f in enumerate(files, 1):  # Iterate through files with their first-appearance index
        commits = file_to_commits[f]  # Get the list of commits for this file
        first_commit = commits[0]  # Get the first commit for this file

        commit_number = first_commit["Commit Number"]  # Get commit number
        commit_date = first_commit["Commit Date"]  # Get commit date
        commit_hash = first_commit["Commit Hash"]  # Get commit hash
        commit_message = first_commit["Commit Message"]  # Get commit message

        print(
            f"{BackgroundColors.CYAN}{idx}. {BackgroundColors.GREEN}{f} {BackgroundColors.CYAN}- {commit_number} - {commit_date} - {commit_hash} {BackgroundColors.GREEN}- {commit_message}{Style.RESET_ALL}"
        )

    print()  # New line for better readability

    finish_time = datetime.datetime.now()  # Get the finish time of the program
    print(
        f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"
    )  # Output the start and finish times
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
