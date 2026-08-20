"""
================================================================================
Facebook Posts Downloader
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-20
Description :
    Downloads posts published on a configured Facebook profile by using an
    authenticated Chromium-based browser session controlled through Playwright.

    Each discovered post is stored inside the ./Outputs/ directory using the
    "{YYYY-MM-DD}-{Title}" directory naming convention. The post directory
    contains a post.json metadata file and every image/video that can be resolved
    to a downloadable media URL from the loaded Facebook post.

    Key features include:
        - Uses a dedicated persistent Playwright browser profile that preserves login.
        - Tries the persistent profile headlessly first and opens a visible browser only when authentication is required.
        - Automatically closes the interactive browser after authentication and relaunches the same profile headlessly.
        - Tracks Facebook page replacements/new tabs across CAPTCHA, 2FA, and checkpoints.
        - Reopens interactive authentication if Facebook interrupts headless scraping with a later verification challenge.
        - Scrolls the Facebook profile until no additional posts are discovered.
        - Extracts post text, title, date, permalink, identifier, images, and videos.
        - Streams media using authentication copied in memory from the browser context.
        - Writes each post immediately so interrupted executions can be resumed safely.
        - Avoids duplicate post processing across executions.
        - Sanitizes output names for Windows, Linux, and macOS filesystems.
        - Logs failures without silently marking unavailable media as successfully saved.

Usage:
    1. Install the dependencies:
        $ make install
       or:
        $ python -m pip install -r requirements.txt
        $ python -m playwright install chromium
    2. Run the downloader:
        $ make run
       or:
        $ python main.py
    3. The program first tries ./.browser_profile/ headlessly. If authentication is
       missing or Facebook requires verification, a visible Chrome window opens so CAPTCHA,
       2FA, checkpoints, and confirmation prompts can be completed manually.
    4. After authentication is stable, the visible browser is closed and the same persistent
       profile is relaunched headlessly before PROFILE_URL is scraped into ./Outputs/.

Outputs:
    - ./Outputs/{YYYY-MM-DD}-{Title}/post.json
    - ./Outputs/{YYYY-MM-DD}-{Title}/photo_001.<ext>
    - ./Outputs/{YYYY-MM-DD}-{Title}/video_001.<ext>
    - ./Logs/main.log
    - ./.browser_profile/ persistent browser data used by Playwright

TODOs:
    - Add an optional command-line interface for overriding constants.
    - Add dedicated extraction adapters if Facebook substantially changes its DOM.
    - Add optional HTML snapshots for posts whose media cannot be directly resolved.
    - Add optional date-range filtering for very large timelines.

Dependencies:
    - Python >= 3.10
    - playwright >= 1.58.0
    - dateparser >= 1.2.0
    - colorama >= 0.4.6
    - requests >= 2.32.0
    - Logger.py included in this project

Assumptions & Notes:
    - This script is intended for content the authenticated user is authorized to access.
    - Facebook does not expose a stable public DOM contract for profile timelines;
      selectors therefore use several fallbacks and may require future maintenance.
    - The script uses its own persistent .browser_profile/ directory for Playwright automation.
    - HEADLESS_AFTER_AUTHENTICATION keeps normal scraping invisible after any required manual login.
    - A visible browser is opened only when the persistent headless session cannot be positively authenticated.
    - Authentication is considered complete only after Facebook session cookies are present,
      normal authenticated Facebook UI is rendered, no login/challenge route is active, and
      that state remains stable for several seconds on the same current browser page.
    - CAPTCHA, 2FA, recovery, checkpoint, and other interactive authentication steps are
      never bypassed; a visible browser is opened only long enough for the user to finish them manually.
    - If Facebook requests another verification during headless scraping, completed posts remain
      on disk, the headless context closes, interactive authentication reopens, and scraping resumes.
    - Authentication query parameters are removed from logs so verification context is not exposed.
    - The automation profile never writes Facebook cookies to JSON or logs.
    - Facebook posts do not have a dedicated "title" field. The title used for the output
      directory is derived from the first meaningful line of the post text.
    - If no post date can be resolved safely, the post is not written with an invented
      date; the failure is logged instead.
"""

import atexit  # For playing a sound when the program finishes
import datetime  # For getting the current date and time
import hashlib  # For generating stable fallback identifiers
import json  # For writing post metadata files
import mimetypes  # For resolving file extensions from content types
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For parsing identifiers and sanitizing names
import requests  # For streaming media downloads without loading whole files into memory
import sys  # For system-specific parameters and functions
import time  # For controlling retries and scroll intervals
import unicodedata  # For normalizing filesystem-safe names
from dataclasses import dataclass  # For storing browser session state
from pathlib import Path  # For handling file paths
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse  # For normalizing Facebook URLs

import dateparser  # For parsing Facebook date labels in multiple languages
from colorama import Style  # For coloring the terminal
from Logger import Logger  # For logging output to both terminal and file
from playwright.sync_api import BrowserContext, Page, Playwright, Response, TimeoutError as PlaywrightTimeoutError, sync_playwright  # For browser automation


# Project Paths:
PROJECT_DIR = Path(__file__).resolve().parent  # Resolve the current project directory


# Macros:
class BackgroundColors:  # Colors for the terminal
    CYAN = "\033[96m"  # Cyan
    GREEN = "\033[92m"  # Green
    YELLOW = "\033[93m"  # Yellow
    RED = "\033[91m"  # Red
    BOLD = "\033[1m"  # Bold
    UNDERLINE = "\033[4m"  # Underline
    CLEAR_TERMINAL = "\033[H\033[J"  # Clear the terminal


@dataclass
class BrowserSession:
    """
    Stores the browser resources used by the downloader.

    :param context: Persistent browser context containing the authenticated session.
    :param page: Facebook page controlled by the downloader.
    """

    context: BrowserContext  # Persistent browser context containing the authenticated session
    page: Page  # Page used to navigate the Facebook profile


class FacebookAuthenticationRequiredError(RuntimeError):
    """
    Raised when Facebook requires manual authentication that cannot be completed headlessly.

    :param message: Human-readable reason the current browser session cannot continue.
    """

    pass  # The exception type itself carries the authentication-required meaning


# Execution Constants:
VERBOSE = False  # Set to True to output verbose messages

# Facebook Constants:
PROFILE_URL = "https://www.facebook.com/BrenoFariasDaSilva"  # Facebook profile containing the posts to download
PROFILE_DISPLAY_NAME = "Breno Farias"  # Preferred display name used when deriving titles
PROFILE_AUTHOR_NAMES = ("Breno Farias", "Breno Farias da Silva")  # Accepted owner names for top-level post validation
ONLY_PROFILE_OWNER_POSTS = True  # Ignore comments and posts authored by other people on the profile timeline
FACEBOOK_BASE_URL = "https://www.facebook.com/"  # Base URL used to resolve relative Facebook links
BROWSER_CHANNEL = "chrome"  # Prefer the locally installed stable Google Chrome browser
HEADLESS_AFTER_AUTHENTICATION = True  # Keep scraping invisible after any required manual Facebook authentication
AUTOMATION_PROFILE_DIR = PROJECT_DIR / ".browser_profile"  # Dedicated persistent profile used by Playwright
OUTPUT_DIR = PROJECT_DIR / "Outputs"  # Root directory containing one subdirectory per downloaded post

# Browser Timing Constants:
PAGE_LOAD_TIMEOUT_MS = 60_000  # Maximum time allowed for normal page navigation
LOGIN_WAIT_SECONDS = 0  # Maximum authentication wait in seconds; 0 waits indefinitely until the user finishes every login step
AUTHENTICATION_POLL_SECONDS = 1.0  # Delay between authentication-state checks
AUTHENTICATION_STABLE_SECONDS = 8.0  # Continuous authenticated time required before accepting login as complete
AUTHENTICATION_STATUS_LOG_INTERVAL_SECONDS = 15.0  # Minimum delay between repeated authentication waiting messages
HEADLESS_AUTHENTICATION_CHECK_TIMEOUT_SECONDS = 15.0  # Maximum time to verify a persisted Facebook session without user interaction
BROWSER_RELAUNCH_DELAY_SECONDS = 1.5  # Delay after closing a persistent context before reopening the same browser profile
PROFILE_READY_TIMEOUT_SECONDS = 60  # Maximum time to wait for the authenticated profile page to render usable content
SCROLL_PAUSE_SECONDS = 2.5  # Delay after each incremental profile scroll to allow lazy-loaded posts to appear
SCROLL_STEP_PX = 900  # Incremental scroll distance used to avoid jumping over virtualized posts
NO_NEW_POST_SCROLL_LIMIT = 12  # Consecutive scrolls without newly discovered canonical post URLs before stopping
MAX_SCROLL_ITERATIONS = 10_000  # Hard safety limit protecting against endless scrolling
ARTICLE_SETTLE_MS = 700  # Delay after bringing a post into the viewport so lazy media can render
VIDEO_NETWORK_CAPTURE_MS = 4_000  # Time spent collecting video/audio requests after a post becomes visible
VIDEO_RANGE_CHUNK_BYTES = 16 * 1024 * 1024  # Chunk size used when reconstructing HTTP 206 ranged media responses

# Output Constants:
POST_METADATA_FILENAME = "post.json"  # Metadata file written inside every post directory
SCRAPE_SCHEMA_VERSION = 3  # Metadata schema version; older broken/profile-feed outputs are intentionally reprocessed
REPROCESS_LEGACY_METADATA = True  # Ignore pre-schema metadata so previously misidentified posts/media are scanned again
MAX_TITLE_LENGTH = 96  # Maximum filesystem title length used after the date prefix
MAX_CONTENT_TITLE_LENGTH = 160  # Maximum amount of post text considered while deriving a title
MAX_MEDIA_FILE_SIZE_BYTES = 4 * 1024 * 1024 * 1024  # Four GiB safety ceiling per media file

# Logger Setup:
LOG_DIR = PROJECT_DIR / "Logs"  # Directory containing project logs
LOG_DIR.mkdir(parents=True, exist_ok=True)  # Ensure the project log directory exists
logger = Logger(str(LOG_DIR / f"{Path(__file__).stem}.log"), clean=True)  # Create a Logger instance
sys.stdout = logger  # Redirect stdout to the logger
sys.stderr = logger  # Redirect stderr to the logger

# Sound Constants:
SOUND_COMMANDS = {
    "Darwin": "afplay",
    "Linux": "aplay",
    "Windows": "start",
}  # The commands to play a sound for each operating system
SOUND_FILE = str(PROJECT_DIR / ".assets" / "Sounds" / "NotificationSound.wav")  # The path to the sound file

# RUN_FUNCTIONS:
RUN_FUNCTIONS = {
    "Play Sound": True,  # Set to True to play a sound when the program finishes
}

# Filesystem Constants:
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{index}" for index in range(1, 10)),
    *(f"LPT{index}" for index in range(1, 10)),
}  # Windows device names that cannot be used as normal directory names

# URL Constants:
TRACKING_QUERY_PARAMETERS = {
    "__cft__",
    "__tn__",
    "comment_id",
    "notif_id",
    "notif_t",
    "ref",
    "refid",
    "mibextid",
}  # Tracking-only parameters removed from normalized Facebook permalinks

POST_URL_PATTERNS = (
    re.compile(r"/posts/(pfbid[A-Za-z0-9]+|\d+)", re.IGNORECASE),
    re.compile(r"[?&]story_fbid=(pfbid[A-Za-z0-9]+|\d+)", re.IGNORECASE),
)  # Patterns used to recover stable post identifiers from canonical post URLs

POST_LINK_HINTS = (
    "/posts/",
    "/permalink.php",
    "/story.php",
    "story_fbid=",
)  # URL fragments used only for canonical top-level post permalinks

PHOTO_LINK_HINTS = (
    "/photo/",
    "/photos/",
    "/photo.php",
)  # URL fragments that identify Facebook post-photo links

VIDEO_LINK_HINTS = (
    "/videos/",
    "/reel/",
    "/watch/",
)  # URL fragments that identify Facebook video/reel links inside a post

VIDEO_RANGE_QUERY_PARAMETERS = {
    "bytestart",
    "byteend",
}  # Facebook CDN range query parameters removed to recover the complete media resource

MESSAGE_SELECTORS = (
    '[data-ad-preview="message"]',
    '[data-ad-comet-preview="message"]',
    'div[dir="auto"]',
)  # Selectors used in order to recover the textual body of each post

ARTICLE_SELECTORS = (
    'div[role="main"] div[role="article"]',
    'div[data-pagelet^="FeedUnit_"]',
)  # Selectors used to locate loaded timeline posts inside Facebook's main profile feed

DATE_ELEMENT_SELECTORS = (
    "abbr[data-utime]",
    "time[datetime]",
)  # Machine-readable date elements used only as a fallback after the canonical permalink timestamp

SEE_MORE_TEXTS = (
    "See more",
    "Ver mais",
)  # Localized text labels used to expand truncated Facebook post bodies

AUTHENTICATION_PATH_PREFIXES = (
    "/login",
    "/checkpoint",
    "/recover",
    "/two_factor",
    "/two_step_verification",
    "/auth_platform",
    "/device-based",
    "/confirmemail",
)  # Facebook URL path prefixes that indicate authentication or account verification is still in progress

AUTHENTICATION_CHALLENGE_SELECTORS = (
    'input[name="email"]',
    'input[name="pass"]',
    'input[name="approvals_code"]',
    'input[name="captcha_response"]',
    'input[autocomplete="one-time-code"]',
    'iframe[src*="captcha"]',
    '[data-testid*="checkpoint"]',
)  # Login, 2FA, CAPTCHA, and checkpoint controls that mean authentication is not complete


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
    except Exception as e:  # Catch any exception to ensure logging and visibility
        print(str(e))  # Print error to terminal for server logs
        raise  # Re-raise to preserve original failure semantics


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

    current_os = platform.system()  # Get the current operating system name
    if current_os == "Windows":  # If the current operating system is Windows
        return  # Do nothing

    if verify_filepath_exists(SOUND_FILE):  # If the sound file exists
        if current_os in SOUND_COMMANDS:  # If the platform.system() is in the SOUND_COMMANDS dictionary
            os.system(f'{SOUND_COMMANDS[current_os]} "{SOUND_FILE}"')  # Play the sound
        else:  # If the platform.system() is not in the SOUND_COMMANDS dictionary
            print(
                f"{BackgroundColors.RED}The {BackgroundColors.CYAN}{current_os}{BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}"
            )
    else:  # If the sound file does not exist
        verbose_output(
            true_string=f"{BackgroundColors.YELLOW}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.YELLOW} not found; completion sound skipped.{Style.RESET_ALL}"
        )  # Avoid treating an optional sound asset as a fatal error


def normalize_whitespace(value: str) -> str:
    """
    Normalize whitespace while preserving meaningful line boundaries.

    :param value: Raw text to normalize.
    :return: Normalized text.
    """

    lines = []  # Initialize normalized lines
    for line in str(value or "").replace("\r", "\n").split("\n"):  # Iterate through logical lines
        normalized = re.sub(r"\s+", " ", line).strip()  # Collapse repeated whitespace
        if normalized and (not lines or normalized != lines[-1]):  # Avoid consecutive duplicate lines
            lines.append(normalized)  # Store the normalized line
    return "\n".join(lines).strip()  # Return the normalized multiline text


