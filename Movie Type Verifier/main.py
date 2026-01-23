"""
================================================================================
Movie Type Verifier
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-01-23
Description :
    This script verifies that movies are correctly placed in their respective
    language/type directories. It checks if movies are in the correct folder
    based on their names and generates a JSON report of misplaced items.

    Key features include:
        - Automatic verification of movie placement based on naming conventions
        - Detection of misplaced movies across language directories
        - Identification of movies without proper tags
        - JSON report generation with relative paths
        - Optional auto-fix functionality to move misplaced movies
        - Logging system with colored terminal output

Usage:
    1. Set the INPUT_DIR constant to the directory containing movie folders.
    2. Optionally enable AUTO_FIX to automatically move misplaced movies.
    3. Run the script:
        $ make run   or   $ python main.py

Outputs:
    - movie_verification_report.json — JSON report with misplaced and unfound movies
    - Unfound Tags/ — Directory for movies without proper tags (if AUTO_FIX is enabled)
    - Logs/main.log — Execution log file

TODOs:
    - Add support for custom tag definitions
    - Implement dry-run mode to preview changes before moving
    - Add statistics summary to the report

Dependencies:
    - Python >= 3.8
    - colorama
    - pathlib
    - json
    - shutil

Assumptions & Notes:
    - Input directory contains subdirectories: Dual, Dublado, English, Legendado, Nacional
    - Movies are stored as directories (not files)
    - Movie names should contain the appropriate tag (e.g., "Movie.Name.2024.Dual")
    - Paths in JSON report are relative to INPUT_DIR
"""

import atexit  # For playing a sound when the program finishes
import datetime  # For getting the current date and time
import json  # For generating JSON reports
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import shutil  # For moving directories
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
AUTO_FIX = True  # Set to True to automatically move misplaced movies
INPUT_DIR = r"E:\Movies"  # The root directory containing the movie type folders

# Movie Type Directories:
MOVIE_TYPES = ["Dual", "Dublado", "English", "Legendado", "Nacional"]

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


def calculate_execution_time(start_time, finish_time):
    """
    Calculates the execution time between start and finish times and formats it as hh:mm:ss.

    :param start_time: The start datetime object
    :param finish_time: The finish datetime object
    :return: String formatted as hh:mm:ss representing the execution time
    """

    delta = finish_time - start_time  # Calculate the time difference
    hours, remainder = divmod(delta.seconds, 3600)  # Calculate the hours, minutes and seconds
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


def get_relative_path(full_path, base_path):
    """
    Get the relative path from the base path.

    :param full_path: The full path to convert
    :param base_path: The base path to calculate relative from
    :return: Relative path as string
    """

    try:
        return str(Path(full_path).relative_to(Path(base_path)))
    except ValueError:
        return full_path


def detect_movie_type(movie_name):
    """
    Detect which movie type tag is present in the movie name.

    :param movie_name: The name of the movie directory
    :return: The detected movie type or None if not found
    """

    movie_name_upper = movie_name.upper()  # Convert to uppercase for case-insensitive comparison

    for movie_type in MOVIE_TYPES:
        if movie_type.upper() in movie_name_upper:
            return movie_type

    return None  # No tag found


def verify_directory_structure():
    """
    Verify that all required movie type directories exist.

    :return: True if all directories exist, False otherwise
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Verifying directory structure at: {BackgroundColors.CYAN}{INPUT_DIR}{Style.RESET_ALL}"
    )

    if not verify_filepath_exists(INPUT_DIR):
        print(
            f"{BackgroundColors.RED}Error: Input directory {BackgroundColors.CYAN}{INPUT_DIR}{BackgroundColors.RED} does not exist!{Style.RESET_ALL}"
        )
        return False

    missing_dirs = []
    for movie_type in MOVIE_TYPES:
        type_dir = os.path.join(INPUT_DIR, movie_type)
        if not verify_filepath_exists(type_dir):
            missing_dirs.append(movie_type)

    if missing_dirs:
        print(
            f"{BackgroundColors.YELLOW}Warning: Missing directories: {BackgroundColors.CYAN}{', '.join(missing_dirs)}{Style.RESET_ALL}"
        )
        return False

    verbose_output(
        f"{BackgroundColors.GREEN}All required directories found!{Style.RESET_ALL}"
    )
    return True


def scan_movies_in_directory(type_dir, expected_type):
    """
    Scan movies in a specific type directory and identify misplaced ones.

    :param type_dir: The directory to scan
    :param expected_type: The expected movie type for this directory
    :return: Dictionary with 'correct', 'misplaced', and 'unfound' movies
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Scanning directory: {BackgroundColors.CYAN}{type_dir}{Style.RESET_ALL}"
    )

    results = {
        "correct": [],
        "misplaced": [],
        "unfound": []
    }

    if not os.path.exists(type_dir):
        return results

    try:
        items = os.listdir(type_dir)
    except PermissionError:
        print(
            f"{BackgroundColors.RED}Error: Permission denied accessing {BackgroundColors.CYAN}{type_dir}{Style.RESET_ALL}"
        )
        return results

    for item in items:
        item_path = os.path.join(type_dir, item)

        # Only check directories (movies are stored as directories)
        if not os.path.isdir(item_path):
            continue

        detected_type = detect_movie_type(item)

        if detected_type is None:
            # No tag found
            results["unfound"].append({
                "name": item,
                "path": get_relative_path(item_path, INPUT_DIR),
                "current_location": expected_type
            })
            verbose_output(
                f"{BackgroundColors.YELLOW}  - Unfound tag: {BackgroundColors.CYAN}{item}{Style.RESET_ALL}"
            )
        elif detected_type != expected_type:
            # Wrong directory
            results["misplaced"].append({
                "name": item,
                "path": get_relative_path(item_path, INPUT_DIR),
                "detected_type": detected_type,
                "current_location": expected_type,
                "should_be_in": detected_type
            })
            verbose_output(
                f"{BackgroundColors.RED}  - Misplaced: {BackgroundColors.CYAN}{item}{BackgroundColors.RED} (found in {expected_type}, should be in {detected_type}){Style.RESET_ALL}"
            )
        else:
            # Correct placement
            results["correct"].append(item)
            verbose_output(
                f"{BackgroundColors.GREEN}  - Correct: {BackgroundColors.CYAN}{item}{Style.RESET_ALL}"
            )

    return results


