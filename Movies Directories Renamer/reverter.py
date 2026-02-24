"""
================================================================================
Reverter — Revert Movie Directory Renames from TMDb Report
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-02-24
Description :
    This script reverts directory and video-file renames previously applied by
    the Movie Directories Renamer. It reads the `movies_renaming_report.json`
    produced by the renamer run and attempts to restore original names when
    possible, handling common edge cases such as missing files or destination
    conflicts.

    Key features include:
        - Safe rename operations with conflict detection and counters
        - Support for reverting both directory-level and video-file renames
        - Detailed summary output and exit status for human inspection
        - Logger integration for persistent run logs

Usage:
    1. Ensure `movies_renaming_report.json` exists in the project root (generated
       by the renamer run).
    2. Run the reverter script:
        $ python reverter.py
    3. Review console output and `Logs/` for details of reverted and skipped
       entries.

Outputs:
    - Console summary of reverted operations and counts
    - Log file under `./Logs/reverter.log` (see Logger configuration)

TODOs:
    - Add a dry-run mode to preview changes without touching the filesystem
    - Add CLI flags to target a specific input root from the report
    - Improve heuristics for resolving ambiguous file locations

Dependencies:
    - Python >= 3.9
    - colorama
    - A project-local `Logger` utility (used to persist console output)

Assumptions & Notes:
    - The report file path is set by the `REPORT_PATH` constant in this file.
    - The script does not attempt to re-create missing files; it only renames
        existing filesystem entries when they can be resolved from the report.
"""

import atexit  # For playing a sound when the program finishes
import datetime  # For getting the current date and time
import json  # For handling JSON files
import os  # For running a command in the terminal
import platform  # For getting the operating system name
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

REPORT_PATH = r"./movies_renaming_report.json"  # The path to the report file

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

    if VERBOSE and true_string != "":  # If VERBOSE is True and a true_string was provided
        print(true_string)  # Output the true statement string
    elif false_string != "":  # If a false_string was provided
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


def increment_counter(counters, key):
    """
    Increment A Specific Counter Key.

    :param counters: Counters Dictionary
    :param key: Counter Key
    :return: None
    """
    
    counters[key] += 1  # Increment requested counter


def print_skip_not_found(path):
    """
    Print Not Found Skip Message.

    :param path: Missing Path
    :return: None
    """
    
    print(f"[SKIP] Not Found: {path}")  # Print missing message


def print_skip_conflict(path):
    """
    Print Destination Conflict Message.

    :param path: Destination Path
    :return: None
    """
    
    print(f"[SKIP] Destination Already Exists: {path}")  # Print conflict message


def print_reverted(src_path, dst_path):
    """
    Print Successful Revert Message.

    :param src_path: Source Path
    :param dst_path: Destination Path
    :return: None
    """
    
    print(f"[OK] Reverted: {src_path} -> {dst_path}")  # Print success message


def handle_missing_source(src_path, dst_path, counters):
    """
    Handle Missing Source Scenario.

    :param src_path: Source Path
    :param dst_path: Destination Path
    :param counters: Counters Dictionary
    :return: True if handled, False otherwise
    """
    
    if os.path.exists(dst_path):  # Check already reverted case
        increment_counter(counters, "already_reverted")  # Increment already reverted
        return True  # Signal handled

    increment_counter(counters, "missing")  # Increment missing counter
    print_skip_not_found(src_path)  # Print missing message
    
    return True  # Signal handled


def handle_destination_conflict(dst_path, counters):
    """
    Handle Destination Already Existing.

    :param dst_path: Destination Path
    :param counters: Counters Dictionary
    :return: True if handled, False otherwise
    """
    
    increment_counter(counters, "conflicts")  # Increment conflicts
    print_skip_conflict(dst_path)  # Print conflict message
    
    return True  # Signal handled


