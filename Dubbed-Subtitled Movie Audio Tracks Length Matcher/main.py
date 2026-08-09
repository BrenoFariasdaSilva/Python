"""
================================================================================
Dubbed-Subtitled Movie Audio Tracks Length Matcher
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-09
Description :
    Scan movie files under dubbed, subtitled, and dual-audio library folders,
    match movies that exist in at least two source trees, compare their real
    video durations, and generate JSON reports for equal-length and
    different-length matches.

    Key features include:
        - Recursive video discovery under E:\\Movies\\Dublado, E:\\Movies\\Legendado, and E:\\Movies\\Dual
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
DUAL_DIRECTORY = os.path.join(INPUT_DIRECTORY, "Dual")  # Dual movie directory
SOURCE_NAMES = ("Dublado", "Legendado", "Dual")  # Source names in deterministic report order
SOURCE_DIRECTORIES = {"Dublado": DUBLADO_DIRECTORY, "Legendado": LEGENDADO_DIRECTORY, "Dual": DUAL_DIRECTORY}  # Source directories by source name
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


def normalize_movie_title(movie_name: str) -> str:
    """
    Normalize a movie title for deterministic comparison.

    :param movie_name: Movie title extracted from a release name.
    :return: Normalized movie title.
    """

    normalized = unicodedata.normalize("NFKD", movie_name)  # Split accented characters into comparable parts
    normalized = "".join(character for character in normalized if not unicodedata.combining(character))  # Remove accent marks
    normalized = normalized.casefold()  # Normalize case for comparison
    normalized = re.sub(r"[^\w\s]", " ", normalized, flags=re.UNICODE)  # Replace punctuation with spaces
    normalized = re.sub(r"\s+", " ", normalized).strip()  # Collapse repeated whitespace
    return normalized  # Return normalized title


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

    movies.sort(key=lambda movie: (str(movie["Year"]), str(movie["NormalizedMovieName"]), str(movie["Path"])))  # Sort movies deterministically
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


def movie_record_key(movie: dict[str, object]) -> str:
    """
    Build a stable physical movie file key.

    :param movie: Parsed movie metadata.
    :return: Stable physical movie file key.
    """

    return str(movie["Path"])  # Return stable physical file key


def movie_group_sort_key(movie_group: dict[str, dict[str, object]]) -> str:
    """
    Build a deterministic sort key for a matched movie group.

    :param movie_group: Matched source movie group.
    :return: Normalized movie group sort key.
    """

    source_names = [source_name for source_name in SOURCE_NAMES if source_name in movie_group]  # Preserve configured source order
    first_movie = movie_group[source_names[0]]  # Read first available source movie
    return f"{first_movie['Year']}|{normalize_movie_title(str(first_movie['MovieName']))}|{movie_record_key(first_movie)}"  # Return stable group key


def select_movie_groups(source_movies: dict[str, list[dict[str, object]]]) -> list[dict[str, dict[str, object]]]:
    """
    Select deterministic matched movie groups across configured sources.

    :param source_movies: Parsed movie metadata records by source name.
    :return: Matched movie groups containing at least two sources.
    """

    candidates: list[tuple[float, str, str, dict[str, object], dict[str, object]]] = []  # Initialize eligible match candidates
    for left_source_index, left_source_name in enumerate(SOURCE_NAMES):  # Iterate source names in deterministic order
        for right_source_name in SOURCE_NAMES[left_source_index + 1:]:  # Iterate later source names for cross-source pairs
            left_movies = source_movies.get(left_source_name, [])  # Read left source movies
            right_movies = source_movies.get(right_source_name, [])  # Read right source movies

            for left_movie in left_movies:  # Iterate left source movies
                for right_movie in right_movies:  # Iterate right source movies
                    if left_movie["Year"] != right_movie["Year"]:  # Verify release years match exactly
                        continue  # Skip movies from different years

                    similarity = movie_similarity(left_movie, right_movie)  # Calculate normalized title similarity
                    if similarity < TITLE_MATCH_THRESHOLD:  # Verify similarity meets minimum threshold
                        continue  # Skip weak matches

                    candidates.append((similarity, left_source_name, right_source_name, left_movie, right_movie))  # Store eligible candidate

    candidates.sort(key=lambda candidate: (-candidate[0], candidate[1], candidate[2], str(candidate[3]["NormalizedMovieName"]), str(candidate[4]["NormalizedMovieName"]), str(candidate[3]["Path"]), str(candidate[4]["Path"])))  # Sort by best score with deterministic ties
    movie_groups: list[dict[str, dict[str, object]]] = []  # Initialize matched movie groups
    movie_group_by_key: dict[str, dict[str, dict[str, object]]] = {}  # Map physical movies to assigned groups

    for candidate in candidates:  # Iterate sorted candidates
        left_source_name = candidate[1]  # Read left source name
        right_source_name = candidate[2]  # Read right source name
        left_movie = candidate[3]  # Read left movie record
        right_movie = candidate[4]  # Read right movie record
        left_key = movie_record_key(left_movie)  # Build left movie key
        right_key = movie_record_key(right_movie)  # Build right movie key
        left_group = movie_group_by_key.get(left_key)  # Read existing left movie group
        right_group = movie_group_by_key.get(right_key)  # Read existing right movie group

        if left_group is None and right_group is None:  # Verify both movies are unassigned
            movie_group = {left_source_name: left_movie, right_source_name: right_movie}  # Create new matched group
            movie_groups.append(movie_group)  # Store new matched group
            movie_group_by_key[left_key] = movie_group  # Assign left movie to group
            movie_group_by_key[right_key] = movie_group  # Assign right movie to group
            continue  # Continue candidate processing

        if left_group is not None and right_group is None:  # Verify only left movie is assigned
            if right_source_name not in left_group:  # Verify right source is absent from group
                left_group[right_source_name] = right_movie  # Add right movie to existing group
                movie_group_by_key[right_key] = left_group  # Assign right movie to group
            continue  # Continue candidate processing

        if left_group is None and right_group is not None:  # Verify only right movie is assigned
            if left_source_name not in right_group:  # Verify left source is absent from group
                right_group[left_source_name] = left_movie  # Add left movie to existing group
                movie_group_by_key[left_key] = right_group  # Assign left movie to group
            continue  # Continue candidate processing

        if left_group is right_group:  # Verify both movies already share one group
            continue  # Continue candidate processing

        if left_group is None or right_group is None:  # Verify both groups exist before merging
            continue  # Continue candidate processing

        if any(source_name in left_group for source_name in right_group):  # Verify groups have no source collision
            continue  # Continue candidate processing

        for source_name, grouped_movie in right_group.items():  # Iterate merged source movies
            left_group[source_name] = grouped_movie  # Add merged source movie
            movie_group_by_key[movie_record_key(grouped_movie)] = left_group  # Reassign merged movie to final group
        movie_groups.remove(right_group)  # Remove merged group shell

    matched_groups = [movie_group for movie_group in movie_groups if len(movie_group) >= 2]  # Keep groups with at least two sources
    matched_groups.sort(key=movie_group_sort_key)  # Sort groups deterministically
    return matched_groups  # Return selected movie groups


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


def merge_source_values(source_names: list[str], source_values: dict[str, object]) -> object:
    """
    Preserve source values when matched source records differ.

    :param source_names: Source names to include.
    :param source_values: Values by source name.
    :return: Single shared value or a source-specific value mapping.
    """

    values = [source_values[source_name] for source_name in source_names]  # Read values in source order
    if all(value == values[0] for value in values):  # Verify all values are identical
        return values[0]  # Return single shared value
    return {source_name: source_values[source_name] for source_name in source_names}  # Return source-specific values


def build_third_movie_record(source_name: str, movie: dict[str, object], duration: int | None) -> dict[str, object]:
    """
    Build a supplemental third movie record.

    :param source_name: Source name for the supplemental movie.
    :param movie: Parsed movie metadata for the supplemental movie.
    :param duration: Whole-second duration for the supplemental movie.
    :return: Structured supplemental movie record.
    """

    third_movie: dict[str, object] = {  # Build supplemental third movie record
        "Source": source_name,  # Store source name
        "Path": movie["Path"],  # Store actual movie file path
        "Resolution": movie["Resolution"],  # Store parsed resolution
        "Length": format_duration(duration),  # Store formatted duration
    }  # Finish supplemental third movie record
    return third_movie  # Return supplemental third movie record


def build_report_record(movie_group: dict[str, dict[str, object]], source_durations: dict[str, int | None], primary_sources: list[str], third_source: str | None) -> dict[str, object]:
    """
    Build a report record for a matched movie group.

    :param movie_group: Matched source movie group.
    :param source_durations: Whole-second durations by source name.
    :param primary_sources: Source names represented in top-level fields.
    :param third_source: Optional unmatched third source name.
    :return: Structured JSON report record.
    """

    movie_names: dict[str, object] = {source_name: movie_group[source_name]["MovieName"] for source_name in primary_sources}  # Build movie names by source
    resolutions: dict[str, object] = {source_name: movie_group[source_name]["Resolution"] for source_name in primary_sources}  # Build resolutions by source
    lengths: dict[str, object] = {source_name: format_duration(source_durations[source_name]) for source_name in primary_sources}  # Build lengths by source
    report_record: dict[str, object] = {  # Build report record with required top-level fields
        "MovieName": merge_source_values(primary_sources, movie_names),  # Preserve title values
        "Year": movie_group[primary_sources[0]]["Year"],  # Store exact matched release year
        "Resolution": merge_source_values(primary_sources, resolutions),  # Preserve resolution values
        "Length": merge_source_values(primary_sources, lengths),  # Preserve duration values
    }  # Finish initial report record

    for source_name in primary_sources:  # Iterate primary sources for path fields
        report_record[f"{source_name}Path"] = movie_group[source_name]["Path"]  # Store actual source file path

    if third_source is not None:  # Verify supplemental third source exists
        report_record["ThirdMovie"] = build_third_movie_record(third_source, movie_group[third_source], source_durations[third_source])  # Store supplemental third movie

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


def select_primary_sources(source_durations: dict[str, int | None]) -> list[str]:
    """
    Select same-length primary sources for a matched movie group.

    :param source_durations: Whole-second durations by source name.
    :return: Primary source names with matching durations, or an empty list.
    """

    duration_sources: dict[int, list[str]] = {}  # Initialize source names by duration
    for source_name in SOURCE_NAMES:  # Iterate source names in deterministic order
        if source_name not in source_durations:  # Verify source exists in duration mapping
            continue  # Skip absent source

        duration = source_durations[source_name]  # Read source duration
        if duration is None:  # Verify duration is available
            continue  # Skip unavailable duration

        duration_sources.setdefault(duration, []).append(source_name)  # Group source by duration

    matching_source_groups = [source_names for source_names in duration_sources.values() if len(source_names) >= 2]  # Keep duration groups with at least two sources
    if not matching_source_groups:  # Verify same-length source groups exist
        return []  # Return empty primary source list

    matching_source_groups.sort(key=lambda source_names: (-len(source_names), [SOURCE_NAMES.index(source_name) for source_name in source_names]))  # Sort largest group first with deterministic ties
    return matching_source_groups[0]  # Return selected primary sources


def generate_movie_overlap_reports() -> None:
    """
    Generate source overlap reports grouped by movie duration.

    :return: None.
    """

    source_movies: dict[str, list[dict[str, object]]] = {}  # Initialize discovered movies by source
    for source_name, directory_path in SOURCE_DIRECTORIES.items():  # Iterate configured source directories
        print(f"{BackgroundColors.GREEN}Scanning {source_name} movies in: {BackgroundColors.CYAN}{directory_path}{Style.RESET_ALL}")  # Log source scan path
        source_movies[source_name] = discover_movie_files(directory_path)  # Discover source movie files

        for movie in source_movies[source_name]:  # Iterate discovered source movies
            movie["Source"] = source_name  # Store source name on parsed movie

    matched_groups = select_movie_groups(source_movies)  # Match movies by year and fuzzy title across sources
    same_length_movies = []  # Initialize equal-duration report records
    different_length_movies = []  # Initialize different-duration report records

    for movie_group in matched_groups:  # Iterate matched movie groups
        source_durations: dict[str, int | None] = {}  # Initialize durations by source
        for source_name in SOURCE_NAMES:  # Iterate source names in deterministic order
            if source_name not in movie_group:  # Verify source exists in group
                continue  # Skip absent source

            source_durations[source_name] = get_video_duration_seconds(str(movie_group[source_name]["Path"]))  # Read source video duration

        primary_sources = select_primary_sources(source_durations)  # Select same-length primary sources
        if primary_sources:  # Verify at least two durations match
            third_sources = [source_name for source_name in SOURCE_NAMES if source_name in movie_group and source_name not in primary_sources]  # Identify unmatched supplemental sources
            third_source = third_sources[0] if third_sources else None  # Select supplemental third source when present
            report_record = build_report_record(movie_group, source_durations, primary_sources, third_source)  # Build equal-duration report record
            same_length_movies.append(report_record)  # Store equal-duration record
        else:  # Handle groups without matching durations
            primary_sources = [source_name for source_name in SOURCE_NAMES if source_name in movie_group]  # Select all available sources
            report_record = build_report_record(movie_group, source_durations, primary_sources, None)  # Build different-duration report record
            different_length_movies.append(report_record)  # Store different-duration record

    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)  # Create Reports directory when missing
    write_json_report(REPORTS_DIRECTORY / "movies_same_length.json", same_length_movies)  # Write equal-duration report
    write_json_report(REPORTS_DIRECTORY / "movies_different_length.json", different_length_movies)  # Write different-duration report

    print(f"{BackgroundColors.GREEN}Matched movie groups: {BackgroundColors.CYAN}{len(matched_groups)}{Style.RESET_ALL}")  # Log total matched groups
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
    
    generate_movie_overlap_reports()  # Generate Dublado, Legendado, and Dual movie overlap reports

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