def sanitize_filename_component(value: str, fallback: str = "Post", max_length: int = MAX_TITLE_LENGTH) -> str:
    """
    Sanitize a string so it can be used safely in a cross-platform directory name.

    :param value: Raw value to sanitize.
    :param fallback: Value returned when sanitization removes all content.
    :param max_length: Maximum number of characters retained.
    :return: Filesystem-safe directory component.
    """

    normalized = unicodedata.normalize("NFKC", str(value or ""))  # Normalize Unicode representation
    normalized = re.sub(r'[<>:"/\\|?*\x00-\x1F]', " ", normalized)  # Replace Windows-invalid characters
    normalized = re.sub(r"\s+", " ", normalized).strip(" .")  # Collapse spaces and remove invalid trailing characters
    normalized = normalized[:max_length].rstrip(" .")  # Enforce a conservative cross-platform path length

    if not normalized:  # Verify a usable name remains
        normalized = fallback  # Use the supplied fallback

    if normalized.upper() in WINDOWS_RESERVED_NAMES:  # Avoid Windows reserved device names
        normalized = f"{normalized} Post"  # Make the component non-reserved

    return normalized  # Return the safe component


def normalize_facebook_url(url: str) -> str:
    """
    Normalize a Facebook URL while preserving identifiers required to address the post.

    :param url: Raw absolute or relative Facebook URL.
    :return: Normalized absolute URL.
    """

    if not url:  # Verify a URL was provided
        return ""  # Return an empty string for missing URLs

    absolute_url = urljoin(FACEBOOK_BASE_URL, url)  # Resolve relative Facebook URLs
    parsed = urlparse(absolute_url)  # Parse the URL into components

    filtered_query = []  # Initialize meaningful query parameters
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):  # Iterate query parameters
        if key not in TRACKING_QUERY_PARAMETERS:  # Keep parameters that are not tracking-only
            filtered_query.append((key, value))  # Preserve the meaningful parameter

    normalized = parsed._replace(
        fragment="",  # Remove non-addressing fragments
        query=urlencode(filtered_query, doseq=True),  # Rebuild the filtered query string
    )  # Build the normalized URL

    return urlunparse(normalized)  # Return the normalized absolute URL


def extract_post_id(post_url: str) -> str:
    """
    Extract a stable Facebook post identifier from a permalink.

    :param post_url: Normalized Facebook post URL.
    :return: Post identifier or an empty string when no supported identifier is present.
    """

    for pattern in POST_URL_PATTERNS:  # Iterate through supported Facebook post URL formats
        match = pattern.search(post_url or "")  # Search the URL for an identifier
        if match:  # Verify a match was found
            return match.group(1)  # Return the first identifier group
    return ""  # Return empty when the URL format does not expose an identifier


def build_fallback_post_key(post_url: str, content: str, date_raw: str) -> str:
    """
    Build a deterministic fallback key for posts without a recoverable numeric identifier.

    :param post_url: Post permalink when available.
    :param content: Extracted post body.
    :param date_raw: Raw date label.
    :return: Stable SHA-256-derived identifier.
    """

    source = f"{post_url}\n{content}\n{date_raw}".encode("utf-8", errors="replace")  # Build the hash input
    return hashlib.sha256(source).hexdigest()[:24]  # Return a compact stable identifier


def is_probable_post_url(url: str) -> bool:
    """
    Determine whether a URL is likely to address a Facebook post or its primary media.

    :param url: URL to inspect.
    :return: True when the URL contains a supported post-link hint.
    """

    lowered = (url or "").lower()  # Normalize the URL for case-insensitive matching
    return any(hint in lowered for hint in POST_LINK_HINTS)  # Return whether any supported hint is present


def collect_post_permalink_candidates(article) -> list[dict]:
    """
    Collect canonical post-permalink candidates that belong to the current top-level article only.

    Nested comments can also use role="article" and contain photo/video links. The JavaScript
    ownership check ensures descendants whose nearest role="article" is a nested comment are not
    allowed to define the parent post identity.

    :param article: Playwright locator representing a Facebook article.
    :return: Canonical permalink candidate dictionaries ordered later by Python scoring.
    """

    try:  # Extract candidate anchors in one browser-side pass to reduce locator churn
        raw_candidates = article.evaluate(
            """root => {
                const rootArticle = root.matches('div[role="article"]') ? root : null;
                const belongsToRoot = element => !rootArticle || element.closest('div[role="article"]') === rootArticle;
                return Array.from(root.querySelectorAll('a[href]'))
                    .filter(belongsToRoot)
                    .map(anchor => ({
                        href: anchor.href || anchor.getAttribute('href') || '',
                        text: (anchor.innerText || anchor.textContent || '').trim(),
                        ariaLabel: anchor.getAttribute('aria-label') || '',
                        title: anchor.getAttribute('title') || '',
                        hasAbbr: !!anchor.querySelector('abbr[data-utime], abbr'),
                        hasTime: !!anchor.querySelector('time[datetime], time'),
                    }));
            }"""
        )  # Read only anchors that semantically belong to the current article
    except Exception:  # Detached articles cannot provide reliable permalink candidates
        return []  # Return no candidates

    profile_path = (urlparse(PROFILE_URL).path or '').casefold().rstrip('/')  # Resolve configured profile path once
    candidates = []  # Initialize scored permalink candidates

    for raw_candidate in raw_candidates or []:  # Inspect browser-returned candidate dictionaries
        href = str(raw_candidate.get('href') or '').strip()  # Normalize candidate href
        if not href or not is_probable_post_url(href):  # Reject photos, videos, comments, and unrelated links
            continue  # Continue to the next candidate

        normalized = normalize_facebook_url(href)  # Normalize tracking parameters from the candidate
        lowered = normalized.casefold()  # Build case-insensitive form for scoring
        score = 0  # Initialize canonical-link score

        if '/posts/pfbid' in lowered:  # Modern canonical post URLs are the strongest identity signal
            score += 600  # Prefer modern pfbid permalinks
        elif '/posts/' in lowered:  # Legacy numeric post permalinks are also strong
            score += 550  # Prefer direct /posts/ links
        elif '/permalink.php' in lowered or '/story.php' in lowered:  # Accept legacy Facebook permalink endpoints
            score += 500  # Prefer legacy post routes over all unrelated links

        if profile_path and profile_path in (urlparse(normalized).path or '').casefold():  # Prefer links explicitly owned by configured profile
            score += 150  # Add profile-ownership preference

        text_value = normalize_whitespace(str(raw_candidate.get('text') or ''))  # Normalize visible timestamp text
        aria_value = normalize_whitespace(str(raw_candidate.get('ariaLabel') or ''))  # Normalize accessible timestamp text
        title_value = normalize_whitespace(str(raw_candidate.get('title') or ''))  # Normalize tooltip timestamp text

        if raw_candidate.get('hasAbbr') or raw_candidate.get('hasTime'):  # Timestamp anchors often contain abbr/time descendants
            score += 300  # Strongly prefer timestamp-bearing post links
        if any(looks_like_date_candidate(value) for value in (text_value, aria_value, title_value) if value):  # Detect date-like labels
            score += 250  # Prefer the post timestamp link rather than other links to the same post

        candidates.append(
            {
                'url': normalized,
                'score': score,
                'text': text_value,
                'aria_label': aria_value,
                'title': title_value,
            }
        )  # Preserve candidate and timestamp metadata

    candidates.sort(key=lambda item: (-int(item['score']), len(str(item['url'])), str(item['url'])))  # Prefer strongest shortest canonical URL
    return candidates  # Return scored canonical post candidates


def is_profile_owner_post_article(article, post_url: str) -> bool:
    """
    Determine whether a top-level Facebook article was authored by the configured profile owner.

    :param article: Facebook article locator.
    :param post_url: Canonical permalink already extracted from the article.
    :return: True when the article belongs to the configured profile owner or owner filtering is disabled.
    """

    if not ONLY_PROFILE_OWNER_POSTS:  # Allow callers to archive all timeline authors when explicitly configured
        return True  # Skip owner validation

    profile_path = (urlparse(PROFILE_URL).path or '').casefold().rstrip('/')  # Normalize configured profile path
    post_path = (urlparse(post_url).path or '').casefold().rstrip('/')  # Normalize canonical post path

    if profile_path and post_path.startswith(f'{profile_path}/posts/'):  # Modern canonical URL explicitly names the configured profile
        return True  # Accept direct owner post immediately

    try:  # Inspect likely author anchors that belong to the current article rather than nested comments
        authors = article.evaluate(
            """root => {
                const rootArticle = root.matches('div[role="article"]') ? root : null;
                const belongsToRoot = element => !rootArticle || element.closest('div[role="article"]') === rootArticle;
                return Array.from(root.querySelectorAll('h2 a[href], h3 a[href], h4 a[href], strong a[href]'))
                    .filter(belongsToRoot)
                    .map(anchor => ({
                        text: (anchor.innerText || anchor.textContent || '').trim(),
                        href: anchor.href || anchor.getAttribute('href') || '',
                    }));
            }"""
        )  # Read article-owner candidates in one browser-side pass
    except Exception:  # Detached articles cannot be positively identified as owner posts
        return False  # Reject ambiguous article

    accepted_names = {normalize_whitespace(name).casefold() for name in PROFILE_AUTHOR_NAMES if normalize_whitespace(name)}  # Normalize configured names

    for author in authors or []:  # Inspect author identity candidates
        author_text = normalize_whitespace(str(author.get('text') or '')).casefold()  # Normalize visible author text
        author_href = normalize_facebook_url(str(author.get('href') or ''))  # Normalize author profile URL
        author_path = (urlparse(author_href).path or '').casefold().rstrip('/')  # Normalize author profile path

        if author_text in accepted_names:  # Accept either configured visible owner name
            return True  # Article belongs to the configured user
        if profile_path and author_path == profile_path:  # Accept direct link to configured profile path
            return True  # Article belongs to the configured user

    return False  # Reject comments, nested articles, and posts authored by other users


def extract_post_permalink(article) -> str:
    """
    Extract the strongest canonical permalink from a top-level Facebook post article.

    :param article: Playwright locator representing a Facebook post.
    :return: Normalized post permalink or an empty string.
    """

    candidates = collect_post_permalink_candidates(article)  # Collect same-article canonical post links only
    return str(candidates[0]['url']) if candidates else ''  # Return the strongest canonical permalink


def expand_post_text(article) -> None:
    """
    Expand truncated Facebook post text when a visible "See more" or "Ver mais" control exists.

    :param article: Playwright locator representing a Facebook post.
    :return: None
    """

    for label in SEE_MORE_TEXTS:  # Iterate through supported localized labels
        try:  # Attempt each selector independently
            controls = article.get_by_text(label, exact=True)  # Locate exact expansion controls
            for index in range(min(controls.count(), 3)):  # Avoid interacting with unrelated repeated controls
                control = controls.nth(index)  # Resolve the current control
                if control.is_visible():  # Verify the control can be clicked
                    control.click(timeout=1_500)  # Expand the post body
                    return  # Stop after the first successful expansion
        except Exception:  # Expansion is optional and should never abort post extraction
            continue  # Try the next localized label


def extract_post_content(article) -> str:
    """
    Extract the meaningful textual body from a Facebook post.

    :param article: Playwright locator representing a Facebook post.
    :return: Normalized post content.
    """

    expand_post_text(article)  # Expand truncated text before reading the post body
    candidates = []  # Initialize text candidates

    for selector in MESSAGE_SELECTORS:  # Iterate through known Facebook message containers
        try:  # Isolate selector-specific failures
            elements = article.locator(selector)  # Locate candidate text containers
            for index in range(min(elements.count(), 30)):  # Bound extraction for unexpectedly large posts
                try:  # Isolate individual element failures
                    text = normalize_whitespace(elements.nth(index).inner_text(timeout=1_000))  # Read and normalize text
                    if text and text not in candidates:  # Avoid duplicate text fragments
                        candidates.append(text)  # Preserve the candidate
                except Exception:  # Ignore detached or hidden elements
                    continue  # Continue to the next candidate
        except Exception:  # Ignore unsupported selectors after Facebook UI changes
            continue  # Continue to the next selector

    specific_candidates = [candidate for candidate in candidates if "\n" in candidate or len(candidate) >= 20]  # Prefer substantial body text
    if specific_candidates:  # Verify useful message-specific candidates exist
        return max(specific_candidates, key=len)  # Return the most complete body candidate

    try:  # Fall back to the entire article text
        article_text = normalize_whitespace(article.inner_text(timeout=2_000))  # Read the loaded post text
    except Exception:  # Handle detached post elements
        return ""  # Return empty on failure

    return clean_article_fallback_text(article_text)  # Remove obvious Facebook interaction UI from the fallback


def clean_article_fallback_text(value: str) -> str:
    """
    Remove common Facebook interaction labels from whole-article fallback text.

    :param value: Raw article text.
    :return: Cleaned post text.
    """

    ignored_exact_lines = {
        "Like",
        "Comment",
        "Share",
        "Curtir",
        "Comentar",
        "Compartilhar",
        "Send",
        "Enviar",
        PROFILE_DISPLAY_NAME,
    }  # Common non-content lines

    result = []  # Initialize retained lines
    for line in normalize_whitespace(value).splitlines():  # Iterate normalized article lines
        stripped = line.strip()  # Normalize the current line
        if not stripped or stripped in ignored_exact_lines:  # Drop known UI-only lines
            continue  # Continue to the next line
        if re.fullmatch(r"\d+\s*(comments?|comentários?|shares?|compartilhamentos?)", stripped, re.IGNORECASE):  # Drop engagement counts
            continue  # Continue to the next line
        result.append(stripped)  # Preserve likely content

    return "\n".join(result).strip()  # Return the cleaned fallback text


def derive_post_title(content: str, post_id: str) -> str:
    """
    Derive a filesystem title from the first meaningful line of the post content.

    :param content: Full extracted post content.
    :param post_id: Post identifier used as a fallback.
    :return: Sanitized post title.
    """

    lines = [line.strip() for line in normalize_whitespace(content).splitlines() if line.strip()]  # Build meaningful lines
    title = ""  # Initialize the title

    for line in lines:  # Iterate through candidate title lines
        if line.casefold() == PROFILE_DISPLAY_NAME.casefold():  # Ignore an author-only line
            continue  # Continue to the next line
        title = line  # Use the first meaningful content line
        break  # Stop after selecting a title

    if not title:  # Handle media-only or otherwise textless posts
        title = f"Post {post_id}" if post_id else "Post"  # Build a deterministic fallback title

    if len(title) > MAX_CONTENT_TITLE_LENGTH:  # Limit the raw content used for the title
        title = title[:MAX_CONTENT_TITLE_LENGTH].rstrip()  # Truncate without trailing whitespace

    return sanitize_filename_component(title, fallback=f"Post {post_id}" if post_id else "Post")  # Return a safe title


def collect_date_candidates(article) -> list[str]:
    """
    Collect date strings from the canonical post timestamp instead of arbitrary nested links.

    :param article: Playwright locator representing a Facebook post.
    :return: Ordered list of distinct date candidates.
    """

    candidates = []  # Initialize ordered date candidates

    for permalink_candidate in collect_post_permalink_candidates(article):  # Inspect canonical post links in score order
        for key in ('aria_label', 'title', 'text'):  # Prefer timestamp metadata attached to the canonical link itself
            value = normalize_whitespace(str(permalink_candidate.get(key) or ''))  # Normalize candidate text
            if value and looks_like_date_candidate(value) and value not in candidates:  # Preserve date-like values only
                candidates.append(value)  # Store timestamp candidate

    try:  # Fall back to machine-readable date descendants that belong to this article only
        fallback_values = article.evaluate(
            """root => {
                const rootArticle = root.matches('div[role="article"]') ? root : null;
                const belongsToRoot = element => !rootArticle || element.closest('div[role="article"]') === rootArticle;
                return Array.from(root.querySelectorAll('abbr[data-utime], time[datetime]'))
                    .filter(belongsToRoot)
                    .flatMap(element => [
                        element.getAttribute('data-utime') || '',
                        element.getAttribute('datetime') || '',
                        element.getAttribute('aria-label') || '',
                        element.getAttribute('title') || '',
                        (element.innerText || element.textContent || '').trim(),
                    ]);
            }"""
        )  # Read same-article timestamp values
    except Exception:  # Detached articles provide no safe fallback date
        fallback_values = []  # Continue with canonical-link candidates only

    for raw_value in fallback_values or []:  # Normalize machine-readable fallback values
        value = normalize_whitespace(str(raw_value or ''))  # Normalize candidate
        if value and value not in candidates:  # Avoid duplicates
            candidates.append(value)  # Preserve fallback timestamp

    return candidates  # Return only post-level timestamp candidates


