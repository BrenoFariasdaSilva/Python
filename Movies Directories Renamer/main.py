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
    Checks if FFmpeg is installed by running 'ffmpeg -version'.

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
    )  # Check if Chocolatey is installed

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
    Checks if FFmpeg is installed and installs it if missing.

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


def parse_dir_name(dir_name):
    """
    Parses folder name like 'The Matrix 1999 1080p Dual'.

    :param dir_name: Directory name string to parse
    :return: Tuple (movie_name, year, resolution, language) or None when parsing fails
    """
    
    match = re.match(
        r"^(?P<movie>.+?)\s*(?P<year>\(\d{4}\)|\d{4})?\s*(?P<res>\d{3,4}p|4k)?\s*(?P<lang>Dual|Dublado|English|Legendado|Nacional)?$",
        dir_name,
        re.IGNORECASE,
    )  # Regex to parse movie name, optional year, optional resolution, and optional language suffix
    
    if match:  # If the regex matched successfully
        movie = match.group("movie").strip()  # Extract and clean movie name
        year = match.group("year")  # Extract year string (may be None)
        resolution = match.group("res")  # Extract resolution string (may be None)
        language = match.group("lang")  # Extract language suffix (may be None)

        if year:  # If a year was found, clean it by removing parentheses if present
            year = year.strip("()")  # Remove parentheses from year if they exist

        return movie, year, resolution, language  # Return the parsed components as a tuple
    
    return None  # Return None when parsing fails (no match)


def get_movie_year(api_key, movie_name):

    """
    Query TMDb movie search endpoint to find a movie and return its release year.

    :param api_key: TMDb API key string
    :param movie_name: Movie title to search for on TMDb
    :return: Year string (e.g., '1999') or None when not found
    """

    try:  # Wrap network call to prevent propagation
        url = f"{TMDB_BASE_URL}/search/movie"  # Build search URL for TMDb movie search endpoint
        params = {"api_key": api_key, "query": movie_name}  # Prepare query parameters including API key and movie name
        response = requests.get(url, params=params, timeout=10)  # Perform HTTP GET request to TMDb search endpoint
        response.raise_for_status()  # Raise exception for HTTP error responses
        data = response.json()  # Parse JSON body from response
        results = data.get("results", [])  # Extract results array from TMDb response
        if not results:  # If no results were returned from TMDb
            return None  # Return None when not found
        first = results[0]  # Use first (best) search result
        release_date = first.get("release_date", "")  # Extract release_date if present
        if release_date and len(release_date) >= 4:  # Ensure a year portion exists
            return release_date.split("-")[0]  # Return year portion only
        return None  # No usable release_date available
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
        if tok.isdigit():  # Numeric token check (keeps leading zeros)
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
            if tok.lower() == s.lower():  # Case-insensitive equality check
                matched_suffix = s  # Use canonical form from configuration
                break  # Stop searching when found
        if matched_suffix:  # If suffix matched any canonical value
            out_tokens.append(matched_suffix)  # Append canonical suffix exactly
            continue  # Proceed to next token

        out_tokens.append(tok)  # Preserve original token casing for movie title

    return " ".join(out_tokens)  # Reconstruct normalized name and return


