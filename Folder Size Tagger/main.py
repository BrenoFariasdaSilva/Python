"""
================================================================================
Directory Size Appender
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-03-27
Description :
    Rename first-level directories in an input path by appending each
    directory size in gigabytes to the directory name.

    This script processes the local filesystem only and is useful for
    storage analysis and dataset organization workflows.

    Key features include:
        - Non-recursive first-level directory discovery
        - Recursive directory size aggregation
        - Automatic size conversion and name formatting in GB
        - Safe rename operations with error handling
        - Optional input path override via command-line argument

Usage:
    1. Optionally edit INPUT_PATH to define the default root path.
    2. Run the script directly with Python and optionally pass a custom path.
        $ python main.py
        $ python main.py "D:\\Your\\Custom\\Path\\"
    3. Directory names inside the root path are updated in place.

Outputs:
    - Renamed directories in the configured input path
    - Execution log in ./Logs/main.log

TODOs:
    - Add dry-run mode for previewing rename operations
    - Add configurable size unit output (MB, GB, TB)
    - Add optional JSON report output for audit history

Dependencies:
    - Python >= 3.8
    - colorama

Assumptions & Notes:
    - Only first-level directories are considered for rename operations.
    - Directory size includes all nested files and subdirectories.
    - Existing names ending with GB are normalized before appending new size.
    - Inaccessible or empty directories are skipped safely.
"""

import atexit  # For playing a sound when the program finishes
import datetime  # For getting the current date and time
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For matching and replacing directory size suffixes
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
INPUT_PATH = r"D:/Sem Backup/Download/Temp/TeraBox/"  # Set the default input path for first-level directory processing

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

# Deletion statistics accumulator:
DELETION_STATS = {"files_deleted": 0, "dirs_deleted": 0, "bytes_deleted": 0}  # Tracks deleted files, directories and total bytes

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


def get_input_path(cli_args: list) -> str:
    """
    Resolve the input path from constants and command-line arguments.

    :param cli_args: Command-line arguments list.
    :return: Resolved input path.
    """

    default_path = INPUT_PATH  # Store the default input path
    has_cli_argument = len(cli_args) > 1  # Verify if a custom argument was provided

    if has_cli_argument:  # Verify if argument index 1 is available
        candidate_path = str(cli_args[1]).strip()  # Normalize the provided path string

        if candidate_path != "":  # Verify if the provided path is not empty
            return candidate_path  # Return the provided input path

    return default_path  # Return the default input path


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


def get_directories_in_path(path: str) -> list:
    """
    Return only first-level directories from a path.

    :param path: Root path to read first-level entries.
    :return: List of absolute first-level directory paths.
    """

    directories = []  # Initialize the first-level directory list

    try:  # Protect path listing operation
        entries = os.listdir(path)  # Read first-level entries from the input path
    except (PermissionError, OSError):  # Handle listing access and OS failures
        return directories  # Return an empty list when listing is not possible

    for entry in entries:  # Iterate through first-level entries
        entry_path = os.path.join(path, entry)  # Build the absolute entry path

        if os.path.isdir(entry_path):  # Verify if the current entry is a directory
            directories.append(entry_path)  # Store the first-level directory path

    return directories  # Return the discovered first-level directories


def calculate_directory_size_bytes(path: str) -> int:
    """
    Calculate recursive directory size in bytes.

    :param path: Directory path to aggregate size.
    :return: Total directory size in bytes.
    """

    total_size = 0  # Initialize byte accumulator

    try:  # Protect recursive traversal operation
        for root, _, files in os.walk(path):  # Traverse all nested directories and files
            for filename in files:  # Iterate through files in the current root
                file_path = os.path.join(root, filename)  # Build the absolute file path

                try:  # Protect file size read operation
                    total_size += os.path.getsize(file_path)  # Add file size in bytes to accumulator
                except (PermissionError, OSError):  # Handle inaccessible or invalid file metadata
                    continue  # Skip the current file and continue traversal
    except (PermissionError, OSError):  # Handle inaccessible directory traversal
        return 0  # Return zero size for inaccessible directories

    return total_size  # Return total recursive directory size in bytes


