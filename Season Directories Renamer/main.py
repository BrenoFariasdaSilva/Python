"""
================================================================================
Rename TV Show Season Directories using TMDb Metadata
================================================================================
Author      : Breno Farias da Silva
Created     : 2025-11-11
Description :
   This script reads all directories inside the INPUT folder and renames them
   based on metadata extracted from their names and from The Movie Database (TMDb) API.
   The renaming pattern follows the format:
      "Season {SeasonNumberWithTwoDigits} {YearOfThatSeason} {Resolution} {Append_String}"

   Key features include:
      - Automatic extraction of season and resolution from folder names.
      - Online lookup of release year for each season via TMDb API.
      - Clean renaming with standardized format and user-defined suffix.
      - Logging and verbose messages for better monitoring.
      - .env integration for secure API key handling.

Usage:
   1. Create a `.env` file in the project root containing your TMDb API key:
         TMDB_API_KEY=your_api_key_here
   2. Place the folders to be renamed inside the `./INPUT` directory.
   3. Run the script via:
         $ python rename_seasons.py
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
   - Directory names must contain the season (e.g., S01) and resolution (e.g., 1080p).
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
INPUT_DIR = Path("E:/Series")  # The input directory containing the season folders
APPEND_STRINGS = ["Legendado", "Dual", "Dublado", "English"]  # User-defined suffixes for renaming
TMDB_BASE_URL = "https://api.themoviedb.org/3"  # Base URL for TMDb API

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
    Parses folder name like 'Arrow.S01.1080p.Bluray.x265-HiQVE'.

    :param dir_name: Directory name string to parse
    :return: Tuple (series_name, season_number, resolution) or None when parsing fails
    """
    
    match = re.match(r"(?P<series>[A-Za-z0-9\._]+)\.S(?P<season>\d{2})\.(?P<res>\d{3,4}p)", dir_name, re.IGNORECASE)  # Attempt classic regex match for series.Sxx.<res>
    if match:  # If classic pattern matched
        series = match.group("series").replace(".", " ")  # Convert dotted series token to readable series name
        season = int(match.group("season"))  # Convert captured season string to integer
        resolution = match.group("res")  # Capture resolution token (e.g., '1080p')
        return series, season, resolution  # Return parsed tuple for classic pattern

    name_only = os.path.basename(dir_name)  # Extract the final path component or the name itself
    season_match = re.match(r"^Season\s*(?P<num>\d{1,2})", name_only, re.IGNORECASE)  # Match names starting with 'Season <number>'
    if not season_match:  # If no season-style match found
        return None  # Return None when neither classic nor season patterns match

    season = int(season_match.group("num"))  # Convert the matched season number to integer

    res_search = re.search(r"\b(?P<res>\d{3,4}p?)\b", name_only, re.IGNORECASE)  # Search for 3-4 digit resolution with optional 'p'
    if res_search:  # If a resolution-like token was found
        res_digits = re.sub(r"\D", "", res_search.group("res"))  # Strip any non-digit chars to leave digits only
        resolution = f"{res_digits}p"  # Normalize to '<digits>p' format
    else:  # No resolution token found in season directory name
        resolution = None  # Use None when no resolution is present

    try:  # Use pathlib to safely derive parent directory name even if path doesn't exist
        parent_name = Path(dir_name).parent.name  # Get parent directory name component
    except Exception:  # Catch any unexpected error when handling Path operations
        parent_name = ""  # Fallback to empty string when extraction fails

    if not parent_name:  # If parent name is empty, we cannot infer the series
        return None  # Return None because series cannot be inferred safely

    series = parent_name.replace(".", " ")  # Normalize parent directory name by replacing dots with spaces
    return series, season, resolution  # Return parsed tuple inferred from season-style directory


