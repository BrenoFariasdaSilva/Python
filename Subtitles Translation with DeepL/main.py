"""
================================================================================
Subtitle (SRT) Translation using DeepL API
================================================================================
Author      : Breno Farias da Silva
Created     : 2025-12-13
Description :
   This script translates subtitle files (SRT) from English to Brazilian Portuguese
   using the DeepL API. It processes all .srt files in the specified input directory,
   respecting API usage limits, and saves the translated files with a '_ptBR' suffix.

   Key features include:
      - Automatic loading of SRT files from a directory
      - Integration with DeepL API for translation
      - Respect for API free plan usage limits
      - Logging output to both terminal and file
      - Optional notification sound upon completion

Usage:
   1. Configure the INPUT_DIR and ensure DEEPL_API_KEY is set in the .env file.
   2. Execute the script using Python:
      $ python <script_name>.py
   3. Translated SRT files are saved in the same directory with '_ptBR' appended.

Outputs:
   - Translated SRT files in the input directory, e.g., 01_ptBR.srt
   - Log file for script execution, e.g., Logs/translate_srt.log

TODOs:
   - Implement CLI argument parsing for input/output directories
   - Add support for batch translation with subdirectories
   - Improve handling of very large SRT files to avoid API limit issues
   - Extend support for additional languages

Dependencies:
   - Python >= 3.8
   - deepl
   - python-dotenv
   - colorama
   - Logger (custom logging module)
   - pathlib
   - datetime
   - atexit
   - os
   - sys
   - platform

Assumptions & Notes:
   - All input files must have a .srt extension
   - Input directory must exist and contain valid SRT files
   - DeepL API key must be set in a .env file as DEEPL_API_KEY
   - Platform-specific notes: notification sound may be disabled on Windows
"""

import atexit  # For playing a sound when the program finishes
import datetime  # For getting the current date and time
import deepl  # For DeepL API
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import sys  # For system-specific parameters and functions
from colorama import Style  # For coloring the terminal
from dotenv import load_dotenv  # For loading environment variables from .env file
from Logger import Logger  # For logging output to both terminal and file
from pathlib import Path  # For handling file paths
from shutil import copyfile  # For copying files


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
DESCRIPTIVE_SUBTITLES_REMOVAL = (
    True  # Set to True to remove descriptive lines (e.g., [music], (laughs)) from SRT before translation
)
DEEPL_API_KEY = ""  # DeepL API key (will be loaded in load_dotenv function)
INPUT_DIR = f"./Input"  # Directory containing the input SRT files
OUTPUT_DIR = Path("./Output")  # Base output directory

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


def ensure_env_file():
    """
    Ensures that a .env file exists. If not, creates it by copying .env.example
    and clears the DEEPL_API_KEY value, prompting the user to fill it.

    :return: True if .env already existed, False if it was created.
    """

    if os.path.exists(".env"):  # Check if .env file exists
        return True  # .env exists

    copyfile(".env.example", ".env")  # Copy .env.example to .env

    with open(".env", "r") as f:  # Open .env file for reading
        lines = f.readlines()  # Read all lines

    with open(".env", "w") as f:  # Open .env file for writing
        for line in lines:  # Iterate through each line
            if line.startswith("DEEPL_API_KEY="):  # If the line contains the DEEPL_API_KEY
                f.write("DEEPL_API_KEY=\n")  # Clear the DEEPL_API_KEY value
            else:  # If the line does not contain the DEEPL_API_KEY
                f.write(line)  # Write the line as is

    return False  # .env was created