def looks_like_date_candidate(value: str) -> bool:
    """
    Determine whether arbitrary Facebook text plausibly represents a post timestamp.

    :param value: Candidate date text.
    :return: True when the value contains a known date/time signal.
    """

    normalized = normalize_whitespace(value).casefold()  # Normalize candidate for matching
    if not normalized:  # Reject empty values
        return False  # Empty text cannot represent a date

    if re.fullmatch(r"\d{9,11}", normalized):  # Accept Unix timestamps directly
        return True  # Numeric timestamp is date-like

    if re.search(r"\d{4}-\d{1,2}-\d{1,2}", normalized):  # Accept ISO-like dates
        return True  # ISO date is date-like

    month_words = (
        "janeiro", "fevereiro", "março", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
        "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december",
        "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
        "janvier", "février", "fevrier", "mars", "avril", "mai", "juin", "juillet", "août", "aout", "septembre", "octobre", "novembre", "décembre", "decembre",
        "januar", "februar", "märz", "marz", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "dezember",
    )  # Month names supported by the configured parser languages

    relative_words = (
        "ontem", "hoje", "yesterday", "today", "ayer", "hoy", "hier", "aujourd", "gestern", "heute",
        "ago", "atrás", "atras", "há ", "ha ", "min", "mins", "minute", "minutes", "hora", "horas",
        "hour", "hours", "dia", "dias", "day", "days", "semana", "semanas", "week", "weeks", "ano", "anos", "year", "years",
    )  # Relative date vocabulary commonly emitted by Facebook

    if any(word in normalized for word in month_words):  # Accept explicit month names
        return True  # Month-based label is date-like

    if any(word in normalized for word in relative_words):  # Accept relative Facebook timestamp text
        return True  # Relative label is date-like

    if re.fullmatch(r"\d+\s*(s|m|min|h|d|w|sem|a|y)", normalized):  # Accept compact timestamps such as "2 h" or "3 d"
        return True  # Compact relative label is date-like

    if re.search(r"\b(19|20)\d{2}\b", normalized) and re.search(r"\b\d{1,2}\b", normalized):  # Accept explicit year labels
        return True  # Year-bearing label is date-like

    return False  # Reject arbitrary aria-labels, names, reaction counts, and accessibility text


def is_plausible_post_datetime(value: datetime.datetime, reference_now: datetime.datetime) -> bool:
    """
    Validate that a parsed timestamp falls inside a plausible Facebook post range.

    :param value: Parsed timestamp.
    :param reference_now: Current local timestamp used as an upper bound.
    :return: True when the parsed date is plausible for a Facebook post.
    """

    lower_bound = datetime.datetime(2004, 2, 4, tzinfo=reference_now.tzinfo)  # Facebook launch-date lower bound
    upper_bound = reference_now + datetime.timedelta(days=1)  # Permit minor timezone/calendar boundary differences

    if value.tzinfo is None:  # Normalize naive parsed values
        value = value.replace(tzinfo=reference_now.tzinfo)  # Attach the local timezone

    normalized = value.astimezone(reference_now.tzinfo)  # Normalize to current local timezone
    return lower_bound <= normalized <= upper_bound  # Reject implausible historical/future parses


def parse_facebook_date(candidates: list[str]) -> tuple[datetime.datetime | None, str]:
    """
    Parse Facebook date candidates using Unix timestamps, ISO values, and localized text.

    :param candidates: Ordered raw date candidates.
    :return: Tuple containing the parsed datetime and the raw value that produced it.
    """

    reference_now = datetime.datetime.now().astimezone()  # Capture a stable base for relative dates

    for candidate in candidates:  # Iterate from most likely to least likely date values
        value = str(candidate).strip()  # Normalize the current candidate
        if not value or not looks_like_date_candidate(value):  # Reject arbitrary labels before parsing
            continue  # Continue to the next candidate

        if re.fullmatch(r"\d{9,11}", value):  # Detect Unix timestamp values
            try:  # Attempt timestamp conversion
                parsed = datetime.datetime.fromtimestamp(int(value), tz=reference_now.tzinfo)  # Convert to local datetime
                if is_plausible_post_datetime(parsed, reference_now):  # Validate timestamp range
                    return parsed, value  # Return the parsed result
            except (OverflowError, OSError, ValueError):  # Ignore invalid timestamp ranges
                pass  # Continue to text parsing

        try:  # Attempt native ISO parsing before using dateparser
            iso_candidate = value.replace("Z", "+00:00")  # Normalize trailing UTC designator
            parsed_iso = datetime.datetime.fromisoformat(iso_candidate)  # Parse ISO date/time
            if parsed_iso.tzinfo is None:  # Normalize naive values to local timezone
                parsed_iso = parsed_iso.replace(tzinfo=reference_now.tzinfo)  # Attach local timezone
            if is_plausible_post_datetime(parsed_iso, reference_now):  # Validate timestamp range
                return parsed_iso.astimezone(reference_now.tzinfo), value  # Return normalized ISO result
        except ValueError:  # Candidate was not ISO-compatible
            pass  # Continue to localized parsing

        parsed = dateparser.parse(
            value,
            languages=["pt", "en", "es", "fr", "de"],
            settings={
                "RELATIVE_BASE": reference_now.replace(tzinfo=None),  # Use one stable base for relative labels such as "2 h"
                "RETURN_AS_TIMEZONE_AWARE": False,  # Parse missing timezone without relying on OS-specific timezone names
                "PREFER_DATES_FROM": "past",  # Facebook post dates should not resolve into the future
            },
        )  # Parse localized Facebook labels

        if parsed is not None:  # Verify parsing succeeded
            if parsed.tzinfo is None:  # Attach the current local timezone when the label did not include one
                parsed = parsed.replace(tzinfo=reference_now.tzinfo)  # Normalize naive result
            else:  # Normalize timezone-aware results
                parsed = parsed.astimezone(reference_now.tzinfo)  # Convert to the local timezone

            if is_plausible_post_datetime(parsed, reference_now):  # Reject false-positive text parses
                return parsed, value  # Return the parsed result and source text

    return None, ""  # Return failure without inventing a post date


def resolve_post_date(article) -> tuple[datetime.datetime | None, str]:
    """
    Resolve the date of a loaded Facebook post.

    :param article: Playwright locator representing a Facebook post.
    :return: Parsed datetime and raw date label.
    """

    candidates = collect_date_candidates(article)  # Collect all available date representations
    return parse_facebook_date(candidates)  # Parse the candidates in preference order


def get_article_locator(page: Page):
    """
    Return the first Facebook article selector that currently matches loaded posts.

    :param page: Facebook profile timeline page.
    :return: Playwright locator for loaded posts.
    """

    for selector in ARTICLE_SELECTORS:  # Iterate supported post container selectors
        locator = page.locator(selector)  # Build the candidate locator
        try:  # Attempt to inspect the current count
            if locator.count() > 0:  # Verify at least one post is currently loaded
                return locator  # Return the matching selector
        except Exception:  # Ignore transient DOM failures
            continue  # Continue to the next selector

    return page.locator(ARTICLE_SELECTORS[0])  # Return the primary selector so later loops can retry naturally


def get_live_page_url(page: Page) -> str:
    """
    Read the current top-level URL directly from the browser page.

    Reading window.location.href first avoids relying only on a cached Page.url value while
    Facebook replaces pages or performs client-side authentication transitions.

    :param page: Playwright page whose current URL should be resolved.
    :return: Current page URL, or an empty string when the page cannot be inspected.
    """

    if page.is_closed():  # A closed page has no usable live URL
        return ""  # Return an empty URL for closed pages

    try:  # Prefer the browser's own live location value
        live_url = page.evaluate("window.location.href")  # Read the current top-level browser URL
        if isinstance(live_url, str) and live_url.strip():  # Verify a usable URL was returned
            return live_url.strip()  # Return the browser-reported URL
    except Exception:  # Fall back to Playwright's Page.url property during transient navigations
        pass  # Continue to the fallback

    try:  # Read Playwright's last known URL as a fallback
        return str(page.url or "").strip()  # Return the normalized fallback URL
    except Exception:  # Treat inaccessible pages as having no current URL
        return ""  # Return an empty URL


def format_url_for_log(url: str) -> str:
    """
    Format a URL for logs without exposing authentication query parameters or fragments.

    Facebook authentication URLs can contain long encrypted_context values and other
    verification state in the query string. Logs therefore retain only scheme, host, and path.

    :param url: Raw browser URL.
    :return: Safe URL containing no query string or fragment.
    """

    try:  # Parse the URL using the standard URL parser
        parsed = urlparse(str(url or ""))  # Split the URL into structured components

        if not parsed.scheme or not parsed.netloc:  # Preserve simple fallback strings such as <unknown>
            return str(url or "<unknown>")  # Return the original non-URL value

        return urlunparse(
            (parsed.scheme, parsed.netloc, parsed.path or "/", "", "", "")
        )  # Rebuild the URL without query parameters or fragments
    except Exception:  # Logging must never fail because of a malformed URL
        return "<unknown>"  # Return a safe fallback


def is_facebook_url(url: str) -> bool:
    """
    Determine whether a URL belongs to Facebook.

    :param url: URL to inspect.
    :return: True when the hostname is facebook.com or one of its subdomains.
    """

    try:  # Parse the URL hostname safely
        hostname = (urlparse(str(url or "")).hostname or "").casefold()  # Normalize hostname
    except Exception:  # Invalid URLs are not Facebook pages
        return False  # Reject malformed URLs

    return hostname == "facebook.com" or hostname.endswith(".facebook.com")  # Match Facebook hostnames only


def is_facebook_authentication_path(url: str) -> bool:
    """
    Determine whether a Facebook URL path represents an authentication or verification flow.

    Query parameters are deliberately ignored. For example, the authenticated Facebook home
    URL "/?checkpoint_src=any" has path "/" and must not be mistaken for "/checkpoint".

    :param url: Facebook URL to inspect.
    :return: True when the URL path is a known authentication/verification route.
    """

    if not is_facebook_url(url):  # Authentication-path checks only apply to Facebook pages
        return False  # Reject non-Facebook URLs

    try:  # Parse only the path component so query-string names cannot cause false positives
        path = (urlparse(url).path or "/").casefold().rstrip("/") or "/"  # Normalize path
    except Exception:  # Treat malformed Facebook URLs conservatively
        return True  # Do not accept authentication based on an unparseable URL

    for prefix in AUTHENTICATION_PATH_PREFIXES:  # Compare against known authentication route prefixes
        normalized_prefix = prefix.casefold().rstrip("/") or "/"  # Normalize configured prefix
        if path == normalized_prefix or path.startswith(f"{normalized_prefix}/"):  # Match route and descendants
            return True  # Authentication or verification is still in progress

    return False  # The current Facebook path is not an authentication route


def has_facebook_session_cookie(context: BrowserContext) -> bool:
    """
    Determine whether the browser context contains Facebook's authenticated user cookie.

    :param context: Persistent browser context containing Facebook session state.
    :return: True when a non-empty c_user cookie is available for a Facebook domain.
    """

    try:  # Read context cookies without logging any cookie value
        cookies = context.cookies()  # Retrieve every cookie from the persistent context
    except Exception:  # Treat cookie-read failures as unauthenticated instead of guessing
        return False  # Authentication cannot be positively confirmed

    for cookie in cookies:  # Inspect cookie metadata only
        cookie_name = str(cookie.get("name") or "")  # Normalize cookie name
        cookie_value = str(cookie.get("value") or "").strip()  # Read value only for non-empty validation
        cookie_domain = str(cookie.get("domain") or "").lstrip(".").casefold()  # Normalize cookie domain

        if (
            cookie_name == "c_user"
            and cookie_value
            and (cookie_domain == "facebook.com" or cookie_domain.endswith(".facebook.com"))
        ):  # Verify Facebook's authenticated-user cookie exists
            return True  # A Facebook user session is present

    return False  # No authenticated Facebook user cookie was found


def has_visible_authentication_challenge(page: Page) -> bool:
    """
    Detect visible Facebook login, CAPTCHA, 2FA, or checkpoint controls.

    :param page: Browser page currently involved in Facebook authentication.
    :return: True when an interactive authentication challenge is still visible.
    """

    if page.is_closed():  # Closed pages cannot be considered challenge-free
        return True  # Treat the page as unusable

    for selector in AUTHENTICATION_CHALLENGE_SELECTORS:  # Inspect known authentication/challenge controls
        try:  # Isolate DOM changes and transient navigation states
            locator = page.locator(selector)  # Build the challenge locator
            count = min(locator.count(), 5)  # Bound work when Facebook renders duplicate hidden controls

            for index in range(count):  # Inspect a few matching controls
                try:  # Protect against elements detaching during navigation
                    if locator.nth(index).is_visible():  # Verify the challenge control is actually visible
                        return True  # Authentication is still interactive/incomplete
                except Exception:  # Ignore one transient element and continue checking
                    continue  # Continue to the next matching control
        except Exception:  # Ignore selector failures during Facebook navigation
            continue  # Continue to the next challenge selector

    return False  # No visible authentication challenge control was found


def has_authenticated_facebook_ui(page: Page) -> bool:
    """
    Detect UI that is expected only after a Facebook user session has reached the normal site.

    The function intentionally combines multiple structural signals instead of depending on
    language-specific text such as "Home", "Página inicial", or profile-menu labels.

    :param page: Facebook page to inspect.
    :return: True when normal authenticated Facebook navigation/main content is rendered.
    """

    if page.is_closed():  # A closed page has no usable authenticated UI
        return False  # Reject the page

    try:  # Require Facebook's normal main content region
        has_main = page.locator('div[role="main"]').count() > 0  # Detect central Facebook content
    except Exception:  # Transient DOM failures mean the UI is not yet stable
        has_main = False  # Keep waiting

    try:  # Look for the normal logged-in navigation region
        has_navigation = page.locator('[role="navigation"]').count() > 0  # Detect navigation controls
    except Exception:  # Ignore transient navigation-region failures
        has_navigation = False  # Keep waiting

    try:  # Detect a link to the configured user's own profile as an additional positive signal
        profile_path = urlparse(PROFILE_URL).path.rstrip("/")  # Resolve configured profile slug/path
        has_profile_link = bool(profile_path) and page.locator(
            f'a[href*="{profile_path}"]'
        ).count() > 0  # Detect the user's profile link in the authenticated shell
    except Exception:  # Ignore transient profile-link detection failures
        has_profile_link = False  # Keep waiting

    return has_main and (has_navigation or has_profile_link)  # Require normal main UI plus one authenticated-shell signal


def is_facebook_authentication_in_progress(page: Page) -> bool:
    """
    Determine whether Facebook is still showing an authentication or verification flow.

    :param page: Browser page to inspect.
    :return: True when login, CAPTCHA, 2FA, recovery, or checkpoint work is still pending.
    """

    if page.is_closed():  # Verify the user has not closed this page
        return True  # A closed page cannot be considered authenticated

    current_url = get_live_page_url(page)  # Read the browser's current live URL

    if not is_facebook_url(current_url):  # Authentication is incomplete while Facebook redirects elsewhere
        return True  # Wait for the flow to return to Facebook

    if is_facebook_authentication_path(current_url):  # Detect known authentication/challenge routes by URL path only
        return True  # Authentication or verification is still in progress

    if has_visible_authentication_challenge(page):  # Detect interactive login/2FA/CAPTCHA controls
        return True  # Wait for the user to finish the challenge

    return False  # No current authentication-flow indicator was found


