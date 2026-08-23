"""
================================================================================
<PROJECT OR SCRIPT TITLE>
================================================================================
Author      : Breno Farias da Silva
Created     : <YYYY-MM-DD>
Description :
    <Provide a concise and complete overview of what this script does.>
    <Mention its purpose, scope, and relevance to the larger project.>

    Key features include:
        - <Feature 1 — e.g., automatic data loading and preprocessing>
        - <Feature 2 — e.g., model training and evaluation>
        - <Feature 3 — e.g., visualization or report generation>
        - <Feature 4 — e.g., logging or notification system>
        - <Feature 5 — e.g., integration with other modules or datasets>

Usage:
    1. <Explain any configuration steps before running, such as editing variables or paths.>
    2. <Describe how to execute the script — typically via Makefile or Python.>
        $ make <target>   or   $ python <script_name>.py
    3. <List what outputs are expected or where results are saved.>

Outputs:
    - <Output file or directory 1 — e.g., results.csv>
    - <Output file or directory 2 — e.g., Feature_Analysis/plots/>
    - <Output file or directory 3 — e.g., logs/output.txt>

TODOs:
    - <Add a task or improvement — e.g., implement CLI argument parsing.>
    - <Add another improvement — e.g., extend support to Parquet files.>
    - <Add optimization — e.g., parallelize evaluation loop.>
    - <Add robustness — e.g., error handling or data validation.>

Dependencies:
    - Python >= <version>
    - <Library 1 — e.g., pandas>
    - <Library 2 — e.g., numpy>
    - <Library 3 — e.g., scikit-learn>
    - <Library 4 — e.g., matplotlib, seaborn, tqdm, colorama>

Assumptions & Notes:
    - <List any key assumptions — e.g., last column is the target variable.>
    - <Mention data format — e.g., CSV files only.>
    - <Mention platform or OS-specific notes — e.g., sound disabled on Windows.>
    - <Note on output structure or reusability.>
"""

import atexit  # For playing a sound when the program finishes
import datetime  # For getting the current date and time
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For matching SRT timestamps and SDH fragments
import sys  # For system-specific parameters and functions
import unicodedata  # For normalizing Unicode subtitle text
from colorama import Style  # For coloring the terminal
from Logger import Logger  # For logging output to both terminal and file
from pathlib import Path  # For handling file paths
from tqdm import tqdm  # For displaying in-place per-directory progress bars


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
IN_PLACE_UPDATE = False  # Set to True to atomically update original SRT files instead of creating .cleaned.srt files
INPUT_DIRS = [f"E:/Movies/", f"F:/Movies/", f"F:/Series/", f"G:/Series/"]  # Directories searched recursively for source SRT files
SRT_TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")  # Common UTF-8 and Western/Portuguese subtitle encodings
MOJIBAKE_MARKERS = ("Ã", "Â", "â€", "ðŸ", "ï»¿", "�")  # Strong indicators of UTF-8 text decoded through a Western single-byte encoding
SRT_TIMESTAMP_PATTERN = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3}\s+-->\s+\d{2}:\d{2}:\d{2},\d{3}(?:\s+.*)?$")  # SRT timestamp validation pattern
SRT_REPAIRABLE_TIMESTAMP_PATTERN = re.compile(r"^(?P<start_h>\d{2}):(?P<start_m>\d{2}):(?P<start_s>\d{2}),(?P<start_ms>\d{3,})\s+-->\s+(?P<end_h>\d{2}):(?P<end_m>\d{2}):(?P<end_s>\d{2}),(?P<end_ms>\d{3,})(?P<suffix>(?:\s+.*)?)$")  # Timestamp pattern that also accepts overlong millisecond fields for repair
SUBTITLE_FORMATTING_TAG_PATTERN = re.compile(r"</?(?:i|b|u|font)(?:\s+[^<>]*)?>", re.IGNORECASE)  # Recognized SRT formatting tag pattern
EMPTY_SUBTITLE_FORMATTING_TAG_PATTERN = re.compile(r"<(i|b|u|font)(?:\s+[^<>]*)?>\s*</\1>", re.IGNORECASE)  # Recognized empty SRT formatting tag pattern
DESCRIPTIVE_PHRASES = frozenset(("music", "door closes", "applause", "speaking indistinctly", "laughing", "laughs", "sighs", "sigh", "whispers", "whispering", "inaudible", "indistinct chatter", "chuckles", "gasps", "coughs", "sobs", "crying", "screaming", "phone ringing", "knocking", "footsteps", "thunder", "alarm", "silence"))  # Conservative complete SDH fragments
DESCRIPTIVE_KEYWORDS = frozenset(("music", "applause", "laughing", "laughs", "sighs", "sigh", "whispers", "whispering", "inaudible", "indistinctly", "chatter", "chuckles", "gasps", "coughs", "sobs", "crying", "screaming", "ringing", "knocking", "footsteps", "thunder", "alarm", "silence"))  # SDH indicator words
DESCRIPTIVE_WORDS = frozenset(("music", "door", "doors", "closes", "close", "closing", "opens", "opening", "applause", "speaking", "indistinctly", "indistinct", "laughing", "laughs", "sighs", "sigh", "whispers", "whispering", "inaudible", "chatter", "crowd", "chuckles", "softly", "gasps", "coughs", "sobs", "crying", "screaming", "phone", "ringing", "knocking", "knocks", "footsteps", "thunder", "alarm", "silence", "dramatic"))  # Allowed words inside SDH fragments