def perform_rename(src_path, dst_path, counters):
    """
    Execute Rename Operation.

    :param src_path: Source Path
    :param dst_path: Destination Path
    :param counters: Counters Dictionary
    :return: True if handled, False otherwise
    """
    
    os.rename(src_path, dst_path)  # Perform filesystem rename
    increment_counter(counters, "reverted_now")  # Increment reverted counter
    print_reverted(src_path, dst_path)  # Print success message
    
    return True  # Signal handled


def safe_rename(src_path, dst_path, counters):
    """
    Safely Rename A File Or Directory From Source To Destination.

    :param src_path: Full Path Of The Current (Wrong) Name
    :param dst_path: Full Path Of The Original (Old) Name
    :param counters: Dictionary Tracking Stats
    :return: True if the rename was handled (either performed or skipped), False otherwise
    """
    
    if not os.path.exists(src_path):  # Check if source exists
        return handle_missing_source(src_path, dst_path, counters)  # Delegate missing handling

    if os.path.exists(dst_path):  # Prevent overwrite
        return handle_destination_conflict(dst_path, counters)  # Delegate conflict handling

    return perform_rename(src_path, dst_path, counters)  # Perform actual rename


def report_exists():
    """
    Verify Report File Exists.
    
    :param: None
    :return: True if the report file exists, False otherwise
    """
    
    exists = os.path.exists(REPORT_PATH)  # Check report file existence
    
    if not exists:  # If missing
        print(f"[ERROR] Report Not Found: {REPORT_PATH}")  # Print error
        
    return exists  # Return existence flag


def load_report_file():
    """
    Load Report JSON File.
    
    :param: None
    :return: Parsed Report Data As A Dictionary
    """
    
    with open(REPORT_PATH, "r", encoding="utf-8") as f:  # Open report file
        report = json.load(f)  # Parse JSON
    
    return report  # Return report data


def initialize_counters():
    """
    Initialize Counters Dictionary.
    
    :param: None
    :return: Initialized Counters Dictionary
    """
    
    counters = {  # Initialize counters
        "expected": 0,  # Total expected operations
        "reverted_now": 0,  # Successfully reverted now
        "already_reverted": 0,  # Already reverted previously
        "missing": 0,  # Missing entries
        "conflicts": 0,  # Destination conflicts
    }  # End dictionary
    return counters  # Return counters


def normalize_base_dir(base_dir):
    """
    Normalize Base Directory Path.
    
    :param base_dir: Base Directory Path
    :return: Normalized Base Directory Path
    """
    
    return base_dir.replace("\\", "/")  # Normalize slashes


def update_expected_counter(counters, video_logs, dir_logs):
    """
    Update Expected Counter Based On Logs.
    
    :param counters: Counters Dictionary
    :param video_logs: List Of Video File Log Entries
    :param dir_logs: List Of Directory Log Entries
    :return: None
    """
    
    counters["expected"] += len(video_logs) + len(dir_logs)  # Add expected operations


def resolve_video_file_entry(base_dir, file_entry, dir_logs, counters):
    """
    Resolve And Revert A Single Video File Entry.
    
    :param base_dir: Base Directory Path
    :param file_entry: Video File Log Entry
    :param dir_logs: List Of Directory Log Entries
    :param counters: Counters Dictionary
    :return: None
    """
    
    old_name = file_entry.get("old_name")  # Extract old name
    new_name = file_entry.get("new_name")  # Extract new name

    if not old_name or not new_name:  # Validate names
        return  # Skip invalid entries

    for dir_entry in dir_logs:  # Iterate directory logs
        old_dir = dir_entry.get("old_name")  # Extract old directory
        new_dir = dir_entry.get("new_name")  # Extract new directory

        if not old_dir or not new_dir:  # Validate directory names
            continue  # Skip invalid

        src_path = os.path.join(base_dir, new_dir, new_name)  # Case 1 source
        dst_path = os.path.join(base_dir, old_dir, old_name)  # Case 1 destination

        if os.path.exists(src_path) or os.path.exists(dst_path):  # Check case 1
            safe_rename(src_path, dst_path, counters)  # Attempt revert
            return  # Stop after handled

        src_path = os.path.join(base_dir, old_dir, new_name)  # Case 2 source
        dst_path = os.path.join(base_dir, old_dir, old_name)  # Case 2 destination

        if os.path.exists(src_path) or os.path.exists(dst_path):  # Check case 2
            safe_rename(src_path, dst_path, counters)  # Attempt revert
            return  # Stop after handled

    src_path = os.path.join(base_dir, new_name)  # Fallback source
    dst_path = os.path.join(base_dir, old_name)  # Fallback destination

    if os.path.exists(src_path) or os.path.exists(dst_path):  # Check fallback
        safe_rename(src_path, dst_path, counters)  # Attempt revert
        return  # Stop after handled

    increment_counter(counters, "missing")  # Increment missing
    print(f"[SKIP] Unresolved Entry: {new_name}")  # Print unresolved