def is_facebook_authenticated(page: Page, context: BrowserContext) -> bool:
    """
    Positively verify that a specific browser page represents a completed Facebook session.

    :param page: Browser page to inspect.
    :param context: Persistent browser context containing Facebook session state.
    :return: True only when session, URL, challenge, and authenticated UI checks all succeed.
    """

    if not has_facebook_session_cookie(context):  # Require Facebook's authenticated-user session cookie first
        return False  # Do not infer authentication from page appearance alone

    if is_facebook_authentication_in_progress(page):  # Reject login/checkpoint/transient states
        return False  # Authentication is not complete on this page

    if not has_authenticated_facebook_ui(page):  # Require normal logged-in Facebook structure
        return False  # Avoid accepting a blank/intermediate redirect after the cookie appears

    return True  # Positive session evidence and authenticated UI are both present


def select_current_facebook_page(context: BrowserContext, preferred_page: Page | None = None) -> Page:
    """
    Resolve the Facebook page that currently represents the user's active authentication state.

    Facebook authentication can replace or open pages during CAPTCHA, 2FA, and checkpoint
    flows. The downloader therefore re-evaluates every page in the persistent context instead
    of permanently trusting the Page object captured when Chrome first launched.

    :param context: Persistent browser context containing all browser pages.
    :param preferred_page: Previously selected page, when still available.
    :return: Best current Facebook page.
    """

    pages = [page for page in context.pages if not page.is_closed()]  # Snapshot all currently usable pages

    if not pages:  # The browser context should always contain at least one page
        raise RuntimeError("The Facebook automation browser has no open pages.")  # Stop with a precise error

    facebook_pages = [page for page in pages if is_facebook_url(get_live_page_url(page))]  # Keep Facebook pages only

    if has_facebook_session_cookie(context):  # Once a session exists, prefer a page that has reached normal Facebook UI
        authenticated_pages = [
            page for page in facebook_pages if is_facebook_authenticated(page, context)
        ]  # Find every positively authenticated Facebook page

        if authenticated_pages:  # Prefer the configured profile when it is already open
            target_prefix = PROFILE_URL.casefold().rstrip("/")  # Normalize configured profile URL
            for candidate in reversed(authenticated_pages):  # Prefer newer pages when multiple pages match
                if get_live_page_url(candidate).casefold().rstrip("/").startswith(target_prefix):
                    return candidate  # Reuse the actual configured profile page

            return authenticated_pages[-1]  # Otherwise use the newest authenticated Facebook page

    challenge_pages = [
        page for page in facebook_pages if is_facebook_authentication_in_progress(page)
    ]  # Find current login/2FA/checkpoint pages

    if challenge_pages:  # Prefer the newest challenge page because Facebook may replace the original tab/page
        return challenge_pages[-1]  # Return the most recently created challenge page

    if preferred_page is not None and not preferred_page.is_closed():  # Reuse the prior page when it remains usable
        return preferred_page  # Preserve continuity during ordinary client-side navigation

    if facebook_pages:  # Fall back to the newest Facebook page
        return facebook_pages[-1]  # Return the newest Facebook page

    return pages[-1]  # Fall back to the newest browser page before initial Facebook navigation


def wait_for_facebook_login(page: Page, context: BrowserContext) -> Page:
    """
    Wait until the complete Facebook authentication flow is finished and stable.

    The function intentionally waits through password entry, CAPTCHA, 2FA, recovery,
    checkpoints, approval prompts, page replacement, and intermediate redirects.
    Authentication is accepted only after the same positively authenticated page remains
    valid for AUTHENTICATION_STABLE_SECONDS.

    :param page: Initial Playwright page displaying the Facebook authentication flow.
    :param context: Persistent browser context containing Facebook session state.
    :return: Current authenticated Facebook page that should be used after login.
    """

    print(
        f"{BackgroundColors.YELLOW}Waiting for complete Facebook authentication. "
        f"{BackgroundColors.GREEN}Finish every required step in the browser, including CAPTCHA, 2FA, "
        f"checkpoints, or confirmation prompts. The session will remain in "
        f"{BackgroundColors.CYAN}{AUTOMATION_PROFILE_DIR.as_posix()}{Style.RESET_ALL}"
    )  # Explain that all interactive authentication steps must be completed manually

    deadline = (
        None
        if LOGIN_WAIT_SECONDS <= 0
        else time.monotonic() + LOGIN_WAIT_SECONDS
    )  # Allow indefinite waiting by default while retaining an optional configurable timeout

    authenticated_since = None  # Track when a continuously valid authenticated state began
    authenticated_page = None  # Track the page that owns the current stability window
    last_status_output = 0.0  # Limit repeated waiting messages

    while deadline is None or time.monotonic() < deadline:  # Wait until authentication is stable or configured timeout expires
        page = select_current_facebook_page(context, page)  # Follow page replacements/new tabs created by Facebook authentication
        now = time.monotonic()  # Capture one monotonic timestamp for this iteration

        try:  # Authentication state can change repeatedly during CAPTCHA/2FA redirects
            authenticated = is_facebook_authenticated(page, context)  # Positively verify the selected current page
        except Exception:  # Treat transient browser/DOM errors as an unstable authentication state
            authenticated = False  # Continue waiting instead of advancing early

        if authenticated:  # A candidate authenticated state is currently present
            if authenticated_since is None or authenticated_page is not page:  # Start/restart stability for the selected page
                authenticated_since = now  # Record the beginning of continuous authentication
                authenticated_page = page  # Bind the stability window to this concrete Page object

            stable_for = now - authenticated_since  # Calculate continuous authenticated duration

            if stable_for >= AUTHENTICATION_STABLE_SECONDS:  # Require the page to remain valid across redirects/prompts
                print(
                    f"{BackgroundColors.GREEN}Facebook authentication confirmed and stable for "
                    f"{BackgroundColors.CYAN}{AUTHENTICATION_STABLE_SECONDS:.0f}s{BackgroundColors.GREEN}. "
                    f"{BackgroundColors.GREEN}Current page: "
                    f"{BackgroundColors.CYAN}{format_url_for_log(get_live_page_url(page))}{Style.RESET_ALL}"
                )  # Log only after positive stable confirmation without exposing authentication query data
                return page  # Return the actual authenticated page currently shown by Facebook
        else:  # Any challenge, missing cookie, redirect, page replacement, or transient state invalidates the candidate
            authenticated_since = None  # Restart the stability window after the user finishes the remaining step
            authenticated_page = None  # Clear the previously authenticated Page candidate

        if now - last_status_output >= AUTHENTICATION_STATUS_LOG_INTERVAL_SECONDS:  # Provide occasional progress without flooding the terminal
            safe_url = format_url_for_log(get_live_page_url(page))  # Strip authentication query data from logs
            print(
                f"{BackgroundColors.YELLOW}Authentication still in progress; waiting for completion. "
                f"{BackgroundColors.GREEN}Current page: {BackgroundColors.CYAN}{safe_url}{Style.RESET_ALL}"
            )  # Make it clear the program has intentionally not advanced
            last_status_output = now  # Record the status-output time

        time.sleep(AUTHENTICATION_POLL_SECONDS)  # Poll slowly while the user interacts with Facebook

    raise TimeoutError(
        f"Facebook authentication was not fully completed and stable within {LOGIN_WAIT_SECONDS} seconds."
    )  # Fail only when the user explicitly configures a finite timeout


def wait_for_existing_facebook_authentication(
    page: Page,
    context: BrowserContext,
    timeout_seconds: float = HEADLESS_AUTHENTICATION_CHECK_TIMEOUT_SECONDS,
) -> Page | None:
    """
    Check whether the persistent browser profile already contains a usable Facebook login.

    This function never waits for manual interaction. It is intended for the initial headless
    probe and for validating the same persistent profile after an interactive authentication
    browser has been closed and relaunched headlessly.

    :param page: Initial Facebook page to inspect.
    :param context: Persistent browser context containing saved authentication state.
    :param timeout_seconds: Maximum number of seconds to wait for existing authenticated UI to render.
    :return: Current authenticated Facebook page, or None when manual authentication is required.
    """

    deadline = time.monotonic() + max(0.0, timeout_seconds)  # Bound the non-interactive authentication probe

    while time.monotonic() <= deadline:  # Wait only for already-saved session state to finish rendering
        try:  # Facebook can replace pages while restoring a persisted browser session
            page = select_current_facebook_page(context, page)  # Follow the current Facebook page
        except Exception:  # A transient page-selection failure means the saved session is not ready yet
            time.sleep(AUTHENTICATION_POLL_SECONDS)  # Wait briefly before another probe
            continue  # Retry until the non-interactive deadline

        try:  # Positively verify cookies, URL path, challenge UI, and authenticated Facebook shell
            if is_facebook_authenticated(page, context):  # Existing authentication is already usable
                return page  # Return the concrete authenticated page without opening a visible browser
        except Exception:  # Treat transient Facebook rerenders as an unresolved existing session
            pass  # Continue polling until timeout

        time.sleep(AUTHENTICATION_POLL_SECONDS)  # Allow persisted Facebook state to finish loading

    return None  # Manual authentication is required


def wait_for_profile_ready(
    page: Page,
    context: BrowserContext,
    allow_interactive_authentication: bool = True,
) -> Page:
    """
    Wait until the authenticated Facebook profile root page has rendered usable main/timeline content.

    :param page: Browser page opened at PROFILE_URL.
    :param context: Persistent authenticated browser context.
    :param allow_interactive_authentication: Whether the function may wait for manual authentication.
    :return: Current authenticated profile page that is ready for scraping.
    """

    deadline = time.monotonic() + PROFILE_READY_TIMEOUT_SECONDS  # Bound post-authentication profile rendering
    target_prefix = PROFILE_URL.casefold().rstrip("/")  # Normalize the configured profile URL

    while time.monotonic() < deadline:  # Wait for Facebook's client-rendered profile to become usable
        page = select_current_facebook_page(context, page)  # Follow any page replacement after profile navigation

        if not is_facebook_authenticated(page, context):  # Authentication may be challenged again after navigating to the profile
            if not allow_interactive_authentication:  # Headless mode cannot complete CAPTCHA/2FA/checkpoint interaction
                raise FacebookAuthenticationRequiredError(
                    "Facebook requires interactive authentication before the profile can be scraped."
                )  # Hand control back to the lifecycle manager so it can open a visible browser

            print(
                f"{BackgroundColors.YELLOW}Facebook requested additional authentication after profile navigation; "
                f"waiting for completion.{Style.RESET_ALL}"
            )  # Explain why scraping has not started
            page = wait_for_facebook_login(page, context)  # Wait through the new challenge and recover the current page
            continue  # Re-evaluate profile readiness afterward

        current_url = get_live_page_url(page).casefold().rstrip("/")  # Read the current live page location
        if not current_url.startswith(target_prefix):  # Ensure the configured profile is the page being inspected
            try:  # Navigate the currently authenticated page to the requested profile
                page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)  # Open configured profile
            except Exception:  # Allow transient client-side navigation failures to retry until the deadline
                time.sleep(AUTHENTICATION_POLL_SECONDS)  # Wait briefly before retrying
            continue  # Re-select and validate the profile page

        try:  # Verify that Facebook rendered the authenticated profile's main content
            has_main_content = page.locator('div[role="main"]').count() > 0  # Detect the main profile region
            has_timeline_articles = any(page.locator(selector).count() > 0 for selector in ARTICLE_SELECTORS)  # Detect loaded posts

            if has_main_content or has_timeline_articles:  # Either signal proves that the authenticated profile UI rendered
                return page  # Return the concrete profile page to the scraper
        except Exception:  # Ignore transient client-side rerenders
            pass  # Continue polling until the page stabilizes

        time.sleep(AUTHENTICATION_POLL_SECONDS)  # Wait before checking the rendered profile again

    raise TimeoutError(
        f"Facebook authentication is valid, but the profile did not render usable content within "
        f"{PROFILE_READY_TIMEOUT_SECONDS} seconds. Current URL: {format_url_for_log(get_live_page_url(page))}"
    )  # Do not silently run an empty scraper against an unusable page


def find_existing_facebook_page(context: BrowserContext) -> Page | None:
    """
    Find the best existing Facebook page inside the persistent browser context.

    :param context: Persistent browser context used by the downloader.
    :return: Existing Facebook page or None.
    """

    pages = [page for page in context.pages if not page.is_closed()]  # Snapshot usable pages
    facebook_pages = [page for page in pages if is_facebook_url(get_live_page_url(page))]  # Keep Facebook pages only

    if not facebook_pages:  # Verify a reusable Facebook page exists
        return None  # No Facebook page is currently open

    target_prefix = PROFILE_URL.casefold().rstrip("/")  # Normalize configured profile URL

    for page in reversed(facebook_pages):  # Prefer the newest exact configured profile page
        if get_live_page_url(page).casefold().rstrip("/").startswith(target_prefix):
            return page  # Return the configured profile page

    if has_facebook_session_cookie(context):  # Prefer a positively authenticated page when login is already persisted
        for page in reversed(facebook_pages):  # Prefer the newest authenticated Facebook page
            if is_facebook_authenticated(page, context):
                return page  # Return the current authenticated page

    return facebook_pages[-1]  # Otherwise return the newest Facebook page for authentication


def launch_browser_session(playwright: Playwright, headless: bool) -> BrowserSession:
    """
    Launch the dedicated persistent browser profile in visible or headless mode.

    Chromium sandboxing is explicitly enabled so Chrome is not launched with Playwright's
    default --no-sandbox configuration. The same AUTOMATION_PROFILE_DIR is reused between
    interactive authentication and headless scraping, but never by two contexts simultaneously.

    :param playwright: Active Playwright instance.
    :param headless: True to run invisibly, False to open an interactive browser window.
    :return: BrowserSession containing the page, context, and browser visibility mode.
    """

    AUTOMATION_PROFILE_DIR.mkdir(parents=True, exist_ok=True)  # Ensure the persistent automation profile exists
    mode_name = "headless" if headless else "interactive"  # Build the browser mode label used in logs
    launch_args = [] if headless else ["--start-maximized"]  # Window-management arguments are useful only for visible Chrome

    print(
        f"{BackgroundColors.GREEN}Launching {mode_name} persistent automation profile: "
        f"{BackgroundColors.CYAN}{AUTOMATION_PROFILE_DIR.as_posix()}{Style.RESET_ALL}"
    )  # Log exactly how the persistent browser profile is being opened

    try:  # Prefer the locally installed stable Google Chrome browser
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(AUTOMATION_PROFILE_DIR),
            channel=BROWSER_CHANNEL,
            headless=headless,
            no_viewport=True,
            chromium_sandbox=True,
            args=launch_args,
        )  # Launch stable Chrome using the project's persistent profile
    except Exception as chrome_error:  # Fall back to Playwright Chromium when stable Chrome cannot be launched
        verbose_output(
            true_string=f"{BackgroundColors.YELLOW}Stable Chrome launch failed: {BackgroundColors.CYAN}{chrome_error}{Style.RESET_ALL}"
        )  # Log the stable Chrome failure only in verbose mode

        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(AUTOMATION_PROFILE_DIR),
            headless=headless,
            no_viewport=True,
            chromium_sandbox=True,
            args=launch_args,
        )  # Launch bundled Chromium using the same persistent profile and visibility mode

    page = find_existing_facebook_page(context) or (context.pages[-1] if context.pages else context.new_page())  # Resolve the page to control
    return BrowserSession(context=context, page=page)  # Return the locally managed browser session


