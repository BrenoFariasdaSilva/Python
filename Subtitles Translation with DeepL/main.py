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
from typing import Any, Dict, List, Tuple  # For typed account, progress, and subtitle structures


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
INPUT_DIRECTORY = f"./Input/"  # Directory containing the input SRT files
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
    file_line = f"File    [{build_progress_bar(file_done, file_total)}] {file_percent:5.1f}% | {file_done:,}/{file_total:,} chars | ETA {file_eta}"  # Build file progress line
    overall_line = f"Overall [{build_progress_bar(overall_done, overall_total)}] {overall_percent:5.1f}% | {overall_done:,}/{overall_total:,} chars | Files {progress_state['completed_files']}/{progress_state['total_files']} | ETA {overall_eta}"  # Build overall progress line

    if interactive:
        stream = sys.__stdout__  # Write directly to terminal for in-place updates
        if progress_state.get("progress_visible"):
            stream.write("\033[F\033[K\033[F\033[K")  # Clear previous two progress lines
        stream.write(f"{BackgroundColors.GREEN}{file_line}{Style.RESET_ALL}\n{BackgroundColors.CYAN}{overall_line}{Style.RESET_ALL}\n")  # Draw current progress lines
        stream.flush()  # Flush terminal output
        progress_state["progress_visible"] = True  # Mark progress as visible
    else:
        print(file_line)  # Plain snapshot for redirected output
        print(overall_line)  # Plain snapshot for redirected output

    progress_state["last_snapshot_time"] = now  # Store snapshot time


def print_progress_event(progress_state: Dict[str, Any] | None, message: str) -> None:
    """
    Prints an event without corrupting active progress bars.

    :param progress_state: Shared progress state.
    :param message: Event message.
    :return: None
    """

    if progress_state and progress_state.get("interactive") and progress_state.get("progress_visible"):
        stream = sys.__stdout__  # Direct terminal stream
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