def convert_bytes_to_gb(size_bytes: int) -> float:
    """
    Convert byte size to gigabytes with two decimal precision.

    :param size_bytes: Size value in bytes.
    :return: Size value in gigabytes.
    """

    size_gb = size_bytes / (1024 ** 3)  # Convert bytes to gibibytes using binary base
    rounded_size_gb = round(size_gb, 2)  # Round the converted value to two decimal places

    return rounded_size_gb  # Return rounded gigabyte value


def update_deletion_stats(deleted_files: int, deleted_bytes: int) -> dict:
    """
    Aggregate deletion statistics increments.

    :param deleted_files: Number of files deleted in this operation.
    :param deleted_bytes: Total bytes deleted in this operation.
    :return: Current deletion statistics dictionary.
    """

    global DELETION_STATS  # Reference global deletion statistics accumulator
    DELETION_STATS["files_deleted"] += int(deleted_files)  # Increment files deleted counter
    DELETION_STATS["bytes_deleted"] += int(deleted_bytes)  # Increment bytes deleted accumulator
    return DELETION_STATS  # Return the updated statistics dictionary


def format_directory_name(dirname: str, size_gb: float) -> str:
    """
    Build the target directory name using the GB suffix format.

    :param dirname: Current directory name.
    :return: Formatted directory name with size suffix.
    """

    sanitized_name = dirname.strip()  # Normalize surrounding whitespace from directory name
    suffix_pattern = r"\s+\d+(?:\.\d+)?GB$"  # Define suffix pattern for existing size suffix
    base_name = re.sub(suffix_pattern, "", sanitized_name)  # Remove existing numeric GB suffix when present
    formatted_name = f"{base_name} {size_gb:.2f}GB"  # Build formatted directory name with updated size suffix

    return formatted_name  # Return the formatted directory name


def rename_directory(original_path: str, new_name: str) -> None:
    """
    Rename a directory path using a target directory name.

    :param original_path: Current absolute directory path.
    :return: None.
    """

    parent_path = os.path.dirname(original_path)  # Resolve parent directory path
    original_name = os.path.basename(original_path)  # Resolve current directory name
    destination_path = os.path.join(parent_path, new_name)  # Build destination directory path

    if original_name == new_name:  # Verify if rename operation is unnecessary
        return  # Exit without modifying the directory name

    try:  # Protect rename filesystem operation
        os.rename(original_path, destination_path)  # Rename the directory to the target name
    except (PermissionError, FileExistsError, OSError):  # Handle rename conflicts and access failures
        return  # Exit safely when rename fails


def delete_foto_directories(path: str) -> None:
    """
    Delete Foto and Fotos directories from a first-level directory.

    :param path: First-level directory path.
    :return: None.
    """

    target_names = {"foto", "fotos"}  # Define target directory names for deletion

    try:  # Protect first-level entry listing
        entries = os.listdir(path)  # Read first-level entries from current directory
    except (PermissionError, OSError):  # Handle inaccessible directory listing
        return  # Exit safely when listing fails

    for entry in entries:  # Iterate through first-level entries
        entry_path = os.path.join(path, entry)  # Build absolute entry path

        if not os.path.isdir(entry_path):  # Verify if current entry is not a directory
            continue  # Skip non-directory entries

        if entry.lower() not in target_names:  # Verify if directory name is not a Foto target
            continue  # Skip non-target directories

        try:  # Protect recursive directory deletion
            import shutil  # Import here for deletion operation
            files_count = 0  # Initialize file counter for this directory
            for _root, _dirs, files in os.walk(entry_path):  # Traverse directory to count files
                files_count += len(files)  # Increment file counter for each file found
            dir_size = calculate_directory_size_bytes(entry_path)  # Compute directory size before deletion
            shutil.rmtree(entry_path)  # Delete directory and all nested contents
            update_deletion_stats(files_count, dir_size)  # Aggregate deleted files and bytes metrics
            DELETION_STATS["dirs_deleted"] += 1  # Increment deleted directories counter
        except (PermissionError, OSError):  # Handle deletion access and OS failures
            continue  # Skip failed deletion and continue processing


