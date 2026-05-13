"""
================================================================================
Games Collection Manager
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-05-12
Description :
    Reads all TXT game-collection files from ./INPUTS/, parses each file
    into structured console sections with game entries, auto-normalizes
    formatting inconsistencies, validates all game entries, recalculates
    counters, sorts games alphabetically within each console section, and
    overwrites each file with a deterministically formatted result.

    Key features include:
        - Automatic discovery and processing of all TXT files in ./INPUTS/
        - Strict per-game validation (year presence, YYYY format, line prefix)
        - Auto-normalization of spacing, prefixes, and icon placement
        - Case-insensitive alphabetical sorting of games per console section
        - Recalculation of per-console and global owned/total counters
        - Warning-logged skipping of irreparably invalid game entries
        - Safe in-place file overwrite with deterministic formatted output

Usage:
    1. Place TXT game-collection files inside ./INPUTS/.
    2. Run the script via Makefile or Python directly.
        $ make run   or   $ python main.py
    3. Each TXT file in ./INPUTS/ will be normalized and overwritten in place.

Outputs:
    - ./INPUTS/<filename>.txt  (normalized and overwritten in place)
    - ./Logs/main.log           (execution log with warnings and summaries)

TODOs:
    - Extend to support additional icon types beyond ✅ and ❓.
    - Add CLI argument for dry-run mode (preview without overwriting).
    - Support exporting a combined summary report across all files.

Dependencies:
    - Python >= 3.8
    - colorama

Assumptions & Notes:
    - Each TXT file follows the strict section/game format described above.
    - Game years must be exactly 4 digits; invalid entries are skipped.
    - Icons ✅ and ❓ are the only recognized ownership markers.
    - Sound is disabled on Windows.
"""

import atexit  # For playing a sound when the program finishes
import datetime  # For getting the current date and time
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For regular expression matching during game-line parsing
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

# Path Constants:
INPUTS_DIR = "./Inputs"  # Directory containing TXT game-collection files to process

# Icon Constants:
ICON_OWNED = "✅"  # Icon representing a confirmed owned game
ICON_MAYBE = "❓"  # Icon representing a maybe-owned game
VALID_ICONS = (ICON_OWNED, ICON_MAYBE)  # Tuple of all recognized ownership icons

# Regex Constants:
GAME_LINE_REGEX = re.compile(r"^-\s+(.+?)\s+(\d{4})\.\s*(✅|❓)?$")  # Pattern matching a valid normalized game line
YEAR_EXTRACT_REGEX = re.compile(r"(\d{4})")  # Pattern extracting a 4-digit year from raw text

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


def parse_game_icon(normalized_line: str) -> str:
    """
    Extract the icon from an already-normalized game line.

    :param normalized_line: A normalized game line in canonical format.
    :return: The icon string (ICON_OWNED or ICON_MAYBE) or empty string if absent.
    """

    if normalized_line.endswith(ICON_OWNED):  # Detect owned icon at line end
        return ICON_OWNED  # Return owned icon
    if normalized_line.endswith(ICON_MAYBE):  # Detect maybe icon at line end
        return ICON_MAYBE  # Return maybe icon
    return ""  # Return empty when no icon is present


def parse_console_sections(lines: list, filepath: str) -> list:
    """
    Parse raw TXT file lines into a list of console section dictionaries.

    Each dictionary contains keys:
      - "name": console name string
      - "games": list of normalized game line strings (sorted alphabetically)

    :param lines: List of raw line strings from the TXT file.
    :param filepath: Source file path used for warning messages during parsing.
    :return: List of console section dictionaries with normalized and sorted game entries.
    """

    try:  # Wrap parsing logic for safe execution
        sections = []  # Initialize list of parsed console sections
        current_console = None  # Track currently active console name
        current_games = []  # Accumulate game lines for the current console

        header_titles = [
            "-- Games Collection:",
            "-- Owned:",
            "-- Total:",
            "-- Icons:"
        ]

        for raw_line in lines:  # Iterate all raw lines from the file
            stripped = raw_line.strip()  # Normalize whitespace for pattern matching

            # Skip global header lines
            if any(stripped.startswith(title) for title in header_titles):
                continue  # Skip header block lines

            if stripped.startswith("-- ") and ":" in stripped:  # Detect console section header line
                if current_console is not None:  # Flush previous console section before starting new one
                    sections.append({"name": current_console, "games": current_games})  # Append completed section
                    current_games = []  # Reset game accumulator for the next section

                header_body = stripped[3:].strip()  # Extract body after "-- " prefix
                console_name = header_body.split(":")[0].strip()  # Extract console name before the colon
                current_console = console_name  # Set active console to parsed name

            elif stripped.startswith("- ") or (stripped.startswith("-") and not stripped.startswith("--")):  # Detect game entry line
                if current_console is None:  # Skip orphaned game lines without a parent console section
                    print(f"{BackgroundColors.YELLOW}Warning: Game line found before any console section — skipping. File: {BackgroundColors.CYAN}{filepath}{BackgroundColors.YELLOW}, Line: {BackgroundColors.CYAN}{stripped}{Style.RESET_ALL}")  # Log warning
                    continue  # Skip orphaned line

                normalized = normalize_game_line(stripped, filepath, current_console)  # Normalize and validate game line

                if normalized:  # Append only valid normalized game lines
                    current_games.append(normalized)  # Accumulate valid game line

        if current_console is not None:  # Flush final console section after loop ends
            sections.append({"name": current_console, "games": current_games})  # Append last section

        for section in sections:  # Sort games alphabetically within each console section
            section["games"] = sorted(section["games"], key=lambda line: line[2:].lower())  # Sort by game name case-insensitively

        return sections  # Return fully parsed and sorted sections

    except Exception as e:  # Catch unexpected parsing errors
        print(f"{BackgroundColors.RED}Error parsing console sections in {BackgroundColors.CYAN}{filepath}{BackgroundColors.RED}: {e}{Style.RESET_ALL}")  # Log error
        return []  # Return empty list on failure


