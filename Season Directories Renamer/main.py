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
import os  # For running a command in the terminal
import platform  # For getting the operating system name
from colorama import Style  # For coloring the terminal
import re  # For parsing directory names
import requests  # For API requests
from pathlib import Path  # For path handling
from dotenv import load_dotenv  # For loading environment variables

# ==============================================================================
# Macros:
# ==============================================================================


class BackgroundColors:  # Colors for the terminal
    CYAN = "\033[96m"  # Cyan
    GREEN = "\033[92m"  # Green
    YELLOW = "\033[93m"  # Yellow
    RED = "\033[91m"  # Red
    BOLD = "\033[1m"  # Bold
    UNDERLINE = "\033[4m"  # Underline
    CLEAR_TERMINAL = "\033[H\033[J"  # Clear the terminal


# ==============================================================================
# Execution Constants:
# ==============================================================================

VERBOSE = False  # Set to True to output verbose messages

# ==============================================================================
# Sound Constants:
# ==============================================================================

SOUND_COMMANDS = {
    "Darwin": "afplay",
    "Linux": "aplay",
    "Windows": "start",
}  # The commands to play a sound for each operating system
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav"  # The path to the sound file

# ==============================================================================
# RUN_FUNCTIONS:
# ==============================================================================

RUN_FUNCTIONS = {
    "Play Sound": True,  # Set to True to play a sound when the program finishes
}

# ==============================================================================
# Configuration Constants:
# ==============================================================================

INPUT_DIR = Path("./INPUT")  # The input directory containing the season folders
APPEND_STRINGS = ["Legendado", "Dual", "Dublado", "English"]  # User-defined suffixes for renaming
TMDB_BASE_URL = "https://api.themoviedb.org/3"  # Base URL for TMDb API

# ==============================================================================
# Function Definitions:
# ==============================================================================


def verbose_output(true_string="", false_string="", telegram_bot=None):
    """
    Outputs a message if the VERBOSE constant is set to True.

    :param true_string: The string to be outputted if the VERBOSE constant is set to True.
    :param false_string: The string to be outputted if the VERBOSE constant is set to False.
    :param telegram_bot: Optional TelegramBot instance to send the message to Telegram.
    :return: None
    """

    if VERBOSE and true_string != "":  # If VERBOSE is True and a true_string was provided
        print(true_string)  # Output the true statement string
        if telegram_bot is not None:  # If a Telegram bot instance was provided
            send_telegram_message(telegram_bot, [true_string])  # Send the true_string to Telegram
    elif false_string != "":  # If a false_string was provided
        print(false_string)  # Output the false statement string
        if telegram_bot is not None:  # If a Telegram bot instance was provided
            send_telegram_message(telegram_bot, [false_string])  # Send the false_string to Telegram