# Logger Setup:
PROGRESS_OUTPUT = sys.stdout  # Preserve the original terminal stream so tqdm can update one line in place
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


def mojibake_score(value: str) -> int:
    """
    Score text for strong mojibake indicators.

    :param value: Decoded subtitle text.
    :return: Number of suspicious mojibake markers.
    """

    score = sum(value.count(marker) for marker in MOJIBAKE_MARKERS)  # Count strong UTF-8/Western decoding artifacts
    score += sum(1 for character in value if 0x80 <= ord(character) <= 0x9F)  # Penalize embedded C1 control characters
    return score  # Return lower-is-better mojibake score


def repair_common_mojibake(value: str) -> str:
    """
    Conservatively repair common UTF-8-as-CP1252/Latin-1 mojibake.

    Valid Portuguese characters are preserved unless a reversible repair
    produces text with fewer strong mojibake indicators.

    :param value: Decoded subtitle text.
    :return: Unicode-normalized subtitle text with safe mojibake repairs.
    """

    repaired_value = unicodedata.normalize("NFC", value)  # Normalize decomposed accents such as a + combining acute

    for _ in range(2):  # Repair at most two layers of accidental re-encoding
        current_score = mojibake_score(repaired_value)  # Measure current text corruption indicators

        if current_score == 0:  # Avoid touching already clean text
            break  # Preserve valid Portuguese and foreign characters exactly

        best_value = repaired_value  # Default to current text
        best_score = current_score  # Keep current score as the threshold to beat

        for source_encoding in ("cp1252", "latin-1"):  # Try common incorrect Western decoding layers
            try:
                candidate = repaired_value.encode(source_encoding).decode("utf-8")  # Reverse UTF-8 bytes misread as Western text
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue  # This repair path is not reversible for the current text

            candidate = unicodedata.normalize("NFC", candidate)  # Normalize repaired Unicode accents
            candidate_score = mojibake_score(candidate)  # Score repaired candidate

            if candidate_score < best_score:  # Accept only a strict reduction in corruption markers
                best_value = candidate  # Store safer repaired text
                best_score = candidate_score  # Store improved score

        if best_value == repaired_value:  # Stop when no safe repair improved the text
            break

        repaired_value = best_value  # Continue in case the subtitle was double-encoded

    repaired_value = repaired_value.replace("\ufeff", "")  # Remove stray BOM characters embedded inside subtitle text
    repaired_value = repaired_value.replace("\u200b", "")  # Remove zero-width spaces that can appear from subtitle conversions
    return unicodedata.normalize("NFC", repaired_value)  # Return canonically normalized Unicode text


def read_srt_file(filepath: Path) -> tuple[str, str]:
    """
    Read an SRT file with PT-BR-friendly encoding fallbacks and mojibake repair.

    :param filepath: Source SRT path.
    :return: Decoded/repaired text and detected encoding name.
    """

    data = filepath.read_bytes()  # Read raw bytes without altering source file

    if data.startswith((b"\xff\xfe", b"\xfe\xff")):  # Detect UTF-16 BOM before trying single-byte encodings
        decoded_text = data.decode("utf-16")  # Decode UTF-16 using BOM byte order
        return repair_common_mojibake(decoded_text), "utf-16"  # Normalize and repair decoded subtitle text

    for encoding in SRT_TEXT_ENCODINGS:  # Try common UTF-8 and Western/Portuguese subtitle encodings
        try:
            decoded_text = data.decode(encoding)  # Decode source bytes using current candidate
            return repair_common_mojibake(decoded_text), encoding  # Repair common mojibake after successful decoding
        except UnicodeDecodeError:
            continue  # Try next encoding after strict decode failure

    raise UnicodeDecodeError("utf-8", data, 0, 1, "Unable to decode subtitle file")  # Report unsupported encoding


def discover_srt_files(input_dir: Path) -> list[Path]:
    """
    Discover source SRT files recursively.

    :param input_dir: Directory to search.
    :return: Sorted source SRT paths.
    """

    return sorted(path for path in input_dir.rglob("*.srt") if not path.name.lower().endswith(".cleaned.srt"))  # Exclude generated cleaned files