def get_resolution_from_first_video(dir_path):
    """
    Attempt to derive resolution from the first valid video file in `dir_path`.

    Steps:
    1) Try to extract resolution token from the filename using regex.
    2) If absent, attempt to call `ffprobe` to read video stream height.
    3) Map height to standard resolution tokens (lowercase 'p').

    Returns resolution token string (preserving filename casing) or None.
    """

    video_exts = {  # Known video file extensions
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
    }  # Set of extensions

    try:  # Guard filesystem iteration
        entries = sorted(dir_path.iterdir())  # Deterministic ordering of directory entries
    except Exception:  # If directory cannot be read
        return None  # Give up and return None

    for candidate in entries:  # Iterate entries to find first video file
        if not candidate.is_file():  # Skip non-file entries
            continue  # Continue search
        if candidate.suffix.lower() not in video_exts:  # Skip non-video extensions
            continue  # Continue search

        # First attempt: Extract resolution from filename
        try:  # Regex can raise on weird inputs, guard it
            name_match = re.search(r"\b(\d{3,4}p|4k)\b", candidate.name, re.IGNORECASE)  # Filename regex search
        except Exception:  # Any regex-related error
            name_match = None  # Treat as not found
        if name_match:  # If token found in filename
            return name_match.group(0)  # Preserve original filename casing

        # Second attempt: Probe metadata with ffprobe (non-fatal)
        try:  # Wrap external call to avoid crashes
            proc = subprocess.run(  # Call ffprobe to get the height of the first video stream
                [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=height",
                    "-of",
                    "csv=p=0",
                    str(candidate),
                ],
                capture_output=True,  # Capture stdout/stderr
                text=True,  # Decode output as text
                check=True,  # Raise CalledProcessError on non-zero exit
            )  # Run ffprobe
            
            out = proc.stdout.strip()  # Strip whitespace from output
            
            if not out:  # No output returned
                return None  # Give up and return None

            try:  # Height parsing may fail on unexpected output
                height = int(out.splitlines()[0])  # Convert to int
            except Exception:  # Parsing failed
                return None  # Unable to derive resolution

            if height >= 2160:  # 4K and above map to 2160p
                return "2160p"  # Use lowercase 'p' per rules
            if height >= 1080:  # Map to 1080p
                return "1080p"  # Use lowercase 'p'
            if height >= 720:  # Map to 720p
                return "720p"  # Use lowercase 'p'
            if height >= 480:  # Map to 480p
                return "480p"  # Use lowercase 'p'
            return None  # Height exists but below thresholds
        except FileNotFoundError:  # ffprobe not installed
            return None  # Fail silently and return None
        except Exception:  # Any other probing error
            return None  # Fail silently and return None

    return None  # No video file found in directory


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
        return "Normalize Format"  # Single tag for spacing-only changes

    tags = []  # Collect change tags

    if re.match(r"^[^-]+\s-\s", new_name) and not re.match(r"^[^-]+\s-\s", old_name):  # Added series prefix
        tags.append("Add Prefix")  # Add tag for added prefix

    year_re = re.compile(r"\b(19|20)\d{2}\b")  # Year regex
    old_year = year_re.search(old_name)  # Find year in old name
    new_year = year_re.search(new_name)  # Find year in new name

    if new_year and not old_year:  # Year added
        tags.append("Add Year")  # Tag for adding year
    elif new_year and old_year and new_year.group(0) != old_year.group(0):  # Year changed
        tags.append("Correct Year")  # Tag for corrected year

    res_re = re.compile(r"\b(\d{3,4}p|4k)\b", re.IGNORECASE)  # Resolution regex
    old_res = res_re.search(old_name)  # Find resolution in old name
    new_res = res_re.search(new_name)  # Find resolution in new name

    if new_res and not old_res:  # Resolution added
        tags.append("Add Resolution")  # Tag for added resolution
    elif new_res and old_res and new_res.group(0).lower() != old_res.group(0).lower():  # Resolution changed
        tags.append("Correct Resolution")  # Tag for changed resolution

    def strip_prefix(s):  # Helper to remove leading 'X - ' if present
        m = re.match(r"^(?P<prefix>[^-]+)\s-\s(?P<rest>.+)$", s)  # Match prefix pattern
        return m.group("rest") if m else s  # Return remainder or original

    base_old = strip_prefix(old_name)  # Remove prefix from old
    base_new = strip_prefix(new_name)  # Remove prefix from new
    toks_old = base_old.split()  # Tokenize old base
    toks_new = base_new.split()  # Tokenize new base

    seen = set()  # Track seen tokens
    dup_old = False  # Assume no duplicates
    for t in toks_old:  # Iterate tokens in old
        key = t.lower()  # Case-insensitive key

        if key in seen:  # Duplicate found
            dup_old = True  # Mark duplicate
            break  # Stop early
        
        seen.add(key)  # Add token

    if dup_old:  # If old had duplicates
        seen_new = set()  # Track new tokens
        dup_new = False  # Default

        for t in toks_new:  # Iterate new tokens
            key = t.lower()  # Case-insensitive key

            if key in seen_new:  # Duplicate in new
                dup_new = True  # Mark
                break  # Stop early

            seen_new.add(key)  # Add
            
        if not dup_new:  # If new has no duplicates but old did
            tags.append("Remove Duplicate Tokens")  # Tag for duplicate removal

    if [t.lower() for t in toks_old] != [t.lower() for t in toks_new] and sorted([t.lower() for t in toks_old]) == sorted([t.lower() for t in toks_new]):  # Same tokens different order
        tags.append("Reorder Tokens")  # Tag for reordering

    if [t.lower() for t in toks_old] == [t.lower() for t in toks_new] and toks_old != toks_new:  # Same tokens different casing
        tags.append("Standardize Casing")  # Tag for casing normalization

    if not tags:  # No specific tags found
        if old_norm != new_norm:  # If normalized forms differ
            tags.append("Normalize Format")  # Use Normalize Format as fallback
        else:  # Otherwise nothing meaningful changed
            return ""  # Signal skip

    return " + ".join(tags)  # Return combined tags


