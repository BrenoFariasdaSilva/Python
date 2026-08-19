"""
================================================================================
Find Repeated Movies-Series
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-19
Description :
    Recursively scans multiple movie-library roots and identifies repeated movie
    titles from directory names that follow the configured movie-directory naming
    pattern. Duplicate detection is based only on the movie title, ignoring release
    year, resolution, language, letter casing, accents, punctuation, and spacing.

    Key features include:
        - INPUT_DIRS list support for scanning two or more independent libraries.
        - Recursive scanning through directories and subdirectories at any depth.
        - Anchored parsing of movie name, year, resolution, and language.
        - Separate internal duplicate report for every configured input directory.
        - Separate cross-input reports grouped by the exact input-directory set in
          which each repeated movie title occurs.
        - Accent/case/punctuation-insensitive movie-title comparison.
        - UTF-8 JSON report generation under ./Outputs/.

Usage:
    1. Configure INPUT_DIRS with one or more movie-library root directories.
    2. Run the script:
        $ python main.py
    3. Review the generated internal and cross-input JSON reports in ./Outputs/.

Outputs:
    - ./Outputs/<input-directory-prefix>-internal-report.json
    - ./Outputs/<input-prefix-1>--<input-prefix-2>[--...]-cross-report.json
    - ./Logs/<script-name>.log

Dependencies:
    - Python >= 3.9
    - colorama
    - Project Logger module (Logger.py)

Assumptions & Notes:
    - Movie directories must end with: <MovieName> <YYYY> <Resolution> <Language>.
    - Supported languages are Dual, Legendado, Dublado, Nacional, and English.
    - Typical resolutions such as 720p, 1080p, 2160p, and 4320p are supported.
    - Internal reports contain duplicates occurring two or more times inside one
      configured input directory.
    - Cross reports contain titles present in two or more distinct input directories
      and are separated by the exact combination of input directories involved.
    - Windows drive colons are removed from report filenames because ':' is invalid.
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
INPUT_DIRS = [f"E:/Movies/"]  # Root directories recursively scanned for movie directories
OUTPUT_DIR = "./Outputs/"  # Directory where the JSON reports are written
SUPPORTED_LANGUAGES = ("Dual", "Legendado", "Dublado", "Nacional", "English")  # Supported terminal language labels in movie-directory names
MOVIE_DIRECTORY_PATTERN = re.compile(  # Compile the anchored movie-directory parsing expression once
    rf"^(?P<movie_name>.+?)\s+(?P<year>\d{{4}})\s+(?P<resolution>\d{{3,4}}p)\s+(?P<language>{'|'.join(SUPPORTED_LANGUAGES)})$",  # Capture title, year, resolution, and language from the directory-name suffix
    re.IGNORECASE,  # Match configured language labels and resolution suffixes case-insensitively
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
        else:  # Handle the alternative branch
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
        verbose_output(  # Output verbose diagnostic information when enabled
            f"{BackgroundColors.GREEN}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}"  # Continue the formatted output message
        )  # Output the verbose message
        
        if not isinstance(filepath, str) or not filepath.strip():  # Verify for non-string or empty/whitespace-only input   
            verbose_output(true_string=f"{BackgroundColors.YELLOW}Invalid filepath provided, skipping existence verification.{Style.RESET_ALL}")  # Log invalid input
            return False  # Return False for invalid input

        if os.path.exists(filepath):  # Fast path: original input exists
            return True  # Return True immediately

        candidate = str(filepath).strip()  # Normalize input to string and strip surrounding whitespace

        if (candidate.startswith("'") and candidate.endswith("'")) or (  # Detect paths wrapped in matching quotes
            candidate.startswith('"') and candidate.endswith('"')  # Execute this step as part of the function flow
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
            try:  # Attempt the protected operation
                normalized_variant = os.path.normpath(path_variant)  # Normalize variant
                if os.path.exists(normalized_variant):  # Verify existence
                    return True  # Return True if found
            except Exception:  # Handle unexpected operation failures
                continue  # Continue safely on error

        try:  # Attempt absolute path resolution as fallback
            abs_candidate = os.path.abspath(candidate)  # Build absolute path
            if os.path.exists(abs_candidate):  # Verify existence
                return True  # Return True if found
        except Exception:  # Handle unexpected operation failures
            pass  # Ignore resolution errors

        for path_variant in (candidate, repo_candidate, cwd_candidate):  # Attempt trailing-space resolution on all variants
            try:  # Attempt to resolve trailing space issues across path components for this variant
                resolved = resolve_full_trailing_space_path(path_variant)  # Resolve trailing space issues across path components
                if resolved != path_variant and os.path.exists(resolved):  # Verify resolved path exists
                    verbose_output(  # Output verbose diagnostic information when enabled
                        f"{BackgroundColors.YELLOW}Resolved trailing space mismatch: {BackgroundColors.CYAN}{path_variant}{BackgroundColors.YELLOW} -> {BackgroundColors.CYAN}{resolved}{Style.RESET_ALL}"  # Continue the formatted output message
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

    normalized = unicodedata.normalize("NFKD", movie_name)  # Split accented characters into base characters and combining marks
    normalized = "".join(  # Rebuild the title without Unicode combining marks
        character for character in normalized if not unicodedata.combining(character)  # Keep only base characters while removing accent marks
    )  # Finish rebuilding the accent-free title
    normalized = normalized.casefold()  # Normalize casing more thoroughly than lower()
    normalized = re.sub(r"[^\w]+", " ", normalized, flags=re.UNICODE)  # Treat punctuation and symbols as word separators
    normalized = re.sub(r"_+", " ", normalized)  # Treat underscores as separators too
    normalized = re.sub(r"\s+", " ", normalized).strip()  # Collapse repeated whitespace and trim the result
    return normalized  # Return the normalized movie-title comparison key


def parse_movie_directory_name(directory_name: str):
    """
    Parse a movie directory name that follows the expected naming convention.

    Parsing is anchored at the end of the directory name so numbers inside movie
    titles, such as "Toy Story 1" or "Resident Evil 3", remain part of the title.

    :param directory_name: Directory basename to parse.
    :return: Parsed metadata dictionary, or None when the directory does not match.
    """

    if not isinstance(directory_name, str):  # Reject non-string directory names
        return None  # Return no metadata for an invalid directory-name value

    match = MOVIE_DIRECTORY_PATTERN.fullmatch(directory_name.strip())  # Match the complete trimmed directory name against the expected pattern
    if match is None:  # Reject directory names outside the expected naming convention
        return None  # Return no metadata for an unmatched directory name

    movie_name = match.group("movie_name").strip()  # Extract and trim the movie-title portion
    if not movie_name:  # Reject matches whose movie-title portion is empty
        return None  # Return no metadata for an empty movie title

    language_lookup = {language.casefold(): language for language in SUPPORTED_LANGUAGES}  # Build a case-insensitive lookup for canonical language labels
    language = language_lookup[match.group("language").casefold()]  # Restore the configured canonical language spelling

    return {  # Build the parsed movie metadata record
        "movie_name": movie_name,  # Store the original movie title
        "normalized_movie_name": normalize_movie_name(movie_name),  # Store the normalized comparison title
        "year": int(match.group("year")),  # Store the parsed release year as an integer
        "resolution": match.group("resolution").lower(),  # Store the parsed video resolution using a normalized suffix
        "language": language,  # Store the canonical language label
    }  # Return-compatible metadata dictionary


def canonicalize_input_dir(input_dir: str) -> str:
    """
    Build a canonical path key used to detect repeated INPUT_DIRS entries.

    :param input_dir: Configured input directory path.
    :return: Canonical normalized absolute path key.
    """

    normalized_path = os.path.normpath(os.path.expanduser(input_dir.strip()))  # Normalize separators, relative segments, home expansion, and surrounding whitespace
    absolute_path = os.path.abspath(normalized_path)  # Resolve the normalized path against the current working directory
    return os.path.normcase(absolute_path)  # Normalize path casing according to the current operating system


def validate_input_dirs(input_dirs):
    """
    Validate and normalize the configured INPUT_DIRS collection.

    :param input_dirs: List or tuple containing one or more input directory paths.
    :return: Cleaned list of distinct validated input directory strings.
    """

    if not isinstance(input_dirs, (list, tuple)):  # Require an ordered collection so report scopes remain deterministic
        raise TypeError("INPUT_DIRS must be a list or tuple of directory paths.")  # Reject scalar strings or unsupported collection types
    if not input_dirs:  # Require at least one directory to perform a scan
        raise ValueError("INPUT_DIRS must contain at least one directory path.")  # Reject an empty input-directory collection

    validated_input_dirs = []  # Initialize the ordered collection of validated directory strings
    canonical_input_dirs = set()  # Track canonical paths to prevent the same directory from appearing twice

    for input_dir in input_dirs:  # Validate every configured input directory independently
        if not isinstance(input_dir, str) or not input_dir.strip():  # Reject non-string, empty, or whitespace-only directory values
            raise ValueError("Every INPUT_DIRS entry must be a non-empty string path.")  # Raise a clear configuration error for an invalid entry

        cleaned_input_dir = input_dir.strip()  # Remove accidental surrounding whitespace from the configured directory path
        canonical_input_dir = canonicalize_input_dir(cleaned_input_dir)  # Build the canonical identity used for duplicate-path detection
        if canonical_input_dir in canonical_input_dirs:  # Prevent the same physical/configured directory from being treated as two input sources
            raise ValueError(f"Duplicate input directory configured in INPUT_DIRS: {cleaned_input_dir}")  # Reject duplicate directory definitions before scanning
        if not verify_filepath_exists(cleaned_input_dir):  # Verify that the configured input directory exists before any reports are generated
            raise FileNotFoundError(f"Input directory not found: {cleaned_input_dir}")  # Raise a descriptive error for a missing input directory
        if not os.path.isdir(cleaned_input_dir):  # Verify that the existing configured path is actually a directory
            raise NotADirectoryError(f"Input path is not a directory: {cleaned_input_dir}")  # Reject files or other non-directory paths

        canonical_input_dirs.add(canonical_input_dir)  # Mark the canonical directory identity as already configured
        validated_input_dirs.append(cleaned_input_dir)  # Preserve the cleaned user-configured path and original ordering

    return validated_input_dirs  # Return the complete validated input-directory collection


def scan_movie_directories(input_dir: str):
    """
    Recursively scan one input directory and collect valid movie entries.

    :param input_dir: Root directory to scan.
    :return: Tuple containing parsed movie entries and total directory count.
    """

    movie_entries = []  # Initialize the collection of parsed movie directories found in this input directory
    total_directories_scanned = 0  # Initialize the recursive descendant-directory counter

    def handle_walk_error(error):  # Define a local handler for recoverable os.walk errors
        print(  # Output the scan warning to the terminal and logger
            f"{BackgroundColors.YELLOW}Warning: unable to scan "  # Begin the formatted scan-warning message
            f"{BackgroundColors.CYAN}{getattr(error, 'filename', 'unknown path')}"  # Include the inaccessible path when available
            f"{BackgroundColors.YELLOW}: {error}{Style.RESET_ALL}"  # Include the original os.walk error description
        )  # Finish the warning output call

    for current_root, directory_names, _ in os.walk(input_dir, onerror=handle_walk_error):  # Recursively walk every directory below the current input root
        directory_names.sort(key=str.casefold)  # Sort discovered child directories for deterministic traversal and report generation
        for directory_name in directory_names:  # Inspect every immediate child directory discovered by os.walk
            total_directories_scanned += 1  # Count the current descendant directory
            metadata = parse_movie_directory_name(directory_name)  # Parse movie metadata from the current directory name
            if metadata is None:  # Skip directories that do not match the expected movie naming pattern
                continue  # Continue with the next discovered directory

            full_path = os.path.normpath(os.path.join(current_root, directory_name))  # Build the normalized path for the matched movie directory
            relative_path = os.path.relpath(full_path, input_dir)  # Build the matched directory path relative to its owning input directory
            movie_entries.append(  # Append the complete movie occurrence to this input directory's scan result
                {  # Build the movie occurrence record
                    **metadata,  # Include all metadata parsed from the movie directory name
                    "input_dir": input_dir,  # Record which configured input directory owns this movie occurrence
                    "directory_name": directory_name,  # Store the original matched directory basename
                    "relative_path": relative_path,  # Store the path relative to the owning input directory
                    "path": full_path,  # Store the normalized matched movie-directory path
                }  # Finish the movie occurrence record
            )  # Finish appending the movie occurrence

            verbose_output(  # Output matched-directory diagnostics when verbose logging is enabled
                true_string=(  # Build the verbose matched-directory message
                    f"{BackgroundColors.GREEN}Matched movie directory: "  # Begin the matched-directory message
                    f"{BackgroundColors.CYAN}{full_path}{Style.RESET_ALL}"  # Include the complete matched directory path
                )  # Finish the formatted verbose message
            )  # Finish the optional verbose output call

    return movie_entries, total_directories_scanned  # Return this input directory's movie entries and scanned-directory count


def build_duplicate_group(normalized_name: str, entries):
    """
    Build one deterministic duplicate-group structure from movie occurrences.

    :param normalized_name: Normalized movie-title grouping key.
    :param entries: Movie occurrences belonging to the normalized title.
    :return: JSON-serializable duplicate-group dictionary.
    """

    sorted_entries = sorted(  # Sort movie occurrences deterministically across input directories and metadata
        entries,  # Provide the movie occurrences that belong to the duplicate group
        key=lambda entry: (  # Define the deterministic occurrence ordering key
            entry["input_dir"].casefold(),  # Sort first by owning input directory
            entry["year"],  # Sort next by release year
            entry["resolution"],  # Sort next by resolution
            entry["language"].casefold(),  # Sort next by canonical language label
            entry["path"].casefold(),  # Sort finally by full movie-directory path
        ),  # Finish the occurrence ordering tuple
    )  # Finish sorting the duplicate occurrences
    movie_name_variants = sorted(  # Collect every original title spelling represented by this normalized group
        {entry["movie_name"] for entry in sorted_entries},  # Build the unique set of original movie-title variants
        key=str.casefold,  # Sort title variants case-insensitively for deterministic report output
    )  # Finish sorting the original title variants
    input_dirs = sorted(  # Collect every distinct configured input directory represented in this duplicate group
        {entry["input_dir"] for entry in sorted_entries},  # Build the distinct input-directory set for this title
        key=str.casefold,  # Sort input-directory labels deterministically
    )  # Finish sorting the represented input directories

    return {  # Build the complete duplicate group shared by internal and cross-input reports
        "movie_name": sorted_entries[0]["movie_name"],  # Use the first deterministic occurrence as the display movie title
        "normalized_movie_name": normalized_name,  # Store the normalized comparison title
        "movie_name_variants": movie_name_variants,  # Store all original title variants found in the group
        "occurrences": len(sorted_entries),  # Store the total number of matching movie-directory occurrences
        "input_dir_count": len(input_dirs),  # Store the number of distinct configured input directories represented
        "input_dirs": input_dirs,  # Store the distinct configured input directories represented by the title
        "entries": [  # Build the serialized occurrence list for the duplicate group
            {  # Build one serialized movie occurrence
                "input_dir": entry["input_dir"],  # Record the configured input directory containing this occurrence
                "directory_name": entry["directory_name"],  # Store the original matched directory basename
                "year": entry["year"],  # Store the parsed release year
                "resolution": entry["resolution"],  # Store the parsed video resolution
                "language": entry["language"],  # Store the canonical language label
                "relative_path": entry["relative_path"],  # Store the path relative to the owning input directory
                "path": entry["path"],  # Store the normalized matched movie-directory path
            }  # Finish the serialized movie occurrence
            for entry in sorted_entries  # Serialize every sorted occurrence in the duplicate group
        ],  # Finish the serialized occurrence list
    }  # Return the complete duplicate-group dictionary


def find_duplicate_movies(movie_entries):
    """
    Group movie entries whose normalized titles repeat within the supplied entries.

    :param movie_entries: Parsed movie directory entries from one input directory.
    :return: Sorted list containing only movie-title groups with 2+ occurrences.
    """

    grouped_entries = {}  # Initialize movie-title groups keyed by normalized names
    for entry in movie_entries:  # Group every parsed movie occurrence by its normalized title
        normalized_name = entry["normalized_movie_name"]  # Read the normalized movie-title grouping key
        grouped_entries.setdefault(normalized_name, []).append(entry)  # Append the current occurrence to its normalized-title group

    duplicate_groups = []  # Initialize the collection of movie titles repeated within the supplied entries
    for normalized_name, entries in grouped_entries.items():  # Inspect every normalized title group for multiple occurrences
        if len(entries) < 2:  # Ignore titles that occur only once in this input directory
            continue  # Continue with the next normalized movie title
        duplicate_groups.append(build_duplicate_group(normalized_name, entries))  # Build and append the complete internal duplicate group

    duplicate_groups.sort(key=lambda group: group["normalized_movie_name"])  # Sort duplicate groups alphabetically by normalized movie title
    return duplicate_groups  # Return the deterministic internal duplicate-group collection


def find_cross_input_duplicate_groups(movie_entries, input_dirs):
    """
    Find duplicate titles present in two or more distinct configured input dirs.

    Cross duplicates are separated by the exact set of input directories in which
    each title occurs, producing one report scope per distinct input-dir combination.

    :param movie_entries: Combined movie entries from every configured input directory.
    :param input_dirs: Validated configured input directories in original order.
    :return: Dictionary mapping input-dir scope tuples to duplicate-group lists.
    """

    grouped_entries = {}  # Initialize combined normalized-title groups across all configured input directories
    for entry in movie_entries:  # Group every combined movie occurrence by its normalized title
        normalized_name = entry["normalized_movie_name"]  # Read the normalized movie-title grouping key
        grouped_entries.setdefault(normalized_name, []).append(entry)  # Append the occurrence to its combined normalized-title group

    cross_groups_by_scope = {}  # Initialize cross-input duplicate groups keyed by their exact configured input-directory scope
    for normalized_name, entries in grouped_entries.items():  # Inspect every combined normalized title for cross-input presence
        present_input_dirs = {entry["input_dir"] for entry in entries}  # Collect the distinct configured input directories containing this title
        if len(present_input_dirs) < 2:  # Ignore titles that occur in only one configured input directory
            continue  # Continue with the next combined normalized title

        scope = tuple(input_dir for input_dir in input_dirs if input_dir in present_input_dirs)  # Preserve INPUT_DIRS ordering while building the exact cross-report scope
        cross_groups_by_scope.setdefault(scope, []).append(build_duplicate_group(normalized_name, entries))  # Append the title to the report matching its exact input-directory combination

    for duplicate_groups in cross_groups_by_scope.values():  # Normalize ordering inside every generated cross-input report scope
        duplicate_groups.sort(key=lambda group: group["normalized_movie_name"])  # Sort cross duplicate groups alphabetically by normalized movie title

    cross_groups_by_scope = dict(sorted(cross_groups_by_scope.items(), key=lambda item: tuple(input_dir.casefold() for input_dir in item[0])))  # Sort exact cross-report scopes deterministically by configured input-directory paths
    return cross_groups_by_scope  # Return all cross-input report scopes and their duplicate groups


def build_report_prefix(input_dir: str) -> str:
    """
    Convert one input directory path into a Windows-safe report filename prefix.

    :param input_dir: Input directory represented by the report filename.
    :return: Sanitized report filename prefix.
    """

    prefix = str(input_dir).strip().replace("\\", "-").replace("/", "-")  # Replace path separators with hyphens as required by the report naming convention
    prefix = prefix.replace(":", "")  # Remove Windows drive colons because colons are invalid inside Windows filenames
    prefix = re.sub(r'[<>"|?*]', "-", prefix)  # Replace any remaining Windows-invalid filename characters with hyphens
    prefix = re.sub(r"-+", "-", prefix).strip("- .")  # Collapse repeated hyphens and remove invalid trailing filename characters
    if not prefix:  # Provide a fallback when sanitization removes every usable prefix character
        prefix = "movies"  # Use a stable safe fallback report prefix
    return prefix  # Return the sanitized input-directory report prefix


def build_internal_report_filename(input_dir: str) -> str:
    """
    Build the internal duplicate-report filename for one input directory.

    :param input_dir: Input directory represented by the report.
    :return: Windows-safe internal JSON report filename.
    """

    return f"{build_report_prefix(input_dir)}-internal-report.json"  # Return the per-input internal duplicate-report filename


def build_cross_report_filename(input_dirs) -> str:
    """
    Build a cross-input report filename from the exact participating directories.

    :param input_dirs: Two or more input directories represented by the cross report.
    :return: Windows-safe cross-input JSON report filename.
    """

    prefixes = [build_report_prefix(input_dir) for input_dir in input_dirs]  # Convert every participating input directory into a safe filename component
    combined_prefix = "--".join(prefixes)  # Join participating directory prefixes while preserving their configured ordering
    return f"{combined_prefix}-cross-report.json"  # Return the exact-scope cross-input duplicate-report filename


def build_comparison_metadata():
    """
    Build the common duplicate-comparison metadata stored in every JSON report.

    :param: None
    :return: JSON-serializable comparison metadata dictionary.
    """

    return {  # Build the shared duplicate-comparison rule description
        "based_on": "movie_name_only",  # Document that duplicate comparison uses only the movie title
        "ignores": [  # List metadata and formatting differences ignored during matching
            "year",  # Document that release-year differences do not affect title matching
            "resolution",  # Document that resolution differences do not affect title matching
            "language",  # Document that language-label differences do not affect title matching
            "letter_casing",  # Document that uppercase and lowercase differences do not affect title matching
            "accents",  # Document that accented and unaccented character variants are treated equally
            "punctuation",  # Document that punctuation differences do not affect title matching
            "extra_whitespace",  # Document that repeated or surrounding whitespace does not affect title matching
        ],  # Finish the ignored-comparison attribute list
    }  # Return the common comparison metadata dictionary


def write_internal_duplicate_report(input_dir: str, movie_entries, total_directories_scanned: int, duplicate_groups):
    """
    Write one duplicate report containing repeats inside a single input directory.

    :param input_dir: Root directory represented by the internal report.
    :param movie_entries: All matching movie directory entries from this input dir.
    :param total_directories_scanned: Number of descendant directories inspected.
    :param duplicate_groups: Duplicate title groups found inside this input dir.
    :return: Path to the written internal JSON report.
    """

    output_dir = Path(OUTPUT_DIR)  # Resolve the configured output directory as a Path object
    output_dir.mkdir(parents=True, exist_ok=True)  # Create the output directory tree when it does not already exist
    report_path = output_dir / build_internal_report_filename(input_dir)  # Build the final per-input internal report path
    unique_movie_names = {entry["normalized_movie_name"] for entry in movie_entries}  # Collect unique normalized titles for this input directory's statistics
    duplicate_movie_directories = sum(group["occurrences"] for group in duplicate_groups)  # Count every directory belonging to an internal duplicate group

    report = {  # Build the complete internal-report JSON structure
        "report_type": "within_input_dir",  # Identify this report as duplicates occurring inside one configured input directory
        "input_dir": input_dir,  # Record the configured input directory represented by this report
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),  # Record when this internal report was generated
        "expected_directory_format": "<MovieName> <YYYY> <Resolution> <Dual|Legendado|Dublado|Nacional|English>",  # Document the naming convention parsed by the scanner
        "comparison": build_comparison_metadata(),  # Store the shared movie-title duplicate-comparison rules
        "summary": {  # Store aggregate statistics for this configured input directory
            "directories_scanned": total_directories_scanned,  # Store the total descendant-directory count inspected under this input root
            "matching_movie_directories": len(movie_entries),  # Store the count of directories matching the movie naming convention
            "non_matching_directories": total_directories_scanned - len(movie_entries),  # Store the count of inspected directories that did not match the movie pattern
            "unique_movie_names": len(unique_movie_names),  # Store the number of unique normalized movie titles found in this input directory
            "duplicate_movie_names": len(duplicate_groups),  # Store the number of movie titles repeated inside this input directory
            "directories_in_duplicate_groups": duplicate_movie_directories,  # Store the number of movie directories belonging to internal duplicate groups
        },  # Finish the internal-report summary section
        "duplicates": duplicate_groups,  # Store every movie title duplicated inside this configured input directory
    }  # Finish the complete internal-report structure

    with report_path.open("w", encoding="utf-8") as report_file:  # Open the internal report destination using UTF-8 encoding
        json.dump(report, report_file, ensure_ascii=False, indent=4)  # Serialize the internal duplicate report as readable UTF-8 JSON
        report_file.write("\n")  # Terminate the generated JSON document with a newline

    return report_path  # Return the generated internal JSON report path


def write_cross_duplicate_reports(cross_groups_by_scope):
    """
    Write one cross report for each exact input-directory combination with duplicates.

    :param cross_groups_by_scope: Mapping of input-dir scope tuples to duplicate groups.
    :return: List containing every written cross-input JSON report path.
    """

    output_dir = Path(OUTPUT_DIR)  # Resolve the configured output directory as a Path object
    output_dir.mkdir(parents=True, exist_ok=True)  # Create the output directory tree when it does not already exist
    report_paths = []  # Initialize the collection of generated cross-input report paths

    for input_dir_scope, duplicate_groups in cross_groups_by_scope.items():  # Generate one report for each exact set of input directories sharing duplicate titles
        report_path = output_dir / build_cross_report_filename(input_dir_scope)  # Build the JSON filename describing this exact cross-input scope
        duplicate_movie_directories = sum(group["occurrences"] for group in duplicate_groups)  # Count every movie-directory occurrence represented by this cross report
        report = {  # Build the complete cross-input report JSON structure
            "report_type": "cross_input_dirs",  # Identify this report as duplicates occurring across distinct configured input directories
            "input_dirs": list(input_dir_scope),  # Record the exact configured input-directory combination represented by this report
            "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),  # Record when this cross-input report was generated
            "expected_directory_format": "<MovieName> <YYYY> <Resolution> <Dual|Legendado|Dublado|Nacional|English>",  # Document the naming convention parsed by the scanner
            "comparison": build_comparison_metadata(),  # Store the shared movie-title duplicate-comparison rules
            "summary": {  # Store aggregate statistics for this exact cross-input report scope
                "input_dir_count": len(input_dir_scope),  # Store how many configured input directories participate in this cross report
                "duplicate_movie_names": len(duplicate_groups),  # Store the number of movie titles present across this exact input-directory combination
                "directories_in_duplicate_groups": duplicate_movie_directories,  # Store the number of movie-directory occurrences represented by the cross duplicates
            },  # Finish the cross-input report summary section
            "duplicates": duplicate_groups,  # Store every title repeated across this exact configured input-directory combination
        }  # Finish the complete cross-input report structure

        with report_path.open("w", encoding="utf-8") as report_file:  # Open this cross-input report destination using UTF-8 encoding
            json.dump(report, report_file, ensure_ascii=False, indent=4)  # Serialize the cross-input duplicate report as readable UTF-8 JSON
            report_file.write("\n")  # Terminate the generated JSON document with a newline

        report_paths.append(report_path)  # Record the generated cross-input report path for caller output

    return report_paths  # Return every generated cross-input JSON report path


def run_duplicate_movie_scans(input_dirs=INPUT_DIRS):
    """
    Validate all inputs, create internal reports, and create cross-input reports.

    :param input_dirs: Ordered list or tuple of movie-library root directories.
    :return: Tuple with internal report data, cross report paths, and cross groups.
    """

    validated_input_dirs = validate_input_dirs(input_dirs)  # Validate the complete configuration before scanning or writing any report
    scan_results = []  # Initialize the per-input scan and internal-report result collection
    all_movie_entries = []  # Initialize the combined movie-entry collection used for cross-input duplicate detection

    for input_dir in validated_input_dirs:  # Scan every configured input directory independently in configured order
        movie_entries, total_directories_scanned = scan_movie_directories(input_dir)  # Recursively collect matching movie directories under the current input root
        duplicate_groups = find_duplicate_movies(movie_entries)  # Find duplicates occurring inside only the current configured input directory
        report_path = write_internal_duplicate_report(  # Write the current input directory's independent internal duplicate report
            input_dir,  # Provide the configured input directory represented by this report
            movie_entries,  # Provide every matching movie occurrence found under this input root
            total_directories_scanned,  # Provide the number of descendant directories inspected under this input root
            duplicate_groups,  # Provide duplicates found within the current input directory
        )  # Finish writing the current internal duplicate report
        scan_results.append(  # Store the complete result for terminal output and callers
            {  # Build the per-input scan result record
                "input_dir": input_dir,  # Record the configured input directory represented by this result
                "movie_entries": movie_entries,  # Store every matching movie entry discovered under this input root
                "total_directories_scanned": total_directories_scanned,  # Store the descendant-directory count inspected under this input root
                "duplicate_groups": duplicate_groups,  # Store duplicates occurring internally within this input directory
                "report_path": report_path,  # Store the generated per-input internal report path
            }  # Finish the per-input scan result record
        )  # Finish appending the per-input scan result
        all_movie_entries.extend(movie_entries)  # Add this input directory's movie occurrences to the combined cross-input comparison pool

    cross_groups_by_scope = find_cross_input_duplicate_groups(all_movie_entries, validated_input_dirs)  # Find titles shared by two or more distinct configured input directories
    cross_report_paths = write_cross_duplicate_reports(cross_groups_by_scope)  # Write one cross report for each exact participating input-directory combination
    return scan_results, cross_report_paths, cross_groups_by_scope  # Return complete internal and cross-input scan/report results


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
        except Exception:  # Handle unexpected operation failures
            pass  # Fallthrough on error
    if hasattr(obj, "timestamp"):  # Datetime-like objects
        try:  # Attempt to call timestamp()
            return float(obj.timestamp())  # Use timestamp() to get seconds since epoch
        except Exception:  # Handle unexpected operation failures
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
            except Exception:  # Handle unexpected operation failures
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
            print(  # Output status information to the terminal and logger
                f"{BackgroundColors.RED}The {BackgroundColors.CYAN}{current_os}{BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}"  # Continue the formatted output message
            )  # Close the current data structure or call
    else:  # If the sound file does not exist
        print(  # Output status information to the terminal and logger
            f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}"  # Continue the formatted output message
        )  # Close the current data structure or call


def main():
    """
    Scan INPUT_DIRS, write per-input duplicate reports, and write cross-input reports.

    :param: None
    :return: None
    """

    print(  # Output the program welcome message to the terminal and logger
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Find Repeated Movies-Series{BackgroundColors.GREEN} program!{Style.RESET_ALL}",  # Include the project name using the configured terminal colors
        end="\n\n",  # Add spacing after the welcome message
    )  # Finish the welcome output call

    start_time = datetime.datetime.now()  # Capture the program start time for final execution-duration reporting

    try:  # Execute the complete multi-input scan while preserving existing failure propagation behavior
        scan_results, cross_report_paths, cross_groups_by_scope = run_duplicate_movie_scans(INPUT_DIRS)  # Run all internal and cross-input duplicate analyses

        for scan_result in scan_results:  # Display one independent summary for every configured input directory
            print(  # Output the current input-directory summary heading
                f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Input directory: "  # Begin the formatted input-directory summary line
                f"{BackgroundColors.CYAN}{scan_result['input_dir']}{Style.RESET_ALL}"  # Include the configured input directory path
            )  # Finish the input-directory heading output call
            print(  # Output the number of matching movie directories found under this input root
                f"{BackgroundColors.GREEN}Matching movie directories: "  # Begin the matching-directory count message
                f"{BackgroundColors.CYAN}{len(scan_result['movie_entries'])}{Style.RESET_ALL}"  # Include the matching movie-directory count
            )  # Finish the matching-directory output call
            print(  # Output the number of movie titles duplicated inside this input root
                f"{BackgroundColors.GREEN}Internal repeated movie names: "  # Begin the internal duplicate count message
                f"{BackgroundColors.CYAN}{len(scan_result['duplicate_groups'])}{Style.RESET_ALL}"  # Include the internal duplicate-title count
            )  # Finish the internal duplicate count output call

            if scan_result["duplicate_groups"]:  # Display internal duplicate titles only when this input directory contains repeats
                print(f"{BackgroundColors.YELLOW}Internal repeated movies:{Style.RESET_ALL}")  # Output the internal duplicate-list heading
                for group in scan_result["duplicate_groups"]:  # Display every movie title repeated inside the current input directory
                    print(  # Output one internal duplicate group summary line
                        f"  {BackgroundColors.CYAN}{group['movie_name']}"  # Include the representative movie title
                        f"{BackgroundColors.GREEN} ({group['occurrences']} occurrences){Style.RESET_ALL}"  # Include the total occurrences inside the current input directory
                    )  # Finish the internal duplicate group output call
            else:  # Handle an input directory with no internal duplicate movie titles
                print(f"{BackgroundColors.GREEN}No internal repeated movie names found.{Style.RESET_ALL}")  # Report that this input directory has no internal duplicates

            print(  # Output the generated internal JSON report path
                f"{BackgroundColors.GREEN}Internal JSON report written to: "  # Begin the internal report-path message
                f"{BackgroundColors.CYAN}{scan_result['report_path']}{Style.RESET_ALL}"  # Include the generated internal report path
            )  # Finish the internal report-path output call
            print()  # Separate per-input summaries with one blank line

        total_cross_duplicate_groups = sum(len(groups) for groups in cross_groups_by_scope.values())  # Count all cross-input duplicate titles across exact report scopes
        print(  # Output the total number of cross-input repeated movie titles
            f"{BackgroundColors.GREEN}Cross-input repeated movie names: "  # Begin the cross-input duplicate count message
            f"{BackgroundColors.CYAN}{total_cross_duplicate_groups}{Style.RESET_ALL}"  # Include the total cross-input duplicate-title count
        )  # Finish the cross-input duplicate count output call

        if cross_groups_by_scope:  # Display and list generated cross reports when duplicates span distinct input directories
            for input_dir_scope, duplicate_groups in cross_groups_by_scope.items():  # Display every exact cross-input report scope and its titles
                print(  # Output the current cross-input scope heading
                    f"{BackgroundColors.YELLOW}Cross duplicates in: "  # Begin the cross-input scope message
                    f"{BackgroundColors.CYAN}{' | '.join(input_dir_scope)}{Style.RESET_ALL}"  # Include all configured input directories participating in this exact scope
                )  # Finish the cross-input scope output call
                for group in duplicate_groups:  # Display every duplicate movie title occurring across this exact input-directory combination
                    print(  # Output one cross-input duplicate group summary line
                        f"  {BackgroundColors.CYAN}{group['movie_name']}"  # Include the representative movie title
                        f"{BackgroundColors.GREEN} ({group['occurrences']} occurrences across {group['input_dir_count']} input dirs){Style.RESET_ALL}"  # Include total occurrences and distinct input-directory count
                    )  # Finish the cross-input duplicate group output call

            for report_path in cross_report_paths:  # Display every cross-input JSON report generated by the scan
                print(  # Output one generated cross-input report path
                    f"{BackgroundColors.GREEN}Cross JSON report written to: "  # Begin the cross-report path message
                    f"{BackgroundColors.CYAN}{report_path}{Style.RESET_ALL}"  # Include the generated cross-input report path
                )  # Finish the cross-report path output call
        else:  # Handle the case where no movie title appears in two or more configured input directories
            print(f"{BackgroundColors.GREEN}No cross-input repeated movie names found.{Style.RESET_ALL}")  # Report that no cross-input duplicate title exists
    except Exception as error:  # Handle and report unexpected multi-input scan failures
        print(  # Output the failure message to the terminal and logger
            f"{BackgroundColors.RED}Failed to scan movie libraries: "  # Begin the formatted multi-input failure message
            f"{BackgroundColors.CYAN}{error}{Style.RESET_ALL}"  # Include the original exception description
        )  # Finish the failure output call
        raise  # Re-raise the original exception after logging it
    finally:  # Always finalize timing, completion output, and optional notification sound registration
        finish_time = datetime.datetime.now()  # Capture the program finish time
        print(  # Output start, finish, and elapsed execution times
            f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n"  # Include the formatted program start time
            f"{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n"  # Include the formatted program finish time
            f"{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"  # Include the calculated human-readable execution duration
        )  # Finish the execution-time output call
        print(  # Output the final program completion message
            f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"  # Include the styled completion message
        )  # Finish the completion output call
        if RUN_FUNCTIONS["Play Sound"]:  # Check whether the optional completion sound callback is enabled
            atexit.register(play_sound)  # Register the completion sound callback for process shutdown


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