def move_movie(movie_info, destination_type):
    """
    Move a movie directory to the correct location.

    :param movie_info: Dictionary containing movie information (path, name, etc.)
    :param destination_type: The destination directory type
    :return: True if successful, False otherwise
    """

    source_path = os.path.join(INPUT_DIR, movie_info["path"])
    dest_dir = os.path.join(INPUT_DIR, destination_type)
    dest_path = os.path.join(dest_dir, movie_info["name"])

    try:
        if not os.path.exists(dest_dir):
            os.makedirs(dest_dir, exist_ok=True)

        if os.path.exists(dest_path):
            print(
                f"{BackgroundColors.YELLOW}Warning: Destination already exists: {BackgroundColors.CYAN}{dest_path}{Style.RESET_ALL}"
            )
            return False

        shutil.move(source_path, dest_path)
        print(
            f"{BackgroundColors.GREEN}Moved: {BackgroundColors.CYAN}{movie_info['name']}{BackgroundColors.GREEN} -> {BackgroundColors.CYAN}{destination_type}/{Style.RESET_ALL}"
        )
        return True
    except Exception as e:
        print(
            f"{BackgroundColors.RED}Error moving {BackgroundColors.CYAN}{movie_info['name']}{BackgroundColors.RED}: {str(e)}{Style.RESET_ALL}"
        )
        return False


def apply_auto_fix(misplaced_movies, unfound_movies):
    """
    Automatically move misplaced and unfound movies to their correct locations.

    :param misplaced_movies: List of misplaced movies
    :param unfound_movies: List of movies without tags
    :return: Dictionary with fix results
    """

    print(
        f"\n{BackgroundColors.BOLD}{BackgroundColors.YELLOW}AUTO_FIX enabled: Moving misplaced movies...{Style.RESET_ALL}\n"
    )

    results = {
        "misplaced_fixed": 0,
        "misplaced_failed": 0,
        "unfound_moved": 0,
        "unfound_failed": 0
    }

    # Fix misplaced movies
    for movie in misplaced_movies:
        if move_movie(movie, movie["should_be_in"]):
            results["misplaced_fixed"] += 1
        else:
            results["misplaced_failed"] += 1

    # Move unfound movies to "Unfound Tags" directory
    unfound_dir = "Unfound Tags"
    for movie in unfound_movies:
        if move_movie(movie, unfound_dir):
            results["unfound_moved"] += 1
        else:
            results["unfound_failed"] += 1

    return results


def generate_report(all_misplaced, all_unfound):
    """
    Generate a JSON report of the verification results.

    :param all_misplaced: List of all misplaced movies
    :param all_unfound: List of all movies without proper tags
    :return: None
    """

    report = {
        "scan_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "input_directory": INPUT_DIR,
        "auto_fix_enabled": AUTO_FIX,
        "summary": {
            "total_misplaced": len(all_misplaced),
            "total_unfound": len(all_unfound),
            "total_issues": len(all_misplaced) + len(all_unfound)
        },
        "misplaced_movies": all_misplaced,
        "unfound_tags": all_unfound
    }

    report_filename = "movie_verification_report.json"

    try:
        with open(report_filename, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=4, ensure_ascii=False)

        print(
            f"\n{BackgroundColors.GREEN}Report generated: {BackgroundColors.CYAN}{report_filename}{Style.RESET_ALL}"
        )
        print(
            f"{BackgroundColors.GREEN}Total issues found: {BackgroundColors.CYAN}{report['summary']['total_issues']}{Style.RESET_ALL}"
        )
        print(
            f"{BackgroundColors.GREEN}  - Misplaced movies: {BackgroundColors.CYAN}{report['summary']['total_misplaced']}{Style.RESET_ALL}"
        )
        print(
            f"{BackgroundColors.GREEN}  - Unfound tags: {BackgroundColors.CYAN}{report['summary']['total_unfound']}{Style.RESET_ALL}"
        )

    except Exception as e:
        print(
            f"{BackgroundColors.RED}Error generating report: {str(e)}{Style.RESET_ALL}"
        )