def build_translation_plan(srt_files: List[Path], input_dir: Path, output_dir: Path, use_configured_output: bool) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    """
    Builds the non-destructive translation plan.

    :param srt_files: Discovered SRT files.
    :param input_dir: Resolved input directory.
    :param output_dir: Resolved output directory.
    :param use_configured_output: Whether configured output layout applies.
    :return: Tuple containing plan entries and summary counts.
    """

    plan = []  # Store pending translation work
    records = []  # Store valid discovered SRT metadata before source/output dedupe
    records_by_path = {}  # Map resolved paths to discovered records
    summary = {"discovered": len(srt_files), "source_candidates": 0, "generated_skipped": 0, "existing_skipped": 0, "target_language_skipped": 0, "empty_skipped": 0, "invalid": 0, "cleanup_fallbacks": 0, "cleanup_warnings": 0, "invalid_language_outputs": 0, "mislabeled_source_files": 0, "other_skipped": 0, "total_characters": 0}  # Store preflight counts

    for srt_file in srt_files:  # Analyze each discovered SRT
        current_srt_path = srt_file.resolve()  # Resolve source path
        if is_generated_srt_file(current_srt_path):
            summary["other_skipped"] += 1  # Count internal files separately from generated outputs
            continue  # Internal temporary or backup files are not source candidates

        output_file = get_translated_output_file(current_srt_path, input_dir, output_dir, use_configured_output)  # Resolve expected output without chaining target suffixes

        try:
            source_lines = read_srt(current_srt_path)  # Read source SRT
            srt_lines = source_lines  # Default to source lines
            removed_entry_count = 0  # Default cleanup counts
            mixed_cleaned_entry_count = 0  # Default cleanup counts
            cleanup_fallback = False  # Track valid source translated without cleanup after cleanup validation failure
            if not has_valid_srt_structure(source_lines):
                summary["invalid"] += 1  # Count genuinely invalid source structure
                print(f"{BackgroundColors.RED}Invalid SRT structure: {BackgroundColors.CYAN}{current_srt_path}{Style.RESET_ALL}")  # Log invalid source
                continue
            if DESCRIPTIVE_SUBTITLES_REMOVAL:
                cleaned_lines, cleaned_removed_entry_count, cleaned_mixed_entry_count = clean_descriptive_subtitle_lines(source_lines)  # Plan cleanup without writing
                if has_valid_srt_structure(cleaned_lines):
                    srt_lines = cleaned_lines  # Use valid cleaned representation for all later processing
                    removed_entry_count = cleaned_removed_entry_count  # Preserve cleanup metadata for valid cleanup
                    mixed_cleaned_entry_count = cleaned_mixed_entry_count  # Preserve cleanup metadata for valid cleanup
                else:
                    cleanup_fallback = True  # Keep original valid source when cleanup breaks structure

            translatable_character_count = count_translatable_characters(srt_lines)  # Count exact DeepL text blocks
            if translatable_character_count == 0:
                summary["empty_skipped"] += 1  # Empty after cleanup is not pending translation
                print(f"{BackgroundColors.YELLOW}{current_srt_path.name} contains no translatable dialogue after SDH cleanup.{Style.RESET_ALL}")  # Log empty skip
                continue

            is_target_language, detection_conclusive, detected_language_label = detect_cleaned_subtitle_language(srt_lines, TARGET_LANG)  # Offline language detection
            record = {"source_path": current_srt_path, "output_file": output_file, "lines": srt_lines, "characters": translatable_character_count, "removed_entries": removed_entry_count, "mixed_cleaned_entries": mixed_cleaned_entry_count, "cleanup_fallback": cleanup_fallback, "detection_conclusive": detection_conclusive, "detected_language_label": detected_language_label, "is_target_language": is_target_language, "filename_has_generated_marker": has_generated_filename_marker(current_srt_path), "family_key": get_srt_family_key(current_srt_path)}  # Store content-based classification record
            records.append(record)  # Keep record for family dedupe
            records_by_path[current_srt_path] = record  # Map by resolved path
        except Exception as e:
            summary["invalid"] += 1  # Count unreadable or invalid preflight file
            print(f"{BackgroundColors.RED}Invalid preflight file: {BackgroundColors.CYAN}{current_srt_path}{BackgroundColors.RED} - {e}{Style.RESET_ALL}")  # Log preflight failure

    records_by_family = {}  # Group source/output family members
    for record in records:
        records_by_family.setdefault(record["family_key"], []).append(record)  # Group related filenames together

    for family_records in records_by_family.values():  # Build one translation decision per source/output family
        family_records.sort(key=lambda record: str(record["source_path"]).lower())  # Keep deterministic selection
        source_records = [record for record in family_records if not record["filename_has_generated_marker"]]  # Prefer clean source filenames
        source_record = source_records[0] if source_records else None  # Pick unique source candidate when present

        if source_record:
            summary["source_candidates"] += 1  # Count unique source family
            output_file = source_record["output_file"]  # Expected translated output
            output_record = records_by_path.get(output_file)  # Existing output if found in discovery snapshot
            extra_records = [record for record in family_records if record is not source_record and record is not output_record]  # Avoid duplicate family work

            if source_record["is_target_language"]:
                summary["target_language_skipped"] += 1  # Source already target language
                summary["generated_skipped"] += sum(1 for record in extra_records if record["is_target_language"])  # Count valid generated companions
                continue

            if output_record and output_record is not source_record:
                if output_record["is_target_language"] and is_translated_output_complete(source_record["lines"], output_file):
                    summary["existing_skipped"] += 1  # Valid generated output completes this source
                    summary["generated_skipped"] += 1  # Existing generated file excluded from independent work
                    summary["generated_skipped"] += sum(1 for record in extra_records if record["is_target_language"])  # Count valid generated companions
                    print(f"{BackgroundColors.YELLOW}Skipping already complete translation: {BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}")  # Log complete skip
                    continue

                summary["invalid_language_outputs"] += 1  # Existing output is present but not valid target-language content
                print(f"{BackgroundColors.YELLOW}Existing target output is not in {BackgroundColors.CYAN}{TARGET_LANG}{BackgroundColors.YELLOW} and will be regenerated:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}")  # Log regeneration
            elif is_complete_target_language_output(source_record["lines"], output_file)[0]:
                summary["existing_skipped"] += 1  # Output outside discovery snapshot still completes source
                print(f"{BackgroundColors.YELLOW}Skipping already complete translation: {BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}")  # Log complete skip
                continue

            summary["generated_skipped"] += sum(1 for record in extra_records if record["is_target_language"])  # Count valid generated companions without planning them
            summary["invalid_language_outputs"] += sum(1 for record in extra_records if not record["is_target_language"])  # Track invalid generated companions
            if source_record["cleanup_fallback"]:
                summary["cleanup_fallbacks"] += 1  # Count planned best-effort cleanup fallback separately from invalid files
                print(f"{BackgroundColors.YELLOW}SDH cleanup failed structural validation. Original subtitle will be translated:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{source_record['source_path']}{Style.RESET_ALL}")  # Log cleanup fallback
            plan.append(source_record)  # Add pending translation work
            summary["total_characters"] += source_record["characters"]  # Add only planned translation characters
            continue

        target_language_records = [record for record in family_records if record["is_target_language"]]  # Generated-looking files already in target language
        non_target_records = [record for record in family_records if not record["is_target_language"]]  # Generated-looking files requiring translation or regeneration

        if not non_target_records:
            summary["target_language_skipped"] += len(target_language_records)  # Valid target-language SRTs consume no quota
            summary["generated_skipped"] += len(target_language_records)  # Generated-looking files excluded from independent translation
            continue

        source_record = non_target_records[0]  # Treat misleading target-looking file as source when no real source exists
        summary["source_candidates"] += 1  # Count unique mislabeled source
        summary["mislabeled_source_files"] += 1  # Track misleading filename
        if source_record["detection_conclusive"]:
            print(f"{BackgroundColors.YELLOW}Filename indicates {BackgroundColors.CYAN}{TARGET_LANG}{BackgroundColors.YELLOW}, but cleaned content was detected as {BackgroundColors.CYAN}{source_record['detected_language_label']}{BackgroundColors.YELLOW}. Scheduling translation:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{source_record['source_path']}{Style.RESET_ALL}")  # Log mislabeled source
        else:
            print(f"{BackgroundColors.YELLOW}Language detection was inconclusive despite the target-language filename. Keeping file eligible for translation:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{source_record['source_path']}{Style.RESET_ALL}")  # Log conservative classification

        if source_record["cleanup_fallback"]:
            summary["cleanup_fallbacks"] += 1  # Count planned best-effort cleanup fallback separately from invalid files
            print(f"{BackgroundColors.YELLOW}SDH cleanup failed structural validation. Original subtitle will be translated:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{source_record['source_path']}{Style.RESET_ALL}")  # Log cleanup fallback
        plan.append(source_record)  # Add pending translation work
        summary["total_characters"] += source_record["characters"]  # Add only planned translation characters
        for record in family_records:
            if record is source_record:
                continue
            if record["is_target_language"]:
                summary["target_language_skipped"] += 1  # Valid generated companion
                summary["generated_skipped"] += 1  # Excluded from independent translation
            else:
                summary["invalid_language_outputs"] += 1  # Non-target generated-looking duplicate in same family

    return plan, summary  # Return plan and counts


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


