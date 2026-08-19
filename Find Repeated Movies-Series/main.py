"""
================================================================================
Find Repeated Movies-Series
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-19
Description :
    Recursively scans a movie library and identifies repeated movie titles from
    directory names that follow the configured movie-directory naming pattern.
    Duplicate detection is based only on the movie title, ignoring release year,
    resolution, language, letter casing, accents, punctuation, and extra spacing.

    Key features include:
        - Recursive scanning through directories and subdirectories at any depth.
        - Anchored parsing of movie name, year, resolution, and language.
        - Accent/case/punctuation-insensitive movie-title comparison.
        - Duplicate grouping with every matching directory and its metadata.
        - UTF-8 JSON report generation under ./Outputs/.

Usage:
    1. Set INPUT_DIR if the movie library is not E:/Movies/.
    2. Run the script:
        $ python main.py
    3. Review the generated JSON report in ./Outputs/.

Outputs:
    - ./Outputs/<input-directory-prefix>report.json
    - ./Logs/main.log

Dependencies:
    - Python >= 3.9
    - colorama
    - Project Logger module (Logger.py)

Assumptions & Notes:
    - Movie directories must end with: <MovieName> <YYYY> <Resolution> <Language>.
    - Supported languages are Dual, Legendado, Dublado, Nacional, and English.
    - Typical resolutions such as 720p, 1080p, 2160p, and 4320p are supported.
    - The Windows drive colon is removed from the report filename because ':' is
      not valid in Windows filenames. For E:/Movies/, the report is named
      E-Movies-report.json.
"""

import atexit  # For playing a sound when the program finishes
import datetime  # For getting the current date and time
import json  # For writing the duplicate movie report
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For parsing directory names and normalizing report filenames
import sys  # For system-specific parameters and functions
import unicodedata  # For accent-insensitive movie title comparison
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
INPUT_DIR = f"E:/Movies/"  # Root directory recursively scanned for movie directories
OUTPUT_DIR = "./Outputs/"  # Directory where the JSON report is written
SUPPORTED_LANGUAGES = ("Dual", "Legendado", "Dublado", "Nacional", "English")
MOVIE_DIRECTORY_PATTERN = re.compile(
    rf"^(?P<movie_name>.+?)\s+(?P<year>\d{{4}})\s+(?P<resolution>\d{{3,4}}p)\s+(?P<language>{'|'.join(SUPPORTED_LANGUAGES)})$",
    re.IGNORECASE,
)  # Parse metadata only from the anchored end of a directory name

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


def normalize_movie_name(movie_name: str) -> str:
    """
    Normalize a movie title for duplicate comparison.

    The comparison ignores casing, accents, punctuation, and repeated whitespace,
    while preserving letters and numbers that are meaningful parts of the title.

    :param movie_name: Original movie title extracted from the directory name.
    :return: Normalized comparison key.
    """

    normalized = unicodedata.normalize("NFKD", movie_name)  # Split accented characters
    normalized = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )  # Remove accent marks
    normalized = normalized.casefold()  # Normalize casing more thoroughly than lower()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)  # Treat punctuation as separators
    normalized = re.sub(r"_+", " ", normalized)  # Treat underscores as separators too
    normalized = re.sub(r"\s+", " ", normalized).strip()  # Collapse whitespace
    return normalized


def parse_movie_directory_name(directory_name: str):
    """
    Parse a movie directory name that follows the expected naming convention.

    Parsing is anchored at the end of the directory name so numbers inside movie
    titles, such as "Toy Story 1" or "Resident Evil 3", remain part of the title.

    :param directory_name: Directory basename to parse.
    :return: Parsed metadata dictionary, or None when the directory does not match.
    """

    if not isinstance(directory_name, str):
        return None

    match = MOVIE_DIRECTORY_PATTERN.fullmatch(directory_name.strip())
    if match is None:
        return None

    movie_name = match.group("movie_name").strip()
    if not movie_name:
        return None

    language_lookup = {language.casefold(): language for language in SUPPORTED_LANGUAGES}
    language = language_lookup[match.group("language").casefold()]

    return {
        "movie_name": movie_name,
        "normalized_movie_name": normalize_movie_name(movie_name),
        "year": int(match.group("year")),
        "resolution": match.group("resolution").lower(),
        "language": language,
    }