def revert_directory_entry(base_dir, dir_entry, counters):
    """
    Revert A Single Directory Entry.
    
    :param base_dir: Base Directory Path
    :param dir_entry: Directory Log Entry
    :param counters: Counters Dictionary
    :return: None
    """
    
    old_name = dir_entry.get("old_name")  # Extract old name
    new_name = dir_entry.get("new_name")  # Extract new name

    if not old_name or not new_name:  # Validate names
        return  # Skip invalid entries

    src_path = os.path.join(base_dir, new_name)  # Build source path
    dst_path = os.path.join(base_dir, old_name)  # Build destination path

    safe_rename(src_path, dst_path, counters)  # Attempt revert


def print_summary(counters):
    """
    Print Final Summary Report.
    
    :param counters: Counters Dictionary
    :return: None
    """
    
    print("\n========== SUMMARY ==========")  # Print header
    print(f"Expected Operations : {counters['expected']}")  # Print expected
    print(f"Reverted Now        : {counters['reverted_now']}")  # Print reverted now
    print(f"Already Reverted    : {counters['already_reverted']}")  # Print already reverted
    print(f"Missing             : {counters['missing']}")  # Print missing
    print(f"Conflicts           : {counters['conflicts']}")  # Print conflicts

    verified_total = counters["reverted_now"] + counters["already_reverted"]  # Compute verified total

    print(f"\nVerified Total      : {verified_total}")  # Print verified total

    if verified_total == counters["expected"]:  # Compare totals
        print("Status              : OK — Nothing Missing")  # Print OK status
    else:
        print("Status              : WARNING — Mismatch Detected")  # Print warning status


def revert_changes():
    """
    Revert All Renames Based On The Report File.
    
    :param: None
    :return: None
    """
    
    if not report_exists():  # Validate report file
        return  # Abort if missing

    report = load_report_file()  # Load report JSON
    input_dirs = report.get("input_dirs", {})  # Extract input dirs
    counters = initialize_counters()  # Initialize counters

    for base_dir, data in input_dirs.items():  # Iterate base directories
        base_dir = normalize_base_dir(base_dir)  # Normalize path

        video_logs = data.get("video_files_renamed", [])  # Extract video logs
        dir_logs = data.get("directories_modified", [])  # Extract directory logs

        update_expected_counter(counters, video_logs, dir_logs)  # Update expected counter

        for file_entry in video_logs:  # Process video entries
            resolve_video_file_entry(base_dir, file_entry, dir_logs, counters)  # Resolve file revert

        for dir_entry in dir_logs:  # Process directory entries
            revert_directory_entry(base_dir, dir_entry, counters)  # Revert directory

    print_summary(counters)  # Print final summary