def get_remaining_characters(translator):
    """
    Checks remaining characters available in DeepL free API plan.

    :param translator: DeepL translator client
    :return: Number of remaining characters or None if unlimited/unknown
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Checking remaining characters in DeepL API...{Style.RESET_ALL}"
    )  # Output the verbose message

    usage = translator.get_usage()  # Get usage information from DeepL API

    if usage.character.valid:  # If character usage information is valid
        remaining = usage.character.limit - usage.character.count  # Calculate remaining characters
        return remaining  # Return remaining characters

    return None  # Return None if unlimited/unknown


def create_deepl_client(account_name: str, api_key: str) -> deepl.DeepLClient:
    """
    Creates a DeepL client for a named account.

    :param account_name: DeepL account name used for logging.
    :param api_key: DeepL API key used to create the client.
    :return: DeepL client instance.
    """

    verbose_output(true_string=f"{BackgroundColors.GREEN}Using DeepL account: {BackgroundColors.CYAN}{account_name}{Style.RESET_ALL}")  # Log account name only
    return deepl.DeepLClient(auth_key=api_key)  # Create client without exposing the API key


def translate_text_block(text_block: str, account_items: List[Tuple[str, str]], active_account_index: int, translators: Dict[str, deepl.DeepLClient], progress_state: Dict[str, Any] | None = None) -> Tuple[List[str], int]:
    """
    Translates a block of text using the DeepL API, respecting remaining characters limit.

    :param text_block: String containing multiple lines to translate
    :param account_items: Ordered list of DeepL account names and API keys.
    :param active_account_index: Index for the currently active account.
    :param translators: DeepL clients already created for this execution.
    :param progress_state: Optional shared progress state for clean event logging.
    :return: Tuple containing translated lines and active account index.
    """

    verbose_output(f"{BackgroundColors.GREEN}Translating text block...{Style.RESET_ALL}")  # Output the verbose message

    attempt_counts = {account_name: 0 for account_name, _ in account_items}  # Track quota attempts for this pending block only
    total_quota_attempts = 0  # Count quota attempts for this pending block
    maximum_quota_attempts = len(account_items) * 2  # Require two quota attempts per account before stopping
    second_cycle_logged = False  # Log second circular pass once per pending block

    while total_quota_attempts < maximum_quota_attempts:  # Retry same block circularly until translated or safely exhausted
        account_name, api_key = account_items[active_account_index]  # Select current active account
        if account_name not in translators:  # Reuse existing client per account
            translators[account_name] = create_deepl_client(account_name, api_key)  # Create client for selected account
        translator = translators[account_name]  # Select cached client for usage and translation

        quota_failed = False  # Track one quota attempt without double-counting
        try:
            remaining_chars = get_remaining_characters(translator)  # Read remaining characters
        except deepl.QuotaExceededException:
            quota_failed = True  # Count this verified quota failure once
            print_progress_event(progress_state, f"{BackgroundColors.YELLOW}DeepL account {BackgroundColors.CYAN}{account_name}{BackgroundColors.YELLOW} quota exhausted. Trying next account.{Style.RESET_ALL}")  # Log quota-only rotation
            remaining_chars = 0  # Keep variable defined after quota failure

        if not quota_failed and remaining_chars is not None and len(text_block) > remaining_chars:  # Detect insufficient allowance before translation
            quota_failed = True  # Count this verified quota failure once
            print_progress_event(progress_state, f"{BackgroundColors.YELLOW}DeepL account {BackgroundColors.CYAN}{account_name}{BackgroundColors.YELLOW} has insufficient quota for block size {BackgroundColors.CYAN}{len(text_block)}{BackgroundColors.YELLOW}. Trying next account.{Style.RESET_ALL}")  # Log quota-only account skip

        if quota_failed:
            attempt_counts[account_name] += 1  # Count this account's quota attempt for the pending block
            total_quota_attempts += 1  # Count one verified quota attempt
            if all(attempt_count >= 1 for attempt_count in attempt_counts.values()) and not second_cycle_logged and total_quota_attempts < maximum_quota_attempts:
                print_progress_event(progress_state, f"{BackgroundColors.YELLOW}All DeepL accounts were attempted once for the current block. Starting the second circular attempt.{Style.RESET_ALL}")  # Log second cycle
                second_cycle_logged = True  # Avoid duplicate second-cycle log
            if total_quota_attempts >= maximum_quota_attempts:
                break  # Stop after two quota attempts per account

            previous_account_name = account_name  # Store account before circular advancement
            active_account_index = (active_account_index + 1) % len(account_items)  # Advance circularly to next account
            next_account_name = account_items[active_account_index][0]  # Read next account name for logging
            if len(account_items) == 1:
                print_progress_event(progress_state, f"{BackgroundColors.YELLOW}Retrying DeepL account {BackgroundColors.CYAN}{next_account_name}{BackgroundColors.YELLOW} for the second quota attempt.{Style.RESET_ALL}")  # Log single-account retry
            elif previous_account_name != next_account_name:
                print_progress_event(progress_state, f"{BackgroundColors.YELLOW}Switching DeepL account from {BackgroundColors.CYAN}{previous_account_name}{BackgroundColors.YELLOW} to {BackgroundColors.CYAN}{next_account_name}{Style.RESET_ALL}")  # Log circular account switch
            continue  # Retry exact same untranslated block with next account

        try:  # Perform translation
            result = translator.translate_text(text_block, target_lang=TARGET_LANG)  # Let DeepL auto-detect the source language
            if result is not None and hasattr(result, "text") and result.text:  # Ensure result is valid
                return result.text.split("\n"), active_account_index  # Return translated lines and current account
            else:
                return text_block.split("\n"), active_account_index  # Fallback to original lines
        except deepl.QuotaExceededException:
            attempt_counts[account_name] += 1  # Count this verified quota failure once
            total_quota_attempts += 1  # Count one verified quota attempt
            print_progress_event(progress_state, f"{BackgroundColors.YELLOW}DeepL account {BackgroundColors.CYAN}{account_name}{BackgroundColors.YELLOW} quota exhausted. Trying next account.{Style.RESET_ALL}")  # Log quota-only rotation
            if all(attempt_count >= 1 for attempt_count in attempt_counts.values()) and not second_cycle_logged and total_quota_attempts < maximum_quota_attempts:
                print_progress_event(progress_state, f"{BackgroundColors.YELLOW}All DeepL accounts were attempted once for the current block. Starting the second circular attempt.{Style.RESET_ALL}")  # Log second cycle
                second_cycle_logged = True  # Avoid duplicate second-cycle log
            if total_quota_attempts >= maximum_quota_attempts:
                break  # Stop after two quota attempts per account

            previous_account_name = account_name  # Store account before circular advancement
            active_account_index = (active_account_index + 1) % len(account_items)  # Advance circularly to next account
            next_account_name = account_items[active_account_index][0]  # Read next account name for logging
            if len(account_items) == 1:
                print_progress_event(progress_state, f"{BackgroundColors.YELLOW}Retrying DeepL account {BackgroundColors.CYAN}{next_account_name}{BackgroundColors.YELLOW} for the second quota attempt.{Style.RESET_ALL}")  # Log single-account retry
            elif previous_account_name != next_account_name:
                print_progress_event(progress_state, f"{BackgroundColors.YELLOW}Switching DeepL account from {BackgroundColors.CYAN}{previous_account_name}{BackgroundColors.YELLOW} to {BackgroundColors.CYAN}{next_account_name}{Style.RESET_ALL}")  # Log circular account switch
            continue  # Continue with next account
        except Exception as e:  # Handle any non-quota translation error
            print_progress_event(progress_state, f"{BackgroundColors.RED}Translation failed: {e}. Returning original lines.{Style.RESET_ALL}")
            return text_block.split("\n"), active_account_index  # Return original lines on failure

    attempted_accounts = ", ".join(account_name for account_name, _ in account_items)  # Build safe account-name summary
    raise RuntimeError(f"All configured DeepL accounts were attempted at least twice and none has sufficient quota for pending block size {len(text_block)}. Accounts attempted: {attempted_accounts}")


def translate_srt_lines(srt_file, lines, translatable_character_count: int, account_items: List[Tuple[str, str]], active_account_index: int, translators: Dict[str, deepl.DeepLClient], progress_state: Dict[str, Any] | None = None) -> Tuple[List[str], int]:
    """
    Translates lines from an SRT file using DeepL API, keeping timing and index lines unchanged.

    :param srt_file: Path to the SRT file (for logging purposes).
    :param lines: List of SRT lines.
    :param translatable_character_count: Total cleaned characters eligible for DeepL translation.
    :param account_items: Ordered list of DeepL account names and API keys.
    :param active_account_index: Process-wide active account index.
    :param translators: DeepL clients reused across files.
    :param progress_state: Optional shared progress state.
    :return: Tuple containing translated lines and active account index.
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Translating SRT lines from file: {BackgroundColors.CYAN}{srt_file}{Style.RESET_ALL}"
    )  # Output verbose message for translating SRT lines

    translated_lines = []  # Initialize empty list for storing translated lines
    buffer = []  # Initialize empty buffer for batching subtitle text lines
    translated_character_count = 0  # Track completed translation workload

    filename = getattr(srt_file, "name", str(srt_file))  # Extract filename string for progress display

    for line in lines:  # Iterate through each line in the SRT file
        stripped = line.strip()  # Remove leading and trailing whitespace from the current line

        if (
            stripped == "" or stripped.replace(":", "").replace(",", "").isdigit() or "-->" in line
        ):  # Verify if the line is empty, a sequence index, or a timing marker
            if buffer:  # Verify if the translation buffer contains pending text lines
                text_block = "\n".join(buffer)  # Build exact text block for DeepL
                try:
                    translated, active_account_index = translate_text_block(text_block, account_items, active_account_index, translators, progress_state)  # Translate buffered text lines as one block
                except RuntimeError as e:
                    remaining_characters = translatable_character_count - translated_character_count  # Count untranslated workload
                    raise RuntimeError(f"Error: {e}. File: {filename}. Remaining: {remaining_characters:,} characters.") from None
                if translated is None:  # Verify if translation returned None instead of a result
                    translated = buffer  # Fall back to the original buffer lines on failed translation
                translated_lines.extend(translated)  # Append translated lines to the result list
                translated_character_count += len(text_block)  # Count block after successful translation path
                if progress_state:
                    progress_state["file_translated_characters"] += len(text_block)  # Advance current-file progress after success
                    progress_state["overall_translated_characters"] += len(text_block)  # Advance overall progress after success
                    render_translation_progress(progress_state)  # Redraw progress after successful block
                buffer = []  # Reset buffer after processing the current block
            translated_lines.append(line.rstrip("\n"))  # Append the timing or index line to result unchanged
        else:  # Handle regular subtitle text lines
            buffer.append(stripped)  # Append the stripped text line to the translation buffer

    if buffer:  # Verify if the buffer still contains unprocessed text lines after the loop
        text_block = "\n".join(buffer)  # Build exact final text block for DeepL
        try:
            translated, active_account_index = translate_text_block(text_block, account_items, active_account_index, translators, progress_state)  # Translate the remaining buffered text lines
        except RuntimeError as e:
            remaining_characters = translatable_character_count - translated_character_count  # Count untranslated workload
            raise RuntimeError(f"Error: {e}. File: {filename}. Remaining: {remaining_characters:,} characters.") from None
        if translated is None:  # Verify if translation returned None for the remaining block
            translated = buffer  # Fall back to the original buffer lines on failed translation
        translated_lines.extend(translated)  # Append the remaining translated lines to the result list
        translated_character_count += len(text_block)  # Count final block after successful translation path
        if progress_state:
            progress_state["file_translated_characters"] += len(text_block)  # Advance current-file progress after final success
            progress_state["overall_translated_characters"] += len(text_block)  # Advance overall progress after final success
            render_translation_progress(progress_state)  # Redraw progress after successful block

    return translated_lines, active_account_index  # Return translated lines and preserved active account index


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