def scan_movie_directories(input_dir: str):
    """
    Recursively scan all descendant directories and collect valid movie entries.

    :param input_dir: Root directory to scan.
    :return: Tuple containing parsed movie entries and total directory count.
    """

    movie_entries = []
    total_directories_scanned = 0

    def handle_walk_error(error):
        print(
            f"{BackgroundColors.YELLOW}Warning: unable to scan "
            f"{BackgroundColors.CYAN}{getattr(error, 'filename', 'unknown path')}"
            f"{BackgroundColors.YELLOW}: {error}{Style.RESET_ALL}"
        )

    for current_root, directory_names, _ in os.walk(input_dir, onerror=handle_walk_error):
        for directory_name in directory_names:
            total_directories_scanned += 1
            metadata = parse_movie_directory_name(directory_name)
            if metadata is None:
                continue

            full_path = os.path.normpath(os.path.join(current_root, directory_name))
            relative_path = os.path.relpath(full_path, input_dir)
            movie_entries.append(
                {
                    **metadata,
                    "directory_name": directory_name,
                    "relative_path": relative_path,
                    "path": full_path,
                }
            )

            verbose_output(
                true_string=(
                    f"{BackgroundColors.GREEN}Matched movie directory: "
                    f"{BackgroundColors.CYAN}{full_path}{Style.RESET_ALL}"
                )
            )

    return movie_entries, total_directories_scanned


def find_duplicate_movies(movie_entries):
    """
    Group movie entries whose normalized movie titles are equal.

    :param movie_entries: Parsed movie directory entries.
    :return: Sorted list containing only movie-title groups with 2+ occurrences.
    """

    grouped_entries = {}
    for entry in movie_entries:
        key = entry["normalized_movie_name"]
        grouped_entries.setdefault(key, []).append(entry)

    duplicate_groups = []
    for normalized_name, entries in grouped_entries.items():
        if len(entries) < 2:
            continue

        sorted_entries = sorted(
            entries,
            key=lambda entry: (
                entry["year"],
                entry["resolution"],
                entry["language"].casefold(),
                entry["path"].casefold(),
            ),
        )
        movie_name_variants = sorted(
            {entry["movie_name"] for entry in sorted_entries},
            key=str.casefold,
        )

        duplicate_groups.append(
            {
                "movie_name": sorted_entries[0]["movie_name"],
                "normalized_movie_name": normalized_name,
                "movie_name_variants": movie_name_variants,
                "occurrences": len(sorted_entries),
                "entries": [
                    {
                        "directory_name": entry["directory_name"],
                        "year": entry["year"],
                        "resolution": entry["resolution"],
                        "language": entry["language"],
                        "relative_path": entry["relative_path"],
                        "path": entry["path"],
                    }
                    for entry in sorted_entries
                ],
            }
        )

    duplicate_groups.sort(key=lambda group: group["normalized_movie_name"])
    return duplicate_groups


def build_report_filename(input_dir: str) -> str:
    """
    Build the report filename from INPUT_DIR using Windows-safe characters.

    Slashes and backslashes are replaced by hyphens as requested. A Windows drive
    colon is removed because ':' cannot be used inside a Windows filename.

    Example: E:/Movies/ -> E-Movies-report.json

    :param input_dir: Input directory used by the scan.
    :return: Safe JSON report filename.
    """

    prefix = str(input_dir).strip().replace("\\", "-").replace("/", "-")
    prefix = prefix.replace(":", "")  # Required for Windows filename compatibility
    prefix = re.sub(r'[<>"|?*]', '-', prefix)  # Sanitize remaining Windows-invalid filename characters
    prefix = re.sub(r"-+", "-", prefix).strip("- .")

    if not prefix:
        prefix = "movies"

    return f"{prefix}-report.json"