def get_api_key():
    """
    Loads environment variables from a .env file and retrieves the DeepL API key.

    :return: DeepL API key as a string
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Loading environment variables from {BackgroundColors.CYAN}.env{BackgroundColors.GREEN} file...{Style.RESET_ALL}"
    )  # Output the verbose message

    global DEEPL_API_KEY  # Use the global DEEPL_API_KEY variable

    load_dotenv()  # Load environment variables from .env file
    DEEPL_API_KEY = os.getenv("DEEPL_API_KEY")  # Get DeepL API key from environment variables

    if not DEEPL_API_KEY:  # If the DeepL API key is not found
        return False  # Return False
    return True  # Return True


def resolve_entry_with_trailing_space(current_path: str, entry: str, stripped_part: str) -> str:
    """
    Resolve and optionally rename a directory entry with trailing spaces.

    :param current_path: Current directory path.
    :param entry: Directory entry name.
    :param stripped_part: Normalized target name without surrounding spaces.
    :return: Resolved path after optional rename.
    """

    try:  # Wrap full function logic to ensure safe execution
        resolved = os.path.join(current_path, entry)  # Build resolved path

        if entry != stripped_part:  # Verify trailing spaces exist
            corrected = os.path.join(current_path, stripped_part)  # Build corrected path
            try:  # Attempt to rename entry
                os.rename(resolved, corrected)  # Rename entry to stripped version
                verbose_output(true_string=f"{BackgroundColors.GREEN}Renamed: {BackgroundColors.CYAN}{resolved}{BackgroundColors.GREEN} -> {BackgroundColors.CYAN}{corrected}{Style.RESET_ALL}")  # Log rename
                resolved = corrected  # Update resolved path after rename
            except Exception:  # Handle rename failure
                verbose_output(true_string=f"{BackgroundColors.RED}Failed to rename: {BackgroundColors.CYAN}{resolved}{Style.RESET_ALL}")  # Log failure

        return resolved  # Return resolved path
    except Exception:  # Catch unexpected errors
        return os.path.join(current_path, entry)  # Return fallback resolved path


def resolve_full_trailing_space_path(filepath: str) -> str:
    """
    Resolve trailing space issues across all path components.

    :param filepath: Path to resolve potential trailing space mismatches.
    :return: Corrected full path if matches are found, otherwise original filepath.
    """

    try:  # Wrap full function logic to ensure safe execution
        verbose_output(true_string=f"{BackgroundColors.GREEN}Resolving full trailing space path for: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}")  # Log start

        if not isinstance(filepath, str) or not filepath:  # Verify filepath validity
            verbose_output(true_string=f"{BackgroundColors.YELLOW}Invalid filepath provided, skipping resolution.{Style.RESET_ALL}")  # Log invalid input
            return filepath  # Return original

        filepath = os.path.expanduser(filepath)  # Expand ~ to user directory
        parts = filepath.split(os.sep)  # Split path into components

        if not parts:  # Verify path parts exist
            return filepath  # Return original

        if filepath.startswith(os.sep):  # Handle absolute paths
            current_path = os.sep  # Start from root
            parts = parts[1:]  # Remove empty root part
        else:
            current_path = parts[0] if parts[0] else os.getcwd()  # Initialize base
            parts = parts[1:] if parts[0] else parts  # Adjust parts

        for part in parts:  # Iterate over each path component
            if part == "":  # Skip empty parts
                continue  # Continue iteration

            try:  # Attempt to list current directory
                entries = os.listdir(current_path) if os.path.isdir(current_path) else []  # List current directory entries
            except Exception:  # Handle failure to list directory contents
                verbose_output(true_string=f"{BackgroundColors.RED}Failed to list directory: {BackgroundColors.CYAN}{current_path}{Style.RESET_ALL}")  # Log failure
                return filepath  # Return original

            stripped_part = part.strip()  # Normalize current part
            match_found = False  # Initialize match flag

            for entry in entries:  # Iterate directory entries
                try:  # Attempt safe comparison for each entry
                    if entry.strip() == stripped_part:  # Compare stripped names
                        current_path = resolve_entry_with_trailing_space(current_path, entry, stripped_part)  # Resolve entry and update current path
                        match_found = True  # Mark match
                        break  # Stop searching
                except Exception:  # Handle any unexpected error during comparison
                    continue  # Continue on error

            if not match_found:  # If no match found for this segment
                verbose_output(true_string=f"{BackgroundColors.YELLOW}No match for segment: {BackgroundColors.CYAN}{part}{Style.RESET_ALL}")  # Log miss
                return filepath  # Return original

        return current_path  # Return fully resolved path

    except Exception:  # Catch unexpected errors to maintain stability
        verbose_output(true_string=f"{BackgroundColors.RED}Error resolving full path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}")  # Log error
        return filepath  # Return original


def verify_filepath_exists(filepath):
    """
    Verify if a file or folder exists at the specified path.

    :param filepath: Path to the file or folder
    :return: True if the file or folder exists, False otherwise
    """

    try:  # Wrap full function logic to ensure production-safe monitoring
        verbose_output(true_string=f"{BackgroundColors.GREEN}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}")  # Output the verbose message

        if os.path.exists(filepath):  # Verify if the file or folder exists at the specified path
            return True  # Return True if the original path exists

        resolved_path = resolve_full_trailing_space_path(filepath)  # Attempt to resolve path with full trailing space correction across components
        if resolved_path != filepath and os.path.exists(resolved_path):  # Verify if resolved path exists and differs from original
            verbose_output(true_string=f"{BackgroundColors.YELLOW}Resolved trailing space mismatch: {BackgroundColors.CYAN}{filepath}{BackgroundColors.YELLOW} -> {BackgroundColors.CYAN}{resolved_path}{Style.RESET_ALL}")  # Output verbose message about the resolution
            return True  # Return True if corrected path exists

        return False  # Return False if neither original nor corrected path exists
    except Exception as e:  # Catch any exception to ensure logging and Telegram alert
        print(str(e))  # Print error to terminal for server logs
        raise  # Re-raise to preserve original failure semantics


def read_srt(file_path):
    """
    Reads the SRT file into a list of lines.

    :param file_path: Path to the SRT file
    :return: List of strings representing each line
    """

    verbose_output(f"Reading SRT file from: {file_path}")  # Output the verbose message

    with open(file_path, "r", encoding="utf-8") as f:  # Open the SRT file for reading
        return f.readlines()  # Read all lines and return as a list


def remove_descriptive_subtitles(file_path):
    """
    Removes descriptive lines from the SRT file, such as text within brackets or parentheses.
    Overwrites the original SRT file with cleaned lines.
    These cleaned lines are used for translation.

    :param file_path: Path to the SRT file
    :return: List of cleaned lines
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Removing descriptive subtitles from: {BackgroundColors.CYAN}{file_path}{Style.RESET_ALL}"
    )  # Verbose message

    cleaned_lines = []  # Store cleaned lines

    with open(file_path, "r", encoding="utf-8") as f:  # Open SRT for reading
        for line in f:  # Iterate through each line
            stripped = line.strip()  # Remove leading/trailing whitespace

            if (
                stripped == "" or stripped.replace(":", "").replace(",", "").isdigit() or "-->" in line
            ):  # If line is empty, timing, or index
                cleaned_lines.append(line.rstrip("\n"))  # Keep timing/index/empty lines as is
                continue  # Skip further checks

            if stripped.startswith("[") and stripped.endswith("]"):  # If line is descriptive (in brackets)
                continue  # Skip descriptive lines
            if stripped.startswith("(") and stripped.endswith(")"):  # If line is descriptive (in parentheses)
                continue  # Skip descriptive lines

            cleaned_lines.append(stripped)  # Keep normal text lines

    with open(file_path, "w", encoding="utf-8") as f:  # Open SRT for writing
        f.write("\n".join(cleaned_lines))  # Overwrite SRT with cleaned lines

    return cleaned_lines  # Return cleaned lines for translation


