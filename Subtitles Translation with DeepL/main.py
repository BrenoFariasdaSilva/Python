"""
================================================================================
Subtitle (SRT) Translation using DeepL API
================================================================================
Author      : Breno Farias da Silva
Created     : 2025-12-13
Description :
   This script translates subtitle files (SRT) from any DeepL-detected source language to Brazilian Portuguese
   using the DeepL API. It processes all .srt files in the specified input directory,
   respecting API usage limits, and saves the translated files with a '_ptBR' suffix.

   Key features include:
      - Automatic loading of SRT files from a directory
      - Integration with DeepL API for translation
      - Respect for API free plan usage limits
      - Logging output to both terminal and file
      - Optional notification sound upon completion

Usage:
   1. Configure the INPUT_DIRECTORY and ensure DEEPL_API_KEYS is set in the .env file.
   2. Execute the script using Python:
      $ python <script_name>.py
   3. Translated SRT files are saved in the same directory with '_ptBR' appended.

Outputs:
   - Translated SRT files in the input directory, e.g., 01_ptBR.srt
   - Log file for script execution, e.g., Logs/translate_srt.log

TODOs:
   - Implement CLI argument parsing for input/output directories
   - Add support for batch translation with subdirectories
   - Improve handling of very large SRT files to avoid API limit issues
   - Extend support for additional languages

Dependencies:
   - Python >= 3.12
   - deepl
   - lingua-language-detector
   - python-dotenv
   - colorama
   - Logger (custom logging module)
   - pathlib
   - datetime
   - atexit
   - os
   - sys
   - platform

Assumptions & Notes:
   - All input files must have a .srt extension
   - Input directory must exist and contain valid SRT files
   - DeepL API keys must be set in a .env file as DEEPL_API_KEYS
   - Platform-specific notes: notification sound may be disabled on Windows
"""

import atexit  # For playing a sound when the program finishes
import datetime  # For getting the current date and time
import deepl  # For DeepL API
import hashlib  # For fingerprinting resumable translation state
import json  # For parsing DeepL API accounts from environment variables
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For recognizing SDH subtitle cue wrappers
import sys  # For system-specific parameters and functions
import time  # For monotonic progress and ETA timing
from colorama import Style  # For coloring the terminal
from dotenv import load_dotenv  # For loading environment variables from .env file
from lingua import LanguageDetectorBuilder  # For offline language detection before translation
from Logger import Logger  # For logging output to both terminal and file
from pathlib import Path  # For handling file paths
from shutil import copyfile  # For copying files
from typing import Any, Callable, Dict, List, Tuple  # For typed account, retry, progress, and subtitle structures


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
DESCRIPTIVE_SUBTITLES_REMOVAL = (
    True  # Set to True to remove descriptive lines (e.g., [music], (laughs)) from SRT before translation
)
DEEPL_API_KEYS = {}  # DeepL API accounts (will be loaded in load_dotenv function)
INPUT_DIRECTORY = f"D:/Sem Backup/Download/Torrent/Completed/Subs/"  # Directory containing the input SRT files
OUTPUT_DIR = Path("./Output")  # Base output directory
TARGET_LANG = "PT-BR"  # DeepL target language code
SCRIPT_DIR = Path(__file__).resolve().parent  # Directory containing this script
LANGUAGE_DETECTION_MIN_LETTERS = 80  # Avoid classifying tiny or numeric-only subtitles
LANGUAGE_DETECTION_MAX_SAMPLE_CHARS = 4000  # Enough dialogue for detection without scanning huge files
TARGET_LANGUAGE_MIN_CONFIDENCE = 0.75  # Require strong target-language confidence before skipping
TARGET_LANGUAGE_MIN_MARGIN = 0.20  # Require target language to clearly beat the next candidate
TARGET_LANGUAGE_MIN_SHARE = 0.80  # Require target language to dominate mixed-language content
SUBTITLE_FORMATTING_TAG_PATTERN = re.compile(r"</?(?:i|b|u|font)(?:\s+[^<>]*)?>", re.IGNORECASE)  # Recognized SRT formatting tags
LANGUAGE_DETECTOR = None  # Lazily initialized offline language detector
TRANSLATION_RESUME_STATE_VERSION = 1  # Version for persistent resumable translation metadata
DEEPL_TRANSIENT_RETRY_DELAYS_SECONDS = (300, 600)  # Wait five minutes, then ten minutes after the SDK exhausts its own transient retries.

# Logger Setup:
logger = Logger(str(SCRIPT_DIR / "Logs" / f"{Path(__file__).stem}.log"), clean=True)  # Create a Logger instance
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


def ensure_env_file():
    """
    Ensures that a .env file exists. If not, creates it by copying .env-example
    and clears the DEEPL_API_KEYS value, prompting the user to fill it.

    :return: True if .env already existed, False if it was created.
    """

    if os.path.exists(".env"):  # Check if .env file exists
        return True  # .env exists

    copyfile(".env-example", ".env")  # Copy .env-example to .env

    with open(".env", "r") as f:  # Open .env file for reading
        lines = f.readlines()  # Read all lines

    with open(".env", "w") as f:  # Open .env file for writing
        for line in lines:  # Iterate through each line
            if line.startswith("DEEPL_API_KEYS="):  # If the line contains the DEEPL_API_KEYS
                f.write("DEEPL_API_KEYS=\n")  # Clear the DEEPL_API_KEYS value
            else:  # If the line does not contain the DEEPL_API_KEYS
                f.write(line)  # Write the line as is

    return False  # .env was created


def parse_deepl_api_keys(raw_value: str) -> Dict[str, str]:
    """
    Parses named DeepL API keys from a JSON object string.

    :param raw_value: Environment variable value containing account names and keys.
    :return: Ordered mapping of DeepL account names to API keys.
    """

    try:
        api_keys = json.loads(raw_value)  # Parse account mapping from JSON
    except json.JSONDecodeError as e:
        raise ValueError(f"DEEPL_API_KEYS must be valid JSON: {e.msg}") from None

    if not isinstance(api_keys, dict):  # Require JSON object for deterministic account order
        raise ValueError("DEEPL_API_KEYS must be a JSON object mapping account names to API keys")

    if not api_keys:  # Require at least one account
        raise ValueError("DEEPL_API_KEYS must contain at least one account")

    for account_name, api_key in api_keys.items():  # Validate every account without exposing keys
        if not isinstance(account_name, str) or not account_name.strip():
            raise ValueError("DEEPL_API_KEYS account names must be non-empty strings")
        if not isinstance(api_key, str) or not api_key.strip():
            raise ValueError(f"DEEPL_API_KEYS account '{account_name}' must have a non-empty string API key")

    return api_keys  # Return validated ordered mapping


def get_api_keys() -> bool:
    """
    Loads environment variables from a .env file and retrieves the DeepL API keys.

    :return: True if DeepL API keys were loaded successfully, otherwise False
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Loading environment variables from {BackgroundColors.CYAN}.env{BackgroundColors.GREEN} file...{Style.RESET_ALL}"
    )  # Output the verbose message

    global DEEPL_API_KEYS  # Use the global DEEPL_API_KEYS variable

    load_dotenv()  # Load environment variables from .env file
    raw_api_keys = os.getenv("DEEPL_API_KEYS")  # Get DeepL API keys from environment variables

    if not raw_api_keys:  # If the DeepL API keys are not found
        return False  # Return False

    try:
        DEEPL_API_KEYS = parse_deepl_api_keys(raw_api_keys)  # Store validated DeepL API accounts
    except ValueError as e:
        print(f"{BackgroundColors.RED}Configuration error: {e}{Style.RESET_ALL}")
        return False  # Return False

    return True  # Return True


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


def resolve_from_script_dir(path) -> Path:
    """
    Resolves a configured path relative to the directory containing this script.

    :param path: Configured path value.
    :return: Absolute resolved path.
    """

    configured_path = Path(path).expanduser()  # Normalize configured path type and expand user home
    if not configured_path.is_absolute():  # Resolve relative config from script directory
        configured_path = SCRIPT_DIR / configured_path

    return configured_path.resolve()  # Return absolute normalized path


def is_path_inside(path: Path, parent: Path) -> bool:
    """
    Determines whether a path is the same as or inside a parent directory.

    :param path: Path to test.
    :param parent: Parent directory.
    :return: True if path is parent or descendant, otherwise False.
    """

    try:
        path.relative_to(parent)  # Succeeds for parent itself and descendants
        return True
    except ValueError:
        return False


def read_srt(file_path):
    """
    Reads the SRT file into a list of lines.

    :param file_path: Path to the SRT file
    :return: List of strings representing each line
    """

    verbose_output(f"Reading SRT file from: {file_path}")  # Output the verbose message

    with open(file_path, "r", encoding="utf-8") as f:  # Open the SRT file for reading
        return f.readlines()  # Read all lines and return as a list


def discover_srt_files(input_dir: Path) -> List[Path]:
    """
    Recursively discovers SRT files under an input directory.

    :param input_dir: Resolved input directory.
    :return: Sorted SRT file paths.
    """

    try:
        return sorted(path for path in input_dir.rglob("*") if path.is_file() and path.suffix.lower() == ".srt")  # Snapshot every SRT recursively
    except OSError as e:
        print(f"{BackgroundColors.RED}Failed to discover SRT files in {BackgroundColors.CYAN}{input_dir}{BackgroundColors.RED}: {e}{Style.RESET_ALL}")  # Log filesystem failure
        return []  # Keep caller behavior simple after explicit error


def parse_srt_blocks(lines: List[str]) -> List[Tuple[str, str, List[str]]]:
    """
    Parses SRT lines into index, timing, and text-line blocks.

    :param lines: SRT lines to parse.
    :return: List of parsed SRT blocks.
    """

    blocks = []  # Store parsed subtitle blocks
    block = []  # Store current subtitle block
    pending_empty_block = None  # Hold index/timing when text appears after extra blank lines

    for line in lines + [""]:  # Add sentinel blank line to flush final block
        stripped = line.strip().lstrip("\ufeff")  # Normalize current line and ignore UTF-8 BOM
        if stripped:
            block.append(stripped)  # Add non-empty line to current block
            continue

        if not block:
            continue

        if len(block) < 2 or not block[0].isdigit() or "-->" not in block[1]:  # Reject malformed SRT block
            if pending_empty_block:
                index, timing = pending_empty_block  # Recover text split from its timing by extra blank lines
                blocks.append((index, timing, [text_line.strip() for text_line in block if text_line.strip()]))  # Store recovered block text
                pending_empty_block = None  # Clear recovered pending block
                block = []  # Reset current subtitle block
                continue
            if blocks:
                blocks[-1][2].extend(text_line.strip() for text_line in block if text_line.strip())  # Recover orphan text split by extra blank lines
                block = []  # Reset current subtitle block
                continue
            return []  # Return empty result for malformed subtitles

        text_lines = [text_line.strip() for text_line in block[2:] if text_line.strip()]  # Normalize translatable text lines
        if pending_empty_block:
            index, timing = pending_empty_block  # Restore earlier empty timed cue before current valid block
            blocks.append((index, timing, []))  # Preserve empty cue structure
            pending_empty_block = None  # Clear restored pending block
        if not text_lines:
            pending_empty_block = (block[0], block[1])  # Wait for possible text split by extra blank lines
            block = []  # Reset current subtitle block
            continue
        blocks.append((block[0], block[1], text_lines))  # Store parsed block
        block = []  # Reset current subtitle block

    if pending_empty_block:
        index, timing = pending_empty_block  # Restore trailing empty timed cue
        blocks.append((index, timing, []))  # Preserve empty cue structure

    return blocks  # Return parsed subtitle blocks


def has_valid_srt_structure(lines: List[str]) -> bool:
    """
    Determines whether SRT lines are empty or structurally parseable.

    :param lines: SRT lines to validate.
    :return: True when empty or valid, otherwise False.
    """

    return not lines or bool(parse_srt_blocks(lines))  # Preserve empty-file handling while rejecting malformed content


def strip_html_tags(text: str) -> str:
    """
    Removes supported SRT formatting tags from text.

    :param text: Text that may contain formatting tags.
    :return: Text without supported SRT formatting tags.
    """

    return SUBTITLE_FORMATTING_TAG_PATTERN.sub("", text)  # Remove recognized formatting tags only


def is_descriptive_cue(text: str) -> bool:
    """
    Determines whether text is only an SDH or descriptive cue.

    :param text: Subtitle text to classify.
    :return: True if text is only descriptive, otherwise False.
    """

    normalized = strip_html_tags(text).strip()  # Remove tags before classification
    normalized = normalized.strip("[](){}").strip()  # Remove cue wrappers
    normalized = normalized.strip("♪♫♬♩?!.- ").strip()  # Remove cue punctuation and music symbols
    cue_text = normalized.lower()  # Normalize cue text

    if not cue_text:
        return True  # Empty cue text is non-dialogue

    cue_words = re.findall(r"[a-z]+", cue_text)  # Extract cue words only

    if not cue_words:
        return True  # Music symbols or punctuation only are non-dialogue

    descriptive_words = {
        "applause", "audience", "beeping", "bell", "breathing", "cheering", "chuckles", "closes",
        "coughing", "crying", "door", "footsteps", "gasps", "groaning", "indistinctly", "instrumental",
        "laugh", "laughing", "laughs", "music", "phone", "playing", "ringing", "sighs", "singing",
        "speaking", "thunder", "whispering", "whispers",
    }  # Conservative SDH cue vocabulary

    return all(word in descriptive_words for word in cue_words)  # Avoid removing dialogue with one cue-like word


def clean_subtitle_text_line(text_line: str) -> Tuple[str, bool]:
    """
    Removes isolated SDH cues from one subtitle text line.

    :param text_line: Subtitle text line to clean.
    :return: Tuple containing cleaned subtitle text line and whether content changed.
    """

    stripped = text_line.strip()  # Normalize current text line
    tagless = strip_html_tags(stripped).strip()  # Remove supported tags before cleanup and classification
    formatting_changed = tagless != stripped  # Track formatting-tag removal as cleanup

    if (
        (tagless.startswith("[") and tagless.endswith("]"))
        or (tagless.startswith("(") and tagless.endswith(")"))
        or (tagless.startswith("♪") and tagless.endswith("♪"))
        or (tagless.startswith("♫") and tagless.endswith("♫"))
        or (tagless.startswith("♬") and tagless.endswith("♬"))
        or (tagless.startswith("♩") and tagless.endswith("♩"))
    ) and is_descriptive_cue(tagless):
        return "", True  # Drop whole-line descriptive cue

    cleaned = re.sub(
        r"(\[[^\]]+\]|\([^)]+\)|[♪♫♬♩][^♪♫♬♩]+[♪♫♬♩])",
        lambda match: "" if is_descriptive_cue(match.group(0)) else match.group(0),
        tagless,
    )  # Remove inline descriptive cue spans only

    cleaned = " ".join(cleaned.split())  # Normalize spacing after cue removal

    return cleaned, formatting_changed or cleaned != stripped  # Return cleaned text and change flag


def serialize_srt_blocks(blocks: List[Tuple[str, str, List[str]]]) -> List[str]:
    """
    Serializes parsed SRT blocks back into lines.

    :param blocks: Parsed subtitle blocks.
    :return: Serialized SRT lines.
    """

    lines = []  # Store serialized lines

    for new_index, (_index, timing, text_lines) in enumerate(blocks, start=1):  # Serialize each subtitle block
        lines.extend([str(new_index), timing])  # Add sequential index and timing lines
        lines.extend(text_lines)  # Add subtitle text lines
        lines.append("")  # Add SRT block separator

    return lines  # Return serialized SRT lines


def count_translatable_characters(lines: List[str]) -> int:
    """
    Counts characters that will be sent to DeepL.

    :param lines: Cleaned SRT lines.
    :return: Total translatable character count.
    """

    return sum(len(text_block) for text_block in build_translation_text_blocks(lines))  # Match translation block counting


def build_translation_text_blocks(lines: List[str]) -> List[str]:
    """
    Builds exact text blocks sent to DeepL.

    :param lines: Cleaned SRT lines.
    :return: Text blocks sent to DeepL.
    """

    return ["\n".join(text_lines) for _, _, text_lines in parse_srt_blocks(lines)]  # Reuse parsed subtitle blocks


def normalize_language_code(language_code: str) -> str:
    """
    Normalizes a language code to the ISO 639-1 base code used by language detection.

    :param language_code: Language code such as PT-BR, PT, EN-US, or EN.
    :return: Uppercase base language code.
    """

    return language_code.replace("_", "-").upper().split("-")[0]  # Lingua detects language, not regional variant


def get_language_display_name(language_code: str) -> str:
    """
    Converts a base language code to a concise display name.

    :param language_code: Base language code.
    :return: Human-readable language label.
    """

    language_names = {
        "EN": "English",
        "PT": "Portuguese",
    }  # Names needed by current source/target configuration

    return language_names.get(language_code, language_code)  # Fall back to code for unmapped languages


def count_letters(text: str) -> int:
    """
    Counts Unicode letters in text.

    :param text: Text to inspect.
    :return: Number of alphabetic characters.
    """

    return sum(1 for character in text if character.isalpha())  # Ignore numbers and punctuation for reliability checks


def build_language_detection_sample(lines: List[str]) -> str:
    """
    Builds a language-detection sample from cleaned subtitle dialogue only.

    :param lines: Cleaned SRT lines.
    :return: Dialogue text sample for offline language detection.
    """

    sample_lines = []  # Store cleaned dialogue lines used for language detection
    seen_lines = {}  # Limit repeated lines so names or repeated short cues do not dominate
    sample_length = 0  # Track sample size without repeatedly joining text

    for _, _, text_lines in parse_srt_blocks(lines):  # Use parsed subtitle text only
        for text_line in text_lines:  # Inspect each cleaned dialogue line
            dialogue_line = strip_html_tags(text_line).strip()  # Ignore formatting tags for detection only
            dialogue_line = re.sub(r"^[A-Z][A-Z0-9 .'-]{1,30}:\s*", "", dialogue_line).strip()  # Remove speaker label prefix for detection
            if count_letters(dialogue_line) < 3:  # Ignore numeric, punctuation-only, or tiny fragments
                continue

            line_key = dialogue_line.lower()  # Normalize repeated dialogue for sampling
            if seen_lines.get(line_key, 0) >= 3:  # Avoid repeated names or phrases dominating detection
                continue

            seen_lines[line_key] = seen_lines.get(line_key, 0) + 1  # Count accepted repeated line
            sample_lines.append(dialogue_line)  # Add dialogue-only text
            sample_length += len(dialogue_line) + 1  # Track approximate joined length
            if sample_length >= LANGUAGE_DETECTION_MAX_SAMPLE_CHARS:
                return "\n".join(sample_lines)[:LANGUAGE_DETECTION_MAX_SAMPLE_CHARS]  # Return bounded sample

    return "\n".join(sample_lines)  # Return complete bounded sample


def get_language_detector():
    """
    Returns the shared offline language detector.

    :return: Lingua language detector.
    """

    global LANGUAGE_DETECTOR  # Reuse detector and loaded models across files

    if LANGUAGE_DETECTOR is None:
        LANGUAGE_DETECTOR = LanguageDetectorBuilder.from_all_languages().build()  # Build offline detector without DeepL quota

    return LANGUAGE_DETECTOR  # Return shared detector


def calculate_language_share(detector, sample: str, target_code: str) -> float:
    """
    Estimates whether target language dominates mixed-language content.

    :param detector: Lingua language detector.
    :param sample: Cleaned dialogue sample.
    :param target_code: Normalized target language code.
    :return: Character share detected as target language.
    """

    detected_sections = detector.detect_multiple_languages_of(sample)  # Segment mixed-language sample conservatively
    if not detected_sections:
        return 0.0

    target_characters = 0  # Count detected target-language section characters
    detected_characters = 0  # Count all detected section characters

    for section in detected_sections:  # Iterate detected contiguous language sections
        section_length = section.end_index - section.start_index  # Calculate section length in sample text
        detected_characters += section_length  # Track detected content length
        detected_code = section.language.iso_code_639_1.name  # Read detector's base language code
        if detected_code == target_code:
            target_characters += section_length  # Track target-language content length

    return target_characters / detected_characters if detected_characters else 0.0  # Return target dominance ratio


def detect_cleaned_subtitle_language(lines: List[str], target_language_code: str) -> Tuple[bool, bool, str]:
    """
    Detects whether cleaned subtitle dialogue is already in the target language.

    :param lines: Cleaned SRT lines.
    :param target_language_code: Configured DeepL target language code.
    :return: Tuple of target-language match, conclusive detection, and detected language label.
    """

    sample = build_language_detection_sample(lines)  # Build sample only from cleaned dialogue
    if count_letters(sample) < LANGUAGE_DETECTION_MIN_LETTERS:
        return False, False, ""  # Avoid classifying tiny, numeric-only, or ambiguous subtitles

    target_code = normalize_language_code(target_language_code)  # Lingua returns base language codes only
    detector = get_language_detector()  # Initialize offline detector before any DeepL call
    confidence_values = detector.compute_language_confidence_values(sample)  # Score likely languages locally
    if not confidence_values:
        return False, False, ""  # Unknown detection result

    top_confidence = confidence_values[0]  # Most likely detected language
    detected_code = top_confidence.language.iso_code_639_1.name  # Base language code from detector
    detected_label = f"{get_language_display_name(detected_code)} ({detected_code})"  # Label for logs
    second_confidence = confidence_values[1].value if len(confidence_values) > 1 else 0.0  # Compare against next candidate
    target_confidence = next((value.value for value in confidence_values if value.language.iso_code_639_1.name == target_code), 0.0)  # Find target score
    target_share = calculate_language_share(detector, sample, target_code)  # Guard mixed-language subtitles

    if (
        detected_code == target_code
        and target_confidence >= TARGET_LANGUAGE_MIN_CONFIDENCE
        and target_confidence - second_confidence >= TARGET_LANGUAGE_MIN_MARGIN
        and target_share >= TARGET_LANGUAGE_MIN_SHARE
    ):
        return True, True, detected_label  # Target language dominates cleaned dialogue

    if top_confidence.value < 0.55 or top_confidence.value - second_confidence < 0.15:
        return False, False, detected_label  # Ambiguous detection should continue to translation

    return False, True, detected_label  # Conclusive non-target detection


def clean_descriptive_subtitle_lines(lines: List[str]) -> Tuple[List[str], int, int]:
    """
    Removes descriptive cues from SRT lines without writing files.

    :param lines: Source SRT lines.
    :return: Tuple containing cleaned lines, removed entry count, and mixed cleaned entry count.
    """

    blocks = parse_srt_blocks(lines)  # Parse source before cue removal

    if not blocks:
        return lines, 0, 0  # Preserve malformed input behavior

    cleaned_blocks = []  # Store cleaned subtitle blocks
    removed_entry_count = 0  # Count blocks removed entirely by cleanup
    mixed_cleaned_entry_count = 0  # Count kept blocks whose text changed

    for index, timing, text_lines in blocks:  # Clean each parsed subtitle block
        cleaned_line_results = [clean_subtitle_text_line(text_line) for text_line in text_lines]  # Remove SDH cue spans
        cleaned_text_lines = [text_line for text_line, _ in cleaned_line_results]  # Extract cleaned text
        cleaned_text_lines = [text_line for text_line in cleaned_text_lines if text_line]  # Drop empty cleaned lines
        if cleaned_text_lines:
            cleaned_blocks.append((index, timing, cleaned_text_lines))  # Keep blocks with dialogue
            if any(changed for _, changed in cleaned_line_results):  # Detect mixed cue cleanup
                mixed_cleaned_entry_count += 1  # Count kept changed block
        else:
            removed_entry_count += 1  # Count removed SDH-only block

    cleaned_lines = serialize_srt_blocks(cleaned_blocks)  # Serialize cleaned SRT blocks
    return cleaned_lines, removed_entry_count, mixed_cleaned_entry_count  # Return cleaned lines and cleanup counts


def remove_descriptive_subtitles(file_path) -> Tuple[List[str], int, int]:
    """
    Removes descriptive cues from parsed SRT subtitle entries.
    Overwrites the original SRT file with cleaned lines.
    These cleaned lines are used for translation.

    :param file_path: Path to the SRT file
    :return: Tuple containing cleaned lines, removed entry count, and mixed cleaned entry count.
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Removing descriptive subtitles from: {BackgroundColors.CYAN}{file_path}{Style.RESET_ALL}"
    )  # Verbose message

    original_lines = read_srt(file_path)  # Read source SRT lines
    cleaned_lines, removed_entry_count, mixed_cleaned_entry_count = clean_descriptive_subtitle_lines(original_lines)  # Clean without duplicating rules
    if cleaned_lines and not parse_srt_blocks(cleaned_lines):  # Validate serialized cleaned subtitles before replacing
        print(f"{BackgroundColors.YELLOW}SDH cleanup failed structural validation. Original subtitle will be translated:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{file_path}{Style.RESET_ALL}")  # Preserve source on cleanup failure
        return original_lines, 0, 0  # Fallback to original valid source lines

    write_srt_lines_atomic(Path(file_path), cleaned_lines)  # Replace source file after successful write

    return cleaned_lines, removed_entry_count, mixed_cleaned_entry_count  # Return cleaned lines and cleanup counts


