"""
================================================================================
Dubbed-Subtitled Movie Audio Tracks Length Matcher
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-09
Description :
    Scan movie files under the dubbed and subtitled library folders, match
    movies that exist in both trees, compare their real video durations, and
    generate JSON reports for equal-length and different-length pairs.

    Key features include:
        - Recursive video discovery under E:\\Movies\\Dublado and E:\\Movies\\Legendado
        - Release-name parsing for movie title, year, and resolution
        - Deterministic fuzzy title matching with exact-year pairing
        - Video duration extraction through ffprobe at whole-second precision
        - Structured JSON report generation in the local Reports directory

Usage:
    1. Ensure the input folders exist under E:\\Movies and ffprobe is available on PATH.
    2. Run the script with Make or Python.
        $ make run   or   $ python main.py
    3. Review the generated report files inside the Reports directory.

Outputs:
    - Reports/movies_same_length.json
    - Reports/movies_different_length.json

TODOs:
    - Add CLI arguments if the input root or report output path must vary.
    - Extend supported video extensions if another real container format is needed.
    - Add optional unmatched-movie reporting if library reconciliation needs it.

Dependencies:
    - Python >= 3.10
    - colorama
    - ffprobe available on PATH

Assumptions & Notes:
    - Movie identity is determined from parsed movie title plus four-digit year.
    - Subtitle and other sidecar files are ignored by explicit video-extension filtering.
    - Reports are written relative to the repository directory that contains this script.
"""

import atexit  # For playing a sound when the program finishes
import datetime  # For getting the current date and time
import difflib  # For deterministic fuzzy title matching
import json  # For writing structured report files
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For parsing release names
import subprocess  # For reading video metadata through ffprobe
import sys  # For system-specific parameters and functions
import unicodedata  # For normalizing accented title text
from colorama import Style  # For coloring the terminal
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
INPUT_DIRECTORY = "E:/Movies"  # Input directory containing movie category folders
DUBLADO_DIRECTORY = os.path.join(INPUT_DIRECTORY, "Dublado")  # Dublado movie directory
LEGENDADO_DIRECTORY = os.path.join(INPUT_DIRECTORY, "Legendado")  # Legendado movie directory
REPORTS_DIRECTORY = Path(__file__).resolve().parent / "Reports"  # Repository report output directory
VIDEO_EXTENSIONS = {".avi", ".m2ts", ".m4v", ".mkv", ".mov", ".mp4", ".mpeg", ".mpg", ".ts", ".webm", ".wmv"}  # Supported movie file extensions
TITLE_MATCH_THRESHOLD = 0.90  # Minimum normalized title similarity for a match
YEAR_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b")  # Release year pattern
RESOLUTION_PATTERN = re.compile(r"\b(?:\d{3,4}p|[48]k|hd|fullhd|uhd)\b", re.IGNORECASE)  # Release resolution pattern

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


def extract_resolution(release_suffix: str) -> str:
    """
    Extract the first resolution token from a release suffix.

    :param release_suffix: Release name text after the parsed year.
    :return: Resolution token or an empty string.
    """

    resolution_match = RESOLUTION_PATTERN.search(release_suffix)  # Locate resolution token in suffix
    if resolution_match:  # Verify a resolution token was found
        return resolution_match.group(0)  # Return original resolution token
    return ""  # Return empty resolution when missing


def parse_movie_file(movie_path: Path) -> dict[str, object] | None:
    """
    Parse a movie file path into comparison metadata.

    :param movie_path: Actual movie file path.
    :return: Parsed movie metadata or None when parsing fails.
    """

    release_name = movie_path.stem.strip()  # Read filename without extension
    year_matches = list(YEAR_PATTERN.finditer(release_name))  # Locate all valid four-digit release years
    if not year_matches:  # Verify release year exists
        verbose_output(true_string=f"{BackgroundColors.YELLOW}Skipping movie without year: {BackgroundColors.CYAN}{movie_path}{Style.RESET_ALL}")  # Log missing year
        return None  # Skip files without release year

    year_match = year_matches[-1]  # Use last valid year so numeric title content remains intact
    movie_name = release_name[:year_match.start()].strip()  # Keep title text before release year
    if not movie_name:  # Verify parsed title exists
        verbose_output(true_string=f"{BackgroundColors.YELLOW}Skipping movie without title: {BackgroundColors.CYAN}{movie_path}{Style.RESET_ALL}")  # Log missing title
        return None  # Skip files without title

    release_suffix = release_name[year_match.end():].strip()  # Capture metadata text after release year
    parsed_movie: dict[str, object] = {  # Build parsed movie record
        "MovieName": movie_name,  # Preserve original parsed movie title
        "NormalizedMovieName": normalize_movie_title(movie_name),  # Store normalized comparison title
        "Year": year_match.group(0),  # Store parsed release year
        "Resolution": extract_resolution(release_suffix),  # Store parsed resolution
        "Path": str(movie_path),  # Store actual movie file path
    }  # Finish parsed movie record
    
    return parsed_movie  # Return parsed metadata