def verify_movies():
    """
    Main verification function that scans all movie directories.

    :return: None
    """

    print(
        f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Starting movie type verification...{Style.RESET_ALL}\n"
    )

    # Verify directory structure
    if not verify_directory_structure():
        print(
            f"{BackgroundColors.RED}Verification cannot proceed. Please check the directory structure.{Style.RESET_ALL}"
        )
        return

    all_misplaced = []
    all_unfound = []
    total_correct = 0

    # Scan each movie type directory
    for movie_type in MOVIE_TYPES:
        type_dir = os.path.join(INPUT_DIR, movie_type)
        print(
            f"\n{BackgroundColors.BOLD}{BackgroundColors.CYAN}Checking {movie_type} directory...{Style.RESET_ALL}"
        )

        results = scan_movies_in_directory(type_dir, movie_type)

        total_correct += len(results["correct"])
        all_misplaced.extend(results["misplaced"])
        all_unfound.extend(results["unfound"])

        print(
            f"{BackgroundColors.GREEN}  Found: {len(results['correct'])} correct, {len(results['misplaced'])} misplaced, {len(results['unfound'])} unfound{Style.RESET_ALL}"
        )

    # Apply auto-fix if enabled
    if AUTO_FIX and (all_misplaced or all_unfound):
        fix_results = apply_auto_fix(all_misplaced, all_unfound)

        print(
            f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Auto-fix results:{Style.RESET_ALL}"
        )
        print(
            f"{BackgroundColors.GREEN}  - Misplaced movies fixed: {BackgroundColors.CYAN}{fix_results['misplaced_fixed']}{Style.RESET_ALL}"
        )
        print(
            f"{BackgroundColors.GREEN}  - Misplaced movies failed: {BackgroundColors.CYAN}{fix_results['misplaced_failed']}{Style.RESET_ALL}"
        )
        print(
            f"{BackgroundColors.GREEN}  - Unfound movies moved: {BackgroundColors.CYAN}{fix_results['unfound_moved']}{Style.RESET_ALL}"
        )
        print(
            f"{BackgroundColors.GREEN}  - Unfound movies failed: {BackgroundColors.CYAN}{fix_results['unfound_failed']}{Style.RESET_ALL}"
        )

        # Regenerate lists after moving (only include failed moves)
        if AUTO_FIX:
            # Clear lists since movies were moved
            all_misplaced = []
            all_unfound = []

    # Generate JSON report
    generate_report(all_misplaced, all_unfound)

    # Final summary
    print(
        f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Verification Summary:{Style.RESET_ALL}"
    )
    print(
        f"{BackgroundColors.GREEN}  - Total correctly placed: {BackgroundColors.CYAN}{total_correct}{Style.RESET_ALL}"
    )
    print(
        f"{BackgroundColors.GREEN}  - Total misplaced: {BackgroundColors.CYAN}{len(all_misplaced)}{Style.RESET_ALL}"
    )
    print(
        f"{BackgroundColors.GREEN}  - Total unfound tags: {BackgroundColors.CYAN}{len(all_unfound)}{Style.RESET_ALL}"
    )


def main():
    """
    Main function.

    :param: None
    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Movie Type Verifier{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the welcome message
    start_time = datetime.datetime.now()  # Get the start time of the program

    # Display configuration
    print(
        f"{BackgroundColors.BOLD}{BackgroundColors.CYAN}Configuration:{Style.RESET_ALL}"
    )
    print(
        f"{BackgroundColors.GREEN}  - Input Directory: {BackgroundColors.CYAN}{INPUT_DIR}{Style.RESET_ALL}"
    )
    print(
        f"{BackgroundColors.GREEN}  - Auto-Fix: {BackgroundColors.CYAN}{AUTO_FIX}{Style.RESET_ALL}"
    )
    print(
        f"{BackgroundColors.GREEN}  - Verbose: {BackgroundColors.CYAN}{VERBOSE}{Style.RESET_ALL}"
    )
    print()

    # Run the verification
    verify_movies()

    finish_time = datetime.datetime.now()  # Get the finish time of the program
    print(
        f"\n{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"
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