def verify_filepath_exists(filepath):
    """
    Verify if a file or folder exists at the specified path.

    :param filepath: Path to the file or folder
    :return: True if the file or folder exists, False otherwise
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}"
    )
    return os.path.exists(filepath)


def play_sound():
    """
    Plays a sound when the program finishes and skips if the operating system is Windows.

    :param: None
    :return: None
    """

    current_os = platform.system()
    if current_os == "Windows":
        return

    if verify_filepath_exists(SOUND_FILE):
        if current_os in SOUND_COMMANDS:
            os.system(f"{SOUND_COMMANDS[current_os]} {SOUND_FILE}")
        else:
            print(
                f"{BackgroundColors.RED}The {BackgroundColors.CYAN}{current_os}{BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}"
            )
    else:
        print(
            f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}"
        )


# ==============================================================================
# TMDb Helper Functions
# ==============================================================================


def load_api_key():
    """
    Loads the TMDb API key from a .env file in the project root.

    :return: API key string
    """
    load_dotenv()
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key:
        raise ValueError("TMDB_API_KEY not found in .env file.")
    return api_key


def parse_dir_name(dir_name):
    """
    Parses folder name like 'Arrow.S01.1080p.Bluray.x265-HiQVE'
    Returns tuple (series_name, season_number (int), resolution_str) or None if no match.
    """
    match = re.match(r"(?P<series>[A-Za-z0-9\._]+)\.S(?P<season>\d{2})\.(?P<res>\d{3,4}p)", dir_name, re.IGNORECASE)
    if not match:
        return None
    series = match.group("series").replace(".", " ")
    season = int(match.group("season"))
    resolution = match.group("res")
    return series, season, resolution


def get_series_id(api_key, series_name):
    """
    Query TMDb search endpoint to find series ID by name.
    Returns first result's id or raises exception.
    """
    url = f"{TMDB_BASE_URL}/search/tv"
    params = {"api_key": api_key, "query": series_name}
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    results = data.get("results", [])
    if not results:
        raise ValueError(f"No TMDb series found for '{series_name}'")
    return results[0]["id"]


def get_season_year(api_key, series_id, season_number):
    """
    Query TMDb to get season details for a given series_id & season_number.
    Returns the year (e.g., 2012) of that season's air date.
    """
    url = f"{TMDB_BASE_URL}/tv/{series_id}/season/{season_number}"
    params = {"api_key": api_key}
    response = requests.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    air_date = data.get("air_date")
    if not air_date:
        episodes = data.get("episodes", [])
        if episodes and "air_date" in episodes[0]:
            air_date = episodes[0]["air_date"]
        else:
            raise ValueError(f"No air_date found for series {series_id} season {season_number}")
    return air_date.split("-")[0]


def rename_dirs():
    """
    Iterates through the INPUT_DIR, extracts metadata, fetches the release year from TMDb,
    and renames each directory according to the defined pattern.

    If a directory does not match the regex pattern (i.e., missing season/resolution info),
    the script assumes it contains season subdirectories and processes those instead.
    """
    api_key = load_api_key()

    for entry in INPUT_DIR.iterdir():
        if not entry.is_dir():
            continue

        parsed = parse_dir_name(entry.name)

        # ------------------------------------------------------------
        # Case 1: The directory name contains season and resolution info
        # ------------------------------------------------------------
        if parsed:
            series_name, season_num, resolution = parsed
            season_str = f"{season_num:02d}"

            try:
                series_id = get_series_id(api_key, series_name)
                year = get_season_year(api_key, series_id, season_num)
            except Exception as e:
                print(
                    f"{BackgroundColors.RED}Error fetching year for {series_name} S{season_str}: {e}{Style.RESET_ALL}"
                )
                year = "Unknown"

            append_str = APPEND_STRINGS[0]
            new_name = f"Season {season_str} {year} {resolution} {append_str}"
            new_path = entry.parent / new_name

            print(f"{BackgroundColors.GREEN}Renaming:{Style.RESET_ALL} '{entry.name}' → '{new_name}'")
            entry.rename(new_path)

        # ------------------------------------------------------------
        # Case 2: The directory likely contains subdirectories for seasons
        # ------------------------------------------------------------
        else:
            print(
                f"{BackgroundColors.YELLOW}No season info found in '{entry.name}', scanning subdirectories...{Style.RESET_ALL}"
            )
            for subentry in entry.iterdir():
                if subentry.is_dir():
                    parsed_sub = parse_dir_name(subentry.name)
                    if not parsed_sub:
                        print(
                            f"{BackgroundColors.YELLOW}Skipping (no match in subdir): {subentry.name}{Style.RESET_ALL}"
                        )
                        continue

                    series_name, season_num, resolution = parsed_sub
                    season_str = f"{season_num:02d}"

                    try:
                        series_id = get_series_id(api_key, series_name)
                        year = get_season_year(api_key, series_id, season_num)
                    except Exception as e:
                        print(
                            f"{BackgroundColors.RED}Error fetching year for {series_name} S{season_str}: {e}{Style.RESET_ALL}"
                        )
                        year = "Unknown"

                    append_str = APPEND_STRINGS[0]
                    new_name = f"Season {season_str} {year} {resolution} {append_str}"
                    new_path = subentry.parent / new_name

                    print(f"{BackgroundColors.GREEN}Renaming subdir:{Style.RESET_ALL} '{subentry.name}' → '{new_name}'")
                    subentry.rename(new_path)


# ==============================================================================
# Main Function
# ==============================================================================


def main():
    """
    Main function.

    :param: None
    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Season Directory Renamer{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
    )
    rename_dirs()
    print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}")
    atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """
    main()