def get_remaining_characters(translator):
    """
    Checks remaining characters available in DeepL free API plan.

    :param translator: DeepL translator client
    :return: Number of remaining characters or None if unlimited/unknown
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Checking remaining characters in DeepL API...{Style.RESET_ALL}"
    )  # Output the verbose message

    usage = translator.get_usage()  # Get usage information from DeepL API

    if usage.character.valid:  # If character usage information is valid
        remaining = usage.character.limit - usage.character.count  # Calculate remaining characters
        return remaining  # Return remaining characters

    return None  # Return None if unlimited/unknown


def translate_text_block(text_block, translator):
    """
    Translates a block of text using the DeepL API, respecting remaining characters limit.

    :param text_block: String containing multiple lines to translate
    :param translator: DeepLClient instance
    :return: List of translated lines or original lines if limit exceeded or translation fails
    """

    verbose_output(f"{BackgroundColors.GREEN}Translating text block...{Style.RESET_ALL}")  # Output the verbose message

    remaining_chars = get_remaining_characters(translator)  # Check remaining characters

    if remaining_chars is not None:  # If there is a limit on remaining characters
        if len(text_block) > remaining_chars:  # Exceeding limit
            print(
                f"{BackgroundColors.YELLOW}Warning: Translation limit would be exceeded. Current block size: {BackgroundColors.CYAN}{len(text_block)}{BackgroundColors.YELLOW}. Exceeding limit by: {BackgroundColors.CYAN}{len(text_block) - remaining_chars}{BackgroundColors.YELLOW} characters. Skipping translation for this block.{Style.RESET_ALL}"
            )  # Output warning message
            return text_block.split("\n")  # Return original lines

    try:  # Perform translation
        result = translator.translate_text(text_block, source_lang="EN", target_lang="PT-BR")  # Translate text block
        if result is not None and hasattr(result, "text") and result.text:  # Ensure result is valid
            return result.text.split("\n")  # Return translated lines
        else:
            return text_block.split("\n")  # Fallback to original lines
    except Exception as e:  # Handle any translation error
        print(f"{BackgroundColors.RED}Translation failed: {e}. Returning original lines.{Style.RESET_ALL}")
        return text_block.split("\n")  # Return original lines on failure


def translate_srt_lines(srt_file, lines):
    """
    Translates lines from an SRT file using DeepL API, keeping timing and index lines unchanged.

    :param srt_file: Path to the SRT file (for logging purposes).
    :param lines: List of SRT lines.
    :return: List of translated lines.
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Translating SRT lines from file: {BackgroundColors.CYAN}{srt_file}{Style.RESET_ALL}"
    )  # Output verbose message for translating SRT lines

    translator = deepl.DeepLClient(auth_key=DEEPL_API_KEY)  # Create a DeepL client with the loaded API key
    translated_lines = []  # Initialize empty list for storing translated lines
    buffer = []  # Initialize empty buffer for batching subtitle text lines

    total_lines = len(lines)  # Store total line count for progress percentage calculation
    current_line = 0  # Initialize line counter for progress tracking
    filename = getattr(srt_file, "name", str(srt_file))  # Extract filename string for progress display
    real_stderr = sys.__stderr__ if sys.__stderr__ is not None else open(os.devnull, "w")  # Resolve original stderr to a non-None stream for in-place progress output

    for line in lines:  # Iterate through each line in the SRT file
        stripped = line.strip()  # Remove leading and trailing whitespace from the current line

        if (
            stripped == "" or stripped.replace(":", "").replace(",", "").isdigit() or "-->" in line
        ):  # Verify if the line is empty, a sequence index, or a timing marker
            if buffer:  # Verify if the translation buffer contains pending text lines
                translated = translate_text_block("\n".join(buffer), translator)  # Translate all buffered text lines as one block
                if translated is None:  # Verify if translation returned None instead of a result
                    translated = buffer  # Fall back to the original buffer lines on failed translation
                translated_lines.extend(translated)  # Append translated lines to the result list
                buffer = []  # Reset buffer after processing the current block
            translated_lines.append(line.rstrip("\n"))  # Append the timing or index line to result unchanged
        else:  # Handle regular subtitle text lines
            buffer.append(stripped)  # Append the stripped text line to the translation buffer

        current_line += 1  # Increment the processed line counter
        percent = int(current_line / total_lines * 100) if total_lines > 0 else 0  # Calculate progress as an integer percentage
        filled = percent // 10  # Calculate the number of filled segments in the progress bar
        bar = "#" * filled + "-" * (10 - filled)  # Build the visual progress bar string with filled and empty segments
        real_stderr.write(f"\r{BackgroundColors.GREEN}Processing: {BackgroundColors.CYAN}{filename}{BackgroundColors.GREEN} [{bar}] {percent}%{Style.RESET_ALL}   ")  # Overwrite current terminal line with updated progress
        real_stderr.flush()  # Flush original stderr to force immediate display of progress

    if buffer:  # Verify if the buffer still contains unprocessed text lines after the loop
        translated = translate_text_block("\n".join(buffer), translator)  # Translate the remaining buffered text lines
        if translated is None:  # Verify if translation returned None for the remaining block
            translated = buffer  # Fall back to the original buffer lines on failed translation
        translated_lines.extend(translated)  # Append the remaining translated lines to the result list

    real_stderr.write("\n")  # Advance the terminal cursor to a new line after progress finishes
    real_stderr.flush()  # Flush original stderr to finalize the progress output

    return translated_lines  # Return the complete list of translated lines