def write_srt_lines_atomic(file_path: Path, lines: List[str]) -> None:
    """
    Writes SRT lines through a same-folder temporary file.

    :param file_path: Destination SRT file.
    :param lines: SRT lines to write.
    :return: None
    """

    temp_file = Path(file_path).with_suffix(Path(file_path).suffix + ".tmp")  # Build same-folder temp file
    temp_file.write_text("\n".join(lines), encoding="utf-8")  # Write cleaned subtitles atomically
    os.replace(temp_file, file_path)  # Replace destination after successful write


def serialize_srt_blocks_preserving_indices(blocks: List[Tuple[str, str, List[str]]]) -> List[str]:
    """
    Serializes SRT blocks while preserving their existing indices and timings.

    :param blocks: Parsed subtitle blocks.
    :return: Serialized SRT lines with original indices and timings.
    """

    lines = []  # Store serialized subtitle lines.

    for index, timing, text_lines in blocks:  # Serialize every complete subtitle block.
        lines.extend([index, timing])  # Preserve the source index and timing lines.
        lines.extend(text_lines)  # Append translated or structural subtitle text lines.
        lines.append("")  # Terminate the subtitle block at a safe SRT boundary.

    return lines  # Return structurally complete serialized subtitle blocks.


def build_srt_blocks_fingerprint(blocks: List[Tuple[str, str, List[str]]]) -> str:
    """
    Builds a deterministic fingerprint for ordered SRT block structure and text.

    :param blocks: Parsed subtitle blocks.
    :return: SHA-256 fingerprint for the ordered subtitle blocks.
    """

    payload = json.dumps([[index, timing, text_lines] for index, timing, text_lines in blocks], ensure_ascii=False, separators=(",", ":"))  # Serialize ordered block data deterministically.
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()  # Return the deterministic subtitle fingerprint.


def get_translation_resume_state_file(output_file: Path) -> Path:
    """
    Resolves the persistent resume metadata file for a translated output.

    :param output_file: Translated output SRT path.
    :return: Resume metadata file path.
    """

    return output_file.with_suffix(output_file.suffix + ".resume.json")  # Keep resume metadata beside the translated output.


def get_in_place_resume_backup_file(output_file: Path) -> Path:
    """
    Resolves the protected source backup used for resumable in-place translation.

    :param output_file: In-place translated output SRT path.
    :return: Protected source backup SRT path.
    """

    return output_file.with_name(f"{output_file.stem}.resume.backup.srt")  # Use an internal backup filename excluded from source discovery.


def write_translation_resume_state_atomic(state_file: Path, state: Dict[str, Any]) -> None:
    """
    Writes translation resume metadata through a same-folder atomic replacement.

    :param state_file: Resume metadata file path.
    :param state: Resume metadata payload.
    :return: None.
    """

    temp_file = state_file.with_suffix(state_file.suffix + ".tmp")  # Build a same-folder temporary metadata path.
    temp_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")  # Persist complete resume metadata before replacement.
    os.replace(temp_file, state_file)  # Atomically replace the previous resume metadata.


def read_translation_resume_state(state_file: Path) -> Dict[str, Any] | None:
    """
    Reads persistent translation resume metadata when it is valid JSON data.

    :param state_file: Resume metadata file path.
    :return: Resume metadata mapping, or None when unavailable or malformed.
    """

    if not state_file.exists():  # Return no state when the metadata file is absent.
        return None  # Signal that no persistent resume metadata exists.

    try:  # Read and parse persistent resume metadata safely.
        state = json.loads(state_file.read_text(encoding="utf-8"))  # Parse the atomic JSON resume metadata.
    except Exception:  # Treat unreadable or malformed metadata as unusable.
        return None  # Preserve source and output data when resume metadata cannot be trusted.

    return state if isinstance(state, dict) else None  # Accept only mapping-shaped resume metadata.


def create_translation_resume_state(source_lines: List[str], output_file: Path, in_place_output: bool) -> Dict[str, Any]:
    """
    Creates persistent resume metadata for the exact preprocessed source representation.

    :param source_lines: Exact preprocessed source SRT lines used for translation.
    :param output_file: Translated output SRT path.
    :param in_place_output: Whether source and translated output share the same path.
    :return: Newly persisted resume metadata mapping.
    """

    source_blocks = parse_srt_blocks(source_lines)  # Parse the exact source representation used for DeepL requests.
    state_file = get_translation_resume_state_file(output_file)  # Resolve persistent resume metadata beside the output.
    state = {"version": TRANSLATION_RESUME_STATE_VERSION, "target_lang": TARGET_LANG.upper(), "source_fingerprint": build_srt_blocks_fingerprint(source_blocks), "source_block_count": len(source_blocks), "completed_blocks": 0, "completed_characters": 0, "completed_output_fingerprint": build_srt_blocks_fingerprint([]), "pending_block": None, "final_output_fingerprint": "", "in_place_output": in_place_output}  # Store source identity and crash-journal state without duplicating completed subtitle content.
    write_translation_resume_state_atomic(state_file, state)  # Persist source identity before the first DeepL request.
    return state  # Return the persisted resume metadata for the active translation session.