def compute_console_counters(games: list) -> tuple:
    """
    Compute owned and total counters for a list of normalized game lines.

    Owned count includes both ICON_OWNED (✅) and ICON_MAYBE (❓) entries.
    Total count equals the number of valid game lines.

    :param games: List of normalized game line strings for a single console section.
    :return: Tuple of (owned_count, total_count) integers.
    """

    total = len(games)  # Total is the count of all valid game entries
    owned = sum(1 for line in games if parse_game_icon(line) in VALID_ICONS)  # Count lines carrying any valid ownership icon

    return owned, total  # Return computed counters as a tuple


def format_txt_output(sections: list) -> str:
    """
    Format a list of parsed console sections into the canonical TXT output string.

    Produces the exact header block and per-console section layout as required.

    :param sections: List of console section dictionaries with "name" and "games" keys.
    :return: Fully formatted TXT string ready for file writing.
    """

    try:  # Wrap formatting to ensure safe execution
        # Sort sections alphabetically by console name (case-insensitive)
        sorted_sections = sorted(sections, key=lambda s: s['name'].lower())

        total_owned = 0  # Initialize global owned counter
        total_games = 0  # Initialize global total counter

        for section in sorted_sections:  # Accumulate global counters from all sections
            owned, total = compute_console_counters(section["games"])
            total_owned += owned
            total_games += total

        output_lines = []  # Initialize output line accumulator

        # Header block with title and counters
        owned_breakdown = " + ".join(f"{section['name']} {compute_console_counters(section['games'])[0]}" for section in sorted_sections)
        total_breakdown = " + ".join(f"{section['name']} {compute_console_counters(section['games'])[1]}" for section in sorted_sections)

        percent_owned = int(round((total_owned / total_games) * 100)) if total_games > 0 else 0
        title_line = f"-- Games Collection: {total_owned} / {total_games} - {percent_owned}%."

        output_lines.append(title_line)
        output_lines.append(f"-- Owned: {total_owned} ({owned_breakdown}).")
        output_lines.append(f"-- Total: {total_games} ({total_breakdown}).")
        output_lines.append(f"-- Icons: {ICON_OWNED} {ICON_MAYBE}")

        output_lines.append("")

        for section in sorted_sections:
            owned, total = compute_console_counters(section["games"])
            percent = int(round((owned / total) * 100)) if total > 0 else 0
            section_line = f"-- {section['name']}: {owned} / {total} - {percent}%."
            section_line = re.sub(r"\.+$", ".", section_line)
            output_lines.append(section_line)

            for game_line in section["games"]:
                output_lines.append(game_line)

            output_lines.append("")

        if output_lines and output_lines[-1] == "":
            output_lines = output_lines[:-1]

        cleaned_lines = [re.sub(r"[ ]{2,}", " ", re.sub(r"\.\.+", ".", line)) for line in output_lines]
        return "\n".join(cleaned_lines) + "\n"

    except Exception as e:  # Catch unexpected formatting errors
        print(f"{BackgroundColors.RED}Error formatting TXT output: {e}{Style.RESET_ALL}")  # Log error
        return ""  # Return empty string on failure