def navigate_to_profile(
    page: Page,
    context: BrowserContext,
    allow_interactive_authentication: bool = True,
) -> Page:
    """
    Verify authentication and open a fresh profile root timeline from its newest position.

    :param page: Initial browser page used by the downloader.
    :param context: Persistent browser context containing Facebook authentication state.
    :param allow_interactive_authentication: Whether manual browser authentication is available.
    :return: Current authenticated profile root page ready for scraping.
    """

    page.set_default_timeout(10_000)  # Configure conservative default action timeout
    page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT_MS)  # Configure navigation timeout

    current_url = get_live_page_url(page)  # Resolve current live browser location
    if not is_facebook_url(current_url):  # Open Facebook first when persistent browser starts elsewhere
        page.goto(FACEBOOK_BASE_URL, wait_until='domcontentloaded', timeout=PAGE_LOAD_TIMEOUT_MS)  # Enter Facebook before session validation

    if allow_interactive_authentication:  # Visible mode can wait for CAPTCHA/2FA/checkpoint interaction
        page = wait_for_facebook_login(page, context)  # Follow current page through full authentication flow
    else:  # Headless mode requires already persisted authentication
        existing_page = wait_for_existing_facebook_authentication(page, context)  # Probe saved session
        if existing_page is None:  # No usable authenticated state restored
            raise FacebookAuthenticationRequiredError('The persistent Facebook session requires manual authentication.')  # Request visible auth
        page = existing_page  # Continue with authenticated headless page

    page.set_default_timeout(10_000)  # Reapply timeout if Facebook replaced page
    page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT_MS)  # Reapply navigation timeout

    # Always perform a fresh navigation after authentication. Persistent Chrome may restore a
    # previous deep scroll position, so explicitly reopening the profile root ensures the timeline
    # starts from its newest visible state. Do not append '/posts': that route is not available for
    # every Facebook profile and can render Facebook's "content unavailable" page.
    page.goto(PROFILE_URL, wait_until='domcontentloaded', timeout=PAGE_LOAD_TIMEOUT_MS)  # Open the configured profile root fresh
    page = select_current_facebook_page(context, page)  # Recover current page if Facebook replaced it during navigation

    if not is_facebook_authenticated(page, context):  # Profile navigation can trigger another challenge
        if not allow_interactive_authentication:  # Headless mode cannot resolve new verification
            raise FacebookAuthenticationRequiredError('Facebook requested additional verification after profile navigation.')  # Reopen visible auth
        page = wait_for_facebook_login(page, context)  # Wait through additional verification
        page.goto(PROFILE_URL, wait_until='domcontentloaded', timeout=PAGE_LOAD_TIMEOUT_MS)  # Reopen profile root after challenge
        page = select_current_facebook_page(context, page)  # Recover current page after challenge navigation

    page = wait_for_profile_ready(
        page,
        context,
        allow_interactive_authentication=allow_interactive_authentication,
    )  # Require authenticated profile content before scraping

    try:  # Explicitly reset browser viewport to newest timeline position
        page.evaluate('window.scrollTo(0, 0)')  # Start from top even if persistent history restored a deep scroll offset
        page.wait_for_timeout(1_500)  # Allow the profile header and newest timeline posts to settle
    except Exception:  # Scrolling reset is best-effort after successful fresh navigation
        pass  # Continue with current top position

    print(
        f"{BackgroundColors.GREEN}Profile timeline loaded from newest position: "
        f"{BackgroundColors.CYAN}{PROFILE_URL}{Style.RESET_ALL}"
    )  # Log profile-root timeline readiness

    return page  # Return exact Page object ready for timeline scraping


def establish_authenticated_scraping_session(
    playwright: Playwright,
    force_interactive_authentication: bool = False,
) -> BrowserSession:
    """
    Establish the browser session that will perform Facebook scraping.

    When HEADLESS_AFTER_AUTHENTICATION is enabled, the persistent profile is checked headlessly
    first. If that check fails, the headless context is closed before a visible context opens for
    manual authentication. The visible context is then closed and the same profile is relaunched
    headlessly. If Facebook immediately requests another verification after that relaunch, the
    process repeats without losing already persisted authentication/profile state.

    :param playwright: Active Playwright instance.
    :param force_interactive_authentication: Skip the initial headless probe and open visible authentication immediately.
    :return: Authenticated browser session ready to scrape PROFILE_URL.
    """

    if not HEADLESS_AFTER_AUTHENTICATION:  # Support an explicit fully-visible mode when desired
        session = launch_browser_session(playwright, headless=False)  # Open the persistent profile visibly
        session.page = navigate_to_profile(
            session.page,
            session.context,
            allow_interactive_authentication=True,
        )  # Complete any required authentication and open the target profile
        return session  # Keep the visible browser for scraping because headless mode is disabled

    if not force_interactive_authentication:  # Normal startup should first reuse a persisted login without showing a window
        print(
            f"{BackgroundColors.GREEN}Checking the persistent Facebook session in headless mode...{Style.RESET_ALL}"
        )  # Explain the invisible authentication probe

        headless_session = launch_browser_session(playwright, headless=True)  # Open the persistent profile invisibly

        try:  # Attempt to reuse the existing login without disturbing the user
            headless_session.page = navigate_to_profile(
                headless_session.page,
                headless_session.context,
                allow_interactive_authentication=False,
            )  # Require an already-authenticated profile without interactive waiting

            print(
                f"{BackgroundColors.GREEN}Existing authenticated headless session confirmed.{Style.RESET_ALL}"
            )  # Log successful invisible startup
            return headless_session  # Start scraping immediately with no visible browser window
        except FacebookAuthenticationRequiredError:  # The saved session needs CAPTCHA/2FA/checkpoint interaction
            print(
                f"{BackgroundColors.YELLOW}The persistent session requires interactive Facebook authentication.{Style.RESET_ALL}"
            )  # Explain why a browser window is about to appear
            close_browser_session(headless_session)  # Release the profile lock before opening the visible browser
            time.sleep(BROWSER_RELAUNCH_DELAY_SECONDS)  # Allow Chrome to flush/close persistent profile files
        except Exception:  # Do not leave a failed headless context holding the persistent profile
            close_browser_session(headless_session)  # Release browser resources before propagating the failure
            raise  # Preserve the original unexpected error

    while True:  # Repeat only if Facebook challenges the account again immediately after headless relaunch
        print(
            f"{BackgroundColors.GREEN}Opening interactive browser for Facebook authentication...{Style.RESET_ALL}"
        )  # Tell the user a visible browser is intentionally required

        interactive_session = launch_browser_session(playwright, headless=False)  # Open the same profile visibly

        try:  # Keep the interactive browser open until the complete authentication flow is stable
            interactive_session.page = navigate_to_profile(
                interactive_session.page,
                interactive_session.context,
                allow_interactive_authentication=True,
            )  # Let the user finish CAPTCHA, 2FA, checkpoints, or confirmation prompts
        except Exception:  # Authentication/navigation failure must not leave the browser/profile locked
            close_browser_session(interactive_session)  # Close the visible browser safely
            raise  # Preserve the original error

        print(
            f"{BackgroundColors.GREEN}Closing interactive authentication browser...{Style.RESET_ALL}"
        )  # Explain why the visible Chrome window is disappearing
        close_browser_session(interactive_session)  # Flush authenticated state to AUTOMATION_PROFILE_DIR
        time.sleep(BROWSER_RELAUNCH_DELAY_SECONDS)  # Ensure the persistent profile lock is fully released

        print(
            f"{BackgroundColors.GREEN}Relaunching authenticated browser in headless mode...{Style.RESET_ALL}"
        )  # Explain the transition to invisible scraping
        headless_session = launch_browser_session(playwright, headless=True)  # Reopen the exact same profile invisibly

        try:  # Verify that authentication survived the headed-to-headless transition
            headless_session.page = navigate_to_profile(
                headless_session.page,
                headless_session.context,
                allow_interactive_authentication=False,
            )  # Require the saved session to work without interaction

            print(
                f"{BackgroundColors.GREEN}Authenticated headless session confirmed. "
                f"Starting Facebook posts download...{Style.RESET_ALL}"
            )  # Confirm that the user can continue using the computer normally
            return headless_session  # Hand the invisible authenticated browser to the scraper
        except FacebookAuthenticationRequiredError:  # Facebook may challenge the account specifically after headless relaunch
            print(
                f"{BackgroundColors.YELLOW}Facebook requested another verification after the headless relaunch. "
                f"Reopening interactive authentication.{Style.RESET_ALL}"
            )  # Explain the automatic recovery path
            close_browser_session(headless_session)  # Release the persistent profile before reopening it visibly
            time.sleep(BROWSER_RELAUNCH_DELAY_SECONDS)  # Allow profile files to flush before the next attempt
            continue  # Reopen a visible authentication browser
        except Exception:  # Unexpected headless startup failure should not leave browser resources open
            close_browser_session(headless_session)  # Release the persistent profile
            raise  # Preserve the original failure


def ensure_scraping_profile_ready(page: Page, context: BrowserContext) -> Page:
    """
    Ensure the current scraping page remains authenticated and belongs to the configured profile feed.

    :param page: Current scraping page.
    :param context: Current authenticated browser context.
    :return: Authenticated profile page.
    """

    page = select_current_facebook_page(context, page)  # Follow Facebook page replacement if one occurred

    if not is_facebook_authenticated(page, context):  # Detect expired login/checkpoint/CAPTCHA/2FA interruption
        raise FacebookAuthenticationRequiredError('Facebook authentication was interrupted during scraping.')  # Reopen visible auth

    target_prefix = PROFILE_URL.casefold().rstrip('/')  # Require the configured profile root
    current_url = get_live_page_url(page).casefold().rstrip('/')  # Read current live URL

    if not current_url.startswith(target_prefix):  # Recover from unexpected navigation away from configured profile
        page.goto(PROFILE_URL, wait_until='domcontentloaded', timeout=PAGE_LOAD_TIMEOUT_MS)  # Return to the configured profile root
        page = wait_for_profile_ready(page, context, allow_interactive_authentication=False)  # Require headless readiness

    return page  # Return usable scraping page


def load_existing_post_keys() -> set[str]:
    """
    Load identifiers only from complete metadata written by the current scrape schema.

    Legacy metadata from earlier broken DOM/media extraction is deliberately ignored when
    REPROCESS_LEGACY_METADATA is True so the fixed scraper revisits those posts automatically.

    :param: None
    :return: Set containing known post identifiers and normalized post URLs.
    """

    known_keys = set()  # Initialize existing identifier set

    if not OUTPUT_DIR.exists():  # Verify an output directory already exists
        return known_keys  # Nothing has been downloaded yet

    for metadata_file in OUTPUT_DIR.glob(f'*/{POST_METADATA_FILENAME}'):  # Iterate existing post metadata files
        try:  # Isolate malformed or interrupted metadata files
            with metadata_file.open('r', encoding='utf-8') as file:  # Open metadata safely
                metadata = json.load(file)  # Parse JSON metadata

            schema_version = int(metadata.get('scrape_schema_version') or 0)  # Read extraction schema version
            complete = bool(metadata.get('complete'))  # Read explicit completion state

            if schema_version != SCRAPE_SCHEMA_VERSION:  # Detect metadata created by obsolete extraction logic
                if REPROCESS_LEGACY_METADATA:  # Fixed scraper should revisit old broken outputs
                    continue  # Do not add legacy post identifiers to the skip set
            if not complete:  # Never permanently skip a post whose media/extraction was incomplete
                continue  # Keep the post retryable on the next pass/run

            post_id = str(metadata.get('post_id') or '').strip()  # Read the stored post identifier
            post_url = normalize_facebook_url(str(metadata.get('post_url') or ''))  # Normalize the stored permalink

            if post_id:  # Preserve stable post identifier
                known_keys.add(f'id:{post_id}')  # Store identifier key
            if post_url:  # Preserve canonical permalink as a second deduplication mechanism
                known_keys.add(f'url:{post_url}')  # Store URL key
        except Exception as error:  # A damaged metadata file should be visible but must not abort all downloads
            print(
                f"{BackgroundColors.YELLOW}Skipping unreadable metadata file: "
                f"{BackgroundColors.CYAN}{metadata_file.as_posix()}"
                f"{BackgroundColors.YELLOW} ({error}){Style.RESET_ALL}"
            )  # Log the damaged file

    return known_keys  # Return completed current-schema post keys


def count_completed_post_outputs() -> int:
    """
    Count completed post outputs written by the current scrape schema.

    :param: None
    :return: Number of current-schema complete post outputs under OUTPUT_DIR.
    """

    if not OUTPUT_DIR.exists():  # No output root means no current-schema post is complete
        return 0  # Return an empty count

    completed = 0  # Initialize current-schema completed-post count

    for metadata_file in OUTPUT_DIR.glob(f'*/{POST_METADATA_FILENAME}'):  # Inspect each post metadata file
        try:  # Ignore legacy/damaged metadata when counting the current run
            with metadata_file.open('r', encoding='utf-8') as file:  # Open metadata safely
                metadata = json.load(file)  # Parse JSON metadata
            if int(metadata.get('scrape_schema_version') or 0) != SCRAPE_SCHEMA_VERSION:  # Ignore outputs from obsolete extraction logic
                continue  # Legacy metadata is intentionally reprocessed
            if not bool(metadata.get('complete')):  # Ignore posts whose required media could not be archived
                continue  # Incomplete posts must remain retryable
            completed += 1  # Count one fully completed current-schema post
        except Exception:  # Damaged files are not completed outputs
            continue  # Continue scanning remaining metadata

    return completed  # Return current-schema completed count


def build_post_keys(post_id: str, post_url: str) -> set[str]:
    """
    Build all deduplication keys available for a post.

    :param post_id: Stable post identifier.
    :param post_url: Normalized post URL.
    :return: Set containing identifier and URL keys.
    """

    keys = set()  # Initialize post key set
    if post_id:  # Verify a post identifier is available
        keys.add(f"id:{post_id}")  # Add identifier key
    if post_url:  # Verify a post URL is available
        keys.add(f"url:{normalize_facebook_url(post_url)}")  # Add normalized permalink key
    return keys  # Return available keys


def normalize_facebook_video_media_url(url: str) -> str:
    """
    Normalize a Facebook CDN video/audio URL by removing byte-range query parameters.

    Facebook frequently requests MP4 media using bytestart/byteend query parameters. Those URLs
    identify only a byte range; removing the range parameters allows the downloader to request the
    complete signed media resource while preserving all authentication/signature parameters.

    :param url: Raw Facebook CDN media URL.
    :return: URL without Facebook byte-range query parameters.
    """

    try:  # Parse the URL safely
        parsed = urlparse(str(url or ''))  # Split URL into components
        filtered_query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.casefold() not in VIDEO_RANGE_QUERY_PARAMETERS
        ]  # Remove only known byte-range query parameters
        return urlunparse(parsed._replace(query=urlencode(filtered_query, doseq=True), fragment=''))  # Rebuild normalized URL
    except Exception:  # Preserve original URL when parsing fails
        return str(url or '')  # Return raw candidate


def parse_http_content_range(value: str) -> tuple[int, int, int | None] | None:
    """
    Parse an HTTP Content-Range header such as "bytes 0-1023/4096".

    :param value: Raw Content-Range header value.
    :return: Tuple of start, end, total bytes, or None when parsing fails.
    """

    match = re.fullmatch(r'bytes\s+(\d+)-(\d+)/(\d+|\*)', str(value or '').strip(), re.IGNORECASE)  # Parse byte range
    if not match:  # Verify header format
        return None  # Return no parsed range

    start = int(match.group(1))  # Parse first byte index
    end = int(match.group(2))  # Parse last byte index
    total = None if match.group(3) == '*' else int(match.group(3))  # Parse complete resource size when known
    return start, end, total  # Return parsed range metadata


