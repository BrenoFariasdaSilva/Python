"""
================================================================================
Subtitle (SRT) Translation using DeepL API
================================================================================
Author      : Breno Farias da Silva
Created     : 2025-12-13
Description :
   This script translates subtitle files (SRT) from English to Brazilian Portuguese
   using the DeepL API. It processes all .srt files in the specified input directory,
   respecting API usage limits, and saves the translated files with a '_ptBR' suffix.

   Key features include:
      - Automatic loading of SRT files from a directory
      - Integration with DeepL API for translation
      - Respect for API free plan usage limits
      - Logging output to both terminal and file
      - Optional notification sound upon completion

Usage:
   1. Configure the INPUT_DIR and ensure DEEPL_API_KEYS is set in the .env file.
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
from colorama import Style  # For coloring the terminal
from dotenv import load_dotenv  # For loading environment variables from .env file
from lingua import LanguageDetectorBuilder  # For offline language detection before translation
from Logger import Logger  # For logging output to both terminal and file
from pathlib import Path  # For handling file paths
from shutil import copyfile  # For copying files
from typing import Dict, List, Set, Tuple  # For typed account and subtitle structures


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
INPUT_DIR = f"./Input"  # Directory containing the input SRT files
OUTPUT_DIR = Path("./Output")  # Base output directory
SOURCE_LANG = "EN"  # DeepL source language code
TARGET_LANG = "PT-BR"  # DeepL target language code
SCRIPT_DIR = Path(__file__).resolve().parent  # Directory containing this script
LANGUAGE_DETECTION_MIN_LETTERS = 80  # Avoid classifying tiny or numeric-only subtitles
LANGUAGE_DETECTION_MAX_SAMPLE_CHARS = 4000  # Enough dialogue for detection without scanning huge files
TARGET_LANGUAGE_MIN_CONFIDENCE = 0.75  # Require strong target-language confidence before skipping
TARGET_LANGUAGE_MIN_MARGIN = 0.20  # Require target language to clearly beat the next candidate
TARGET_LANGUAGE_MIN_SHARE = 0.80  # Require target language to dominate mixed-language content
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


def parse_srt_blocks(lines: List[str]) -> List[Tuple[str, str, List[str]]]:
    """
    Parses SRT lines into index, timing, and text-line blocks.

    :param lines: SRT lines to parse.
    :return: List of parsed SRT blocks.
    """

    blocks = []  # Store parsed subtitle blocks
    block = []  # Store current subtitle block

    for line in lines + [""]:  # Add sentinel blank line to flush final block
        stripped = line.strip()  # Normalize current line
        if stripped:
            block.append(stripped)  # Add non-empty line to current block
            continue

        if not block:
            continue

        if len(block) < 3 or not block[0].isdigit() or "-->" not in block[1]:  # Reject malformed SRT block
            return []  # Return empty result for malformed subtitles

        text_lines = [text_line.strip() for text_line in block[2:] if text_line.strip()]  # Normalize translatable text lines
        if not text_lines:
            return []  # Return empty result for blocks without text

        blocks.append((block[0], block[1], text_lines))  # Store parsed block
        block = []  # Reset current subtitle block

    return blocks  # Return parsed subtitle blocks


def strip_html_tags(text: str) -> str:
    """
    Removes simple HTML tags from text for cue classification.

    :param text: Text that may contain HTML tags.
    :return: Text without HTML tags.
    """

    return re.sub(r"<[^>]+>", "", text)  # Remove simple inline HTML tags


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
    tagless = strip_html_tags(stripped).strip()  # Remove tags for line-level classification

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
        stripped,
    )  # Remove inline descriptive cue spans only
    cleaned = re.sub(r"<([^>\s]+)[^>]*>\s*</\1>", "", cleaned)  # Remove empty HTML tags left by cue removal

    cleaned = " ".join(cleaned.split())  # Normalize spacing after cue removal

    return cleaned, cleaned != stripped  # Return cleaned text and change flag


def serialize_srt_blocks(blocks: List[Tuple[str, str, List[str]]]) -> List[str]:
    """
    Serializes parsed SRT blocks back into lines.

    :param blocks: Parsed subtitle blocks.
    :return: Serialized SRT lines.
    """

    lines = []  # Store serialized lines

    for index, timing, text_lines in blocks:  # Serialize each subtitle block
        lines.extend([index, timing])  # Add index and timing lines
        lines.extend(text_lines)  # Add subtitle text lines
        lines.append("")  # Add SRT block separator

    return lines  # Return serialized SRT lines


def count_translatable_characters(lines: List[str]) -> int:
    """
    Counts characters that will be sent to DeepL.

    :param lines: Cleaned SRT lines.
    :return: Total translatable character count.
    """

    return sum(len("\n".join(text_lines)) for _, _, text_lines in parse_srt_blocks(lines))  # Match translation block counting


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
    blocks = parse_srt_blocks(original_lines)  # Parse source before cue removal

    if not blocks:
        return original_lines, 0, 0  # Preserve malformed input behavior

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
    if cleaned_lines and not parse_srt_blocks(cleaned_lines):  # Validate serialized cleaned subtitles before replacing
        raise ValueError(f"Invalid SRT structure after SDH cleanup: {file_path}")  # Stop before source replacement

    temp_file = Path(file_path).with_suffix(Path(file_path).suffix + ".tmp")  # Build same-folder temp file
    temp_file.write_text("\n".join(cleaned_lines), encoding="utf-8")  # Write cleaned subtitles atomically
    os.replace(temp_file, file_path)  # Replace source file after successful write

    return cleaned_lines, removed_entry_count, mixed_cleaned_entry_count  # Return cleaned lines and cleanup counts


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


def translate_text_block(text_block: str, account_items: List[Tuple[str, str]], active_account_index: int, exhausted_accounts: Set[str], translators: Dict[str, deepl.DeepLClient]) -> Tuple[List[str], int]:
    """
    Translates a block of text using the DeepL API, respecting remaining characters limit.

    :param text_block: String containing multiple lines to translate
    :param account_items: Ordered list of DeepL account names and API keys.
    :param active_account_index: Index for the currently active account.
    :param exhausted_accounts: Set of account names already exhausted during this execution.
    :param translators: DeepL clients already created for this execution.
    :return: Tuple containing translated lines and active account index.
    """

    verbose_output(f"{BackgroundColors.GREEN}Translating text block...{Style.RESET_ALL}")  # Output the verbose message

    for account_offset in range(len(account_items)):  # Try each configured account at most once for this block
        account_index = (active_account_index + account_offset) % len(account_items)  # Rotate in configured order
        account_name, api_key = account_items[account_index]  # Select account tuple

        if account_name in exhausted_accounts:  # Avoid accounts already proven unusable
            continue  # Continue with next account

        if account_index != active_account_index:  # Detect quota-driven account rotation
            previous_account_name = account_items[active_account_index][0]  # Read previous account name for logging
            print(
                f"{BackgroundColors.YELLOW}Switching DeepL account from {BackgroundColors.CYAN}{previous_account_name}{BackgroundColors.YELLOW} to {BackgroundColors.CYAN}{account_name}{Style.RESET_ALL}"
            )  # Log rotation without exposing API keys

        if account_name not in translators:  # Reuse existing client per account
            translators[account_name] = create_deepl_client(account_name, api_key)  # Create client for selected account
        translator = translators[account_name]  # Select cached client for usage and translation
        try:
            remaining_chars = get_remaining_characters(translator)  # Read remaining characters
        except deepl.QuotaExceededException:
            exhausted_accounts.add(account_name)  # Mark account exhausted after SDK usage response
            print(
                f"{BackgroundColors.YELLOW}DeepL account {BackgroundColors.CYAN}{account_name}{BackgroundColors.YELLOW} quota exhausted. Trying next account.{Style.RESET_ALL}"
            )  # Log quota-only rotation
            continue  # Continue with next account

        if remaining_chars is not None and len(text_block) > remaining_chars:  # Detect insufficient allowance before translation
            if remaining_chars <= 0:
                exhausted_accounts.add(account_name)  # Mark account exhausted for this execution
            print(
                f"{BackgroundColors.YELLOW}DeepL account {BackgroundColors.CYAN}{account_name}{BackgroundColors.YELLOW} has insufficient quota for block size {BackgroundColors.CYAN}{len(text_block)}{BackgroundColors.YELLOW}. Trying next account.{Style.RESET_ALL}"
            )  # Log quota-only account skip
            continue  # Continue with next account

        try:  # Perform translation
            result = translator.translate_text(text_block, source_lang=SOURCE_LANG, target_lang=TARGET_LANG)  # Translate text block
            if result is not None and hasattr(result, "text") and result.text:  # Ensure result is valid
                return result.text.split("\n"), account_index  # Return translated lines and current account
            else:
                return text_block.split("\n"), account_index  # Fallback to original lines
        except deepl.QuotaExceededException:
            exhausted_accounts.add(account_name)  # Mark account exhausted after SDK quota response
            print(
                f"{BackgroundColors.YELLOW}DeepL account {BackgroundColors.CYAN}{account_name}{BackgroundColors.YELLOW} quota exhausted. Trying next account.{Style.RESET_ALL}"
            )  # Log quota-only rotation
            continue  # Continue with next account
        except Exception as e:  # Handle any non-quota translation error
            print(f"{BackgroundColors.RED}Translation failed: {e}. Returning original lines.{Style.RESET_ALL}")
            return text_block.split("\n"), account_index  # Return original lines on failure

    raise RuntimeError("All configured DeepL accounts have insufficient quota for the pending subtitle block")


def translate_srt_lines(srt_file, lines, translatable_character_count: int):
    """
    Translates lines from an SRT file using DeepL API, keeping timing and index lines unchanged.

    :param srt_file: Path to the SRT file (for logging purposes).
    :param lines: List of SRT lines.
    :param translatable_character_count: Total cleaned characters eligible for DeepL translation.
    :return: List of translated lines.
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Translating SRT lines from file: {BackgroundColors.CYAN}{srt_file}{Style.RESET_ALL}"
    )  # Output verbose message for translating SRT lines

    account_items = list(DEEPL_API_KEYS.items())  # Preserve configured account order for deterministic rotation
    active_account_index = 0  # Start with the first configured account
    exhausted_accounts = set()  # Track accounts with insufficient quota during this execution
    translators = {}  # Reuse DeepL clients by account during this execution
    translated_lines = []  # Initialize empty list for storing translated lines
    buffer = []  # Initialize empty buffer for batching subtitle text lines
    translated_character_count = 0  # Track completed translation workload

    total_lines = len(lines)  # Store total line count for progress percentage calculation
    current_line = 0  # Initialize line counter for progress tracking
    filename = getattr(srt_file, "name", str(srt_file))  # Extract filename string for progress display
    real_stderr = sys.__stderr__ if sys.__stderr__ is not None else open(os.devnull, "w")  # Resolve original stderr to a non-None stream for in-place progress output

    for line in lines:  # Iterate through each line in the SRT file
        stripped = line.strip()  # Remove leading and trailing whitespace from the current line

        if (
            stripped == "" or stripped.replace(":", "").replace(",", "").isdigit() or "-->" in line
        ):  # Verify if the line is empty, a sequence index, or a timing marker
            if buffer:  # Verify if the translation buffer contains pending text lines
                text_block = "\n".join(buffer)  # Build exact text block for DeepL
                try:
                    translated, active_account_index = translate_text_block(text_block, account_items, active_account_index, exhausted_accounts, translators)  # Translate buffered text lines as one block
                except RuntimeError:
                    remaining_characters = translatable_character_count - translated_character_count  # Count untranslated workload
                    raise RuntimeError(f"Error: All configured DeepL accounts have insufficient quota to finish {filename}. Remaining: {remaining_characters:,} characters.") from None
                if translated is None:  # Verify if translation returned None instead of a result
                    translated = buffer  # Fall back to the original buffer lines on failed translation
                translated_lines.extend(translated)  # Append translated lines to the result list
                translated_character_count += len(text_block)  # Count block after successful translation path
                buffer = []  # Reset buffer after processing the current block
            translated_lines.append(line.rstrip("\n"))  # Append the timing or index line to result unchanged
        else:  # Handle regular subtitle text lines
            buffer.append(stripped)  # Append the stripped text line to the translation buffer

        current_line += 1  # Increment the processed line counter
        percent = int(current_line / total_lines * 100) if total_lines > 0 else 0  # Calculate progress as an integer percentage
        filled = percent // 10  # Calculate the number of filled segments in the progress bar
        bar = "#" * filled + "-" * (10 - filled)  # Build the visual progress bar string with filled and empty segments
        real_stderr.write(f"\r{BackgroundColors.GREEN}Processing: {BackgroundColors.CYAN}{filename}{BackgroundColors.GREEN} ({translatable_character_count:,} characters) [{bar}] {percent}%{Style.RESET_ALL}   ")  # Overwrite current terminal line with updated progress
        real_stderr.flush()  # Flush original stderr to force immediate display of progress

    if buffer:  # Verify if the buffer still contains unprocessed text lines after the loop
        text_block = "\n".join(buffer)  # Build exact final text block for DeepL
        try:
            translated, active_account_index = translate_text_block(text_block, account_items, active_account_index, exhausted_accounts, translators)  # Translate the remaining buffered text lines
        except RuntimeError:
            remaining_characters = translatable_character_count - translated_character_count  # Count untranslated workload
            raise RuntimeError(f"Error: All configured DeepL accounts have insufficient quota to finish {filename}. Remaining: {remaining_characters:,} characters.") from None
        if translated is None:  # Verify if translation returned None for the remaining block
            translated = buffer  # Fall back to the original buffer lines on failed translation
        translated_lines.extend(translated)  # Append the remaining translated lines to the result list
        translated_character_count += len(text_block)  # Count final block after successful translation path

    real_stderr.write("\n")  # Advance the terminal cursor to a new line after progress finishes
    real_stderr.flush()  # Flush original stderr to finalize the progress output

    return translated_lines  # Return the complete list of translated lines


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

    with open(output_file, "w", encoding="utf-8") as f:  # Open the output SRT file for writing
        f.write("\n".join(lines))  # Write translated lines to the file

    print(
        f"{BackgroundColors.GREEN}{success_message}: {BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}"
    )  # Output the saved file message