def normalize_srt_time_component(hours: str, minutes: str, seconds: str, milliseconds: str) -> str:
    """
    Normalize one SRT time component whose millisecond field may overflow three digits.

    Values such as 00:20:08,1000 are interpreted as 1000 milliseconds and
    normalized to 00:20:09,000 instead of being truncated to 00:20:08,100.

    :param hours: Two-digit hour component.
    :param minutes: Two-digit minute component.
    :param seconds: Two-digit second component.
    :param milliseconds: Millisecond component containing at least three digits.
    :return: Strict HH:MM:SS,mmm SRT time component.
    """

    millisecond_value = int(milliseconds)  # Parse the full millisecond value without discarding overflow digits
    carry_seconds, normalized_milliseconds = divmod(millisecond_value, 1000)  # Carry every complete 1000 ms into seconds
    total_seconds = (int(hours) * 3600) + (int(minutes) * 60) + int(seconds) + carry_seconds  # Build normalized whole-second value
    normalized_hours, remaining_seconds = divmod(total_seconds, 3600)  # Carry second/minute overflow into hours
    normalized_minutes, normalized_seconds = divmod(remaining_seconds, 60)  # Carry second overflow into minutes
    return f"{normalized_hours:02d}:{normalized_minutes:02d}:{normalized_seconds:02d},{normalized_milliseconds:03d}"  # Return strict SRT timestamp component


def repair_srt_timestamp_line(timestamp: str) -> tuple[str, bool]:
    """
    Repair overlong SRT millisecond fields while preserving valid timestamps.

    :param timestamp: Original SRT timestamp line.
    :return: Repaired timestamp and whether a repair was applied.
    """

    if SRT_TIMESTAMP_PATTERN.match(timestamp):  # Preserve already-valid timestamps exactly
        return timestamp, False  # No repair needed

    match = SRT_REPAIRABLE_TIMESTAMP_PATTERN.match(timestamp)  # Match timestamps whose millisecond fields contain three or more digits

    if match is None:  # Leave unrelated malformed timestamp formats for normal validation to reject
        return timestamp, False  # Not safely repairable by this rule

    start_ms = match.group("start_ms")  # Capture starting millisecond field
    end_ms = match.group("end_ms")  # Capture ending millisecond field

    if len(start_ms) == 3 and len(end_ms) == 3:  # Require at least one actual overlong millisecond field
        return timestamp, False  # Nothing to repair

    repaired_start = normalize_srt_time_component(
        match.group("start_h"),
        match.group("start_m"),
        match.group("start_s"),
        start_ms,
    )  # Normalize starting timestamp
    repaired_end = normalize_srt_time_component(
        match.group("end_h"),
        match.group("end_m"),
        match.group("end_s"),
        end_ms,
    )  # Normalize ending timestamp
    repaired_timestamp = f"{repaired_start} --> {repaired_end}{match.group('suffix')}"  # Rebuild strict SRT timestamp line
    return repaired_timestamp, repaired_timestamp != timestamp  # Report whether timestamp changed


def repair_srt_timestamps(content: str) -> tuple[str, list[tuple[int, str, str]]]:
    """
    Repair overlong millisecond fields in SRT timestamp lines before strict parsing.

    :param content: Decoded SRT text.
    :return: Repaired SRT text and timestamp repair records.
    """

    normalized_content = content.replace("\r\n", "\n").replace("\r", "\n")  # Normalize line endings for deterministic scanning
    lines = normalized_content.split("\n")  # Split content while preserving SRT structure
    repairs = []  # Store block number and original/repaired timestamp values
    block_number = 0  # Track logical SRT block number

    for line_index, line in enumerate(lines):  # Inspect every line for timestamp candidates
        if line.strip().isdigit():  # Detect an SRT block index line
            try:
                block_number = int(line.strip())  # Use the actual subtitle index for repair reporting
            except ValueError:
                block_number = 0  # Fall back safely if an unexpected numeric conversion issue occurs
            continue

        stripped_line = line.strip()  # Ignore only outer whitespace while matching timestamp syntax

        if "-->" not in stripped_line:  # Skip ordinary subtitle dialogue lines
            continue

        repaired_timestamp, changed = repair_srt_timestamp_line(stripped_line)  # Repair safe millisecond overflow

        if not changed:  # Preserve lines that do not require this specific repair
            continue

        lines[line_index] = repaired_timestamp  # Replace malformed timestamp with strict normalized value
        repairs.append((block_number, stripped_line, repaired_timestamp))  # Record repair for diff reporting

    return "\n".join(lines), repairs  # Return repaired content and deterministic repair records