def move_video_contents_to_parent(path: str) -> None:
    """
    Move Video and Videos directory contents to the first-level directory root.

    :param path: First-level directory path.
    :return: None.
    """

    target_names = {"video", "videos"}  # Define target directory names for content move

    try:  # Protect first-level entry listing
        entries = os.listdir(path)  # Read first-level entries from current directory
    except (PermissionError, OSError):  # Handle inaccessible directory listing
        return  # Exit safely when listing fails

    for entry in entries:  # Iterate through first-level entries
        source_directory_path = os.path.join(path, entry)  # Build absolute source directory path

        if not os.path.isdir(source_directory_path):  # Verify if current entry is not a directory
            continue  # Skip non-directory entries

        if entry.lower() not in target_names:  # Verify if directory name is not a Video target
            continue  # Skip non-target directories

        try:  # Protect source directory content listing
            source_items = os.listdir(source_directory_path)  # Read items inside Video target directory
        except (PermissionError, OSError):  # Handle inaccessible source directory listing
            continue  # Skip inaccessible source directory

        for source_item in source_items:  # Iterate through each source content item
            source_item_path = os.path.join(source_directory_path, source_item)  # Build absolute source item path
            destination_item_path = os.path.join(path, source_item)  # Build initial destination item path
            destination_exists = os.path.exists(destination_item_path)  # Verify if destination path already exists

            if destination_exists:  # Verify if a destination conflict exists
                source_stem, source_extension = os.path.splitext(source_item)  # Split source item name into stem and extension
                suffix_index = 1  # Initialize numeric suffix index for conflict resolution

                while True:  # Iterate until a unique destination name is found
                    candidate_name = f"{source_stem}_{suffix_index}{source_extension}"  # Build candidate item name with numeric suffix
                    candidate_path = os.path.join(path, candidate_name)  # Build candidate destination path

                    if not os.path.exists(candidate_path):  # Verify if candidate destination path is available
                        destination_item_path = candidate_path  # Assign conflict-safe destination path
                        break  # Stop conflict resolution loop

                    suffix_index += 1  # Increment suffix index for next candidate

            try:  # Protect filesystem move operation
                import shutil  # Import here for move operation
                shutil.move(source_item_path, destination_item_path)  # Move source item to destination path
            except (PermissionError, OSError, Exception):  # Handle move errors and filesystem conflicts
                continue  # Skip failed move and continue processing

        try:  # Protect source directory removal after content move
            os.rmdir(source_directory_path)  # Remove now-empty Video target directory
            DELETION_STATS["dirs_deleted"] += 1  # Increment deleted directories counter after successful removal
        except (PermissionError, OSError):  # Handle non-empty or inaccessible directory removal
            continue  # Skip failed directory removal and continue processing


def extract_clean_directory_name(dirname: str) -> str:
    """
    Remove existing index prefix and GB suffix from a directory name.

    :param dirname: Directory name to normalize.
    :return: Clean directory name without index or GB suffix.
    """

    name = dirname  # Preserve the original name for processing
    name = re.sub(r"^\d+\.\s", "", name)  # Remove leading index pattern if present
    name = re.sub(r"\s\d+(?:\.\d+)?GB$", "", name)  # Remove trailing size suffix if present

    return name.strip()  # Return trimmed clean name


def build_indexed_name(index: int, clean_name: str, size_gb: float) -> str:
    """
    Build the final indexed directory name with size suffix.

    :param index: Numeric index for ordering.
    :param clean_name: Directory base name without index or suffix.
    :return: Formatted indexed directory name.
    """

    return f"{index}. {clean_name} {size_gb:.2f}GB"  # Return the indexed and suffixed directory name