def save_srt(lines, output_file):
    """
    Saves translated lines to an output SRT file.

    :param lines: List of translated lines
    :param output_file: Path to save the output SRT
    :return: None
    """

    with open(output_file, "w", encoding="utf-8") as f:  # Open the output SRT file for writing
        f.write("\n".join(lines))  # Write translated lines to the file

    print(
        f"{BackgroundColors.GREEN}Translated SRT saved as: {BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}"
    )  # Output the saved file message


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


def main():
    """
    Main function.

    Processes all .srt files in the INPUT_DIR. Each file is translated using DeepL API
    from English to Brazilian Portuguese. Translated files are saved in the same directory
    with '_ptBR' appended to the filename.

    :param: None
    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Subtitle (SRT) translation using DeepL API{BackgroundColors.GREEN} program!{Style.RESET_ALL}\n"
    )  # Output the welcome message
    start_time = datetime.datetime.now()  # Get the start time of the program

    ensure_env_file()  # Ensure .env file exists

    if not get_api_key():  # Load .env and get DeepL API key
        print(
            f"{BackgroundColors.RED}DEEPL_API_KEY not found in .env file. Please set it before running the program.{Style.RESET_ALL}"
        )  # Output error message
        return  # Exit the program

    if not os.path.exists(INPUT_DIR):  # If the input directory does not exist
        os.makedirs(INPUT_DIR)  # Create the input directory
        print(f"Input directory does not exist: {INPUT_DIR}")  # Output the error message
        return  # Exit the program

    if not os.path.exists(OUTPUT_DIR):  # If the output directory does not exist
        os.makedirs(OUTPUT_DIR)  # Create the output directory

    srt_files = [f for f in Path(INPUT_DIR).rglob("*.srt") if f.is_file()]  # List of SRT file paths (includes subdirectories)

    if not srt_files:  # If no SRT files were found
        print(f"No .srt files found in directory: {INPUT_DIR}")  # Output message
        return  # Exit the program

    for srt_file in srt_files:  # Iterate through each SRT file in the input directory
        srt_lines = read_srt(srt_file)  # Read SRT file into a list of lines

        if DESCRIPTIVE_SUBTITLES_REMOVAL:  # Verify if descriptive subtitle removal is enabled
            srt_lines = remove_descriptive_subtitles(srt_file)  # Clean SRT lines by removing descriptive text

        translated_lines = translate_srt_lines(srt_file, srt_lines)  # Translate SRT lines using DeepL API

        relative_path = srt_file.relative_to(INPUT_DIR).parent  # Extract relative path from the input directory
        output_subdir = OUTPUT_DIR / relative_path  # Build the output subdirectory path
        output_subdir.mkdir(parents=True, exist_ok=True)  # Ensure the output subdirectory exists

        output_file = output_subdir / f"{srt_file.stem}_ptBR.srt"  # Build the output file path with ptBR suffix
        save_srt(translated_lines, output_file)  # Save the translated SRT to the output file

    finish_time = datetime.datetime.now()  # Get the finish time of the program
    print(
        f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"
    )  # Output start, finish, and execution times
    print(
        f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
    )  # Output end of program message

    (
        atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None
    )  # Register the play_sound function to be called when the program finishes


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