def get_series_id(api_key, series_name):

    """
    Query TMDb search endpoint to find series ID by name.

    :param api_key: TMDb API key string
    :param series_name: Series name to search for on TMDb
    :return: Integer TMDb series id
    """

    url = f"{TMDB_BASE_URL}/search/tv"  # Build search URL for TMDb TV search endpoint
    params = {"api_key": api_key, "query": series_name}  # Prepare query parameters including API key and series name
    response = requests.get(url, params=params)  # Perform HTTP GET request to TMDb search endpoint
    response.raise_for_status()  # Raise exception for HTTP error responses
    data = response.json()  # Parse JSON body from response
    
    results = data.get("results", [])  # Extract results array from TMDb response
    
    if not results:  # If no results were returned from TMDb
        raise ValueError(f"No TMDb series found for '{series_name}'")  # Raise descriptive error when not found
    
    return results[0]["id"]  # Return the id of the first search result


def get_season_year(api_key, series_id, season_number):

    """
    Query TMDb to get season details for a given series_id & season_number.
    Returns the year (e.g., 2012) of that season's air date.

    :param api_key: TMDb API key string
    :param series_id: TMDb series id integer
    :param season_number: Season number integer
    :return: Year string (e.g., '2012') for the season air date
    """

    url = f"{TMDB_BASE_URL}/tv/{series_id}/season/{season_number}"  # Build URL for season details endpoint
    params = {"api_key": api_key}  # Prepare params with API key
    response = requests.get(url, params=params)  # Request season details from TMDb
    response.raise_for_status()  # Raise exception on HTTP errors
    data = response.json()  # Parse JSON payload from response
    air_date = data.get("air_date")  # Attempt to read top-level air_date for the season
    
    if not air_date:  # If top-level air_date is missing, fallback to episode-level air_date
        episodes = data.get("episodes", [])  # Extract episodes array from season details
        
        if episodes and "air_date" in episodes[0]:  # Check first episode for an air_date field
            air_date = episodes[0]["air_date"]  # Use first episode air_date as fallback
        else:  # No air_date available anywhere in response
            raise ValueError(f"No air_date found for series {series_id} season {season_number}")  # Raise descriptive error
        
    return air_date.split("-")[0]  # Return only the year portion of the date string


def standardize_final_name(name):
    """
    Standardize non-numeric words in the final folder name according to project rules.

    Rules:
    - 'Season' is capitalized exactly as 'Season'.
    - Numeric tokens remain unchanged (season number, year).
    - Resolution tokens preserve original casing (e.g., 720p, 4K).
    - Language suffixes are normalized to canonical values from APPEND_STRINGS.
    - All other alphabetic words are Title-cased (first upper, rest lower).
    """

    tokens = name.split()  # Split on whitespace to tokens
    out_tokens = []  # Container for transformed tokens
    for tok in tokens:  # Iterate each token for classification
        if tok.isdigit():  # Numeric token check (keeps leading zeros)
            out_tokens.append(tok)  # Append numeric token unchanged
            continue  # Proceed to next token

        if re.fullmatch(r"(\d{3,4}p|4k)", tok, re.IGNORECASE):  # Resolution detection
            out_tokens.append(tok)  # Append resolution exactly as present
            continue  # Proceed to next token

        matched_suffix = None  # Default no match
        for s in APPEND_STRINGS:  # Iterate configured canonical suffixes
            if tok.lower() == s.lower():  # Case-insensitive equality check
                matched_suffix = s  # Use canonical form from configuration
                break  # Stop searching when found
        if matched_suffix:  # If suffix matched any canonical value
            out_tokens.append(matched_suffix)  # Append canonical suffix exactly
            continue  # Proceed to next token

        if tok.lower() == "season":  # Detect 'season' regardless of case
            out_tokens.append("Season")  # Append canonical 'Season'
            continue  # Proceed to next token

        out_tokens.append(tok.capitalize())  # Title-case the token and append

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


