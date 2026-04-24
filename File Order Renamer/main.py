import atexit  # For playing a sound when the program finishes
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For regular expression matching
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
INPUT_DIRECTORIES = ["./Input"]  # The input directories to process files from

# Ignored Files and Directories:
IGNORED_FILES = {"Makefile", "main.py", "requirements.txt"}  # Files to be ignored
IGNORED_DIRS = {".assets", "venv"}  # Directories to be ignored

# File Constants:
MOVIES_FILE_FORMAT = ["avi", "mkv", "mov", "mp4"]  # The extensions of the movies
SUBTITLES_FILE_FORMAT = ["srt"]  # The extensions of the subtitles
SUBTITLE_VARIATION = {  # Dictionary of languages and their possible subtitle codes
    "Portuguese": ["pt-BR", "pt", "pt-PT"],  # Portuguese subtitle codes
    "English": ["eng", "en", "en-US"],  # English subtitle codes
}

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
    Get all subdirectories inside the input directory.
    Excludes the INPUT_DIRECTORY itself if it contains subdirectories.

    :return: List of absolute paths to subdirectories
    """

    dirs = []  # Initialize aggregate directory list

    for base_dir in INPUT_DIRECTORIES:  # Iterate over each configured base directory
        for root, _, _ in os.walk(base_dir):  # Walk the directory tree for this base directory
            dirs.append(os.path.normpath(os.path.abspath(root)))  # Collect each discovered directory

    # Remove any base directory root if it contains subdirectories to avoid processing the root itself
    base_abs_set = {os.path.normpath(os.path.abspath(d)) for d in INPUT_DIRECTORIES}  # Compute absolute bases set
    for base_abs in base_abs_set:  # Iterate through each absolute base path
        if any(d != base_abs and d.startswith(base_abs + os.sep) for d in dirs):  # Verify if base contains nested dirs
            if base_abs in dirs:  # Verify base_abs presence before removal
                dirs.remove(base_abs)  # Remove the root base directory when nested dirs exist

    return dirs  # Return only valid subdirectories


def getFileFormat(file):
    """
    This function will return the file format of the file.

    :param file: The file to get the format from.
    :return: The file format.
    """

    return file[file.rfind(".") + 1 :]  # Return the file format


def is_two_digit_sequence(filename):
    """
    This function checks if the filename is already in the "two-digit sequence" format (e.g., 01.mkv, 02.s

    :param filename: The filename to check.
    :return: True if the filename is in the "two-digit sequence" format, False otherwise.
    """

    return bool(
        re.match(r"^\d{2}\.[a-zA-Z]+$", filename)
    )  # Verify if the filename is in the "two-digit sequence" format


def all_files_properly_renamed(file_list):
    """
    This function checks if all files in the list are properly renamed.

    :param file_list: The list of files to check.
    :return: True if all files are properly renamed, False otherwise.
    """

    return all(is_two_digit_sequence(file) for file in file_list)  # Check if all files are properly renamed


def getFileNameWithoutExtension(file):
    """
    This function will return the file name without the extension.

    :param file: The file to get the name from.
    :return: The file name without the extension.
    """

    return file[: file.rfind(".")]  # Return the file name without the extension


def get_file_number(file_order):
    """
    Returns the formatted file number.

    :param file_order: The current file order.
    :return: Formatted file number as string.
    """

    return f"0{file_order}" if file_order < 10 else str(file_order)  # Return the formatted file number


def extract_season_episode(file_name):
    """
    This function extracts the season and episode numbers from a file name.

    It supports two patterns:
    - "S{season}E{episode}" (e.g., S01E01)
    - "{episode:02}.{extension}" (e.g., 01.mkv) where season defaults to 1

    :param file_name: The file name to extract the season and episode from.
    :return: A tuple (season, episode) if found, otherwise None.
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Extracting the season and episode numbers from the file name: {BackgroundColors.CYAN}{file_name}{Style.RESET_ALL}"
    )  # Output the verbose message

    # First try the classic SxxExx pattern
    pattern_season_episode = r"S(\d+)E(\d+)"  # Pattern to match season and episode (e.g., S01E01)
    match = re.search(
        pattern_season_episode, file_name, re.IGNORECASE
    )  # Search for the SxxExx pattern in the file name

    if match:  # If the SxxExx pattern is found
        season = int(match.group(1))  # Extract the season number
        episode = int(match.group(2))  # Extract the episode number
        return season, episode  # Return the season and episode numbers as a tuple

    # Fallback to the simplified two-digit prefix pattern (e.g., 01.mkv)
    pattern_two_digit = (
        r"(\d{2})\.(\w+)$"  # Pattern to match a two-digit number before the file extension (e.g., 01.mkv)
    )
    match2 = re.search(pattern_two_digit, file_name)  # Search for the two-digit pattern in the file name

    if match2:  # If the two-digit pattern is found
        season = 1  # Default season number set to 1 for simplified naming convention
        episode = int(match2.group(1))  # Extract the episode number from the two-digit match
        return season, episode  # Return the season and episode numbers as a tuple

    return None  # Return None if no pattern matched


