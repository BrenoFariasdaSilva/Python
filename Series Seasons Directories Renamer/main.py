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
import json  # For writing JSON report files
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For parsing directory names
import requests  # For API requests
import subprocess  # For probing video metadata with ffprobe
from colorama import Style  # For coloring the terminal
from dotenv import load_dotenv  # For loading environment variables
from pathlib import Path  # For path handling
from tqdm import tqdm  # For displaying one inline colored progress bar during directory processing


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
INPUT_DIRS = [Path("./Input"), Path("./Inputs"), Path(f"F:/Series/"), Path(f"G:/Animes/"), Path(f"G:/Series/")]  # The input directory or list of input directories
LANGUAGE_OPTIONS = ["Dual", "Dublado", "English", "Legendado", "Nacional"]  # User-defined suffixes for renaming
TMDB_BASE_URL = "https://api.themoviedb.org/3"  # Base URL for TMDb API
IGNORE_DIR_REGEX = re.compile(r'^(featurettes|extras|making[-_\s]?of|behind[ _-]?the[ _-]?scenes|specials)$', re.IGNORECASE)  # Regex for ignore dirs
FPS_PATTERN = re.compile(r"(?<!\d)60\s*fps(?![A-Za-z0-9])", re.IGNORECASE)  # Detect 60FPS/60 fps variants anywhere in a season directory name
CANONICAL_FPS_TOKEN = "60FPS"  # Canonical frame-rate token preserved immediately after the resolution

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


def output_rename_change(change_desc: str, old_name: str, new_name: str) -> None:
    """
    Output one persistent rename line without breaking the active tqdm progress bar.

    Static labels remain green while dynamic change descriptions and directory
    names are cyan, matching the terminal color conventions used by this project.

    :param change_desc: Human-readable change description returned by detect_changes().
    :param old_name: Original directory name.
    :param new_name: Final renamed directory name.
    :return: None
    """

    tqdm.write(
        f"{BackgroundColors.GREEN}Renaming subdir "
        f"{BackgroundColors.CYAN}({change_desc})"
        f"{BackgroundColors.GREEN}: "
        f"'{BackgroundColors.CYAN}{old_name}{BackgroundColors.GREEN}' → "
        f"'{BackgroundColors.CYAN}{new_name}{BackgroundColors.GREEN}'"
        f"{Style.RESET_ALL}"
    )  # Write above the active progress bar so the bar remains an inline update


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

    verbose_output(f"{BackgroundColors.GREEN}Verifying for Chocolatey...{Style.RESET_ALL}")  # Output the verbose message

    choco_installed = (
        subprocess.run(["choco", "--version"], capture_output=True, text=True).returncode == 0
    )  # Verify if Chocolatey is installed

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

    release_match = re.match(r"(?P<series>[A-Za-z0-9\._]+?)\.S(?P<season>\d{2})\.", dir_name, re.IGNORECASE)  # Attempt release-style match for series.Sxx.extra-tokens with resolution anywhere in name
    if release_match:  # If release-style pattern with extra tokens between season and resolution matched
        series = release_match.group("series").replace(".", " ")  # Convert dotted series token to readable series name
        season = int(release_match.group("season"))  # Convert captured season string to integer
        res_search = re.search(r"\b(\d{3,4}p|4k)\b", dir_name, re.IGNORECASE)  # Search for resolution token anywhere in the full directory name
        resolution = res_search.group(0) if res_search else None  # Preserve matched resolution casing or use None when absent
        return series, season, resolution  # Return parsed tuple for release-style pattern

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


def normalize_series_lookup_name(series_name: str) -> str:
    """
    Normalize a series title for conservative TMDb candidate comparison.

    :param series_name: Series title from the directory or TMDb result.
    :return: Lowercase alphanumeric comparison string.
    """

    return re.sub(r"[^a-z0-9]+", "", series_name.casefold())  # Remove punctuation/spacing differences for title comparison