def rename_dirs():
    """
    Iterates through the INPUT_DIR, extracts metadata, fetches the release year from TMDb,
    and renames each directory according to the defined pattern.

    If a directory does not match the regex pattern (i.e., missing season/resolution info),
    the script assumes it contains season subdirectories and processes those instead.

    :return: None
    """

    api_key = load_api_key()  # Load TMDb API key from environment before processing directories
    suffix_group = "|".join([re.escape(s) for s in APPEND_STRINGS])  # Build alternation group from APPEND_STRINGS
    formatted_pattern = rf"^Season\s(?P<season>\d{{2}})\s(?P<year>\d{{4}})(?:\s(?P<resolution>\d{{3,4}}p|4k))?(?:\s(?P<suffix>{suffix_group}))?$"  # Strict formatted folder regex

    for entry in INPUT_DIR.iterdir():  # Iterate over entries in the INPUT_DIR path
        print(f"{BackgroundColors.CYAN}Processing: {entry.name}{Style.RESET_ALL}")  # Output the name of the current entry being processed
        if not entry.is_dir():  # Skip non-directory entries such as files
            continue  # Continue to next entry when current one is not a directory

        parsed = parse_dir_name(entry.name)  # Try parsing the directory name for season metadata

        if parsed:  # Case 1: The directory name contains season and resolution info
            series_name, season_num, resolution = parsed  # Unpack parsed metadata tuple
            season_str = f"{season_num:02d}"  # Format season number as two digits

            formatted_match = re.match(formatted_pattern, entry.name, re.IGNORECASE)  # Match strict formatted pattern against folder name (case-insensitive)
            if formatted_match:  # If folder already matches strict format
                existing_season = formatted_match.group("season")  # Extract existing zero-padded season string
                existing_year = formatted_match.group("year")  # Extract existing year string
                existing_resolution = formatted_match.group("resolution")  # Extract existing optional resolution string
                existing_suffix = formatted_match.group("suffix")  # Extract existing optional suffix string

                try:  # Try to convert existing year to int for validation
                    existing_year_int = int(existing_year)  # Convert the existing year to integer
                except Exception:  # Conversion failed, treat as invalid format
                    existing_year_int = None  # Mark as invalid

                try:  # Try to convert existing season to int for validation
                    existing_season_int = int(existing_season)  # Convert existing season to integer
                except Exception:  # Conversion failed, treat as invalid format
                    existing_season_int = None  # Mark as invalid

                if existing_year_int is not None and existing_season_int is not None:  # Only proceed when both parse as integers
                    series_lookup_name = series_name or entry.parent.name  # Prefer parsed series_name, fallback to parent directory name
                    try:  # Attempt to verify year with TMDb API
                        series_id_chk = get_series_id(api_key, series_lookup_name)  # Lookup series id for verification
                        api_year = get_season_year(api_key, series_id_chk, existing_season_int)  # Fetch year from API for existing season
                    except Exception as e:  # API lookup failed, cannot safely decide to rename
                        print(f"{BackgroundColors.RED}Error verifying year for {series_lookup_name} S{existing_season}: {e}{Style.RESET_ALL}")  # Inform about verification error
                        api_year = None  # Mark API year as unavailable

                    if api_year is not None and str(api_year) == str(existing_year_int):  # If API year matches existing year exactly
                        verbose_output(f"{BackgroundColors.YELLOW}Skipping (already correctly formatted): {entry.name}{Style.RESET_ALL}")  # Inform user that folder is already correct
                        continue  # Skip renaming since folder is already correct

                    if api_year is not None and str(api_year) != str(existing_year_int):  # If API year differs, correct the year in the folder name
                        corrected_name = f"Season {existing_season} {int(api_year)}"  # Build corrected name with new year
                        if existing_resolution:  # Preserve existing resolution when present
                            corrected_name = f"{corrected_name} {existing_resolution}"  # Append resolution after year
                        if existing_suffix:  # If an allowed suffix was present, preserve it
                            corrected_name = f"{corrected_name} {existing_suffix}"  # Append the existing suffix
                        corrected_name = " ".join(corrected_name.split())  # Normalize whitespace
                        corrected_path = entry.parent / corrected_name  # Compute corrected path
                        print(f"{BackgroundColors.GREEN}Correcting year: '{entry.name}' → '{corrected_name}'{Style.RESET_ALL}")  # Inform about correction
                        entry.rename(corrected_path)  # Perform rename to corrected year
                        continue  # Continue to next entry after correction

            try:  # Attempt TMDb lookups which may raise exceptions
                series_id = get_series_id(api_key, series_name)  # Fetch TMDb series id by name
                year = get_season_year(api_key, series_id, season_num)  # Fetch season year using series id
            except Exception as e:  # Catch any exception from TMDb calls
                print(f"{BackgroundColors.RED}Error fetching year for {series_name} S{season_str}: {e}{Style.RESET_ALL}")  # Print error message when lookup fails
                year = None  # Mark year as unavailable after error

            valid_year = None  # Assume invalid until proven otherwise
            if year is not None:  # Only attempt conversion when year is not None
                try:  # Attempt to coerce year to int
                    valid_year = int(year)  # Convert year to integer
                except Exception:  # Conversion failed, mark as invalid
                    valid_year = None  # Ensure invalid status

            if valid_year is None:  # If year could not be determined, skip renaming
                print(f"{BackgroundColors.YELLOW}Skipping (no valid year found): {entry.name}{Style.RESET_ALL}")  # Inform about skipping due to missing year
                continue  # Continue to next entry without renaming

            res_match = re.search(r"\b(\d{3,4}p|4k)\b", entry.name, re.IGNORECASE)  # Find resolution token in folder name
            res_token = res_match.group(0) if res_match else None  # Preserve original matched token or None
            if not res_token:  # If no resolution token in folder name
                res_token = get_resolution_from_first_video(entry)  # Probe first video file for resolution

            append_str = None  # Default to no suffix
            for s in APPEND_STRINGS:  # Iterate in configured order to detect suffix
                if re.search(rf"\b{s}\b", entry.name, re.IGNORECASE):  # Case-insensitive whole-word match
                    append_str = s  # Select the first matching configured suffix
                    break  # Stop after the first match

            name_parts = ["Season", season_str, str(valid_year)]  # Base parts for new name
            if res_token:  # Insert resolution if present in original
                name_parts.append(res_token)  # Preserve original casing for resolution
            if append_str:  # Append suffix only when present
                name_parts.append(append_str)  # Append selected suffix

            new_name = " ".join(name_parts).strip()  # Join parts and trim edges
            new_name = " ".join(new_name.split())  # Collapse multiple internal spaces
            new_name = standardize_final_name(new_name)  # Apply capitalization rules
            new_name = " ".join(new_name.split())  # Normalize whitespace again
            new_path = entry.parent / new_name  # Compute new path for the top-level directory rename

            if new_name == entry.name:  # If name is already correct, skip renaming
                verbose_output(f"{BackgroundColors.YELLOW}Skipping (already named): {entry.name}{Style.RESET_ALL}")  # Inform skip
                continue  # Continue to next entry

            res_present = bool(res_token)  # Detect presence of resolution token
            lang_present = bool(append_str)  # Detect presence of language suffix
            name_color = BackgroundColors.CYAN if (res_present and lang_present) else BackgroundColors.YELLOW  # Choose color
            print(f"{BackgroundColors.GREEN}Renaming: '{name_color}{entry.name}{BackgroundColors.GREEN}' → '{BackgroundColors.CYAN}{new_name}{BackgroundColors.GREEN}'{Style.RESET_ALL}")  # Inform about rename
            entry.rename(new_path)  # Perform the filesystem rename operation for the top-level directory

        else:  # Case 2: The directory likely contains season subdirectories, scan them here
            print(f"{BackgroundColors.YELLOW}No season info found for '{entry.name}'. Scanning subdirectories...{Style.RESET_ALL}")  # Inform user about scanning
            for subentry in entry.iterdir():  # Iterate over subentries inside the top-level directory
                if not subentry.is_dir():  # Skip non-directory subentries such as files
                    continue  # Continue to next subentry when current one is not a directory

                parsed_sub = parse_dir_name(subentry.name)  # Attempt to parse subdirectory name using generic parser
                if parsed_sub:  # If parser returned a tuple, use it directly
                    series_name_sub, season_num_sub, resolution_sub = parsed_sub  # Unpack parsed metadata for subdirectory
                else:  # Fallback: detect 'Season <number>' pattern in subdirectory name and infer series from parent
                    season_match = re.search(r"Season\s+(?P<num>\d{1,2})", subentry.name, re.IGNORECASE)  # Match 'Season <number>' case-insensitively
                    if not season_match:  # If no season-style pattern found in subdirectory name
                        print(f"{BackgroundColors.YELLOW}Skipping (no match in subdir): {subentry.name}{Style.RESET_ALL}")  # Inform about skipped subdirectory
                        continue  # Continue to next subentry when parsing fails
                    season_num_sub = int(season_match.group("num"))  # Convert extracted season number to integer
                    res_search = re.search(r"\b(?P<res>\d{3,4}p?)\b", subentry.name, re.IGNORECASE)  # Search for resolution token
                    if res_search:  # If resolution token found
                        res_digits = re.sub(r"\D", "", res_search.group("res"))  # Strip non-digits to leave digits only
                        resolution_sub = f"{res_digits}p"  # Normalize to '<digits>p' format
                    else:  # No resolution token found for this subdirectory
                        resolution_sub = None  # Use None when no resolution is present
                    series_name_sub = entry.name  # Infer series name from parent directory name

                season_str_sub = f"{season_num_sub:02d}"  # Format season number as two digits for subdirectory

                formatted_match_sub = re.match(formatted_pattern, subentry.name, re.IGNORECASE)  # Match strict formatted pattern against subdirectory name (case-insensitive)
                if formatted_match_sub:  # If the subdirectory already matches strict format
                    existing_season = formatted_match_sub.group("season")  # Extract existing zero-padded season string from subdir
                    existing_year = formatted_match_sub.group("year")  # Extract existing year string from subdir
                    existing_resolution = formatted_match_sub.group("resolution")  # Extract existing optional resolution string from subdir
                    existing_suffix = formatted_match_sub.group("suffix")  # Extract existing optional suffix string from subdir
                    try:  # Try convert existing year to int
                        existing_year_int = int(existing_year)  # Convert to integer
                    except Exception:  # Conversion failed
                        existing_year_int = None  # Mark invalid
                    try:  # Try convert existing season to int
                        existing_season_int = int(existing_season)  # Convert to integer
                    except Exception:  # Conversion failed
                        existing_season_int = None  # Mark invalid

                    if existing_year_int is not None and existing_season_int is not None:  # Only when both valid integers
                        series_lookup_name = series_name_sub or entry.name  # Prefer parsed series_name_sub, fallback to parent directory name for subdir
                        try:  # Attempt to verify year with TMDb API for subdir
                            series_id_chk = get_series_id(api_key, series_lookup_name)  # Lookup series id for verification
                            api_year = get_season_year(api_key, series_id_chk, existing_season_int)  # Fetch year from API for existing season
                        except Exception as e:  # API lookup failed for subdir
                            print(f"{BackgroundColors.RED}Error verifying year for {series_lookup_name} S{existing_season}: {e}{Style.RESET_ALL}")  # Inform about verification error
                            api_year = None  # Mark API year as unavailable

                        if api_year is not None and str(api_year) == str(existing_year_int):  # API year matches existing year
                            verbose_output(f"{BackgroundColors.YELLOW}Skipping (already correctly formatted): {subentry.name}{Style.RESET_ALL}")  # Inform that subdir is already correct
                            continue  # Skip renaming for this subdirectory

                        if api_year is not None and str(api_year) != str(existing_year_int):  # API year differs from folder year
                            corrected_name = f"Season {existing_season} {int(api_year)}"  # Build corrected name with new year
                            if existing_resolution:  # Preserve existing resolution when present
                                corrected_name = f"{corrected_name} {existing_resolution}"  # Append resolution after year
                            if existing_suffix:  # Preserve existing suffix when present
                                corrected_name = f"{corrected_name} {existing_suffix}"  # Append suffix
                            corrected_name = " ".join(corrected_name.split())  # Normalize whitespace
                            corrected_path = subentry.parent / corrected_name  # Compute corrected path
                            print(f"{BackgroundColors.GREEN}Correcting year: '{subentry.name}' → '{corrected_name}'{Style.RESET_ALL}")  # Inform about correction
                            subentry.rename(corrected_path)  # Perform rename to corrected year for subdirectory
                            continue  # Continue to next subentry after correction

                try:  # Attempt TMDb lookups for the subdirectory using resolved series_name_sub and season_num_sub
                    series_id = get_series_id(api_key, series_name_sub)  # Fetch TMDb series id by name for subdir
                    year = get_season_year(api_key, series_id, season_num_sub)  # Fetch season year for subdir
                except Exception as e:  # Catch any exception from TMDb calls for subdir
                    print(f"{BackgroundColors.RED}Error fetching year for {series_name_sub} S{season_str_sub}: {e}{Style.RESET_ALL}")  # Print error message when lookup fails for subdir
                    year = None  # Mark year as unavailable after error

                valid_year = None  # Assume invalid until proven otherwise
                if year is not None:  # Only attempt conversion when year is not None
                    try:  # Attempt to coerce year to int
                        valid_year = int(year)  # Convert year to integer
                    except Exception:  # Conversion failed, mark as invalid
                        valid_year = None  # Ensure invalid status

                if valid_year is None:  # If year could not be determined, skip renaming this subdirectory
                    print(f"{BackgroundColors.YELLOW}Skipping (no valid year found): {subentry.name}{Style.RESET_ALL}")  # Inform about skipping due to missing year
                    continue  # Continue to next subentry without renaming

                res_match_sub = re.search(r"\b(\d{3,4}p|4k)\b", subentry.name, re.IGNORECASE)  # Find resolution token
                res_token_sub = res_match_sub.group(0) if res_match_sub else None  # Preserve matched token or None
                if not res_token_sub:  # If no resolution token in subdirectory name
                    res_token_sub = get_resolution_from_first_video(subentry)  # Probe first video file for resolution

                append_str = None  # Default to no suffix
                for s in APPEND_STRINGS:  # Iterate in configured order
                    if re.search(rf"\b{s}\b", subentry.name, re.IGNORECASE):  # Case-insensitive whole-word match
                        append_str = s  # Select the first matching configured suffix
                        break  # Stop after the first match

                name_parts = ["Season", season_str_sub, str(valid_year)]  # Base parts
                if res_token_sub:  # Insert resolution if present in original
                    name_parts.append(res_token_sub)  # Preserve original casing for resolution
                if append_str:  # Append suffix only when present
                    name_parts.append(append_str)  # Append selected suffix

                new_name = " ".join(name_parts).strip()  # Join parts and trim edges
                new_name = " ".join(new_name.split())  # Collapse multiple internal spaces
                new_name = standardize_final_name(new_name)  # Apply capitalization rules for subdir name
                new_name = " ".join(new_name.split())  # Normalize whitespace again after standardization
                new_path = subentry.parent / new_name  # Compute new path for subdirectory rename

                if new_name == subentry.name:  # If new name equals current, skip renaming
                    verbose_output(f"{BackgroundColors.YELLOW}Skipping (already named): {subentry.name}{Style.RESET_ALL}")  # Inform skip
                    continue  # Continue to next subentry

                res_present = bool(res_token_sub)  # Detect presence of resolution token
                lang_present = bool(append_str)  # Detect presence of language suffix
                name_color = BackgroundColors.CYAN if (res_present and lang_present) else BackgroundColors.YELLOW  # Choose color
                print(f"{BackgroundColors.GREEN}Renaming subdir: '{name_color}{subentry.name}{BackgroundColors.GREEN}' → '{BackgroundColors.CYAN}{new_name}{BackgroundColors.GREEN}'{Style.RESET_ALL}")  # Inform about the subdirectory rename
                subentry.rename(new_path)  # Perform the filesystem rename operation for subdirectory
                
        print(f"\n")  # Add spacing after processing a top-level directory


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
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Season Directory Renamer{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
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