def write_duplicate_report(input_dir: str, movie_entries, total_directories_scanned: int, duplicate_groups):
    """
    Write the duplicate movie report to OUTPUT_DIR.

    :param input_dir: Root directory scanned.
    :param movie_entries: All matching movie directory entries.
    :param total_directories_scanned: Number of descendant directories inspected.
    :param duplicate_groups: Duplicate title groups generated from movie_entries.
    :return: Path to the written JSON report.
    """

    output_dir = Path(OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / build_report_filename(input_dir)

    unique_movie_names = {entry["normalized_movie_name"] for entry in movie_entries}
    duplicate_movie_directories = sum(group["occurrences"] for group in duplicate_groups)

    report = {
        "input_dir": input_dir,
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "expected_directory_format": "<MovieName> <YYYY> <Resolution> <Dual|Legendado|Dublado|Nacional|English>",
        "comparison": {
            "based_on": "movie_name_only",
            "ignores": [
                "year",
                "resolution",
                "language",
                "letter_casing",
                "accents",
                "punctuation",
                "extra_whitespace",
            ],
        },
        "summary": {
            "directories_scanned": total_directories_scanned,
            "matching_movie_directories": len(movie_entries),
            "non_matching_directories": total_directories_scanned - len(movie_entries),
            "unique_movie_names": len(unique_movie_names),
            "duplicate_movie_names": len(duplicate_groups),
            "directories_in_duplicate_groups": duplicate_movie_directories,
        },
        "duplicates": duplicate_groups,
    }

    with report_path.open("w", encoding="utf-8") as report_file:
        json.dump(report, report_file, ensure_ascii=False, indent=4)
        report_file.write("\n")

    return report_path


def run_duplicate_movie_scan(input_dir: str = INPUT_DIR):
    """
    Validate input, scan movie directories, find duplicates, and write the report.

    :param input_dir: Root movie directory to scan recursively.
    :return: Tuple containing the report path, all matched entries, and duplicates.
    """

    if not verify_filepath_exists(input_dir):
        raise FileNotFoundError(f"Input directory not found: {input_dir}")
    if not os.path.isdir(input_dir):
        raise NotADirectoryError(f"Input path is not a directory: {input_dir}")

    movie_entries, total_directories_scanned = scan_movie_directories(input_dir)
    duplicate_groups = find_duplicate_movies(movie_entries)
    report_path = write_duplicate_report(
        input_dir,
        movie_entries,
        total_directories_scanned,
        duplicate_groups,
    )

    return report_path, movie_entries, duplicate_groups


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
    Scan INPUT_DIR recursively, identify duplicate movie titles, and write the report.

    :param: None
    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Find Repeated Movies-Series{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
    )

    start_time = datetime.datetime.now()

    try:
        report_path, movie_entries, duplicate_groups = run_duplicate_movie_scan(INPUT_DIR)

        print(
            f"{BackgroundColors.GREEN}Matching movie directories: "
            f"{BackgroundColors.CYAN}{len(movie_entries)}{Style.RESET_ALL}"
        )
        print(
            f"{BackgroundColors.GREEN}Repeated movie names: "
            f"{BackgroundColors.CYAN}{len(duplicate_groups)}{Style.RESET_ALL}"
        )

        if duplicate_groups:
            print(f"{BackgroundColors.YELLOW}Repeated movies:{Style.RESET_ALL}")
            for group in duplicate_groups:
                print(
                    f"  {BackgroundColors.CYAN}{group['movie_name']}"
                    f"{BackgroundColors.GREEN} ({group['occurrences']} occurrences){Style.RESET_ALL}"
                )
        else:
            print(f"{BackgroundColors.GREEN}No repeated movie names found.{Style.RESET_ALL}")

        print(
            f"{BackgroundColors.GREEN}JSON report written to: "
            f"{BackgroundColors.CYAN}{report_path}{Style.RESET_ALL}"
        )
    except Exception as error:
        print(
            f"{BackgroundColors.RED}Failed to scan movie library: "
            f"{BackgroundColors.CYAN}{error}{Style.RESET_ALL}"
        )
        raise
    finally:
        finish_time = datetime.datetime.now()
        print(
            f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n"
            f"{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n"
            f"{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"
        )
        print(
            f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
        )
        if RUN_FUNCTIONS["Play Sound"]:
            atexit.register(play_sound)


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
