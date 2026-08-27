"""
================================================================================
Non-English Dual Audio Default Movies Report
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-10
Description :
    This script analyzes movie directories under one or more configured library
    roots and reports
    movies whose actual default audio track is not identified as English.
    It reads media metadata through FFprobe, resolves language values through
    LANGUAGES_MAPPING, and preserves uncertain default-audio language cases.

    Key features include:
        - Movie directory discovery under multiple configured input directories
        - Deterministic video file selection without treating .srt files as movies
        - Default audio stream detection from media container metadata
        - Language identification using media metadata and LANGUAGES_MAPPING
        - Movie metadata, audio tracks, internal subtitles, and external .srt subtitles
        - Structured JSON report generation in the script Reports directory

Usage:
    1. Set INPUT_DIRS to the movie-library root directories.
    2. Ensure FFprobe is installed and available through the system PATH.
    3. Run the script via terminal:
        $ make run   or   $ python main.py

Outputs:
    - Non-English Dual Audio Default Movies Report/Reports/<input-dir-prefix>-non_english_default_audio_movies.json

TODOs:
    - Add CLI arguments for input and report paths if needed.

Dependencies:
    - Python
    - FFprobe
    - colorama

Assumptions & Notes:
    - Movie directories and media files may appear at any nested level under each INPUT_DIRS entry.
    - Movie directory names follow MovieName Year Resolution Language.
    - Unknown default-audio language metadata is recorded separately from the
      primary non-English report list.
"""

import atexit  # For playing a sound when the program finishes
import datetime  # For getting the current date and time
import json  # For reading FFprobe metadata and writing JSON reports
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For parsing movie directory names
import shutil  # For locating FFprobe
import subprocess  # For running FFprobe
import sys  # For system-specific parameters and functions
from colorama import Style  # For coloring the terminal
from pathlib import Path  # For handling file paths
from typing import Any  # For typing FFprobe JSON data


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
INPUT_DIRS = [f"E:/Movies/", f"F:/Documentaries/", f"F:/Movies/", f"F:/Series/", f"G:/Animes/", f"G:/Series/"]  # Set the movie library root directories
SCRIPT_DIRECTORY = Path(__file__).resolve().parent  # Resolve the executing file directory
REPORTS_DIRECTORY = SCRIPT_DIRECTORY / "Reports"  # Set the script report directory
SUPPORTED_VIDEO_EXTENSIONS = (".mkv", ".mp4", ".avi", ".mov")  # Define supported video file extensions
IGNORED_FILENAME_KEYWORDS = ("nacional", "dublado")  # Ignore video filenames containing any of these case-insensitive keywords.
IGNORE_SINGLE_NON_ENGLISH_AUDIO_TRACK = True  # Ignore report entries when a file has exactly one audio track and that track is confidently non-English.
LANGUAGES_MAPPING = {  # Map display languages to known metadata aliases
    "English": ["english", "eng", "en", "Inglês"],  # Map English aliases
    "Brazilian Portuguese": ["PT-BR FULL", "brazilian", "portuguese", "COMPLETA PT-BR", "PT-BR COMPLETA", "Português (Brasil)", "pt-br", "pt"],  # Map Brazilian Portuguese aliases
}  # Close the language mapping

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


def validate_ffprobe_available() -> None:
    """
    Validate that FFprobe is available through the system PATH.

    :return: None.
    """

    if shutil.which("ffprobe") is None:  # Detect missing FFprobe executable.
        raise RuntimeError("Required executable not found in PATH: ffprobe.")  # Stop execution with a clear dependency error.


def build_report_prefix(input_dir: str) -> str:
    """
    Build a filesystem-safe report prefix from one configured input directory.

    :param input_dir: Configured input directory path.
    :return: Report filename prefix derived from the input directory.
    """

    cleaned_input_dir = input_dir.strip()  # Remove accidental surrounding whitespace from the configured input directory
    sanitized_prefix = re.sub(r"[\\/]+", "-", cleaned_input_dir)  # Replace any slash direction with the required dash separator
    sanitized_prefix = sanitized_prefix.replace(":", "")  # Remove Windows drive separators so the prefix remains a valid filename
    sanitized_prefix = re.sub(r"-+", "-", sanitized_prefix).strip("-")  # Collapse repeated dashes and trim any leading or trailing separator
    return sanitized_prefix or "report"  # Return the safe prefix or a deterministic fallback when the input directory is unexpectedly empty