def build_translation_resume_info(source_lines: List[str], output_file: Path) -> Dict[str, Any]:
    """
    Validates persistent resume metadata and translated output against the current source.

    :param source_lines: Exact preprocessed source SRT lines used for translation.
    :param output_file: Translated output SRT path.
    :return: Resume validation data describing safely reusable translated progress.
    """

    source_blocks = parse_srt_blocks(source_lines)  # Parse the current exact translation source representation.
    state_file = get_translation_resume_state_file(output_file)  # Resolve persistent resume metadata for this output.
    result = {"valid": False, "reason": "No resume metadata exists.", "state_file": state_file, "state": None, "output_blocks": [], "completed_blocks": 0, "completed_characters": 0, "effective_blocks": 0, "effective_characters": 0, "pending_block": None, "pending_persisted": False, "final_output_ready": False}  # Initialize conservative resume validation data.

    if not state_file.exists():  # Stop when no persistent resume session exists.
        return result  # Return the conservative no-resume result.

    state = read_translation_resume_state(state_file)  # Read persistent source identity and progress journal.
    if state is None:  # Reject malformed or unreadable resume metadata.
        result["reason"] = "Resume metadata is unreadable or malformed."  # Record the conservative rejection reason.
        return result  # Avoid trusting any partial output without valid metadata.

    result["state"] = state  # Preserve validated JSON data for later session preparation.

    if state.get("version") != TRANSLATION_RESUME_STATE_VERSION:  # Require the exact supported state format.
        result["reason"] = "Resume metadata version is unsupported."  # Record version incompatibility.
        return result  # Avoid interpreting unknown persistent state.
    if state.get("target_lang") != TARGET_LANG.upper():  # Require the same configured DeepL target language.
        result["reason"] = "Resume metadata target language differs from the current configuration."  # Record target-language incompatibility.
        return result  # Prevent reusing translation progress for another target language.
    if not source_blocks or state.get("source_block_count") != len(source_blocks):  # Require identical source block cardinality.
        result["reason"] = "Current source block structure differs from the resumable source."  # Record source structure incompatibility.
        return result  # Avoid skipping content after structural source changes.

    source_fingerprint = build_srt_blocks_fingerprint(source_blocks)  # Fingerprint the exact current preprocessed source.
    if state.get("source_fingerprint") != source_fingerprint:  # Require source text, indices, timings, and order to remain unchanged.
        result["reason"] = "Current source content differs from the resumable source."  # Record exact source identity mismatch.
        return result  # Prevent stale translated content from being reused for changed source text.

    output_lines = []  # Default to no persisted translated SRT blocks.
    if output_file.exists() and output_file.stat().st_size > 0:  # Read an existing non-empty translated output when present.
        try:  # Read the current translated output safely.
            output_lines = output_file.read_text(encoding="utf-8").splitlines()  # Load persisted output lines for structural validation.
        except Exception:  # Reject unreadable output while preserving all files.
            result["reason"] = "Translated output is unreadable."  # Record output read failure.
            return result  # Avoid skipping any source content from unreadable output.

    output_blocks = parse_srt_blocks(output_lines) if output_lines else []  # Parse only complete structurally valid output blocks.
    if output_lines and not output_blocks:  # Reject malformed non-empty translated output.
        result["reason"] = "Translated output is malformed."  # Record malformed partial output.
        return result  # Avoid trusting an ambiguous SRT boundary.

    final_output_fingerprint = state.get("final_output_fingerprint", "")  # Read a journaled finalized-output fingerprint when available.
    if final_output_fingerprint and output_blocks and build_srt_blocks_fingerprint(output_blocks) == final_output_fingerprint:  # Recognize cleanup already persisted before metadata removal.
        total_characters = sum(len("\n".join(text_lines)) for _, _, text_lines in source_blocks)  # Count all previously translated source characters.
        result.update({"valid": True, "reason": "Final translated output is already persisted.", "output_blocks": output_blocks, "completed_blocks": len(source_blocks), "completed_characters": total_characters, "effective_blocks": len(source_blocks), "effective_characters": total_characters, "final_output_ready": True})  # Mark final output as complete without another DeepL request.
        return result  # Return finalized crash-recovery state.

    completed_blocks = state.get("completed_blocks")  # Read committed safely persisted block count.
    completed_characters = state.get("completed_characters")  # Read committed source character count.
    if not isinstance(completed_blocks, int) or completed_blocks < 0 or completed_blocks > len(source_blocks):  # Require a possible committed prefix length.
        result["reason"] = "Resume metadata contains an impossible completed block count."  # Record impossible progression.
        return result  # Avoid skipping any source content from inconsistent metadata.
    if not isinstance(completed_characters, int) or completed_characters < 0:  # Require a valid committed character total.
        result["reason"] = "Resume metadata contains an invalid completed character count."  # Record invalid character progression.
        return result  # Avoid trusting inconsistent progress totals.

    expected_completed_characters = sum(len("\n".join(text_lines)) for _, _, text_lines in source_blocks[:completed_blocks])  # Recalculate committed characters from the current source prefix.
    if completed_characters != expected_completed_characters:  # Require mathematically exact committed character totals.
        result["reason"] = "Resume metadata character totals do not match the current source prefix."  # Record arithmetic inconsistency.
        return result  # Prevent incorrect progress or quota planning.

    in_place_output = bool(state.get("in_place_output"))  # Read whether this session replaces a misleading generated filename in place.
    pending_block = state.get("pending_block")  # Read a translated block journaled before SRT persistence.
    if in_place_output and completed_blocks == 0 and pending_block is None and output_blocks and build_srt_blocks_fingerprint(output_blocks) == source_fingerprint:  # Recognize an in-place session that crashed before its first translated block.
        output_blocks = []  # Treat the still-intact source path as zero translated output progress.

    if len(output_blocks) < completed_blocks:  # Require every committed block to remain present in the output.
        result["reason"] = "Translated output is shorter than the committed resume progression."  # Record missing persisted translation data.
        return result  # Avoid reconstructing completed translations that are no longer available.

    for position in range(completed_blocks):  # Validate structural correspondence for every committed output block.
        source_block = source_blocks[position]  # Read the matching current source block.
        output_block = output_blocks[position]  # Read the persisted translated block.
        if source_block[0] != output_block[0] or source_block[1] != output_block[1]:  # Require exact index and timing correspondence.
            result["reason"] = "Translated output index or timing differs from the current source prefix."  # Record structural incompatibility.
            return result  # Prevent unsafe skipping when ordering or timing changed.

    completed_output_fingerprint = state.get("completed_output_fingerprint")  # Read the committed translated prefix fingerprint.
    if not isinstance(completed_output_fingerprint, str) or build_srt_blocks_fingerprint(output_blocks[:completed_blocks]) != completed_output_fingerprint:  # Require persisted translated prefix content to remain unchanged.
        result["reason"] = "Translated output content differs from the committed resume prefix."  # Record translated-prefix mutation.
        return result  # Avoid trusting altered or unrelated generated content.

    effective_blocks = completed_blocks  # Start reusable progress at the committed SRT prefix.
    effective_characters = completed_characters  # Start reusable character progress at the committed prefix total.
    pending_persisted = False  # Default to no journaled block already present in the output.

    if pending_block is not None:  # Validate a DeepL result journaled before or during output persistence.
        if not isinstance(pending_block, dict):  # Require mapping-shaped pending journal data.
            result["reason"] = "Pending resume metadata is malformed."  # Record malformed pending journal data.
            return result  # Avoid interpreting ambiguous pending progress.

        position = pending_block.get("position")  # Read the pending source block position.
        translated_lines = pending_block.get("translated_lines")  # Read the journaled DeepL translation lines.
        if not isinstance(position, int) or position != completed_blocks or position >= len(source_blocks):  # Require the exact next source block.
            result["reason"] = "Pending resume metadata has impossible ordering."  # Record impossible pending progression.
            return result  # Prevent skipping non-prefix source content.
        if not isinstance(translated_lines, list) or any(not isinstance(line, str) for line in translated_lines):  # Require complete translated text lines.
            result["reason"] = "Pending resume metadata contains invalid translated text."  # Record invalid journaled translation payload.
            return result  # Avoid persisting malformed translated content.

        source_block = source_blocks[position]  # Read the exact source block represented by the pending translation.
        source_block_fingerprint = build_srt_blocks_fingerprint([source_block])  # Fingerprint the current pending source block.
        if pending_block.get("source_fingerprint") != source_block_fingerprint:  # Require pending translation to belong to the unchanged source block.
            result["reason"] = "Pending resume metadata belongs to different source content."  # Record pending source mismatch.
            return result  # Prevent stale pending translation from being reused.

        pending_characters = len("\n".join(source_block[2]))  # Recalculate source characters represented by the pending DeepL result.
        if pending_block.get("characters") != pending_characters:  # Require exact pending character accounting.
            result["reason"] = "Pending resume character totals are inconsistent."  # Record pending arithmetic mismatch.
            return result  # Prevent incorrect remaining-character planning.

        pending_output_block = (source_block[0], source_block[1], translated_lines)  # Reconstruct the complete SRT block from journaled DeepL output.
        pending_output_fingerprint = build_srt_blocks_fingerprint([pending_output_block])  # Fingerprint the journaled translated block.
        if pending_block.get("output_fingerprint") != pending_output_fingerprint:  # Require pending translated content to remain intact.
            result["reason"] = "Pending translated content differs from its persisted fingerprint."  # Record pending output mutation.
            return result  # Avoid persisting altered journal content.

        if len(output_blocks) == completed_blocks:  # Pending block was journaled but not yet atomically written to the SRT.
            pending_persisted = False  # Mark that restart must persist the journaled block before another DeepL request.
        elif len(output_blocks) == completed_blocks + 1:  # Pending block may already be present after a crash before metadata commit.
            output_pending_block = output_blocks[position]  # Read the possible already-persisted pending output block.
            if source_block[0] != output_pending_block[0] or source_block[1] != output_pending_block[1] or build_srt_blocks_fingerprint([output_pending_block]) != pending_output_fingerprint:  # Require exact structural and translated-content equality.
                result["reason"] = "Pending translated block does not match the persisted SRT progression."  # Record pending persistence mismatch.
                return result  # Avoid advancing beyond an ambiguous output boundary.
            pending_persisted = True  # Mark that only metadata commit remains for this translated block.
        else:  # Reject extra output beyond the single crash-journaled block.
            result["reason"] = "Translated output extends beyond the safely journaled progression."  # Record impossible output progression.
            return result  # Avoid trusting unproven translated content.

        effective_blocks += 1  # Count the journaled DeepL result as reusable translated work.
        effective_characters += pending_characters  # Exclude journaled characters from future DeepL quota planning.
    elif len(output_blocks) != completed_blocks:  # Require exact output length when no pending translation journal exists.
        result["reason"] = "Translated output contains uncommitted blocks without a pending journal."  # Record unproven translated progression.
        return result  # Avoid skipping any unjournaled output content.

    result.update({"valid": True, "reason": "Resume metadata and translated prefix are valid.", "output_blocks": output_blocks, "completed_blocks": completed_blocks, "completed_characters": completed_characters, "effective_blocks": effective_blocks, "effective_characters": effective_characters, "pending_block": pending_block, "pending_persisted": pending_persisted})  # Return safely reusable prefix and journaled progress.
    return result  # Return validated resumable translation state.


def reconcile_translation_resume_state(source_lines: List[str], output_file: Path, resume_info: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Tuple[str, str, List[str]]]]:
    """
    Reconciles a valid pending translation journal with the persistent output SRT.

    :param source_lines: Exact preprocessed source SRT lines used for translation.
    :param output_file: Translated output SRT path.
    :param resume_info: Validated resume information for this source and output.
    :return: Updated resume metadata and safely persisted translated output blocks.
    """

    if not resume_info.get("valid") or not isinstance(resume_info.get("state"), dict):  # Require previously validated resume data.
        raise RuntimeError("Resume state cannot be reconciled because validation did not succeed.")  # Reject unsafe resume preparation.

    state = dict(resume_info["state"])  # Copy validated persistent state for deterministic updates.
    output_blocks = list(resume_info.get("output_blocks", []))  # Start from the structurally validated persisted prefix.
    pending_block = resume_info.get("pending_block")  # Read a DeepL result journaled across the previous interruption.
    state_file = get_translation_resume_state_file(output_file)  # Resolve persistent metadata path once.

    if pending_block is None:  # Return immediately when no journaled result needs reconciliation.
        return state, output_blocks  # Preserve the already committed translated prefix.

    source_blocks = parse_srt_blocks(source_lines)  # Parse exact source blocks for pending reconstruction.
    position = pending_block["position"]  # Read validated pending block position.
    source_block = source_blocks[position]  # Read the validated matching source block.
    pending_output_block = (source_block[0], source_block[1], list(pending_block["translated_lines"]))  # Reconstruct the complete journaled translated block.

    if not resume_info.get("pending_persisted"):  # Persist the journaled DeepL result when the prior run stopped before output replacement.
        candidate_blocks = output_blocks + [pending_output_block]  # Build the next structurally complete translated prefix.
        candidate_lines = serialize_srt_blocks_preserving_indices(candidate_blocks)  # Serialize only complete SRT blocks.
        if len(parse_srt_blocks(candidate_lines)) != len(candidate_blocks):  # Require the journaled translation to serialize as complete SRT structure.
            raise RuntimeError("Journaled translated block cannot be persisted as a structurally complete SRT prefix.")  # Preserve the journal instead of consuming more quota.
        write_srt_lines_atomic(output_file, candidate_lines)  # Atomically persist the previously returned DeepL translation.
        output_blocks = candidate_blocks  # Advance in-memory output only after atomic SRT persistence.

    state["completed_blocks"] = position + 1  # Commit the journaled block after output persistence is confirmed.
    state["completed_characters"] = sum(len("\n".join(text_lines)) for _, _, text_lines in source_blocks[: position + 1])  # Recalculate exact committed source characters.
    state["completed_output_fingerprint"] = build_srt_blocks_fingerprint(output_blocks[: position + 1])  # Fingerprint the committed translated prefix.
    state["pending_block"] = None  # Clear the crash journal only after its translated block is safely persisted.
    write_translation_resume_state_atomic(state_file, state)  # Atomically commit reconciled resume progress.
    return state, output_blocks  # Return committed state and translated output prefix.


def persist_translated_srt_block(source_blocks: List[Tuple[str, str, List[str]]], output_blocks: List[Tuple[str, str, List[str]]], block_position: int, translated_lines: List[str], output_file: Path, resume_state: Dict[str, Any]) -> Tuple[List[Tuple[str, str, List[str]]], Dict[str, Any]]:
    """
    Journals and atomically persists one successfully translated complete SRT block.

    :param source_blocks: Exact parsed source SRT blocks.
    :param output_blocks: Safely persisted translated output prefix.
    :param block_position: Zero-based source block position being persisted.
    :param translated_lines: DeepL-returned translated text lines for this block.
    :param output_file: Translated output SRT path.
    :param resume_state: Active persistent resume metadata.
    :return: Updated translated output blocks and resume metadata.
    """

    if block_position != len(output_blocks):  # Require strict prefix progression without gaps or reordering.
        raise RuntimeError("Translated block persistence attempted an invalid SRT progression.")  # Reject ambiguous output ordering.

    source_block = source_blocks[block_position]  # Read the exact source block represented by this DeepL result.
    source_characters = len("\n".join(source_block[2]))  # Count exact source characters billed for the translation unit.
    output_block = (source_block[0], source_block[1], translated_lines)  # Preserve source index and timing around translated text.
    pending_block = {"position": block_position, "source_fingerprint": build_srt_blocks_fingerprint([source_block]), "characters": source_characters, "translated_lines": translated_lines, "output_fingerprint": build_srt_blocks_fingerprint([output_block])}  # Journal returned translation content before SRT persistence.
    state_file = get_translation_resume_state_file(output_file)  # Resolve persistent metadata path for this output.
    resume_state["pending_block"] = pending_block  # Record the returned DeepL block before touching the output SRT.
    write_translation_resume_state_atomic(state_file, resume_state)  # Atomically persist the returned translation crash journal.

    candidate_blocks = output_blocks + [output_block]  # Build the next complete translated SRT prefix.
    candidate_lines = serialize_srt_blocks_preserving_indices(candidate_blocks)  # Serialize only complete SRT blocks at a safe boundary.
    parsed_candidate_blocks = parse_srt_blocks(candidate_lines)  # Parse the candidate prefix before persistent replacement.
    if len(parsed_candidate_blocks) != len(candidate_blocks):  # Require the translated block to remain structurally unambiguous.
        raise RuntimeError("DeepL returned text that cannot be persisted as a structurally complete SRT block.")  # Preserve the pending journal without falsely advancing progress.
    for source_candidate, output_candidate in zip(source_blocks[: len(parsed_candidate_blocks)], parsed_candidate_blocks):  # Verify every persisted block remains aligned with the source progression.
        if source_candidate[0] != output_candidate[0] or source_candidate[1] != output_candidate[1]:  # Require source index and timing correspondence after serialization.
            raise RuntimeError("Translated SRT prefix lost source index or timing correspondence during persistence.")  # Preserve the pending journal instead of writing ambiguous progress.

    write_srt_lines_atomic(output_file, candidate_lines)  # Atomically persist the complete translated prefix including the new successful block.
    output_blocks = candidate_blocks  # Advance in-memory translated output only after atomic persistence succeeds.
    resume_state["completed_blocks"] = block_position + 1  # Commit the newly persisted translated block count.
    resume_state["completed_characters"] = sum(len("\n".join(text_lines)) for _, _, text_lines in source_blocks[: block_position + 1])  # Recalculate exact committed source characters.
    resume_state["completed_output_fingerprint"] = build_srt_blocks_fingerprint(output_blocks)  # Fingerprint the complete committed translated prefix.
    resume_state["pending_block"] = None  # Clear the journal only after successful output persistence.
    write_translation_resume_state_atomic(state_file, resume_state)  # Atomically commit the translated progression metadata.
    return output_blocks, resume_state  # Return safely persisted output and committed resume metadata.