def is_related_movie_subtitle(movie_file, subtitle_file):
    """
    This function checks if the movie name is a substring of the subtitle file name or
    if the season and episode numbers match in both the movie and subtitle files.

    :param movie_file: The movie file name.
    :param subtitle_file: The subtitle file name.
    :return: True if the movie and subtitle are related, False otherwise.
    """

    verbose_output(
        f"{BackgroundColors.YELLOW}Checking if the movie and subtitle are related:{Style.RESET_ALL}"
    )  # Output the verbose message

    movie_base_name = getFileNameWithoutExtension(movie_file)  # Get the movie's base name
    subtitle_base_name = getFileNameWithoutExtension(subtitle_file)  # Get the subtitle's base name

    if movie_base_name in subtitle_base_name:  # If the movie's base name is a substring of the subtitle's base name
        return True  # Return True if the movie and subtitle are related

    movie_season_episode = extract_season_episode(
        movie_base_name
    )  # Extract the season and episode numbers from the movie base name
    subtitle_season_episode = extract_season_episode(
        subtitle_base_name
    )  # Extract the season and episode numbers from the subtitle base name

    if (
        movie_season_episode and subtitle_season_episode
    ):  # If both the movie and subtitle have season and episode numbers
        return movie_season_episode == subtitle_season_episode  # Return True if the season and episode numbers match

    return False  # Return False if no relation is found


def find_related_subtitle(file_list, i, number_of_files):
    """
    Finds the related subtitle for a movie file.

    :param file_list: The list of files in the directory.
    :param i: The index of the current movie file in the list.
    :param number_of_files: The total number of files in the list.
    :return: The related subtitle file if found, otherwise None.
    """

    for j in range(i + 1, number_of_files):  # Loop through subsequent files to find a related subtitle
        if getFileFormat(file_list[j]) in SUBTITLES_FILE_FORMAT and is_related_movie_subtitle(
            file_list[i], file_list[j]
        ):  # If the file is a subtitle and is related to the movie
            return file_list[j]  # Return the related subtitle file if found

    return None  # Return None if no related subtitle is found


def rename_with_subtitle(file_number, dir_path, related_subtitle, has_portuguese):
    """
    Renames a related subtitle file with a language code suffix.
    The movie file is NOT renamed here to prevent multiple renaming errors.
    The first Portuguese subtitle found will be named exactly like the movie, without a suffix.

    :param file_number: The formatted file number to be used in the renaming.
    :param dir_path: The directory path where the files are located.
    :param related_subtitle: The related subtitle file.
    :param has_portuguese: Boolean flag indicating whether a Portuguese subtitle has already been processed.
    :return: Updated has_portuguese flag (True if a Portuguese subtitle was just renamed without suffix)
    """

    sub_base = getFileNameWithoutExtension(related_subtitle)  # Get the base name of the subtitle without extension

    lang_code = "other"  # Default language code

    for lang_family, variants in SUBTITLE_VARIATION.items():  # Loop through each language family and its variants
        for variant in variants:  # Loop through each variant of the language family
            if variant in sub_base:  # If the variant is found in the subtitle base name
                lang_code = variant  # Set the language code to the found variant
                break  # Break the inner loop if a variant is found
        if lang_code != "other":  # If a language code has been found
            break  # Break the outer loop

    # If it's the first Portuguese subtitle, rename it without suffix
    if lang_code in SUBTITLE_VARIATION["Portuguese"] and not has_portuguese:
        new_sub_name = f"{file_number}.srt"  # Portuguese subtitle without suffix
        has_portuguese = True  # Mark that a Portuguese subtitle has already been used
    else:
        new_sub_name = f"{file_number}-{lang_code}.srt"  # Subtitle with language code suffix

    print(
        f"Renaming subtitle: {BackgroundColors.CYAN}{related_subtitle}{BackgroundColors.GREEN} -> {BackgroundColors.CYAN}{new_sub_name}{Style.RESET_ALL}"
    )

    os.rename(
        os.path.join(dir_path, related_subtitle), os.path.join(dir_path, new_sub_name)
    )  # Rename the subtitle file

    return has_portuguese  # Return updated Portuguese flag


def rename_file(file_list, i, dir_path, current_file_format, file_number):
    """
    Renames a movie file when no related subtitle is found.

    :param file_list: The list of files to rename.
    :param i: The index of the movie file in the list.
    :param dir_path: The directory path where the files are located.
    :param current_file_format: The format of the movie file.
    :param file_number: The formatted file number to be used in the renaming.
    :return: None
    """

    print(
        f"Renaming: {BackgroundColors.CYAN}{file_list[i]}{BackgroundColors.GREEN} -> {BackgroundColors.CYAN}{file_number}.{current_file_format}{Style.RESET_ALL}"
    )

    os.rename(
        os.path.join(dir_path, file_list[i]), os.path.join(dir_path, f"{file_number}.{current_file_format}")
    )  # Rename the movie file