def count_post_media_indicators(article) -> tuple[int, int]:
    """
    Count visible top-level photo/video indicators in a post article before media extraction.

    :param article: Facebook post article.
    :return: Tuple containing photo-indicator count and video-indicator count.
    """

    try:  # Count only elements whose nearest article is the current post, excluding comments
        counts = article.evaluate(
            """root => {
                const rootArticle = root.matches('div[role="article"]') ? root : null;
                const belongsToRoot = element => !rootArticle || element.closest('div[role="article"]') === rootArticle;
                const anchors = Array.from(root.querySelectorAll('a[href]')).filter(belongsToRoot);
                const photoLinks = new Set(anchors
                    .map(anchor => anchor.href || anchor.getAttribute('href') || '')
                    .filter(href => href.includes('/photo/') || href.includes('/photos/') || href.includes('/photo.php')));
                const mediaImages = Array.from(root.querySelectorAll('img[data-visualcompletion="media-vc-image"]')).filter(belongsToRoot);
                const videos = Array.from(root.querySelectorAll('video')).filter(belongsToRoot);
                const videoLinks = new Set(anchors
                    .map(anchor => anchor.href || anchor.getAttribute('href') || '')
                    .filter(href => href.includes('/videos/') || href.includes('/reel/') || href.includes('/watch/')));
                return { photos: Math.max(photoLinks.size, mediaImages.length), videos: Math.max(videos.length, videoLinks.size) };
            }"""
        )  # Read top-level media indicators
        return int(counts.get('photos') or 0), int(counts.get('videos') or 0)  # Normalize counts
    except Exception:  # Detached articles provide no reliable indicator counts
        return 0, 0  # Treat media presence as unknown/absent


def collect_image_candidates(article) -> list[dict]:
    """
    Collect top-level post-photo URLs while excluding avatars, comments, icons, and reactions.

    :param article: Playwright locator representing a Facebook post.
    :return: List of image candidate dictionaries.
    """

    try:  # Read image/media relationship data in one browser-side pass
        raw_images = article.evaluate(
            """root => {
                const rootArticle = root.matches('div[role="article"]') ? root : null;
                const belongsToRoot = element => !rootArticle || element.closest('div[role="article"]') === rootArticle;
                const chooseLargestSrcset = srcset => {
                    if (!srcset) return '';
                    const entries = srcset.split(',').map(item => item.trim()).filter(Boolean).map(item => {
                        const parts = item.split(/\\s+/);
                        const descriptor = parts[1] || '0w';
                        const weight = parseFloat(descriptor) || 0;
                        return { url: parts[0] || '', weight };
                    }).filter(item => item.url);
                    entries.sort((a, b) => b.weight - a.weight);
                    return entries.length ? entries[0].url : '';
                };
                return Array.from(root.querySelectorAll('img[src], img[srcset]'))
                    .filter(belongsToRoot)
                    .map(image => {
                        const anchor = image.closest('a[href]');
                        return {
                            src: chooseLargestSrcset(image.getAttribute('srcset') || '') || image.currentSrc || image.src || '',
                            width: image.naturalWidth || image.width || 0,
                            height: image.naturalHeight || image.height || 0,
                            displayWidth: image.clientWidth || 0,
                            displayHeight: image.clientHeight || 0,
                            alt: image.alt || '',
                            anchorHref: anchor ? (anchor.href || anchor.getAttribute('href') || '') : '',
                            visualCompletion: image.getAttribute('data-visualcompletion') || '',
                        };
                    });
            }"""
        )  # Extract only images belonging to the current top-level post
    except Exception:  # Detached articles cannot provide reliable images
        return []  # Return no candidates

    candidates = []  # Initialize retained post-photo candidates
    seen_urls = set()  # Track duplicate responsive image URLs

    for info in raw_images or []:  # Inspect browser-returned image metadata
        src = str(info.get('src') or '').strip()  # Normalize resolved image URL
        width = int(info.get('width') or 0)  # Normalize intrinsic width
        height = int(info.get('height') or 0)  # Normalize intrinsic height
        display_width = int(info.get('displayWidth') or 0)  # Normalize rendered width
        display_height = int(info.get('displayHeight') or 0)  # Normalize rendered height
        alt = normalize_whitespace(str(info.get('alt') or ''))  # Normalize alternative text
        anchor_href = str(info.get('anchorHref') or '').strip()  # Read surrounding media link
        visual_completion = str(info.get('visualCompletion') or '').casefold()  # Read Facebook media marker
        anchor_lower = anchor_href.casefold()  # Normalize anchor URL for semantic filtering
        src_lower = src.casefold()  # Normalize image URL for filtering

        if not src.startswith(('http://', 'https://')):  # Ignore data/blob/UI-only image sources
            continue  # Continue to the next image
        if src in seen_urls:  # Ignore duplicate responsive references
            continue  # Continue to the next image
        if 'emoji.php' in src_lower or '/emoji/' in src_lower:  # Exclude Facebook emoji/reaction rendering
            continue  # Continue to the next image

        linked_as_photo = any(hint in anchor_lower for hint in PHOTO_LINK_HINTS)  # Detect a Facebook photo/media anchor
        explicit_media_image = visual_completion == 'media-vc-image'  # Detect Facebook's post/media-viewer image marker
        rendered_large_enough = max(display_width, display_height) >= 120  # Distinguish post media from tiny author avatars
        intrinsically_large = max(width, height) >= 240  # Reject small icons even if layout information is missing

        if not ((linked_as_photo or explicit_media_image) and (rendered_large_enough or intrinsically_large)):  # Keep semantic post photos only
            continue  # Ignore avatars, link icons, reactions, and unrelated images

        seen_urls.add(src)  # Mark post-photo source as retained
        candidates.append(
            {
                'type': 'photo',
                'url': src,
                'width': width,
                'height': height,
                'display_width': display_width,
                'display_height': display_height,
                'alt': alt,
                'photo_url': normalize_facebook_url(anchor_href) if anchor_href else None,
            }
        )  # Preserve post-photo candidate

    candidates.sort(key=lambda item: (int(item.get('width') or 0) * int(item.get('height') or 0)), reverse=True)  # Prefer larger resolved media first
    return candidates  # Return top-level post photos


def collect_video_element_candidates(article) -> list[dict]:
    """
    Collect direct HTTP(S) video URLs from top-level video elements in a Facebook post.

    :param article: Playwright locator representing a Facebook post.
    :return: List of direct video candidate dictionaries.
    """

    try:  # Inspect only video elements belonging to the current post rather than nested comments
        raw_videos = article.evaluate(
            """root => {
                const rootArticle = root.matches('div[role="article"]') ? root : null;
                const belongsToRoot = element => !rootArticle || element.closest('div[role="article"]') === rootArticle;
                return Array.from(root.querySelectorAll('video')).filter(belongsToRoot).map(video => ({
                    src: video.currentSrc || video.src || '',
                    poster: video.poster || '',
                    width: video.videoWidth || video.clientWidth || 0,
                    height: video.videoHeight || video.clientHeight || 0,
                }));
            }"""
        )  # Read direct top-level video sources
    except Exception:  # Detached article
        return []  # Return no candidates

    candidates = []  # Initialize direct video candidates
    seen_urls = set()  # Track normalized direct URLs

    for info in raw_videos or []:  # Inspect resolved video elements
        src = normalize_facebook_video_media_url(str(info.get('src') or '').strip())  # Remove Facebook byte-range query parameters
        if not src.startswith(('http://', 'https://')):  # Blob-backed players require network capture instead
            continue  # Continue to next video element
        if src in seen_urls:  # Avoid duplicate source entries
            continue  # Continue to next video element
        seen_urls.add(src)  # Mark normalized URL
        candidates.append(
            {
                'type': 'video',
                'url': src,
                'width': int(info.get('width') or 0),
                'height': int(info.get('height') or 0),
                'source': 'video_element',
            }
        )  # Preserve direct downloadable media

    return candidates  # Return direct top-level video sources


def capture_video_network_candidates(page: Page, article) -> list[dict]:
    """
    Capture Facebook CDN media requests for a top-level post video, including already-loaded resources.

    :param page: Facebook profile timeline page containing the post.
    :param article: Playwright locator representing the Facebook post.
    :return: Deduplicated video/audio resource candidates represented as downloadable media URLs.
    """

    photo_count, video_count = count_post_media_indicators(article)  # Determine whether this post actually contains video media
    if video_count <= 0:  # Do not capture unrelated autoplay/background traffic for non-video posts
        return []  # Return no video candidates

    captured = []  # Initialize captured media candidates
    seen_urls = set()  # Track normalized media URLs

    def add_candidate(raw_url: str, source: str, content_type: str = '') -> None:
        """Normalize and retain one likely Facebook CDN media URL."""

        url = normalize_facebook_video_media_url(str(raw_url or '').strip())  # Recover complete resource URL from range request
        lowered = url.casefold()  # Normalize URL for filtering
        normalized_content_type = str(content_type or '').casefold()  # Normalize response MIME type

        if not url.startswith(('http://', 'https://')):  # Ignore blob/data resources
            return  # Do not retain unsupported URL
        if not (
            normalized_content_type.startswith(('video/', 'audio/'))
            or ('.mp4' in lowered and ('fbcdn.net' in lowered or 'facebook.com' in lowered))
            or ('.webm' in lowered and 'fbcdn.net' in lowered)
        ):  # Keep only likely Facebook video/audio CDN resources
            return  # Ignore scripts/images/unrelated requests
        if url in seen_urls:  # Ignore duplicate byte-range variants after normalization
            return  # Candidate already retained

        seen_urls.add(url)  # Mark normalized media URL
        captured.append(
            {
                'type': 'video',
                'url': url,
                'source': source,
                'content_type': normalized_content_type or None,
            }
        )  # Preserve candidate for streaming download

    def collect_performance_entries(source: str) -> None:
        """Collect already-issued resource requests visible through the Performance API."""

        try:  # Performance entries recover media requests that started before the response listener was attached
            urls = page.evaluate(
                """() => performance.getEntriesByType('resource').map(entry => entry.name || '').filter(Boolean)"""
            )  # Read current resource URLs
            for url in urls or []:  # Inspect browser resource history
                add_candidate(str(url), source)  # Retain likely Facebook media URLs
        except Exception:  # Performance API failure should not abort post processing
            return  # Continue with response-listener candidates

    def handle_response(response: Response) -> None:
        """Collect media-like responses without reading their bodies."""

        try:  # Protect the Playwright event loop from transient response failures
            headers = response.headers  # Read response headers already available in Playwright
            add_candidate(
                response.url or '',
                'network_response',
                headers.get('content-type') or '',
            )  # Retain likely complete media URL after range normalization
        except Exception:  # Never allow one malformed response to terminate scraping
            return  # Ignore the response

    collect_performance_entries('performance_before_playback')  # Recover media that loaded before listener registration
    page.on('response', handle_response)  # Start collecting new media traffic

    try:  # Trigger lazy media loading for this specific top-level post
        article.scroll_into_view_if_needed(timeout=3_000)  # Bring post into viewport
        page.wait_for_timeout(ARTICLE_SETTLE_MS)  # Allow lazy media elements to mount

        videos = article.locator('video')  # Locate potential video players in the current post
        for index in range(min(videos.count(), 10)):  # Trigger a bounded number of post videos
            try:  # Ignore autoplay restrictions or detached elements
                videos.nth(index).evaluate(
                    """element => {
                        element.muted = true;
                        element.preload = 'auto';
                        const promise = element.play();
                        if (promise && promise.catch) promise.catch(() => {});
                    }"""
                )  # Start enough playback to resolve CDN media URLs
            except Exception:  # One blocked player should not prevent other candidates
                continue  # Continue to next video

        page.wait_for_timeout(VIDEO_NETWORK_CAPTURE_MS)  # Observe video/audio resource traffic
        collect_performance_entries('performance_after_playback')  # Recover all media URLs now present in browser resource history
    finally:  # Always unregister the response listener
        try:  # Protect cleanup if page was replaced/closed
            page.remove_listener('response', handle_response)  # Stop response collection
        except Exception:  # Listener may already be gone
            pass  # No action required

    return captured  # Return normalized Facebook media resources


def deduplicate_media_candidates(candidates: list[dict]) -> list[dict]:
    """
    Deduplicate media candidates while preserving their discovery order.

    :param candidates: Raw image/video candidate dictionaries.
    :return: Deduplicated media candidate list.
    """

    deduplicated = []  # Initialize result list
    seen = set()  # Track normalized URLs

    for candidate in candidates:  # Iterate raw candidates
        url = str(candidate.get("url") or "").strip()  # Normalize candidate URL
        media_type = str(candidate.get("type") or "").strip()  # Normalize media type
        if not url or not media_type:  # Reject incomplete candidates
            continue  # Continue to the next candidate

        key = (media_type, url)  # Build exact deduplication key
        if key in seen:  # Skip exact duplicates
            continue  # Continue to the next candidate

        seen.add(key)  # Mark candidate as retained
        deduplicated.append(candidate)  # Preserve candidate order

    return deduplicated  # Return unique candidates


def extension_from_response(content_type: str, url: str, media_type: str) -> str:
    """
    Resolve a useful media file extension from HTTP metadata and URL structure.

    :param content_type: Response Content-Type header.
    :param url: Media source URL.
    :param media_type: Logical media type ("photo" or "video").
    :return: File extension including the leading dot.
    """

    normalized_content_type = (content_type or "").split(";", 1)[0].strip().lower()  # Remove charset/codec parameters

    explicit_types = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/avif": ".avif",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "video/quicktime": ".mov",
        "video/x-matroska": ".mkv",
    }  # Stable MIME-to-extension mapping

    if normalized_content_type in explicit_types:  # Prefer explicit known MIME mappings
        return explicit_types[normalized_content_type]  # Return the mapped extension

    guessed = mimetypes.guess_extension(normalized_content_type) if normalized_content_type else None  # Ask Python for a MIME mapping
    if guessed:  # Verify a mapping exists
        return ".jpg" if guessed == ".jpe" else guessed  # Normalize the uncommon JPEG alias

    path_suffix = Path(urlparse(url).path).suffix.lower()  # Inspect the URL path suffix
    if re.fullmatch(r"\.[a-z0-9]{1,5}", path_suffix):  # Keep only plausible short extensions
        return path_suffix  # Return the URL-derived extension

    return ".jpg" if media_type == "photo" else ".mp4"  # Use a sensible media-type fallback


def build_authenticated_requests_session(context: BrowserContext, url: str) -> requests.Session:
    """
    Build an in-memory requests session using only cookies relevant to the target media URL.

    :param context: Authenticated Playwright browser context.
    :param url: Media URL that will be requested.
    :return: Configured requests session.
    """

    session = requests.Session()  # Create an isolated HTTP session used only for the current download

    try:  # Copy relevant cookies into memory without writing them to disk or logs
        cookies = context.cookies([url, FACEBOOK_BASE_URL])  # Read cookies applicable to Facebook and the media target
        for cookie in cookies:  # Transfer supported cookie attributes into requests
            try:  # Ignore cookies whose domain/path syntax requests cannot represent
                session.cookies.set(
                    cookie["name"],
                    cookie["value"],
                    domain=cookie.get("domain") or None,
                    path=cookie.get("path") or "/",
                )  # Preserve authentication only for this process memory
            except Exception:  # One unusual cookie must not prevent media download
                continue  # Continue copying remaining cookies
    except Exception:  # Signed CDN URLs often work even when no browser cookie is required
        pass  # Continue with an empty cookie jar

    return session  # Return the in-memory authenticated session