def to_seconds(obj):
    """
    Converts various time-like objects to seconds.
    
    :param obj: The object to convert (can be int, float, timedelta, datetime, etc.)
    :return: The equivalent time in seconds as a float, or None if conversion fails
    """
    
    if obj is None:  # None can't be converted
        return None  # Signal failure to convert
    if isinstance(obj, (int, float)):  # Already numeric (seconds or timestamp)
        return float(obj)  # Return as float seconds
    if hasattr(obj, "total_seconds"):  # Timedelta-like objects
        try:  # Attempt to call total_seconds()
            return float(obj.total_seconds())  # Use the total_seconds() method
        except Exception:
            pass  # Fallthrough on error
    if hasattr(obj, "timestamp"):  # Datetime-like objects
        try:  # Attempt to call timestamp()
            return float(obj.timestamp())  # Use timestamp() to get seconds since epoch
        except Exception:
            pass  # Fallthrough on error
    return None  # Couldn't convert


def calculate_execution_time(start_time, finish_time=None):
    """
    Calculates the execution time and returns a human-readable string.

    Accepts either:
    - Two datetimes/timedeltas: `calculate_execution_time(start, finish)`
    - A single timedelta or numeric seconds: `calculate_execution_time(delta)`
    - Two numeric timestamps (seconds): `calculate_execution_time(start_s, finish_s)`

    Returns a string like "1h 2m 3s".
    """

    if finish_time is None:  # Single-argument mode: start_time already represents duration or seconds
        total_seconds = to_seconds(start_time)  # Try to convert provided value to seconds
        if total_seconds is None:  # Conversion failed
            try:  # Attempt numeric coercion
                total_seconds = float(start_time)  # Attempt numeric coercion
            except Exception:
                total_seconds = 0.0  # Fallback to zero
    else:  # Two-argument mode: Compute difference finish_time - start_time
        st = to_seconds(start_time)  # Convert start to seconds if possible
        ft = to_seconds(finish_time)  # Convert finish to seconds if possible
        if st is not None and ft is not None:  # Both converted successfully
            total_seconds = ft - st  # Direct numeric subtraction
        else:  # Fallback to other methods
            try:  # Attempt to subtract (works for datetimes/timedeltas)
                delta = finish_time - start_time  # Try subtracting (works for datetimes/timedeltas)
                total_seconds = float(delta.total_seconds())  # Get seconds from the resulting timedelta
            except Exception:  # Subtraction failed
                try:  # Final attempt: Numeric coercion
                    total_seconds = float(finish_time) - float(start_time)  # Final numeric coercion attempt
                except Exception:  # Numeric coercion failed
                    total_seconds = 0.0  # Fallback to zero on failure

    if total_seconds is None:  # Ensure a numeric value
        total_seconds = 0.0  # Default to zero
    if total_seconds < 0:  # Normalize negative durations
        total_seconds = abs(total_seconds)  # Use absolute value

    days = int(total_seconds // 86400)  # Compute full days
    hours = int((total_seconds % 86400) // 3600)  # Compute remaining hours
    minutes = int((total_seconds % 3600) // 60)  # Compute remaining minutes
    seconds = int(total_seconds % 60)  # Compute remaining seconds

    if days > 0:  # Include days when present
        return f"{days}d {hours}h {minutes}m {seconds}s"  # Return formatted days+hours+minutes+seconds
    if hours > 0:  # Include hours when present
        return f"{hours}h {minutes}m {seconds}s"  # Return formatted hours+minutes+seconds
    if minutes > 0:  # Include minutes when present
        return f"{minutes}m {seconds}s"  # Return formatted minutes+seconds
    return f"{seconds}s"  # Fallback: only seconds


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
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Movie Directories Renamer — Reverter{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the welcome message for the reverter tool
    start_time = datetime.datetime.now()  # Get the start time of the program
    
    if not verify_filepath_exists(REPORT_PATH):  # Check if the report file exists
        print(
            f"{BackgroundColors.RED}Report file {BackgroundColors.CYAN}{REPORT_PATH}{BackgroundColors.RED} not found. Make sure the file exists and try again.{Style.RESET_ALL}"
        )
        return  # Exit the program if the report file is not found
    
    revert_changes()  # Call the function to revert the changes based on the report file

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