def cleanup_saved_translation(output_file: Path) -> bool:
    """
    Attempts SDH cleanup on a saved translated SRT without risking the valid output.

    :param output_file: Saved translated SRT path.
    :return: True when cleanup was skipped because it produced invalid structure.
    """

    output_lines = output_file.read_text(encoding="utf-8").splitlines()  # Read valid translated output
    cleaned_lines, removed_entry_count, mixed_cleaned_entry_count = clean_descriptive_subtitle_lines(output_lines)  # Clean translated output in memory
    if not removed_entry_count and not mixed_cleaned_entry_count:
        return False  # No translated cleanup needed

    if not has_valid_srt_structure(cleaned_lines) or count_translatable_characters(cleaned_lines) == 0:
        print(f"{BackgroundColors.YELLOW}Translated SRT saved successfully, but SDH cleanup was skipped because it produced an invalid structure:{Style.RESET_ALL}\n{BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}")  # Preserve valid translated output
        return True  # Cleanup warning emitted

    write_srt_lines_atomic(output_file, cleaned_lines)  # Replace only with validated cleaned translation
    return False  # Cleanup succeeded


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


def main():
    """
    Main function.

    Processes all .srt files in the INPUT_DIRECTORY. Each file is translated using DeepL API
    from DeepL-detected source language to Brazilian Portuguese. Translated files are saved in the same directory
    with '_ptBR' appended to the filename.

    :param: None
    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Subtitle (SRT) translation using DeepL API{BackgroundColors.GREEN} program!{Style.RESET_ALL}\n"
    )  # Output the welcome message
    start_time = datetime.datetime.now()  # Get the start time of the program

    ensure_env_file()  # Ensure .env file exists

    input_dir = resolve_from_script_dir(INPUT_DIRECTORY)  # Resolve configured input from script location
    output_dir = resolve_from_script_dir(OUTPUT_DIR)  # Resolve configured output from script location
    use_configured_output = is_path_inside(input_dir, SCRIPT_DIR)  # Internal inputs keep configured output layout

    if not input_dir.exists() or not input_dir.is_dir():  # If the input directory does not exist or is invalid
        print(f"{BackgroundColors.RED}Input directory not found or is not a directory: {BackgroundColors.CYAN}{input_dir}{Style.RESET_ALL}")  # Output the error message
        return  # Exit the program

    srt_files = discover_srt_files(input_dir)  # Snapshot SRT file paths recursively before translation

    if not srt_files:  # If no SRT files were found
        print(f"No SRT files were found in the input directory or any of its subdirectories: {input_dir}")  # Output message
        return  # Exit the program

    translation_plan, preflight_summary = build_translation_plan(srt_files, input_dir, output_dir, use_configured_output)  # Build non-destructive plan before DeepL
    planned_files = len(translation_plan)  # Count pending files
    total_planned_characters = preflight_summary["total_characters"]  # Count pending characters only
    other_skipped_files = preflight_summary["empty_skipped"] + preflight_summary["other_skipped"]  # Count non-language skipped files
    print(f"{BackgroundColors.GREEN}Translation plan: {BackgroundColors.CYAN}{planned_files}{BackgroundColors.GREEN} files | {BackgroundColors.CYAN}{total_planned_characters:,}{BackgroundColors.GREEN} characters | {BackgroundColors.CYAN}{preflight_summary['existing_skipped']}{BackgroundColors.GREEN} existing translations skipped | {BackgroundColors.CYAN}{preflight_summary['target_language_skipped']}{BackgroundColors.GREEN} target-language files skipped | {BackgroundColors.CYAN}{preflight_summary['invalid_language_outputs']}{BackgroundColors.GREEN} invalid-language outputs | {BackgroundColors.CYAN}{preflight_summary['cleanup_fallbacks']}{BackgroundColors.GREEN} cleanup fallbacks | {BackgroundColors.CYAN}{preflight_summary['invalid']}{BackgroundColors.GREEN} invalid files{Style.RESET_ALL}")  # Print preflight summary

    translated_files = 0  # Count files translated in this run
    failed_files = 0  # Count failed planned files
    translated_characters = 0  # Count successfully translated characters

    if not translation_plan:
        print(f"{BackgroundColors.YELLOW}{get_zero_plan_message(input_dir, preflight_summary)}{Style.RESET_ALL}")  # Print no-op summary
    else:
        if use_configured_output and not output_dir.exists():  # If configured output is needed and missing
            output_dir.mkdir(parents=True, exist_ok=True)  # Create output directory only when work exists

        if not get_api_keys():  # Load DeepL API keys only after pending work exists
            print(
                f"{BackgroundColors.RED}DEEPL_API_KEYS not found or invalid in .env file. Please set it before running the program.{Style.RESET_ALL}"
            )  # Output error message
            return  # Exit the program

        account_items = list(DEEPL_API_KEYS.items())  # Preserve configured account order across files
        active_account_index = 0  # Process-wide active account index
        translators = {}  # Process-wide DeepL clients reused across files
        progress_state = {"interactive": is_interactive_output(), "overall_total_characters": total_planned_characters, "overall_translated_characters": 0, "overall_start_time": time.monotonic(), "total_files": planned_files, "completed_files": 0, "progress_visible": False, "last_snapshot_time": 0.0}  # Shared progress state

        for file_number, planned_file in enumerate(translation_plan, start=1):  # Translate each planned file
            current_srt_path = planned_file["source_path"]  # Source path
            output_file = planned_file["output_file"]  # Output path
            srt_lines = planned_file["lines"]  # Planned cleaned lines
            translatable_character_count = planned_file["characters"]  # Planned exact character count
            filename = current_srt_path.name  # Display filename

            if planned_file["removed_entries"] or planned_file["mixed_cleaned_entries"]:  # Log concise cleanup summary when cleanup changed content
                write_srt_lines_atomic(current_srt_path, srt_lines)  # Preserve existing source cleanup behavior after preflight
                print(f"{BackgroundColors.YELLOW}SDH cleanup: {BackgroundColors.CYAN}{filename}{BackgroundColors.YELLOW} removed {BackgroundColors.CYAN}{planned_file['removed_entries']}{BackgroundColors.YELLOW} entries, cleaned {BackgroundColors.CYAN}{planned_file['mixed_cleaned_entries']}{BackgroundColors.YELLOW} mixed entries.{Style.RESET_ALL}")  # Log cleanup summary
            if planned_file["cleanup_fallback"]:
                print(f"{BackgroundColors.YELLOW}Cleanup mode: Original subtitle content{Style.RESET_ALL}")  # Identify fallback source representation once

            if not planned_file["detection_conclusive"]:  # Continue normally when language detection is not reliable
                print(f"{BackgroundColors.YELLOW}Source language detection was inconclusive for {BackgroundColors.CYAN}{filename}{BackgroundColors.YELLOW}. DeepL will determine the source language during translation.{Style.RESET_ALL}")  # Log inconclusive detection

            output_file.parent.mkdir(parents=True, exist_ok=True)  # Ensure output directory exists for this file
            progress_state.update({"file_total_characters": translatable_character_count, "file_translated_characters": 0, "file_start_time": time.monotonic(), "progress_visible": False, "last_snapshot_time": 0.0})  # Reset file progress only
            print(f"{BackgroundColors.GREEN}File {BackgroundColors.CYAN}{file_number}/{planned_files}{BackgroundColors.GREEN}: {BackgroundColors.CYAN}{filename}{Style.RESET_ALL}")  # Print compact file header once
            print(f"{BackgroundColors.GREEN}Characters: {BackgroundColors.CYAN}{translatable_character_count:,}{Style.RESET_ALL}")  # Print character total once
            render_translation_progress(progress_state, force=True)  # Render 0% progress

            try:
                translated_lines, active_account_index = translate_srt_lines(current_srt_path, srt_lines, translatable_character_count, account_items, active_account_index, translators, progress_state)  # Translate SRT lines using DeepL API
            except RuntimeError as e:
                failed_files += 1  # Count failed planned file
                translated_characters = progress_state["overall_translated_characters"]  # Preserve partial successful character progress
                print_progress_event(progress_state, f"{BackgroundColors.RED}{e}{Style.RESET_ALL}")  # Log fatal quota exhaustion cleanly
                break  # Preserve existing stop-on-fatal-quota behavior

            if translated_lines and not has_valid_srt_structure(translated_lines):
                failed_files += 1  # Count invalid translated serialization as failed work
                print_progress_event(progress_state, f"{BackgroundColors.RED}Translated SRT structure is invalid and was not saved: {BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}")  # Preserve output safety
                continue
            progress_state["completed_files"] += 1  # Count fully translated file
            translated_files += 1  # Count successful file
            translated_characters = progress_state["overall_translated_characters"]  # Store successful character progress
            render_translation_progress(progress_state, force=True)  # Finalize successful file progress
            save_srt(translated_lines, output_file)  # Save the translated SRT to the output file
            if DESCRIPTIVE_SUBTITLES_REMOVAL and cleanup_saved_translation(output_file):
                preflight_summary["cleanup_warnings"] += 1  # Count skipped translated cleanup separately from translation failure

    finish_time = datetime.datetime.now()  # Get the finish time of the program
    print(
        f"\n{BackgroundColors.GREEN}Translation completed.{Style.RESET_ALL}\n\n"
        f"{BackgroundColors.GREEN}Files discovered: {BackgroundColors.CYAN}{preflight_summary['discovered']}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Files planned: {BackgroundColors.CYAN}{planned_files}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Files translated: {BackgroundColors.CYAN}{translated_files}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Source candidates: {BackgroundColors.CYAN}{preflight_summary['source_candidates']}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Existing translations skipped: {BackgroundColors.CYAN}{preflight_summary['existing_skipped']}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Target-language files skipped: {BackgroundColors.CYAN}{preflight_summary['target_language_skipped']}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Generated files skipped: {BackgroundColors.CYAN}{preflight_summary['generated_skipped']}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Invalid-language outputs: {BackgroundColors.CYAN}{preflight_summary['invalid_language_outputs']}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Mislabeled source files: {BackgroundColors.CYAN}{preflight_summary['mislabeled_source_files']}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Cleanup fallbacks: {BackgroundColors.CYAN}{preflight_summary['cleanup_fallbacks']}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Cleanup warnings: {BackgroundColors.CYAN}{preflight_summary['cleanup_warnings']}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Other files skipped: {BackgroundColors.CYAN}{other_skipped_files}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Invalid files: {BackgroundColors.CYAN}{preflight_summary['invalid']}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Files failed: {BackgroundColors.CYAN}{failed_files}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Characters translated: {BackgroundColors.CYAN}{translated_characters:,}/{total_planned_characters:,}{Style.RESET_ALL}"
    )  # Output concise translation summary
    print(
        f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"
    )  # Output start, finish, and execution times
    print(
        f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
    )  # Output end of program message

    (
        atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None
    )  # Register the play_sound function to be called when the program finishes


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
