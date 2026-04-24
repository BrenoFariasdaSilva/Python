import atexit  # For playing a sound when the program finishes
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import pysubs2  # For handling subtitle timing
import re  # For parsing the offset string
from colorama import Style  # For coloring the terminal
from tqdm import tqdm  # For progress bar


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
OFFSET = "-00h00m00s5000ms"  # Offset to apply to all subtitles
REPLACE_EXISTING_SRT = True  # Set to True to replace existing .srt files
INPUT_DIRECTORY = "./Input"  # Input directory to search for subtitles

# Sound Constants:
SOUND_COMMANDS = {"Darwin": "afplay", "Linux": "aplay", "Windows": "start"}  # Commands to play a sound
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav"  # Path to sound file

# Exclusions:
EXCLUDE_DIRS = {".assets", ".venv"}  # Directories to exclude
EXCLUDE_FILES = {"./main.py", "./Makefile", "./requirements.txt"}  # Files to exclude


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
        verbose_output(
            f"{BackgroundColors.GREEN}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}"
        )  # Output the verbose message
        
        if not isinstance(filepath, str) or not filepath.strip():  # Verify for non-string or empty/whitespace-only input   
            verbose_output(true_string=f"{BackgroundColors.YELLOW}Invalid filepath provided, skipping existence verification.{Style.RESET_ALL}")  # Log invalid input
            return False  # Return False for invalid input

        if os.path.exists(filepath):  # Fast path: original input exists
            return True  # Return True immediately

        candidate = str(filepath).strip()  # Normalize input to string and strip surrounding whitespace

        if (candidate.startswith("'") and candidate.endswith("'")) or (
            candidate.startswith('"') and candidate.endswith('"')
        ):  # Handle quoted paths from config files
            candidate = candidate[1:-1].strip()  # Remove wrapping quotes and trim again

        candidate = os.path.expanduser(candidate)  # Expand ~ to user home directory
        candidate = os.path.normpath(candidate)  # Normalize path separators and structure

        if os.path.exists(candidate):  # Verify normalized candidate directly
            return True  # Return True if normalized path exists

        repo_dir = os.path.dirname(os.path.abspath(__file__))  # Resolve repository directory
        cwd = os.getcwd()  # Capture current working directory

        alt = candidate.lstrip(os.sep) if candidate.startswith(os.sep) else candidate  # Prepare relative-safe path

        repo_candidate = os.path.join(repo_dir, alt)  # Build repo-relative candidate
        cwd_candidate = os.path.join(cwd, alt)  # Build cwd-relative candidate

        for path_variant in (repo_candidate, cwd_candidate):  # Iterate alternative base paths
            try:
                normalized_variant = os.path.normpath(path_variant)  # Normalize variant
                if os.path.exists(normalized_variant):  # Verify existence
                    return True  # Return True if found
            except Exception:
                continue  # Continue safely on error

        try:  # Attempt absolute path resolution as fallback
            abs_candidate = os.path.abspath(candidate)  # Build absolute path
            if os.path.exists(abs_candidate):  # Verify existence
                return True  # Return True if found
        except Exception:
            pass  # Ignore resolution errors

        for path_variant in (candidate, repo_candidate, cwd_candidate):  # Attempt trailing-space resolution on all variants
            try:  # Attempt to resolve trailing space issues across path components for this variant
                resolved = resolve_full_trailing_space_path(path_variant)  # Resolve trailing space issues across path components
                if resolved != path_variant and os.path.exists(resolved):  # Verify resolved path exists
                    verbose_output(
                        f"{BackgroundColors.YELLOW}Resolved trailing space mismatch: {BackgroundColors.CYAN}{path_variant}{BackgroundColors.YELLOW} -> {BackgroundColors.CYAN}{resolved}{Style.RESET_ALL}"
                    )  # Log successful resolution
                    return True  # Return True if corrected path exists
            except Exception:  # Catch any exception during trailing space resolution   
                continue  # Continue safely on error

        return False  # Not found after all resolution strategies
    except Exception as e:  # Catch any exception to ensure logging and Telegram alert
        print(str(e))  # Print error to terminal for server logs
        raise  # Re-raise to preserve original failure semantics


def get_directories():
    """
    Get all directories (including subdirectories) inside the input directory that contain at least one .srt file.

    :param none
    :return: List of directories in absolute paths
    """

    input_dir_abs = os.path.abspath(INPUT_DIRECTORY)  # Ensure input directory is absolute and normalized
    matching_dirs = []  # Store directories that contain .srt files

    for root, dirs, files in os.walk(input_dir_abs):  # Walk through all subdirectories
        if any(file.lower().endswith(".srt") for file in files):  # Check if current dir has at least one .srt file
            matching_dirs.append(os.path.normpath(os.path.abspath(root)))  # Add the directory if it qualifies

    return matching_dirs  # Return the list of directories that contain .srt files