def discover_movie_files(directory_path: str) -> list[dict[str, object]]:
    """
    Recursively discover movie files under a directory.

    :param directory_path: Directory path to scan.
    :return: Parsed movie metadata records.
    """

    movies = []  # Initialize parsed movie list
    root_path = Path(directory_path)  # Convert directory string to Path
    if not root_path.exists():  # Verify scan directory exists
        print(f"{BackgroundColors.RED}Directory not found: {BackgroundColors.CYAN}{directory_path}{Style.RESET_ALL}")  # Log missing directory
        return movies  # Return empty list when directory is absent

    for movie_path in root_path.rglob("*"):  # Traverse directory tree recursively
        if not movie_path.is_file():  # Verify current path is a file
            continue  # Skip folders

        if movie_path.suffix.casefold() not in VIDEO_EXTENSIONS:  # Verify file extension is a movie extension
            continue  # Skip subtitles and sidecar files

        parsed_movie = parse_movie_file(movie_path)  # Parse candidate movie file
        if parsed_movie is None:  # Verify parsing succeeded
            continue  # Skip unparsable movie file

        movies.append(parsed_movie)  # Store parsed movie metadata

    return movies  # Return discovered movie records


def movie_similarity(dublado_movie: dict[str, object], legendado_movie: dict[str, object]) -> float:
    """
    Calculate normalized title similarity for two parsed movies.

    :param dublado_movie: Parsed Dublado movie metadata.
    :param legendado_movie: Parsed Legendado movie metadata.
    :return: Similarity ratio between normalized titles.
    """

    dublado_title = str(dublado_movie["NormalizedMovieName"])  # Read normalized Dublado title
    legendado_title = str(legendado_movie["NormalizedMovieName"])  # Read normalized Legendado title
    return difflib.SequenceMatcher(None, dublado_title, legendado_title).ratio()  # Return deterministic similarity score


def select_movie_pairs(dublado_movies: list[dict[str, object]], legendado_movies: list[dict[str, object]]) -> list[tuple[dict[str, object], dict[str, object], float]]:
    """
    Select deterministic one-to-one Dublado and Legendado movie pairs.

    :param dublado_movies: Parsed Dublado movie metadata records.
    :param legendado_movies: Parsed Legendado movie metadata records.
    :return: Matched movie pairs with similarity scores.
    """

    candidates = []  # Initialize eligible match candidates
    for dublado_index, dublado_movie in enumerate(dublado_movies):  # Iterate Dublado movies with stable index
        for legendado_index, legendado_movie in enumerate(legendado_movies):  # Iterate Legendado movies with stable index
            if dublado_movie["Year"] != legendado_movie["Year"]:  # Verify release years match exactly
                continue  # Skip movies from different years

            similarity = movie_similarity(dublado_movie, legendado_movie)  # Calculate normalized title similarity
            if similarity < TITLE_MATCH_THRESHOLD:  # Verify similarity meets minimum threshold
                continue  # Skip weak matches

            candidates.append((similarity, dublado_index, legendado_index, dublado_movie, legendado_movie))  # Store eligible candidate

    candidates.sort(key=lambda candidate: (-candidate[0], str(candidate[3]["NormalizedMovieName"]), str(candidate[4]["NormalizedMovieName"]), str(candidate[3]["Path"]), str(candidate[4]["Path"])))  # Sort by best score with deterministic ties
    used_dublado_indexes = set()  # Track paired Dublado records
    used_legendado_indexes = set()  # Track paired Legendado records
    selected_pairs = []  # Initialize selected one-to-one pairs

    for similarity, dublado_index, legendado_index, dublado_movie, legendado_movie in candidates:  # Iterate sorted candidates
        if dublado_index in used_dublado_indexes or legendado_index in used_legendado_indexes:  # Verify neither side is already paired
            continue  # Skip duplicate pairing

        used_dublado_indexes.add(dublado_index)  # Mark Dublado movie as paired
        used_legendado_indexes.add(legendado_index)  # Mark Legendado movie as paired
        selected_pairs.append((dublado_movie, legendado_movie, similarity))  # Store final pair

    return selected_pairs  # Return deterministic selected pairs


