"""
================================================================================
Rename Movie Directories using TMDb Metadata
================================================================================
Author      : Breno Farias da Silva
Created     : 2025-11-11
Description :
   This script reads all directories inside the INPUT folder and renames them
   based on metadata extracted from their names and from The Movie Database (TMDb) API.
   The renaming pattern follows the format:
      "{MovieName} {YearOfRelease} {Resolution} {Append_String}"

   Key features include:
      - Automatic extraction of movie name, year, resolution, and language from folder names.
      - Online lookup of release year for each movie via TMDb API.
      - Clean renaming with standardized format and user-defined suffix.
      - Logging and verbose messages for better monitoring.
      - .env integration for secure API key handling.

Usage:
   1. Create a `.env` file in the project root containing your TMDb API key:
         TMDB_API_KEY=your_api_key_here
   2. Place the folders to be renamed inside the `./INPUT` directory.
   3. Run the script via:
         $ python rename_movies.py
   4. The renamed folders will appear in the same directory with the new format.

Outputs:
   - Renamed directories under ./INPUT/
   - Console logs for progress and any errors encountered

TODOs:
   - Add command-line argument parsing for dynamic append string selection.
   - Add caching for TMDb API responses to reduce requests.
   - Add logging to file with timestamp and results summary.
   - Handle batch renames for multiple append string variations.

Dependencies:
   - Python >= 3.9
   - requests
   - python-dotenv
   - colorama

Assumptions & Notes:
   - Directory names must contain the movie name, year, resolution, and language.
   - Internet access is required to query TMDb API for release years.
   - The TMDb API key must be defined in a `.env` file in the project root.
"""
    

import atexit  # For playing a sound when the program finishes
import datetime  # For getting the current date and time
import json  # For writing JSON report files
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For parsing directory names
import requests  # For API requests
import subprocess  # For probing video metadata with ffprobe
from colorama import Style  # For coloring the terminal
from dotenv import load_dotenv  # For loading environment variables
from pathlib import Path  # For path handling


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
INPUT_DIRS = [
    Path("E:/Movies/Dual"),
    Path("E:/Movies/Dublado"),
    Path("E:/Movies/English"),
    Path("E:/Movies/Legendado"),
    Path("E:/Movies/Nacional"),
]  # The input directory or list of input directories
LANGUAGE_OPTIONS = ["Dual", "Dublado", "English", "Legendado", "Nacional"]  # User-defined suffixes for renaming
TMDB_BASE_URL = "https://api.themoviedb.org/3"  # Base URL for TMDb API
IGNORE_DIR_REGEX = re.compile(r'^(featurettes|extras|making[-_\s]?of|behind[ _-]?the[ _-]?scenes|specials)$', re.IGNORECASE)  # Regex for ignore dirs

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

VIDEO_EXTS = {  # Video file extensions to consider when probing for resolution
    ".mkv",
    ".mp4",
    ".avi",
    ".mov",
    ".m4v",
    ".webm",
    ".ts",
    ".flv",
    ".mpg",
    ".mpeg",
    ".wmv",
    ".m2ts",
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


def verify_filepath_exists(filepath):
    """
    Verify if a file or folder exists at the specified path.

    :param filepath: Path to the file or folder
    :return: True if the file or folder exists, False otherwise
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}"
    )  # Output the verbose message

    return os.path.exists(filepath)  # Return True if the file or folder exists, False otherwise


def load_api_key():

    """
    Loads the TMDb API key from a .env file in the project root.

    :return: API key string
    """

    load_dotenv()  # Load environment variables from a .env file into the process environment
    
    api_key = os.getenv("TMDB_API_KEY")  # Read the TMDB_API_KEY value from environment
    
    if not api_key:  # Validate that the API key exists and is not falsy
        raise ValueError("TMDB_API_KEY not found in .env file.")  # Raise a descriptive error when API key is missing
    
    return api_key  # Return the TMDb API key string


def is_ffmpeg_installed():
    """
    Verifies if FFmpeg is installed by running 'ffmpeg -version'.

    :return: bool - True if FFmpeg is installed, False otherwise.
    """

    try:  # Try to execute FFmpeg
        subprocess.run(
            ["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )  # Run the command
        return True  # FFmpeg is installed
    except (subprocess.CalledProcessError, FileNotFoundError):  # If an error occurs
        return False  # FFmpeg is not installed


def install_ffmpeg_windows():
    """
    Installs FFmpeg on Windows using Chocolatey. If Chocolatey is not installed, it installs it first.

    :return: None
    """

    verbose_output(f"{BackgroundColors.GREEN}Checking for Chocolatey...{Style.RESET_ALL}")  # Output the verbose message

    choco_installed = (
        subprocess.run(["choco", "--version"], capture_output=True, text=True).returncode == 0
    )  # Verifies if Chocolatey is installed

    if not choco_installed:  # If Chocolatey is not installed
        verbose_output(f"{BackgroundColors.YELLOW}Chocolatey not found. Installing Chocolatey...{Style.RESET_ALL}")

        choco_install_cmd = (
            "powershell -NoProfile -ExecutionPolicy Bypass -Command "
            '"Set-ExecutionPolicy Bypass -Scope Process -Force; '
            "[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; "
            "iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))\""
        )

        subprocess.run(choco_install_cmd, shell=True, check=True)  # Install Chocolatey

        verbose_output(
            f"{BackgroundColors.GREEN}Chocolatey installed successfully. Restart your terminal if needed.{Style.RESET_ALL}"
        )

    verbose_output(f"{BackgroundColors.GREEN}Installing FFmpeg via Chocolatey...{Style.RESET_ALL}")
    subprocess.run(["choco", "install", "ffmpeg", "-y"], check=True)  # Install FFmpeg using Chocolatey

    verbose_output(
        f"{BackgroundColors.GREEN}FFmpeg installed successfully. Please restart your terminal if necessary.{Style.RESET_ALL}"
    )


def install_ffmpeg_linux():
    """
    Installs FFmpeg on Linux using the package manager.

    :return: None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Installing FFmpeg on Linux...{Style.RESET_ALL}"
    )  # Output the verbose message

    try:  # Try installing FFmpeg
        subprocess.run(["sudo", "apt", "update"], check=True)  # Update package list
        subprocess.run(["sudo", "apt", "install", "-y", "ffmpeg"], check=True)  # Install FFmpeg
        verbose_output(
            f"{BackgroundColors.GREEN}FFmpeg installed successfully.{Style.RESET_ALL}"
        )  # Output the verbose message
    except subprocess.CalledProcessError:  # If an error occurs
        print("Failed to install FFmpeg. Please install it manually using your package manager.")  # Inform the user