def build_timestamp_repair_report(repairs: list[tuple[int, str, str]]) -> str:
    """
    Build diff report sections for repaired SRT timestamps.

    :param repairs: Timestamp repair records.
    :return: Human-readable timestamp repair report text.
    """

    sections = []  # Store one report section per repaired timestamp

    for block_number, original_timestamp, repaired_timestamp in repairs:  # Describe each timestamp correction
        sections.append(
            f"Original index: {block_number}\n"
            f"Change: Timestamp repaired\n"
            f"Original timestamp:\n{original_timestamp}\n"
            f"Cleaned timestamp:\n{repaired_timestamp}"
        )  # Add deterministic repair section

    return "\n\n---\n\n".join(sections) + ("\n" if sections else "")  # Return diff-compatible report text


def remove_empty_srt_blocks(content: str) -> tuple[str, list[tuple[int, str]]]:
    """
    Remove SRT blocks that contain an index and timestamp but no subtitle text.

    Example removed block:
        162
        00:19:13,471 --> 00:19:15,861

    :param content: SRT text after timestamp repair.
    :return: Repaired SRT text and records of removed empty blocks.
    """

    normalized_content = content.replace("\r\n", "\n").replace("\r", "\n").strip("\ufeff")  # Normalize line endings
    raw_blocks = [block for block in re.split(r"\n\s*\n", normalized_content.strip()) if block.strip()]  # Split logical SRT blocks
    kept_blocks = []  # Store valid/non-empty blocks for strict parsing
    removed_blocks = []  # Store removed empty block index/timestamp pairs

    for block in raw_blocks:  # Inspect every logical SRT block before strict validation
        lines = block.split("\n")  # Split current block into index, timestamp, and possible text

        if len(lines) >= 2:  # Require enough structure to identify an SRT block safely
            index_text = lines[0].strip()  # Normalize possible subtitle index
            timestamp = lines[1].strip()  # Normalize possible timestamp
            text_lines = lines[2:]  # Capture any subtitle text lines, including whitespace-only lines

            if index_text.isdigit() and SRT_TIMESTAMP_PATTERN.match(timestamp) and not any(line.strip() for line in text_lines):
                removed_blocks.append((int(index_text), timestamp))  # Record empty subtitle block removal
                continue  # Exclude empty block from repaired SRT content

        kept_blocks.append(block)  # Preserve blocks that are not safely identified as empty subtitle entries

    repaired_content = "\n\n".join(kept_blocks) + ("\n" if kept_blocks else "")  # Rebuild deterministic SRT structure
    return repaired_content, removed_blocks  # Return repaired SRT text and removed block records


def build_empty_block_repair_report(removed_blocks: list[tuple[int, str]]) -> str:
    """
    Build diff report sections for removed empty SRT blocks.

    :param removed_blocks: Empty block index/timestamp pairs.
    :return: Human-readable empty-block repair report text.
    """

    sections = []  # Store one report section per removed empty block

    for index, timestamp in removed_blocks:  # Describe each malformed empty block removal
        sections.append(
            f"Original index: {index}\n"
            f"Timestamp: {timestamp}\n"
            f"Change: Empty block removed\n"
            f"Original:\n<empty subtitle block>\n"
            f"Cleaned:\n<removed>"
        )  # Add deterministic repair section

    return "\n\n---\n\n".join(sections) + ("\n" if sections else "")  # Return diff-compatible report text


def parse_srt_content(content: str, filepath: Path) -> list[tuple[int, str, list[str]]]:
    """
    Parse and validate SRT content.

    :param content: Decoded SRT text.
    :param filepath: Source path for error context.
    :return: Parsed subtitle entries.
    """

    normalized_content = content.replace("\r\n", "\n").replace("\r", "\n").strip("\ufeff")  # Normalize line endings
    blocks = [block for block in re.split(r"\n\s*\n", normalized_content.strip()) if block.strip()]  # Split entries on blank lines

    if not blocks:  # Reject empty subtitles
        raise ValueError(f"Malformed SRT file with no entries: {filepath}")  # Report malformed file

    entries = []  # Store parsed subtitle entries

    for block_number, block in enumerate(blocks, start=1):  # Parse each subtitle block
        lines = block.split("\n")  # Split block into lines

        if len(lines) < 3:  # Require index, timestamp, and subtitle text
            raise ValueError(f"Malformed SRT block {block_number} in {filepath}")  # Report malformed block

        try:  # Parse numeric subtitle index
            index = int(lines[0].strip())  # Convert index line to integer
        except ValueError as exc:  # Handle invalid index line
            raise ValueError(f"Invalid SRT index in block {block_number} in {filepath}") from exc  # Report invalid index

        if index <= 0:  # Require positive subtitle indexes
            raise ValueError(f"Invalid SRT index in block {block_number} in {filepath}")  # Report invalid index

        timestamp = lines[1].strip()  # Preserve timestamp text without outer whitespace

        if not SRT_TIMESTAMP_PATTERN.match(timestamp):  # Validate timestamp range syntax
            raise ValueError(f"Invalid SRT timestamp in block {block_number} in {filepath}")  # Report invalid timestamp

        text_lines = [line.rstrip() for line in lines[2:]]  # Preserve subtitle text with trailing whitespace removed

        if not any(line.strip() for line in text_lines):  # Require meaningful subtitle text lines
            raise ValueError(f"Empty SRT text in block {block_number} in {filepath}")  # Report empty subtitle text

        entries.append((index, timestamp, text_lines))  # Store parsed entry

    return entries  # Return parsed entries