def download_media(context: BrowserContext, page: Page, candidate: dict, output_path_without_extension: Path, referer: str) -> tuple[Path | None, str]:
    """
    Download one Facebook media URL using authenticated streaming HTTP requests.

    Facebook video CDN requests may return HTTP 206 ranges. The downloader normalizes known
    bytestart/byteend URL parameters and, when the CDN still responds with Content-Range, requests
    the remaining byte ranges sequentially so a complete media resource is written instead of a
    corrupt fragment.

    :param context: Browser context containing the authenticated Facebook session.
    :param page: Browser page used to obtain the current browser User-Agent.
    :param candidate: Media candidate containing type and URL.
    :param output_path_without_extension: Destination path without extension.
    :param referer: Facebook post URL used as the HTTP Referer header.
    :return: Tuple containing saved path and an error string.
    """

    media_type = str(candidate.get('type') or '').strip()  # Resolve logical media type
    raw_url = str(candidate.get('url') or '').strip()  # Resolve candidate URL
    url = normalize_facebook_video_media_url(raw_url) if media_type == 'video' else raw_url  # Normalize ranged video URLs

    if not url.startswith(('http://', 'https://')):  # Verify direct HTTP(S) media can be requested
        return None, f'Unsupported media URL scheme: {url[:80]}'  # Report unsupported blob/data URLs explicitly

    temporary_path = output_path_without_extension.with_suffix('.download')  # Use temporary file until validation completes
    session = build_authenticated_requests_session(context, url)  # Build ephemeral authenticated streaming session

    try:  # Resolve same browser User-Agent when possible
        user_agent = str(page.evaluate('navigator.userAgent'))  # Read current browser User-Agent
    except Exception:  # Use browser-compatible fallback only when page is unavailable
        user_agent = 'Mozilla/5.0'  # Minimal fallback User-Agent

    base_headers = {
        'Referer': referer or PROFILE_URL,
        'User-Agent': user_agent,
        'Accept': '*/*',
        'Accept-Encoding': 'identity',
    }  # Build browser-like request headers without exposing credentials

    response = None  # Track current response for guaranteed cleanup

    try:  # Stream media without loading large videos entirely into memory
        response = session.get(
            url,
            headers=base_headers,
            stream=True,
            allow_redirects=True,
            timeout=(30, 120),
        )  # Open the initial media response

        if response.status_code not in (200, 206):  # Require a successful complete/ranged media response
            return None, f'HTTP {response.status_code} while downloading {url}'  # Report server failure

        content_type = (response.headers.get('content-type') or '').split(';', 1)[0].strip().casefold()  # Normalize MIME type

        if media_type == 'photo' and content_type and not content_type.startswith('image/'):  # Prevent HTML/error pages as photos
            return None, f"Unexpected photo Content-Type '{content_type}' for {url}"  # Report MIME mismatch
        if media_type == 'video' and content_type and not (
            content_type.startswith(('video/', 'audio/')) or content_type == 'application/octet-stream'
        ):  # Prevent HTML/error pages as media files
            return None, f"Unexpected video Content-Type '{content_type}' for {url}"  # Report MIME mismatch

        total_written = 0  # Track bytes persisted across complete/ranged requests
        expected_total = None  # Track total resource size when Content-Range supplies it
        next_start = 0  # Track next required byte for ranged downloads

        with temporary_path.open('wb') as file:  # Open destination once and append ranges sequentially
            while True:  # Continue until a 200 response finishes or all known ranges are reconstructed
                if response.status_code == 206:  # Parse ranged response metadata
                    parsed_range = parse_http_content_range(response.headers.get('content-range') or '')  # Parse current range
                    if parsed_range is None:  # Cannot safely reconstruct an unlabelled partial response
                        return None, f"Facebook returned HTTP 206 without a usable Content-Range for {url}"  # Avoid corrupt output
                    range_start, range_end, range_total = parsed_range  # Unpack byte-range metadata
                    if range_start != next_start:  # Require contiguous resource reconstruction from byte zero
                        if total_written == 0 and range_start != 0:  # Initial response may still reflect a stale CDN range
                            response.close()  # Release stale partial response
                            response = session.get(
                                url,
                                headers={**base_headers, 'Range': f'bytes=0-{VIDEO_RANGE_CHUNK_BYTES - 1}'},
                                stream=True,
                                allow_redirects=True,
                                timeout=(30, 120),
                            )  # Explicitly restart from byte zero
                            next_start = 0  # Reset expected position
                            if response.status_code not in (200, 206):  # Verify restart response
                                return None, f'HTTP {response.status_code} while restarting ranged media {url}'
                            continue  # Parse restarted response on the next iteration
                        return None, f'Non-contiguous Facebook media range {range_start}-{range_end}; expected {next_start}'  # Reject corrupt sequence
                    if range_total is not None:  # Preserve complete resource size when known
                        expected_total = range_total  # Store expected total bytes

                for chunk in response.iter_content(chunk_size=1024 * 1024):  # Stream one MiB chunks
                    if not chunk:  # Ignore keep-alive chunks
                        continue  # Continue streaming
                    total_written += len(chunk)  # Update persisted byte count
                    if total_written > MAX_MEDIA_FILE_SIZE_BYTES:  # Enforce configured safety ceiling
                        raise ValueError(f'Downloaded media exceeds {MAX_MEDIA_FILE_SIZE_BYTES} bytes.')  # Abort oversized transfer
                    file.write(chunk)  # Persist chunk immediately

                if response.status_code == 200:  # Complete non-ranged response finished
                    break  # Media resource is complete

                parsed_range = parse_http_content_range(response.headers.get('content-range') or '')  # Re-read completed range
                if parsed_range is None:  # Defensive validation
                    return None, f'Could not parse completed Facebook Content-Range for {url}'  # Reject ambiguous file
                _, range_end, range_total = parsed_range  # Read completed range end/total
                if range_total is not None:  # Preserve total resource size
                    expected_total = range_total  # Update expected total

                next_start = range_end + 1  # Continue immediately after completed byte range
                if expected_total is None or next_start >= expected_total:  # All known bytes have been written
                    break  # Ranged resource is complete

                response.close()  # Release completed range before requesting next one
                range_end_request = min(next_start + VIDEO_RANGE_CHUNK_BYTES - 1, expected_total - 1)  # Bound next chunk
                response = session.get(
                    url,
                    headers={**base_headers, 'Range': f'bytes={next_start}-{range_end_request}'},
                    stream=True,
                    allow_redirects=True,
                    timeout=(30, 120),
                )  # Fetch next contiguous range

                if response.status_code not in (200, 206):  # Verify continuation request
                    return None, f'HTTP {response.status_code} while continuing ranged media {url}'  # Report range failure

        if total_written == 0:  # Reject empty files
            return None, f'Downloaded media body was empty: {url}'  # Report invalid empty response
        if expected_total is not None and total_written != expected_total:  # Verify byte-perfect ranged reconstruction
            return None, f'Incomplete ranged media: wrote {total_written} of {expected_total} bytes for {url}'  # Reject partial file

        extension = extension_from_response(content_type, str(response.url or url) if response is not None else url, media_type)  # Resolve extension
        output_path = output_path_without_extension.with_suffix(extension)  # Build final media path
        os.replace(temporary_path, output_path)  # Atomically promote completed media file
        return output_path, ''  # Return successful output path
    except Exception as error:  # Capture network/filesystem failures per media item
        return None, str(error)  # Return error for JSON reporting
    finally:  # Always clean temporary resources
        try:  # Close current HTTP response
            if response is not None:
                response.close()  # Release connection
        except Exception:  # Ignore cleanup failure
            pass  # No action required
        try:  # Remove incomplete temporary downloads
            if temporary_path.exists():
                temporary_path.unlink()  # Delete partial file
        except Exception:  # Cleanup failure should not hide original result
            pass  # No action required
        session.close()  # Release HTTP connections and in-memory cookies


def choose_post_output_directory(post_date: datetime.datetime, title: str, post_id: str) -> Path:
    """
    Choose a unique output directory while preserving the "{YYYY-MM-DD}-{Title}" format.

    :param post_date: Parsed Facebook post date.
    :param title: Sanitized post title.
    :param post_id: Stable post identifier used only to distinguish collisions.
    :return: Directory path reserved for the post.
    """

    date_prefix = post_date.strftime("%Y-%m-%d")  # Format the date exactly as requested
    base_title = sanitize_filename_component(title, fallback=f"Post {post_id}" if post_id else "Post")  # Normalize title
    candidate = OUTPUT_DIR / f"{date_prefix}-{base_title}"  # Build requested directory structure

    if not candidate.exists():  # Prefer the exact requested directory name
        return candidate  # Return unused path

    metadata_path = candidate / POST_METADATA_FILENAME  # Inspect an existing directory before changing its name
    try:  # Determine whether the directory already belongs to this same post
        if metadata_path.exists():  # Verify metadata exists
            with metadata_path.open("r", encoding="utf-8") as file:  # Open existing metadata
                metadata = json.load(file)  # Parse metadata
            existing_id = str(metadata.get("post_id") or "")  # Read existing identifier
            if post_id and existing_id == post_id:  # Verify this is the same post
                return candidate  # Reuse the original directory
    except Exception:  # Fall through to collision-safe naming
        pass  # No action required

    suffix = sanitize_filename_component(post_id or "Duplicate", fallback="Duplicate", max_length=24)  # Build collision discriminator
    collision_title = sanitize_filename_component(f"{base_title} {suffix}", fallback=f"Post {suffix}")  # Keep suffix inside the Title portion
    return OUTPUT_DIR / f"{date_prefix}-{collision_title}"  # Preserve YYYY-MM-DD-Title naming convention


def write_post_metadata(post_dir: Path, metadata: dict) -> None:
    """
    Write post metadata as UTF-8 formatted JSON.

    :param post_dir: Post output directory.
    :param metadata: Metadata dictionary to serialize.
    :return: None
    """

    metadata_path = post_dir / POST_METADATA_FILENAME  # Resolve destination metadata path
    temporary_path = post_dir / f".{POST_METADATA_FILENAME}.tmp"  # Build temporary file for replacement

    with temporary_path.open("w", encoding="utf-8", newline="\n") as file:  # Write temporary metadata first
        json.dump(metadata, file, ensure_ascii=False, indent=4)  # Serialize human-readable JSON
        file.write("\n")  # End the file with a newline

    os.replace(temporary_path, metadata_path)  # Atomically replace the final metadata file


def resolve_post_date_from_permalink(context: BrowserContext, post_url: str) -> tuple[datetime.datetime | None, str]:
    """
    Resolve a post date from its dedicated permalink page when the timeline card does not expose enough date information.

    :param context: Authenticated browser context.
    :param post_url: Facebook permalink to inspect.
    :return: Parsed datetime and raw date label.
    """

    if not post_url:  # Verify a permalink exists
        return None, ""  # No fallback navigation can be performed

    details_page = None  # Initialize detail page for guaranteed cleanup

    try:  # Open a separate page so the scrolling timeline remains untouched
        details_page = context.new_page()  # Create a temporary authenticated page
        details_page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT_MS)  # Configure navigation timeout
        details_page.goto(post_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)  # Open the post permalink
        details_page.wait_for_timeout(1_500)  # Allow Facebook client rendering to complete

        articles = get_article_locator(details_page)  # Locate the post on its dedicated page
        if articles.count() == 0:  # Verify a post container is available
            return None, ""  # No date-bearing post container could be found

        return resolve_post_date(articles.first)  # Parse date from the dedicated post view
    except Exception as error:  # Permalink fallback is best-effort and must not terminate timeline scrolling
        verbose_output(
            true_string=f"{BackgroundColors.YELLOW}Permalink date fallback failed for "
            f"{BackgroundColors.CYAN}{post_url}{BackgroundColors.YELLOW}: "
            f"{BackgroundColors.CYAN}{error}{Style.RESET_ALL}"
        )  # Log diagnostic details only in verbose mode
        return None, ""  # Report unresolved date
    finally:  # Always close the temporary details page
        if details_page is not None:  # Verify the page was created
            try:  # Protect cleanup if navigation crashed the page
                details_page.close()  # Close only the temporary details page
            except Exception:  # Ignore cleanup failure
                pass  # No further action required


