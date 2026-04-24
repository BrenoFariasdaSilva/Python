import atexit  # For playing a sound when the program finishes
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For regular expressions
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


def clean_filename(filename):
    """
    Removes the last whitespace before the opening brace, the content between the braces, the braces themselves, and any emojis from the filename.

    :param filename: The filename to clean.
    :return: The cleaned filename.
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Cleaning the filename: {BackgroundColors.CYAN}{filename}{Style.RESET_ALL}"
    )  # Output the verbose message

    pattern = r"\s*\([^)]*\)"  # Regular expression to match a space, opening brace, content, and closing brace.

    emoji_pattern = re.compile(  # Regular expression to match emojis.
        r"[\U0001F600-\U0001F64F"  # Emoticons
        r"|\U0001F300-\U0001F5FF"  # Symbols & Pictographs
        r"|\U0001F680-\U0001F6FF"  # Transport & Map Symbols
        r"|\U0001F1E0-\U0001F1FF"  # Flags (iOS)
        r"|\U00002700-\U000027BF"  # Dingbats
        r"|\U00002600-\U000026FF"  # Miscellaneous Symbols
        r"|\U00002B50-\U00002B55"  # Stars
        r"|\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        r"|\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        r"|\U00002500-\U00002BEF"  # Miscellaneous Symbols
        r"|\U0001F100-\U0001F1FF"  # Enclosed Alphanumeric Supplement
        r"]+",
        flags=re.UNICODE,  # Flags
    )  # Emojis

    filename = re.sub(pattern, "", filename)  # Remove the pattern from the filename.

    return emoji_pattern.sub("", filename)  # Remove the emojis from the filename.


def rename_files_in_dir_recursively(base_dir):
    """
    Renames files in the given directory and its subdirectories recursively to remove
    patterns like " (some_text)" and emojis.

    :param base_dir: The base directory to start renaming files.
    :return None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Renaming files in the directory: {BackgroundColors.CYAN}{base_dir}{Style.RESET_ALL}"
    )  # Output the verbose message

    for root, dirs, files in os.walk(base_dir):  # Recursively traverses directories
        for file in files:  # For each file in the directory
            original_path = os.path.join(root, file)  # Get the original path of the file
            cleaned_filename = clean_filename(file)  # Clean the filename

            if file != cleaned_filename:  # Rename only if the name was changed.
                new_path = os.path.join(root, cleaned_filename)  # Get the new path of the file
                try:  # Try to rename the file
                    os.rename(original_path, new_path)  # Rename the file
                    print(
                        f"{BackgroundColors.GREEN}Renamed file {BackgroundColors.CYAN}{original_path}{BackgroundColors.GREEN} to {BackgroundColors.CYAN}{new_path}{Style.RESET_ALL}"
                    )  # Output the success message
                except Exception as e:
                    print(
                        f"{BackgroundColors.RED}Error renaming file {BackgroundColors.CYAN}{original_path}{BackgroundColors.RED} to {BackgroundColors.CYAN}{new_path}{BackgroundColors.RED}: {e}{Style.RESET_ALL}"
                    )  # Output the error message


def play_sound():
    """
    Plays a sound when the program finishes and skips if the operating system is Windows.
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

    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Hitomi Downloader File Renamer{BackgroundColors.GREEN}!{Style.RESET_ALL}"
    )  # Output the welcome message

    root_directory = os.getcwd()  # Get the current working directory
    rename_files_in_dir_recursively(
        root_directory
    )  # Rename files in the current directory and its subdirectories recursively

    print(
        f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
    )  # Output the end of the program message

    atexit.register(play_sound)  # Register the function to play a sound when the program finishes


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