def get_series_id(
    api_key,
    series_name,
    required_seasons: set[int] | None = None,
    expected_years: dict[int, int] | None = None,
):
    """
    Query TMDb and resolve the most appropriate series ID.

    When required seasons are provided, candidates are validated against those
    actual season numbers instead of blindly returning the first search result.
    Candidate selection prioritizes season coverage, then title similarity, then
    proximity to already-known season years.

    :param api_key: TMDb API key string.
    :param series_name: Series name to search for on TMDb.
    :param required_seasons: Optional set of season numbers that must be considered.
    :param expected_years: Optional mapping of season number to existing folder year.
    :return: Integer TMDb series ID.
    """

    url = f"{TMDB_BASE_URL}/search/tv"  # Build search URL for TMDb TV search endpoint
    params = {"api_key": api_key, "query": series_name}  # Prepare query parameters including API key and series name
    response = requests.get(url, params=params)  # Perform HTTP GET request to TMDb search endpoint
    response.raise_for_status()  # Raise exception for HTTP error responses
    data = response.json()  # Parse JSON body from response
    results = data.get("results", [])  # Extract results array from TMDb response

    if not results:  # If no results were returned from TMDb
        raise ValueError(f"No TMDb series found for '{series_name}'")

    if not required_seasons:  # Preserve simple behavior when no season context is available
        return results[0]["id"]

    required_seasons = {int(season) for season in required_seasons}  # Normalize required season numbers
    expected_years = expected_years or {}  # Normalize optional expected-year mapping
    normalized_query = normalize_series_lookup_name(series_name)  # Normalize requested title
    candidate_scores = []  # Store sortable candidate scores

    for search_position, result in enumerate(results[:10]):  # Inspect a bounded set of top TMDb candidates
        series_id = result.get("id")

        if series_id is None:
            continue

        candidate_name = str(result.get("name") or result.get("original_name") or "")
        normalized_candidate = normalize_series_lookup_name(candidate_name)
        matched_seasons = 0
        year_distance = 0

        for season_number in sorted(required_seasons):  # Validate every season present locally
            try:
                candidate_year = int(get_season_year(api_key, int(series_id), season_number))
            except Exception:
                continue

            matched_seasons += 1

            if season_number in expected_years:
                year_distance += abs(candidate_year - int(expected_years[season_number]))

        if matched_seasons == 0:
            continue

        if normalized_candidate == normalized_query:
            title_penalty = 0
        elif normalized_query and normalized_query in normalized_candidate:
            title_penalty = 1
        elif normalized_candidate and normalized_candidate in normalized_query:
            title_penalty = 1
        else:
            title_penalty = 2

        candidate_scores.append(
            (
                -matched_seasons,  # Prefer candidates containing the greatest number of local seasons
                title_penalty,  # Then prefer the closest title match
                year_distance,  # Then prefer plausible season-year proximity
                search_position,  # Preserve TMDb ordering as deterministic tie-breaker
                int(series_id),
            )
        )

    if not candidate_scores:
        raise ValueError(
            f"No TMDb series candidate for '{series_name}' contains the requested seasons: "
            f"{', '.join(str(season) for season in sorted(required_seasons))}"
        )

    candidate_scores.sort()
    return candidate_scores[0][4]

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
        
        if episodes and "air_date" in episodes[0]:  # Verify first episode for an air_date field
            air_date = episodes[0]["air_date"]  # Use first episode air_date as fallback
        else:  # No air_date available anywhere in response
            raise ValueError(f"No air_date found for series {series_id} season {season_number}")  # Raise descriptive error
        
    return air_date.split("-")[0]  # Return only the year portion of the date string


def detect_60fps_token(name: str) -> str | None:
    """
    Detect a 60 FPS marker anywhere in a season directory name.

    Accepted forms are case-insensitive and may contain whitespace between the
    numeric value and FPS, including "60FPS", "60fps", "60 FPS", and "60 fps".

    :param name: Directory name to inspect.
    :return: Canonical "60FPS" token when detected, otherwise None.
    """

    return CANONICAL_FPS_TOKEN if FPS_PATTERN.search(name) else None  # Normalize every accepted variant to one canonical token


def remove_60fps_token(name: str) -> str:
    """
    Remove recognized 60 FPS markers from a name before canonical reconstruction.

    :param name: Directory name that may contain a 60 FPS marker.
    :return: Name without the detected marker and with normalized whitespace.
    """

    return " ".join(FPS_PATTERN.sub(" ", name).split())  # Remove only the recognized marker so it can be reinserted in canonical position