def serialize_srt_entries(entries: list[tuple[int, str, list[str]]]) -> str:
    """
    Serialize parsed SRT entries with sequential numbering.

    :param entries: Parsed subtitle entries.
    :return: Serialized SRT text.
    """

    blocks = []  # Store serialized blocks

    for new_index, entry in enumerate(entries, start=1):  # Renumber entries sequentially
        blocks.append("\n".join([str(new_index), entry[1], *entry[2]]))  # Serialize one subtitle block

    return "\n\n".join(blocks) + ("\n" if blocks else "")  # Return valid SRT text


def normalize_phrase(value: str) -> str:
    """
    Normalize a possible SDH phrase for conservative matching.

    :param value: Phrase to normalize.
    :return: Normalized phrase.
    """

    plain_value = remove_subtitle_formatting_tags(value)  # Remove recognized SRT formatting tags for classification
    plain_value = plain_value.replace("♪", " ")  # Ignore music note markers for classification
    plain_value = re.sub(r"[^A-Za-z\s-]", " ", plain_value)  # Remove punctuation except word separators
    plain_value = re.sub(r"\s+", " ", plain_value).strip().lower()  # Normalize whitespace and case
    return plain_value  # Return normalized phrase


def is_descriptive_phrase(value: str) -> bool:
    """
    Identify conservative SDH/descriptive phrases.

    :param value: Candidate text inside a fragment.
    :return: True when the phrase is descriptive content.
    """

    if any(character.isdigit() for character in value):  # Preserve numbered bracketed text
        return False  # Treat numeric fragments as dialogue context

    phrase = normalize_phrase(value)  # Normalize candidate phrase

    if not phrase:  # Ignore empty candidates
        return False  # Preserve unknown empty fragments

    if phrase in DESCRIPTIVE_PHRASES:  # Match known complete descriptors
        return True  # Remove known descriptor

    words = phrase.replace("-", " ").split()  # Split phrase into words

    if len(words) > 5:  # Avoid broad removal of long prose fragments
        return False  # Preserve long ambiguous fragments

    if not any(word in DESCRIPTIVE_KEYWORDS for word in words):  # Require one strong SDH word
        return False  # Preserve ambiguous fragments

    return all(word in DESCRIPTIVE_WORDS for word in words)  # Remove only known descriptive word combinations


def is_music_only_line(value: str) -> bool:
    """
    Identify music-symbol lines that contain only descriptive content.

    :param value: Subtitle line.
    :return: True when the line contains only a music descriptor.
    """

    if "♪" not in value:  # Preserve lines without music symbols
        return False  # Not a music-symbol descriptor

    return is_descriptive_phrase(value)  # Reuse conservative phrase classification


def remove_subtitle_formatting_tags(value: str) -> str:
    """
    Remove recognized SRT formatting tags while preserving enclosed dialogue.

    :param value: Subtitle line.
    :return: Subtitle line without recognized SRT formatting tags.
    """

    return SUBTITLE_FORMATTING_TAG_PATTERN.sub("", value)  # Remove opening, closing, and orphan formatting tags


def remove_empty_html_tags(value: str) -> str:
    """
    Remove empty HTML tags left after SDH removal.

    :param value: Subtitle line.
    :return: Subtitle line without empty HTML tags.
    """

    previous_value = None  # Track previous value for loop convergence

    while previous_value != value:  # Repeat until nested empty tags are gone
        previous_value = value  # Store value before replacement
        value = EMPTY_SUBTITLE_FORMATTING_TAG_PATTERN.sub(" ", value)  # Remove empty recognized formatting tags

    return value  # Return cleaned line


def normalize_subtitle_whitespace(value: str) -> str:
    """
    Normalize repeated horizontal whitespace without merging subtitle lines.

    :param value: Subtitle text to normalize.
    :return: Text with horizontal whitespace runs collapsed to one regular space.
    """

    return re.sub(r"[^\S\r\n]+", " ", value).strip()  # Collapse spaces, tabs, and other horizontal whitespace runs