def parse_offset(offset_str):
    """
    Parses an offset string like +00h00m00s0500ms into milliseconds.

    :param offset_str: String offset (e.g. '+00h00m00s0500ms' or '-00h00m05s000ms')
    :return: Integer offset in milliseconds
    """

    sign = 1 if offset_str.startswith("+") else -1  # Determine the sign of the offset
    offset_str = offset_str[1:]  # Remove + or -

    # Use regex to safely extract all time units (defaulting to 0 if missing)
    match = re.match(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?(?:(\d+)ms)?", offset_str)  # Match the offset string
    if not match:  # If the offset string does not match the expected format
        raise ValueError(f"Invalid offset format: {offset_str}")

    hours = int(match.group(1) or 0)  # Extract hours or default to 0
    minutes = int(match.group(2) or 0)  # Extract minutes or default to 0
    seconds = int(match.group(3) or 0)  # Extract seconds or default to 0
    milliseconds = int(match.group(4) or 0)  # Extract milliseconds or default to 0

    total_ms = ((hours * 3600 + minutes * 60 + seconds) * 1000) + milliseconds  # Calculate total milliseconds

    return sign * total_ms  # Return the total milliseconds with the correct sign


def get_srt_file(base_name):
    """
    Returns the appropriate subtitle file name if it exists in the same directory
    or any subdirectory.

    :param base_name: The base name of the video file
    :return: The subtitle file name if it exists, None otherwise
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Searching for subtitle file for: {BackgroundColors.CYAN}{base_name}{Style.RESET_ALL}"
    )

    base_dir = os.path.dirname(os.path.abspath(base_name))  # Get directory of the video
    base_no_ext = os.path.splitext(os.path.basename(base_name))[0]  # Get file name without extension

    for root, _, files in os.walk(base_dir):  # Walk through all subdirs
        for file in files:  # For each file in the directory
            if file.startswith(base_no_ext) and file.endswith(
                ".srt"
            ):  # If the file matches the base name and has .srt extension
                return os.path.join(root, file)  # Return the full path to the subtitle file

    return None  # Return None if no subtitle file is found


def adjust_subtitle_timing(srt_file, offset_ms):
    """
    Adjusts the start and end times of all subtitles by offset_ms.

    :param srt_file: Subtitle file path
    :param offset_ms: Offset in milliseconds
    :return: None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Adjusting subtitle timing for: {BackgroundColors.CYAN}{srt_file}{Style.RESET_ALL}"
    )

    try:  # Try to adjust the subtitle timing
        srt_file = os.path.normpath(srt_file)  # Normalize the file path
        ext = os.path.splitext(srt_file)[1].lower()  # Get the file extension

        if ext != ".srt":  # If the file extension is not .srt
            print(
                f"{BackgroundColors.YELLOW}Skipping unsupported file: {BackgroundColors.CYAN}{srt_file}{Style.RESET_ALL}"
            )
            return  # Exit the function

        subs = pysubs2.load(srt_file, format_="srt", encoding="utf-8")  # Load the subtitle file
        subs.shift(ms=offset_ms)  # Shift the subtitle timing by offset_ms

        adjusted_path = (
            srt_file if REPLACE_EXISTING_SRT else os.path.splitext(srt_file)[0] + f"_offset{ext}"
        )  # Determine the adjusted file path
        subs.save(adjusted_path, format_="srt", encoding="utf-8")  # Save the adjusted subtitle file

        verbose_output(
            f"{BackgroundColors.GREEN}Adjusted subtitle saved as: {BackgroundColors.CYAN}{adjusted_path}{Style.RESET_ALL}"
        )

    except Exception as e:  # If an error occurs while adjusting the subtitle timing
        print(f"{BackgroundColors.RED}Error adjusting subtitle {srt_file}: {e}{Style.RESET_ALL}")


def process_directory(directory, offset_ms):
    """
    Processes all subtitles in a directory and applies the offset.

    :param directory: Directory path
    :param offset_ms: Offset in milliseconds
    :return: None
    """

    verbose_output(f"{BackgroundColors.GREEN}Processing directory: {BackgroundColors.CYAN}{directory}{Style.RESET_ALL}")

    directory_abs = os.path.normpath(os.path.abspath(directory))  # Get absolute path of the directory
    srt_files = [
        os.path.join(directory_abs, f) for f in os.listdir(directory_abs) if f.lower().endswith(".srt")
    ]  # List of .srt files in the directory

    for srt_file in tqdm(
        srt_files,
        desc=f"{BackgroundColors.GREEN}Adjusting subtitles in {BackgroundColors.CYAN}{os.path.basename(directory_abs)}",
        unit="file",
    ):  # For each .srt file in the directory with a progress bar
        adjust_subtitle_timing(srt_file, offset_ms)  # Adjust the subtitle timing


def process_all_directories(directories, offset_ms):
    """
    Applies offset adjustment to all subtitle files in the directories.

    :param directories: List of directories
    :param offset_ms: Offset in milliseconds
    :return: None
    """

    for directory in directories:  # For each directory in the list of directories
        process_directory(directory, offset_ms)  # Process the directory

    print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}All subtitles adjusted successfully.{Style.RESET_ALL}")


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
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Subtitle Offset Adjuster{BackgroundColors.GREEN}!{Style.RESET_ALL}\n"
    )

    os.makedirs(INPUT_DIRECTORY, exist_ok=True)  # Ensure the input directory exists

    dirs = get_directories()  # Get all directories with .srt files
    if not dirs:  # If no directories were found
        print(
            f"{BackgroundColors.RED}No directories found in {BackgroundColors.CYAN}Input{BackgroundColors.RED}. Please add .srt files to adjust.{Style.RESET_ALL}"
        )
        return  # Exit the program

    offset_ms = parse_offset(OFFSET)  # Parse the offset string into milliseconds
    verbose_output(
        f"{BackgroundColors.GREEN}Applying offset of {BackgroundColors.CYAN}{OFFSET}{BackgroundColors.GREEN} ({offset_ms} ms){Style.RESET_ALL}"
    )

    process_all_directories(dirs, offset_ms)  # Process all directories

    print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}")
    atexit.register(play_sound)


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