def get_video_duration_seconds(movie_path: str) -> int | None:
    """
    Read a video duration with ffprobe at whole-second precision.

    :param movie_path: Actual movie file path.
    :return: Whole-second duration or None when unavailable.
    """

    try:  # Guard ffprobe execution so one bad file does not stop report generation
        result = subprocess.run(  # Execute ffprobe for duration metadata
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", movie_path],  # Pass ffprobe arguments without shell parsing
            capture_output=True,  # Capture stdout and stderr
            text=True,  # Decode process output as text
            timeout=60,  # Bound metadata read time
        )  # Finish ffprobe execution
        if result.returncode != 0:  # Verify ffprobe completed successfully
            verbose_output(true_string=f"{BackgroundColors.YELLOW}ffprobe failed for: {BackgroundColors.CYAN}{movie_path}{Style.RESET_ALL}")  # Log ffprobe failure
            return None  # Return unavailable duration

        duration_text = result.stdout.strip()  # Normalize ffprobe output
        if not duration_text:  # Verify duration output exists
            return None  # Return unavailable duration

        return int(round(float(duration_text)))  # Return whole-second duration
    except Exception:  # Handle missing ffprobe, timeout, or malformed duration output
        verbose_output(true_string=f"{BackgroundColors.YELLOW}Unable to read duration for: {BackgroundColors.CYAN}{movie_path}{Style.RESET_ALL}")  # Log duration failure
        return None  # Return unavailable duration


def format_duration(duration_seconds: int | None) -> str:
    """
    Format whole seconds as HH:MM:SS.

    :param duration_seconds: Whole-second duration or None.
    :return: Formatted duration string.
    """

    if duration_seconds is None:  # Verify duration is available
        return ""  # Return empty value when unavailable

    hours = duration_seconds // 3600  # Calculate full hours
    minutes = (duration_seconds % 3600) // 60  # Calculate remaining minutes
    seconds = duration_seconds % 60  # Calculate remaining seconds
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"  # Return HH:MM:SS duration


def merge_pair_value(dublado_value: object, legendado_value: object) -> object:
    """
    Preserve pair values when Dublado and Legendado records differ.

    :param dublado_value: Dublado value.
    :param legendado_value: Legendado value.
    :return: Single shared value or a side-specific value mapping.
    """

    if dublado_value == legendado_value:  # Verify values are identical
        return dublado_value  # Return single shared value
    return {"Dublado": dublado_value, "Legendado": legendado_value}  # Return side-specific values


def build_report_record(dublado_movie: dict[str, object], legendado_movie: dict[str, object], dublado_duration: int | None, legendado_duration: int | None) -> dict[str, object]:
    """
    Build a report record for a matched movie pair.

    :param dublado_movie: Parsed Dublado movie metadata.
    :param legendado_movie: Parsed Legendado movie metadata.
    :param dublado_duration: Dublado whole-second duration.
    :param legendado_duration: Legendado whole-second duration.
    :return: Structured JSON report record.
    """

    dublado_length = format_duration(dublado_duration)  # Format Dublado duration
    legendado_length = format_duration(legendado_duration)  # Format Legendado duration
    report_record = {  # Build report record with required top-level fields
        "MovieName": merge_pair_value(dublado_movie["MovieName"], legendado_movie["MovieName"]),  # Preserve title values
        "Year": dublado_movie["Year"],  # Store exact matched release year
        "Resolution": merge_pair_value(dublado_movie["Resolution"], legendado_movie["Resolution"]),  # Preserve resolution values
        "Length": merge_pair_value(dublado_length, legendado_length),  # Preserve duration values
        "DubladoPath": dublado_movie["Path"],  # Store actual Dublado file path
        "LegendadoPath": legendado_movie["Path"],  # Store actual Legendado file path
    }  # Finish report record
    return report_record  # Return report record