def rename_movies(file_list, dir_path):
    """
    Renames movie files and their related subtitles with language code suffix.
    The first Portuguese subtitle found for each movie is renamed without suffix.
    Movie files are renamed exactly once after their subtitles are processed.

    :param file_list: List of files in the directory.
    :param dir_path: Path of the directory.
    :return: None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Renaming the files in the directory: {BackgroundColors.CYAN}{dir_path}{Style.RESET_ALL}"
    )

    movie_files = [file for file in file_list if getFileFormat(file) not in SUBTITLES_FILE_FORMAT]  # Movie files
    subtitle_files = [file for file in file_list if getFileFormat(file) in SUBTITLES_FILE_FORMAT]  # Subtitle files

    movie_files.sort()  # Sort movie files
    subtitle_files.sort()  # Sort subtitle files

    file_order = 1  # Initialize file numbering

    # Loop through each movie file
    for movie_file in movie_files:
        current_file_format = getFileFormat(movie_file)  # Get movie file format
        file_number = get_file_number(file_order)  # Get formatted file number

        related_subs = [
            sub for sub in subtitle_files if is_related_movie_subtitle(movie_file, sub)
        ]  # Find all related subtitles for this movie

        has_portuguese = False  # Track if a Portuguese subtitle was already renamed without suffix

        for sub in related_subs:  # Rename all related subtitles with language code suffix
            has_portuguese = rename_with_subtitle(
                file_number, dir_path, sub, has_portuguese
            )  # Rename the related subtitle and update flag
            if sub in subtitle_files:  # If the subtitle is still in the list
                subtitle_files.remove(sub)  # Remove renamed subtitle from the list

        print(
            f"Renaming movie: {BackgroundColors.CYAN}{movie_file}{BackgroundColors.GREEN} -> {BackgroundColors.CYAN}{file_number}.{current_file_format}{Style.RESET_ALL}"
        )
        os.rename(
            os.path.join(dir_path, movie_file), os.path.join(dir_path, f"{file_number}.{current_file_format}")
        )  # Rename the movie file

        file_order += 1  # Increment file order

    for sub in subtitle_files:  # Loop through leftover subtitle files
        current_file_format = getFileFormat(sub)  # Get subtitle file format
        file_number = get_file_number(file_order)  # Get formatted file number
        rename_file(
            file_list, file_list.index(sub), dir_path, current_file_format, file_number
        )  # Rename the leftover subtitle file
        file_order += 1  # Increment file order


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
        f"{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}File Order Renamer{BackgroundColors.GREEN}!{Style.RESET_ALL}",
        end="\n\n",
    )

    if not any(verify_filepath_exists(d) for d in INPUT_DIRECTORIES):  # Verify at least one configured input directory exists
        print(
            f"{BackgroundColors.RED}Input directories {BackgroundColors.CYAN}{', '.join(INPUT_DIRECTORIES)}{BackgroundColors.RED} not found. Please create the directories and add files to them.{Style.RESET_ALL}"
        )  # Output the error message listing all configured input directories
        return  # Exit the program when none of the configured input directories exist

    dirs = get_directories()  # Get all directories inside the input directory

    for dir_path in dirs:  # Loop through each directory
        if any(
            ignored_dir in dir_path for ignored_dir in IGNORED_DIRS
        ):  # If the directory is in the ignored directories
            continue  # Skip the directory if it is in the ignored directories

        files = os.listdir(dir_path)  # List all files in the current directory

        file_list = [
            file
            for file in files
            if file not in IGNORED_FILES
            and (getFileFormat(file) in MOVIES_FILE_FORMAT or getFileFormat(file) in SUBTITLES_FILE_FORMAT)
        ]  # Get the list of files in the directory
        file_list.sort()  # Sort the list of files

        if len(file_list) == 0:  # If there are no files in the directory
            print(
                f"{BackgroundColors.CYAN}No files found in the directory: {dir_path}{Style.RESET_ALL}"
            )  # Output the message
        else:  # If there are files in the directory
            print(f"{BackgroundColors.GREEN}Processing directory: {dir_path}{Style.RESET_ALL}")  # Output the message
            if all_files_properly_renamed(file_list):  # If all files are already properly renamed
                print(
                    f"{BackgroundColors.CYAN}All files are already properly renamed in this directory.{Style.RESET_ALL}"
                )  # Output the message
            else:  # If not all files are properly renamed
                rename_movies(file_list, dir_path)  # Rename the files

    print(f"\n{BackgroundColors.GREEN}Finished renaming the files!{Style.RESET_ALL}")

    atexit.register(play_sound)  # Register the function to play a sound when the program finishes


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