def clean_subtitle_line(line: str) -> str:
    """
    Remove conservative SDH/descriptive fragments from one subtitle line.

    :param line: Original subtitle line.
    :return: Cleaned subtitle line.
    """

    def replace_fragment(match: re.Match[str]) -> str:
        """
        Replace one bracketed or parenthesized fragment when descriptive.

        :param match: Regex match object.
        :return: Replacement text.
        """

        fragment = match.group(0)  # Capture full bracketed fragment
        inner_text = fragment[1:-1]  # Extract fragment text without brackets
        return " " if is_descriptive_phrase(inner_text) else fragment  # Remove descriptor or preserve text

    cleaned_line = remove_subtitle_formatting_tags(line)  # Remove formatting tags before SDH cue removal
    cleaned_line = re.sub(r"\[[^\[\]\n]{1,80}\]|\([^\(\)\n]{1,80}\)", replace_fragment, cleaned_line)  # Remove conservative bracket fragments
    cleaned_line = remove_empty_html_tags(cleaned_line)  # Remove tags emptied by fragment removal

    if is_music_only_line(cleaned_line):  # Remove music-only descriptor lines
        return ""  # Drop descriptor line

    cleaned_line = normalize_subtitle_whitespace(cleaned_line)  # Collapse repeated horizontal whitespace to one regular space
    cleaned_line = re.sub(r"\s+([,.!?;:])", r"\1", cleaned_line)  # Remove spaces before punctuation
    cleaned_line = re.sub(r"(<[^/][^>]*>)\s+", r"\1", cleaned_line)  # Remove leading whitespace inside opening tags
    cleaned_line = re.sub(r"\s+(</[^>]+>)", r"\1", cleaned_line)  # Remove trailing whitespace inside closing tags
    cleaned_line = remove_empty_html_tags(cleaned_line)  # Remove any newly empty tags
    return normalize_subtitle_whitespace(cleaned_line)  # Normalize whitespace introduced by cleanup and strip outer whitespace


def clean_subtitle_lines(lines: list[str]) -> list[str]:
    """
    Remove SDH/descriptive content from multiline subtitle text.

    :param lines: Original subtitle text lines.
    :return: Cleaned subtitle text lines.
    """

    cleaned_lines = []  # Store cleaned text lines

    for line in lines:  # Clean every original subtitle line
        cleaned_line = clean_subtitle_line(line)  # Remove SDH fragments from current line

        if cleaned_line:  # Preserve non-empty dialogue lines
            cleaned_lines.append(cleaned_line)  # Add cleaned dialogue line

    return cleaned_lines  # Return cleaned text lines


def clean_subtitle_entries(entries: list[tuple[int, str, list[str]]]) -> tuple[list[tuple[int, str, list[str]]], list[tuple[int, str, str, str, bool]], int, int]:
    """
    Remove SDH/descriptive content from parsed subtitle entries.

    :param entries: Parsed subtitle entries.
    :return: Cleaned entries, diff changes, removed count, and mixed modified count.
    """

    cleaned_entries = []  # Store entries that keep dialogue
    changes = []  # Store diff report entries
    removed_count = 0  # Count complete entry removals
    modified_count = 0  # Count mixed entry modifications

    for index, timestamp, lines in entries:  # Process each parsed subtitle entry
        cleaned_lines = clean_subtitle_lines(lines)  # Clean multiline subtitle text
        original_text = "\n".join(lines)  # Build original text for diff report
        cleaned_text = "\n".join(cleaned_lines)  # Build cleaned text for diff report

        if not cleaned_lines:  # Remove entry when no dialogue remains
            removed_count += 1  # Count removed entry
            changes.append((index, timestamp, original_text, "", True))  # Store removed-entry diff with empty cleaned text
            continue  # Skip removed entry

        cleaned_entries.append((index, timestamp, cleaned_lines))  # Preserve cleaned entry

        if cleaned_text != original_text:  # Record mixed entry changes
            modified_count += 1  # Count modified mixed entry
            changes.append((index, timestamp, original_text, cleaned_text, False))  # Store replacement diff

    return cleaned_entries, changes, removed_count, modified_count  # Return cleaned data and counts


def build_diff_report(changes: list[tuple[int, str, str, str, bool]]) -> str:
    """
    Build a deterministic readable cleanup diff report.

    :param changes: Modified or removed subtitle entries.
    :return: Diff report text.
    """

    sections = []  # Store report sections

    for index, timestamp, original_text, cleaned_text, removed in changes:  # Add one section per changed entry
        marker = "Removed" if removed else "Modified"  # Select change marker
        sections.append(f"Original index: {index}\nTimestamp: {timestamp}\nChange: {marker}\nOriginal:\n{original_text}\nCleaned:\n{cleaned_text}")  # Add readable diff section

    return "\n\n---\n\n".join(sections) + "\n"  # Return deterministic UTF-8 report text


def validate_cleaned_srt(content: str, filepath: Path) -> None:
    """
    Validate cleaned SRT content before publishing.

    :param content: Cleaned SRT text.
    :param filepath: Output SRT path.
    :return: None
    """

    if not content.strip():  # Allow an empty cleaned file when every entry was removed
        return  # Empty output is valid for all-descriptor sources

    parse_srt_content(content, filepath)  # Validate serialized SRT structure