def determine_resolution(dir_path, name_hint):
    """
    Unified resolution detection for a given movie folder.

    1) Check for resolution token in `name_hint` using the project's regex.
    2) If not found, probe the first video file inside `dir_path` (non-recursive)
        using `get_resolution_from_first_video()`.
    Preserves casing from filename results and returns None when absent.
    """

    res_search = re.search(r"\b(\d{3,4}p|4k)\b", name_hint, re.IGNORECASE)  # Search name hint for resolution
    if res_search:  # If token found in folder name hint
        return res_search.group(0)  # Preserve original matched casing

    try:  # Guard the probe call which may access filesystem
        res_from_file = get_resolution_from_first_video(dir_path)  # Probe videos inside dir_path
    except Exception:  # Any unexpected error while probing
        res_from_file = None  # Fail silently and return None

    return res_from_file  # May be None when no resolution found


def rename_dirs():
    """
    Iterates through the INPUT_DIRS, extracts metadata, fetches the release year from TMDb,
    and renames each directory according to the defined pattern.

    :return: None
    """
    
    api_key = load_api_key()  # Load TMDb API key from environment before processing directories

    for root in INPUT_DIRS:  # Process each input root independently per requirements
        root_path = Path(root)  # Convert root to Path object for consistent handling
        if not root_path.exists():  # If the configured root does not exist
            verbose_output(f"{BackgroundColors.YELLOW}Input path not found, skipping: {BackgroundColors.CYAN}{root_path}{Style.RESET_ALL}")  # Verbose notification when skipping
            continue  # Continue to next root when this one is missing

        try:  # Attempt to list directories inside the current root safely
            entries = [p for p in sorted(root_path.iterdir()) if p.is_dir()]  # Deterministic, directories only
        except Exception:  # If listing fails for this root
            verbose_output(f"{BackgroundColors.YELLOW}Cannot read input path, skipping: {BackgroundColors.CYAN}{root_path}{Style.RESET_ALL}")  # Verbose notification when skip
            continue  # Continue to next root on error

        total = len(entries)  # Compute number of movie directories in this root

        for idx, entry in enumerate(entries, start=1):  # Iterate directories inside this root with index
            print(f"{BackgroundColors.GREEN}Processing {BackgroundColors.CYAN}{idx}{BackgroundColors.GREEN}/{BackgroundColors.CYAN}{total}{BackgroundColors.GREEN}: {BackgroundColors.CYAN}{entry.name}{Style.RESET_ALL}")  # Print progress line
            if not entry.is_dir():  # Skip non-directories defensively
                continue  # Continue to next entry when current one is not a directory

            if re.match(IGNORE_DIR_REGEX, entry.name.strip()):  # Skip known ignore directories
                verbose_output(f"{BackgroundColors.YELLOW}Ignoring top-level directory: {entry.name}{Style.RESET_ALL}")  # Verbose notification when skipping
                continue  # Continue to next entry when current one is ignored

            # Step 1: Extract language token if present (must be last token) without inventing one
            append_lang = None  # Default to None when absent
            for s in LANGUAGE_OPTIONS:  # Iterate canonical language options
                if re.search(rf"\b{s}\b", entry.name, re.IGNORECASE):  # Detect whole-word match case-insensitively
                    append_lang = s  # Use canonical form
                    break  # Stop after first match

            # Step 2: Extract resolution token from name (including 4K conversion)
            res_match = re.search(r"\b(\d{3,4}p|4k)\b", entry.name, re.IGNORECASE)  # Search for resolution token
            res_token = res_match.group(0) if res_match else None  # Preserve matched token or None
            if res_token and res_token.lower() == "4k":  # Convert 4K to 2160p per rules
                res_token = "2160p"  # Use canonical 2160p

            # Step 3: Extract year token (4 digits) from folder name if present
            year_match = re.search(r"\b(19|20)\d{2}\b", entry.name)  # Year regex
            existing_year = year_match.group(0) if year_match else None  # Existing year string or None

            # Step 4: Clean movie title by removing year/resolution/language tokens and brackets
            name_work = entry.name  # Work on a copy of the original name
            if append_lang:  # Remove language token when present
                name_work = re.sub(rf"\b{re.escape(append_lang)}\b", "", name_work, flags=re.IGNORECASE)  # Strip language token
            if res_match:  # Remove resolution token when present in name
                name_work = re.sub(re.escape(res_match.group(0)), "", name_work, flags=re.IGNORECASE)  # Strip resolution token
            
            name_work = re.sub(r"\((\d{4})\)", r"\1", name_work)  # Unwrap parenthesized year
            if existing_year:  # Remove a bare year token once to avoid duplicates
                name_work = re.sub(re.escape(existing_year), "", name_work, count=1)  # Remove first occurrence of year
            
            name_work = re.sub(r"[._]+", " ", name_work)  # Replace dots/underscores with space
            movie_title = " ".join(name_work.split()).strip()  # Normalize whitespace and trim edges
            if not movie_title:  # If title becomes empty after cleaning
                verbose_output(f"{BackgroundColors.YELLOW}Skipping (empty title after cleanup): {entry.name}{Style.RESET_ALL}")  # Inform skip case
                continue  # Continue to next entry when title can't be derived

            # Step 5: Verify/fetch correct year via TMDb (non-blocking)
            tmdb_year = None  # Default when lookup fails
            try:  # Protect API call with try/except to avoid crash
                tmdb_year = get_movie_year(api_key, movie_title)  # Query TMDb for movie year
            except Exception as e:  # Any unexpected exception from helper
                print(f"{BackgroundColors.RED}TMDb lookup error for '{movie_title}': {e}{Style.RESET_ALL}")  # Log error but continue processing
                tmdb_year = None  # Ensure non-blocking behavior

            # Decide which year to use following rules: prefer TMDb when available, else keep existing year
            final_year = None  # Final year to insert into name
            if tmdb_year:  # If TMDb returned a year
                final_year = tmdb_year  # Prefer the TMDb value
            elif existing_year:  # Else fall back to folder-provided year when present
                final_year = existing_year  # Use existing year

            # Step 6: If resolution missing, attempt to probe first video file (non-blocking)
            if not res_token:  # Only probe when resolution not found in folder name
                try:  # Protect filesystem/ffprobe calls from bubbling errors
                    probed = get_resolution_from_first_video(entry)  # Probe the first video file for resolution
                except Exception:  # Any probing error should not abort processing
                    probed = None  # Treat as unavailable
                if probed and probed.lower() == "4k":  # Convert probed 4K token to 2160p
                    probed = "2160p"  # Normalize 4K to 2160p
                res_token = probed or res_token  # Use probed value when present, else keep previous

            # Step 7: Rebuild the final name strictly as 'MovieName Year Resolution Language' (omit missing tokens)
            parts = [movie_title]  # Start with cleaned movie title
            if final_year:  # Append year when available
                parts.append(str(final_year))  # Year must be 4 digits when present
            if res_token:  # Append resolution when available
                parts.append(res_token)  # Resolution token (e.g., 1080p)
            if append_lang:  # Append language when present
                parts.append(append_lang)  # Language must always be last token

            new_name = " ".join(parts).strip()  # Join parts and trim edges
            new_name = " ".join(new_name.split())  # Normalize internal whitespace
            new_name = standardize_final_name(new_name)  # Apply canonical normalization rules
            new_name = " ".join(new_name.split())  # Normalize whitespace again after standardization

            # Step 8: Detect differences and decide renaming action
            if new_name == entry.name:  # If nothing changed compared to original name
                verbose_output(f"{BackgroundColors.YELLOW}Skipping (already named): {entry.name}{Style.RESET_ALL}")  # Inform skip case
                continue  # Continue to next entry

            change_desc = detect_changes(entry.name, new_name)  # Compute a human-readable list of changes
            if not change_desc:  # If no meaningful changes detected
                verbose_output(f"{BackgroundColors.YELLOW}Skipping (no detected meaningful change): {entry.name}{Style.RESET_ALL}")  # Inform skip case
                continue  # Continue to next entry

            print(
                f"{BackgroundColors.GREEN}Renaming "  # Start message
                f"({change_desc}): "  # Show change tags
                f"'{BackgroundColors.CYAN}{entry.name}{BackgroundColors.GREEN}' → "  # Old name
                f"'{BackgroundColors.CYAN}{new_name}{BackgroundColors.GREEN}'"  # New name
                f"{Style.RESET_ALL}"
            )  # Formatted rename output
            try:  # Attempt filesystem rename operation under try/except
                entry.rename(entry.parent / new_name)  # Perform the filesystem rename operation for the movie folder
            except Exception as e:  # If rename fails, log error but continue processing
                print(f"{BackgroundColors.RED}Failed to rename '{entry.name}' → '{new_name}': {e}{Style.RESET_ALL}")  # Inform about failure

        print()  # Add single spacing after processing this input root


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