def write_txt_file(filepath: str, content: str) -> bool:
    """
    Overwrite a TXT file with the given content string using UTF-8 encoding.

    :param filepath: Absolute path to the TXT file to overwrite.
    :param content: Full content string to write into the file.
    :return: True on successful write, False on failure.
    """

    try:  # Wrap file writing for safe execution
        with open(filepath, "w", encoding="utf-8") as file_handle:  # Open file in write mode with UTF-8 encoding
            file_handle.write(content)  # Write full formatted content to file

        verbose_output(true_string=f"{BackgroundColors.GREEN}Successfully wrote normalized output to: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}")  # Log success

        return True  # Signal successful write

    except Exception as e:  # Catch file write errors
        print(f"{BackgroundColors.RED}Error writing file {BackgroundColors.CYAN}{filepath}{BackgroundColors.RED}: {e}{Style.RESET_ALL}")  # Log error
        return False  # Signal write failure


def process_txt_file(filepath: str) -> None:
    """
    Process a single TXT game-collection file end-to-end.

    Reads the file, parses all console sections and game entries, normalizes
    formatting, sorts games alphabetically, recalculates all counters, and
    overwrites the file with the canonical deterministic output.

    :param filepath: Absolute path to the TXT file to process.
    :return: None
    """

    try:  # Wrap full file processing for safe execution
        print(f"{BackgroundColors.GREEN}Processing file: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}")  # Log processing start

        lines = read_txt_file(filepath)  # Read all lines from the target file

        if not lines:  # Skip files that could not be read or are empty
            print(f"{BackgroundColors.YELLOW}Warning: File is empty or unreadable — skipping. File: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}")  # Log warning
            return  # Exit early for empty or unreadable files

        sections = parse_console_sections(lines, filepath)  # Parse all console sections and games from file lines

        if not sections:  # Skip files that produced no valid console sections
            print(f"{BackgroundColors.YELLOW}Warning: No valid console sections found — skipping. File: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}")  # Log warning
            return  # Exit early when no sections were parsed

        formatted_content = format_txt_output(sections)  # Format all sections into canonical TXT string

        if not formatted_content:  # Skip files where formatting produced empty output
            print(f"{BackgroundColors.YELLOW}Warning: Formatted output is empty — skipping write. File: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}")  # Log warning
            return  # Exit early when formatting fails

        success = write_txt_file(filepath, formatted_content)  # Overwrite file with normalized canonical content

        if success:  # Log successful completion
            total_games = sum(len(s["games"]) for s in sections)  # Compute total valid game count for summary
            print(f"{BackgroundColors.GREEN}Finished processing: {BackgroundColors.CYAN}{filepath}{BackgroundColors.GREEN} — {BackgroundColors.CYAN}{len(sections)}{BackgroundColors.GREEN} console(s), {BackgroundColors.CYAN}{total_games}{BackgroundColors.GREEN} game(s).{Style.RESET_ALL}")  # Log file summary

    except Exception as e:  # Catch unexpected errors during full file processing
        print(f"{BackgroundColors.RED}Error processing file {BackgroundColors.CYAN}{filepath}{BackgroundColors.RED}: {e}{Style.RESET_ALL}")  # Log error


def process_all_txt_files() -> None:
    """
    Discover and process all TXT files found in the INPUTS_DIR directory.

    Iterates each discovered TXT file and delegates processing to process_txt_file.
    Logs a summary upon completion of all files.

    :param: None
    :return: None
    """

    try:  # Wrap full multi-file processing for safe execution
        txt_files = collect_txt_files(INPUTS_DIR)  # Discover all TXT files in the inputs directory

        if not txt_files:  # Skip when no TXT files were found
            print(f"{BackgroundColors.YELLOW}No TXT files found in {BackgroundColors.CYAN}{INPUTS_DIR}{BackgroundColors.YELLOW}. Nothing to process.{Style.RESET_ALL}")  # Log empty state
            return  # Exit early when no files are available

        print(f"{BackgroundColors.GREEN}Starting TXT processing for {BackgroundColors.CYAN}{len(txt_files)}{BackgroundColors.GREEN} file(s) in {BackgroundColors.CYAN}{INPUTS_DIR}{BackgroundColors.GREEN}.{Style.RESET_ALL}")  # Log processing start

        for txt_filepath in txt_files:  # Iterate and process each discovered TXT file
            process_txt_file(txt_filepath)  # Process individual TXT file end-to-end

        print(f"{BackgroundColors.GREEN}All TXT files processed successfully.{Style.RESET_ALL}")  # Log global completion

    except Exception as e:  # Catch unexpected errors during multi-file processing
        print(f"{BackgroundColors.RED}Error during TXT file processing: {e}{Style.RESET_ALL}")  # Log error


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
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Games Collection Manager{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n",
    )  # Output the welcome message
    
    start_time = datetime.datetime.now()  # Get the start time of the program
    
    process_all_txt_files()  # Discover, parse, normalize, and rewrite all TXT files in INPUTS_DIR

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