def process_article(page: Page, context: BrowserContext, article, known_keys: set[str]) -> tuple[bool, str]:
    """
    Extract and download one top-level profile-owner Facebook post.

    :param page: Facebook profile timeline page.
    :param context: Authenticated browser context.
    :param article: Playwright locator representing the candidate post.
    :param known_keys: Cross-run and current-run deduplication keys.
    :return: Tuple containing whether a post metadata file was written and its primary key.
    """

    try:  # Bring post into view so lazy text/media resolve before extraction
        article.scroll_into_view_if_needed(timeout=3_000)  # Ensure current post is mounted/visible
        page.wait_for_timeout(ARTICLE_SETTLE_MS)  # Allow lazy media to settle
    except Exception:  # Detached article will be retried naturally during later incremental scrolling
        return False, ''  # Report no processed post

    post_url = extract_post_permalink(article)  # Resolve canonical top-level post permalink
    if not post_url:  # Reject comments/UI cards lacking canonical post identity
        return False, ''  # Only canonical post cards are archived
    if not is_profile_owner_post_article(article, post_url):  # Reject other people's timeline posts and nested comments
        return False, ''  # Skip non-owner content

    post_id = extract_post_id(post_url)  # Extract stable numeric/pfbid identifier when available
    content = extract_post_content(article)  # Extract post body from the validated top-level article
    post_date, date_raw = resolve_post_date(article)  # Resolve timestamp from canonical post-link metadata

    if post_date is None and post_url:  # Use dedicated permalink page only when top-level timestamp cannot be parsed
        post_date, date_raw = resolve_post_date_from_permalink(context, post_url)  # Retry exact post page timestamp extraction

    if not post_id:  # Build deterministic key only for uncommon canonical URLs without recoverable identifier
        post_id = build_fallback_post_key(post_url, content, date_raw)  # Generate fallback identifier

    post_keys = build_post_keys(post_id, post_url)  # Build deduplication keys
    if post_keys and post_keys.intersection(known_keys):  # Skip complete current-schema posts already archived
        return False, next(iter(post_keys))  # Return one key for diagnostics

    if post_date is None:  # Never invent a date-based directory
        print(
            f"{BackgroundColors.YELLOW}Skipping canonical post because its date could not be resolved safely: "
            f"{BackgroundColors.CYAN}{post_url or post_id}{Style.RESET_ALL}"
        )  # Log explicit timestamp-resolution failure
        return False, f'id:{post_id}'  # Keep post retryable

    expected_photo_count, expected_video_count = count_post_media_indicators(article)  # Detect whether the post visibly contains media
    title = derive_post_title(content, post_id)  # Derive requested directory title
    post_dir = choose_post_output_directory(post_date, title, post_id)  # Resolve collision-safe output path
    post_dir.mkdir(parents=True, exist_ok=True)  # Create post directory before downloads

    image_candidates = collect_image_candidates(article)  # Collect semantic top-level post photos
    direct_video_candidates = collect_video_element_candidates(article)  # Collect directly exposed video URLs
    network_video_candidates = capture_video_network_candidates(page, article)  # Recover blob/ranged Facebook CDN video resources
    media_candidates = deduplicate_media_candidates(
        image_candidates + direct_video_candidates + network_video_candidates
    )  # Merge and deduplicate media sources

    print(
        f"{BackgroundColors.GREEN}Post media: photos detected {BackgroundColors.CYAN}{expected_photo_count}"
        f"{BackgroundColors.GREEN}, photo candidates {BackgroundColors.CYAN}{len(image_candidates)}"
        f"{BackgroundColors.GREEN}, videos detected {BackgroundColors.CYAN}{expected_video_count}"
        f"{BackgroundColors.GREEN}, video candidates {BackgroundColors.CYAN}{len(direct_video_candidates) + len(network_video_candidates)}"
        f"{Style.RESET_ALL}"
    )  # Expose media extraction health instead of silently writing JSON-only outputs

    media_results = []  # Initialize downloaded media metadata
    counters = {'photo': 0, 'video': 0}  # Track deterministic filenames by media type

    for candidate in media_candidates:  # Download each discovered media source
        media_type = str(candidate.get('type') or '')  # Read logical media type
        if media_type not in counters:  # Ignore unexpected media categories
            continue  # Continue to next candidate

        counters[media_type] += 1  # Allocate deterministic media number
        filename_prefix = 'photo' if media_type == 'photo' else 'video'  # Resolve filename prefix
        output_without_extension = post_dir / f'{filename_prefix}_{counters[media_type]:03d}'  # Build destination stem

        saved_path, error = download_media(
            context,
            page,
            candidate,
            output_without_extension,
            post_url or PROFILE_URL,
        )  # Stream media using in-memory authentication from browser context

        media_result = {
            'type': media_type,
            'source_url': candidate.get('url', ''),
            'source': candidate.get('source'),
            'filename': saved_path.name if saved_path else None,
            'downloaded': saved_path is not None,
            'error': error or None,
        }  # Build transparent per-media result

        for key in ('width', 'height', 'display_width', 'display_height', 'alt', 'photo_url', 'content_type'):  # Preserve optional diagnostics
            if candidate.get(key) is not None and candidate.get(key) != '':
                media_result[key] = candidate.get(key)  # Store available candidate metadata

        media_results.append(media_result)  # Preserve download outcome

        if saved_path:  # Log successful media download
            print(
                f"{BackgroundColors.GREEN}Downloaded {media_type}: "
                f"{BackgroundColors.CYAN}{saved_path.relative_to(PROJECT_DIR).as_posix()}{Style.RESET_ALL}"
            )  # Output saved path
        else:  # Log media failure without aborting unrelated posts
            print(
                f"{BackgroundColors.YELLOW}Failed {media_type}: "
                f"{BackgroundColors.CYAN}{format_url_for_log(str(candidate.get('url') or ''))}"
                f"{BackgroundColors.YELLOW} ({error}){Style.RESET_ALL}"
            )  # Output sanitized failure reason

    downloaded_photos = sum(1 for item in media_results if item.get('downloaded') and item.get('type') == 'photo')  # Count successful photos
    downloaded_videos = sum(1 for item in media_results if item.get('downloaded') and item.get('type') == 'video')  # Count successful video resources
    photo_complete = expected_photo_count <= 0 or downloaded_photos > 0  # Require at least one photo if photo media is visibly present
    video_complete = expected_video_count <= 0 or downloaded_videos > 0  # Require at least one video resource if video media is visibly present
    complete = photo_complete and video_complete  # Mark post complete only when visibly-required media was archived

    metadata = {
        'scrape_schema_version': SCRAPE_SCHEMA_VERSION,
        'complete': complete,
        'post_id': post_id,
        'post_url': post_url or None,
        'profile_url': PROFILE_URL,
        'date': post_date.date().isoformat(),
        'datetime': post_date.isoformat(),
        'date_raw': date_raw or None,
        'title': title,
        'content': content,
        'output_directory': post_dir.relative_to(PROJECT_DIR).as_posix(),
        'expected_photo_indicators': expected_photo_count,
        'expected_video_indicators': expected_video_count,
        'photo_candidate_count': len(image_candidates),
        'video_candidate_count': len(direct_video_candidates) + len(network_video_candidates),
        'media_count': len(media_results),
        'downloaded_media_count': sum(1 for item in media_results if item.get('downloaded')),
        'failed_media_count': sum(1 for item in media_results if not item.get('downloaded')),
        'media': media_results,
        'scraped_at': datetime.datetime.now().astimezone().isoformat(),
    }  # Build current-schema per-post metadata

    write_post_metadata(post_dir, metadata)  # Persist metadata after all media attempts

    if complete:  # Only complete posts may be skipped on future runs
        known_keys.update(post_keys)  # Mark post completed after media requirements are satisfied
        print(
            f"{BackgroundColors.GREEN}Saved complete post: "
            f"{BackgroundColors.CYAN}{post_dir.relative_to(PROJECT_DIR).as_posix()}{Style.RESET_ALL}"
        )  # Log completed post
    else:  # Keep incomplete post retryable
        print(
            f"{BackgroundColors.YELLOW}Saved incomplete post metadata; media will be retried on later passes/runs: "
            f"{BackgroundColors.CYAN}{post_dir.relative_to(PROJECT_DIR).as_posix()}{Style.RESET_ALL}"
        )  # Explain why this post was not added to known keys

    return True, f'id:{post_id}'  # Report processed post metadata


def scroll_profile_and_download(page: Page, context: BrowserContext) -> dict:
    """
    Incrementally scroll the profile root timeline and archive every newly discovered owner post.

    The stop condition is based on newly discovered canonical post URLs, not newly saved outputs.
    This is critical for resumable runs: already-downloaded posts can occupy many consecutive screens
    before the scraper reaches an older post that still needs processing.

    :param page: Authenticated profile root timeline page.
    :param context: Authenticated browser context.
    :return: Execution statistics.
    """

    page = ensure_scraping_profile_ready(page, context)  # Refuse to start against challenged session
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # Ensure output root exists
    known_keys = load_existing_post_keys()  # Load only complete current-schema posts

    try:  # Always start newest-first regardless of persisted browser history
        page.evaluate('window.scrollTo(0, 0)')  # Reset feed to newest position
        page.wait_for_timeout(1_000)  # Allow top batch to settle
    except Exception:  # Fresh navigation should already be near top
        pass  # Continue safely

    processed_posts = 0  # Count metadata files written during this browser session
    discovered_post_urls = set()  # Track canonical profile post URLs seen while scrolling
    no_new_discovery_scrolls = 0  # Track consecutive scrolls without new canonical URLs
    previous_scroll_y = -1  # Track actual viewport movement for end-of-feed detection

    print(
        f"{BackgroundColors.GREEN}Previously completed current-schema post keys: "
        f"{BackgroundColors.CYAN}{len(known_keys)}{Style.RESET_ALL}"
    )  # Log resume state

    for scroll_iteration in range(1, MAX_SCROLL_ITERATIONS + 1):  # Scroll until feed discovery stabilizes
        page = ensure_scraping_profile_ready(page, context)  # Revalidate authentication before touching DOM
        articles = get_article_locator(page)  # Resolve mounted timeline articles
        current_count = articles.count()  # Count currently mounted article-like containers
        new_discovered_this_iteration = 0  # Count new canonical owner-post URLs in this viewport batch
        processed_this_iteration = 0  # Count posts whose metadata was written in this pass

        for index in range(current_count):  # Process mounted posts before Facebook virtualizes them away
            try:  # Isolate individual post-card failures
                article = articles.nth(index)  # Resolve current article locator
                post_url = extract_post_permalink(article)  # Resolve strict canonical post identity
                if not post_url:  # Ignore comments/UI cards without canonical post permalink
                    continue  # Continue to next article
                if not is_profile_owner_post_article(article, post_url):  # Ignore other authors and nested comments
                    continue  # Continue to next article

                normalized_post_url = normalize_facebook_url(post_url)  # Normalize canonical discovery key
                if normalized_post_url in discovered_post_urls:  # Process each canonical post only once per browser session
                    continue  # Continue to next article

                discovered_post_urls.add(normalized_post_url)  # Mark newly discovered canonical post
                new_discovered_this_iteration += 1  # Reset end-of-feed confidence for genuine new URL

                processed, _ = process_article(page, context, article, known_keys)  # Extract post and media when not already complete
                if processed:  # Metadata was written or refreshed
                    processed_posts += 1  # Increment session total
                    processed_this_iteration += 1  # Increment pass total
            except FacebookAuthenticationRequiredError:  # Never swallow manual verification requirement
                raise  # Let browser lifecycle reopen visible authentication
            except Exception as error:  # One malformed post must not terminate full export
                try:  # Distinguish parsing failure from authentication interruption
                    page = ensure_scraping_profile_ready(page, context)  # Revalidate session
                except FacebookAuthenticationRequiredError:
                    raise  # Recover interactively instead of producing misleading failures

                print(
                    f"{BackgroundColors.YELLOW}Post extraction failed at mounted index "
                    f"{BackgroundColors.CYAN}{index}{BackgroundColors.YELLOW}: "
                    f"{BackgroundColors.CYAN}{error}{Style.RESET_ALL}"
                )  # Log genuine post-level failure

        if new_discovered_this_iteration > 0:  # New canonical URLs mean the feed is still advancing
            no_new_discovery_scrolls = 0  # Reset stability streak
        else:  # No new canonical owner post appeared in this viewport batch
            no_new_discovery_scrolls += 1  # Increase end-of-feed confidence

        try:  # Read scroll position and document geometry before next movement
            scroll_state = page.evaluate(
                """() => ({
                    y: window.scrollY || window.pageYOffset || 0,
                    height: document.documentElement.scrollHeight || document.body.scrollHeight || 0,
                    viewport: window.innerHeight || 0,
                })"""
            )  # Capture current feed geometry
            current_scroll_y = int(scroll_state.get('y') or 0)  # Normalize vertical position
            current_height = int(scroll_state.get('height') or 0)  # Normalize document height
            viewport_height = int(scroll_state.get('viewport') or 0)  # Normalize viewport height
            at_bottom = current_scroll_y + viewport_height >= max(0, current_height - 100)  # Detect current bottom threshold
        except Exception as error:  # Determine whether geometry failure is authentication-related
            page = ensure_scraping_profile_ready(page, context)  # Raise if challenge replaced feed
            verbose_output(true_string=f"{BackgroundColors.YELLOW}Could not read timeline geometry: {BackgroundColors.CYAN}{error}{Style.RESET_ALL}")
            current_scroll_y = previous_scroll_y  # Preserve previous position
            at_bottom = False  # Continue attempting incremental scrolling

        print(
            f"{BackgroundColors.GREEN}Timeline pass {BackgroundColors.CYAN}{scroll_iteration}"
            f"{BackgroundColors.GREEN}: mounted {BackgroundColors.CYAN}{current_count}"
            f"{BackgroundColors.GREEN}, new canonical posts {BackgroundColors.CYAN}{new_discovered_this_iteration}"
            f"{BackgroundColors.GREEN}, processed {BackgroundColors.CYAN}{processed_this_iteration}"
            f"{BackgroundColors.GREEN}, total discovered {BackgroundColors.CYAN}{len(discovered_post_urls)}"
            f"{BackgroundColors.GREEN}, no-new streak {BackgroundColors.CYAN}{no_new_discovery_scrolls}/{NO_NEW_POST_SCROLL_LIMIT}"
            f"{Style.RESET_ALL}"
        )  # Provide discovery-oriented progress

        if no_new_discovery_scrolls >= NO_NEW_POST_SCROLL_LIMIT and (at_bottom or current_scroll_y == previous_scroll_y):  # Confirm stable discovery and no movement
            print(f"{BackgroundColors.GREEN}Timeline end/stability condition reached.{Style.RESET_ALL}")  # Log stop reason
            break  # Stop scrolling

        previous_scroll_y = current_scroll_y  # Preserve current position before incremental movement
        page = ensure_scraping_profile_ready(page, context)  # Revalidate immediately before next lazy-load scroll

        try:  # Scroll incrementally instead of jumping to document bottom
            page.evaluate(f'window.scrollBy(0, {SCROLL_STEP_PX})')  # Advance approximately one post/screen batch
            page.wait_for_timeout(int(SCROLL_PAUSE_SECONDS * 1000))  # Allow virtualized posts to mount
        except PlaywrightTimeoutError:  # Timeout should not immediately abort long export
            page = ensure_scraping_profile_ready(page, context)  # Raise if auth challenge appeared
            time.sleep(SCROLL_PAUSE_SECONDS)  # Pause before next extraction attempt
        except Exception as error:  # Surface genuine scroll failures
            page = ensure_scraping_profile_ready(page, context)  # Raise instead if auth-related
            print(
                f"{BackgroundColors.YELLOW}Timeline scroll failed: "
                f"{BackgroundColors.CYAN}{error}{Style.RESET_ALL}"
            )  # Log non-authentication scroll failure
            time.sleep(SCROLL_PAUSE_SECONDS)  # Allow page to recover

    return {
        'saved_posts': processed_posts,
        'known_post_keys': len(known_keys),
        'encountered_post_keys': len(discovered_post_urls),
    }  # Return session statistics


def close_browser_session(session: BrowserSession) -> None:
    """
    Close the persistent browser context owned by the downloader.

    :param session: BrowserSession returned by launch_browser_session.
    :return: None
    """

    try:  # Close the persistent context launched by this script
        session.context.close()  # Flush profile state and close the automation browser
    except Exception as error:  # Browser may already have been closed manually
        verbose_output(
            true_string=f"{BackgroundColors.YELLOW}Browser context close warning: {BackgroundColors.CYAN}{error}{Style.RESET_ALL}"
        )  # Log non-fatal cleanup warning


def main():
    """
    Main function.

    :param: None
    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the "
        f"{BackgroundColors.CYAN}Facebook Posts Downloader{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the welcome message

    start_time = datetime.datetime.now()  # Get the start time of the program
    session = None  # Initialize browser session for safe cleanup
    initial_completed_posts = count_completed_post_outputs()  # Snapshot completed outputs before any new scraping work starts
    final_statistics = None  # Store statistics from the browser session that reaches the end of the timeline
    force_interactive_authentication = False  # Normal startup first tries the saved profile headlessly

    try:  # Execute the complete Facebook export workflow
        with sync_playwright() as playwright:  # Start Playwright runtime
            while True:  # Re-establish authentication automatically if Facebook challenges a long-running headless scrape
                session = establish_authenticated_scraping_session(
                    playwright,
                    force_interactive_authentication=force_interactive_authentication,
                )  # Obtain a profile page that is ready for visible or headless scraping

                try:  # Run until the timeline completes or Facebook requires another interactive verification
                    statistics = scroll_profile_and_download(session.page, session.context)  # Download discovered posts
                    final_statistics = statistics  # Retain final known/encountered counts for summary output
                    break  # The timeline completed without another authentication interruption
                except FacebookAuthenticationRequiredError:
                    print(
                        f"{BackgroundColors.YELLOW}Facebook requested authentication during headless scraping. "
                        f"{BackgroundColors.GREEN}Completed posts are already saved; reopening interactive authentication.{Style.RESET_ALL}"
                    )  # Explain the automatic resume behavior

                    close_browser_session(session)  # Release the persistent profile before reopening it visibly
                    session = None  # Prevent duplicate cleanup
                    time.sleep(BROWSER_RELAUNCH_DELAY_SECONDS)  # Allow the persistent profile lock to be released
                    force_interactive_authentication = True  # Skip the next headless probe and go directly to visible verification
                    continue  # Authenticate visibly, return headless, and resume from existing post.json files

            if final_statistics is None:  # Defensive guard: the loop should only exit after receiving final statistics
                raise RuntimeError("Facebook scraping ended without final execution statistics.")  # Surface impossible lifecycle state

            saved_posts_this_run = max(
                0,
                count_completed_post_outputs() - initial_completed_posts,
            )  # Count outputs created across every headless/interactive recovery cycle in this execution

            print(
                f"\n{BackgroundColors.GREEN}Saved posts this run: "
                f"{BackgroundColors.CYAN}{saved_posts_this_run}\n"
                f"{BackgroundColors.GREEN}Known post keys after run: "
                f"{BackgroundColors.CYAN}{final_statistics['known_post_keys']}{Style.RESET_ALL}"
            )  # Output aggregate export statistics across authentication/relaunch cycles

            close_browser_session(session)  # Close the final persistent automation browser
            session = None  # Prevent duplicate cleanup after successful close
    finally:  # Ensure locally launched browser resources are closed after errors
        if session is not None:  # Verify a session still needs cleanup
            close_browser_session(session)  # Close the persistent automation browser safely

    finish_time = datetime.datetime.now()  # Get the finish time of the program

    print(
        f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n"
        f"{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n"
        f"{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"
    )  # Output the start and finish times

    print(
        f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
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
