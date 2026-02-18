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
from colorama import Style  # For coloring the terminal
import re  # For parsing directory names
import requests  # For API requests
from pathlib import Path  # For path handling
from dotenv import load_dotenv  # For loading environment variables


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


def rename_dirs():
    """
    Iterates through the INPUT_DIR, extracts metadata, fetches the release year from TMDb,
    and renames each directory according to the defined pattern.

    If a directory does not match the regex pattern (i.e., missing season/resolution info),
    the script assumes it contains season subdirectories and processes those instead.

    :return: None
    """

    api_key = load_api_key()  # Load TMDb API key from environment before processing directories
    # Prepare a strict formatted-folder regex using configured suffixes
    suffix_group = "|".join([re.escape(s) for s in APPEND_STRINGS])  # Build alternation group from APPEND_STRINGS
    formatted_pattern = rf"^Season\s(?P<season>\d{{2}})\s(?P<year>\d{{4}})(?:\s(?P<suffix>{suffix_group}))?$"  # Strict formatted folder regex

    for entry in INPUT_DIR.iterdir():  # Iterate over entries in the INPUT_DIR path
        if not entry.is_dir():  # Skip non-directory entries such as files
            continue  # Continue to next entry when current one is not a directory

        parsed = parse_dir_name(entry.name)  # Try parsing the directory name for season metadata

        # Case 1: The directory name contains season and resolution info
        if parsed:  # When directory name matched the expected season/resolution pattern
            series_name, season_num, resolution = parsed  # Unpack parsed metadata tuple
            season_str = f"{season_num:02d}"  # Format season number as two digits

            year = None  # Initialize year variable before lookup
            # Check if the current folder is already strictly formatted
            formatted_match = re.match(formatted_pattern, entry.name)  # Match strict formatted pattern against folder name
            if formatted_match:  # If folder already matches strict format
                existing_season = formatted_match.group("season")  # Extract existing zero-padded season string
                existing_year = formatted_match.group("year")  # Extract existing year string
                existing_suffix = formatted_match.group("suffix")  # Extract existing optional suffix string

                # Validate numeric values for season and year
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
                        print(f"{BackgroundColors.YELLOW}Skipping (already correctly formatted): {entry.name}{Style.RESET_ALL}")  # Inform user that folder is already correct
                        continue  # Skip renaming since folder is already correct
                    if api_year is not None and str(api_year) != str(existing_year_int):  # If API year differs, correct the year in the folder name
                        corrected_name = f"Season {existing_season} {int(api_year)}"  # Build corrected name with new year
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

            valid_year = None  # Assume invalid until proven otherwise
            if year is not None:  # Only attempt conversion when year is not None
                try:  # Attempt to coerce year to int
                    valid_year = int(year)  # Convert year to integer
                except Exception:  # Conversion failed, mark as invalid
                    valid_year = None  # Ensure invalid status

            if valid_year is None:  # If year could not be determined, skip renaming
                print(f"{BackgroundColors.YELLOW}Skipping (no valid year found): {entry.name}{Style.RESET_ALL}")  # Inform about skipping due to missing year
                continue  # Continue to next entry without renaming

            append_str = None  # Default to no suffix
            for s in APPEND_STRINGS:  # Iterate in configured order
                if re.search(rf"\b{s}\b", entry.name, re.IGNORECASE):  # Case-insensitive whole-word match
                    append_str = s  # Select the first matching configured suffix
                    break  # Stop after the first match

            if append_str:  # If a suffix was found
                new_name = f"Season {season_str} {valid_year} {append_str}"  # Include suffix at end
            else:  # No suffix found
                new_name = f"Season {season_str} {valid_year}"  # No suffix appended

            new_name = " ".join(new_name.split())  # Normalize whitespace to prevent double spaces
            new_path = entry.parent / new_name  # Compute new path for renaming

            print(f"{BackgroundColors.GREEN}Renaming:{Style.RESET_ALL} '{entry.name}' → '{new_name}'")  # Inform about the rename operation
            entry.rename(new_path)  # Perform the filesystem rename operation

        # Case 2: The directory likely contains subdirectories for seasons
        else:  # When top-level directory does not contain season info, inspect its subdirectories
            print(f"{BackgroundColors.YELLOW}No season info found in '{entry.name}', scanning subdirectories...{Style.RESET_ALL}")  # Inform about scanning subdirectories
            for subentry in entry.iterdir():  # Iterate over subentries inside the directory
                if not subentry.is_dir():  # Skip non-directory subentries such as files
                    continue  # Continue to next subentry when current one is not a directory

                # First attempt: try parsing the subdirectory name with existing parser
                parsed_sub = parse_dir_name(subentry.name)  # Attempt to parse subdirectory name using generic parser
                if parsed_sub:  # If parser returned a tuple, use it directly
                    series_name, season_num, resolution = parsed_sub  # Unpack parsed metadata for subdirectory
                else:  # Fallback: detect 'Season <number>' pattern in subdirectory name and infer series from parent
                    season_match = re.search(r"Season\s+(?P<num>\d{1,2})", subentry.name, re.IGNORECASE)  # Match 'Season <number>' case-insensitively
                    if not season_match:  # If no season-style pattern found in subdirectory name
                        print(f"{BackgroundColors.YELLOW}Skipping (no match in subdir): {subentry.name}{Style.RESET_ALL}")  # Inform about skipped subdirectory
                        continue  # Continue to next subentry when parsing fails

                    season_num = int(season_match.group("num"))  # Convert extracted season number to integer

                    # Detect numeric resolution in subdirectory name (e.g., '720' or '1080' or '720p')
                    res_search = re.search(r"\b(?P<res>\d{3,4}p?)\b", subentry.name, re.IGNORECASE)  # Search for resolution token
                    if res_search:  # If resolution token found
                        res_digits = re.sub(r"\D", "", res_search.group("res"))  # Strip non-digits to leave digits only
                        resolution = f"{res_digits}p"  # Normalize to '<digits>p' format
                    else:  # No resolution token found for this subdirectory
                        resolution = None  # Use None when no resolution present

                    series_name = entry.name  # Infer series name from parent directory name

                season_str = f"{season_num:02d}"  # Format season number as two digits for subdirectory

                year = None  # Initialize year variable before lookup
                # Check if subdirectory is already strictly formatted
                formatted_match_sub = re.match(formatted_pattern, subentry.name)  # Match strict formatted pattern against subdirectory name
                if formatted_match_sub:  # If the subdirectory already matches strict format
                    existing_season = formatted_match_sub.group("season")  # Extract existing zero-padded season string from subdir
                    existing_year = formatted_match_sub.group("year")  # Extract existing year string from subdir
                    existing_suffix = formatted_match_sub.group("suffix")  # Extract existing optional suffix string from subdir

                    # Validate numeric season/year values
                    try:  # Try convert existing year to int
                        existing_year_int = int(existing_year)  # Convert to integer
                    except Exception:  # Conversion failed
                        existing_year_int = None  # Mark invalid
                    try:  # Try convert existing season to int
                        existing_season_int = int(existing_season)  # Convert to integer
                    except Exception:  # Conversion failed
                        existing_season_int = None  # Mark invalid

                    if existing_year_int is not None and existing_season_int is not None:  # Only when both valid integers
                        series_lookup_name = series_name or entry.name  # Prefer parsed series_name, fallback to parent directory name for subdir
                        try:  # Attempt to verify year with TMDb API for subdir
                            series_id_chk = get_series_id(api_key, series_lookup_name)  # Lookup series id for verification
                            api_year = get_season_year(api_key, series_id_chk, existing_season_int)  # Fetch year from API for existing season
                        except Exception as e:  # API lookup failed for subdir
                            print(f"{BackgroundColors.RED}Error verifying year for {series_lookup_name} S{existing_season}: {e}{Style.RESET_ALL}")  # Inform about verification error
                            api_year = None  # Mark API year as unavailable

                        if api_year is not None and str(api_year) == str(existing_year_int):  # API year matches existing year
                            print(f"{BackgroundColors.YELLOW}Skipping (already correctly formatted): {subentry.name}{Style.RESET_ALL}")  # Inform that subdir is already correct
                            continue  # Skip renaming for this subdirectory
                        if api_year is not None and str(api_year) != str(existing_year_int):  # API year differs from folder year
                            corrected_name = f"Season {existing_season} {int(api_year)}"  # Build corrected name with new year
                            if existing_suffix:  # Preserve existing suffix when present
                                corrected_name = f"{corrected_name} {existing_suffix}"  # Append suffix
                            corrected_name = " ".join(corrected_name.split())  # Normalize whitespace
                            corrected_path = subentry.parent / corrected_name  # Compute corrected path
                            print(f"{BackgroundColors.GREEN}Correcting year: '{subentry.name}' → '{corrected_name}'{Style.RESET_ALL}")  # Inform about correction
                            subentry.rename(corrected_path)  # Perform rename to corrected year for subdirectory
                            continue  # Continue to next subentry after correction
                try:  # Attempt TMDb lookups for the subdirectory using resolved series_name and season_num
                    series_id = get_series_id(api_key, series_name)  # Fetch TMDb series id by name for subdir
                    year = get_season_year(api_key, series_id, season_num)  # Fetch season year for subdir
                except Exception as e:  # Catch any exception from TMDb calls for subdir
                    print(f"{BackgroundColors.RED}Error fetching year for {series_name} S{season_str}: {e}{Style.RESET_ALL}")  # Print error message when lookup fails for subdir

                valid_year = None  # Assume invalid until proven otherwise
                if year is not None:  # Only attempt conversion when year is not None
                    try:  # Attempt to coerce year to int
                        valid_year = int(year)  # Convert year to integer
                    except Exception:  # Conversion failed, mark as invalid
                        valid_year = None  # Ensure invalid status

                if valid_year is None:  # If year could not be determined, skip renaming this subdirectory
                    print(f"{BackgroundColors.YELLOW}Skipping (no valid year found): {subentry.name}{Style.RESET_ALL}")  # Inform about skipping due to missing year
                    continue  # Continue to next subentry without renaming

                append_str = None  # Default to no suffix
                for s in APPEND_STRINGS:  # Iterate in configured order
                    if re.search(rf"\b{s}\b", subentry.name, re.IGNORECASE):  # Case-insensitive whole-word match
                        append_str = s  # Select the first matching configured suffix
                        break  # Stop after the first match

                if append_str:  # If a suffix was found
                    new_name = f"Season {season_str} {valid_year} {append_str}"  # Include suffix at end
                else:  # No suffix found
                    new_name = f"Season {season_str} {valid_year}"  # No suffix appended

                new_name = " ".join(new_name.split())  # Normalize whitespace to prevent double spaces
                new_path = subentry.parent / new_name  # Compute new path for subdirectory rename

                print(f"{BackgroundColors.GREEN}Renaming subdir: '{BackgroundColors.CYAN}{subentry.name}{BackgroundColors.GREEN}' → '{BackgroundColors.CYAN}{new_name}{BackgroundColors.GREEN}'{Style.RESET_ALL}")  # Inform about the subdirectory rename
                subentry.rename(new_path)  # Perform the filesystem rename operation for subdirectory


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