def standardize_final_name(name):
    """
    Standardize non-numeric words in the final folder name according to project rules.

    Rules:
    - 'Season' is capitalized exactly as 'Season'.
    - Numeric tokens remain unchanged (season number, year).
    - Resolution tokens preserve original casing (e.g., 720p, 4K).
    - Language suffixes are normalized to canonical values from LANGUAGE_OPTIONS.
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

        if tok.casefold() == CANONICAL_FPS_TOKEN.casefold():  # Preserve canonical frame-rate marker
            out_tokens.append(CANONICAL_FPS_TOKEN)  # Force exact "60FPS" casing
            continue  # Proceed to next token

        matched_suffix = None  # Default no match
        for s in LANGUAGE_OPTIONS:  # Iterate configured canonical suffixes
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

    old_fps = detect_60fps_token(old_name)  # Detect 60 FPS marker in original name
    new_fps = detect_60fps_token(new_name)  # Detect 60 FPS marker in generated name
    old_fps_exact = re.search(r"(?<!\d)60FPS(?![A-Za-z0-9])", old_name)  # Detect already-canonical exact token
    if new_fps and not old_fps:  # Frame-rate metadata was newly restored/preserved from another source
        tags.append("Add 60FPS")  # Tag explicit frame-rate addition
    elif old_fps and new_fps and old_fps_exact is None:  # Original marker existed but used non-canonical spacing/casing
        tags.append("Normalize 60FPS")  # Tag canonicalization such as "60 fps" -> "60FPS"

    part_re = re.compile(r"\b(part|pt|volume|vol|cour|arc)\b\.?\s*([A-Za-z0-9]+)\b", re.IGNORECASE)  # Part token regex
    old_part = part_re.search(old_name)  # Find part in old name
    new_part = part_re.search(new_name)  # Find part in new name
    if new_part and not old_part:  # Part added
        tags.append("Add Part")  # Tag for added part

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
    Unified resolution detection for a given season folder.

    1) Verify for resolution token in `name_hint` using the project's regex.
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


def format_season_num(season):
    """
    Return a season number zero-padded to two digits.

    Accepts int or string values. If conversion fails, returns the original value.
    """
    
    try:  # Normalize to int then format with two digits
        return f"{int(season):02d}"
    except Exception:  # If conversion fails, return original (avoid raising)
        return season


def strip_expected_series_prefix(directory_name: str, series_name: str) -> str:
    """
    Remove the current parent-series prefix from one season directory name.

    :param directory_name: Current season directory name.
    :param series_name: Parent series directory name.
    :return: Season-specific portion without the parent-series prefix.
    """

    series_name = series_name.strip()
    directory_name = directory_name.strip()
    expected_prefix = f"{series_name} - "

    if directory_name.casefold().startswith(expected_prefix.casefold()):
        return directory_name[len(expected_prefix):].strip()

    malformed_prefix_pattern = rf"^{re.escape(series_name)}\s*-?\s*"
    stripped_name = re.sub(malformed_prefix_pattern, "", directory_name, count=1, flags=re.IGNORECASE).strip()
    return stripped_name or directory_name


def build_change_labels(change_desc: str) -> list[str]:
    """
    Convert detect_changes() tags into report labels.

    :param change_desc: Combined human-readable change tags.
    :return: Ordered unique report labels.
    """

    tags = [tag.strip() for tag in change_desc.split("+")] if change_desc else []
    labels = []

    mappings = (
        ("Add Prefix", "Prefix Added"),
        ("Add Year", "Year Added"),
        ("Correct Year", "Year Corrected"),
        ("Add Resolution", "Resolution Added"),
        ("Correct Resolution", "Resolution Corrected"),
        ("Add 60FPS", "60FPS Preserved"),
        ("Normalize 60FPS", "60FPS Normalized"),
        ("Remove Duplicate Tokens", "Duplicate Tokens Removed"),
        ("Reorder Tokens", "Format Reordered"),
        ("Normalize Format", "Whitespace Normalized"),
        ("Standardize Casing", "Whitespace Normalized"),
    )

    for tag_fragment, report_label in mappings:
        if any(tag_fragment in tag for tag in tags) and report_label not in labels:
            labels.append(report_label)

    return labels


def record_directory_change(
    report_data: dict,
    root_path: Path,
    old_name: str,
    new_name: str,
    change_desc: str,
) -> None:
    """
    Record one successful directory rename in report_data.

    :param report_data: Mutable report dictionary for the current execution.
    :param root_path: Configured input root containing the renamed series.
    :param old_name: Directory name before the rename.
    :param new_name: Directory name after the rename.
    :param change_desc: Human-readable change description.
    :return: None
    """

    root_key = str(root_path)

    if root_key not in report_data["input_dirs"]:
        report_data["input_dirs"][root_key] = {
            "directories_modified": [],
            "video_files_renamed": [],
        }

    report_data["input_dirs"][root_key]["directories_modified"].append(
        {
            "old_name": old_name,
            "new_name": new_name,
            "changes": build_change_labels(change_desc),
        }
    )


def ensure_nested_season_prefix(
    subentry: Path,
    series_name: str,
    root_path: Path,
    report_data: dict,
) -> Path:
    """
    Ensure a nested season directory has exactly one canonical parent-series prefix.

    This prefix rename is physically performed before any TMDb year validation or
    other metadata-based normalization, and the updated Path is returned.

    :param subentry: Current nested season directory path.
    :param series_name: Parent series directory name.
    :param root_path: Configured input root for reporting.
    :param report_data: Mutable report dictionary.
    :return: Updated Path after prefix normalization.
    """

    series_name = series_name.strip()
    season_name = strip_expected_series_prefix(subentry.name, series_name)
    expected_name = " ".join(f"{series_name} - {season_name}".split())

    if subentry.name == expected_name:
        return subentry

    target_path = subentry.parent / expected_name

    if target_path.exists() and target_path != subentry:
        raise FileExistsError(f"Cannot add series prefix because destination already exists: {target_path}")

    old_name = subentry.name
    change_desc = detect_changes(old_name, expected_name) or "Add Prefix"
    output_rename_change(change_desc, old_name, expected_name)
    subentry.rename(target_path)

    if not target_path.exists():
        raise RuntimeError(f"Prefix rename did not create expected directory: {target_path}")

    record_directory_change(report_data, root_path, old_name, expected_name, change_desc)
    return target_path


def format_progress_input_dir(root_path: Path) -> str:
    """
    Format one configured input directory for progress-bar descriptions.

    Drive-letter paths remain in Unix-style form such as "G:/Series/", while
    relative project paths are displayed explicitly as "./Input/".

    :param root_path: Configured input directory path.
    :return: Human-readable forward-slash input-directory string.
    """

    display_path = root_path.as_posix().rstrip("/")  # Normalize separators and remove duplicate trailing separators

    if (
        display_path
        and not display_path.startswith("./")
        and not display_path.startswith("../")
        and not display_path.startswith("/")
        and not re.match(r"^[A-Za-z]:/", display_path)
    ):  # Preserve explicit relative-root notation for local project directories
        display_path = f"./{display_path}"

    return f"{display_path}/" if display_path else "./"  # Guarantee exactly one trailing slash


def get_relative_series_path(series_path: Path, root_path: Path) -> str:
    """
    Return the current series path relative to its configured input directory.

    :param series_path: Current top-level series directory.
    :param root_path: Configured input directory containing the series.
    :return: Forward-slash relative series path.
    """

    try:
        return series_path.relative_to(root_path).as_posix()  # Prefer exact path relative to the active input root
    except ValueError:
        return series_path.name  # Fall back safely when path objects cannot be relativized


def discover_processable_series_dirs(root_path: Path) -> list[Path]:
    """
    Discover immediate series directories eligible for one input-root progress bar.

    Ignored utility directories are excluded before progress-bar creation so an
    input directory containing no processable series does not create an empty bar.

    :param root_path: Configured input directory to inspect.
    :return: Sorted immediate series directories.
    """

    return sorted(
        (
            path
            for path in root_path.iterdir()
            if path.is_dir() and not re.match(IGNORE_DIR_REGEX, path.name.strip())
        ),
        key=lambda path: path.name.casefold(),
    )  # Keep progress totals deterministic and exclude configured non-series directories


def rename_dirs():
    """
    Iterates through the INPUT_DIRS, extracts metadata, fetches the release year from TMDb,
    and renames each directory according to the defined pattern.

    If a directory does not match the regex pattern (i.e., missing season/resolution info),
    the script assumes it contains season subdirectories and processes those instead.

    :return: None
    """

    api_key = load_api_key()  # Load TMDb API key from environment before processing directories
    
    report_data = {  # Initialize the report data structure before processing
        "generated_at": None,  # Placeholder for ISO timestamp to be set by generate_report
        "input_dirs": {},  # Container to hold per-root modification records
    }  # End report_data initialization
    
    suffix_group = "|".join([re.escape(s) for s in LANGUAGE_OPTIONS])  # Build alternation group from LANGUAGE_OPTIONS
    formatted_pattern = rf"^Season\s(?P<season>\d{{2}})\s(?P<year>\d{{4}})(?:\s(?P<resolution>\d{{3,4}}p|4k))?(?:\s(?P<fps>60\s*fps))?(?:\s(?P<suffix>{suffix_group}))?$"  # Strict formatted folder regex including optional 60 FPS marker after resolution

    roots = INPUT_DIRS if isinstance(INPUT_DIRS, (list, tuple)) else [INPUT_DIRS]  # Normalize INPUT_DIRS to a list of paths

    for root in roots:  # Process each configured input directory independently
        root_path = Path(root)  # Normalize configured root to Path

        if not root_path.exists() or not root_path.is_dir():  # Skip missing/non-directory roots without creating a progress bar
            verbose_output(
                true_string=f"{BackgroundColors.YELLOW}Input path not found or is not a directory, skipping: "
                f"{BackgroundColors.CYAN}{root_path.as_posix()}{Style.RESET_ALL}"
            )
            continue

        try:
            root_entries = discover_processable_series_dirs(root_path)  # Discover only processable series for this root
        except Exception as exc:
            verbose_output(
                true_string=f"{BackgroundColors.YELLOW}Cannot read input path, skipping: "
                f"{BackgroundColors.CYAN}{root_path.as_posix()}{BackgroundColors.YELLOW} - {exc}{Style.RESET_ALL}"
            )
            continue

        if not root_entries:  # Do not create a meaningless 0/0 progress bar for empty roots
            verbose_output(
                true_string=f"{BackgroundColors.YELLOW}No processable series directories found in: "
                f"{BackgroundColors.CYAN}{format_progress_input_dir(root_path)}{Style.RESET_ALL}"
            )
            continue

        root_display = format_progress_input_dir(root_path)  # Build stable Unix-style root label for this progress bar
        progress_bar = tqdm(
            root_entries,
            total=len(root_entries),
            desc=f"{BackgroundColors.GREEN}Processing {BackgroundColors.CYAN}{root_display}{Style.RESET_ALL}",
            unit="series",
            dynamic_ncols=True,
            leave=True,
            colour="green",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} "
            "[{elapsed}<{remaining}, {rate_fmt}] {postfix}",
        )  # Create exactly one inline progress bar for this non-empty input directory

        for idx, entry in enumerate(progress_bar, start=1):  # Process only the series belonging to the active input root
            series_relative_path = get_relative_series_path(entry, root_path)  # Keep displayed series path relative to this root
            progress_bar.set_postfix_str(
                f"{BackgroundColors.GREEN}Series: {BackgroundColors.CYAN}{series_relative_path}{Style.RESET_ALL}",
                refresh=True,
            )  # Show the relative series path without replacing it with nested season paths
            if not entry.is_dir():  # Skip non-directory entries such as files
                continue  # Continue to next entry when current one is not a directory

            if re.match(IGNORE_DIR_REGEX, entry.name.strip()):  # Skip configured ignore directories at top-level
                verbose_output(f"{BackgroundColors.YELLOW}Ignoring top-level directory: {entry.name}{Style.RESET_ALL}")  # Verbose notification when skipping
                continue  # Continue to next entry when current one is an ignored directory

            parsed = parse_dir_name(entry.name)  # Try parsing the directory name for season metadata

            if parsed:  # Case 1: The directory name contains season and resolution info
                series_name, season_num, resolution = parsed  # Unpack parsed metadata tuple
                season_str = f"{season_num:02d}"  # Format season number as two digits
                append_str = None  # Default to no suffix (safe default for earlier checks)
                existing_year_int = None  # Reset existing year so prior loop iterations can never leak state

                formatted_match = re.match(formatted_pattern, entry.name, re.IGNORECASE)  # Match strict formatted pattern against folder name (case-insensitive)
                if formatted_match:  # If folder already matches strict format
                    existing_season = formatted_match.group("season")  # Extract existing season string
                    existing_season = format_season_num(existing_season)  # Normalize to two digits
                    existing_year = formatted_match.group("year")  # Extract existing year string
                    existing_resolution = formatted_match.group("resolution")  # Extract existing optional resolution string
                    existing_fps = CANONICAL_FPS_TOKEN if formatted_match.group("fps") else None  # Preserve optional 60 FPS marker canonically
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
                            api_year = None  # Mark API year as unavailable

                        if api_year is not None and str(api_year) == str(existing_year_int):  # If API year matches existing year exactly
                            verbose_output(f"{BackgroundColors.YELLOW}Skipping (already correctly formatted): {entry.name}{Style.RESET_ALL}")  # Inform user that folder is already correct
                            continue  # Skip renaming since folder is already correct

                        if api_year is not None and str(api_year) != str(existing_year_int):  # If API year differs, correct the year in the folder name
                            part_match_existing = re.search(r"\b(?P<label>part|pt|volume|vol|cour|arc)\b\.?\s*(?P<num>[A-Za-z0-9]+)\b", entry.name, re.IGNORECASE)  # Detect existing part token
                            if part_match_existing:  # If an existing part token exists
                                part_label_existing = part_match_existing.group("label")  # Extract existing label
                                part_num_existing = part_match_existing.group("num")  # Extract existing number/alpha
                                existing_part_token = f"{part_label_existing.capitalize()} {part_num_existing}"  # Standardize existing part token
                            else:  # No existing part token
                                existing_part_token = None  # Ensure None when absent
                            corrected_name = f"Season {existing_season} {int(api_year)}"  # Build corrected name with new year
                            if existing_part_token:  # If a part token should be preserved
                                corrected_name = f"{corrected_name} {existing_part_token}"  # Append part token after year
                            if existing_resolution:  # Preserve existing resolution when present
                                corrected_name = f"{corrected_name} {existing_resolution}"  # Append resolution after year/part
                            if existing_fps:  # Preserve 60 FPS metadata after resolution
                                corrected_name = f"{corrected_name} {existing_fps}"  # Keep canonical 60FPS immediately after resolution
                            if existing_suffix:  # If an allowed suffix was present, preserve it
                                corrected_name = f"{corrected_name} {existing_suffix}"  # Append the existing suffix after frame-rate metadata
                            corrected_name = " ".join(corrected_name.split())  # Normalize whitespace
                            corrected_path = entry.parent / corrected_name  # Compute corrected path
                            change_desc = detect_changes(entry.name, corrected_name) or "Correct Year"  # Describe the exact rename before changing the filesystem
                            output_rename_change(change_desc, entry.name, corrected_name)  # Persist only the actual change above the progress bar
                            entry.rename(corrected_path)  # Perform rename to corrected year
                            
                            if corrected_path.exists():  # Only record when filesystem shows the rename succeeded
                                root_key = str(root_path)  # Use string form of input root as dictionary key
                                if root_key not in report_data["input_dirs"]:  # Lazily create per-root entry when first change occurs
                                    report_data["input_dirs"][root_key] = {  # Initialize per-root structure
                                        "directories_modified": [],  # List to hold directory modifications
                                        "video_files_renamed": [],  # List to hold video rename records (unused here but preserved)
                                    }  # End initialization
                                change_desc = detect_changes(entry.name, corrected_name)  # Compute a human-readable list of changes
                                tags = [t.strip() for t in change_desc.split("+")] if change_desc else []  # Split tags from detect_changes
                                labels = []  # Collect mapped labels for the report
                                if any("Add Year" in t for t in tags):  # Map to Year Added
                                    labels.append("Year Added")  # Append label
                                if any("Correct Year" in t for t in tags):  # Map to Year Corrected
                                    labels.append("Year Corrected")  # Append label
                                if any("Add Resolution" in t for t in tags):  # Map to Resolution Added
                                    labels.append("Resolution Added")  # Append label
                                if any("Correct Resolution" in t for t in tags):  # Map to Resolution Corrected
                                    labels.append("Resolution Corrected")  # Append label
                                if any("Remove Duplicate Tokens" in t for t in tags):  # Map to Duplicate Tokens Removed
                                    labels.append("Duplicate Tokens Removed")  # Append label
                                if any("Reorder Tokens" in t for t in tags):  # Map to Format Reordered
                                    labels.append("Format Reordered")  # Append label
                                if any("Normalize Format" in t or "Standardize Casing" in t for t in tags):  # Map spacing/casing changes
                                    labels.append("Whitespace Normalized")  # Append label
                                try:  # Detect parentheses removal (guard regex)
                                    if re.search(r"\(\d{4}\)", entry.name) and not re.search(r"\(\d{4}\)", corrected_name):  # Parentheses removed
                                        labels.append("Parentheses Removed")  # Append label
                                except Exception:  # If regex fails
                                    pass  # Ignore detection errors
                                try:  # Detect 4K -> 2160p conversion (guard regex)
                                    if re.search(r"\b4k\b", entry.name, re.IGNORECASE) and "2160p" in corrected_name.lower():  # 4K converted
                                        labels.append("4K Converted to 2160p")  # Append label
                                except Exception:  # If detection fails
                                    pass  # Ignore detection errors
                                try:  # Detect language normalization differences (guard regex)
                                    old_lang_match = re.search(r"\b(Dual|Dublado|English|Legendado|Nacional)\b", entry.name, re.IGNORECASE)  # Find old lang token
                                    if old_lang_match:  # If an old language token existed
                                        old_lang_raw = old_lang_match.group(0)  # Extract raw matched token
                                        if append_str and old_lang_raw != append_str:  # If canonical differs from raw
                                            labels.append("Language Normalized")  # Append label
                                except Exception:  # On detection errors
                                    pass  # Ignore
                                seen = set()  # Deduplicate labels while preserving order
                                final_labels = []  # Ordered unique labels
                                for L in labels:  # Iterate computed labels
                                    if L not in seen:  # If label not yet recorded
                                        seen.add(L)  # Mark seen
                                        final_labels.append(L)  # Append to final list
                                report_data["input_dirs"][root_key]["directories_modified"].append({  # Append directory modification record
                                    "old_name": entry.name,  # Record old directory name
                                    "new_name": corrected_name,  # Record new directory name
                                    "changes": final_labels,  # Record detected change labels
                                })  # End append directory record
                            continue  # Continue to next entry after correction

                try:  # Attempt TMDb lookups which may raise exceptions
                    series_id = get_series_id(api_key, series_name)  # Fetch TMDb series id by name
                    year = get_season_year(api_key, series_id, season_num)  # Fetch season year using series id
                except Exception as e:  # Catch any exception from TMDb calls
                    verbose_output(true_string=f"{BackgroundColors.RED}Error fetching year for {series_name} S{season_str}: {e}{Style.RESET_ALL}")  # Keep lookup diagnostics hidden unless VERBOSE=True
                    year = None  # Mark year as unavailable after error

                valid_year = None  # Assume invalid until proven otherwise
                if year is not None:  # Only attempt conversion when year is not None
                    try:  # Attempt to coerce year to int
                        valid_year = int(year)  # Convert year to integer
                    except Exception:  # Conversion failed, mark as invalid
                        valid_year = None  # Ensure invalid status

                # existing_year_int is initialized explicitly for this entry above; never recover it from locals().
                if valid_year is None and existing_year_int is not None:  # If TMDb didn't provide a year but folder had one
                    valid_year = existing_year_int  # Use the existing year instead of aborting

                res_token = determine_resolution(entry, entry.name)  # Determine resolution for this season folder
                fps_token = detect_60fps_token(entry.name)  # Detect 60 FPS metadata anywhere in the original directory name

                part_match = re.search(r"\b(?P<label>part|pt|volume|vol|cour|arc)\b\.?\s*(?P<num>[A-Za-z0-9]+)\b", entry.name, re.IGNORECASE)  # Detect part/segment tokens
                if part_match:  # If a part token was found
                    part_label = part_match.group("label")  # Extract matched label token
                    part_num = part_match.group("num")  # Extract matched numeric/alpha part token
                    part_token = f"{part_label.capitalize()} {part_num}"  # Standardize casing and build token
                else:  # No part token found
                    part_token = None  # Ensure part_token is None when absent

                append_str = None  # Default to no suffix
                for s in LANGUAGE_OPTIONS:  # Iterate in configured order to detect suffix
                    if re.search(rf"\b{s}\b", entry.name, re.IGNORECASE):  # Case-insensitive whole-word match
                        append_str = s  # Select the first matching configured suffix
                        break  # Stop after the first match

                name_parts = ["Season", season_str]  # Base parts for new name (year optional)
                if valid_year is not None:  # Append year only when available
                    name_parts.append(str(valid_year))  # Add year token when present
                if part_token:  # Insert part token after year when present
                    name_parts.append(part_token)  # Preserve standardized part token
                if res_token:  # Insert resolution if present in original
                    name_parts.append(res_token)  # Preserve original casing for resolution
                if fps_token:  # Preserve detected 60 FPS metadata
                    name_parts.append(fps_token)  # Canonically place 60FPS immediately after resolution
                if append_str:  # Append suffix only when present
                    name_parts.append(append_str)  # Append selected suffix after frame-rate metadata

                new_name = " ".join(name_parts).strip()  # Join parts and trim edges
                new_name = " ".join(new_name.split())  # Collapse multiple internal spaces
                new_name = standardize_final_name(new_name)  # Apply capitalization rules
                new_name = " ".join(new_name.split())  # Normalize whitespace again
                new_path = entry.parent / new_name  # Compute new path for the top-level directory rename

                if new_name == entry.name:  # If name is already correct, skip renaming
                    verbose_output(f"{BackgroundColors.YELLOW}Skipping (already named): {entry.name}{Style.RESET_ALL}")  # Inform skip
                    continue  # Continue to next entry
                
                change_desc = detect_changes(entry.name, new_name)  # Detect descriptive change tags
                if not change_desc:  # If detect_changes returned empty, nothing to do
                    verbose_output(f"{BackgroundColors.YELLOW}Skipping (no detected meaningful change): {entry.name}{Style.RESET_ALL}")  # Inform skip
                    continue  # Continue to next entry
                
                res_present = bool(res_token)  # Detect presence of resolution token
                lang_present = bool(append_str)  # Detect presence of language suffix
                name_color = BackgroundColors.CYAN if (res_present and lang_present) else BackgroundColors.YELLOW  # Choose color
                
                output_rename_change(change_desc, entry.name, new_name)  # Persist only the actual rename above the inline progress bar
                entry.rename(new_path)  # Perform the filesystem rename operation for the top-level directory
                if new_path.exists():  # Only record when filesystem shows the rename succeeded
                    root_key = str(root_path)  # Use string form of input root as dictionary key
                    if root_key not in report_data["input_dirs"]:  # Lazily create per-root entry when first change occurs
                        report_data["input_dirs"][root_key] = {  # Initialize per-root structure
                            "directories_modified": [],  # List to hold directory modifications
                            "video_files_renamed": [],  # List to hold video rename records (unused here but preserved)
                        }  # End initialization
                    tags = [t.strip() for t in change_desc.split("+")] if change_desc else []  # Split tags from detect_changes
                    labels = []  # Collect mapped labels for the report
                    if any("Add Year" in t for t in tags):  # Map to Year Added
                        labels.append("Year Added")  # Append label
                    if any("Correct Year" in t for t in tags):  # Map to Year Corrected
                        labels.append("Year Corrected")  # Append label
                    if any("Add Resolution" in t for t in tags):  # Map to Resolution Added
                        labels.append("Resolution Added")  # Append label
                    if any("Correct Resolution" in t for t in tags):  # Map to Resolution Corrected
                        labels.append("Resolution Corrected")  # Append label
                    if any("Remove Duplicate Tokens" in t for t in tags):  # Map to Duplicate Tokens Removed
                        labels.append("Duplicate Tokens Removed")  # Append label
                    if any("Reorder Tokens" in t for t in tags):  # Map to Format Reordered
                        labels.append("Format Reordered")  # Append label
                    if any("Normalize Format" in t or "Standardize Casing" in t for t in tags):  # Map spacing/casing changes
                        labels.append("Whitespace Normalized")  # Append label
                    try:  # Detect parentheses removal (guard regex)
                        if re.search(r"\(\d{4}\)", entry.name) and not re.search(r"\(\d{4}\)", new_name):  # Parentheses removed
                            labels.append("Parentheses Removed")  # Append label
                    except Exception:  # If regex fails
                        pass  # Ignore detection errors
                    try:  # Detect 4K -> 2160p conversion (guard regex)
                        if re.search(r"\b4k\b", entry.name, re.IGNORECASE) and "2160p" in new_name.lower():  # 4K converted
                            labels.append("4K Converted to 2160p")  # Append label
                    except Exception:  # If detection fails
                        pass  # Ignore detection errors
                    try:  # Detect language normalization differences (guard regex)
                        old_lang_match = re.search(r"\b(Dual|Dublado|English|Legendado|Nacional)\b", entry.name, re.IGNORECASE)  # Find old lang token
                        if old_lang_match:  # If an old language token existed
                            old_lang_raw = old_lang_match.group(0)  # Extract raw matched token
                            if append_str and old_lang_raw != append_str:  # If canonical differs from raw
                                labels.append("Language Normalized")  # Append label
                    except Exception:  # On detection errors
                        pass  # Ignore
                    seen = set()  # Deduplicate labels while preserving order
                    final_labels = []  # Ordered unique labels
                    for L in labels:  # Iterate computed labels
                        if L not in seen:  # If label not yet recorded
                            seen.add(L)  # Mark seen
                            final_labels.append(L)  # Append to final list
                    report_data["input_dirs"][root_key]["directories_modified"].append({  # Append directory modification record
                        "old_name": entry.name,  # Record old directory name
                        "new_name": new_name,  # Record new directory name
                        "changes": final_labels,  # Record detected change labels
                    })  # End append directory record

            else:  # Case 2: The directory likely contains season subdirectories, scan them here
                verbose_output(f"{BackgroundColors.YELLOW}No season info found for '{entry.name}'. Scanning subdirectories...{Style.RESET_ALL}")
                series_prefix = entry.name.strip()  # Parent directory is authoritative series name
                season_infos = []  # Store prefix-normalized season metadata for second-pass validation

                for raw_subentry in sorted(entry.iterdir(), key=lambda path: path.name.casefold()):  # Pass 1: discover and prefix every season directory first
                    if not raw_subentry.is_dir():
                        continue

                    if re.match(IGNORE_DIR_REGEX, raw_subentry.name.strip()):
                        verbose_output(f"{BackgroundColors.YELLOW}Ignoring subdirectory: {raw_subentry.name}{Style.RESET_ALL}")
                        continue

                    season_specific_name = strip_expected_series_prefix(raw_subentry.name, series_prefix)
                    parsed_sub = parse_dir_name(season_specific_name)

                    if parsed_sub:
                        _, season_num_sub, resolution_sub = parsed_sub
                    else:
                        season_match = re.search(r"\bSeason\s+(?P<num>\d{1,2})\b", season_specific_name, re.IGNORECASE)

                        if not season_match:
                            verbose_output(true_string=f"{BackgroundColors.YELLOW}Skipping (no season match in subdir): {raw_subentry.name}{Style.RESET_ALL}")
                            continue

                        season_num_sub = int(season_match.group("num"))
                        resolution_search = re.search(r"\b(?P<res>\d{3,4}p|4k)\b", season_specific_name, re.IGNORECASE)
                        resolution_sub = resolution_search.group("res") if resolution_search else None

                    subentry = ensure_nested_season_prefix(raw_subentry, series_prefix, root_path, report_data)  # PREFIX FIRST
                    normalized_season_name = strip_expected_series_prefix(subentry.name, series_prefix)
                    existing_year_match = re.search(r"\b(?P<year>(?:19|20)\d{2})\b", normalized_season_name)
                    existing_year_int = int(existing_year_match.group("year")) if existing_year_match else None

                    season_infos.append(
                        {
                            "path": subentry,
                            "season_number": int(season_num_sub),
                            "existing_year": existing_year_int,
                            "resolution_hint": resolution_sub,
                        }
                    )

                required_seasons = {info["season_number"] for info in season_infos}
                expected_years = {
                    info["season_number"]: info["existing_year"]
                    for info in season_infos
                    if info["existing_year"] is not None
                }

                series_id = None

                if required_seasons:
                    try:
                        series_id = get_series_id(
                            api_key,
                            series_prefix,
                            required_seasons=required_seasons,
                            expected_years=expected_years,
                        )  # Resolve one series only after every local season has been prefixed
                    except Exception as e:
                        verbose_output(
                            true_string=f"{BackgroundColors.RED}Error resolving TMDb series for {series_prefix}: {e}{Style.RESET_ALL}"
                        )

                for season_info in season_infos:  # Pass 2: only now verify/correct year and the rest
                    subentry = season_info["path"]
                    season_num_sub = int(season_info["season_number"])
                    season_str_sub = f"{season_num_sub:02d}"
                    existing_year_int = season_info["existing_year"]
                    normalized_season_name = strip_expected_series_prefix(subentry.name, series_prefix)

                    year = None

                    if series_id is not None:
                        try:
                            year = get_season_year(api_key, series_id, season_num_sub)
                        except Exception as e:
                            verbose_output(
                                true_string=f"{BackgroundColors.RED}Error fetching year for {series_prefix} S{season_str_sub}: {e}{Style.RESET_ALL}"
                            )

                    valid_year = existing_year_int

                    if year is not None:
                        try:
                            valid_year = int(year)
                        except Exception:
                            valid_year = existing_year_int

                    res_token_sub = determine_resolution(subentry, normalized_season_name)
                    fps_token_sub = detect_60fps_token(normalized_season_name)  # Preserve 60 FPS metadata from any accepted format/location

                    part_match_sub = re.search(
                        r"\b(?P<label>part|pt|volume|vol|cour|arc)\b\.?\s*(?P<num>[A-Za-z0-9]+)\b",
                        normalized_season_name,
                        re.IGNORECASE,
                    )
                    part_token_sub = (
                        f"{part_match_sub.group('label').capitalize()} {part_match_sub.group('num')}"
                        if part_match_sub
                        else None
                    )

                    append_str = None

                    for language_option in LANGUAGE_OPTIONS:
                        if re.search(rf"\b{re.escape(language_option)}\b", normalized_season_name, re.IGNORECASE):
                            append_str = language_option
                            break

                    name_parts = ["Season", season_str_sub]

                    if valid_year is not None:
                        name_parts.append(str(valid_year))
                    if part_token_sub:
                        name_parts.append(part_token_sub)
                    if res_token_sub:
                        name_parts.append(res_token_sub)
                    if fps_token_sub:
                        name_parts.append(fps_token_sub)  # Canonically place 60FPS immediately after resolution
                    if append_str:
                        name_parts.append(append_str)  # Keep language suffix after frame-rate metadata

                    canonical_season_name = standardize_final_name(" ".join(name_parts))
                    canonical_season_name = " ".join(canonical_season_name.split())
                    new_name = " ".join(f"{series_prefix} - {canonical_season_name}".split())
                    new_path = subentry.parent / new_name

                    if new_name == subentry.name:
                        verbose_output(f"{BackgroundColors.YELLOW}Skipping (already named): {subentry.name}{Style.RESET_ALL}")
                        continue

                    if new_path.exists() and new_path != subentry:
                        raise FileExistsError(f"Cannot rename season directory because destination already exists: {new_path}")

                    old_name = subentry.name
                    change_desc = detect_changes(old_name, new_name)

                    if not change_desc:
                        verbose_output(f"{BackgroundColors.YELLOW}Skipping (no detected meaningful change): {subentry.name}{Style.RESET_ALL}")
                        continue

                    output_rename_change(change_desc, old_name, new_name)
                    subentry.rename(new_path)

                    if not new_path.exists():
                        raise RuntimeError(f"Season rename did not create expected directory: {new_path}")

                    record_directory_change(report_data, root_path, old_name, new_name, change_desc)


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


def generate_report(report_data: dict) -> None:
    """
    Generate a `report.json` file in the project root from `report_data`.

    :param report_data: The report dictionary built during processing
    :return: None
    """

    report_data["generated_at"] = datetime.datetime.now().isoformat()  # Add ISO timestamp to the report
    out_path = Path(__file__).parent / "report.json"  # Compute output path in project root
    try:  # Guard file I/O to avoid raising
        with out_path.open("w", encoding="utf-8") as f:  # Open file for writing with UTF-8 encoding
            json.dump(report_data, f, indent=4, ensure_ascii=False)  # Write JSON with required options
    except Exception as e:  # On any error while writing, report but do not raise
        print(f"{BackgroundColors.RED}Failed to write report.json: {e}{Style.RESET_ALL}")  # Log write failure
        return  # Ensure function exits without raising


def main():
    """
    Main function.

    :param: None
    :return: None
    """

    verbose_output(
        true_string=f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Season Directory Renamer{BackgroundColors.GREEN} program!{Style.RESET_ALL}"
    )  # Keep non-change startup output hidden unless VERBOSE=True
    start_time = datetime.datetime.now()  # Get the start time of the program
    
    verify_ffmpeg_is_installed()  # Verify if ffmpeg is installed
    
    rename_dirs()  # Execute the directory renaming workflow

    finish_time = datetime.datetime.now()  # Get the finish time of the program
    verbose_output(
        true_string=(
            f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n"
            f"{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n"
            f"{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}\n"
            f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
        )
    )  # Keep non-change completion output hidden unless VERBOSE=True
    (
        atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None
    )  # Register the play_sound function to be called when the program finishes


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