def collect_directory_metadata(paths: list) -> list:
    """
    Collect (path, original_name, size_bytes) tuples for given directories.

    :param paths: List of directory paths to measure.
    :return: List of metadata tuples.
    """

    metadata = []  # Initialize metadata list

    for p in paths:  # Iterate through given directory paths
        try:  # Protect basename and size measurement
            original_name = os.path.basename(p)  # Extract the original directory name
            size_bytes = calculate_directory_size_bytes(p)  # Compute recursive size in bytes
            metadata.append((p, original_name, size_bytes))  # Append metadata tuple
        except (PermissionError, OSError):  # Handle access and OS errors
            continue  # Skip directories that cannot be accessed

    return metadata  # Return collected metadata


def sort_directories_by_size(metadata: list) -> list:
    """
    Sort metadata list by ascending directory size in bytes.

    :param metadata: List of (path, name, size_bytes) tuples.
    :return: Sorted list of metadata tuples.
    """

    return sorted(metadata, key=lambda t: t[2])  # Return metadata sorted by the size_bytes element


def is_directory_empty(path: str) -> bool:
    """
    Determine whether a directory is empty or has zero total size.

    :param path: Directory path to verify.
    :return: True when directory is empty or zero-sized, False otherwise.
    """

    try:  # Protect directory listing operation
        entries = os.listdir(path)  # List entries inside the directory
    except (PermissionError, OSError):  # Handle inaccessible directory listing
        return False  # Consider inaccessible directories as non-empty for safety

    if not entries:  # Verify when there are no entries inside directory
        return True  # Directory is empty

    size_bytes = calculate_directory_size_bytes(path)  # Compute recursive size in bytes

    return size_bytes == 0  # Return True when total size is zero


def delete_empty_directories(paths: list) -> list:
    """
    Delete empty directories and return the remaining paths list.

    :param paths: List of directory paths to inspect and possibly delete.
    :return: Filtered list of directory paths that remain.
    """

    remaining = []  # Initialize list for non-deleted directories

    for p in paths:  # Iterate through supplied directory paths
        try:  # Protect emptiness verification and deletion
            if is_directory_empty(p):  # Verify if directory is empty by criteria
                try:  # Protect removal operation for empty directory
                    if not os.listdir(p):  # Verify if directory truly has no entries
                        os.rmdir(p)  # Remove empty directory
                        DELETION_STATS["dirs_deleted"] += 1  # Increment deleted directories counter for empty dir
                    else:  # Handle case with no size but entries (defensive)
                        import shutil  # Import here for recursive removal
                        files_count = 0  # Initialize file counter for recursive removal
                        for _root, _dirs, files in os.walk(p):  # Traverse directory tree to count files
                            files_count += len(files)  # Increment file counter for each file
                        dir_size = calculate_directory_size_bytes(p)  # Compute total size before recursive removal
                        shutil.rmtree(p)  # Remove directory recursively
                        update_deletion_stats(files_count, dir_size)  # Aggregate deleted files and bytes metrics for recursive removal
                        DELETION_STATS["dirs_deleted"] += 1  # Increment deleted directories counter for recursive removal
                except (PermissionError, OSError):  # Handle deletion access failures
                    remaining.append(p)  # Keep directory when deletion fails
            else:  # Keep non-empty directories
                remaining.append(p)  # Preserve directory path for further processing
        except (PermissionError, OSError):  # Handle access failures during inspection
            remaining.append(p)  # Preserve directory when inspection fails

    return remaining  # Return updated directory list excluding deleted ones