def build_report_path(input_dir: str) -> Path:
    """
    Build the JSON report path for one configured input directory.

    :param input_dir: Configured input directory path.
    :return: Report path using the sanitized input-directory prefix.
    """

    return REPORTS_DIRECTORY / f"{build_report_prefix(input_dir)}-non_english_default_audio_movies.json"  # Return the per-input report path


def to_unix_path(path_value: str | Path) -> str:
    """
    Convert one filesystem path to a forward-slash string.

    :param path_value: Path-like value converted for JSON output.
    :return: Path string using only forward slashes.
    """

    return str(path_value).replace("\\", "/")  # Normalize Windows separators for report output.


def parse_movie_directory_name(directory_name: str) -> dict[str, str]:
    """
    Parse movie name, year, and resolution from one directory name.

    :param directory_name: Movie directory name using MovieName Year Resolution Language format.
    :return: Parsed movie metadata.
    """

    match = re.match(r"^(?P<MovieName>.+)\s+(?P<Year>(?:19|20)\d{2})\s+(?P<Resolution>\d{3,4}p|[48]k)\b", directory_name, re.IGNORECASE)  # Parse the final movie metadata tokens.

    if match is None:  # Detect directory names outside the expected pattern.
        return {"MovieName": directory_name, "Year": "", "Resolution": ""}  # Preserve the directory name when parsing is unavailable.

    return {  # Return normalized parsed fields.
        "MovieName": match.group("MovieName").strip(),  # Preserve title numbers before the year token.
        "Year": match.group("Year").strip(),  # Preserve the parsed release year.
        "Resolution": match.group("Resolution").strip(),  # Preserve the parsed resolution value.
    }  # Close the parsed metadata mapping.


def discover_movie_files(input_directory: Path) -> list[Path]:
    """
    Discover supported video files recursively under one input directory.

    :param input_directory: Configured movie-library root directory.
    :return: Ordered video file list.
    """

    return sorted(  # Return every supported video file discovered below the configured input directory.
        (
            candidate
            for candidate in input_directory.rglob("*")
            if candidate.is_file()
            and candidate.suffix.casefold() in SUPPORTED_VIDEO_EXTENSIONS
            and not any(keyword in candidate.name.casefold() for keyword in IGNORED_FILENAME_KEYWORDS)
        ),  # Keep only supported video files discovered recursively whose filenames do not contain ignored keywords.
        key=lambda candidate: str(candidate.relative_to(input_directory)).casefold(),  # Sort files by case-insensitive relative path for deterministic report generation.
    )  # Close the recursive video-file collection.


def run_ffprobe_metadata(movie_file: Path) -> dict[str, Any]:
    """
    Read media format and stream metadata from one movie file.

    :param movie_file: Movie file inspected by FFprobe.
    :return: Parsed FFprobe metadata.
    """

    command = [  # Build the FFprobe JSON metadata command.
        "ffprobe",  # Select the FFprobe executable.
        "-v",  # Configure FFprobe output verbosity.
        "error",  # Emit errors only.
        "-show_format",  # Include container format metadata.
        "-show_streams",  # Include stream metadata.
        "-of",  # Configure output format.
        "json",  # Emit structured JSON.
        str(movie_file),  # Pass the movie file path.
    ]  # Close the FFprobe command vector.

    try:  # Run FFprobe and capture the JSON output.
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)  # Execute FFprobe with deterministic text decoding.
    except subprocess.CalledProcessError as error:  # Convert FFprobe failures into runtime errors.
        details = error.stderr.strip() or "No FFprobe error output was provided."  # Preserve FFprobe diagnostic text.
        raise RuntimeError(f"FFprobe failed for {movie_file}: {details}") from error  # Raise a contextual metadata error.
    except OSError as error:  # Convert executable launch failures into runtime errors.
        raise RuntimeError(f"FFprobe could not be started for {movie_file}: {error}") from error  # Raise a contextual launch error.

    try:  # Parse FFprobe JSON output.
        metadata = json.loads(result.stdout)  # Decode FFprobe JSON metadata.
    except json.JSONDecodeError as error:  # Convert malformed JSON into runtime errors.
        raise RuntimeError(f"FFprobe returned invalid JSON for {movie_file}.") from error  # Raise a contextual JSON error.

    if not isinstance(metadata, dict):  # Detect an invalid top-level FFprobe shape.
        raise RuntimeError(f"FFprobe returned unexpected metadata for {movie_file}.")  # Reject malformed FFprobe metadata.

    return metadata  # Return parsed metadata.