def prepare_translation_resume_session(source_lines: List[str], source_path: Path, source_storage_path: Path, output_file: Path, resume_info: Dict[str, Any]) -> Tuple[Dict[str, Any], List[Tuple[str, str, List[str]]]]:
    """
    Prepares protected source storage and persistent state before translation continues.

    :param source_lines: Exact preprocessed source SRT lines used for translation.
    :param source_path: Logical source SRT path used by existing output rules.
    :param source_storage_path: Physical file containing the preserved source representation.
    :param output_file: Translated output SRT path.
    :param resume_info: Preflight resume validation data.
    :return: Active resume metadata and safely persisted translated output blocks.
    """

    in_place_output = output_file == source_path  # Identify generated-looking sources that must be replaced in place.
    if in_place_output and source_storage_path == source_path:  # Protect the exact source before the first partial in-place output replacement.
        backup_file = get_in_place_resume_backup_file(output_file)  # Resolve the internal protected source backup path.
        write_srt_lines_atomic(backup_file, source_lines)  # Atomically preserve the exact preprocessed source for future restart validation.

    if resume_info.get("valid") and isinstance(resume_info.get("state"), dict):  # Reuse only source-validated persistent resume state.
        return reconcile_translation_resume_state(source_lines, output_file, resume_info)  # Persist any journaled prior DeepL result before new quota is consumed.

    resume_state = create_translation_resume_state(source_lines, output_file, in_place_output)  # Persist exact source identity before the first new DeepL request.
    return resume_state, []  # Start a fresh translation prefix without trusting existing invalid output content.


def mark_translation_final_output(output_file: Path, resume_state: Dict[str, Any], final_lines: List[str]) -> None:
    """
    Journals the expected final translated output before final atomic cleanup replacement.

    :param output_file: Translated output SRT path.
    :param resume_state: Active persistent resume metadata.
    :param final_lines: Structurally validated final output SRT lines.
    :return: None.
    """

    final_blocks = parse_srt_blocks(final_lines)  # Parse structurally validated final output lines.
    resume_state["final_output_fingerprint"] = build_srt_blocks_fingerprint(final_blocks)  # Journal final output identity before any cleanup replacement.
    write_translation_resume_state_atomic(get_translation_resume_state_file(output_file), resume_state)  # Persist finalization recovery metadata atomically.


def remove_translation_resume_artifacts(output_file: Path, resume_state: Dict[str, Any]) -> None:
    """
    Removes completed resume metadata and the protected in-place source backup.

    :param output_file: Completed translated output SRT path.
    :param resume_state: Completed persistent resume metadata.
    :return: None.
    """

    state_file = get_translation_resume_state_file(output_file)  # Resolve completed resume metadata path.
    if state_file.exists():  # Remove metadata only after final translated output persistence succeeds.
        state_file.unlink()  # Delete completed resume metadata so normal complete-output skipping resumes.

    if resume_state.get("in_place_output"):  # Remove protected source backup only for completed in-place translation.
        backup_file = get_in_place_resume_backup_file(output_file)  # Resolve internal protected source backup path.
        if backup_file.exists():  # Remove backup only after resume metadata is no longer needed.
            backup_file.unlink()  # Delete protected source backup after successful finalization.


def is_interactive_output() -> bool:
    """
    Determines whether terminal output supports in-place progress updates.

    :return: True when stdout is interactive, otherwise False.
    """

    return bool(getattr(logger, "is_tty", False))  # Reuse logger's original stdout TTY detection


def format_duration(total_seconds: float) -> str:
    """
    Formats a duration for progress ETA and execution time.

    :param total_seconds: Duration in seconds.
    :return: Human-readable duration.
    """

    total_seconds = max(0, int(total_seconds))  # Avoid negative or fractional display noise
    days, remainder = divmod(total_seconds, 86400)  # Split long durations into days and clock time
    hours, remainder = divmod(remainder, 3600)  # Calculate hours
    minutes, seconds = divmod(remainder, 60)  # Calculate minutes and seconds

    if days:
        return f"{days}d {hours:02d}:{minutes:02d}:{seconds:02d}"  # Include days for long runs

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"  # Return clock-style duration


def format_eta(done_characters: int, total_characters: int, start_time_monotonic: float) -> str:
    """
    Formats ETA from completed characters and monotonic elapsed time.

    :param done_characters: Completed translated characters.
    :param total_characters: Total planned characters.
    :param start_time_monotonic: Monotonic start time.
    :return: Formatted ETA text.
    """

    if done_characters <= 0 or total_characters <= done_characters:
        return "calculating..." if done_characters <= 0 and total_characters > 0 else "00:00:00"  # Avoid fake early ETA

    elapsed_seconds = time.monotonic() - start_time_monotonic  # Use monotonic elapsed time
    if elapsed_seconds <= 0:
        return "calculating..."  # Avoid division by zero

    characters_per_second = done_characters / elapsed_seconds  # Average throughput smooths block-level jitter
    if characters_per_second <= 0:
        return "calculating..."  # Guard impossible rates

    return format_duration((total_characters - done_characters) / characters_per_second)  # Return remaining duration


def build_progress_bar(done_characters: int, total_characters: int, width: int = 20) -> str:
    """
    Builds a bounded text progress bar.

    :param done_characters: Completed characters.
    :param total_characters: Total characters.
    :param width: Bar width.
    :return: Text progress bar.
    """

    ratio = min(1.0, max(0.0, done_characters / total_characters)) if total_characters else 0.0  # Clamp ratio
    filled = int(ratio * width)  # Calculate filled cells
    return "#" * filled + "-" * (width - filled)  # Return bar text


def render_translation_progress(progress_state: Dict[str, Any] | None, force: bool = False) -> None:
    """
    Renders current file and overall progress.

    :param progress_state: Shared progress state.
    :param force: True to force a snapshot.
    :return: None
    """

    if not progress_state:
        return  # No progress display requested

    now = time.monotonic()  # Current monotonic time
    interactive = progress_state["interactive"]  # Read output mode
    if not interactive and not force and now - progress_state.get("last_snapshot_time", 0.0) < 5.0:
        return  # Avoid one log line per tiny block in redirected output

    file_total = progress_state["file_total_characters"]  # Current file total characters
    file_done = min(progress_state["file_translated_characters"], file_total)  # Clamp file progress
    overall_total = progress_state["overall_total_characters"]  # Overall total characters
    overall_done = min(progress_state["overall_translated_characters"], overall_total)  # Clamp overall progress
    file_percent = (file_done / file_total * 100) if file_total else 0.0  # Current file percent
    overall_percent = (overall_done / overall_total * 100) if overall_total else 0.0  # Overall percent
    file_eta = format_eta(file_done, file_total, progress_state["file_start_time"])  # Current file ETA
    overall_eta = format_eta(overall_done, overall_total, progress_state["overall_start_time"])  # Overall ETA
    api_key_name = str(progress_state.get("active_api_key_name", "N/A"))  # Read the currently selected DeepL account name without exposing its API key.
    file_line = f"{BackgroundColors.GREEN}File - API Key: {BackgroundColors.CYAN}{api_key_name}{BackgroundColors.GREEN} [{build_progress_bar(file_done, file_total)}] {file_percent:5.1f}% | {BackgroundColors.CYAN}{file_done:,}{BackgroundColors.GREEN}/{BackgroundColors.CYAN}{file_total:,}{BackgroundColors.GREEN} chars | {BackgroundColors.CYAN}ETA {file_eta}{Style.RESET_ALL}"  # Build the green file progress line with only the active API key name in cyan.
    overall_line = f"{BackgroundColors.GREEN}Overall - API Key: {BackgroundColors.CYAN}{api_key_name}{BackgroundColors.GREEN} [{build_progress_bar(overall_done, overall_total)}] {overall_percent:5.1f}% | {BackgroundColors.CYAN}{overall_done:,}{BackgroundColors.GREEN}/{BackgroundColors.CYAN}{overall_total:,}{BackgroundColors.GREEN} chars | Files {progress_state['current_file_number']}/{progress_state['total_files']} | ETA {BackgroundColors.CYAN}{overall_eta}{Style.RESET_ALL}"  # Build the green overall progress line using the active planned-file ordinal instead of completed-file count.

    stream = sys.__stdout__  # Read the original terminal stream once so Pylance can narrow the optional type safely

    if interactive and stream is not None:
        if progress_state.get("progress_visible"):
            stream.write("\033[F\033[K\033[F\033[K")  # Clear previous two progress lines
        stream.write(f"{file_line}\n{overall_line}\n")  # Draw both fully colored progress lines.
        stream.flush()  # Flush terminal output
        progress_state["progress_visible"] = True  # Mark progress as visible
    else:
        print(file_line)  # Print the colored file progress snapshot in redirected output.
        print(overall_line)  # Print the colored overall progress snapshot in redirected output.

    progress_state["last_snapshot_time"] = now  # Store snapshot time


def print_progress_event(progress_state: Dict[str, Any] | None, message: str) -> None:
    """
    Prints an event without corrupting active progress bars.

    :param progress_state: Shared progress state.
    :param message: Event message.
    :return: None
    """

    stream = sys.__stdout__  # Read the original terminal stream once so Pylance can narrow the optional type safely

    if progress_state and progress_state.get("interactive") and progress_state.get("progress_visible") and stream is not None:
        stream.write(f"{Style.RESET_ALL}\033[F\033[K\033[F\033[K")  # Reset color and clear active progress lines before standalone message
        stream.flush()  # Flush clear sequence
        progress_state["progress_visible"] = False  # Mark progress as hidden

    print(message)  # Print event through logger

    if progress_state:
        render_translation_progress(progress_state, force=True)  # Redraw progress when translation continues


def get_translated_output_file(current_srt_path: Path, input_dir: Path, output_dir: Path, use_configured_output: bool) -> Path:
    """
    Resolves translated output path using existing output rules.

    :param current_srt_path: Source SRT path.
    :param input_dir: Resolved input directory.
    :param output_dir: Resolved configured output directory.
    :param use_configured_output: Whether configured output layout applies.
    :return: Resolved translated output file path.
    """

    if has_generated_filename_marker(current_srt_path):
        return current_srt_path.resolve()  # Mislabeled generated-looking sources are replaced in place, not chained

    if use_configured_output:
        relative_path = current_srt_path.relative_to(input_dir).parent  # Extract relative path from input directory
        output_subdir = output_dir / relative_path  # Build configured output subdirectory
    else:
        output_subdir = current_srt_path.parent  # External input writes beside source

    return (output_subdir / f"{current_srt_path.stem}_ptBR.srt").resolve()  # Build target filename


def get_target_filename_suffix() -> str:
    """
    Gets the target-language suffix used in generated subtitle filenames.

    :return: Target-language filename suffix.
    """

    return "ptBR" if TARGET_LANG.upper() == "PT-BR" else TARGET_LANG.replace("-", "_").replace(" ", "")  # Preserve existing ptBR naming


def has_generated_filename_marker(srt_file: Path) -> bool:
    """
    Determines whether an SRT filename contains generated-output markers.

    :param srt_file: SRT path.
    :return: True when the filename looks generated, otherwise False.
    """

    lower_stem = srt_file.stem.lower()  # Normalize stem only
    target_suffix = get_target_filename_suffix().lower()  # Normalize configured suffix
    return lower_stem.endswith(f"_{target_suffix}") or lower_stem.endswith(".cleaned")  # Marker alone does not prove translated content


def get_srt_family_key(srt_file: Path) -> Tuple[str, str]:
    """
    Builds a source/output family key by stripping generated filename markers.

    :param srt_file: SRT path.
    :return: Tuple containing parent path and normalized source stem.
    """

    stem = srt_file.stem  # Start with filename stem
    target_suffix = get_target_filename_suffix().lower()  # Normalize configured suffix

    while True:
        lower_stem = stem.lower()  # Normalize current stem
        if lower_stem.endswith(f"_{target_suffix}"):
            stem = stem[: -len(target_suffix) - 1]  # Strip trailing target suffix
            continue
        if lower_stem.endswith(".cleaned"):
            stem = stem[:-8]  # Strip trailing cleaned marker
            continue
        break

    return str(srt_file.parent.resolve()).lower(), stem.lower()  # Keep families scoped to their directory


def is_generated_srt_file(srt_file: Path) -> bool:
    """
    Identifies internal subtitle files that must not be source candidates.

    :param srt_file: SRT path.
    :return: True when file is temporary or backup output, otherwise False.
    """

    lower_name = srt_file.name.lower()  # Normalize filename
    return lower_name.endswith(".tmp.srt") or lower_name.endswith(".bak.srt") or lower_name.endswith(".backup.srt")  # Filename-only exclusion is safe only for internal files


def is_complete_target_language_output(source_lines: List[str], output_file: Path) -> Tuple[bool, bool, str]:
    """
    Validates an existing translated output structurally and by cleaned dialogue language.

    :param source_lines: Cleaned source SRT lines.
    :param output_file: Expected translated output path.
    :return: Tuple of valid target output, conclusive detection, and detected language label.
    """

    if not is_translated_output_complete(source_lines, output_file):
        return False, False, ""  # Missing, malformed, or structurally incomplete output is invalid

    try:
        output_lines = output_file.read_text(encoding="utf-8").splitlines()  # Read output for content language validation
    except Exception:
        return False, False, ""  # Unreadable output is invalid

    if DESCRIPTIVE_SUBTITLES_REMOVAL:
        output_lines, _, _ = clean_descriptive_subtitle_lines(output_lines)  # Detect language from meaningful dialogue only

    is_target_language, detection_conclusive, detected_language_label = detect_cleaned_subtitle_language(output_lines, TARGET_LANG)  # Validate content, not filename
    return is_target_language, detection_conclusive, detected_language_label  # Return validation result


def configure_translation_resume_plan(record: Dict[str, Any], summary: Dict[str, int]) -> bool:
    """
    Applies validated reusable translation progress to one planned source record.

    :param record: Translation source record being considered for planning.
    :param summary: Mutable preflight summary counts.
    :return: True when safely reusable translated progress exists, otherwise False.
    """

    source_characters = record["characters"]  # Preserve total source workload before subtracting reusable progress.
    resume_info = build_translation_resume_info(record["lines"], record["output_file"])  # Validate persistent output progression against the exact planned source.
    record["source_characters"] = source_characters  # Store full source character count for diagnostics and resume accounting.
    record["resume_info"] = resume_info  # Preserve validated or rejected resume state for execution preparation.
    record["resumed_characters"] = 0  # Default to no reusable translated characters.
    record["resumed_blocks"] = 0  # Default to no reusable translated SRT blocks.
    record["finalize_only"] = False  # Default to requiring translation work.

    if not resume_info.get("valid") or resume_info.get("effective_blocks", 0) <= 0:  # Continue normal preflight when no translated progress is safely reusable.
        return False  # Signal that existing output must follow the normal complete or invalid classification path.

    resumed_characters = int(resume_info["effective_characters"])  # Read safely reusable translated source characters.
    resumed_blocks = int(resume_info["effective_blocks"])  # Read safely reusable translated SRT block count.
    if resumed_characters < 0 or resumed_characters > source_characters:  # Require mathematically possible reusable character progress.
        record["resume_info"] = {**resume_info, "valid": False, "reason": "Reusable character progress exceeds the current source workload."}  # Reject inconsistent resume arithmetic conservatively.
        return False  # Fall back to normal regeneration behavior for a distinct preserved source.

    remaining_characters = source_characters - resumed_characters  # Plan only source characters that still require a new DeepL request.
    record["characters"] = remaining_characters  # Replace planned workload with current-execution remaining characters.
    record["resumed_characters"] = resumed_characters  # Preserve prior-run translated character count without adding it to current-run totals.
    record["resumed_blocks"] = resumed_blocks  # Preserve the exact next safe SRT block position.
    record["finalize_only"] = remaining_characters == 0  # Mark fully persisted output that only needs normal finalization.

    if record["finalize_only"]:  # Track complete persisted output awaiting finalization after interruption.
        summary["finalization_only_outputs"] += 1  # Count no-quota finalization work separately from complete normal skips.
        print(f"{BackgroundColors.YELLOW}Complete translated output recovered for finalization without another DeepL request: {BackgroundColors.CYAN}{record['output_file']}{Style.RESET_ALL}")  # Log final-block crash recovery.
    else:  # Track a valid partial target translation that will resume from its exact persisted prefix.
        summary["resumable_partial_outputs"] += 1  # Count legitimate partial outputs separately from invalid-language generated files.
        print(f"{BackgroundColors.YELLOW}Resuming partial translation: {BackgroundColors.CYAN}{record['output_file']}{BackgroundColors.YELLOW} | Reusing {BackgroundColors.CYAN}{resumed_characters:,}{BackgroundColors.YELLOW} characters | Remaining {BackgroundColors.CYAN}{remaining_characters:,}{Style.RESET_ALL}")  # Log exact reusable and remaining workload.

    return True  # Signal that the persistent partial output is demonstrably reusable.