def install_ffmpeg_mac():
    """
    Installs FFmpeg on macOS using Homebrew.

    :return: None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Installing FFmpeg on macOS...{Style.RESET_ALL}"
    )  # Output the verbose message

    try:  # Try installing FFmpeg
        subprocess.run(["brew", "install", "ffmpeg"], check=True)  # Run the installation command
        print("FFmpeg installed successfully.")  # Inform the user
    except subprocess.CalledProcessError:  # If an error occurs
        print(
            "Homebrew not found or installation failed. Please install FFmpeg manually using 'brew install ffmpeg'."
        )  # Inform the user


def verify_ffmpeg_is_installed():
    """
    Verifies if FFmpeg is installed and installs it if missing.

    :return: None
    """

    INSTALL_COMMANDS = {  # Installation commands for different platforms
        "Windows": install_ffmpeg_windows,  # Windows
        "Linux": install_ffmpeg_linux,  # Linux
        "Darwin": install_ffmpeg_mac,  # macOS
    }

    if is_ffmpeg_installed():  # If FFmpeg is already installed
        verbose_output(f"{BackgroundColors.GREEN}FFmpeg is installed.{Style.RESET_ALL}")  # Output the verbose message
    else:  # If FFmpeg is not installed
        verbose_output(
            f"{BackgroundColors.RED}FFmpeg is not installed. Installing FFmpeg...{Style.RESET_ALL}"
        )  # Output the verbose message
        if platform.system() in INSTALL_COMMANDS:  # If the platform is supported
            INSTALL_COMMANDS[platform.system()]()  # Call the corresponding installation function
        else:  # If the platform is not supported
            print(
                f"Installation for {platform.system()} is not implemented. Please install FFmpeg manually."
            )  # Inform the user


def find_exact_year_match(results, filename_year):
    """
    Iterate TMDb results and return exact matching release year.

    :param results: TMDb results list
    :param filename_year: Existing year from filename
    :return: Year string when exact match found, otherwise None
    """

    target_year = str(filename_year)  # Normalize filename_year to string for comparison
    
    for result in results:  # Iterate TMDb results in ranking order
        release_date = result.get("release_date", "")  # Extract release_date if present
        extracted_year = extract_year_from_release_date(release_date)  # Extract year safely from release_date
        
        if extracted_year and extracted_year == target_year:  # Require exact numeric year equality
            return target_year  # Return matched year when exact-year match found
        
    return None  # Return None when no exact-year match found


def extract_year_from_release_date(release_date):
    """
    Extract year portion from a TMDb release_date string.

    :param release_date: TMDb release_date string
    :return: Year string when valid, otherwise None
    """

    if release_date and len(release_date) >= 4:  # Ensure release_date contains at least year portion
        return release_date.split("-")[0]  # Return first 4-digit year portion
    return None  # Return None when release_date is invalid


def get_movie_year(api_key, movie_name, filename_year=None):
    """
    Query TMDb movie search endpoint to find a movie and return its release year.

    :param api_key: TMDb API key string
    :param movie_name: Movie title to search for on TMDb
    :param filename_year: Existing year from filename or None
    :return: Year string (e.g., '1999') or None when not found
    """

    try:  # Wrap network call to prevent propagation
        url = f"{TMDB_BASE_URL}/search/movie"  # Build search URL for TMDb movie search endpoint
        params = {"api_key": api_key, "query": movie_name}  # Prepare query parameters including API key and movie name

        if filename_year and re.fullmatch(r"(19|20)\d{2}", str(filename_year)):  # If filename_year is strict 4-digit pattern
            params["year"] = str(filename_year)  # Narrow TMDb search by year to prefer exact matches

        response = requests.get(url, params=params, timeout=10)  # Perform HTTP GET request to TMDb search endpoint
        response.raise_for_status()  # Raise exception for HTTP error responses
        data = response.json()  # Parse JSON body from response
        results = data.get("results", [])  # Extract results array from TMDb response
        
        if not results:  # If no results were returned from TMDb
            return None  # Return None when not found

        if filename_year and re.fullmatch(r"(19|20)\d{2}", str(filename_year)):  # If caller supplied an existing year
            return find_exact_year_match(results, filename_year)  # Delegate exact-year validation to helper

        first = results[0]  # Use first (best) search result when no filename_year provided
        release_date = first.get("release_date", "")  # Extract release_date if present
        return extract_year_from_release_date(release_date)  # Return extracted year or None
    except Exception:  # Any network or parsing error must not crash the program
        return None  # Fail silently and allow caller to continue


def standardize_final_name(name):
    """
    Standardize tokens in the final folder name according to movie rules.

    Rules:
    - Numeric tokens remain unchanged (year).
    - Convert '4K' to '2160p' and normalize resolutions to lowercase (e.g., 1080p).
    - Language suffixes are normalized to canonical values from LANGUAGE_OPTIONS.
    - Movie title tokens preserve their original casing (except for token cleanup).
    """

    tokens = name.split()  # Split on whitespace to tokens
    out_tokens = []  # Container for transformed tokens
    
    for tok in tokens:  # Iterate each token for classification
        if tok.isdigit():  # Numeric token verification (keeps leading zeros)
            out_tokens.append(tok)  # Append numeric token unchanged
            continue  # Proceed to next token

        if re.fullmatch(r"4k", tok, re.IGNORECASE):  # Convert 4K token to canonical 2160p
            out_tokens.append("2160p")  # Use canonical 2160p for 4K
            continue  # Proceed to next token

        if re.fullmatch(r"\d{3,4}p", tok, re.IGNORECASE):  # Resolution detection
            out_tokens.append(tok.lower())  # Normalize resolution to lowercase (e.g., 1080p)
            continue  # Proceed to next token

        matched_suffix = None  # Default no match
        for s in LANGUAGE_OPTIONS:  # Iterate configured canonical suffixes
            if tok.lower() == s.lower():  # Case-insensitive equality verification for language suffixes
                matched_suffix = s  # Use canonical form from configuration
                break  # Stop searching when found
        if matched_suffix:  # If suffix matched any canonical value
            out_tokens.append(matched_suffix)  # Append canonical suffix exactly
            continue  # Proceed to next token

        out_tokens.append(tok)  # Preserve original token casing for movie title

    return " ".join(out_tokens)  # Reconstruct normalized name and return


def find_resolution_index(tokens):
    """
    Find the index of the first resolution token.

    :param tokens: List of filename tokens
    :return: Index of resolution token or None
    """

    for idx, tok in enumerate(tokens):  # Iterate tokens to locate resolution
        if re.fullmatch(r"(?i)(\d{3,4}p|4k)", tok):  # Match resolution pattern
            return idx  # Return index when resolution found
    return None  # Return None if resolution not found


def extract_special_tokens(tokens):
    """
    Extract IMAX, HDR and AI Upscaled 60FPS tokens with original casing.

    :param tokens: List of filename tokens
    :return: Tuple containing indices and raw tokens
    """

    imax_idx = None  # Index of IMAX when found
    hdr_idx = None  # Index of HDR when found
    ai_idx = None  # Start index of AI group when found
    ai_raw = []  # Original AI tokens when found
    imax_raw = None  # Original IMAX token casing
    hdr_raw = None  # Original HDR token casing
    i = 0  # Iterator index
    
    while i < len(tokens):  # Scan tokens for special markers
        if imax_idx is None and re.fullmatch(r"(?i)IMAX", tokens[i]):  # Check IMAX token
            imax_idx = i  # Record IMAX index
            imax_raw = tokens[i]  # Capture original IMAX casing
            i += 1  # Advance after IMAX
            continue  # Continue scanning
        
        if hdr_idx is None and re.fullmatch(r"(?i)HDR", tokens[i]):  # Check HDR token
            hdr_idx = i  # Record HDR index
            hdr_raw = tokens[i]  # Capture original HDR casing
            i += 1  # Advance after HDR
            continue  # Continue scanning
        
        if ai_idx is None and i + 2 < len(tokens) and tokens[i].lower() == "ai" and tokens[i + 1].lower() == "upscaled" and tokens[i + 2].lower() == "60fps":  # Check AI group
            ai_idx = i  # Record AI group start index
            ai_raw = [tokens[i], tokens[i + 1], tokens[i + 2]]  # Capture original AI tokens
            i += 3  # Advance past AI group
            continue  # Continue scanning
        
        i += 1  # Advance index when no special token matched
        
    return imax_idx, hdr_idx, ai_idx, imax_raw, hdr_raw, ai_raw  # Return extracted markers


def remove_special_tokens(tokens):
    """
    Remove first occurrence of IMAX, HDR and AI Upscaled 60FPS tokens.

    :param tokens: List of filename tokens
    :return: Cleaned tokens list
    """

    cleaned = []  # Tokens after removal of first occurrences
    removed_imax = False  # Track IMAX removal
    removed_hdr = False  # Track HDR removal
    removed_ai = False  # Track AI removal
    j = 0  # Index for removal pass
    
    while j < len(tokens):  # Iterate original tokens
        if not removed_ai and j + 2 < len(tokens) and tokens[j].lower() == "ai" and tokens[j + 1].lower() == "upscaled" and tokens[j + 2].lower() == "60fps":  # Remove AI group once
            removed_ai = True  # Mark AI removed
            j += 3  # Skip AI tokens
            continue  # Continue after skipping
        
        if not removed_imax and re.fullmatch(r"(?i)IMAX", tokens[j]):  # Remove IMAX once
            removed_imax = True  # Mark IMAX removed
            j += 1  # Skip IMAX token
            continue  # Continue after skipping
        
        if not removed_hdr and re.fullmatch(r"(?i)HDR", tokens[j]):  # Remove HDR once
            removed_hdr = True  # Mark HDR removed
            j += 1  # Skip HDR token
            continue  # Continue after skipping
        
        cleaned.append(tokens[j])  # Keep non-removed token
        j += 1  # Advance index
        
    return cleaned  # Return cleaned tokens


def build_expected_sequence(imax_raw, hdr_raw, ai_raw):
    """
    Build expected special token sequence.

    :param imax_raw: Original IMAX token or None
    :param hdr_raw: Original HDR token or None
    :param ai_raw: Original AI token list
    :return: Ordered list of tokens
    """

    expected = []  # Expected tokens sequence after resolution
    
    if imax_raw is not None:  # If IMAX present it precedes HDR and AI
        expected.append(imax_raw)  # Add IMAX preserving casing
    
    if hdr_raw is not None:  # If HDR present it follows IMAX when IMAX exists
        expected.append(hdr_raw)  # Add HDR preserving casing
    
    if ai_raw:  # If AI present it follows IMAX or HDR or resolution
        expected.extend(ai_raw)  # Add AI group preserving original order and casing
    
    return expected  # Return expected ordered tokens


def is_sequence_correct(tokens, res_index, expected):
    """
    Validate whether expected tokens already follow resolution.

    :param tokens: Token list
    :param res_index: Resolution index
    :param expected: Expected ordered tokens
    :return: Boolean indicating correctness
    """

    check_slice = tokens[res_index + 1 : res_index + 1 + len(expected)]  # Slice tokens after resolution for comparison
    
    if len(check_slice) == len(expected) and all(a.lower() == b.lower() for a, b in zip(check_slice, expected)):  # Case-insensitive compare for exact sequence
        return True  # Sequence already correct
    
    return False  # Sequence not correct


def insert_special_tokens(cleaned, res_index_new, imax_raw, hdr_raw, ai_raw):
    """
    Insert special tokens immediately after resolution.

    :param cleaned: Cleaned token list
    :param res_index_new: Resolution index in cleaned list
    :param imax_raw: Original IMAX token
    :param hdr_raw: Original HDR token
    :param ai_raw: Original AI tokens
    :return: Modified token list
    """

    insert_index = res_index_new + 1  # Insert immediately after resolution
    insertion = build_expected_sequence(imax_raw, hdr_raw, ai_raw)  # Build insertion sequence
    
    for tok in reversed(insertion):  # Insert in reverse to maintain final order
        cleaned.insert(insert_index, tok)  # Insert token at calculated position
    
    return cleaned  # Return updated tokens


def normalize_special_tokens_position(filename):
    """
    Reposition IMAX, HDR and AI Upscaled 60FPS tokens immediately after the resolution token in a filename.

    :param filename: The filename (with or without extension) to normalize
    :return: The filename with tokens positioned after the resolution token or the original filename when unchanged
    """

    p = Path(filename)  # Create Path object from filename
    ext = p.suffix  # Extract file extension
    name = p.stem  # Extract filename without extension
    tokens = name.split()  # Split filename into tokens
    res_index = find_resolution_index(tokens)  # Locate resolution token
    
    if res_index is None:  # If resolution missing, nothing to do
        return filename  # Return original filename unchanged
    
    imax_idx, hdr_idx, ai_idx, imax_raw, hdr_raw, ai_raw = extract_special_tokens(tokens)  # Extract special tokens
    
    if imax_idx is None and hdr_idx is None and not ai_raw:  # If no special markers found
        return filename  # Return original filename unchanged
    
    expected = build_expected_sequence(imax_raw, hdr_raw, ai_raw)  # Build expected ordered sequence
    
    if is_sequence_correct(tokens, res_index, expected):  # Validate ordering
        return filename  # Return original filename unchanged
    
    cleaned = remove_special_tokens(tokens)  # Remove first occurrence of special tokens
    res_index_new = find_resolution_index(cleaned)  # Recompute resolution index in cleaned list
    
    if res_index_new is None:  # Defensive: if resolution lost, abort
        return filename  # Return original filename unchanged
    
    cleaned = insert_special_tokens(cleaned, res_index_new, imax_raw, hdr_raw, ai_raw)  # Insert tokens correctly
    new_name = " ".join(cleaned)  # Reconstruct filename body
    
    return new_name + ext  # Reattach extension and return normalized filename


def extract_resolution_from_filename(filename):
    """
    Extract resolution token directly from filename using regex.

    :param filename: Filename string
    :return: Resolution token preserving original casing or None
    """
    try:  # Guard regex execution
        match = re.search(r"\b(\d{3,4}p|4k)\b", filename, re.IGNORECASE)  # Search for resolution token in filename
    except Exception:  # Handle any regex-related error
        return None  # Return None if regex fails
    if match:  # If a resolution token was found
        return match.group(0)  # Return matched token preserving original casing
    return None  # Return None when no resolution token found


def map_height_to_resolution(height):
    """
    Map numeric height to standard lowercase resolution token.

    :param height: Integer video height
    :return: Resolution token string or None
    """
    if height >= 2160:  # Map 2160 and above to 2160p
        return "2160p"  # Return 2160p
    if height >= 1080:  # Map 1080 and above to 1080p
        return "1080p"  # Return 1080p
    if height >= 720:  # Map 720 and above to 720p
        return "720p"  # Return 720p
    if height >= 480:  # Map 480 and above to 480p
        return "480p"  # Return 480p
    return None  # Return None when below supported thresholds


def probe_resolution_with_ffprobe(filepath):
    """
    Use ffprobe to extract video height and map to resolution.

    :param filepath: Path to video file
    :return: Resolution token string or None
    """
    
    try:  # Wrap subprocess call to avoid crashes
        proc = subprocess.run(  # Execute ffprobe command
            [  # Command arguments list
                "ffprobe",  # ffprobe executable
                "-v",  # Set verbosity flag
                "error",  # Only show errors
                "-select_streams",  # Select specific streams
                "v:0",  # First video stream
                "-show_entries",  # Specify entries to show
                "stream=height",  # Request stream height
                "-of",  # Output format flag
                "csv=p=0",  # CSV output without prefix
                str(filepath),  # Target file path
            ],
            capture_output=True,  # Capture stdout and stderr
            text=True,  # Decode output as text
            check=True,  # Raise exception on non-zero exit
        )  # Run subprocess
    except FileNotFoundError:  # ffprobe not installed
        return None  # Return None when ffprobe missing
    except Exception:  # Any other subprocess error
        return None  # Return None on probing failure

    out = proc.stdout.strip()  # Strip whitespace from ffprobe output
    if not out:  # If no output received
        return None  # Return None when height missing

    try:  # Attempt to parse height
        height = int(out.splitlines()[0])  # Convert first line to integer
    except Exception:  # Parsing failure
        return None  # Return None when parsing fails

    return map_height_to_resolution(height)  # Map height to resolution token


def get_resolution_from_first_video(dir_path):
    """
    Attempt to derive resolution from the first valid video file in `dir_path`.
    """

    video_exts = VIDEO_EXTS  # Reference global video extensions set

    try:  # Guard directory iteration
        entries = sorted(dir_path.iterdir())  # Retrieve sorted directory entries
    except Exception:  # Directory access failure
        return None  # Return None if directory cannot be read

    for candidate in entries:  # Iterate directory entries
        if not candidate.is_file():  # Skip non-file entries
            continue  # Continue to next entry
        
        if candidate.suffix.lower() not in video_exts:  # Skip non-video files
            continue  # Continue to next entry

        filename_resolution = extract_resolution_from_filename(candidate.name)  # Attempt filename-based extraction
        if filename_resolution:  # If resolution found in filename
            return filename_resolution  # Return filename resolution immediately

        probed_resolution = probe_resolution_with_ffprobe(candidate)  # Attempt ffprobe-based extraction
        if probed_resolution:  # If resolution obtained from ffprobe
            return probed_resolution  # Return probed resolution immediately

        return None  # Stop after first video file even if resolution not found

    return None  # Return None when no video files found


def strip_prefix(name):
    """
    Remove leading 'X - ' prefix if present.

    :param name: Filename string
    :return: Filename without prefix
    """
    
    m = re.match(r"^(?P<prefix>[^-]+)\s-\s(?P<rest>.+)$", name)  # Match prefix pattern
    return m.group("rest") if m else name  # Return remainder or original


def has_duplicate_tokens(tokens):
    """
    Determine whether a token list contains case-insensitive duplicates.

    :param tokens: List of tokens
    :return: True if duplicates exist, otherwise False
    """
    
    seen = set()  # Track seen lowercase tokens
    
    for t in tokens:  # Iterate tokens
        key = t.lower()  # Normalize token case
        
        if key in seen:  # Duplicate found
            return True  # Return immediately
        
        seen.add(key)  # Record token
        
    return False  # No duplicates found


def tokens_reordered(toks_old, toks_new):
    """
    Determine if tokens were reordered but content is identical.

    :param toks_old: Old token list
    :param toks_new: New token list
    :return: True if reordered only
    """
    
    lower_old = [t.lower() for t in toks_old]  # Lowercase old tokens
    lower_new = [t.lower() for t in toks_new]  # Lowercase new tokens
    
    if lower_old != lower_new and sorted(lower_old) == sorted(lower_new):  # Same tokens different order
        return True  # Reordered
    
    return False  # Not reordered-only


def tokens_casing_changed(toks_old, toks_new):
    """
    Determine if only casing changed.

    :param toks_old: Old token list
    :param toks_new: New token list
    :return: True if casing differs only
    """
    
    lower_old = [t.lower() for t in toks_old]  # Lowercase old tokens
    lower_new = [t.lower() for t in toks_new]  # Lowercase new tokens
    
    if lower_old == lower_new and toks_old != toks_new:  # Same words different casing
        return True  # Casing standardized
    
    return False  # Not casing-only change


def detect_changes(old_name, new_name):
    """
    Detect a list of change tags between old_name and new_name.

    Returns a human-readable string like 'Add Prefix + Add Year'.
    """

    old_norm = " ".join(old_name.split())  # Normalize old name whitespace
    new_norm = " ".join(new_name.split())  # Normalize new name whitespace

    if old_name == new_name:  # No change at all
        return ""  # Empty means skip rename

    if old_norm == new_norm and old_name != new_name:  # Only spacing differs
        return "Normalize Format"  # Spacing-only change

    tags = []  # Collect change tags

    if re.match(r"^[^-]+\s-\s", new_name) and not re.match(r"^[^-]+\s-\s", old_name):  # Added series prefix
        tags.append("Add Prefix")  # Tag prefix addition

    year_re = re.compile(r"\b(19|20)\d{2}\b")  # Year regex
    old_year = year_re.search(old_name)  # Extract old year
    new_year = year_re.search(new_name)  # Extract new year

    if new_year and not old_year:  # Year added
        tags.append("Add Year")  # Tag year addition
    elif new_year and old_year and new_year.group(0) != old_year.group(0):  # Year corrected
        tags.append("Correct Year")  # Tag corrected year

    res_re = re.compile(r"\b(\d{3,4}p|4k)\b", re.IGNORECASE)  # Resolution regex
    old_res = res_re.search(old_name)  # Extract old resolution
    new_res = res_re.search(new_name)  # Extract new resolution

    if new_res and not old_res:  # Resolution added
        tags.append("Add Resolution")  # Tag resolution addition
    elif new_res and old_res and new_res.group(0).lower() != old_res.group(0).lower():  # Resolution corrected
        tags.append("Correct Resolution")  # Tag corrected resolution

    base_old = strip_prefix(old_name)  # Remove prefix from old
    base_new = strip_prefix(new_name)  # Remove prefix from new
    toks_old = base_old.split()  # Tokenize old base
    toks_new = base_new.split()  # Tokenize new base

    dup_old = has_duplicate_tokens(toks_old)  # Check duplicates in old
    dup_new = has_duplicate_tokens(toks_new)  # Check duplicates in new

    if dup_old and not dup_new:  # Duplicates removed
        tags.append("Remove Duplicate Tokens")  # Tag duplicate removal

    if tokens_reordered(toks_old, toks_new):  # Tokens reordered
        tags.append("Reorder Tokens")  # Tag reorder

    if tokens_casing_changed(toks_old, toks_new):  # Casing standardized
        tags.append("Standardize Casing")  # Tag casing normalization

    if not tags:  # No specific tags detected
        if old_norm != new_norm:  # Normalized forms differ
            tags.append("Normalize Format")  # Fallback normalization tag
        else:  # No meaningful change
            return ""  # Signal skip

    return " + ".join(tags)  # Return combined tags


def build_initial_report_data():
    """
    Initialize the base report_data structure.

    :return: Initialized report_data dict
    """
    
    report_data = {  # Initialize report structure
        "generated_at": None,  # Placeholder timestamp filled later
        "input_dirs": {},  # Container for per-root modifications
    }  # End initialization
    
    return report_data  # Return initialized structure


def get_root_directories(root):
    """
    Safely retrieve sorted directory entries from a root path.

    :param root: Root path string
    :return: (root_path, entries) or (None, None) on failure
    """
    
    root_path = Path(root)  # Convert to Path object
    if not root_path.exists():  # Skip non-existing roots
        verbose_output(f"{BackgroundColors.YELLOW}Input path not found, skipping: {BackgroundColors.CYAN}{root_path}{Style.RESET_ALL}")  # Notify skip
        return None, None  # Signal skip

    try:  # Guard directory listing
        entries = [p for p in sorted(root_path.iterdir()) if p.is_dir()]  # Deterministic directories only
    except Exception:  # If listing fails
        verbose_output(f"{BackgroundColors.YELLOW}Cannot read input path, skipping: {BackgroundColors.CYAN}{root_path}{Style.RESET_ALL}")  # Notify skip
        return None, None  # Signal skip

    return root_path, entries  # Return valid root and entries


def extract_language_token(dir_name):
    """
    Extract canonical language token from directory name.

    :param dir_name: Directory name
    :return: Canonical language token or None
    """
    
    for s in LANGUAGE_OPTIONS:  # Iterate canonical options
        if re.search(rf"\b{s}\b", dir_name, re.IGNORECASE):  # Detect case-insensitive match
            return s  # Return canonical form
        
    return None  # No language found


def extract_resolution_token(dir_name):
    """
    Extract and normalize resolution token.

    :param dir_name: Directory name
    :return: Resolution token or None
    """
    
    res_match = re.search(r"\b(\d{3,4}p|4k)\b", dir_name, re.IGNORECASE)  # Search resolution
    res_token = res_match.group(0) if res_match else None  # Extract token
    
    if res_token and res_token.lower() == "4k":  # Normalize 4K
        res_token = "2160p"  # Convert to canonical 2160p
    
    return res_token  # Return token


def replace(match):
    """
    Replacement function for regex substitution to protect dots in abbreviations.
    
    :param match: Regex match object
    :return: Replacement string with dots protected
    """
    
    txt = match.group(0)  # Matched abbreviation
    
    return txt.replace(".", "<<DOT>>")  # Protect dots inside abbreviation


def protect_title_abbreviation_dots(s):
    """
    Temporarily replace dots inside abbreviation-like sequences with a placeholder.

    :param s: Input string
    :return: String with abbreviation dots replaced by '<<DOT>>'
    """

    abbr_re = re.compile(r"\b(?:[A-Za-z]{1,3}\.){1,}[A-Za-z]{1,3}\.?\b")  # Abbreviation pattern

    return abbr_re.sub(replace, s)  # Return string with protected abbreviations


def clean_title_for_lookup(original_name, append_lang, res_token):
    """
    Prepare cleaned title for TMDb lookup.

    :param original_name: Original directory name
    :param append_lang: Extracted language token
    :param res_token: Extracted resolution token
    :return: (cleaned_title, years_in_name)
    """
    
    years_in_name = re.findall(r"\b((?:19|20)\d{2})\b", original_name)  # Extract all 4-digit years
    name_work = original_name  # Work copy

    if append_lang:  # Remove language token
        name_work = re.sub(rf"\b{re.escape(append_lang)}\b", "", name_work, flags=re.IGNORECASE)  # Remove language token

    if res_token:  # Remove resolution token
        name_work = re.sub(rf"\b{re.escape(res_token)}\b", "", name_work, flags=re.IGNORECASE)  # Remove resolution token

    name_work = re.sub(r"\((\d{4})\)", r"\1", name_work)  # Remove parentheses around years

    name_work = protect_title_abbreviation_dots(name_work)  # Protect abbreviation dots before normalization
    name_work = re.sub(r"[._]+", " ", name_work)  # Replace dots/underscores used as separators
    name_work = name_work.replace("<<DOT>>", ".")  # Restore protected abbreviation dots
    name_work = " ".join(name_work.split()).strip()  # Normalize whitespace

    return name_work, years_in_name  # Return cleaned title and detected years


def remove_bluray_tokens(title):
    """
    Remove any standalone "BluRay" tokens (case-insensitive) from the title.

    This handles variants like "bluray", "BLURAY" and "blu-ray" and
    preserves spacing and other tokens.
    :param title: Input title string
    :return: Title with BluRay tokens removed
    """
    
    if not title:  # Guard empty input
        return title  # Return unchanged when empty
    
    cleaned = re.sub(r"\bblu-?ray\b", "", title, flags=re.IGNORECASE)  # Remove blu(r)-ray tokens
    
    return " ".join(cleaned.split()).strip()  # Normalize whitespace and return


def remove_audio_quality_tokens(title):
    """
    Remove standalone audio-quality tokens such as '5.1', '2.1', '7.1', '6.1', '4.1'.

    Detection is precise: tokens must match exactly (word boundaries).
    :param title: Input title string
    :return: Title with audio-quality tokens removed
    """
    
    if not title:  # Guard empty input
        return title  # Return unchanged when empty
    
    cleaned = re.sub(r"\b(?:2|4|5|6|7)\.1\b", "", title)  # Remove audio tokens

    return " ".join(cleaned.split()).strip()  # Normalize whitespace and return


def remove_release_year_tokens(title, release_year):
    """
    Remove all tokens equal to `release_year` from `title`.
    
    :param title: Movie title string
    :param release_year: Release year string to remove
    :return: Title with release year tokens removed
    """
    
    if not release_year:  # Nothing to remove when no release year is provided
        return title  # Return original title unchanged
    
    ry = str(release_year)  # Normalize release year to string for comparison
    toks = title.split()  # Tokenize title on whitespace
    filtered = [t for t in toks if t != ry]  # Keep tokens not equal to release year
    
    return " ".join(filtered).strip()  # Reconstruct and return


def rebuild_final_name(movie_title, final_year, res_token, append_lang):
    """
    Rebuild canonical directory name.

    :return: Final normalized name
    """

    title_cleaned = remove_bluray_tokens(movie_title)  # Remove BluRay tokens case-insensitively
    title_cleaned = remove_audio_quality_tokens(title_cleaned)  # Remove audio quality tokens like 5.1
    title_without_year = remove_release_year_tokens(title_cleaned, final_year)  # Remove any exact-release-year tokens

    parts = []  # Build parts list in desired order
    if title_without_year:  # Only add title when non-empty
        parts.append(title_without_year)  # Append cleaned title
    if final_year:  # Append year exactly once when provided
        parts.append(str(final_year))  # Append canonical release year
    if res_token:  # Append resolution if present
        parts.append(res_token)  # Append resolution
    if append_lang:  # Append language if present
        parts.append(append_lang)  # Append language suffix

    new_name = " ".join(parts).strip()  # Join parts into final name
    new_name = " ".join(new_name.split())  # Normalize whitespace
    new_name = standardize_final_name(new_name)  # Apply canonical normalization
    new_name = " ".join(new_name.split())  # Normalize again
    new_name = normalize_special_tokens_position(new_name)  # Reposition IMAX/HDR tokens

    return new_name  # Return final normalized name


def rename_path_with_subtitle_sync(src, dst, report_data=None, root_key=None):
    """
    Rename a file or directory from src to dst, and if it's a video file with an accompanying .srt subtitle, rename the subtitle in sync.
    
    :param src: Source Path object
    :param dst: Destination Path object
    :param report_data: Optional dict for accumulating report data
    :param root_key: Optional key for report_data mapping
    :return: None, but performs filesystem rename and updates report_data when applicable
    """
    
    try:  # Attempt the primary filesystem rename operation
        src.rename(dst)  # Perform filesystem rename operation
    except Exception:  # Propagate exception to caller for consistent handling
        raise  # Re-raise to allow caller to log/handle exactly as existing flow

    if src.is_file() and src.suffix.lower() in VIDEO_EXTS:  # Only sync subtitles for recognized video files
        orig_sub = src.with_suffix(".srt")  # Detect subtitle file based on original video stem
        if orig_sub.exists():  # The .srt rename must happen ONLY if the subtitle file exists
            dst_sub = dst.with_suffix(".srt")  # Build destination subtitle path preserving .srt extension
            if dst_sub.exists():  # Prevent unsafe overwrite consistent with project safety checks
                raise FileExistsError(f"Destination subtitle exists: {dst_sub}")  # Signal collision to caller
            try:  # Attempt to rename the subtitle file
                orig_sub.rename(dst_sub)  # Perform subtitle rename operation
            except Exception:  # Follow same error handling pattern on failure
                raise  # Re-raise to let caller handle logging and continuation

            if report_data is not None and root_key is not None:  # Update JSON report structure when present
                rk = str(root_key)  # Canonicalize root key for report mapping
                if rk not in report_data.get("input_dirs", {}):  # Lazily create per-root entry when missing
                    report_data.setdefault("input_dirs", {})  # Ensure input_dirs mapping exists
                    report_data["input_dirs"][rk] = {"directories_modified": [], "video_files_renamed": []}  # Initialize per-root structure
                if "video_files_renamed" not in report_data["input_dirs"][rk]:  # Ensure list exists for consistency
                    report_data["input_dirs"][rk]["video_files_renamed"] = []  # Initialize list
                report_data["input_dirs"][rk]["video_files_renamed"].append({  # Append subtitle rename using same record shape
                    "old_name": str(orig_sub.name),  # Old subtitle filename
                    "new_name": str(dst_sub.name),  # New subtitle filename
                    "reason": "Sync Subtitle With Video",  # Reason matching existing report style
                })  # End append


def rename_dirs():
    """
    Iterates through the INPUT_DIRS, extracts metadata, fetches the release year from TMDb,
    and renames each directory according to the defined pattern.

    :return: None
    """

    api_key = load_api_key()  # Load TMDb API key into `api_key`
    report_data = build_initial_report_data()  # Initialize report structure into `report_data`

    for root in INPUT_DIRS:  # Iterate configured roots list
        root_path, entries = get_root_directories(root)  # Safely fetch directories for this root
        if not root_path or entries is None:  # Skip root when retrieval failed or entries is None
            continue  # Continue to next root if current root invalid

        total = len(entries)  # Count directories in `entries` (now non-None)
        root_key = str(root_path)  # Use string form of input root as dictionary key
        if root_key not in report_data["input_dirs"]:  # Lazily create per-root entry when first change occurs
            report_data["input_dirs"][root_key] = {  # Initialize per-root structure
                "directories_modified": [],  # List to hold directory modifications
                "video_files_renamed": [],  # List to hold video rename records
            }  # End initialization

        for idx, entry in enumerate(entries, start=1):  # Iterate entries with index starting at 1
            print(f"{BackgroundColors.GREEN}Processing {BackgroundColors.CYAN}{idx}{BackgroundColors.GREEN}/{BackgroundColors.CYAN}{total}{BackgroundColors.GREEN}: {BackgroundColors.CYAN}{entry.name}{Style.RESET_ALL}")  # Progress output

            if re.match(IGNORE_DIR_REGEX, entry.name.strip()):  # Skip ignored directories by regex
                verbose_output(f"{BackgroundColors.YELLOW}Ignoring top-level directory: {entry.name}{Style.RESET_ALL}")  # Verbose message for ignored directory
                continue  # Continue loop when directory is ignored

            append_lang = extract_language_token(entry.name)  # Extract language suffix token if present
            res_token = extract_resolution_token(entry.name)  # Extract resolution token if present
            name_work, years_in_name = clean_title_for_lookup(entry.name, append_lang, res_token)  # Clean title for lookup and capture years

            if not name_work:  # Skip entries that become empty after cleanup
                verbose_output(f"{BackgroundColors.YELLOW}Skipping (empty title after cleanup): {entry.name}{Style.RESET_ALL}")  # Verbose skip message
                continue  # Continue to next entry

            try:  # Guard TMDb lookup network call
                tmdb_year = get_movie_year(api_key, name_work, None)  # Query TMDb for release year
            except Exception as e:  # Handle lookup errors gracefully
                print(f"{BackgroundColors.RED}TMDb lookup error for '{name_work}': {e}{Style.RESET_ALL}")  # Print TMDb error
                tmdb_year = None  # Fallback when lookup fails

            final_year = tmdb_year or (years_in_name[0] if years_in_name else None)  # Choose TMDb year or fallback to filename year

            movie_title = " ".join(name_work.split()).strip()  # Normalize whitespace in movie title

            if not res_token:  # Probe resolution from media files when resolution missing
                try:
                    probed = get_resolution_from_first_video(entry)  # Probe first video file for resolution
                except Exception:
                    probed = None  # Fall back to None on probe failure
                if probed and probed.lower() == "4k":  # Normalize textual 4K to canonical token
                    probed = "2160p"  # Map 4K to 2160p canonical token
                res_token = probed or res_token  # Use probed resolution if available

            new_name = rebuild_final_name(movie_title, final_year, res_token, append_lang)  # Build final normalized directory name

            if new_name == entry.name:  # Skip when name unchanged
                verbose_output(f"{BackgroundColors.YELLOW}Skipping (already named): {entry.name}{Style.RESET_ALL}")  # Verbose already-named message
                continue  # Continue to next entry when no rename required

            change_desc = detect_changes(entry.name, new_name)  # Determine change description tags
            if not change_desc:  # Skip when no meaningful change detected
                verbose_output(f"{BackgroundColors.YELLOW}Skipping (no detected meaningful change): {entry.name}{Style.RESET_ALL}")  # Verbose no-change message
                continue  # Continue to next entry

            print(f"{BackgroundColors.YELLOW}Renaming ({change_desc}): '{BackgroundColors.CYAN}{entry.name}{BackgroundColors.GREEN}' → '{BackgroundColors.CYAN}{new_name}{BackgroundColors.GREEN}'{Style.RESET_ALL}")  # Announce rename

            try:  # Attempt to rename directory on filesystem (and sync subtitles when applicable)
                rename_path_with_subtitle_sync(entry, entry.parent / new_name, report_data, root_key)  # Perform filesystem rename and subtitle sync
            except Exception as e:  # Handle rename or subtitle exceptions with same pattern
                print(f"{BackgroundColors.RED}Failed to rename '{entry.name}' → '{new_name}': {e}{Style.RESET_ALL}")  # Print rename failure
                continue  # Continue processing next entries after failure

        print()  # Spacing between roots for readability

    generate_report(report_data)  # Generate summary report JSON file
    generate_duplicate_movies_report(report_data)  # Generate duplicate movies report JSON file


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


def generate_report(report_data: dict) -> None:
    """
    Generate a `movies_renaming_report.json` file in the project root from `report_data`.

    :param report_data: The report dictionary built during processing
    :return: None
    """

    report_data["generated_at"] = datetime.datetime.now().isoformat()  # Add ISO timestamp to the report
    
    out_path = Path(__file__).parent / "movies_renaming_report.json"  # Compute output path in project root
    
    try:  # Guard file I/O to avoid raising
        with out_path.open("w", encoding="utf-8") as f:  # Open file for writing with UTF-8 encoding
            json.dump(report_data, f, indent=4, ensure_ascii=False)  # Write JSON with required options
    except Exception as e:  # On any error while writing, report but do not raise
        print(f"{BackgroundColors.RED}Failed to write movies_renaming_report.json: {e}{Style.RESET_ALL}")  # Log write failure
        return  # Ensure function exits without raising


def generate_duplicate_movies_report(report_data: dict) -> None:
    """
    Generate a `duplicate_movies_report.json` summarizing movies with the same
    base title but different language or resolution across input roots.

    This function receives the already-built `report_data` dictionary,
    computes groups of duplicates, and writes the resulting JSON file to
    the project root. The function is defensive and never raises.
    """

    try:  # Guard the whole duplicate report generation
        duplicates_map = {}  # Initialize mapping of base_title -> list of records
        for root_key, root_info in report_data.get("input_dirs", {}).items():  # Iterate configured input roots
            for rec in root_info.get("directories_modified", []):  # Iterate modifications for this root
                new_name = rec.get("new_name", "")  # Read the new directory name safely
                old_name = rec.get("old_name", "")  # Read the old directory name safely
                
                try:  # Guard regex operations
                    base = re.sub(r"\b(19|20)\d{2}\b", "", new_name)  # Strip year tokens
                except Exception:  # On regex failure
                    base = new_name  # Fallback to full new_name
                
                try:  # Guard regex operations
                    base = re.sub(r"\b(\d{3,4}p|4k)\b", "", base, flags=re.IGNORECASE)  # Strip resolution tokens
                except Exception:  # On regex failure
                    base = base  # Keep as-is on failure
                
                try:  # Guard language stripping
                    for s in LANGUAGE_OPTIONS:  # Iterate canonical language options
                        base = re.sub(rf"\b{re.escape(s)}\b", "", base, flags=re.IGNORECASE)  # Strip language token
                except Exception:  # On any failure
                    base = base  # Keep as-is on failure
                base_title = " ".join(base.split()).strip()  # Normalize whitespace to produce canonical base title

                try:  # Guard extraction
                    res_m = re.search(r"\b(\d{3,4}p|4k)\b", new_name, re.IGNORECASE)  # Search for resolution token
                except Exception:  # On regex failure
                    res_m = None  # Treat as missing
                resolution = None if not res_m else ("2160p" if res_m.group(0).lower() == "4k" else res_m.group(0))  # Normalize 4K

                lang = None  # Default when absent
                try:  # Guard language extraction
                    for s in LANGUAGE_OPTIONS:  # Iterate canonical suffix list
                        if re.search(rf"\b{s}\b", new_name, re.IGNORECASE):  # Detect whole-word match
                            lang = s  # Use canonical form
                            break  # Stop after first match
                except Exception:  # On any error
                    lang = None  # Keep as None on failure

                record = {  # Prepare record dictionary
                    "input_root": root_key,  # Source input root path
                    "old_name": old_name,  # Original directory name
                    "new_name": new_name,  # Final directory name
                    "resolution": resolution,  # Detected resolution or None
                    "language": lang,  # Detected language or None
                }  # End record

                try:  # Guard mapping append
                    if not base_title:  # Skip empty base titles defensively
                        continue  # Skip to next record
                    duplicates_map.setdefault(base_title, []).append(record)  # Append record into list for base_title
                except Exception:  # On failure to append
                    continue  # Skip problematic record

        filtered = {}  # Initialize filtered duplicates dictionary
        for title, records in duplicates_map.items():  # Iterate candidate groups
            try:  # Guard comparison logic
                combos = set()  # Track distinct (resolution, language) pairs
                for r in records:  # Iterate records in group
                    combos.add((r.get("resolution"), r.get("language")))  # Add tuple to set
                if len(records) > 1 and len(combos) > 1:  # Require multiple entries and differing resolution/lang combos
                    filtered[title] = records  # Keep this title as duplicate group
            except Exception:  # On any error while filtering
                continue  # Skip this title on error

        dup_report = {  # Top-level structure for duplicate report
            "generated_at": datetime.datetime.now().isoformat(),  # ISO timestamp
            "duplicates": filtered,  # Mapping of base title -> list of records
        }  # End dup_report

        out_dup_path = Path(__file__).parent / "duplicate_movies_report.json"  # Compute output path
        try:  # Guard file writing
            with out_dup_path.open("w", encoding="utf-8") as f:  # Open file for writing in UTF-8
                json.dump(dup_report, f, indent=4, ensure_ascii=False)  # Dump JSON using required parameters
        except Exception as e:  # On file write failure
            print(f"{BackgroundColors.RED}Failed to write duplicate_movies_report.json: {e}{Style.RESET_ALL}")  # Log write failure
            return  # Ensure function exits without raising
    except Exception:  # Catch-all to prevent any exception from escaping
        return  # Never raise outward


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
    Main function.

    :param: None
    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Movie Directory Renamer{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the welcome message
    start_time = datetime.datetime.now()  # Get the start time of the program
    
    verify_ffmpeg_is_installed()  # Verify if ffmpeg is installed
    
    rename_dirs()  # Execute the directory renaming workflow

    finish_time = datetime.datetime.now()  # Get the finish time of the program
    print(
        f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"
    )  # Output the start and finish times
    print(
        f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
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