def format_duration(duration_value: Any) -> str:
    """
    Format a media duration value as HH:MM:SS.

    :param duration_value: Raw FFprobe duration value.
    :return: Duration formatted as HH:MM:SS.
    """

    try:  # Convert FFprobe duration seconds to a float.
        total_seconds = int(round(float(duration_value)))  # Round duration to the nearest full second.
    except (TypeError, ValueError):  # Handle missing or malformed durations.
        total_seconds = 0  # Use a deterministic zero duration for missing metadata.

    hours = total_seconds // 3600  # Calculate full hours.
    minutes = (total_seconds % 3600) // 60  # Calculate remaining minutes.
    seconds = total_seconds % 60  # Calculate remaining seconds.

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"  # Return HH:MM:SS duration text.


def get_stream_tags(stream: dict[str, Any]) -> dict[str, str]:
    """
    Extract string metadata tags from one FFprobe stream.

    :param stream: FFprobe stream metadata.
    :return: Stream tag mapping with string keys and values.
    """

    tags_value = stream.get("tags", {})  # Read optional stream tags.

    if not isinstance(tags_value, dict):  # Detect absent or malformed tag metadata.
        return {}  # Return an empty tag mapping.

    return {str(key): str(value) for key, value in tags_value.items()}  # Return normalized string tags.


def get_streams_by_type(metadata: dict[str, Any], codec_type: str) -> list[dict[str, Any]]:
    """
    Return streams matching one FFprobe codec type.

    :param metadata: Parsed FFprobe metadata.
    :param codec_type: FFprobe stream codec type.
    :return: Ordered stream metadata list.
    """

    streams_value = metadata.get("streams", [])  # Read the FFprobe stream list.

    if not isinstance(streams_value, list):  # Detect malformed stream metadata.
        return []  # Return an empty stream list.

    return [stream for stream in streams_value if isinstance(stream, dict) and stream.get("codec_type") == codec_type]  # Return streams with the requested codec type.