def calculate_execution_time(start_time, finish_time):
    """
    Calculates the execution time between start and finish times and formats it as hh:mm:ss.

    :param start_time: The start datetime object
    :param finish_time: The finish datetime object
    :return: String formatted as hh:mm:ss representing the execution time
    """

    delta = finish_time - start_time  # Calculate the time difference

    hours, remainder = divmod(delta.seconds, 3600)  # Calculate the hours, minutes and seconds
    minutes, seconds = divmod(remainder, 60)  # Calculate the minutes and seconds

    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"  # Format the execution time


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

    Processes all .srt files in the INPUT_DIR. Each file is translated using DeepL API
    from English to Brazilian Portuguese. Translated files are saved in the same directory
    with '_ptBR' appended to the filename.

    :param: None
    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Subtitle (SRT) translation using DeepL API{BackgroundColors.GREEN} program!{Style.RESET_ALL}\n"
    )  # Output the welcome message
    start_time = datetime.datetime.now()  # Get the start time of the program

    ensure_env_file()  # Ensure .env file exists

    api_keys_loaded = False  # Load DeepL API keys only for files that require translation

    input_dir = resolve_from_script_dir(INPUT_DIR)  # Resolve configured input from script location
    output_dir = resolve_from_script_dir(OUTPUT_DIR)  # Resolve configured output from script location
    use_configured_output = is_path_inside(input_dir, SCRIPT_DIR)  # Internal inputs keep configured output layout

    if not input_dir.exists():  # If the input directory does not exist
        input_dir.mkdir(parents=True, exist_ok=True)  # Create the input directory
        print(f"Input directory does not exist: {input_dir}")  # Output the error message
        return  # Exit the program

    if use_configured_output and not output_dir.exists():  # If configured output is needed and missing
        output_dir.mkdir(parents=True, exist_ok=True)  # Create the output directory

    srt_files = [f for f in input_dir.rglob("*.srt") if f.is_file()]  # List of SRT file paths (includes subdirectories)

    if not srt_files:  # If no SRT files were found
        print(f"No .srt files found in directory: {input_dir}")  # Output message
        return  # Exit the program

    for srt_file in srt_files:  # Iterate through each SRT file in the input directory
        current_srt_path = srt_file.resolve()  # Resolve the current source SRT safely
        srt_lines = read_srt(current_srt_path)  # Read SRT file into a list of lines

        if DESCRIPTIVE_SUBTITLES_REMOVAL:  # Verify if descriptive subtitle removal is enabled
            srt_lines, removed_entry_count, mixed_cleaned_entry_count = remove_descriptive_subtitles(current_srt_path)  # Clean SRT lines by removing descriptive text
            if removed_entry_count or mixed_cleaned_entry_count:  # Log concise cleanup summary when cleanup changed content
                print(f"{BackgroundColors.YELLOW}SDH cleanup: {BackgroundColors.CYAN}{current_srt_path.name}{BackgroundColors.YELLOW} removed {BackgroundColors.CYAN}{removed_entry_count}{BackgroundColors.YELLOW} entries, cleaned {BackgroundColors.CYAN}{mixed_cleaned_entry_count}{BackgroundColors.YELLOW} mixed entries.{Style.RESET_ALL}")  # Log cleanup summary

        cleaned_blocks = parse_srt_blocks(srt_lines)  # Validate cleaned SRT structure
        if srt_lines and not cleaned_blocks:  # Reject malformed cleaned subtitles
            print(f"{BackgroundColors.RED}Invalid SRT structure after SDH cleanup: {BackgroundColors.CYAN}{current_srt_path}{Style.RESET_ALL}")  # Log invalid cleaned file
            continue  # Continue with next SRT file

        translatable_character_count = count_translatable_characters(srt_lines)  # Count only cleaned subtitle text sent to DeepL
        filename = getattr(current_srt_path, "name", str(current_srt_path))  # Extract filename string for processing display
        print(f"{BackgroundColors.GREEN}Processing: {BackgroundColors.CYAN}{filename}{BackgroundColors.GREEN} ({translatable_character_count:,} characters){Style.RESET_ALL}")  # Log cleaned workload

        if use_configured_output:  # Internal configured input keeps project output organization
            relative_path = current_srt_path.relative_to(input_dir).parent  # Extract relative path from the input directory
            output_subdir = output_dir / relative_path  # Build the output subdirectory path
        else:  # External input writes each translation beside its source file
            output_subdir = current_srt_path.parent  # Use current source SRT directory independently

        output_subdir.mkdir(parents=True, exist_ok=True)  # Ensure the output subdirectory exists

        output_file = (output_subdir / f"{current_srt_path.stem}_ptBR.srt").resolve()  # Build the output file path with ptBR suffix
        if output_file == current_srt_path:  # Never overwrite the source SRT
            raise RuntimeError(f"Refusing to overwrite source subtitle: {current_srt_path}")

        if translatable_character_count == 0:  # Avoid DeepL calls when cleanup removed every translatable line
            print(f"{BackgroundColors.YELLOW}{filename} contains no translatable dialogue after SDH cleanup.{Style.RESET_ALL}")  # Log empty cleaned file
            continue  # Continue with next SRT file

        is_target_language, detection_conclusive, detected_language_label = detect_cleaned_subtitle_language(srt_lines, TARGET_LANG)  # Detect language from cleaned dialogue only
        if is_target_language:  # Skip DeepL when cleaned subtitle is already in target language
            print(f"{BackgroundColors.YELLOW}Skipping translation: {BackgroundColors.CYAN}{filename}{BackgroundColors.YELLOW} is already in the target language ({BackgroundColors.CYAN}{get_language_display_name(normalize_language_code(TARGET_LANG))}{BackgroundColors.YELLOW}; detected {BackgroundColors.CYAN}{detected_language_label}{BackgroundColors.YELLOW}).{Style.RESET_ALL}")  # Log target-language skip
            if is_translated_output_complete(srt_lines, output_file):  # Preserve complete-output skip behavior
                print(f"{BackgroundColors.YELLOW}Skipping already complete translation: {BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}")  # Log complete-file skip
            else:
                save_srt(srt_lines, output_file, "Cleaned target-language SRT saved as")  # Save cleaned target-language output safely
            continue  # Continue with next SRT file

        if not detection_conclusive:  # Continue normally when language detection is not reliable
            print(f"{BackgroundColors.YELLOW}Language detection was inconclusive for {BackgroundColors.CYAN}{filename}{BackgroundColors.YELLOW}. Continuing with translation.{Style.RESET_ALL}")  # Log inconclusive detection

        if is_translated_output_complete(srt_lines, output_file):  # Require parseable matching output before skipping
            print(f"{BackgroundColors.YELLOW}Skipping already complete translation: {BackgroundColors.CYAN}{output_file}{Style.RESET_ALL}")  # Log complete-file skip
            continue  # Continue with next SRT file

        if not api_keys_loaded and not get_api_keys():  # Load .env and get DeepL API keys only before translation
            print(
                f"{BackgroundColors.RED}DEEPL_API_KEYS not found or invalid in .env file. Please set it before running the program.{Style.RESET_ALL}"
            )  # Output error message
            return  # Exit the program

        api_keys_loaded = True  # Mark DeepL API keys as available for subsequent translation files

        try:
            translated_lines = translate_srt_lines(current_srt_path, srt_lines, translatable_character_count)  # Translate SRT lines using DeepL API
        except RuntimeError as e:
            print(f"{BackgroundColors.RED}{e}{Style.RESET_ALL}")  # Log fatal quota exhaustion
            return  # Stop without saving an incomplete output

        save_srt(translated_lines, output_file)  # Save the translated SRT to the output file

    finish_time = datetime.datetime.now()  # Get the finish time of the program
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