def report_sort_key(report_record: dict[str, object]) -> str:
    """
    Build a deterministic case-insensitive report sort key.

    :param report_record: Structured JSON report record.
    :return: Normalized sort key.
    """

    movie_name = report_record["MovieName"]  # Read report movie name field
    if isinstance(movie_name, dict):  # Verify movie name contains side-specific values
        movie_name = movie_name.get("Dublado", next(iter(movie_name.values()), ""))  # Prefer Dublado title for sorting
    return normalize_movie_title(str(movie_name))  # Return normalized sort text


def write_json_report(report_path: Path, report_records: list[dict[str, object]]) -> None:
    """
    Write report records as deterministic human-readable JSON.

    :param report_path: JSON report path.
    :param report_records: Structured report records.
    :return: None.
    """

    sorted_records = sorted(report_records, key=report_sort_key)  # Sort records deterministically by movie name
    with report_path.open("w", encoding="utf-8") as report_file:  # Open report file for UTF-8 JSON writing
        json.dump(sorted_records, report_file, ensure_ascii=False, indent=4)  # Write human-readable JSON content
        report_file.write("\n")  # End file with newline


def generate_movie_overlap_reports() -> None:
    """
    Generate Dublado and Legendado overlap reports grouped by movie duration.

    :return: None.
    """

    print(f"{BackgroundColors.GREEN}Scanning Dublado movies in: {BackgroundColors.CYAN}{DUBLADO_DIRECTORY}{Style.RESET_ALL}")  # Log Dublado scan path
    dublado_movies = discover_movie_files(DUBLADO_DIRECTORY)  # Discover Dublado movie files

    print(f"{BackgroundColors.GREEN}Scanning Legendado movies in: {BackgroundColors.CYAN}{LEGENDADO_DIRECTORY}{Style.RESET_ALL}")  # Log Legendado scan path
    legendado_movies = discover_movie_files(LEGENDADO_DIRECTORY)  # Discover Legendado movie files

    matched_pairs = select_movie_pairs(dublado_movies, legendado_movies)  # Match movies by year and fuzzy title
    same_length_movies = []  # Initialize equal-duration report records
    different_length_movies = []  # Initialize different-duration report records

    for dublado_movie, legendado_movie, similarity in matched_pairs:  # Iterate matched movie pairs
        verbose_output(true_string=f"{BackgroundColors.GREEN}Matched {BackgroundColors.CYAN}{dublado_movie['Path']}{BackgroundColors.GREEN} with {BackgroundColors.CYAN}{legendado_movie['Path']}{BackgroundColors.GREEN} at {similarity:.3f}{Style.RESET_ALL}")  # Log matched pair
        dublado_duration = get_video_duration_seconds(str(dublado_movie["Path"]))  # Read Dublado video duration
        legendado_duration = get_video_duration_seconds(str(legendado_movie["Path"]))  # Read Legendado video duration
        report_record = build_report_record(dublado_movie, legendado_movie, dublado_duration, legendado_duration)  # Build output record

        if dublado_duration is not None and dublado_duration == legendado_duration:  # Verify durations are available and equal
            same_length_movies.append(report_record)  # Store equal-duration record
        else:  # Handle different or unavailable durations
            different_length_movies.append(report_record)  # Store different-duration record

    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)  # Create Reports directory when missing
    write_json_report(REPORTS_DIRECTORY / "movies_same_length.json", same_length_movies)  # Write equal-duration report
    write_json_report(REPORTS_DIRECTORY / "movies_different_length.json", different_length_movies)  # Write different-duration report

    print(f"{BackgroundColors.GREEN}Matched movie pairs: {BackgroundColors.CYAN}{len(matched_pairs)}{Style.RESET_ALL}")  # Log total matched pairs
    print(f"{BackgroundColors.GREEN}Same length report records: {BackgroundColors.CYAN}{len(same_length_movies)}{Style.RESET_ALL}")  # Log equal-duration count
    print(f"{BackgroundColors.GREEN}Different length report records: {BackgroundColors.CYAN}{len(different_length_movies)}{Style.RESET_ALL}")  # Log different-duration count


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
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Dubbed-Subtitled Movie Audio Tracks Length Matcher{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the welcome message
    
    start_time = datetime.datetime.now()  # Get the start time of the program
    
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
