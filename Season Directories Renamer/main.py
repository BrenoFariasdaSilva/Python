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
INPUT_DIR = Path("./INPUT")  # The input directory containing the season folders
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

    match = re.match(r"(?P<series>[A-Za-z0-9\._]+)\.S(?P<season>\d{2})\.(?P<res>\d{3,4}p)", dir_name, re.IGNORECASE)  # Attempt regex match for series, season and resolution
    
    if not match:  # If regex does not match the expected pattern
        return None  # Return None to indicate parsing failure
    
    series = match.group("series").replace(".", " ")  # Convert dotted series token to readable series name
    season = int(match.group("season"))  # Convert captured season string to integer
    resolution = match.group("res")  # Capture resolution token (e.g., '1080p')
    
    return series, season, resolution  # Return parsed tuple with series name, season int, and resolution


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