def atomic_write_text(filepath: Path, content: str) -> None:
    """
    Write text with a temporary file and atomic replacement.

    :param filepath: Destination path.
    :param content: UTF-8 text content.
    :return: None
    """

    temporary_filepath = filepath.with_name(f".{filepath.name}.{os.getpid()}.tmp")  # Build sibling temporary path

    try:  # Write and publish atomically
        filepath.parent.mkdir(parents=True, exist_ok=True)  # Create output directory
        with open(temporary_filepath, "w", encoding="utf-8", newline="\n") as temporary_file:  # Open UTF-8 temporary file
            temporary_file.write(content)  # Write generated text
        os.replace(temporary_filepath, filepath)  # Replace destination atomically on same filesystem
    finally:  # Remove leftover temporary file after failures
        if temporary_filepath.exists():  # Detect incomplete temporary file
            temporary_filepath.unlink()  # Remove incomplete temporary file


def display_input_directory(input_dir: Path) -> str:
    """
    Format an input directory using forward slashes for progress display.

    :param input_dir: Input root path.
    :return: Display-friendly input directory path.
    """

    return input_dir.as_posix().rstrip("/") + "/"  # Keep Unix-like separators and one trailing slash


def display_relative_path(filepath: Path, input_dir: Path) -> str:
    """
    Format a path relative to the input directory when possible.

    :param filepath: Path to format.
    :param input_dir: Input root path.
    :return: Display path.
    """

    try:  # Prefer paths relative to the current input directory
        return filepath.relative_to(input_dir).as_posix()  # Return relative display path
    except ValueError:  # Fall back when path is outside the current input directory
        return filepath.as_posix()  # Return absolute display path


def process_srt_file(filepath: Path, input_dir: Path, log_output: bool = True) -> tuple[int, int, int, int, int]:
    """
    Process one SRT file and write cleaned output when content changed.

    :param filepath: Source SRT path.
    :param input_dir: Input root path.
    :param log_output: Set to False when an external progress bar owns per-file terminal output.
    :return: Cleaned files, unchanged files, failed files, removed entries, and modified mixed entries.
    """

    relative_path = display_relative_path(filepath, input_dir)  # Build concise log path

    if log_output:  # Preserve direct-call processing log outside progress-bar mode
        print(f"Processing: {relative_path}")  # Log source being processed

    try:  # Keep one file failure from stopping the batch
        content, _encoding = read_srt_file(filepath)  # Read and decode source SRT
        timestamp_repaired_content, timestamp_repairs = repair_srt_timestamps(content)  # Repair overlong millisecond fields before strict SRT validation
        structurally_repaired_content, empty_block_repairs = remove_empty_srt_blocks(timestamp_repaired_content)  # Remove timestamped blocks that contain no subtitle text
        entries = parse_srt_content(structurally_repaired_content, filepath)  # Parse and validate structurally repaired source SRT
        cleaned_entries, changes, removed_count, modified_count = clean_subtitle_entries(entries)  # Remove SDH content

        if not changes and not timestamp_repairs and not empty_block_repairs:  # Avoid output files when no subtitle cleanup or structural repair occurred
            if log_output:  # Preserve direct-call unchanged log outside progress-bar mode
                print(f"No SDH/descriptive content or SRT repairs found: {relative_path}")  # Log unchanged source
            return 0, 1, 0, 0, 0  # Return unchanged count

        cleaned_srt_filepath = filepath if IN_PLACE_UPDATE else filepath.with_name(f"{filepath.stem}.cleaned.srt")  # Select original file or separate cleaned output
        diff_filepath = filepath.with_name(f"{filepath.stem}.cleaned.diff")  # Build per-source diff path

        if diff_filepath == filepath:  # Prevent diff report from overwriting source subtitle
            raise ValueError(f"Refusing to overwrite source file with diff report: {filepath}")  # Report unsafe output path
        if not IN_PLACE_UPDATE and cleaned_srt_filepath == filepath:  # Prevent accidental source overwrite outside explicit in-place mode
            raise ValueError(f"Refusing to overwrite source file: {filepath}")  # Report unsafe output path

        cleaned_content = serialize_srt_entries(cleaned_entries)  # Serialize cleaned SRT with sequential numbering
        validate_cleaned_srt(cleaned_content, cleaned_srt_filepath)  # Validate cleaned SRT before writing
        text_diff_content = build_diff_report(changes) if changes else ""  # Build readable subtitle-text diff report when needed
        timestamp_diff_content = build_timestamp_repair_report(timestamp_repairs)  # Build timestamp repair report when needed
        empty_block_diff_content = build_empty_block_repair_report(empty_block_repairs)  # Build malformed empty-block repair report when needed
        diff_sections = [section.rstrip() for section in (timestamp_diff_content, empty_block_diff_content, text_diff_content) if section.strip()]  # Keep only populated report sections
        diff_content = "\n\n---\n\n".join(diff_sections) + ("\n" if diff_sections else "")  # Merge structural and text changes into one diff report

        if not diff_content.strip():  # Prevent empty diff output
            raise ValueError(f"Empty diff report for changed file: {filepath}")  # Report invalid diff state

        atomic_write_text(cleaned_srt_filepath, cleaned_content)  # Write cleaned SRT beside source
        atomic_write_text(diff_filepath, diff_content)  # Write diff report beside source

        if log_output:  # Preserve direct-call output logs outside progress-bar mode
            output_label = "Updated in place" if IN_PLACE_UPDATE else "Cleaned"  # Describe how cleaned subtitle content was published
            print(f"{output_label}: {display_relative_path(cleaned_srt_filepath, input_dir)}")  # Log cleaned output destination
            print(f"Diff: {display_relative_path(diff_filepath, input_dir)}")  # Log diff output
        return 1, 0, 0, removed_count + len(empty_block_repairs), modified_count  # Return cleaned counts including malformed empty-block removals
    except Exception as exc:  # Report file-specific failure and continue
        failure_message = f"{BackgroundColors.RED}Failed: {BackgroundColors.CYAN}{relative_path}{BackgroundColors.RED} - {exc}{Style.RESET_ALL}"  # Build concise failure log
        if log_output:  # Use normal output outside progress-bar mode
            print(failure_message)  # Log failure directly
        else:  # Keep tqdm progress display intact while surfacing the error
            tqdm.write(failure_message, file=PROGRESS_OUTPUT)  # Print above the active progress bar and redraw it without routing carriage returns through Logger
        return 0, 0, 1, 0, 0  # Return failure count