def perform_safe_rename(original_path: str, target_name: str) -> None:
    """
    Rename a directory avoiding name collisions by appending numeric suffixes.

    :param original_path: Current absolute directory path.
    :param target_name: Desired new directory name.
    :return: None.
    """

    parent = os.path.dirname(original_path)  # Resolve parent directory path
    dest = os.path.join(parent, target_name)  # Build initial destination path
    if os.path.exists(dest):  # Verify if destination already exists
        base, ext = os.path.splitext(target_name)  # Split name and extension if any
        suffix = 1  # Initialize numeric suffix

        while True:  # Iterate to find a unique name
            candidate = f"{base}_{suffix}{ext}"  # Build candidate name with numeric suffix
            candidate_path = os.path.join(parent, candidate)  # Build candidate absolute path
            if not os.path.exists(candidate_path):  # Verify uniqueness of candidate path
                dest = candidate_path  # Use unique candidate as destination
                break  # Exit collision resolution loop
            suffix += 1  # Increment suffix for next candidate

    try:  # Protect rename filesystem operation
        os.rename(original_path, dest)  # Perform directory rename to resolved destination
    except (PermissionError, OSError):  # Handle rename failures and access errors
        return  # Exit safely when rename fails


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
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Directory Size Appender{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n",
    )  # Output the welcome message
    
    start_time = datetime.datetime.now()  # Get the start time of the program

    input_path = get_input_path(sys.argv)  # Resolve input path from default value and CLI arguments

    if not verify_filepath_exists(input_path):  # Verify if the resolved input path exists
        print(  # Output a missing path message
            f"{BackgroundColors.RED}Input path {BackgroundColors.CYAN}{input_path}{BackgroundColors.RED} was not found.{Style.RESET_ALL}"  # Build missing input path message
        )  # Output the error message for invalid input path
        finish_time = datetime.datetime.now()  # Get the finish time when input path is invalid
        print(  # Output timing data for invalid path flow
            f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"  # Build timing message
        )  # Output execution timing details
        print(  # Output final program completion message
            f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"  # Build completion message
        )  # Output completion message
        (  # Execute optional exit routine registration
            atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None  # Register play_sound based on runtime configuration
        )  # Complete conditional exit routine registration
        return  # Exit main function early for invalid input path

    directories = get_directories_in_path(input_path)  # Retrieve first-level directories from input path

    for directory_path in directories:  # Iterate through each first-level directory for media cleanup
        delete_foto_directories(directory_path)  # Delete Foto and Fotos directories inside current first-level directory
        move_video_contents_to_parent(directory_path)  # Move Video and Videos contents to current first-level directory root

    directories = get_directories_in_path(input_path)  # Refresh first-level directory list after cleanup
    directories = delete_empty_directories(directories)  # Delete empty directories before metadata collection

    metadata = collect_directory_metadata(directories)  # Collect path, name and size metadata for remaining directories
    sorted_meta = sort_directories_by_size(metadata)  # Sort directories ascending by size in bytes

    for index, (path, original_name, size_bytes) in enumerate(sorted_meta, start=1):  # Iterate sorted directories with index
        clean_name = extract_clean_directory_name(original_name)  # Normalize original name by removing index and GB suffix
        size_gb = convert_bytes_to_gb(size_bytes)  # Convert size from bytes to gigabytes
        new_name = build_indexed_name(index, clean_name, size_gb)  # Build the final indexed and suffixed name
        perform_safe_rename(path, new_name)  # Rename directory safely avoiding collisions
    
    print(
        f"{BackgroundColors.GREEN}Total files deleted: {BackgroundColors.CYAN}{DELETION_STATS['files_deleted']}{BackgroundColors.GREEN} | Total dirs deleted: {BackgroundColors.CYAN}{DELETION_STATS['dirs_deleted']}{BackgroundColors.GREEN} | Total deleted size: {BackgroundColors.CYAN}{convert_bytes_to_gb(DELETION_STATS['bytes_deleted']):.2f}GB{Style.RESET_ALL}"
    )  # Output aggregated deletion statistics

    finish_time = datetime.datetime.now()  # Get the finish time of the program
    
    print(
        f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"
    )  # Output the start and finish times
    
    print(
        f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
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