def build_translation_plan(srt_files: List[Path], input_dir: Path, output_dir: Path, use_configured_output: bool) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Builds the non-destructive translation plan.

    :param srt_files: Discovered SRT files.
    :param input_dir: Resolved input directory.
    :param output_dir: Resolved output directory.
    :param use_configured_output: Whether configured output layout applies.
    :return: Tuple containing plan entries and summary counts.
    """

    plan = []  # Store pending translation or finalization work.
    records = []  # Store valid discovered SRT metadata before source/output dedupe.
    records_by_path = {}  # Map resolved paths to discovered records.
    summary = {"discovered": len(srt_files), "source_candidates": 0, "generated_skipped": 0, "existing_skipped": 0, "target_language_skipped": 0, "empty_skipped": 0, "invalid": 0, "cleanup_fallbacks": 0, "cleanup_warnings": 0, "invalid_language_outputs": 0, "mislabeled_source_files": 0, "resumable_partial_outputs": 0, "finalization_only_outputs": 0, "other_skipped": 0, "total_characters": 0}  # Store preflight counts including resumable work.

    for srt_file in srt_files:  # Analyze each discovered SRT.
        current_srt_path = srt_file.resolve()  # Resolve the logical source or generated-output path.
        if is_generated_srt_file(current_srt_path):  # Exclude internal temporary and backup SRT files from source candidacy.
            summary["other_skipped"] += 1  # Count internal files separately from generated outputs.
            continue  # Preserve existing internal-file exclusion behavior.

        output_file = get_translated_output_file(current_srt_path, input_dir, output_dir, use_configured_output)  # Resolve expected output without chaining target suffixes.
        source_storage_path = current_srt_path  # Default physical source storage to the logical source path.
        protected_in_place_resume = False  # Track restart sessions whose original source is preserved in an internal backup.
        resume_state_file = get_translation_resume_state_file(current_srt_path)  # Resolve possible in-place resume metadata beside generated-looking paths.
        resume_state_preview = read_translation_resume_state(resume_state_file) if resume_state_file.exists() else None  # Read state only when persistent resume metadata exists.

        if has_generated_filename_marker(current_srt_path) and resume_state_file.exists():  # Detect generated-looking paths that may currently contain in-place partial output.
            backup_file = get_in_place_resume_backup_file(current_srt_path)  # Resolve the protected source backup used only for in-place resume sessions.
            if resume_state_preview is None and backup_file.exists():  # Preserve ambiguous in-place artifacts when metadata cannot be interpreted.
                summary["invalid"] += 1  # Count unusable resume state as invalid preflight input.
                print(f"{BackgroundColors.RED}Resume metadata is malformed for an in-place partial translation. Preserving output and source backup without unsafe regeneration:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{current_srt_path}{Style.RESET_ALL}")  # Log conservative in-place preservation.
                continue  # Avoid treating partial translated output as new source content.
            if isinstance(resume_state_preview, dict) and resume_state_preview.get("in_place_output"):  # Use the protected source representation for an active in-place resume session.
                if not backup_file.exists():  # Require preserved source data before trusting in-place partial output.
                    summary["invalid"] += 1  # Count missing protected source as invalid resume state.
                    print(f"{BackgroundColors.RED}Protected source backup is missing for in-place resumable output. Preserving the current output without unsafe regeneration:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{current_srt_path}{Style.RESET_ALL}")  # Log missing in-place source protection.
                    continue  # Avoid destroying partial output when the exact source can no longer be proven.
                source_storage_path = backup_file  # Read the exact preserved source instead of the partial translated output path.
                protected_in_place_resume = True  # Mark this record as protected in-place resume work.

        try:  # Read and preprocess the actual source representation used for translation.
            source_lines = read_srt(source_storage_path)  # Read logical source or protected in-place source backup.
            srt_lines = source_lines  # Default translation representation to the stored source lines.
            removed_entry_count = 0  # Default cleanup removed-entry count.
            mixed_cleaned_entry_count = 0  # Default cleanup mixed-entry count.
            cleanup_fallback = False  # Track valid source translated without cleanup after cleanup validation failure.
            if not has_valid_srt_structure(source_lines):  # Reject genuinely malformed source structure.
                summary["invalid"] += 1  # Count genuinely invalid source structure.
                print(f"{BackgroundColors.RED}Invalid SRT structure: {BackgroundColors.CYAN}{source_storage_path}{Style.RESET_ALL}")  # Log invalid physical source representation.
                continue  # Skip invalid source safely.
            if DESCRIPTIVE_SUBTITLES_REMOVAL:  # Apply the same exact SDH preprocessing before resume fingerprint validation.
                cleaned_lines, cleaned_removed_entry_count, cleaned_mixed_entry_count = clean_descriptive_subtitle_lines(source_lines)  # Plan cleanup without writing.
                if has_valid_srt_structure(cleaned_lines):  # Use only structurally valid cleaned source representation.
                    srt_lines = cleaned_lines  # Use valid cleaned representation for all later processing.
                    removed_entry_count = cleaned_removed_entry_count  # Preserve cleanup metadata for valid cleanup.
                    mixed_cleaned_entry_count = cleaned_mixed_entry_count  # Preserve cleanup metadata for valid cleanup.
                else:  # Preserve original valid source when cleanup produces invalid structure.
                    cleanup_fallback = True  # Keep original valid source for translation.

            translatable_character_count = count_translatable_characters(srt_lines)  # Count exact DeepL text blocks from the actual preprocessed source.
            if translatable_character_count == 0:  # Skip sources with no translatable dialogue.
                summary["empty_skipped"] += 1  # Count empty-after-cleanup sources separately.
                print(f"{BackgroundColors.YELLOW}{current_srt_path.name} contains no translatable dialogue after SDH cleanup.{Style.RESET_ALL}")  # Log empty skip.
                continue  # Avoid unnecessary API or resume work.

            is_target_language, detection_conclusive, detected_language_label = detect_cleaned_subtitle_language(srt_lines, TARGET_LANG)  # Detect source language from the exact translation representation.
            record = {"source_path": current_srt_path, "source_storage_path": source_storage_path, "output_file": output_file, "lines": srt_lines, "characters": translatable_character_count, "source_characters": translatable_character_count, "removed_entries": removed_entry_count, "mixed_cleaned_entries": mixed_cleaned_entry_count, "cleanup_fallback": cleanup_fallback, "detection_conclusive": detection_conclusive, "detected_language_label": detected_language_label, "is_target_language": is_target_language, "filename_has_generated_marker": has_generated_filename_marker(current_srt_path), "family_key": get_srt_family_key(current_srt_path), "protected_in_place_resume": protected_in_place_resume, "resume_info": {"valid": False}, "resumed_characters": 0, "resumed_blocks": 0, "finalize_only": False}  # Store content-based classification and resume-safe source storage.
            records.append(record)  # Keep record for family dedupe.
            records_by_path[current_srt_path] = record  # Map logical path to the discovered record.
        except Exception as e:  # Preserve existing preflight failure isolation.
            summary["invalid"] += 1  # Count unreadable or invalid preflight file.
            print(f"{BackgroundColors.RED}Invalid preflight file: {BackgroundColors.CYAN}{source_storage_path}{BackgroundColors.RED} - {e}{Style.RESET_ALL}")  # Log preflight failure without altering source data.

    records_by_family = {}  # Group source and generated-output family members.
    for record in records:  # Group every valid discovered record deterministically.
        records_by_family.setdefault(record["family_key"], []).append(record)  # Group related filenames together.

    for family_records in records_by_family.values():  # Build one translation decision per source/output family.
        family_records.sort(key=lambda record: str(record["source_path"]).lower())  # Keep deterministic selection.
        source_records = [record for record in family_records if not record["filename_has_generated_marker"]]  # Prefer clean source filenames.
        source_record = source_records[0] if source_records else None  # Pick unique source candidate when present.

        if source_record:  # Handle normal source plus optional generated-output companions.
            summary["source_candidates"] += 1  # Count unique source family.
            output_file = source_record["output_file"]  # Read expected translated output.
            output_record = records_by_path.get(output_file)  # Read existing generated output when discovered in the input snapshot.
            extra_records = [record for record in family_records if record is not source_record and record is not output_record]  # Avoid duplicate family work.

            if source_record["is_target_language"]:  # Preserve existing skip for source already in target language.
                summary["target_language_skipped"] += 1  # Count target-language source skip.
                summary["generated_skipped"] += sum(1 for record in extra_records if record["is_target_language"])  # Count valid generated companions.
                continue  # Consume no DeepL quota.

            resume_recognized = configure_translation_resume_plan(source_record, summary)  # Validate legitimate partial or fully persisted interrupted output before language-based invalid classification.
            if resume_recognized:  # Resume only demonstrably source-matching persistent translation state.
                if output_record and output_record is not source_record:  # Exclude discovered partial output from independent family work.
                    summary["generated_skipped"] += 1  # Count valid resumable generated output separately from invalid-language output.
                summary["generated_skipped"] += sum(1 for record in extra_records if record["is_target_language"])  # Count valid generated companions without planning them.
                summary["invalid_language_outputs"] += sum(1 for record in extra_records if not record["is_target_language"])  # Preserve invalid companion accounting outside the resumable output.
                if source_record["cleanup_fallback"]:  # Preserve existing cleanup-fallback reporting.
                    summary["cleanup_fallbacks"] += 1  # Count planned best-effort cleanup fallback separately from invalid files.
                    print(f"{BackgroundColors.YELLOW}SDH cleanup failed structural validation. Original subtitle will be translated:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{source_record['source_path']}{Style.RESET_ALL}")  # Log cleanup fallback.
                plan.append(source_record)  # Add remaining translation or finalization-only work.
                summary["total_characters"] += source_record["characters"]  # Add only characters requiring new DeepL requests in this execution.
                continue  # Avoid misclassifying legitimate partial target output as invalid-language content.

            if output_record and output_record is not source_record:  # Preserve existing discovered-output classification when no valid resume state exists.
                if output_record["is_target_language"] and is_translated_output_complete(source_record["lines"], output_file):  # Skip structurally complete target-language output.
                    summary["existing_skipped"] += 1  # Valid generated output completes this source.
                    summary["generated_skipped"] += 1  # Existing generated file excluded from independent work.
                    summary["generated_skipped"] += sum(1 for record in extra_records if record["is_target_language"])  # Count valid generated companions.
                    print(f"{BackgroundColors.YELLOW}Skipping already complete translation: {BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}")  # Log complete skip.
                    continue  # Preserve exact complete-output skip behavior.

                summary["invalid_language_outputs"] += 1  # Existing output is present but not valid target-language content.
                print(f"{BackgroundColors.YELLOW}Existing target output is not in {BackgroundColors.CYAN}{TARGET_LANG}{BackgroundColors.YELLOW} and will be regenerated:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}")  # Log regeneration.
            elif is_complete_target_language_output(source_record["lines"], output_file)[0]:  # Preserve complete-output skip outside the discovery snapshot.
                summary["existing_skipped"] += 1  # Output outside discovery snapshot still completes source.
                print(f"{BackgroundColors.YELLOW}Skipping already complete translation: {BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}")  # Log complete skip.
                continue  # Consume no DeepL quota.

            summary["generated_skipped"] += sum(1 for record in extra_records if record["is_target_language"])  # Count valid generated companions without planning them.
            summary["invalid_language_outputs"] += sum(1 for record in extra_records if not record["is_target_language"])  # Track invalid generated companions.
            if source_record["cleanup_fallback"]:  # Preserve existing cleanup-fallback reporting.
                summary["cleanup_fallbacks"] += 1  # Count planned best-effort cleanup fallback separately from invalid files.
                print(f"{BackgroundColors.YELLOW}SDH cleanup failed structural validation. Original subtitle will be translated:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{source_record['source_path']}{Style.RESET_ALL}")  # Log cleanup fallback.
            plan.append(source_record)  # Add fresh translation work.
            summary["total_characters"] += source_record["characters"]  # Add full source workload when no valid translated progress can be reused.
            continue  # Finish this source family decision.

        target_language_records = [record for record in family_records if record["is_target_language"]]  # Identify generated-looking files already in target language by content.
        non_target_records = [record for record in family_records if not record["is_target_language"]]  # Identify generated-looking files requiring translation or resume.

        if not non_target_records:  # Preserve existing generated-only target-language skip behavior.
            summary["target_language_skipped"] += len(target_language_records)  # Valid target-language SRTs consume no quota.
            summary["generated_skipped"] += len(target_language_records)  # Generated-looking files excluded from independent translation.
            continue  # Finish this generated-only family.

        source_record = non_target_records[0]  # Treat misleading target-looking file or protected in-place source backup as logical source.
        summary["source_candidates"] += 1  # Count unique mislabeled source.
        summary["mislabeled_source_files"] += 1  # Track misleading filename.
        resume_recognized = configure_translation_resume_plan(source_record, summary)  # Validate protected in-place or generated-only resumable progression.
        if source_record["protected_in_place_resume"] and not source_record["resume_info"].get("valid"):  # Preserve partial in-place output when its metadata cannot prove a safe progression.
            summary["invalid"] += 1  # Count unusable in-place resume state without destroying either artifact.
            print(f"{BackgroundColors.RED}In-place partial translation could not be proven safe to resume. Preserving translated output and source backup:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{source_record['source_path']}{Style.RESET_ALL}")  # Log conservative in-place refusal.
            continue  # Avoid blind restart against ambiguous in-place state.

        if source_record["detection_conclusive"]:  # Preserve existing misleading-filename language reporting.
            print(f"{BackgroundColors.YELLOW}Filename indicates {BackgroundColors.CYAN}{TARGET_LANG}{BackgroundColors.YELLOW}, but cleaned content was detected as {BackgroundColors.CYAN}{source_record['detected_language_label']}{BackgroundColors.YELLOW}. Scheduling translation:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{source_record['source_path']}{Style.RESET_ALL}")  # Log mislabeled source.
        else:  # Preserve conservative translation eligibility when source language detection is inconclusive.
            print(f"{BackgroundColors.YELLOW}Language detection was inconclusive despite the target-language filename. Keeping file eligible for translation:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{source_record['source_path']}{Style.RESET_ALL}")  # Log conservative classification.

        if source_record["cleanup_fallback"]:  # Preserve existing cleanup-fallback reporting.
            summary["cleanup_fallbacks"] += 1  # Count planned best-effort cleanup fallback separately from invalid files.
            print(f"{BackgroundColors.YELLOW}SDH cleanup failed structural validation. Original subtitle will be translated:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{source_record['source_path']}{Style.RESET_ALL}")  # Log cleanup fallback.
        plan.append(source_record)  # Add fresh, resumable, or finalization-only generated-path work.
        summary["total_characters"] += source_record["characters"]  # Add only remaining DeepL workload after validated resume subtraction.
        for record in family_records:  # Preserve companion generated-file accounting.
            if record is source_record:  # Avoid counting the selected logical source twice.
                continue  # Continue to other family records.
            if record["is_target_language"]:  # Count valid generated companion.
                summary["target_language_skipped"] += 1  # Count target-language companion skip.
                summary["generated_skipped"] += 1  # Exclude valid companion from independent translation.
            else:  # Preserve invalid generated companion accounting.
                summary["invalid_language_outputs"] += 1  # Count non-target generated-looking duplicate in the same family.

    return plan, summary  # Return pending work and exact current-execution character totals.


def get_zero_plan_message(input_dir: Path, preflight_summary: Dict[str, int]) -> str:
    """
    Builds a specific zero-plan message.

    :param input_dir: Resolved input directory.
    :param preflight_summary: Preflight summary counts.
    :return: Zero-plan explanation.
    """

    discovered = preflight_summary["discovered"]  # Count all discovered SRT files
    generated = preflight_summary["generated_skipped"]  # Count generated files
    existing = preflight_summary["existing_skipped"]  # Count source files with complete outputs
    target_language = preflight_summary["target_language_skipped"]  # Count files confirmed as target language by content
    source_candidates = preflight_summary["source_candidates"]  # Count source candidates

    if discovered == 0:
        return f"No SRT files were found in the input directory or any of its subdirectories: {input_dir}"  # No recursive matches
    if target_language == discovered:
        return f"No files require translation. Found {discovered} SRT files already in {TARGET_LANG} based on cleaned subtitle content."  # All files already target language
    if generated == discovered:
        return f"No source SRT files require translation. Found {discovered} SRT files, but all generated-looking files were confirmed as {TARGET_LANG} from cleaned subtitle content."  # Only valid generated files
    if source_candidates and existing == source_candidates:
        return f"No files require translation. Valid target-language outputs already exist for all {source_candidates} source SRT files."  # All sources complete
    if generated or existing or target_language:
        return f"No files require translation. Found {discovered} SRT files: {generated} generated files were ignored, {target_language} files were already {TARGET_LANG} by content, and {existing} source files already have valid target-language outputs."  # Mixed no-op

    return "No files require translation. Source files were skipped during preflight classification."  # Fallback for target-language, empty, or invalid-only sources


def get_remaining_characters(translator: deepl.DeepLClient) -> int | None:
    """
    Returns remaining characters available for one DeepL account.

    :param translator: DeepL translator client.
    :return: Number of remaining characters or None if unlimited or unknown.
    """

    verbose_output(f"{BackgroundColors.GREEN}Reading remaining characters from DeepL API...{Style.RESET_ALL}")  # Output the verbose usage-request message.
    usage = translator.get_usage()  # Request the current DeepL account usage through the SDK.

    if usage.character.valid:  # Use character quota information only when the SDK marks it valid.
        remaining = usage.character.limit - usage.character.count  # Calculate remaining account characters.
        return remaining  # Return the exact remaining character allowance.

    return None  # Return None when the account has unlimited or unavailable character quota information.


def is_retryable_deepl_exception(exception: deepl.DeepLException) -> bool:
    """
    Determines whether a DeepL exception represents a transient request failure.

    :param exception: DeepL exception raised after the SDK exhausted its internal retries.
    :return: True when the operation may safely be retried after stabilization, otherwise False.
    """

    if isinstance(exception, deepl.TooManyRequestsException):  # Treat DeepL high-load and HTTP 429 responses as transient.
        return True  # Retry high-load responses after the configured stabilization delay.

    if isinstance(exception, deepl.ConnectionException):  # Treat DeepL connection failures as transient.
        return True  # Retry network failures after the configured stabilization delay.

    return bool(getattr(exception, "should_retry", False))  # Respect the SDK retryability flag for service-unavailable and similar failures.


def run_deepl_request_with_retries(request_callable: Callable[[], Any], operation_name: str, account_name: str, progress_state: Dict[str, Any] | None = None) -> Any:
    """
    Runs one DeepL API operation with long stabilization retries for transient failures.

    :param request_callable: Callable that performs exactly one DeepL SDK operation.
    :param operation_name: Concise operation label used in retry logging.
    :param account_name: DeepL account name used in retry logging.
    :param progress_state: Optional shared progress state for clean event logging.
    :return: Result returned by the successful DeepL SDK operation.
    """

    retry_number = 0  # Track only long stabilization retries performed after the SDK gives up.

    while True:  # Repeat the same operation only for verified transient DeepL failures.
        try:  # Execute one DeepL operation through the SDK.
            return request_callable()  # Return immediately when the operation succeeds.
        except deepl.QuotaExceededException:  # Never wait and retry a billing-period quota failure on the same key.
            raise  # Let the caller retire this account and select a new unused key.
        except deepl.DeepLException as e:  # Classify all SDK API and connection failures using verified DeepL exception metadata.
            if not is_retryable_deepl_exception(e):  # Reject authorization, bad-request, and other non-transient API failures immediately.
                raise  # Preserve the original DeepL exception for the caller's fatal error message.

            if retry_number >= len(DEEPL_TRANSIENT_RETRY_DELAYS_SECONDS):  # Stop after all configured stabilization waits were consumed.
                raise  # Preserve the final SDK exception instead of looping forever.

            retry_delay_seconds = DEEPL_TRANSIENT_RETRY_DELAYS_SECONDS[retry_number]  # Select five-minute then ten-minute stabilization delays.
            retry_number += 1  # Count this long retry before sleeping so logs show the upcoming attempt number.
            print_progress_event(progress_state, f"{BackgroundColors.YELLOW}DeepL {operation_name} failed for account {BackgroundColors.CYAN}{account_name}{BackgroundColors.YELLOW} with {BackgroundColors.CYAN}{type(e).__name__}{BackgroundColors.YELLOW}: {e}. Waiting {BackgroundColors.CYAN}{format_duration(retry_delay_seconds)}{BackgroundColors.YELLOW} before retry {BackgroundColors.CYAN}{retry_number}/{len(DEEPL_TRANSIENT_RETRY_DELAYS_SECONDS)}{BackgroundColors.YELLOW}.{Style.RESET_ALL}")  # Log the transient failure and exact stabilization delay.
            time.sleep(retry_delay_seconds)  # Wait for DeepL service or network stabilization before replaying the same operation.


def create_deepl_client(account_name: str, api_key: str) -> deepl.DeepLClient:
    """
    Creates a DeepL client for a named account.

    :param account_name: DeepL account name used for logging.
    :param api_key: DeepL API key used to create the client.
    :return: DeepL client instance.
    """

    verbose_output(true_string=f"{BackgroundColors.GREEN}Using DeepL account: {BackgroundColors.CYAN}{account_name}{Style.RESET_ALL}")  # Log account name only.
    return deepl.DeepLClient(auth_key=api_key)  # Create the client while retaining the SDK's built-in transient retry behavior.


def set_progress_api_key_name(progress_state: Dict[str, Any] | None, account_name: str) -> None:
    """
    Stores the currently selected DeepL account name for progress rendering.

    :param progress_state: Optional shared progress state.
    :param account_name: DeepL account name currently selected for API operations.
    :return: None.
    """

    if progress_state is not None:  # Update progress state only when progress rendering is enabled.
        progress_state["active_api_key_name"] = account_name  # Store only the configured account name and never the secret API key.


def select_next_unused_deepl_account(account_items: List[Tuple[str, str]], active_account_index: int, api_state: Dict[str, Any], progress_state: Dict[str, Any] | None = None) -> int:
    """
    Selects the next DeepL account that has not been used during this execution.

    :param account_items: Ordered list of DeepL account names and API keys.
    :param active_account_index: Index of the quota-exhausted account.
    :param api_state: Process-wide DeepL account usage state.
    :param progress_state: Optional shared progress state for clean event logging.
    :return: Index of the next unused DeepL account.
    """

    used_accounts = api_state["used_accounts"]  # Read process-wide account usage history.
    current_account_name = account_items[active_account_index][0]  # Read the exhausted account name for transition logging.

    for offset in range(1, len(account_items) + 1):  # Search every configured account once in deterministic circular order.
        candidate_index = (active_account_index + offset) % len(account_items)  # Resolve the next configured account position.
        candidate_account_name = account_items[candidate_index][0]  # Read the candidate account name without exposing its key.
        if candidate_account_name in used_accounts:  # Reject every account already touched during this execution.
            continue  # Continue until a genuinely unused key is found.

        set_progress_api_key_name(progress_state, candidate_account_name)  # Update both progress bars before logging and redrawing the quota-driven account switch.
        print_progress_event(progress_state, f"{BackgroundColors.YELLOW}Switching DeepL account from {BackgroundColors.CYAN}{current_account_name}{BackgroundColors.YELLOW} to unused account {BackgroundColors.CYAN}{candidate_account_name}{BackgroundColors.YELLOW} after quota exhaustion.{Style.RESET_ALL}")  # Log quota-driven account rotation.
        return candidate_index  # Return the next unused account without issuing an API request yet.

    used_account_names = ", ".join(account_name for account_name, _ in account_items if account_name in used_accounts)  # Build a safe account-name-only exhaustion summary.
    raise RuntimeError(f"No unused DeepL API account remains after quota exhaustion. Accounts already used this run: {used_account_names}")  # Stop instead of retrying an exhausted or previously used key.


def translate_text_block(text_block: str, account_items: List[Tuple[str, str]], active_account_index: int, translators: Dict[str, deepl.DeepLClient], api_state: Dict[str, Any], progress_state: Dict[str, Any] | None = None) -> Tuple[List[str], int]:
    """
    Translates one subtitle text block with quota rotation and transient API retries.

    :param text_block: String containing subtitle lines to translate.
    :param account_items: Ordered list of DeepL account names and API keys.
    :param active_account_index: Index for the currently active account.
    :param translators: DeepL clients already created for this execution.
    :param api_state: Process-wide DeepL account usage and quota state.
    :param progress_state: Optional shared progress state for clean event logging.
    :return: Tuple containing translated lines and active account index.
    """

    verbose_output(f"{BackgroundColors.GREEN}Translating text block...{Style.RESET_ALL}")  # Output the verbose translation message.

    if not account_items:  # Require API credentials whenever a block needs new translation.
        raise RuntimeError("No DeepL API accounts are available for pending translation work.")  # Reject impossible runtime state before indexing the account list.

    while True:  # Keep the same pending block until it translates or no eligible account remains.
        account_name, api_key = account_items[active_account_index]  # Select the current process-wide active account in configured insertion order.
        set_progress_api_key_name(progress_state, account_name)  # Keep both progress bars synchronized with the account used by the next DeepL operation.
        api_state["used_accounts"].add(account_name)  # Mark this key as used before its first API operation in this execution.

        if account_name not in translators:  # Reuse one client per account across files and retries.
            translators[account_name] = create_deepl_client(account_name, api_key)  # Create the selected account client lazily.
        translator = translators[account_name]  # Select the cached client for usage and translation requests.

        try:  # Read quota through the same crash-resilient API retry layer.
            remaining_chars = run_deepl_request_with_retries(lambda: get_remaining_characters(translator), "usage request", account_name, progress_state)  # Retry transient usage failures on the same account after stabilization.
        except deepl.QuotaExceededException:  # Retire a key whose quota is explicitly exhausted.
            api_state["quota_exhausted_accounts"].add(account_name)  # Record quota exhaustion for process-wide diagnostics.
            print_progress_event(progress_state, f"{BackgroundColors.YELLOW}DeepL account {BackgroundColors.CYAN}{account_name}{BackgroundColors.YELLOW} quota is exhausted.{Style.RESET_ALL}")  # Log verified quota exhaustion.
            active_account_index = select_next_unused_deepl_account(account_items, active_account_index, api_state, progress_state)  # Move only to a key never used earlier in this execution.
            continue  # Retry the exact same untranslated block with the newly selected account.
        except deepl.DeepLException as e:  # Convert exhausted transient retries or permanent SDK failures into the existing file-level failure path.
            raise RuntimeError(f"DeepL usage request failed with {type(e).__name__}: {e}") from e  # Preserve the API failure without falsely completing the block.
        except Exception as e:  # Treat unexpected usage-query failures as fatal unsuccessful work.
            raise RuntimeError(f"DeepL usage request failed with {type(e).__name__}: {e}") from e  # Preserve the original failure without entering quota rotation.

        if remaining_chars is not None and len(text_block) > remaining_chars:  # Detect insufficient allowance before submitting the translation.
            api_state["quota_exhausted_accounts"].add(account_name)  # Retire this account because it cannot satisfy the pending existing translation unit.
            print_progress_event(progress_state, f"{BackgroundColors.YELLOW}DeepL account {BackgroundColors.CYAN}{account_name}{BackgroundColors.YELLOW} has only {BackgroundColors.CYAN}{remaining_chars:,}{BackgroundColors.YELLOW} characters remaining for pending block size {BackgroundColors.CYAN}{len(text_block):,}{BackgroundColors.YELLOW}.{Style.RESET_ALL}")  # Log quota insufficiency without consuming translation quota.
            active_account_index = select_next_unused_deepl_account(account_items, active_account_index, api_state, progress_state)  # Select the next never-used account.
            continue  # Retry the exact same untranslated block with the new key.

        try:  # Submit the translation through long stabilization retries after the SDK's own retry policy.
            result = run_deepl_request_with_retries(lambda: translator.translate_text(text_block, target_lang=TARGET_LANG), "translation request", account_name, progress_state)  # Retry verified transient translation failures without changing accounts.
        except deepl.QuotaExceededException:  # Rotate only when DeepL explicitly reports quota exhaustion during translation.
            api_state["quota_exhausted_accounts"].add(account_name)  # Record the exhausted key so it is never reused this run.
            print_progress_event(progress_state, f"{BackgroundColors.YELLOW}DeepL account {BackgroundColors.CYAN}{account_name}{BackgroundColors.YELLOW} quota was exhausted during translation.{Style.RESET_ALL}")  # Log quota-driven request failure.
            active_account_index = select_next_unused_deepl_account(account_items, active_account_index, api_state, progress_state)  # Move to the next never-used configured key.
            continue  # Retry the same untranslated subtitle block without advancing progress.
        except deepl.DeepLException as e:  # Convert exhausted transient retries or permanent SDK failures into the existing file-level failure path.
            raise RuntimeError(f"DeepL translation failed with {type(e).__name__}: {e}") from e  # Preserve the final API failure without persisting untranslated content.
        except Exception as e:  # Treat unexpected request or response failures as fatal unsuccessful work.
            raise RuntimeError(f"Translation failed with {type(e).__name__}: {e}") from e  # Preserve the original error without returning source text as translation.

        if result is None or not hasattr(result, "text") or not isinstance(result.text, str) or not result.text.strip():  # Require genuine non-empty DeepL translation text.
            raise RuntimeError("DeepL returned no valid translated text for the pending subtitle block.")  # Prevent invalid API responses from being persisted or counted.

        translated_lines = result.text.split("\n")  # Preserve DeepL newline behavior for the existing subtitle translation unit.
        return translated_lines, active_account_index  # Return only genuine DeepL-returned translation content.


def translate_srt_lines(srt_file: Path, lines: List[str], output_file: Path, translatable_character_count: int, account_items: List[Tuple[str, str]], active_account_index: int, translators: Dict[str, deepl.DeepLClient], api_state: Dict[str, Any], resume_state: Dict[str, Any], output_blocks: List[Tuple[str, str, List[str]]], progress_state: Dict[str, Any] | None = None) -> Tuple[List[str], int, Dict[str, Any]]:
    """
    Translates remaining SRT blocks and atomically persists every successful translation unit.

    :param srt_file: Path to the logical source SRT file for logging purposes.
    :param lines: Exact preprocessed source SRT lines.
    :param output_file: Persistent translated output SRT path.
    :param translatable_character_count: Remaining source characters planned for DeepL in this execution.
    :param account_items: Ordered list of DeepL account names and API keys.
    :param active_account_index: Process-wide active DeepL account index.
    :param translators: DeepL clients reused across files.
    :param api_state: Process-wide DeepL account usage and quota state.
    :param resume_state: Active persistent translation resume metadata.
    :param output_blocks: Safely persisted translated output prefix.
    :param progress_state: Optional shared progress state.
    :return: Tuple containing complete translated lines, active account index, and committed resume metadata.
    """

    verbose_output(f"{BackgroundColors.GREEN}Translating SRT lines from file: {BackgroundColors.CYAN}{srt_file}{Style.RESET_ALL}")  # Output verbose message for translating SRT lines.

    source_blocks = parse_srt_blocks(lines)  # Parse the exact source representation into existing translation units.
    translated_character_count = 0  # Track only characters newly translated during this execution.
    filename = srt_file.name  # Extract filename for remaining-character failure messages.
    start_block_position = len(output_blocks)  # Resume immediately after the last safely persisted translated block.

    if resume_state.get("completed_blocks") != start_block_position:  # Require persistent metadata and translated output to begin at the same safe boundary.
        raise RuntimeError(f"Resume state and translated output progression differ for file: {filename}")  # Refuse ambiguous resume progression before any new DeepL request.

    for block_position in range(start_block_position, len(source_blocks)):  # Translate only source blocks not already safely persisted.
        source_block = source_blocks[block_position]  # Read the next exact source subtitle block.
        text_block = "\n".join(source_block[2])  # Preserve the existing per-entry DeepL translation unit.

        if text_block:  # Submit only translatable subtitle text to DeepL.
            try:  # Translate the next unpersisted subtitle block.
                translated_lines, active_account_index = translate_text_block(text_block, account_items, active_account_index, translators, api_state, progress_state)  # Request one existing translation unit from DeepL.
            except RuntimeError as e:  # Preserve all previously persisted translation work when the current request fails.
                remaining_characters = max(0, translatable_character_count - translated_character_count)  # Count only still-untranslated characters from this execution plan.
                raise RuntimeError(f"Error: {e}. File: {filename}. Remaining: {remaining_characters:,} characters.") from None  # Report exact remaining workload without counting resumed characters.
        else:  # Preserve zero-character structural subtitle entries without consuming DeepL quota.
            translated_lines = []  # Keep the empty subtitle text block structurally unchanged.

        output_blocks, resume_state = persist_translated_srt_block(source_blocks, output_blocks, block_position, translated_lines, output_file, resume_state)  # Journal and atomically persist the complete successful translation unit.

        if text_block:  # Advance current-run progress only after successful translated SRT persistence.
            translated_character_count += len(text_block)  # Count this newly translated source block once.
            if progress_state:  # Update visible current-run progress when enabled.
                progress_state["file_translated_characters"] += len(text_block)  # Advance current-file progress by newly translated characters only.
                progress_state["overall_translated_characters"] += len(text_block)  # Advance overall progress by newly translated characters only.
                render_translation_progress(progress_state)  # Redraw progress after durable translated-block persistence.

    translated_lines = serialize_srt_blocks_preserving_indices(output_blocks)  # Serialize the complete persisted translated output deterministically.
    return translated_lines, active_account_index, resume_state  # Return complete translated output and committed persistent state.


def parse_srt_entries(lines: List[str]) -> List[Tuple[str, str, str]]:
    """
    Parses SRT lines into index, timing, and text entries.

    :param lines: SRT lines to parse.
    :return: List of parsed SRT entries.
    """

    return [(index, timing, "\n".join(text_lines)) for index, timing, text_lines in parse_srt_blocks(lines)]  # Reuse parsed blocks


def is_translated_output_complete(source_lines: List[str], output_file: Path) -> bool:
    """
    Determines whether translated output is complete for the source subtitle.

    :param source_lines: Source SRT lines after existing preprocessing.
    :param output_file: Translated output file path.
    :return: True if output is parseable and matches source entries, otherwise False.
    """

    if not output_file.exists() or output_file.stat().st_size == 0:  # Require existing non-empty output
        return False  # Missing or empty output is incomplete

    try:
        output_lines = output_file.read_text(encoding="utf-8").splitlines()  # Read translated output for validation
    except Exception:
        return False  # Unreadable output is incomplete

    source_entries = parse_srt_entries(source_lines)  # Parse source subtitle entries
    output_entries = parse_srt_entries(output_lines)  # Parse translated subtitle entries

    if not source_entries or len(source_entries) != len(output_entries):  # Require matching entry count
        return False  # Malformed or partial output is incomplete

    for source_entry, output_entry in zip(source_entries, output_entries):  # Compare structural SRT fields
        if source_entry[0] != output_entry[0] or source_entry[1] != output_entry[1]:
            return False  # Index or timing mismatch is incomplete

    return True  # Output is complete for this source


def save_srt(lines, output_file, success_message: str = "Translated SRT saved as"):
    """
    Saves translated lines to an output SRT file.

    :param lines: List of translated lines
    :param output_file: Path to save the output SRT.
    :param success_message: Message prefix for the saved output path.
    :return: None
    """

    write_srt_lines_atomic(Path(output_file), lines)  # Write complete output atomically, including safe in-place replacements

    print(
        f"{BackgroundColors.GREEN}{success_message}:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}"
    )  # Output the saved file message


def cleanup_saved_translation(output_file: Path, resume_state: Dict[str, Any] | None = None) -> bool:
    """
    Attempts SDH cleanup on a saved translated SRT without risking the valid output.

    :param output_file: Saved translated SRT path.
    :param resume_state: Optional persistent resume metadata used for crash-safe finalization.
    :return: True when cleanup was skipped because it produced invalid structure.
    """

    output_lines = output_file.read_text(encoding="utf-8").splitlines()  # Read valid translated output.
    cleaned_lines, removed_entry_count, mixed_cleaned_entry_count = clean_descriptive_subtitle_lines(output_lines)  # Clean translated output in memory.
    if not removed_entry_count and not mixed_cleaned_entry_count:  # Finish without rewriting when translated cleanup changes nothing.
        if resume_state is not None:  # Journal the already-persisted final output before resume metadata removal.
            mark_translation_final_output(output_file, resume_state, output_lines)  # Record final translated output identity for interruption recovery.
        return False  # No translated cleanup needed.

    if not has_valid_srt_structure(cleaned_lines) or count_translatable_characters(cleaned_lines) == 0:  # Preserve valid translation when cleanup would produce unusable output.
        print(f"{BackgroundColors.YELLOW}Translated SRT saved successfully, but SDH cleanup was skipped because it produced an invalid structure:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}")  # Preserve valid translated output.
        if resume_state is not None:  # Journal the unchanged final output before resume metadata removal.
            mark_translation_final_output(output_file, resume_state, output_lines)  # Record final translated output identity after cleanup rejection.
        return True  # Cleanup warning emitted.

    if resume_state is not None:  # Journal expected cleaned output before atomic replacement.
        mark_translation_final_output(output_file, resume_state, cleaned_lines)  # Allow restart to recognize cleanup already persisted after interruption.
    write_srt_lines_atomic(output_file, cleaned_lines)  # Replace only with validated cleaned translation.
    return False  # Cleanup succeeded.


def calculate_execution_time(start_time, finish_time):
    """
    Calculates the execution time between start and finish times and formats it as hh:mm:ss.

    :param start_time: The start datetime object
    :param finish_time: The finish datetime object
    :return: String formatted as hh:mm:ss representing the execution time
    """

    delta = finish_time - start_time  # Calculate the time difference
    return format_duration(delta.total_seconds())  # Format the execution time


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


def print_translation_plan_summary(planned_files: int, total_planned_characters: int, reused_characters: int, preflight_summary: Dict[str, int]) -> None:
    """
    Prints the translation plan summary with new and reusable work separated.

    :param planned_files: Number of files requiring translation or recovered finalization work.
    :param total_planned_characters: Number of characters requiring new DeepL requests in this execution.
    :param reused_characters: Number of safely persisted translated characters reused from prior executions.
    :param preflight_summary: Preflight classification and planning counters.
    :return: None.
    """

    print(f"{BackgroundColors.GREEN}Translation plan: {BackgroundColors.CYAN}{planned_files}{BackgroundColors.GREEN} files | {BackgroundColors.CYAN}{total_planned_characters:,}{BackgroundColors.GREEN} new characters | {BackgroundColors.CYAN}{reused_characters:,}{BackgroundColors.GREEN} reused characters | {BackgroundColors.CYAN}{preflight_summary['resumable_partial_outputs']}{BackgroundColors.GREEN} resumable partial outputs | {BackgroundColors.CYAN}{preflight_summary['finalization_only_outputs']}{BackgroundColors.GREEN} recovered finalizations | {BackgroundColors.CYAN}{preflight_summary['existing_skipped']}{BackgroundColors.GREEN} existing translations skipped | {BackgroundColors.CYAN}{preflight_summary['target_language_skipped']}{BackgroundColors.GREEN} target-language files skipped | {BackgroundColors.CYAN}{preflight_summary['invalid_language_outputs']}{BackgroundColors.GREEN} invalid-language outputs | {BackgroundColors.CYAN}{preflight_summary['cleanup_fallbacks']}{BackgroundColors.GREEN} cleanup fallbacks | {BackgroundColors.CYAN}{preflight_summary['invalid']}{BackgroundColors.GREEN} invalid files{Style.RESET_ALL}")  # Print preflight summary with current-run and reusable work separated.


def prepare_translation_runtime(translation_plan: List[Dict[str, Any]], total_planned_characters: int, use_configured_output: bool, output_dir: Path) -> Tuple[List[Tuple[str, str]], Dict[str, deepl.DeepLClient], Dict[str, Any], Dict[str, Any]] | None:
    """
    Prepares API clients and shared progress state for planned translation work.

    :param translation_plan: Planned translation and recovered finalization entries.
    :param total_planned_characters: Number of characters requiring new DeepL requests.
    :param use_configured_output: Whether the configured output directory layout applies.
    :param output_dir: Resolved configured output directory.
    :return: Runtime API, account, and progress state, or None when required API credentials are unavailable.
    """

    if use_configured_output and not output_dir.exists():  # Create configured output root only when planned work exists.
        output_dir.mkdir(parents=True, exist_ok=True)  # Preserve lazy output directory creation.

    account_items: List[Tuple[str, str]] = []  # Default to no API accounts when every planned file only needs finalization.
    translators: Dict[str, deepl.DeepLClient] = {}  # Initialize process-wide DeepL clients reused across files.

    if total_planned_characters > 0:  # Load API credentials only when new DeepL quota is actually required.
        if not get_api_keys():  # Preserve existing API-key validation before new translation requests.
            print(f"{BackgroundColors.RED}DEEPL_API_KEYS not found or invalid in .env file. Please set it before running the program.{Style.RESET_ALL}")  # Output configuration error.
            return None  # Leave persisted partial outputs untouched for the next run.
        account_items = list(DEEPL_API_KEYS.items())  # Preserve the exact JSON insertion order from DEEPL_API_KEYS for account priority across files.

    api_state = {"used_accounts": set(), "quota_exhausted_accounts": set()}  # Track account usage and quota retirement across the entire execution.
    initial_api_key_name = account_items[0][0] if account_items else "N/A"  # Select the first configured account name for initial progress display without exposing its API key.
    progress_state = {"interactive": is_interactive_output(), "overall_total_characters": total_planned_characters, "overall_translated_characters": 0, "overall_start_time": time.monotonic(), "total_files": len(translation_plan), "completed_files": 0, "current_file_number": 0, "progress_visible": False, "last_snapshot_time": 0.0, "active_api_key_name": initial_api_key_name}  # Track current-execution progress, the active planned-file ordinal, and the configured DeepL account name.
    return account_items, translators, api_state, progress_state  # Return initialized API, account, and progress state for deterministic plan execution.


def prepare_planned_translation_file(planned_file: Dict[str, Any], file_number: int, planned_files: int, progress_state: Dict[str, Any]) -> Tuple[Path, Path, Path, List[str], int]:
    """
    Prepares one planned subtitle file and prints its concise execution information.

    :param planned_file: Planned subtitle translation or finalization entry.
    :param file_number: One-based position of the planned file.
    :param planned_files: Total number of planned files.
    :param progress_state: Shared translation progress state.
    :return: Logical source path, physical source path, output path, source lines, and remaining character count.
    """

    current_srt_path = planned_file["source_path"]  # Read logical source path used by existing output rules.
    source_storage_path = planned_file["source_storage_path"]  # Read physical preserved source representation used for resume validation.
    output_file = planned_file["output_file"]  # Read persistent translated output path.
    srt_lines = planned_file["lines"]  # Read exact preprocessed source representation.
    translatable_character_count = planned_file["characters"]  # Read only remaining current-run DeepL character workload.
    filename = current_srt_path.name  # Build display filename.

    if planned_file["removed_entries"] or planned_file["mixed_cleaned_entries"]:  # Persist source preprocessing only after preflight selected this source.
        write_srt_lines_atomic(source_storage_path, srt_lines)  # Preserve cleanup in the actual source storage without overwriting in-place partial output.
        print(f"{BackgroundColors.YELLOW}SDH cleanup: {BackgroundColors.CYAN}{filename}{BackgroundColors.YELLOW} removed {BackgroundColors.CYAN}{planned_file['removed_entries']}{BackgroundColors.YELLOW} entries, cleaned {BackgroundColors.CYAN}{planned_file['mixed_cleaned_entries']}{BackgroundColors.YELLOW} mixed entries.{Style.RESET_ALL}")  # Log concise source cleanup summary.

    if planned_file["cleanup_fallback"]:  # Preserve existing cleanup fallback visibility.
        print(f"{BackgroundColors.YELLOW}Cleanup mode: Original subtitle content{Style.RESET_ALL}")  # Identify fallback source representation once.

    if not planned_file["detection_conclusive"]:  # Preserve existing DeepL source-language autodetection behavior.
        print(f"{BackgroundColors.YELLOW}Source language detection was inconclusive for {BackgroundColors.CYAN}{filename}{BackgroundColors.YELLOW}. DeepL will determine the source language during translation.{Style.RESET_ALL}")  # Log inconclusive offline detection.

    output_file.parent.mkdir(parents=True, exist_ok=True)  # Ensure output directory exists before resume metadata or SRT persistence.
    progress_state.update({"file_total_characters": translatable_character_count, "file_translated_characters": 0, "file_start_time": time.monotonic(), "current_file_number": file_number, "progress_visible": False, "last_snapshot_time": 0.0})  # Reset file progress and expose the one-based active planned-file ordinal before any progress render.
    print(f"{BackgroundColors.GREEN}File {BackgroundColors.CYAN}{file_number}/{planned_files}{BackgroundColors.GREEN}: {BackgroundColors.CYAN}{filename}{Style.RESET_ALL}")  # Print compact file header once.
    print(f"{BackgroundColors.GREEN}Characters remaining: {BackgroundColors.CYAN}{translatable_character_count:,}{Style.RESET_ALL}")  # Print new DeepL workload without counting persisted prior-run characters.

    if planned_file.get("resumed_characters", 0):  # Report persistent translation work reused from earlier execution.
        print(f"{BackgroundColors.GREEN}Characters reused: {BackgroundColors.CYAN}{planned_file['resumed_characters']:,}{Style.RESET_ALL}")  # Keep resumed characters separate from current-run translated totals.

    return current_srt_path, source_storage_path, output_file, srt_lines, translatable_character_count  # Return prepared file state for resume or translation processing.


def finalize_resumed_translation(srt_lines: List[str], output_file: Path, output_blocks: List[Tuple[str, str, List[str]]], resume_state: Dict[str, Any], resume_info: Dict[str, Any], preflight_summary: Dict[str, int]) -> None:
    """
    Finalizes a complete persisted translation recovered after interruption.

    :param srt_lines: Exact preprocessed source SRT lines.
    :param output_file: Persistent translated output path.
    :param output_blocks: Validated persisted translated output blocks.
    :param resume_state: Active persistent resume metadata.
    :param resume_info: Validated resume information for the planned file.
    :param preflight_summary: Preflight counters updated with cleanup warnings.
    :return: None.
    """

    if resume_info.get("final_output_ready"):  # Recognize cleanup already atomically persisted before the previous interruption.
        remove_translation_resume_artifacts(output_file, resume_state)  # Remove only completed resume artifacts without rewriting final output.
        return  # Finish recovered finalization without another persistent output write.

    if not is_translated_output_complete(srt_lines, output_file):  # Require complete source index and timing correspondence before finalization.
        raise RuntimeError(f"Recovered translated output is structurally incomplete for finalization: {output_file}")  # Refuse finalization of ambiguous output.

    translated_lines = serialize_srt_blocks_preserving_indices(output_blocks)  # Rebuild complete persisted translation from validated blocks.
    save_srt(translated_lines, output_file)  # Preserve existing final saved-output message and atomic final write.

    if DESCRIPTIVE_SUBTITLES_REMOVAL:  # Preserve existing translated-output SDH cleanup behavior.
        if cleanup_saved_translation(output_file, resume_state):  # Run cleanup with crash-safe final-output journaling.
            preflight_summary["cleanup_warnings"] += 1  # Count skipped translated cleanup separately from translation failure.
    else:  # Journal unchanged final output when translated cleanup is disabled.
        mark_translation_final_output(output_file, resume_state, translated_lines)  # Record final output identity before resume metadata removal.

    remove_translation_resume_artifacts(output_file, resume_state)  # Remove persistent resume artifacts only after final output is safely complete.


def validate_completed_translation_output(srt_lines: List[str], translated_lines: List[str], output_file: Path, progress_state: Dict[str, Any]) -> bool:
    """
    Validates a newly completed translated output before final persistence and cleanup.

    :param srt_lines: Exact preprocessed source SRT lines.
    :param translated_lines: Complete translated SRT lines returned by the translation flow.
    :param output_file: Persistent translated output path.
    :param progress_state: Shared translation progress state.
    :return: True when final output structure matches the source progression, otherwise False.
    """

    if translated_lines and not has_valid_srt_structure(translated_lines):  # Reject impossible complete translated serialization before finalization.
        print_progress_event(progress_state, f"{BackgroundColors.RED}Translated SRT structure is invalid and remains resumable for review: {BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}")  # Preserve persisted state instead of deleting it.
        return False  # Leave resume artifacts intact for conservative recovery.

    if not is_translated_output_complete(srt_lines, output_file):  # Require exact source index and timing correspondence at full completion.
        print_progress_event(progress_state, f"{BackgroundColors.RED}Translated SRT does not completely match the source progression and remains resumable: {BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}")  # Preserve persistent translated prefix and metadata.
        return False  # Avoid final cleanup or metadata deletion for incomplete output.

    return True  # Allow normal final persistence after structural validation succeeds.


def persist_completed_translation_output(translated_lines: List[str], output_file: Path, resume_state: Dict[str, Any], preflight_summary: Dict[str, int]) -> None:
    """
    Persists and finalizes a newly completed translated subtitle output.

    :param translated_lines: Complete translated SRT lines.
    :param output_file: Persistent translated output path.
    :param resume_state: Active persistent resume metadata.
    :param preflight_summary: Preflight counters updated with cleanup warnings.
    :return: None.
    """

    save_srt(translated_lines, output_file)  # Preserve existing final atomic save and success message after per-block persistence.

    if DESCRIPTIVE_SUBTITLES_REMOVAL:  # Preserve existing translated-output cleanup behavior.
        if cleanup_saved_translation(output_file, resume_state):  # Run cleanup with final-output crash journaling.
            preflight_summary["cleanup_warnings"] += 1  # Count skipped translated cleanup separately from translation failure.
    else:  # Journal unchanged final output when translated cleanup is disabled.
        mark_translation_final_output(output_file, resume_state, translated_lines)  # Record final output identity before completed resume metadata removal.

    remove_translation_resume_artifacts(output_file, resume_state)  # Remove persistent state only after complete final validation and cleanup.


def process_planned_translation_file(planned_file: Dict[str, Any], file_number: int, planned_files: int, account_items: List[Tuple[str, str]], active_account_index: int, translators: Dict[str, deepl.DeepLClient], api_state: Dict[str, Any], progress_state: Dict[str, Any], preflight_summary: Dict[str, int]) -> Tuple[str, int]:
    """
    Processes one planned translation or recovered finalization entry.

    :param planned_file: Planned subtitle translation or finalization entry.
    :param file_number: One-based position of the planned file.
    :param planned_files: Total number of planned files.
    :param account_items: Ordered DeepL account names and API keys.
    :param active_account_index: Process-wide active DeepL account index.
    :param translators: DeepL clients reused across files.
    :param api_state: Process-wide DeepL account usage and quota state.
    :param progress_state: Shared translation progress state.
    :param preflight_summary: Preflight counters updated during final cleanup.
    :return: Processing status and updated active DeepL account index.
    """

    current_srt_path, source_storage_path, output_file, srt_lines, translatable_character_count = prepare_planned_translation_file(planned_file, file_number, planned_files, progress_state)  # Prepare source persistence and concise file logging.
    resume_state, output_blocks = prepare_translation_resume_session(srt_lines, current_srt_path, source_storage_path, output_file, planned_file["resume_info"])  # Recover journaled DeepL output or initialize source-bound resume metadata.

    if planned_file["finalize_only"]:  # Finalize a complete persisted translation without consuming new DeepL quota.
        try:  # Complete normal save and cleanup semantics from persistent translated output.
            finalize_resumed_translation(srt_lines, output_file, output_blocks, resume_state, planned_file["resume_info"], preflight_summary)  # Finalize validated persisted output without new translation requests.
        except Exception as e:  # Preserve complete translated output and resume metadata when finalization fails.
            raise RuntimeError(f"Finalization failed for {BackgroundColors.CYAN}{output_file}{BackgroundColors.RED}: {e}") from None  # Preserve deterministic next-run recovery after finalization failure.

        progress_state["completed_files"] += 1  # Count recovered finalized file in overall file progress.
        render_translation_progress(progress_state, force=True)  # Refresh overall file completion after recovered finalization.
        return "finalized", active_account_index  # Proceed without changing the active DeepL account.

    render_translation_progress(progress_state, force=True)  # Render 0% of current-run remaining characters before translation starts.
    translated_lines, active_account_index, resume_state = translate_srt_lines(current_srt_path, srt_lines, output_file, translatable_character_count, account_items, active_account_index, translators, api_state, resume_state, output_blocks, progress_state)  # Translate and atomically persist each remaining existing translation unit.

    if not validate_completed_translation_output(srt_lines, translated_lines, output_file, progress_state):  # Preserve resumable state when complete output validation fails.
        return "failed_continue", active_account_index  # Continue later planned files without deleting persistent progress.

    progress_state["completed_files"] += 1  # Count fully translated file.
    render_translation_progress(progress_state, force=True)  # Finalize successful file progress.
    persist_completed_translation_output(translated_lines, output_file, resume_state, preflight_summary)  # Preserve final save, cleanup, and resume-artifact removal order.
    return "translated", active_account_index  # Report successful current-run translation completion.


def execute_translation_plan(translation_plan: List[Dict[str, Any]], total_planned_characters: int, use_configured_output: bool, output_dir: Path, preflight_summary: Dict[str, int]) -> Dict[str, int] | None:
    """
    Executes planned translation and recovered finalization work.

    :param translation_plan: Planned translation and recovered finalization entries.
    :param total_planned_characters: Number of characters requiring new DeepL requests.
    :param use_configured_output: Whether the configured output directory layout applies.
    :param output_dir: Resolved configured output directory.
    :param preflight_summary: Preflight counters updated during final cleanup.
    :return: Execution counters, or None when required API credentials are unavailable.
    """

    runtime_state = prepare_translation_runtime(translation_plan, total_planned_characters, use_configured_output, output_dir)  # Prepare API and progress state only when planned work exists.
    if runtime_state is None:  # Stop when new translation work requires unavailable API credentials.
        return None  # Preserve the existing early-return behavior from main.

    account_items, translators, api_state, progress_state = runtime_state  # Unpack initialized API, account, and progress state.
    active_account_index = 0  # Initialize process-wide active account index.
    execution_summary = {"translated_files": 0, "finalized_files": 0, "failed_files": 0, "translated_characters": 0}  # Track current-execution results separately from reused progress.
    planned_files = len(translation_plan)  # Count planned translation and recovered finalization files.

    for file_number, planned_file in enumerate(translation_plan, start=1):  # Process every planned translation or recovered finalization deterministically.
        try:  # Preserve fatal stop behavior for resume, quota, API, network, persistence, and recovered finalization failures.
            status, active_account_index = process_planned_translation_file(planned_file, file_number, planned_files, account_items, active_account_index, translators, api_state, progress_state, preflight_summary)  # Process one plan entry through resume, translation, validation, and finalization.
        except RuntimeError as e:  # Preserve partial progress after fatal planned-file failure.
            execution_summary["failed_files"] += 1  # Count failed planned file.
            execution_summary["translated_characters"] = progress_state["overall_translated_characters"]  # Preserve only current-run successfully persisted translated characters.
            print_progress_event(progress_state, f"{BackgroundColors.RED}{e}{Style.RESET_ALL}")  # Log fatal request, persistence, resume, or finalization failure cleanly.
            break  # Preserve existing stop-on-fatal behavior while leaving resumable data intact.

        if status == "failed_continue":  # Preserve non-fatal invalid-completion behavior for later planned files.
            execution_summary["failed_files"] += 1  # Count invalid completed serialization as failed work.
            continue  # Leave resumable artifacts intact and proceed to the next planned file.

        if status == "finalized":  # Count recovered no-quota finalization separately.
            execution_summary["finalized_files"] += 1  # Count interrupted complete output finalized in this execution.
            continue  # No current-run translated character total changes are required.

        execution_summary["translated_files"] += 1  # Count file completed with new DeepL translation work this run.
        execution_summary["translated_characters"] = progress_state["overall_translated_characters"]  # Store only current-run successful translated character progress.

    return execution_summary  # Return deterministic execution counters for final reporting.


def print_translation_completion_summary(preflight_summary: Dict[str, int], planned_files: int, translated_files: int, finalized_files: int, failed_files: int, reused_characters: int, translated_characters: int, total_planned_characters: int, other_skipped_files: int) -> None:
    """
    Prints the final translation execution summary.

    :param preflight_summary: Preflight classification and cleanup counters.
    :param planned_files: Number of planned translation or finalization files.
    :param translated_files: Number of files completed with new DeepL work in this execution.
    :param finalized_files: Number of persisted complete outputs finalized without new DeepL work.
    :param failed_files: Number of planned files that failed.
    :param reused_characters: Number of safely persisted translated characters reused from prior executions.
    :param translated_characters: Number of characters successfully translated in this execution.
    :param total_planned_characters: Number of characters planned for new DeepL requests.
    :param other_skipped_files: Number of empty or internal files skipped for non-language reasons.
    :return: None.
    """

    print(  # Output concise summary with reused and newly translated characters separated.
        f"\n{BackgroundColors.GREEN}Translation completed.{Style.RESET_ALL}\n\n"  # Add summary heading.
        f"{BackgroundColors.GREEN}Files discovered: {BackgroundColors.CYAN}{preflight_summary['discovered']}{Style.RESET_ALL}\n"  # Add discovered file count.
        f"{BackgroundColors.GREEN}Files planned: {BackgroundColors.CYAN}{planned_files}{Style.RESET_ALL}\n"  # Add planned file count.
        f"{BackgroundColors.GREEN}Files translated: {BackgroundColors.CYAN}{translated_files}{Style.RESET_ALL}\n"  # Add current-run translated file count.
        f"{BackgroundColors.GREEN}Files finalized from persisted output: {BackgroundColors.CYAN}{finalized_files}{Style.RESET_ALL}\n"  # Add recovered finalization count.
        f"{BackgroundColors.GREEN}Resumable partial outputs: {BackgroundColors.CYAN}{preflight_summary['resumable_partial_outputs']}{Style.RESET_ALL}\n"  # Add resumable partial output count.
        f"{BackgroundColors.GREEN}Characters reused from persisted output: {BackgroundColors.CYAN}{reused_characters:,}{Style.RESET_ALL}\n"  # Add prior-run reusable character count.
        f"{BackgroundColors.GREEN}Source candidates: {BackgroundColors.CYAN}{preflight_summary['source_candidates']}{Style.RESET_ALL}\n"  # Add source candidate count.
        f"{BackgroundColors.GREEN}Existing translations skipped: {BackgroundColors.CYAN}{preflight_summary['existing_skipped']}{Style.RESET_ALL}\n"  # Add complete existing-output skip count.
        f"{BackgroundColors.GREEN}Target-language files skipped: {BackgroundColors.CYAN}{preflight_summary['target_language_skipped']}{Style.RESET_ALL}\n"  # Add target-language source skip count.
        f"{BackgroundColors.GREEN}Generated files skipped: {BackgroundColors.CYAN}{preflight_summary['generated_skipped']}{Style.RESET_ALL}\n"  # Add generated companion skip count.
        f"{BackgroundColors.GREEN}Invalid-language outputs: {BackgroundColors.CYAN}{preflight_summary['invalid_language_outputs']}{Style.RESET_ALL}\n"  # Add invalid-language output count.
        f"{BackgroundColors.GREEN}Mislabeled source files: {BackgroundColors.CYAN}{preflight_summary['mislabeled_source_files']}{Style.RESET_ALL}\n"  # Add mislabeled source count.
        f"{BackgroundColors.GREEN}Cleanup fallbacks: {BackgroundColors.CYAN}{preflight_summary['cleanup_fallbacks']}{Style.RESET_ALL}\n"  # Add source cleanup fallback count.
        f"{BackgroundColors.GREEN}Cleanup warnings: {BackgroundColors.CYAN}{preflight_summary['cleanup_warnings']}{Style.RESET_ALL}\n"  # Add translated cleanup warning count.
        f"{BackgroundColors.GREEN}Other files skipped: {BackgroundColors.CYAN}{other_skipped_files}{Style.RESET_ALL}\n"  # Add other skipped file count.
        f"{BackgroundColors.GREEN}Invalid files: {BackgroundColors.CYAN}{preflight_summary['invalid']}{Style.RESET_ALL}\n"  # Add invalid file count.
        f"{BackgroundColors.GREEN}Files failed: {BackgroundColors.CYAN}{failed_files}{Style.RESET_ALL}\n"  # Add failed planned file count.
        f"{BackgroundColors.GREEN}Characters translated this run: {BackgroundColors.CYAN}{translated_characters:,}/{total_planned_characters:,}{Style.RESET_ALL}"  # Add current-run translated character total.
    )  # Finish concise translation summary output.


def print_execution_time_summary(start_time: datetime.datetime, finish_time: datetime.datetime) -> None:
    """
    Prints execution start, finish, and elapsed time information.

    :param start_time: Program start datetime.
    :param finish_time: Program finish datetime.
    :return: None.
    """

    print(  # Output start, finish, and execution times.
        f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n"  # Add execution start time.
        f"{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n"  # Add execution finish time.
        f"{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"  # Add total execution duration.
    )  # Finish execution timing output.


def main() -> None:
    """
    Runs recursive subtitle preflight, translation, resume, persistence, and finalization.

    :return: None.
    """

    print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Subtitle (SRT) translation using DeepL API{BackgroundColors.GREEN} program!{Style.RESET_ALL}\n")  # Output the welcome message.
    start_time = datetime.datetime.now()  # Record program start time.

    ensure_env_file()  # Preserve existing environment-file initialization.

    input_dir = resolve_from_script_dir(INPUT_DIRECTORY)  # Resolve configured input from script location.
    output_dir = resolve_from_script_dir(OUTPUT_DIR)  # Resolve configured output from script location.
    use_configured_output = is_path_inside(input_dir, SCRIPT_DIR)  # Preserve configured output layout for internal inputs.

    if not input_dir.exists() or not input_dir.is_dir():  # Reject missing or invalid input directory.
        print(f"{BackgroundColors.RED}Input directory not found or is not a directory: {BackgroundColors.CYAN}{input_dir}{Style.RESET_ALL}")  # Output the existing input error message.
        return  # Exit before discovery.

    srt_files = discover_srt_files(input_dir)  # Snapshot SRT file paths recursively before translation.
    if not srt_files:  # Stop when recursive discovery found no SRT files.
        print(f"No SRT files were found in the input directory or any of its subdirectories: {input_dir}")  # Output existing empty-discovery message.
        return  # Exit without API initialization.

    translation_plan, preflight_summary = build_translation_plan(srt_files, input_dir, output_dir, use_configured_output)  # Build source-validated remaining translation and finalization work.
    planned_files = len(translation_plan)  # Count pending translation or finalization files.
    total_planned_characters = preflight_summary["total_characters"]  # Count only characters requiring new DeepL requests in this execution.
    reused_characters = sum(int(planned_file.get("resumed_characters", 0)) for planned_file in translation_plan)  # Count safely reused prior-run translated characters separately.
    other_skipped_files = preflight_summary["empty_skipped"] + preflight_summary["other_skipped"]  # Count non-language skipped files.
    print_translation_plan_summary(planned_files, total_planned_characters, reused_characters, preflight_summary)  # Print plan metrics outside the orchestration function.

    execution_summary = {"translated_files": 0, "finalized_files": 0, "failed_files": 0, "translated_characters": 0}  # Default execution counters for a zero-work plan.

    if not translation_plan:  # Preserve existing no-op preflight behavior.
        print(f"{BackgroundColors.YELLOW}{get_zero_plan_message(input_dir, preflight_summary)}{Style.RESET_ALL}")  # Print specific zero-plan summary.
    else:  # Execute remaining translation or finalization work.
        plan_execution_summary = execute_translation_plan(translation_plan, total_planned_characters, use_configured_output, output_dir, preflight_summary)  # Run translation and recovered finalization outside main.
        if plan_execution_summary is None:  # Preserve existing early exit when required API credentials are unavailable.
            return  # Leave persisted partial outputs untouched for the next run.
        execution_summary = plan_execution_summary  # Store completed plan execution counters for final reporting.

    finish_time = datetime.datetime.now()  # Record program finish time.
    print_translation_completion_summary(preflight_summary, planned_files, execution_summary["translated_files"], execution_summary["finalized_files"], execution_summary["failed_files"], reused_characters, execution_summary["translated_characters"], total_planned_characters, other_skipped_files)  # Print final translation counters outside main.
    print_execution_time_summary(start_time, finish_time)  # Print execution timing outside main.
    print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}")  # Output end-of-program message.

    atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None  # Register completion sound using existing configuration behavior.



if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