def main():
    """
    Main function.

    :param: None
    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Main Template Python{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the welcome message
    
    start_time = datetime.datetime.now()  # Get the start time of the program
    
    discovered_count = 0  # Count discovered SRT files across all input directories
    cleaned_count = 0  # Count files with generated outputs
    unchanged_count = 0  # Count files without SDH content
    failed_count = 0  # Count files that failed processing
    removed_entries_count = 0  # Count removed subtitle entries
    modified_entries_count = 0  # Count mixed entries modified

    for configured_input_dir in INPUT_DIRS:  # Process every configured input directory
        input_dir = Path(resolve_full_trailing_space_path(str(configured_input_dir))).resolve()  # Resolve configured input path safely

        if not verify_filepath_exists(str(input_dir)) or not input_dir.is_dir():  # Validate current input directory
            print(f"{BackgroundColors.RED}Input directory not found: {BackgroundColors.CYAN}{input_dir}{Style.RESET_ALL}")  # Log missing input directory
            continue  # Continue with remaining configured input directories

        srt_files = discover_srt_files(input_dir)  # Discover source SRT files recursively in current input directory
        discovered_count += len(srt_files)  # Add current directory discovery count
        directory_display = display_input_directory(input_dir)  # Build Unix-like directory label for progress output

        with tqdm(
            srt_files,
            total=len(srt_files),
            file=PROGRESS_OUTPUT,
            desc=f"{BackgroundColors.GREEN}Processing {BackgroundColors.CYAN}{directory_display}{Style.RESET_ALL}",
            unit="file",
            dynamic_ncols=True,
            leave=True,
            colour="green",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {postfix}",
        ) as progress_bar:  # Create exactly one in-place progress bar for the current input directory
            for srt_file in progress_bar:  # Process every source SRT file while reusing the same progress line
                relative_path = display_relative_path(srt_file, input_dir)  # Build current file path for progress display
                progress_bar.set_postfix_str(f"{BackgroundColors.GREEN}File: {BackgroundColors.CYAN}{relative_path}{Style.RESET_ALL}", refresh=True)  # Show current file without creating a new progress bar
                file_cleaned, file_unchanged, file_failed, file_removed, file_modified = process_srt_file(srt_file, input_dir, log_output=False)  # Process one source file without per-file scrolling logs
                cleaned_count += file_cleaned  # Add cleaned file count
                unchanged_count += file_unchanged  # Add unchanged file count
                failed_count += file_failed  # Add failed file count
                removed_entries_count += file_removed  # Add removed entry count
                modified_entries_count += file_modified  # Add modified entry count

    print(
        f"{BackgroundColors.GREEN}Summary:{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}SRT files discovered: {BackgroundColors.CYAN}{discovered_count}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Files cleaned: {BackgroundColors.CYAN}{cleaned_count}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Files unchanged: {BackgroundColors.CYAN}{unchanged_count}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Files failed: {BackgroundColors.CYAN}{failed_count}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Subtitle entries removed: {BackgroundColors.CYAN}{removed_entries_count}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Mixed entries modified: {BackgroundColors.CYAN}{modified_entries_count}{Style.RESET_ALL}"
    )  # Output final processing summary

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