def find_default_audio_stream(audio_streams: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Find the audio stream used as the default stream.

    :param audio_streams: Audio streams returned by FFprobe.
    :return: Default audio stream metadata when available.
    """

    for audio_stream in audio_streams:  # Inspect audio streams in FFprobe order.
        disposition = audio_stream.get("disposition", {})  # Read stream disposition metadata.

        if isinstance(disposition, dict) and disposition.get("default") == 1:  # Detect the container default flag.
            return audio_stream  # Return the explicitly marked default audio stream.

    if audio_streams:  # Detect media files where no explicit default flag exists.
        return audio_streams[0]  # Use FFprobe order as the deterministic default fallback.

    return None  # Return no default when no audio streams exist.


def identify_language(stream: dict[str, Any]) -> str:
    """
    Identify a stream language from metadata and configured aliases.

    :param stream: FFprobe stream metadata.
    :return: Language display name or Unknown.
    """

    tags = get_stream_tags(stream)  # Read stream tag metadata.
    language = tags.get("language", "").strip()  # Read language tag metadata.
    title = tags.get("title", "").strip()  # Read title metadata.
    normalized_language = language.casefold()  # Normalize language metadata for matching.
    normalized_title = title.casefold()  # Normalize title metadata for matching.
    title_tokens = set(re.split(r"[^0-9a-zA-ZÀ-ÿ]+", normalized_title))  # Split title metadata into searchable tokens.

    for display_name, aliases in LANGUAGES_MAPPING.items():  # Compare every configured language alias.
        for alias in aliases:  # Compare every alias for this display language.
            normalized_alias = alias.casefold()  # Normalize the alias for case-insensitive matching.

            if normalized_alias == normalized_language:  # Match exact language tag metadata.
                return display_name  # Return the configured language display name.

            if normalized_alias in title_tokens or (len(normalized_alias) > 2 and normalized_alias in normalized_title):  # Match title metadata safely.
                return display_name  # Return the configured language display name.

    if language and language.casefold() not in {"und", "unknown"}:  # Preserve defined non-English language tags.
        return language  # Return the raw language tag when no configured alias matched.

    return "Unknown"  # Return a deterministic unknown language value.


def format_audio_track(stream: dict[str, Any], default_audio_stream: dict[str, Any] | None) -> str:
    """
    Format one audio stream for the JSON report.

    :param stream: FFprobe audio stream metadata.
    :param default_audio_stream: Default audio stream metadata.
    :return: Human-readable audio track text.
    """

    tags = get_stream_tags(stream)  # Read audio metadata tags.
    language = identify_language(stream)  # Identify the audio language.
    raw_language = tags.get("language", "").strip()  # Read the raw language tag.
    title = tags.get("title", "").strip()  # Read the audio title metadata.
    parts = [language]  # Start the audio display with the identified language.

    if raw_language and raw_language.casefold() != language.casefold():  # Detect a distinct raw language tag.
        parts.append(f"({raw_language})")  # Add the raw language tag.

    if title and title.casefold() not in {language.casefold(), raw_language.casefold()}:  # Detect useful title metadata.
        parts.append(f"- {title}")  # Add the track title.

    track_text = " ".join(parts).strip()  # Build the audio track text.

    if default_audio_stream is stream:  # Detect the selected default audio stream.
        track_text = f"{track_text} (Default)"  # Mark only the default stream.

    return track_text  # Return formatted audio track text.


def format_subtitle_track(stream: dict[str, Any]) -> str:
    """
    Format one internal subtitle stream for the JSON report.

    :param stream: FFprobe subtitle stream metadata.
    :return: Human-readable internal subtitle text.
    """

    tags = get_stream_tags(stream)  # Read subtitle metadata tags.
    language = tags.get("language", "").strip()  # Read subtitle language metadata.
    title = tags.get("title", "").strip()  # Read subtitle title metadata.
    codec = str(stream.get("codec_name") or "").strip()  # Read subtitle codec metadata.
    parts = ["Internal:"]  # Start the internal subtitle display marker.

    if language:  # Detect subtitle language metadata.
        parts.append(language)  # Add subtitle language metadata.

    if codec:  # Detect subtitle codec metadata.
        parts.append(f"({codec})")  # Add subtitle codec metadata.

    if title:  # Detect subtitle title metadata.
        parts.append(f"- {title}")  # Add subtitle title metadata.

    return " ".join(parts).strip()  # Return formatted internal subtitle text.


def find_external_subtitles(movie_file: Path) -> list[str]:
    """
    Find external SRT subtitle files associated with one video file.

    :param movie_file: Video file inspected for matching sidecar subtitles.
    :return: Ordered external subtitle track text list.
    """

    base_stem = movie_file.stem.casefold()  # Normalize the current video filename stem for sidecar matching.
    subtitle_files = sorted(  # Collect matching external SRT files deterministically.
        (
            candidate
            for candidate in movie_file.parent.iterdir()
            if candidate.is_file()
            and candidate.suffix.casefold() == ".srt"
            and (
                candidate.stem.casefold() == base_stem
                or candidate.stem.casefold().startswith(f"{base_stem}.")
                or candidate.stem.casefold().startswith(f"{base_stem} ")
            )
        ),  # Keep only SRT sidecar files that belong to this specific video file.
        key=lambda candidate: candidate.name.casefold(),  # Sort subtitle filenames case-insensitively.
    )  # Close the external subtitle collection.

    return [f"External: {subtitle_file.name}" for subtitle_file in subtitle_files]  # Return formatted external subtitle entries.


def build_movie_report_entry(movie_file: Path, metadata: dict[str, Any]) -> dict[str, Any]:
    """
    Build one movie report entry from one video file and media metadata.

    :param movie_file: Video file path.
    :param metadata: Parsed FFprobe metadata.
    :return: Structured movie report entry.
    """

    movie_directory = movie_file.parent  # Resolve the parent directory used for path-derived metadata.
    parsed_name = parse_movie_directory_name(movie_directory.name)  # Parse movie naming metadata.
    format_metadata = metadata.get("format", {})  # Read container format metadata.
    duration_value = format_metadata.get("duration") if isinstance(format_metadata, dict) else None  # Read duration metadata when available.
    audio_streams = get_streams_by_type(metadata, "audio")  # Read audio stream metadata.
    subtitle_streams = get_streams_by_type(metadata, "subtitle")  # Read internal subtitle stream metadata.
    default_audio_stream = find_default_audio_stream(audio_streams)  # Resolve the default audio stream.
    internal_subtitles = [format_subtitle_track(stream) for stream in subtitle_streams]  # Format internal subtitle streams.
    external_subtitles = find_external_subtitles(movie_file)  # Format external SRT subtitles associated with this video file.

    return {  # Return the structured movie entry.
        "MovieName": parsed_name["MovieName"],  # Include parsed movie name.
        "Year": parsed_name["Year"],  # Include parsed movie year.
        "Resolution": parsed_name["Resolution"],  # Include parsed movie resolution.
        "VideoFile": movie_file.name,  # Include the processed video filename so multi-file directories remain distinguishable.
        "FullPath": to_unix_path(movie_file),  # Include the full normalized video path immediately after the filename.
        "Length": format_duration(duration_value),  # Include HH:MM:SS duration.
        "AudioTracks": [format_audio_track(stream, default_audio_stream) for stream in audio_streams],  # Include every audio track.
        "SubtitleTracks": internal_subtitles + external_subtitles,  # Include internal and external subtitles.
    }  # Close the movie report entry.


def generate_report(input_dir: str) -> Path:
    """
    Generate the non-English default audio movie JSON report for one input directory.

    :param input_dir: Configured movie-library root directory.
    :return: Written report path.
    """

    validate_ffprobe_available()  # Validate FFprobe availability.
    input_directory = Path(input_dir)  # Build the input directory path.

    if not input_directory.exists():  # Detect a missing input directory.
        raise FileNotFoundError(f"Input directory not found: {input_directory}")  # Stop execution when the movie root is absent.

    movie_files = discover_movie_files(input_directory)  # Collect video files recursively so every nested media file is processed individually.
    reported_movies = []  # Store movies with non-English default audio.
    unknown_default_audio_language = []  # Store movies with unresolved default audio language.

    for movie_file in movie_files:  # Process each discovered video file independently.
        try:  # Read metadata for this movie.
            metadata = run_ffprobe_metadata(movie_file)  # Extract FFprobe metadata.
            audio_streams = get_streams_by_type(metadata, "audio")  # Read audio stream metadata.
            default_audio_stream = find_default_audio_stream(audio_streams)  # Resolve default audio stream metadata.
            default_language = identify_language(default_audio_stream) if default_audio_stream is not None else "Unknown"  # Identify default audio language.
            movie_entry = build_movie_report_entry(movie_file, metadata)  # Build the movie report entry.
        except Exception as error:  # Preserve processing failures without aborting the full report.
            print(f"{BackgroundColors.RED}[WARNING] Failed to process {movie_file}: {error}{Style.RESET_ALL}")  # Report the failed video file.
            continue  # Continue with the next movie directory.

        if default_language == "English":  # Exclude confident English default audio.
            continue  # Continue with the next movie directory.

        if IGNORE_SINGLE_NON_ENGLISH_AUDIO_TRACK and len(audio_streams) == 1 and default_language not in {"English", "Unknown"}:  # Skip files that only provide one confidently non-English audio option when configured.
            continue  # Continue with the next movie directory.

        if default_language == "Unknown":  # Preserve unresolved language metadata separately.
            unknown_default_audio_language.append(movie_entry)  # Add movie to the unknown-language collection.
            continue  # Continue with the next movie directory.

        reported_movies.append(movie_entry)  # Add movie to the non-English report collection.

    reported_movies.sort(key=lambda movie: str(movie["MovieName"]).casefold())  # Sort reported movies by name.
    unknown_default_audio_language.sort(key=lambda movie: str(movie["MovieName"]).casefold())  # Sort unknown-language movies by name.
    report_data = {  # Build the structured report payload for the current input directory
        "InputDir": to_unix_path(input_directory),  # Record the processed input directory represented by this report using normalized separators
        f"Movies ({len(reported_movies)})": reported_movies,  # Store movies whose default audio is confidently non-English and expose the count in the JSON section name
        "UnknownDefaultAudioLanguage": unknown_default_audio_language,  # Store movies whose default audio language could not be resolved
    }  # Close the structured report payload
    REPORTS_DIRECTORY.mkdir(parents=True, exist_ok=True)  # Create the script Reports directory when needed.
    report_file = build_report_path(to_unix_path(input_directory))  # Build the current input directory report path
    report_file.write_text(json.dumps(report_data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")  # Write human-readable JSON.

    return report_file  # Return the written report path.


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
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Non-English Dual Audio Default Movies Report{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the welcome message
    
    start_time = datetime.datetime.now()  # Get the start time of the program
    
    validate_ffprobe_available()  # Validate FFprobe once before processing all configured input directories

    report_files = []  # Store the written report path for each configured input directory
    for input_dir in INPUT_DIRS:  # Process every configured movie-library root independently
        report_file = generate_report(input_dir)  # Generate the non-English default audio report for the current input directory
        report_files.append(report_file)  # Store the generated report path for summary output
        print(f"{BackgroundColors.GREEN}Report saved for {BackgroundColors.CYAN}{input_dir}{BackgroundColors.GREEN}: {BackgroundColors.CYAN}{report_file}{Style.RESET_ALL}")  # Output the current report path

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
