"""
================================================================================
Facebook Posts Downloader
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-20
Description :
    Downloads posts published on a configured Facebook profile by using an
    authenticated Chromium-based browser session controlled through Playwright.

    Each discovered post is stored inside ./Outputs/{ProfileUsername}/ using the
    "{Index}. {YYYY-MM-DD}-{Title}" directory naming convention, indexed oldest-to-newest. The post directory
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
       profile is relaunched headlessly before PROFILE_URL is scraped into ./Outputs/{ProfileUsername}/.

Outputs:
    - ./Outputs/{ProfileUsername}/{Index}. {YYYY-MM-DD}-{Title}/post.json
    - ./Outputs/{ProfileUsername}/{Index}. {YYYY-MM-DD}-{Title}/photo_001.<ext>
    - ./Outputs/{ProfileUsername}/{Index}. {YYYY-MM-DD}-{Title}/video_001.<ext>
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
import html  # For decoding HTML-escaped Facebook media URLs
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
PROFILE_DISPLAY_NAME = "Breno Farias da Silva"  # Preferred current Facebook display name used when deriving titles
PROFILE_AUTHOR_NAMES = ("Breno Farias da Silva", "Breno Farias")  # Accepted owner names for top-level post validation
ONLY_PROFILE_OWNER_POSTS = True  # Ignore comments and posts authored by other people on the profile timeline
FACEBOOK_BASE_URL = "https://www.facebook.com/"  # Base URL used to resolve relative Facebook links
BROWSER_CHANNEL = "chrome"  # Prefer the locally installed stable Google Chrome browser
HEADLESS_AFTER_AUTHENTICATION = True  # Keep scraping invisible after any required manual Facebook authentication
AUTOMATION_PROFILE_DIR = PROJECT_DIR / ".browser_profile"  # Dedicated persistent profile used by Playwright
PROFILE_USERNAME = (urlparse(PROFILE_URL).path.strip("/").split("/", 1)[0]).strip()  # Extract the profile username from PROFILE_URL after the Facebook base URL
if not PROFILE_USERNAME:  # Refuse ambiguous output placement when PROFILE_URL has no profile path
    raise ValueError(f"PROFILE_URL does not contain a Facebook profile username: {PROFILE_URL}")  # Fail before writing data into an incorrect output folder
OUTPUT_ROOT_DIR = PROJECT_DIR / "Outputs"  # Shared output root containing one intermediate directory per configured Facebook profile
OUTPUT_DIR = OUTPUT_ROOT_DIR / PROFILE_USERNAME  # Profile-specific output directory containing this profile's indexed post subdirectories
LEGACY_OUTPUT_DIR = PROJECT_DIR / "Outputs Legacy" / PROFILE_USERNAME  # Profile-specific quarantine for outputs produced by obsolete/broken scrape schemas

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
MEDIA_PERMALINK_SETTLE_MS = 1_500  # Delay after opening a photo/video permalink so viewer media can resolve
POST_TIMESTAMP_HOVER_SETTLE_MS = 450  # Delay after hovering a post timestamp so Facebook can render its absolute-time tooltip
MAX_MEDIA_PER_POST = 500  # Safety ceiling for distinct photos/videos resolved from one post
MAX_POST_PROCESS_RETRIES_PER_SESSION = 3  # Maximum retries for a mounted post that detaches or remains incomplete

# Output Constants:
POST_METADATA_FILENAME = "post.json"  # Metadata file written inside every post directory
POST_DIRECTORY_INDEX_MIN_WIDTH = 2  # Minimum zero-padded width used by oldest-to-newest post directory indexes
POST_DIRECTORY_INDEX_PATTERN = re.compile(r"^\d+\.\s+")  # Existing post-directory index prefix removed before canonical reindexing
SCRAPE_SCHEMA_VERSION = 5  # Metadata schema version; older timestamp/comment/media extraction outputs are intentionally reprocessed
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
    "reply_comment_id",
    "reply_comment_token",
    "notif_id",
    "notif_t",
    "ref",
    "refid",
    "mibextid",
}  # Tracking/comment-context parameters removed from normalized Facebook permalinks

COMMENT_CONTEXT_QUERY_PARAMETERS = {
    "comment_id",
    "reply_comment_id",
    "reply_comment_token",
}  # Query parameters proving that a Facebook URL addresses a comment/reply context rather than the top-level post

POST_URL_PATTERNS = (
    re.compile(r"/posts/(pfbid[A-Za-z0-9]+|\d+)", re.IGNORECASE),
    re.compile(r"[?&]story_fbid=(pfbid[A-Za-z0-9]+|\d+)", re.IGNORECASE),
    re.compile(r"[?&]fbid=(pfbid[A-Za-z0-9]+|\d+)", re.IGNORECASE),
    re.compile(r"/(?:videos|reel)/(pfbid[A-Za-z0-9]+|\d+)", re.IGNORECASE),
    re.compile(r"/share/(?:p|v|r)/([A-Za-z0-9_-]+)", re.IGNORECASE),
    re.compile(r"[?&]v=([A-Za-z0-9_-]+)", re.IGNORECASE),
)  # Patterns used to recover stable identifiers from modern and legacy Facebook post permalinks

POST_LINK_HINTS = (
    "/posts/",
    "/permalink.php",
    "/permalink/",
    "/story.php",
    "story_fbid=",
    "/share/p/",
    "/share/v/",
    "/share/r/",
    "/photo/",
    "/photos/",
    "/photo.php",
    "/videos/",
    "/watch/",
    "/reel/",
    "/people/",
    "?v=",
    "&v=",
)  # Known personal-profile/post/media routes used as secondary permalink/timestamp-link signals

PHOTO_LINK_HINTS = (
    "/photo/",
    "/photos/",
    "/photo.php",
)  # URL fragments that identify Facebook post-photo links

VIDEO_LINK_HINTS = (
    "/videos/",
    "/reel/",
    "/watch/",
    "/share/v/",
    "/share/r/",
)  # URL fragments that identify Facebook video/reel links inside a post

VIDEO_RANGE_QUERY_PARAMETERS = {
    "bytestart",
    "byteend",
}  # Facebook CDN range query parameters removed only when requesting a complete video resource

MESSAGE_SELECTORS = (
    'div[data-ad-rendering-role="story_message"]',
    '[data-ad-preview="message"]',
    '[data-ad-comet-preview="message"]',
    'div[dir="auto"]',
)  # Current/fallback selectors used in order to recover the textual body of each root post

ARTICLE_SELECTORS = (
    'div[role="main"] div[role="article"]',
    'div[role="feed"] div[role="article"]',
    'div[data-pagelet^="FeedUnit_"]',
    'div[data-pagelet*="FeedUnit"]',
    'div[role="feed"] > div',
)  # Current/fallback selectors used to locate mounted profile-feed post containers

PROFILE_FEED_CONTAINER_SELECTORS = (
    'div[role="feed"]',
    'div[data-pagelet*="ProfileTimeline"]',
    'div[data-pagelet*="Timeline"]',
    'div[data-pagelet*="Feed"]',
)  # Structural selectors proving that the actual profile timeline/feed rendered

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


def url_has_comment_context(url: str) -> bool:
    """
    Determine whether a Facebook URL explicitly addresses a comment or reply context.

    :param url: Facebook URL to inspect before tracking parameters are removed.
    :return: True when a comment/reply query parameter is present.
    """

    try:  # Parse query parameters without normalizing away comment context first
        query_keys = {key.casefold() for key, _ in parse_qsl(urlparse(str(url or '')).query, keep_blank_values=True)}  # Read query keys
    except Exception:  # Malformed URLs are not trusted as top-level post permalinks
        return True  # Reject the ambiguous candidate

    return bool(query_keys.intersection(COMMENT_CONTEXT_QUERY_PARAMETERS))  # Report explicit comment/reply context


def is_top_level_timeline_article(article) -> bool:
    """
    Determine whether a locator is a top-level timeline article instead of a nested comment/reply article.

    :param article: Playwright locator representing a Facebook article-like container.
    :return: True only when the candidate is not nested inside another role=article container.
    """

    try:  # Ask the browser to inspect ancestry because Facebook nests comments as role=article elements
        return bool(
            article.evaluate(
                """root => {
                    if (root.matches('[role="article"]')) {
                        const parent = root.parentElement;
                        return !parent || !parent.closest('[role="article"]');
                    }
                    return !root.closest('[role="article"]');
                }"""
            )
        )  # Reject comment/reply articles nested inside the actual post
    except Exception:  # Detached/ambiguous nodes cannot safely be treated as posts
        return False  # Reject the candidate


def collect_timestamp_link_candidates(article) -> list[dict]:
    """
    Collect likely root-post timestamp links from current and legacy Facebook post headers.

    :param article: Playwright locator representing a top-level Facebook post.
    :return: Timestamp-link dictionaries sorted strongest-first.
    """

    if not is_top_level_timeline_article(article):  # Timestamp identity must come from a root post only
        return []  # Reject nested comments/replies

    try:  # Evaluate ancestry/time semantics in the live DOM before Facebook virtualizes the post
        raw_candidates = article.evaluate(
            """root => {
                const rootArticle = root.matches('[role="article"]') ? root : root.querySelector('[role="article"]') || root;
                const belongsToRoot = element => {
                    const closestArticle = element.closest('[role="article"]');
                    return !closestArticle || closestArticle === rootArticle;
                };
                const compactTime = /(?:^|\\s)\\d+\\s*(?:s|m|min|mins|h|hr|hrs|d|w|wk|sem|a|y)(?:\\b|\\s|·|•|$)/i;
                const timeWords = /ago|just now|yesterday|today|ontem|hoje|agora mesmo|atrás|atras|há\\s|ha\\s|minute|minutes|minuto|minutos|hora|horas|day|days|dia|dias|week|weeks|semana|semanas|month|months|mês|meses|year|years|ano|anos|janeiro|fevereiro|março|marco|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro|january|february|march|april|may|june|july|august|september|october|november|december/i;
                const postReference = /\\/posts\\/|\\/videos\\/|\\/watch|\\/permalink(?:\\.php|\\/)|\\/story\\.php|\\/reel\\/|\\/share\\/(?:p|v|r)\\/|\\/photo(?:s|\\.php|\\/)|\\/people\\/|[?&](?:fbid|story_fbid|v)=/i;

                return Array.from(root.querySelectorAll('a[href], a[role="link"]'))
                    .filter(belongsToRoot)
                    .filter(link => !link.closest('h2, h3, h4, [data-ad-rendering-role="profile_name"]'))
                    .filter(link => !link.querySelector('svg, img'))
                    .map(link => {
                        const href = link.href || link.getAttribute('href') || '';
                        if (!href || /[?&](?:comment_id|reply_comment_id|reply_comment_token)=/i.test(href)) return null;

                        const ariaLabel = (link.getAttribute('aria-label') || '').trim();
                        const title = (link.getAttribute('title') || '').trim();
                        const text = (link.textContent || '').trim();
                        const combined = `${ariaLabel} ${title} ${text}`.trim();
                        const hasTimeReference =
                            /\\d/.test(ariaLabel) ||
                            /\\d/.test(title) ||
                            compactTime.test(text) ||
                            timeWords.test(combined);
                        if (!hasTimeReference) return null;

                        const hasPostReference = postReference.test(href);
                        let score = 1000;
                        if (hasPostReference) score += 800;
                        if (ariaLabel && /\\d/.test(ariaLabel)) score += 500;
                        if (title && /\\d/.test(title)) score += 250;
                        if (link.matches('[role="link"]')) score += 100;

                        return { href, ariaLabel, title, text, hasPostReference, score };
                    })
                    .filter(Boolean)
                    .sort((a, b) => b.score - a.score);
            }"""
        )  # Collect timestamp links without assuming one Facebook permalink shape
    except Exception:  # Detached/transitioning articles provide no trustworthy timestamp link
        return []  # Allow later mounted representations to retry

    candidates: list[dict] = []  # Normalize browser payload into Python dictionaries
    seen: set[tuple[str, str, str, str]] = set()  # Deduplicate responsive duplicate links

    for raw_candidate in raw_candidates or []:  # Preserve strongest unique timestamp representations
        href = str(raw_candidate.get("href") or "").strip()
        aria_label = normalize_whitespace(str(raw_candidate.get("ariaLabel") or ""))
        title = normalize_whitespace(str(raw_candidate.get("title") or ""))
        visible_text = normalize_whitespace(str(raw_candidate.get("text") or ""))
        identity = (href, aria_label, title, visible_text)

        if identity in seen:
            continue
        seen.add(identity)

        candidates.append(
            {
                "href": href,
                "aria_label": aria_label,
                "title": title,
                "text": visible_text,
                "has_post_reference": bool(raw_candidate.get("hasPostReference")),
                "score": int(raw_candidate.get("score") or 0),
            }
        )

    candidates.sort(key=lambda item: -int(item.get("score") or 0))
    return candidates


def split_facebook_timestamp_variants(value: str) -> list[str]:
    """
    Normalize Facebook timestamp text and build parseable variants.

    :param value: Raw aria-label, title, tooltip, or visible timestamp text.
    :return: Ordered unique timestamp variants.
    """

    normalized = normalize_whitespace(str(value or "")).replace("\n", " ").strip()
    if not normalized:
        return []

    variants: list[str] = []

    def add(candidate: str) -> None:
        cleaned = re.sub(r"\s+", " ", str(candidate or "")).strip(" \t\r\n·•|")
        cleaned = re.sub(r"^(?:edited|editado)\s*[·•:-]?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(
            r"\s*[·•]\s*(?:public|público|publico|friends|amigos|only me|somente eu).*$",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        cleaned = cleaned.strip(" \t\r\n·•|")
        if cleaned and cleaned not in variants:
            variants.append(cleaned)

    add(normalized)
    for part in re.split(r"\s+[·•]\s+|\s*\|\s*", normalized):
        add(part)

    return variants


def collect_hover_timestamp_candidates(page: Page, article) -> list[str]:
    """
    Hover likely timestamp links and collect Facebook's absolute-time tooltip.

    :param page: Page containing the mounted root post.
    :param article: Root post locator.
    :return: Direct and hover-derived timestamp candidates.
    """

    timestamp_candidates = collect_timestamp_link_candidates(article)
    if not timestamp_candidates:
        return []

    desired_hrefs = {
        str(candidate.get("href") or "")
        for candidate in timestamp_candidates[:5]
        if candidate.get("href")
    }
    collected: list[str] = []

    def add(value: str) -> None:
        for variant in split_facebook_timestamp_variants(value):
            if variant not in collected:
                collected.append(variant)

    for candidate in timestamp_candidates[:5]:
        add(str(candidate.get("aria_label") or ""))
        add(str(candidate.get("title") or ""))
        add(str(candidate.get("text") or ""))

    try:
        links = article.locator('a[href], a[role="link"]')
        for index in range(min(links.count(), 100)):
            link = links.nth(index)
            try:
                live_href = str(link.evaluate("element => element.href || element.getAttribute('href') || ''") or "")
                if desired_hrefs and live_href not in desired_hrefs:
                    continue

                link.hover(timeout=1_500)
                page.wait_for_timeout(POST_TIMESTAMP_HOVER_SETTLE_MS)

                before_tooltip_count = len(collected)  # Distinguish new hover data from direct aria/title/text candidates
                tooltips = page.locator('[role="tooltip"]')
                tooltip_count = tooltips.count()
                for tooltip_index in range(max(0, tooltip_count - 5), tooltip_count):
                    tooltip = tooltips.nth(tooltip_index)
                    try:
                        if tooltip.is_visible():
                            add(tooltip.inner_text(timeout=750))
                    except Exception:
                        continue

                if len(collected) > before_tooltip_count:
                    break  # Stop only after this hover actually produced additional tooltip timestamp text
            except Exception:
                continue
    except Exception:
        pass

    return collected


def collect_post_permalink_candidates(article) -> list[dict]:
    """
    Collect post-permalink candidates from one top-level Facebook timeline article.

    Timestamp semantics are the primary signal. This is intentionally broader than a fixed list of
    Facebook URL shapes because modern posts can expose /share/p/, photo, video, reel, story, or
    other Facebook routes. Nested comment/reply anchors are excluded before scoring.

    :param article: Playwright locator representing a Facebook article.
    :return: Scored permalink candidate dictionaries sorted strongest-first.
    """

    if not is_top_level_timeline_article(article):  # Never derive post identity from a nested comment/reply article
        return []  # Reject nested article

    try:  # Extract same-post anchors and semantic timestamp metadata in one browser-side pass
        raw_candidates = article.evaluate(
            """root => {
                const rootArticle = root.matches('[role="article"]') ? root : root.querySelector('[role="article"]');
                const belongsToRoot = element => {
                    if (!rootArticle) return true;
                    return element.closest('[role="article"]') === rootArticle;
                };
                const message = root.querySelector('div[data-ad-rendering-role="story_message"], [data-ad-preview="message"], [data-ad-comet-preview="message"]');
                return Array.from(root.querySelectorAll('a[href]'))
                    .filter(belongsToRoot)
                    .map(anchor => {
                        const relation = message ? anchor.compareDocumentPosition(message) : 0;
                        return {
                            href: anchor.href || anchor.getAttribute('href') || '',
                            text: (anchor.innerText || anchor.textContent || '').trim(),
                            ariaLabel: anchor.getAttribute('aria-label') || '',
                            title: anchor.getAttribute('title') || '',
                            hasAbbr: !!anchor.querySelector('abbr[data-utime], abbr'),
                            hasTime: !!anchor.querySelector('time[datetime], time'),
                            inHeading: !!anchor.closest('h1, h2, h3, h4, strong'),
                            beforeMessage: !!(relation & Node.DOCUMENT_POSITION_FOLLOWING),
                        };
                    });
            }"""
        )  # Read anchors that belong to the root post rather than nested comments
    except Exception:  # Detached article cannot provide reliable identity
        return []  # Return no permalink candidates

    profile_path = (urlparse(PROFILE_URL).path or '').casefold().rstrip('/')  # Resolve configured profile path
    candidates: list[dict] = []  # Initialize scored candidates

    for raw_candidate in raw_candidates or []:  # Inspect root-post anchors
        href = str(raw_candidate.get('href') or '').strip()  # Normalize raw href
        if not href or not is_facebook_url(href):  # Require an absolute Facebook URL
            continue  # Ignore external/unresolved links
        if url_has_comment_context(href):  # A comment/reply timestamp must never become the post identity
            continue  # Reject comment-context URL

        text_value = normalize_whitespace(str(raw_candidate.get('text') or ''))  # Normalize visible anchor text
        aria_value = normalize_whitespace(str(raw_candidate.get('ariaLabel') or ''))  # Normalize accessibility label
        title_value = normalize_whitespace(str(raw_candidate.get('title') or ''))  # Normalize tooltip label
        has_date_semantics = bool(raw_candidate.get('hasAbbr') or raw_candidate.get('hasTime')) or any(
            looks_like_date_candidate(value)
            for value in (text_value, aria_value, title_value)
            if value
        )  # Detect timestamp anchors independently of their URL route

        known_route = is_probable_post_url(href)  # Determine whether href matches a known post/media route
        if not has_date_semantics and not known_route:  # Arbitrary profile/navigation links cannot identify a post
            continue  # Ignore unrelated anchor

        normalized = normalize_facebook_url(href)  # Remove tracking/comment-context parameters after they were checked
        lowered = normalized.casefold()  # Normalize URL for route scoring
        path = (urlparse(normalized).path or '').casefold()  # Resolve normalized route path
        score = 0  # Initialize candidate score

        if has_date_semantics:  # Timestamp semantics are the strongest cross-version signal
            score += 700  # Prefer anchors that visibly represent the post timestamp
        if raw_candidate.get('hasAbbr') or raw_candidate.get('hasTime'):  # Machine-readable time descendants are especially strong
            score += 250  # Prefer semantic time markup
        if raw_candidate.get('inHeading'):  # Post author/timestamp header anchors are preferable to embedded-media links
            score += 180  # Prefer header area
        if raw_candidate.get('beforeMessage'):  # Root post timestamp normally precedes the message body
            score += 120  # Prefer anchors before message content

        if '/posts/pfbid' in lowered:  # Modern explicit post permalink
            score += 600
        elif '/posts/' in lowered:  # Legacy numeric post permalink
            score += 560
        elif '/permalink.php' in lowered or '/story.php' in lowered or 'story_fbid=' in lowered:  # Legacy story routes
            score += 520
        elif '/share/p/' in lowered:  # Modern shared post permalink
            score += 500
        elif '/share/v/' in lowered or '/videos/' in lowered:  # Video post permalink
            score += 430
        elif '/share/r/' in lowered or '/reel/' in lowered:  # Reel post permalink
            score += 420
        elif any(hint in lowered for hint in PHOTO_LINK_HINTS):  # Photo posts can expose their timestamp through a photo route
            score += 350

        if profile_path and path.startswith(profile_path):  # Prefer routes explicitly scoped to the configured profile
            score += 150  # Add owner-path preference without using it as sole proof of authorship

        candidates.append(
            {
                'url': normalized,
                'score': score,
                'text': text_value,
                'aria_label': aria_value,
                'title': title_value,
                'has_date_semantics': has_date_semantics,
            }
        )  # Preserve candidate and timestamp metadata

    unique_by_url: dict[str, dict] = {}  # Retain only strongest score for each normalized URL
    for candidate in candidates:  # Deduplicate repeated responsive/header links
        url = str(candidate.get('url') or '')  # Read normalized URL
        previous = unique_by_url.get(url)  # Find existing candidate
        if previous is None or int(candidate.get('score') or 0) > int(previous.get('score') or 0):  # Prefer stronger semantics
            unique_by_url[url] = candidate  # Retain strongest representation

    result = list(unique_by_url.values())  # Build deduplicated candidate list
    result.sort(key=lambda item: (-int(item.get('score') or 0), len(str(item.get('url') or '')), str(item.get('url') or '')))  # Strongest first
    return result  # Return post permalink candidates


def is_profile_owner_post_article(article, post_url: str) -> bool:
    """
    Determine whether a top-level Facebook article was authored by the configured profile owner.

    URL shape alone is never accepted as proof of authorship because nested comments frequently
    link back to the owner post. The function requires top-level article ancestry plus an author
    name/profile link from the root post header.

    :param article: Facebook article locator.
    :param post_url: Canonical permalink extracted from the article.
    :return: True when the root article belongs to the configured profile owner or filtering is disabled.
    """

    if not is_top_level_timeline_article(article):  # Reject nested comment/reply role=article containers first
        return False  # Nested article cannot be a root profile post
    if url_has_comment_context(post_url):  # Defensive rejection of comment-specific permalinks
        return False  # Never archive comment context as a post
    if not ONLY_PROFILE_OWNER_POSTS:  # Allow all top-level authors only when explicitly configured
        return True  # Skip author filtering

    profile_path = (urlparse(PROFILE_URL).path or '').casefold().rstrip('/')  # Normalize configured profile path
    accepted_names = {
        normalize_whitespace(name).casefold()
        for name in PROFILE_AUTHOR_NAMES
        if normalize_whitespace(name)
    }  # Normalize accepted visible owner names

    try:  # Extract author/header links belonging only to the root post article
        author_data = article.evaluate(
            """root => {
                const rootArticle = root.matches('[role="article"]') ? root : root.querySelector('[role="article"]');
                const belongsToRoot = element => {
                    if (!rootArticle) return true;
                    return element.closest('[role="article"]') === rootArticle;
                };
                const anchors = Array.from(root.querySelectorAll('div[data-ad-rendering-role="profile_name"] a[href], h1 a[href], h2 a[href], h3 a[href], h4 a[href], strong a[href], a[role="link"][href]'))
                    .filter(belongsToRoot)
                    .slice(0, 40)
                    .map(anchor => ({
                        text: (anchor.innerText || anchor.textContent || '').trim(),
                        href: anchor.href || anchor.getAttribute('href') || '',
                        inHeading: !!anchor.closest('h1, h2, h3, h4, strong'),
                    }));
                const clone = root.cloneNode(true);
                clone.querySelectorAll('[role="article"]').forEach(node => {
                    if (node !== clone && node.parentNode) node.remove();
                });
                const lines = (clone.innerText || clone.textContent || '').split(/\\n+/).map(line => line.trim()).filter(Boolean).slice(0, 12);
                return { anchors, lines };
            }"""
        )  # Read root-post header identity and initial text without nested comments
    except Exception:  # Detached article cannot be positively attributed
        return False  # Reject ambiguous candidate

    for author in (author_data or {}).get('anchors', []):  # Inspect root-post author/header links
        author_text = normalize_whitespace(str(author.get('text') or '')).casefold()  # Normalize visible text
        author_href = str(author.get('href') or '').strip()  # Preserve raw href
        if not author_href or not is_facebook_url(author_href):  # Ignore non-Facebook links
            continue  # Continue to next author candidate
        author_path = (urlparse(author_href).path or '').casefold().rstrip('/')  # Normalize author path

        if author_text in accepted_names:  # Visible configured owner name is positive author proof
            return True  # Accept owner post
        if profile_path and author_path == profile_path:  # Exact configured profile path is positive author proof
            return True  # Accept owner post

    first_lines = [normalize_whitespace(str(line or '')).casefold() for line in (author_data or {}).get('lines', [])]  # Normalize root-post initial lines
    if any(line in accepted_names for line in first_lines[:8]):  # Older Facebook markup may render author text without a direct heading anchor
        return True  # Accept owner post from root header text
    if any(
        any(line.startswith(f"{accepted_name} ") or line.startswith(f"{accepted_name} ·") for accepted_name in accepted_names)
        for line in first_lines[:8]
    ):  # Accept header lines that append action/audience/timestamp text to the owner name
        return True  # Root article is visibly attributed to the configured owner

    normalized_post_url = normalize_facebook_url(post_url) if post_url else ""  # Normalize optional canonical permalink
    post_path = (urlparse(normalized_post_url).path or "").casefold().rstrip("/") if normalized_post_url else ""  # Read post route path
    if profile_path and post_path.startswith(f"{profile_path}/") and is_top_level_timeline_article(article):
        return True  # A top-level article whose canonical route is under the configured profile is safe owner evidence

    return False  # Reject posts by other authors and genuinely ambiguous containers


def extract_post_permalink(article) -> str:
    """
    Extract the strongest root-post permalink while rejecting nested comments/replies.

    :param article: Playwright locator representing a Facebook post candidate.
    :return: Normalized post permalink or an empty string.
    """

    if not is_top_level_timeline_article(article):
        return ""

    for timestamp_candidate in collect_timestamp_link_candidates(article):
        if not timestamp_candidate.get("has_post_reference"):
            continue
        raw_url = str(timestamp_candidate.get("href") or "")
        if raw_url and not url_has_comment_context(raw_url):
            return normalize_facebook_url(raw_url)

    candidates = collect_post_permalink_candidates(article)
    for candidate in candidates:
        url = str(candidate.get("url") or "")
        if url and not url_has_comment_context(url):
            return url

    return ""


def expand_post_text(article) -> None:
    """
    Expand truncated root-post text without clicking "See more" controls inside nested comments.

    :param article: Playwright locator representing a Facebook post.
    :return: None
    """

    for label in SEE_MORE_TEXTS:  # Iterate supported localized labels
        try:  # Inspect exact controls in this root post
            controls = article.get_by_text(label, exact=True)  # Locate expansion controls
            for index in range(min(controls.count(), 10)):  # Bound repeated controls
                control = controls.nth(index)  # Resolve current control
                try:  # Verify control belongs to root post rather than a nested comment article
                    belongs_to_root = bool(
                        control.evaluate(
                            """element => {
                                const root = element.closest('[role="article"]');
                                const outer = root && root.parentElement ? root.parentElement.closest('[role="article"]') : null;
                                return !root || !outer;
                            }"""
                        )
                    )  # Reject nested-comment controls
                except Exception:  # Detached control cannot be safely clicked
                    belongs_to_root = False  # Skip ambiguous control

                if belongs_to_root and control.is_visible():  # Click only visible root-post expansion
                    control.click(timeout=1_500)  # Expand post body
                    return  # Stop after first successful expansion
        except Exception:  # Expansion is optional and must never abort extraction
            continue  # Try next localized label


def extract_post_content(article) -> str:
    """
    Extract root-post body text while excluding nested comments, replies, and interaction UI.

    :param article: Playwright locator representing a top-level Facebook post.
    :return: Normalized post content.
    """

    if not is_top_level_timeline_article(article):  # Never extract a nested comment as post content
        return ''  # Reject nested article

    expand_post_text(article)  # Expand truncated root-post text before extraction

    try:  # Extract explicit message containers and fallback text browser-side without nested role=article descendants
        payload = article.evaluate(
            """root => {
                const rootArticle = root.matches('[role="article"]') ? root : root.querySelector('[role="article"]');
                const belongsToRoot = element => {
                    if (!rootArticle) return true;
                    return element.closest('[role="article"]') === rootArticle;
                };
                const cleanedText = element => {
                    const clone = element.cloneNode(true);
                    clone.querySelectorAll('[role="article"]').forEach(node => node.remove());
                    return (clone.innerText || clone.textContent || '').trim();
                };
                const explicit = Array.from(root.querySelectorAll('div[data-ad-rendering-role="story_message"], [data-ad-preview="message"], [data-ad-comet-preview="message"]'))
                    .filter(belongsToRoot)
                    .map(cleanedText)
                    .filter(Boolean);
                const generic = Array.from(root.querySelectorAll('div[dir="auto"]'))
                    .filter(belongsToRoot)
                    .map(cleanedText)
                    .filter(Boolean)
                    .slice(0, 80);
                const rootClone = root.cloneNode(true);
                rootClone.querySelectorAll('[role="article"]').forEach(node => node.remove());
                const fallback = (rootClone.innerText || rootClone.textContent || '').trim();
                return { explicit, generic, fallback };
            }"""
        )  # Read root-post-only text snapshots
    except Exception:  # Detached article cannot provide reliable content
        return ''  # Return empty content

    explicit_candidates = [normalize_whitespace(str(value or '')) for value in (payload or {}).get('explicit', [])]  # Normalize dedicated message blocks
    explicit_candidates = [value for value in explicit_candidates if value]  # Remove empty message blocks
    if explicit_candidates:  # Dedicated message markup is the safest source
        return max(explicit_candidates, key=len)  # Return most complete dedicated message

    generic_candidates: list[str] = []  # Initialize generic root-post text candidates
    for raw_value in (payload or {}).get('generic', []):  # Inspect generic dir=auto blocks
        value = clean_article_fallback_text(str(raw_value or ''))  # Remove author/date/action UI lines
        if not value:  # Ignore empty/UI-only blocks
            continue  # Continue to next generic candidate
        if value not in generic_candidates:  # Avoid duplicate nested containers
            generic_candidates.append(value)  # Preserve candidate

    if generic_candidates:  # Use the most substantial clean root-post candidate
        generic_candidates.sort(key=lambda value: (len(value.splitlines()), len(value)), reverse=True)  # Prefer complete multiline body
        return generic_candidates[0]  # Return best clean generic body

    return clean_article_fallback_text(str((payload or {}).get('fallback') or ''))  # Final root-article fallback without nested comments


def clean_article_fallback_text(value: str) -> str:
    """
    Remove common Facebook author/date/interaction lines from root-article fallback text.

    :param value: Raw root-article text with nested comments already removed.
    :return: Cleaned likely post content.
    """

    ignored_exact_lines = {
        'Like', 'Comment', 'Share', 'Curtir', 'Comentar', 'Compartilhar', 'Send', 'Enviar',
        'Reply', 'Responder', 'Edited', 'Editado', 'Author', 'do autor', '·',
        *PROFILE_AUTHOR_NAMES,
    }  # Common non-content lines
    ignored_casefold = {normalize_whitespace(line).casefold() for line in ignored_exact_lines if normalize_whitespace(line)}  # Normalize ignored labels

    result: list[str] = []  # Initialize retained lines
    for line in normalize_whitespace(value).splitlines():  # Iterate normalized lines
        stripped = line.strip()  # Normalize current line
        lowered = stripped.casefold()  # Build case-insensitive representation
        if not stripped or lowered in ignored_casefold:  # Drop known UI/author-only lines
            continue  # Continue to next line
        if re.fullmatch(r'\d+\s*(comments?|comentários?|comentarios?|shares?|compartilhamentos?|replies?|respostas?)', stripped, re.IGNORECASE):  # Drop engagement counts
            continue  # Continue to next line
        if re.fullmatch(r'\d+\s*(s|m|min|h|d|w|sem|a|y|anos?|years?|dias?|days?|horas?|hours?)', stripped, re.IGNORECASE):  # Drop standalone relative-age/timestamp labels
            continue  # Continue to next line
        if lowered in {'public', 'público', 'publico'}:  # Drop audience label
            continue  # Continue to next line
        result.append(stripped)  # Preserve likely content

    return '\n'.join(result).strip()  # Return cleaned fallback text


def derive_post_title(content: str, post_id: str) -> str:
    """
    Derive a filesystem title from the first meaningful post-content line.

    :param content: Full extracted post content.
    :param post_id: Post identifier used as a fallback.
    :return: Sanitized post title.
    """

    ignored_names = {normalize_whitespace(name).casefold() for name in PROFILE_AUTHOR_NAMES if normalize_whitespace(name)}  # Normalize owner names
    ignored_ui = {'reply', 'responder', 'like', 'curtir', 'comment', 'comentar', 'share', 'compartilhar', 'do autor', 'author', '·'}  # UI-only lines
    lines = [line.strip() for line in normalize_whitespace(content).splitlines() if line.strip()]  # Build meaningful lines
    title = ''  # Initialize title

    for line in lines:  # Select first line that is actual post content
        lowered = line.casefold()  # Normalize candidate
        if lowered in ignored_names or lowered in ignored_ui:  # Skip owner/UI lines
            continue  # Continue to next line
        title = line  # Use first meaningful content line
        break  # Stop after selecting title

    if not title:  # Handle media-only posts
        title = f'Post {post_id}' if post_id else 'Post'  # Build deterministic fallback title
    if len(title) > MAX_CONTENT_TITLE_LENGTH:  # Limit raw title content
        title = title[:MAX_CONTENT_TITLE_LENGTH].rstrip()  # Truncate safely

    return sanitize_filename_component(title, fallback=f'Post {post_id}' if post_id else 'Post')  # Return filesystem-safe title


def collect_date_candidates(article) -> list[str]:
    """
    Collect root-post date candidates using current Facebook timestamp links first.

    :param article: Playwright locator representing a top-level Facebook post.
    :return: Ordered unique raw timestamp candidates.
    """

    candidates: list[str] = []

    def add(value: str) -> None:
        for variant in split_facebook_timestamp_variants(value):
            if variant not in candidates:
                candidates.append(variant)

    for timestamp_candidate in collect_timestamp_link_candidates(article):
        add(str(timestamp_candidate.get("aria_label") or ""))
        add(str(timestamp_candidate.get("title") or ""))
        add(str(timestamp_candidate.get("text") or ""))

    for permalink_candidate in collect_post_permalink_candidates(article):
        add(str(permalink_candidate.get("aria_label") or ""))
        add(str(permalink_candidate.get("title") or ""))
        add(str(permalink_candidate.get("text") or ""))

    try:
        fallback_values = article.evaluate(
            """root => {
                const rootArticle = root.matches('[role="article"]') ? root : root.querySelector('[role="article"]') || root;
                const belongsToRoot = element => {
                    const closestArticle = element.closest('[role="article"]');
                    return !closestArticle || closestArticle === rootArticle;
                };
                const selectors = [
                    'abbr[data-utime]',
                    'abbr',
                    'time[datetime]',
                    '[data-utime]',
                    'a[aria-label]',
                    'a[title]'
                ];

                return Array.from(root.querySelectorAll(selectors.join(',')))
                    .filter(belongsToRoot)
                    .filter(element => !element.closest('[data-commentid]'))
                    .filter(element => {
                        const href = element.closest('a')?.href || '';
                        return !/[?&](?:comment_id|reply_comment_id|reply_comment_token)=/i.test(href);
                    })
                    .flatMap(element => [
                        element.getAttribute('data-utime') || '',
                        element.getAttribute('datetime') || '',
                        element.getAttribute('aria-label') || '',
                        element.getAttribute('title') || '',
                        (element.textContent || '').trim()
                    ]);
            }"""
        )
    except Exception:
        fallback_values = []

    for raw_value in fallback_values or []:
        value = str(raw_value or "")
        if looks_like_date_candidate(value):
            add(value)

    return candidates


def looks_like_date_candidate(value: str) -> bool:
    """
    Determine whether Facebook text plausibly contains a post timestamp.

    :param value: Candidate timestamp text.
    :return: True when at least one normalized variant has a date/time signal.
    """

    month_words = (
        "janeiro", "fevereiro", "março", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
        "january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december",
        "enero", "febrero", "marzo", "mayo", "junio", "julio", "septiembre", "octubre", "noviembre", "diciembre",
        "janvier", "février", "fevrier", "mars", "avril", "mai", "juin", "juillet", "août", "aout", "septembre", "octobre", "novembre", "décembre", "decembre",
        "januar", "februar", "märz", "marz", "april", "mai", "juni", "juli", "august", "september", "oktober", "november", "dezember",
        "jan", "fev", "feb", "mar", "abr", "apr", "mai", "may", "jun", "jul", "ago", "aug", "set", "sep", "sept", "out", "oct", "nov", "dez", "dec",
    )
    relative_words = (
        "ontem", "hoje", "agora mesmo", "yesterday", "today", "just now",
        "ago", "atrás", "atras", "há ", "ha ",
        "minute", "minutes", "minuto", "minutos", "hora", "horas", "hour", "hours",
        "dia", "dias", "day", "days", "semana", "semanas", "week", "weeks",
        "ano", "anos", "year", "years",
    )

    for variant in split_facebook_timestamp_variants(value):
        normalized = variant.casefold().strip()
        if not normalized:
            continue

        if re.fullmatch(r"\d{9,11}", normalized):
            return True
        if re.search(r"\b(?:19|20)\d{2}[-/.]\d{1,2}[-/.]\d{1,2}\b", normalized):
            return True
        if re.search(r"\b\d{1,2}[-/.]\d{1,2}(?:[-/.](?:19|20)?\d{2})?\b", normalized):
            return True
        if re.fullmatch(
            r"(?:há\s+|ha\s+)?\d+\s*(?:s|seg(?:undo)?s?|m|min(?:uto)?s?|mins|h|hr|hrs|hora|horas|d|dia|dias|w|wk|week|weeks|sem|semana|semanas|a|ano|anos|y|yr|yrs|year|years)(?:\s+ago|\s+atrás|\s+atras)?",
            normalized,
            flags=re.IGNORECASE,
        ):
            return True
        if any(word in normalized for word in month_words):
            return True
        if any(word in normalized for word in relative_words):
            return True
        if re.search(r"\b(?:19|20)\d{2}\b", normalized) and re.search(r"\b\d{1,2}\b", normalized):
            return True

    return False


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
    Parse current and legacy Facebook timestamp candidates into an absolute local datetime.

    :param candidates: Ordered raw timestamp candidates.
    :return: Parsed datetime and the value that produced it.
    """

    reference_now = datetime.datetime.now().astimezone()

    for candidate in candidates:
        for value in split_facebook_timestamp_variants(candidate):
            if not value or not looks_like_date_candidate(value):
                continue

            if re.fullmatch(r"\d{9,11}", value):
                try:
                    parsed_timestamp = datetime.datetime.fromtimestamp(int(value), tz=reference_now.tzinfo)
                    if is_plausible_post_datetime(parsed_timestamp, reference_now):
                        return parsed_timestamp, value
                except (OverflowError, OSError, ValueError):
                    pass

            normalized_relative = value.casefold().strip()
            relative_match = re.fullmatch(
                r"(?:há\s+|ha\s+)?(\d+)\s*(s|seg(?:undo)?s?|m|min(?:uto)?s?|mins|h|hr|hrs|hora|horas|d|dia|dias|w|wk|week|weeks|sem|semana|semanas|a|ano|anos|y|yr|yrs|year|years)(?:\s+ago|\s+atrás|\s+atras)?",
                normalized_relative,
                flags=re.IGNORECASE,
            )
            if relative_match:
                amount = int(relative_match.group(1))
                unit = relative_match.group(2).casefold()

                if unit in {"s", "seg", "segs", "segundo", "segundos"}:
                    delta = datetime.timedelta(seconds=amount)
                elif unit in {"m", "min", "mins", "minuto", "minutos"}:
                    delta = datetime.timedelta(minutes=amount)
                elif unit in {"h", "hr", "hrs", "hora", "horas"}:
                    delta = datetime.timedelta(hours=amount)
                elif unit in {"d", "dia", "dias"}:
                    delta = datetime.timedelta(days=amount)
                elif unit in {"w", "wk", "week", "weeks", "sem", "semana", "semanas"}:
                    delta = datetime.timedelta(weeks=amount)
                else:
                    delta = datetime.timedelta(days=365 * amount)

                parsed_relative = reference_now - delta
                if is_plausible_post_datetime(parsed_relative, reference_now):
                    return parsed_relative, value

            if normalized_relative in {"ontem", "yesterday"}:
                parsed_relative = reference_now - datetime.timedelta(days=1)
                return parsed_relative, value
            if normalized_relative in {"hoje", "today", "agora mesmo", "just now"}:
                return reference_now, value

            try:
                iso_candidate = value.replace("Z", "+00:00")
                parsed_iso = datetime.datetime.fromisoformat(iso_candidate)
                if parsed_iso.tzinfo is None:
                    parsed_iso = parsed_iso.replace(tzinfo=reference_now.tzinfo)
                if is_plausible_post_datetime(parsed_iso, reference_now):
                    return parsed_iso.astimezone(reference_now.tzinfo), value
            except ValueError:
                pass

            parsed = dateparser.parse(
                value,
                languages=["pt", "en", "es", "fr", "de"],
                settings={
                    "RELATIVE_BASE": reference_now.replace(tzinfo=None),
                    "RETURN_AS_TIMEZONE_AWARE": False,
                    "PREFER_DATES_FROM": "past",
                    "DATE_ORDER": "DMY",
                },
            )

            if parsed is not None:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=reference_now.tzinfo)
                else:
                    parsed = parsed.astimezone(reference_now.tzinfo)

                if is_plausible_post_datetime(parsed, reference_now):
                    return parsed, value

    return None, ""


def resolve_post_date(page: Page, article) -> tuple[datetime.datetime | None, str]:
    """
    Resolve a mounted Facebook root-post date, including absolute-time hover fallback.

    :param page: Page containing the mounted post.
    :param article: Root post locator.
    :return: Parsed datetime and raw date label.
    """

    direct_candidates = collect_date_candidates(article)
    parsed, raw_value = parse_facebook_date(direct_candidates)
    raw_lowered = raw_value.casefold() if raw_value else ""
    relative_timestamp = bool(
        raw_value
        and (
            re.fullmatch(
                r"(?:há\s+|ha\s+)?\d+\s*(?:s|seg(?:undo)?s?|m|min(?:uto)?s?|mins|h|hr|hrs|hora|horas|d|dia|dias|w|wk|week|weeks|sem|semana|semanas|a|ano|anos|y|yr|yrs|year|years)(?:\s+ago|\s+atrás|\s+atras)?",
                raw_lowered,
                flags=re.IGNORECASE,
            )
            or raw_lowered in {"ontem", "yesterday", "hoje", "today", "agora mesmo", "just now"}
        )
    )  # Relative labels are useful fallback dates but hover can expose the exact absolute timestamp

    if parsed is not None and not relative_timestamp:
        return parsed, raw_value  # Preserve exact direct absolute timestamps without an unnecessary hover

    hover_candidates = collect_hover_timestamp_candidates(page, article)
    hover_parsed, hover_raw = parse_facebook_date(hover_candidates)
    if hover_parsed is not None:
        return hover_parsed, hover_raw  # Prefer hover-derived absolute timestamp when available

    return parsed, raw_value  # Fall back to a valid relative timestamp only if hover could not improve it


def page_has_content_unavailable_message(page: Page) -> bool:
    """
    Detect Facebook's content-unavailable/error view so it cannot be mistaken for a usable timeline.

    :param page: Facebook page to inspect.
    :return: True when the rendered main content contains a known unavailable-content message.
    """

    try:  # Read only a bounded amount of visible main-page text
        body_text = normalize_whitespace(page.locator("body").inner_text(timeout=2_000))[:20_000].casefold()  # Normalize visible page text
    except Exception:  # A transient DOM read is not enough to classify the page as unavailable
        return False  # Let the normal readiness checks retry

    unavailable_markers = (
        "este conteúdo não está disponível no momento",
        "este conteudo não esta disponível no momento",
        "este conteudo nao esta disponivel no momento",
        "this content isn't available right now",
        "this content is not available right now",
        "content isn't available right now",
        "content is not available right now",
    )  # Known Portuguese/English Facebook unavailable-page messages

    return any(marker in body_text for marker in unavailable_markers)  # Report whether a known unavailable state is visible


def is_probable_timeline_post_article(article) -> bool:
    """
    Distinguish an actual Facebook post card from other top-level profile widgets using role=article.

    :param article: Candidate top-level article locator.
    :return: True when post-header/body/toolbar/timestamp signals are present.
    """

    if not is_top_level_timeline_article(article):
        return False

    try:
        return bool(
            article.evaluate(
                """root => {
                    if (root.querySelector('[data-ad-rendering-role="profile_name"]')) return true;
                    if (root.querySelector('[data-ad-rendering-role="story_message"]')) return true;
                    if (root.querySelector('[data-ad-preview="message"], [data-ad-comet-preview="message"]')) return true;

                    const links = Array.from(root.querySelectorAll('a[href], a[role="link"]'));
                    return links.some(link => {
                        const href = link.href || link.getAttribute('href') || '';
                        if (/[?&](?:comment_id|reply_comment_id|reply_comment_token)=/i.test(href)) return false;
                        if (link.closest('h2, h3, h4, [data-ad-rendering-role="profile_name"]')) return false;
                        const label = link.getAttribute('aria-label') || '';
                        const text = (link.textContent || '').trim();
                        const hasTime = /\\d/.test(label) || /\\d+\\s*(?:s|m|min|h|d|w|sem|a|y)\\b/i.test(text);
                        const hasPostRef = /\\/posts\\/|\\/videos\\/|\\/watch|\\/permalink|\\/story\\.php|\\/reel\\/|\\/share\\/[pvr]\\/|[?&](?:fbid|story_fbid|v)=/i.test(href);
                        return hasTime && hasPostRef;
                    });
                }"""
            )
        )
    except Exception:
        return False


def collect_profile_timeline_diagnostics(page: Page) -> dict[str, int]:
    """
    Collect lightweight DOM counts used to diagnose profile-timeline discovery failures.

    :param page: Current Facebook profile page.
    :return: Dictionary containing feed/article/permalink/message counts.
    """

    selectors = {
        "main": 'div[role="main"]',
        "feed": 'div[role="feed"]',
        "articles": 'div[role="article"]',
        "main_articles": 'div[role="main"] div[role="article"]',
        "feed_articles": 'div[role="feed"] div[role="article"]',
        "feed_units": 'div[data-pagelet*="FeedUnit"]',
        "profile_name_roles": 'div[data-ad-rendering-role="profile_name"]',
        "story_messages": 'div[data-ad-rendering-role="story_message"]',
        "messages": 'div[data-ad-preview="message"], div[data-ad-comet-preview="message"]',
        "post_links": 'a[href*="/posts/"], a[href*="/permalink.php"], a[href*="/story.php"], a[href*="/share/p/"]',
    }  # Stable diagnostic selectors kept separate from extraction policy

    diagnostics: dict[str, int] = {}  # Initialize numeric diagnostic result
    for key, selector in selectors.items():  # Count each selector independently
        try:  # One unsupported/transient selector must not break diagnostics
            diagnostics[key] = int(page.locator(selector).count())  # Capture current DOM count
        except Exception:
            diagnostics[key] = 0  # Treat failed count as unavailable for this diagnostic sample

    return diagnostics  # Return diagnostic snapshot


def profile_timeline_is_rendered(page: Page) -> bool:
    """
    Determine whether the configured profile has rendered at least one real post/timeline structure.

    :param page: Authenticated configured-profile page.
    :return: True when the actual profile timeline is mounted.
    """

    if page.is_closed() or page_has_content_unavailable_message(page):
        return False

    try:
        has_feed_structure = any(page.locator(selector).count() > 0 for selector in PROFILE_FEED_CONTAINER_SELECTORS)
        has_current_post_marker = (
            page.locator('div[data-ad-rendering-role="profile_name"]').count() > 0
            or page.locator('div[data-ad-rendering-role="story_message"]').count() > 0
            or page.locator('div[role="feed"] div[role="article"]').count() > 0
        )
        if has_feed_structure and has_current_post_marker:
            return True
    except Exception:
        pass

    try:
        root_articles = page.locator('div[role="main"] div[role="article"]')
        for index in range(min(root_articles.count(), 25)):
            if is_probable_timeline_post_article(root_articles.nth(index)):
                return True
    except Exception:
        pass

    return False


def build_mounted_article_discovery_key(article) -> str:
    """
    Build a stable-enough in-session identity for a top-level post when Facebook exposes no canonical permalink.

    The key is derived only from the root post (nested comments are removed) and is used for current-session
    discovery/retry bookkeeping. Persisted cross-run identity is still derived later from post content/date/id.

    :param article: Top-level Facebook post/container locator.
    :return: SHA-256 based discovery key, or an empty string when the article cannot be inspected.
    """

    try:  # Extract root-post-only text/link/media signals in one browser-side call
        payload = article.evaluate(
            """root => {
                const clone = root.cloneNode(true);
                clone.querySelectorAll('[role="article"]').forEach(node => {
                    if (node !== clone && node.parentNode) node.remove();
                });
                const text = (clone.innerText || clone.textContent || '').trim();
                const links = Array.from(clone.querySelectorAll('a[href]'))
                    .slice(0, 80)
                    .map(a => a.href || a.getAttribute('href') || '')
                    .filter(Boolean);
                const media = Array.from(clone.querySelectorAll('img[src], video[src], video source[src]'))
                    .slice(0, 80)
                    .map(el => el.currentSrc || el.src || el.getAttribute('src') || '')
                    .filter(Boolean);
                return { text, links, media };
            }"""
        )  # Read only signals belonging to this mounted root container
    except Exception:
        return ""  # Detached/unsupported article cannot provide a fallback identity

    source = json.dumps(
        payload or {},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8", errors="replace")  # Build deterministic in-session hash input

    if not source or source == b"{}":  # Reject empty payloads that would collapse unrelated articles
        return ""  # No safe fallback identity exists

    return f"mounted:{hashlib.sha256(source).hexdigest()[:32]}"  # Return compact fallback discovery identity


def get_article_locator(page: Page):
    """
    Return the first Facebook article selector that currently matches the profile timeline.

    Facebook also marks comments as role=article, so callers must use is_top_level_timeline_article
    before interpreting any returned element as a post.

    :param page: Facebook profile page.
    :return: Playwright locator for currently mounted article-like containers.
    """

    for selector in ARTICLE_SELECTORS:  # Iterate supported post/container selectors
        locator = page.locator(selector)  # Build candidate locator
        try:  # Attempt to inspect current count
            if locator.count() > 0:  # Verify at least one article-like container is mounted
                return locator  # Return matching broad locator; top-level filtering occurs per element
        except Exception:  # Ignore transient DOM failures
            continue  # Continue to next selector

    return page.locator(ARTICLE_SELECTORS[0])  # Return primary selector so scrolling can retry naturally


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
                except Exception:  # Ignore one transient element and continue verifying
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
    Verify whether the persistent browser profile already contains a usable Facebook login.

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

        if page_has_content_unavailable_message(page):  # Never accept Facebook's unavailable/error view as a profile timeline
            try:  # Recover explicitly to the configured profile root
                page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)  # Reopen the valid profile root
            except Exception:
                time.sleep(AUTHENTICATION_POLL_SECONDS)  # Allow another readiness iteration to retry
            continue  # Re-evaluate only after leaving the unavailable view

        try:  # Require both authenticated main chrome and an actual timeline/feed structure
            has_main_content = page.locator('div[role="main"]').count() > 0  # Detect the configured profile's main region
        except Exception:
            has_main_content = False  # Transient DOM state is not ready

        if has_main_content and profile_timeline_is_rendered(page):  # Main chrome without a feed must not start an empty scrape
            return page  # Return only a page with a real rendered profile timeline

        try:  # Nudge lazy profile sections into mounting while remaining near the newest posts
            page.evaluate("window.scrollBy(0, 500)")  # Move enough to mount the first timeline cards below the profile header
            page.wait_for_timeout(500)  # Give Facebook's client renderer a short opportunity to mount the feed
        except Exception:
            pass  # Continue readiness polling even when the nudge fails

        time.sleep(AUTHENTICATION_POLL_SECONDS)  # Wait before verifying the rendered profile again

    diagnostics = collect_profile_timeline_diagnostics(page)  # Capture DOM state before surfacing readiness failure
    raise TimeoutError(
        f"Facebook authentication is valid, but the configured profile timeline did not render within "
        f"{PROFILE_READY_TIMEOUT_SECONDS} seconds. Current URL: {format_url_for_log(get_live_page_url(page))}. "
        f"DOM diagnostics: {diagnostics}"
    )  # Fail explicitly instead of silently scraping a page with no timeline


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
        f"{BackgroundColors.GREEN}Configured Facebook profile: "
        f"{BackgroundColors.CYAN}{PROFILE_DISPLAY_NAME}{BackgroundColors.GREEN} | username "
        f"{BackgroundColors.CYAN}{PROFILE_USERNAME}{Style.RESET_ALL}"
    )  # Log the configured display name and URL-derived username explicitly
    print(
        f"{BackgroundColors.GREEN}Profile timeline loaded from newest position: "
        f"{BackgroundColors.CYAN}{PROFILE_URL}{Style.RESET_ALL}"
    )  # Log the complete configured profile URL

    return page  # Return exact Page object ready for timeline scraping


def activate_profile_posts_view(page: Page, context: BrowserContext) -> Page:
    """
    Preserve the configured profile-root timeline without navigating to inferred Posts-tab URLs.

    Facebook may render links containing ``sk=posts`` that are unavailable or unsuitable for a personal
    profile. The downloader therefore keeps PROFILE_URL as the only profile-feed navigation target.

    :param page: Authenticated configured-profile page.
    :param context: Authenticated browser context retained for API compatibility.
    :return: The same configured-profile page after verifying its real timeline is rendered.
    """

    _ = context  # Preserve the existing call signature without introducing an unused-parameter warning
    if page_has_content_unavailable_message(page):  # Defensive guard against an already-invalid page
        page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)  # Recover to profile root

    return page  # Never navigate automatically to ?sk=posts or /posts


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
        session.page = activate_profile_posts_view(session.page, session.context)  # Use Facebook-provided Posts view when available
        return session  # Keep the visible browser for scraping because headless mode is disabled

    if not force_interactive_authentication:  # Normal startup should first reuse a persisted login without showing a window
        print(
            f"{BackgroundColors.GREEN}Verifying the persistent Facebook session in headless mode...{Style.RESET_ALL}"
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
            headless_session.page = activate_profile_posts_view(headless_session.page, headless_session.context)  # Prefer live Facebook Posts view when available
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
            headless_session.page = activate_profile_posts_view(headless_session.page, headless_session.context)  # Prefer live Facebook Posts view when available
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


def strip_post_directory_index(directory_name: str) -> str:
    """
    Remove an existing numeric post-directory index prefix.

    :param directory_name: Current post directory name.
    :return: Directory name without a leading "NN. " index prefix.
    """

    return POST_DIRECTORY_INDEX_PATTERN.sub("", str(directory_name or ""), count=1).strip()  # Remove only the canonical leading index


def resolve_post_output_sort_timestamp(metadata: dict) -> float:
    """
    Resolve a sortable timestamp from persisted post metadata.

    :param metadata: Parsed post.json metadata.
    :return: Unix timestamp used to order post directories oldest to newest, or positive infinity when unavailable.
    """

    raw_datetime = str(metadata.get("datetime") or "").strip()  # Prefer full timezone-aware post datetime
    if raw_datetime:  # Attempt full datetime parsing first
        try:  # Parse metadata written by datetime.isoformat()
            parsed_datetime = datetime.datetime.fromisoformat(raw_datetime.replace("Z", "+00:00"))  # Normalize optional UTC suffix
            if parsed_datetime.tzinfo is None:  # Ensure timestamp conversion is deterministic for naive legacy metadata
                parsed_datetime = parsed_datetime.replace(tzinfo=datetime.datetime.now().astimezone().tzinfo)  # Attach current local timezone
            return parsed_datetime.timestamp()  # Return sortable Unix timestamp
        except (TypeError, ValueError, OverflowError, OSError):  # Fall back to date-only metadata
            pass  # Continue to date parsing

    raw_date = str(metadata.get("date") or "").strip()  # Read persisted YYYY-MM-DD date
    if raw_date:  # Attempt date-only parsing
        try:  # Parse ISO date and place it at local midnight
            parsed_date = datetime.date.fromisoformat(raw_date)  # Parse persisted post date
            parsed_datetime = datetime.datetime.combine(
                parsed_date,
                datetime.time.min,
                tzinfo=datetime.datetime.now().astimezone().tzinfo,
            )  # Build timezone-aware local midnight
            return parsed_datetime.timestamp()  # Return sortable Unix timestamp
        except (TypeError, ValueError, OverflowError, OSError):  # Invalid metadata is sorted after valid posts
            pass  # Continue to fallback

    return float("inf")  # Keep malformed/undated directories after every correctly dated post


def build_post_output_base_name(post_dir: Path, metadata: dict) -> str:
    """
    Build the canonical unindexed "YYYY-MM-DD-Title" post directory name.

    :param post_dir: Existing post output directory.
    :param metadata: Parsed post.json metadata.
    :return: Canonical directory base name without a numeric index.
    """

    raw_date = str(metadata.get("date") or "").strip()  # Read persisted post date
    raw_title = str(metadata.get("title") or "").strip()  # Read persisted post title

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_date) and raw_title:  # Prefer metadata-backed canonical naming
        safe_title = sanitize_filename_component(raw_title, fallback="Post")  # Normalize title for filesystem use
        return f"{raw_date}-{safe_title}"  # Rebuild canonical date-title base name

    fallback_name = strip_post_directory_index(post_dir.name)  # Preserve existing unindexed name when metadata is incomplete
    return fallback_name or sanitize_filename_component(str(metadata.get("post_id") or "Post"), fallback="Post")  # Return safe fallback


def migrate_flat_post_outputs_to_profile_directory() -> int:
    """
    Move existing flat ./Outputs/{PostDirectory}/ results into ./Outputs/{ProfileUsername}/.

    Only direct child directories of OUTPUT_ROOT_DIR that contain post.json are migrated. Existing
    profile subdirectories and unrelated folders are left untouched. The move is collision-safe and
    metadata output_directory values are updated immediately after each successful migration.

    :param: None
    :return: Number of existing post directories migrated into the profile-specific output directory.
    """

    if not OUTPUT_ROOT_DIR.exists():  # Nothing can require migration before the shared output root exists
        return 0  # Return an empty migration count

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # Ensure the profile-specific intermediate directory exists
    migrated_count = 0  # Count successfully migrated flat post directories

    for candidate in list(OUTPUT_ROOT_DIR.iterdir()):  # Snapshot direct children before moving any of them
        if candidate == OUTPUT_DIR:  # Never inspect or move the destination profile directory itself
            continue  # Continue to the next direct child
        if not candidate.is_dir():  # Only directories can represent persisted post outputs
            continue  # Ignore files under the shared output root

        metadata_path = candidate / POST_METADATA_FILENAME  # A direct child is a flat post output only when post.json exists
        if not metadata_path.is_file():  # Preserve other profile folders, backups, and unrelated directories
            continue  # Skip non-post directories

        destination = OUTPUT_DIR / candidate.name  # Preserve the existing indexed/unindexed post directory name
        if destination.exists():  # Never merge or overwrite two persisted post directories implicitly
            raise FileExistsError(
                f"Cannot migrate flat post output because destination already exists: {destination.as_posix()}"
            )  # Fail safely so no media or metadata can be lost

        candidate.rename(destination)  # Move the complete post directory, including media files, into the profile subdirectory

        original_metadata: dict | None = None  # Preserve the pre-migration metadata so rollback can restore it exactly
        try:  # Keep persisted output_directory synchronized with the new filesystem location
            migrated_metadata_path = destination / POST_METADATA_FILENAME  # Resolve metadata at its new location
            with migrated_metadata_path.open("r", encoding="utf-8") as file:  # Read the existing metadata document
                loaded_metadata = json.load(file)  # Parse metadata before updating its path fields
            if not isinstance(loaded_metadata, dict):  # post.json must contain an object before it can be migrated safely
                raise TypeError(f"Post metadata must be a JSON object: {migrated_metadata_path.as_posix()}")  # Reject unsupported metadata shapes
            original_metadata = dict(loaded_metadata)  # Snapshot exact original fields for rollback
            metadata = dict(loaded_metadata)  # Build an independent mutable copy for the profile-scoped path update
            metadata["profile_url"] = PROFILE_URL  # Preserve the profile associated with this output tree
            metadata["profile_username"] = PROFILE_USERNAME  # Persist the intermediate output directory identifier explicitly
            metadata["output_directory"] = destination.relative_to(PROJECT_DIR).as_posix()  # Store the new profile-scoped relative path
            write_post_metadata(destination, metadata)  # Atomically rewrite metadata at the migrated location
        except Exception as error:  # A metadata refresh failure must not silently leave inconsistent persisted state
            try:  # Attempt to restore the original directory location and metadata before surfacing the error
                destination.rename(candidate)  # Roll back the filesystem migration
                if original_metadata is not None:  # Restore original metadata if it had already been parsed successfully
                    write_post_metadata(candidate, original_metadata)  # Restore the original output_directory and all other fields
            except Exception as rollback_error:  # Surface both failures if rollback cannot restore the original output
                raise RuntimeError(
                    f"Failed to update migrated metadata for {destination.as_posix()} and rollback also failed: {rollback_error}"
                ) from error
            raise RuntimeError(f"Failed to update migrated metadata for {candidate.as_posix()}: {error}") from error

        migrated_count += 1  # Count the successfully migrated post directory

    if migrated_count > 0:  # Log only when an existing flat layout was actually converted
        print(
            f"{BackgroundColors.GREEN}Migrated flat post outputs into profile directory: "
            f"{BackgroundColors.CYAN}{migrated_count}{BackgroundColors.GREEN} -> "
            f"{BackgroundColors.CYAN}{OUTPUT_DIR.relative_to(PROJECT_DIR).as_posix()}{Style.RESET_ALL}"
        )  # Report the completed layout migration

    return migrated_count  # Return the number of post directories moved


def find_existing_post_output_directory(post_id: str) -> Path | None:
    """
    Find an existing indexed or unindexed output directory for a specific Facebook post.

    :param post_id: Stable Facebook post identifier.
    :return: Existing post directory when found, otherwise None.
    """

    normalized_post_id = str(post_id or "").strip()  # Normalize requested post identifier
    if not normalized_post_id or not OUTPUT_DIR.exists():  # Avoid filesystem scanning when lookup cannot succeed
        return None  # No reusable post directory is available

    for metadata_path in OUTPUT_DIR.glob(f"*/{POST_METADATA_FILENAME}"):  # Inspect both indexed and unindexed post directories
        try:  # Isolate malformed metadata files
            with metadata_path.open("r", encoding="utf-8") as file:  # Open persisted post metadata
                metadata = json.load(file)  # Parse JSON document
            if str(metadata.get("post_id") or "").strip() == normalized_post_id:  # Match the stable Facebook post identifier
                return metadata_path.parent  # Reuse the existing post directory regardless of its current index
        except Exception:  # Damaged metadata must not prevent creating/recovering other posts
            continue  # Continue scanning remaining outputs

    return None  # No existing directory belongs to this post


def reindex_post_output_directories() -> int:
    """
    Rename post output directories using oldest-to-newest zero-padded numeric indexes.

    Index width is at least two digits and automatically expands for 100+ or 1000+ posts. Renaming
    is performed in two phases through unique temporary names so index shifts cannot overwrite or
    collide with another post directory. Each post.json output_directory value is updated afterward.

    :param: None
    :return: Number of post directories successfully indexed.
    """

    if not OUTPUT_DIR.exists():  # No output directory means there is nothing to index
        return 0  # Return an empty result

    records = []  # Collect valid post directories and metadata before any rename

    for metadata_path in OUTPUT_DIR.glob(f"*/{POST_METADATA_FILENAME}"):  # Inspect every persisted post directory
        try:  # Isolate malformed/incomplete metadata files
            with metadata_path.open("r", encoding="utf-8") as file:  # Open metadata document
                metadata = json.load(file)  # Parse post metadata
            post_dir = metadata_path.parent  # Resolve directory that owns this metadata
            records.append(
                {
                    "path": post_dir,
                    "metadata": metadata,
                    "sort_timestamp": resolve_post_output_sort_timestamp(metadata),
                    "base_name": build_post_output_base_name(post_dir, metadata),
                    "post_id": str(metadata.get("post_id") or "").strip(),
                }
            )  # Preserve all values required for deterministic ordering and naming
        except Exception as error:  # Leave unreadable directories untouched and visible
            print(
                f"{BackgroundColors.YELLOW}Skipping post directory reindex because metadata could not be read: "
                f"{BackgroundColors.CYAN}{metadata_path.as_posix()}"
                f"{BackgroundColors.YELLOW} ({error}){Style.RESET_ALL}"
            )  # Log reindex skip

    if not records:  # Verify at least one valid post directory was found
        return 0  # Nothing can be indexed

    records.sort(
        key=lambda item: (
            float(item["sort_timestamp"]),
            str(item["post_id"]),
            str(item["base_name"]).casefold(),
        )
    )  # Sort oldest to newest with stable deterministic tie breakers

    index_width = max(POST_DIRECTORY_INDEX_MIN_WIDTH, len(str(len(records))))  # Expand zero padding for large post counts
    used_base_names = set()  # Track collision-safe unindexed names across all posts

    for position, record in enumerate(records, start=1):  # Assign final oldest-to-newest indexes
        base_name = str(record["base_name"])  # Read canonical unindexed date-title name
        canonical_base_name = base_name  # Prefer the plain date-title name

        if canonical_base_name.casefold() in used_base_names:  # Resolve same-date/same-title collisions deterministically
            suffix_source = str(record["post_id"] or "Duplicate")  # Prefer stable post identifier as collision suffix
            suffix = sanitize_filename_component(suffix_source, fallback="Duplicate", max_length=24)  # Sanitize discriminator
            canonical_base_name = sanitize_filename_component(
                f"{base_name} {suffix}",
                fallback=f"Post {suffix}",
                max_length=max(MAX_TITLE_LENGTH + 11, len(base_name) + len(suffix) + 1),
            )  # Preserve date/title context while distinguishing the duplicate

            duplicate_counter = 2  # Initialize fallback counter for extremely rare repeated identifiers
            while canonical_base_name.casefold() in used_base_names:  # Guarantee unique final base name
                canonical_base_name = sanitize_filename_component(
                    f"{base_name} {suffix} {duplicate_counter}",
                    fallback=f"Post {suffix} {duplicate_counter}",
                    max_length=max(MAX_TITLE_LENGTH + 16, len(base_name) + len(suffix) + 8),
                )  # Add deterministic numeric fallback
                duplicate_counter += 1  # Advance collision counter

        used_base_names.add(canonical_base_name.casefold())  # Reserve the selected base name
        record["desired_name"] = f"{position:0{index_width}d}. {canonical_base_name}"  # Build final indexed directory name
        record["index"] = position  # Preserve assigned position for metadata updates

    temporarily_renamed = []  # Track directories moved to collision-proof temporary names

    for position, record in enumerate(records, start=1):  # First phase moves changed directories away from final names
        current_path = Path(record["path"])  # Read current post directory path
        desired_name = str(record["desired_name"])  # Read final indexed directory name

        if current_path.name == desired_name:  # Directory already has the correct index and canonical name
            record["temporary_path"] = current_path  # Preserve path for metadata refresh
            continue  # No filesystem rename is required

        digest = hashlib.sha256(f"{current_path.name}|{record['post_id']}|{position}".encode("utf-8", errors="replace")).hexdigest()[:12]  # Build deterministic temp token
        temporary_path = OUTPUT_DIR / f".__post_reindex_{position}_{digest}"  # Build temporary sibling directory name
        collision_counter = 2  # Initialize safety counter if a prior interrupted run left the same temp path
        while temporary_path.exists():  # Guarantee the temporary path does not overwrite existing data
            temporary_path = OUTPUT_DIR / f".__post_reindex_{position}_{digest}_{collision_counter}"  # Add collision suffix
            collision_counter += 1  # Advance temporary-name counter

        current_path.rename(temporary_path)  # Move directory away from all final indexed names
        record["temporary_path"] = temporary_path  # Preserve temporary path for phase two
        temporarily_renamed.append(record)  # Track changed directory

    for record in records:  # Second phase assigns final unique indexed names
        temporary_path = Path(record.get("temporary_path") or record["path"])  # Resolve current directory location
        desired_path = OUTPUT_DIR / str(record["desired_name"])  # Build final indexed destination

        if temporary_path != desired_path:  # Rename only when the directory is not already final
            if desired_path.exists():  # A non-participating collision would risk overwriting data
                raise FileExistsError(f"Cannot index post directory because destination already exists: {desired_path.as_posix()}")  # Fail safely
            temporary_path.rename(desired_path)  # Assign final oldest-to-newest index

        metadata = dict(record["metadata"])  # Copy parsed metadata before updating persisted location
        metadata["profile_url"] = PROFILE_URL  # Keep metadata explicitly associated with the configured profile
        metadata["profile_username"] = PROFILE_USERNAME  # Persist the profile-specific intermediate directory identifier
        metadata["output_directory"] = desired_path.relative_to(PROJECT_DIR).as_posix()  # Keep JSON path synchronized with rename
        write_post_metadata(desired_path, metadata)  # Atomically persist corrected metadata path

    print(
        f"{BackgroundColors.GREEN}Indexed post directories oldest-to-newest: "
        f"{BackgroundColors.CYAN}{len(records)}"
        f"{BackgroundColors.GREEN} directories, width "
        f"{BackgroundColors.CYAN}{index_width}{Style.RESET_ALL}"
    )  # Log completed reindex summary

    return len(records)  # Return number of indexed post directories


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
    :return: Number of current-schema complete post outputs under the profile-specific OUTPUT_DIR.
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


def collect_photo_permalink_urls(article) -> list[str]:
    """
    Collect distinct top-level Facebook photo permalinks from one post.

    :param article: Top-level Facebook post article.
    :return: Ordered distinct photo permalink URLs.
    """

    if not is_top_level_timeline_article(article):  # Never collect media from nested comments
        return []  # Reject nested article

    try:  # Extract same-root media anchors browser-side
        raw_urls = article.evaluate(
            """root => {
                const rootArticle = root.matches('[role="article"]') ? root : root.querySelector('[role="article"]');
                const belongsToRoot = element => !rootArticle || element.closest('[role="article"]') === rootArticle;
                return Array.from(root.querySelectorAll('a[href]'))
                    .filter(belongsToRoot)
                    .map(anchor => anchor.href || anchor.getAttribute('href') || '')
                    .filter(Boolean);
            }"""
        )  # Read root-post anchors
    except Exception:  # Detached article
        return []  # Return no permalinks

    result: list[str] = []  # Initialize ordered photo permalinks
    seen: set[str] = set()  # Track duplicates
    for raw_url in raw_urls or []:  # Inspect post anchors
        url = str(raw_url or '').strip()  # Normalize raw URL
        lowered = url.casefold()  # Normalize for route matching
        if not is_facebook_url(url) or url_has_comment_context(url):  # Reject external/comment-context URLs
            continue  # Continue to next anchor
        if not any(hint in lowered for hint in PHOTO_LINK_HINTS):  # Keep photo-viewer routes only
            continue  # Ignore unrelated anchor
        normalized = normalize_facebook_url(url)  # Remove tracking parameters
        if normalized in seen:  # Avoid duplicate photo anchors
            continue  # Continue to next anchor
        seen.add(normalized)  # Mark photo permalink
        result.append(normalized)  # Preserve post order
        if len(result) >= MAX_MEDIA_PER_POST:  # Enforce safety ceiling
            break  # Stop collecting pathological media counts

    return result  # Return distinct photo permalinks


def collect_video_permalink_urls(article) -> list[str]:
    """
    Collect distinct top-level Facebook video/reel permalinks from one post.

    :param article: Top-level Facebook post article.
    :return: Ordered distinct video/reel permalink URLs.
    """

    if not is_top_level_timeline_article(article):  # Never collect video links from comments
        return []  # Reject nested article

    try:  # Extract same-root anchors browser-side
        raw_urls = article.evaluate(
            """root => {
                const rootArticle = root.matches('[role="article"]') ? root : root.querySelector('[role="article"]');
                const belongsToRoot = element => !rootArticle || element.closest('[role="article"]') === rootArticle;
                return Array.from(root.querySelectorAll('a[href]'))
                    .filter(belongsToRoot)
                    .map(anchor => anchor.href || anchor.getAttribute('href') || '')
                    .filter(Boolean);
            }"""
        )  # Read root-post anchors
    except Exception:  # Detached article
        return []  # Return no permalinks

    result: list[str] = []  # Initialize ordered video permalinks
    seen: set[str] = set()  # Track duplicates
    for raw_url in raw_urls or []:  # Inspect post anchors
        url = str(raw_url or '').strip()  # Normalize raw URL
        lowered = url.casefold()  # Normalize for route matching
        if not is_facebook_url(url) or url_has_comment_context(url):  # Reject external/comment-context URLs
            continue  # Continue to next anchor
        if not any(hint in lowered for hint in VIDEO_LINK_HINTS):  # Keep video/reel routes only
            continue  # Ignore unrelated anchor
        normalized = normalize_facebook_url(url)  # Remove tracking parameters
        if normalized in seen:  # Avoid duplicates
            continue  # Continue to next anchor
        seen.add(normalized)  # Mark video permalink
        result.append(normalized)  # Preserve order
        if len(result) >= MAX_MEDIA_PER_POST:  # Enforce safety ceiling
            break  # Stop collecting pathological counts

    return result  # Return distinct video/reel permalinks


def decode_facebook_serialized_url(value: str) -> str:
    """
    Decode a URL stored as a JSON/HTML escaped string inside Facebook page markup.

    :param value: Escaped serialized URL value.
    :return: Decoded HTTP(S) URL or an empty string.
    """

    raw_value = str(value or '').strip()  # Normalize raw serialized value
    if not raw_value:  # Reject empty capture
        return ''  # Return empty URL

    decoded = raw_value  # Initialize decoded value
    try:  # JSON string decoding handles \\/ and \\uXXXX escapes safely
        decoded = json.loads(f'"{raw_value}"')  # Decode one JSON string literal
    except Exception:  # Fall back to common Facebook escape substitutions
        decoded = raw_value.replace(r'\/', '/').replace(r'\u0025', '%').replace(r'\u0026', '&').replace(r'\u003d', '=')  # Decode common URL escapes

    decoded = html.unescape(str(decoded or '')).replace('\\/', '/').strip()  # Decode HTML entities and residual slash escaping
    return decoded if decoded.startswith(('http://', 'https://')) else ''  # Return direct HTTP(S) URL only


def extract_progressive_video_urls_from_html(page_html: str) -> list[str]:
    """
    Extract progressive/native Facebook video URLs embedded in serialized page data.

    :param page_html: HTML markup returned by Playwright for a video/reel permalink page.
    :return: Ordered distinct direct HTTP(S) video URLs.
    """

    patterns = (
        r'"playable_url_quality_hd"\s*:\s*"([^"\r\n]+)"',
        r'"browser_native_hd_url"\s*:\s*"([^"\r\n]+)"',
        r'"playable_url"\s*:\s*"([^"\r\n]+)"',
        r'"browser_native_sd_url"\s*:\s*"([^"\r\n]+)"',
        r'"progressive_url"\s*:\s*"([^"\r\n]+)"',
        r'"hd_src"\s*:\s*"([^"\r\n]+)"',
        r'"sd_src"\s*:\s*"([^"\r\n]+)"',
    )  # Known Facebook serialized progressive/native video fields, ordered high-quality first

    result: list[str] = []  # Initialize decoded video URLs
    seen: set[str] = set()  # Track duplicates
    for pattern in patterns:  # Search each known field
        for match in re.finditer(pattern, str(page_html or ''), re.IGNORECASE):  # Iterate all serialized occurrences
            decoded = decode_facebook_serialized_url(match.group(1))  # Decode captured URL
            if not decoded or decoded in seen:  # Reject invalid/duplicate URLs
                continue  # Continue to next capture
            seen.add(decoded)  # Mark retained URL
            result.append(decoded)  # Preserve quality-preference order
            if len(result) >= MAX_MEDIA_PER_POST:  # Enforce safety ceiling
                return result  # Return bounded result

    return result  # Return progressive/native URLs


def resolve_photo_candidate_from_permalink(context: BrowserContext, photo_url: str) -> dict | None:
    """
    Resolve the largest currently available image URL from one authenticated Facebook photo permalink.

    :param context: Authenticated persistent browser context.
    :param photo_url: Facebook photo-viewer permalink.
    :return: Downloadable photo candidate or None when the viewer cannot resolve an image.
    """

    details_page: Page | None = None  # Initialize optional cleanup reference for the temporary viewer page
    try:  # Open photo viewer without disturbing the scrolling timeline
        active_page: Page = context.new_page()  # Create a definitely initialized authenticated temporary page
        details_page = active_page  # Preserve the page separately for guaranteed cleanup in finally
        active_page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT_MS)  # Configure navigation timeout
        active_page.goto(photo_url, wait_until='domcontentloaded', timeout=PAGE_LOAD_TIMEOUT_MS)  # Open photo permalink
        active_page.wait_for_timeout(MEDIA_PERMALINK_SETTLE_MS)  # Allow media viewer to resolve currentSrc

        raw_images = active_page.evaluate(
            """() => Array.from(document.querySelectorAll('img[src], img[srcset]')).map(image => ({
                src: image.currentSrc || image.src || '',
                width: image.naturalWidth || image.width || 0,
                height: image.naturalHeight || image.height || 0,
                displayWidth: image.clientWidth || 0,
                displayHeight: image.clientHeight || 0,
                alt: image.alt || '',
                media: image.getAttribute('data-visualcompletion') === 'media-vc-image',
            }))"""
        )  # Read viewer images and dimensions

        ranked: list[tuple[int, dict]] = []  # Initialize scored viewer images
        for info in raw_images or []:  # Inspect viewer images
            src = str(info.get('src') or '').strip()  # Normalize image source
            if not src.startswith(('http://', 'https://')):  # Require direct downloadable URL
                continue  # Skip blob/data images
            width = int(info.get('width') or 0)  # Normalize intrinsic width
            height = int(info.get('height') or 0)  # Normalize intrinsic height
            display_width = int(info.get('displayWidth') or 0)  # Normalize rendered width
            display_height = int(info.get('displayHeight') or 0)  # Normalize rendered height
            if max(width, height, display_width, display_height) < 240:  # Exclude avatars/icons
                continue  # Continue to next image
            score = width * height  # Prefer largest intrinsic image
            if info.get('media'):  # Facebook's media-viewer marker is a strong positive signal
                score += 10_000_000_000  # Prioritize media-vc-image over UI images
            ranked.append((score, info))  # Preserve scored image

        if not ranked:  # Viewer exposed no usable image
            return None  # Report unresolved photo

        ranked.sort(key=lambda item: item[0], reverse=True)  # Prefer explicit/largest viewer image
        best = ranked[0][1]  # Select strongest photo
        return {
            'type': 'photo',
            'url': str(best.get('src') or ''),
            'width': int(best.get('width') or 0),
            'height': int(best.get('height') or 0),
            'display_width': int(best.get('displayWidth') or 0),
            'display_height': int(best.get('displayHeight') or 0),
            'alt': normalize_whitespace(str(best.get('alt') or '')),
            'photo_url': photo_url,
            'source': 'photo_permalink',
        }  # Return direct viewer-photo candidate
    except Exception as error:  # Photo-viewer resolution is best-effort per media item
        verbose_output(
            true_string=f"{BackgroundColors.YELLOW}Photo permalink resolution failed for "
            f"{BackgroundColors.CYAN}{format_url_for_log(photo_url)}{BackgroundColors.YELLOW}: "
            f"{BackgroundColors.CYAN}{error}{Style.RESET_ALL}"
        )  # Log diagnostics only in verbose mode
        return None  # Report unresolved photo
    finally:  # Always close temporary viewer page
        if details_page is not None:  # Verify page was created
            try:  # Protect cleanup if viewer crashed
                details_page.close()  # Close only temporary photo page
            except Exception:  # Ignore cleanup failure
                pass  # No further action required


def resolve_video_candidates_from_permalink(context: BrowserContext, video_url: str) -> list[dict]:
    """
    Resolve direct video resources from an authenticated Facebook video/reel permalink.

    The function combines serialized progressive/native URLs with Playwright response observation.
    Audio-only DASH resources are explicitly excluded so they are never saved as videos.

    :param context: Authenticated persistent browser context.
    :param video_url: Facebook video/reel permalink.
    :return: Ordered distinct downloadable video candidates.
    """

    details_page: Page | None = None  # Initialize temporary page
    candidates: list[dict] = []  # Initialize resolved video candidates
    seen: set[str] = set()  # Track exact direct URLs

    def add_candidate(raw_url: str, source: str, content_type: str = '') -> None:
        """Retain one direct video resource while preserving its original signed URL."""

        direct_url = str(raw_url or '').strip()  # Preserve exact signed URL
        lowered = direct_url.casefold()  # Normalize for extension/domain filtering
        normalized_content_type = str(content_type or '').split(';', 1)[0].strip().casefold()  # Normalize MIME type
        if not direct_url.startswith(('http://', 'https://')):  # Ignore blob/data URLs
            return  # Unsupported direct download
        if normalized_content_type.startswith('audio/'):  # Never misclassify DASH audio as video
            return  # Ignore audio-only resource
        if not (
            normalized_content_type.startswith('video/')
            or '.mp4' in lowered
            or '.webm' in lowered
        ):  # Require video MIME or recognizable video URL
            return  # Ignore unrelated resource
        if direct_url in seen:  # Avoid duplicate response/range observations
            return  # Candidate already retained
        seen.add(direct_url)  # Mark direct signed URL
        candidates.append(
            {
                'type': 'video',
                'url': normalize_facebook_video_media_url(direct_url),
                'raw_url': direct_url,
                'source': source,
                'content_type': normalized_content_type or None,
            }
        )  # Preserve normalized and raw signed forms

    def handle_response(response: Response) -> None:
        """Capture video response metadata without reading response bodies."""

        try:  # Isolate transient response failures
            content_type = str(response.headers.get('content-type') or '')  # Read MIME header
            add_candidate(response.url or '', 'video_permalink_network', content_type)  # Retain actual video responses only
        except Exception:  # One malformed response must not abort viewer inspection
            return  # Ignore response

    try:  # Open the video/reel page and observe playback resources
        active_page: Page = context.new_page()  # Create a definitely initialized authenticated temporary page
        details_page = active_page  # Preserve the page separately for guaranteed cleanup in finally
        active_page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT_MS)  # Configure navigation timeout
        active_page.on('response', handle_response)  # Capture media responses before navigation
        active_page.goto(video_url, wait_until='domcontentloaded', timeout=PAGE_LOAD_TIMEOUT_MS)  # Open video/reel permalink
        active_page.wait_for_timeout(MEDIA_PERMALINK_SETTLE_MS)  # Allow initial serialized/player data to render

        try:  # Extract progressive/native MP4 URLs embedded in Facebook serialized page data
            page_html = active_page.content()  # Read rendered markup
            for direct_url in extract_progressive_video_urls_from_html(page_html):  # Decode known progressive/native fields
                add_candidate(direct_url, 'video_permalink_html', 'video/mp4')  # Prefer direct progressive MP4 candidates
        except Exception:  # HTML extraction is optional when network capture succeeds
            pass  # Continue to player activation

        try:  # Trigger muted playback to force lazy video resource resolution
            videos = active_page.locator('video')  # Locate player elements
            for index in range(min(videos.count(), 10)):  # Bound multiple videos
                try:  # Ignore autoplay/player restrictions independently
                    videos.nth(index).evaluate(
                        """element => {
                            element.muted = true;
                            element.preload = 'auto';
                            const promise = element.play();
                            if (promise && promise.catch) promise.catch(() => {});
                        }"""
                    )  # Trigger media network requests
                except Exception:  # One blocked player should not prevent other candidates
                    continue  # Continue to next video
            active_page.wait_for_timeout(VIDEO_NETWORK_CAPTURE_MS)  # Observe playback video responses
        except Exception:  # Player activation is best-effort
            pass  # Keep HTML/network candidates already captured
    except Exception as error:  # Video permalink failure is isolated per media item
        verbose_output(
            true_string=f"{BackgroundColors.YELLOW}Video permalink resolution failed for "
            f"{BackgroundColors.CYAN}{format_url_for_log(video_url)}{BackgroundColors.YELLOW}: "
            f"{BackgroundColors.CYAN}{error}{Style.RESET_ALL}"
        )  # Log diagnostics only in verbose mode
    finally:  # Always close temporary video page
        if details_page is not None:  # Verify page exists
            try:  # Remove listener before closing page
                details_page.remove_listener('response', handle_response)  # Stop response collection
            except Exception:  # Listener may already be gone
                pass  # No action required
            try:  # Protect cleanup if viewer crashed
                details_page.close()  # Close only temporary video page
            except Exception:  # Ignore cleanup failure
                pass  # No action required

    source_priority = {'video_permalink_html': 0, 'video_permalink_network': 1}  # Prefer progressive/native HTML URLs over segmented network resources
    candidates.sort(key=lambda item: source_priority.get(str(item.get('source') or ''), 9))  # Return strongest direct URLs first
    if not candidates:  # Verify at least one direct video resource was resolved
        return []  # Report no downloadable candidate

    primary = dict(candidates[0])  # Use the strongest progressive/native resource as the logical video candidate
    alternate_urls: list[str] = []  # Preserve lower-priority direct URLs as request fallbacks for the same logical video
    for alternate in candidates[1:]:  # Inspect remaining direct resources
        alternate_url = str(alternate.get('raw_url') or alternate.get('url') or '').strip()  # Prefer exact signed URL
        if alternate_url and alternate_url not in alternate_urls:  # Avoid duplicate fallbacks
            alternate_urls.append(alternate_url)  # Preserve fallback URL
    if alternate_urls:  # Store fallbacks only when available
        primary['alternate_urls'] = alternate_urls  # Let download_media retry alternate SD/network resources if primary fails

    return [primary]  # Return exactly one logical video candidate for this permalink


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
                'source': 'article_image',
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

    if not is_top_level_timeline_article(article):  # Never collect players from nested comments
        return []  # Reject nested article

    try:  # Inspect only video elements belonging to the root post
        raw_videos = article.evaluate(
            """root => {
                const rootArticle = root.matches('[role="article"]') ? root : root.querySelector('[role="article"]');
                const belongsToRoot = element => !rootArticle || element.closest('[role="article"]') === rootArticle;
                return Array.from(root.querySelectorAll('video')).filter(belongsToRoot).map(video => ({
                    src: video.currentSrc || video.src || '',
                    poster: video.poster || '',
                    width: video.videoWidth || video.clientWidth || 0,
                    height: video.videoHeight || video.clientHeight || 0,
                }));
            }"""
        )  # Read direct root-post video sources
    except Exception:  # Detached article
        return []  # Return no candidates

    candidates: list[dict] = []  # Initialize direct video candidates
    seen_urls: set[str] = set()  # Track exact signed sources
    for info in raw_videos or []:  # Inspect resolved player elements
        raw_src = str(info.get('src') or '').strip()  # Preserve original signed player URL
        if not raw_src.startswith(('http://', 'https://')):  # Blob-backed players require network/permalink capture
            continue  # Continue to next video element
        if raw_src in seen_urls:  # Avoid duplicates
            continue  # Continue to next video element
        seen_urls.add(raw_src)  # Mark exact signed URL
        candidates.append(
            {
                'type': 'video',
                'url': normalize_facebook_video_media_url(raw_src),
                'raw_url': raw_src,
                'width': int(info.get('width') or 0),
                'height': int(info.get('height') or 0),
                'source': 'video_element',
            }
        )  # Preserve normalized and exact forms

    return candidates  # Return direct root-post video sources


def capture_video_network_candidates(page: Page, article) -> list[dict]:
    """
    Capture actual video resources requested while a root-post player is visible/playing.

    Audio-only DASH requests are excluded. Exact signed URLs are retained alongside a normalized
    complete-resource URL so the downloader can retry the original signature when necessary.

    :param page: Facebook profile timeline page containing the post.
    :param article: Playwright locator representing the Facebook post.
    :return: Deduplicated video resource candidates.
    """

    _, video_count = count_post_media_indicators(article)  # Determine whether post exposes video media
    if video_count <= 0 or not is_top_level_timeline_article(article):  # Avoid unrelated background capture
        return []  # No root-post video is visible

    captured: list[dict] = []  # Initialize video candidates
    seen_urls: set[str] = set()  # Track exact signed URLs

    def add_candidate(raw_url: str, source: str, content_type: str = '') -> None:
        """Retain one likely video resource while rejecting audio-only DASH traffic."""

        direct_url = str(raw_url or '').strip()  # Preserve exact signed URL
        lowered = direct_url.casefold()  # Normalize URL
        normalized_content_type = str(content_type or '').split(';', 1)[0].strip().casefold()  # Normalize MIME
        if not direct_url.startswith(('http://', 'https://')):  # Ignore blob/data resources
            return  # Unsupported direct download
        if normalized_content_type.startswith('audio/'):  # Never save an audio-only stream as a video file
            return  # Reject DASH audio
        if not (
            normalized_content_type.startswith('video/')
            or ('.mp4' in lowered and ('fbcdn.net' in lowered or 'facebook.com' in lowered))
            or ('.webm' in lowered and ('fbcdn.net' in lowered or 'facebook.com' in lowered))
        ):  # Keep actual video resources only
            return  # Ignore scripts/images/audio/background resources
        if direct_url in seen_urls:  # Avoid repeated byte-range observations of same exact URL
            return  # Candidate already retained

        seen_urls.add(direct_url)  # Mark exact signed URL
        captured.append(
            {
                'type': 'video',
                'url': normalize_facebook_video_media_url(direct_url),
                'raw_url': direct_url,
                'source': source,
                'content_type': normalized_content_type or None,
            }
        )  # Preserve normalized and raw signed URL forms

    def collect_performance_entries(source: str) -> None:
        """Collect already-issued likely video resource requests from the Performance API."""

        try:  # Recover requests that began before response listener registration
            urls = page.evaluate("""() => performance.getEntriesByType('resource').map(entry => entry.name || '').filter(Boolean)""")  # Read resource history
            for url in urls or []:  # Inspect browser resource URLs
                add_candidate(str(url), source)  # MIME is unavailable here, so extension/domain filtering applies
        except Exception:  # Performance API failure is non-fatal
            return  # Continue with response listener

    def handle_response(response: Response) -> None:
        """Collect actual video MIME responses without reading their bodies."""

        try:  # Protect Playwright event processing from transient failures
            content_type = str(response.headers.get('content-type') or '')  # Read MIME
            add_candidate(response.url or '', 'network_response', content_type)  # Retain actual video response
        except Exception:  # One malformed response must not terminate scraping
            return  # Ignore response

    collect_performance_entries('performance_before_playback')  # Recover already-started video resources
    page.on('response', handle_response)  # Start observing new responses

    try:  # Trigger lazy root-post video loading
        article.scroll_into_view_if_needed(timeout=3_000)  # Bring post into viewport
        page.wait_for_timeout(ARTICLE_SETTLE_MS)  # Allow player to mount
        videos = article.locator('video')  # Locate post player elements
        for index in range(min(videos.count(), 10)):  # Trigger bounded number of videos
            try:  # Ignore autoplay restrictions independently
                video = videos.nth(index)  # Resolve player
                if not bool(video.evaluate("element => !element.closest('[role=article]') || !element.closest('[role=article]').parentElement.closest('[role=article]')")):  # Reject nested-comment players
                    continue  # Skip nested player
                video.evaluate(
                    """element => {
                        element.muted = true;
                        element.preload = 'auto';
                        const promise = element.play();
                        if (promise && promise.catch) promise.catch(() => {});
                    }"""
                )  # Start enough playback to resolve CDN URL
            except Exception:  # One blocked/detached player should not prevent others
                continue  # Continue to next video
        page.wait_for_timeout(VIDEO_NETWORK_CAPTURE_MS)  # Observe video traffic
        collect_performance_entries('performance_after_playback')  # Recover resource history after playback
    finally:  # Always unregister listener
        try:  # Protect cleanup if page was replaced
            page.remove_listener('response', handle_response)  # Stop response collection
        except Exception:  # Listener may already be gone
            pass  # No action required

    return captured[:MAX_MEDIA_PER_POST]  # Return bounded actual video resources


def deduplicate_media_candidates(candidates: list[dict]) -> list[dict]:
    """
    Deduplicate media candidates while preferring permalink-resolved photos and progressive videos.

    :param candidates: Raw image/video candidate dictionaries.
    :return: Deduplicated media candidate list.
    """

    source_priority = {
        'photo_permalink': 0,
        'video_permalink_html': 0,
        'article_image': 1,
        'video_element': 1,
        'video_permalink_network': 2,
        'network_response': 3,
        'performance_after_playback': 4,
        'performance_before_playback': 5,
    }  # Prefer high-confidence direct media sources

    ordered = sorted(
        candidates,
        key=lambda item: source_priority.get(str(item.get('source') or ''), 9),
    )  # Put strongest source for a logical media item first

    deduplicated: list[dict] = []  # Initialize result list
    seen_keys: set[tuple[str, str]] = set()  # Track logical media identity
    for candidate in ordered:  # Iterate strongest-first candidates
        media_type = str(candidate.get('type') or '').strip()  # Normalize media type
        url = str(candidate.get('url') or '').strip()  # Normalize direct URL
        if media_type not in {'photo', 'video'} or not url:  # Reject malformed candidates
            continue  # Continue to next candidate

        if media_type == 'photo' and candidate.get('photo_url'):  # Photo permalink is stable across CDN thumbnail variants
            identity = normalize_facebook_url(str(candidate.get('photo_url') or ''))  # Use logical photo permalink
        elif media_type == 'video' and candidate.get('video_url'):  # Video/reel permalink identifies one logical post video
            identity = normalize_facebook_url(str(candidate.get('video_url') or ''))  # Deduplicate HD/SD/network URLs for that video
        else:  # Direct-media fallback identity
            identity = str(candidate.get('raw_url') or url).strip()  # Preserve exact signed resource identity

        key = (media_type, identity)  # Build logical deduplication key
        if key in seen_keys:  # Skip lower-priority duplicate
            continue  # Continue to next candidate
        seen_keys.add(key)  # Mark logical media retained
        deduplicated.append(candidate)  # Preserve strongest candidate
        if len(deduplicated) >= MAX_MEDIA_PER_POST:  # Enforce safety ceiling
            break  # Stop collecting pathological counts

    return deduplicated  # Return unique media candidates


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
    Download one Facebook photo/video using authenticated streaming HTTP requests.

    For videos, the downloader tries the complete normalized URL first when byte-range query
    parameters are present, then retries the exact original signed URL if normalization is rejected.
    HTTP 206 resources are reconstructed only when contiguous Content-Range metadata permits it.

    :param context: Browser context containing authenticated Facebook state.
    :param page: Browser page used to obtain the current User-Agent.
    :param candidate: Media candidate containing type, URL, and optional raw_url.
    :param output_path_without_extension: Destination path without extension.
    :param referer: Facebook post permalink used as Referer.
    :return: Tuple containing saved path and error string.
    """

    media_type = str(candidate.get('type') or '').strip()  # Resolve logical media type
    candidate_url = str(candidate.get('url') or '').strip()  # Resolve normalized/direct URL
    raw_signed_url = str(candidate.get('raw_url') or candidate_url).strip()  # Preserve exact signed browser-observed URL
    if media_type not in {'photo', 'video'}:  # Reject unsupported categories
        return None, f'Unsupported media type: {media_type}'  # Report invalid candidate

    request_urls: list[str] = []  # Build ordered direct URL attempts
    if media_type == 'video':  # Video candidates can include range-specific URLs
        normalized_url = normalize_facebook_video_media_url(candidate_url or raw_signed_url)  # Build complete-resource attempt
        for url in (normalized_url, raw_signed_url):  # Prefer normalized complete URL, then exact signed form
            if url and url not in request_urls:
                request_urls.append(url)  # Preserve unique attempt
        for alternate_url in candidate.get('alternate_urls') or []:  # Retry alternate progressive/SD/network URLs for same logical video
            alternate = str(alternate_url or '').strip()  # Normalize alternate URL
            if alternate and alternate not in request_urls:
                request_urls.append(alternate)  # Preserve unique fallback attempt
    else:  # Photos should preserve exact CDN URL
        if candidate_url:
            request_urls.append(candidate_url)  # Use photo URL directly

    if not request_urls or not all(url.startswith(('http://', 'https://')) for url in request_urls):  # Verify HTTP(S) URLs
        return None, f'Unsupported media URL scheme: {(candidate_url or raw_signed_url)[:80]}'  # Report unsupported URL

    temporary_path = output_path_without_extension.with_suffix('.download')  # Use temporary file until validation completes
    try:  # Resolve browser User-Agent when page remains available
        user_agent = str(page.evaluate('navigator.userAgent'))  # Read current browser User-Agent
    except Exception:  # Use browser-compatible fallback only when page is unavailable
        user_agent = 'Mozilla/5.0'  # Minimal fallback User-Agent

    base_headers = {
        'Referer': referer or PROFILE_URL,
        'User-Agent': user_agent,
        'Accept': '*/*',
        'Accept-Encoding': 'identity',
    }  # Build browser-like request headers

    last_error = ''  # Preserve final attempt error

    for attempt_url in request_urls:  # Try normalized and exact signed URLs when applicable
        session = build_authenticated_requests_session(context, attempt_url)  # Build ephemeral authenticated session for this host
        response = None  # Track current response for guaranteed cleanup

        try:  # Stream media without loading whole file into memory
            response = session.get(
                attempt_url,
                headers=base_headers,
                stream=True,
                allow_redirects=True,
                timeout=(30, 120),
            )  # Open initial media response

            if response.status_code not in (200, 206):  # Require successful complete/ranged response
                last_error = f'HTTP {response.status_code} while downloading {attempt_url}'  # Preserve failure and retry alternate URL
                continue  # Try next URL form

            content_type = (response.headers.get('content-type') or '').split(';', 1)[0].strip().casefold()  # Normalize MIME type
            if media_type == 'photo' and content_type and not content_type.startswith('image/'):  # Prevent HTML/error pages as photos
                last_error = f"Unexpected photo Content-Type '{content_type}' for {attempt_url}"  # Preserve MIME mismatch
                continue  # Try alternate URL if available
            if media_type == 'video' and content_type and not (
                content_type.startswith('video/') or content_type == 'application/octet-stream'
            ):  # Audio-only DASH and HTML/error pages are not valid video outputs
                last_error = f"Unexpected video Content-Type '{content_type}' for {attempt_url}"  # Preserve MIME mismatch
                continue  # Try alternate URL if available

            if temporary_path.exists():  # Remove prior failed attempt before writing again
                temporary_path.unlink()  # Reset temporary output

            total_written = 0  # Track bytes persisted across ranges
            expected_total: int | None = None  # Track complete resource size when supplied
            next_start = 0  # Track next required byte

            with temporary_path.open('wb') as file:  # Open destination once and append contiguous ranges
                while True:  # Continue until complete response/ranges finish
                    if response.status_code == 206:  # Parse current ranged response
                        parsed_range = parse_http_content_range(response.headers.get('content-range') or '')  # Parse range metadata
                        if parsed_range is None:  # Cannot safely reconstruct unlabeled partial response
                            raise ValueError(f'Facebook returned HTTP 206 without a usable Content-Range for {attempt_url}')
                        range_start, range_end, range_total = parsed_range  # Unpack range metadata
                        if range_start != next_start:  # Require contiguous reconstruction from byte zero
                            if total_written == 0 and range_start != 0 and attempt_url != raw_signed_url:  # Normalized URL unexpectedly began mid-resource
                                raise ValueError(f'Initial media range starts at {range_start}, expected 0 for {attempt_url}')  # Retry raw signed form
                            if total_written == 0 and range_start != 0:  # Exact signed URL encodes only a partial range
                                raise ValueError(f'Exact signed media URL exposes only range {range_start}-{range_end} for {attempt_url}')  # Cannot safely reconstruct with this URL
                            raise ValueError(f'Non-contiguous Facebook media range {range_start}-{range_end}; expected {next_start}')  # Reject corrupt sequence
                        if range_total is not None:
                            expected_total = range_total  # Preserve complete size

                    for chunk in response.iter_content(chunk_size=1024 * 1024):  # Stream one MiB chunks
                        if not chunk:
                            continue  # Ignore keep-alive chunks
                        total_written += len(chunk)  # Update byte count
                        if total_written > MAX_MEDIA_FILE_SIZE_BYTES:
                            raise ValueError(f'Downloaded media exceeds {MAX_MEDIA_FILE_SIZE_BYTES} bytes.')  # Enforce safety ceiling
                        file.write(chunk)  # Persist chunk immediately

                    if response.status_code == 200:  # Complete non-ranged response finished
                        break  # Resource complete

                    parsed_range = parse_http_content_range(response.headers.get('content-range') or '')  # Re-read completed range
                    if parsed_range is None:
                        raise ValueError(f'Could not parse completed Facebook Content-Range for {attempt_url}')  # Reject ambiguous range
                    _, range_end, range_total = parsed_range  # Read completed range end/total
                    if range_total is not None:
                        expected_total = range_total  # Update expected total
                    next_start = range_end + 1  # Continue after completed byte
                    if expected_total is None or next_start >= expected_total:
                        break  # All known bytes complete

                    response.close()  # Release completed response
                    range_end_request = min(next_start + VIDEO_RANGE_CHUNK_BYTES - 1, expected_total - 1)  # Bound next range
                    response = session.get(
                        attempt_url,
                        headers={**base_headers, 'Range': f'bytes={next_start}-{range_end_request}'},
                        stream=True,
                        allow_redirects=True,
                        timeout=(30, 120),
                    )  # Request next contiguous range
                    if response.status_code not in (200, 206):
                        raise ValueError(f'HTTP {response.status_code} while continuing ranged media {attempt_url}')  # Reject failed continuation

            if total_written == 0:
                raise ValueError(f'Downloaded media body was empty: {attempt_url}')  # Reject empty output
            if expected_total is not None and total_written != expected_total:
                raise ValueError(f'Incomplete ranged media: wrote {total_written} of {expected_total} bytes for {attempt_url}')  # Reject partial output

            extension = extension_from_response(content_type, str(response.url or attempt_url), media_type)  # Resolve extension
            output_path = output_path_without_extension.with_suffix(extension)  # Build final media path
            os.replace(temporary_path, output_path)  # Atomically promote completed file
            return output_path, ''  # Return success immediately
        except Exception as error:  # Preserve per-attempt network/filesystem failure
            last_error = str(error)  # Record error before alternate URL retry
        finally:  # Always clean this attempt's resources
            try:
                if response is not None:
                    response.close()  # Release HTTP response
            except Exception:
                pass  # Ignore cleanup failure
            try:
                session.close()  # Release requests session
            except Exception:
                pass  # Ignore cleanup failure
            try:
                if temporary_path.exists():
                    temporary_path.unlink()  # Remove incomplete temporary file
            except Exception:
                pass  # Ignore cleanup failure

    return None, last_error or f'Could not download media from {format_url_for_log(candidate_url or raw_signed_url)}'  # Report final failure


def choose_post_output_directory(post_date: datetime.datetime, title: str, post_id: str) -> Path:
    """
    Choose or reuse a unique post output directory before final oldest-to-newest indexing.

    :param post_date: Parsed Facebook post date.
    :param title: Sanitized post title.
    :param post_id: Stable post identifier used only to distinguish collisions.
    :return: Directory path reserved for the post.
    """

    existing_post_dir = find_existing_post_output_directory(post_id)  # Reuse the post directory even after numeric indexing
    if existing_post_dir is not None:  # Verify a previously persisted directory belongs to this post
        return existing_post_dir  # Avoid duplicate outputs when indexed directories already exist

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
    Resolve a post date from its dedicated permalink page when the timeline card lacks enough date information.

    :param context: Authenticated browser context.
    :param post_url: Facebook permalink to inspect.
    :return: Parsed datetime and raw date label.
    """

    if not post_url:
        return None, ""

    details_page: Page | None = None

    try:
        active_page: Page = context.new_page()
        details_page = active_page
        active_page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT_MS)
        active_page.goto(post_url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
        active_page.wait_for_timeout(1_500)

        articles = get_article_locator(active_page)
        if articles.count() == 0:
            return None, ""

        for index in range(min(articles.count(), 10)):
            article = articles.nth(index)
            if not is_top_level_timeline_article(article):
                continue
            parsed, raw_value = resolve_post_date(active_page, article)
            if parsed is not None:
                return parsed, raw_value

        return None, ""
    except Exception as error:
        verbose_output(
            true_string=f"{BackgroundColors.YELLOW}Permalink date fallback failed for "
            f"{BackgroundColors.CYAN}{format_url_for_log(post_url)}{BackgroundColors.YELLOW}: "
            f"{BackgroundColors.CYAN}{error}{Style.RESET_ALL}"
        )
        return None, ""
    finally:
        if details_page is not None:
            try:
                details_page.close()
            except Exception:
                pass


def process_article(page: Page, context: BrowserContext, article, known_keys: set[str]) -> tuple[bool, str]:
    """
    Extract and download one validated top-level profile-owner Facebook post.

    A non-empty returned key means the post is terminal for this browser session (already complete or
    newly completed). Retryable detachment/date/media failures return an empty key so a later mounted
    copy of the same canonical post can be attempted again.

    :param page: Facebook profile timeline page.
    :param context: Authenticated browser context.
    :param article: Playwright locator representing the candidate post.
    :param known_keys: Cross-run/current-run keys for complete current-schema posts.
    :return: Tuple containing whether metadata was written and a terminal primary key when complete/known.
    """

    if not is_top_level_timeline_article(article):  # Reject nested comments/replies before any expensive extraction
        return False, ''  # Not a root post

    try:  # Bring root post into view so lazy text/media resolve
        article.scroll_into_view_if_needed(timeout=3_000)  # Ensure current post is mounted/visible
        page.wait_for_timeout(ARTICLE_SETTLE_MS)  # Allow lazy media to settle
    except Exception:  # Detached article can be retried on a later mount
        return False, ''  # Keep retryable

    post_url = extract_post_permalink(article)  # Resolve canonical root-post permalink when Facebook exposes one
    if post_url and url_has_comment_context(post_url):  # Reject explicit comment/reply identity
        return False, ''  # A comment-context URL must never become a post
    if not is_profile_owner_post_article(article, post_url):  # Require configured profile owner as author
        return False, ''  # Ignore other authors

    post_id = extract_post_id(post_url) if post_url else ""  # Recover stable id when an exposed URL contains one
    content = extract_post_content(article)  # Extract root-post body without nested comments
    post_date, date_raw = resolve_post_date(page, article)  # Resolve timestamp from root-post ARIA/text/tooltip semantics
    if post_date is None and post_url:  # Use dedicated permalink only when one actually exists
        post_date, date_raw = resolve_post_date_from_permalink(context, post_url)  # Retry exact post page

    if not post_id:  # Modern/unknown Facebook routes may not expose a numeric/pfbid identifier
        post_id = build_fallback_post_key(post_url, content, date_raw)  # Build deterministic fallback id

    post_keys = build_post_keys(post_id, post_url)  # Build deduplication keys
    if post_keys and post_keys.intersection(known_keys):  # Skip complete current-schema posts already archived
        return False, sorted(post_keys)[0]  # Return terminal key so same mounted post is not reprocessed

    if post_date is None:  # Never invent a date-based directory
        timestamp_debug = collect_timestamp_link_candidates(article)[:3]  # Capture safe current-DOM timestamp evidence
        safe_timestamp_debug = [
            {
                "url": format_url_for_log(str(candidate.get("href") or "")),
                "aria_label": str(candidate.get("aria_label") or "")[:160],
                "title": str(candidate.get("title") or "")[:160],
                "text": str(candidate.get("text") or "")[:160],
            }
            for candidate in timestamp_debug
        ]  # Strip query strings and bound potentially large accessibility strings
        print(
            f"{BackgroundColors.YELLOW}Skipping top-level post because its date could not be resolved safely: "
            f"{BackgroundColors.CYAN}{format_url_for_log(post_url)}"
            f"{BackgroundColors.YELLOW} | timestamp candidates: "
            f"{BackgroundColors.CYAN}{safe_timestamp_debug}{Style.RESET_ALL}"
        )  # Surface exactly what Facebook exposed without leaking URL query parameters
        return False, ''  # Keep post retryable during this run

    expected_photo_count, expected_video_count = count_post_media_indicators(article)  # Count visible root-post media indicators
    photo_permalinks = collect_photo_permalink_urls(article)  # Collect logical photo items, including non-current carousel images
    video_permalinks = collect_video_permalink_urls(article)  # Collect logical video/reel items
    expected_photo_count = max(expected_photo_count, len(photo_permalinks))  # Use logical links as stronger completeness signal
    expected_video_count = max(expected_video_count, len(video_permalinks))  # Use logical video links as stronger completeness signal

    title = derive_post_title(content, post_id)  # Derive requested directory title
    post_dir = choose_post_output_directory(post_date, title, post_id)  # Reuse/collision-resolve output directory
    post_dir.mkdir(parents=True, exist_ok=True)  # Create directory before media downloads

    image_candidates = collect_image_candidates(article)  # Collect currently rendered root-post photo URLs
    represented_photo_urls = {
        normalize_facebook_url(str(candidate.get('photo_url') or ''))
        for candidate in image_candidates
        if candidate.get('photo_url')
    }  # Track photos already represented by a direct timeline image

    resolved_photo_candidates: list[dict] = []  # Initialize non-rendered/high-confidence photo candidates
    for photo_url in photo_permalinks:  # Resolve only logical photos not already represented in timeline DOM
        normalized_photo_url = normalize_facebook_url(photo_url)  # Normalize logical photo identity
        if normalized_photo_url in represented_photo_urls:  # Timeline already exposes direct image for this photo
            continue  # Avoid opening an extra viewer page
        resolved = resolve_photo_candidate_from_permalink(context, photo_url)  # Resolve direct viewer image URL
        if resolved is not None:  # Preserve successfully resolved photo
            resolved_photo_candidates.append(resolved)  # Add direct viewer candidate
            represented_photo_urls.add(normalized_photo_url)  # Mark logical photo represented

    direct_video_candidates = collect_video_element_candidates(article)  # Collect direct root-post player URLs
    network_video_candidates = capture_video_network_candidates(page, article)  # Collect root-post video responses
    permalink_video_candidates: list[dict] = []  # Initialize one direct candidate per logical video/reel permalink
    for video_url in video_permalinks:  # Resolve progressive/native URLs from each logical video permalink
        resolved_video_candidates = resolve_video_candidates_from_permalink(context, video_url)  # Resolve strongest direct resource plus alternates
        for resolved_video in resolved_video_candidates:  # Normally exactly one logical candidate is returned
            resolved_video['video_url'] = video_url  # Preserve stable logical video identity for deduplication/metadata
            permalink_video_candidates.append(resolved_video)  # Add resolved logical video
        if len(permalink_video_candidates) >= MAX_MEDIA_PER_POST:  # Enforce safety ceiling
            permalink_video_candidates = permalink_video_candidates[:MAX_MEDIA_PER_POST]  # Trim excess
            break  # Stop resolving pathological count

    if permalink_video_candidates:  # Dedicated video/reel pages provide the strongest one-candidate-per-video mapping
        selected_video_candidates = permalink_video_candidates  # Avoid downloading duplicate timeline/network representations
    elif direct_video_candidates:  # Fall back to direct player URLs when no permalink resolved
        limit = max(1, expected_video_count) if expected_video_count > 0 else len(direct_video_candidates)  # Keep expected logical count when known
        selected_video_candidates = direct_video_candidates[:limit]  # Use direct player resources
    else:  # Last resort uses network-observed video resources
        limit = max(1, expected_video_count) if expected_video_count > 0 else len(network_video_candidates)  # Bound likely duplicate DASH observations
        selected_video_candidates = network_video_candidates[:limit]  # Use strongest observed video resources

    media_candidates = deduplicate_media_candidates(
        resolved_photo_candidates
        + image_candidates
        + selected_video_candidates
    )  # Merge logical photos and one best direct representation per logical video

    photo_candidates = [candidate for candidate in media_candidates if candidate.get('type') == 'photo']  # Count final photo candidates
    video_candidates = [candidate for candidate in media_candidates if candidate.get('type') == 'video']  # Count final video candidates

    print(
        f"{BackgroundColors.GREEN}Post media: photos detected {BackgroundColors.CYAN}{expected_photo_count}"
        f"{BackgroundColors.GREEN}, photo permalinks {BackgroundColors.CYAN}{len(photo_permalinks)}"
        f"{BackgroundColors.GREEN}, photo candidates {BackgroundColors.CYAN}{len(photo_candidates)}"
        f"{BackgroundColors.GREEN}, videos detected {BackgroundColors.CYAN}{expected_video_count}"
        f"{BackgroundColors.GREEN}, video permalinks {BackgroundColors.CYAN}{len(video_permalinks)}"
        f"{BackgroundColors.GREEN}, video candidates {BackgroundColors.CYAN}{len(video_candidates)}{Style.RESET_ALL}"
    )  # Expose discovery vs direct-download media health

    media_results: list[dict] = []  # Initialize per-media results
    counters = {'photo': 0, 'video': 0}  # Track deterministic filenames
    for candidate in media_candidates:  # Download every retained logical media item
        media_type = str(candidate.get('type') or '')  # Resolve media type
        if media_type not in counters:
            continue  # Ignore unsupported category
        counters[media_type] += 1  # Allocate deterministic sequence
        filename_prefix = 'photo' if media_type == 'photo' else 'video'  # Resolve filename prefix
        output_without_extension = post_dir / f'{filename_prefix}_{counters[media_type]:03d}'  # Build destination stem
        saved_path, error = download_media(
            context,
            page,
            candidate,
            output_without_extension,
            post_url,
        )  # Stream media using browser-authenticated cookies/User-Agent

        media_result: dict = {
            'type': media_type,
            'source_url': candidate.get('url', ''),
            'raw_source_url': candidate.get('raw_url'),
            'source': candidate.get('source'),
            'filename': saved_path.name if saved_path else None,
            'downloaded': saved_path is not None,
            'error': error or None,
        }  # Build transparent download result
        for key in ('width', 'height', 'display_width', 'display_height', 'alt', 'photo_url', 'video_url', 'content_type', 'alternate_urls'):  # Preserve optional diagnostics
            if candidate.get(key) not in (None, ''):
                media_result[key] = candidate.get(key)  # Store available metadata
        media_results.append(media_result)  # Preserve outcome

        if saved_path:  # Log successful media download
            print(
                f"{BackgroundColors.GREEN}Downloaded {media_type}: "
                f"{BackgroundColors.CYAN}{saved_path.relative_to(PROJECT_DIR).as_posix()}{Style.RESET_ALL}"
            )  # Output saved path
        else:  # Log sanitized failure
            print(
                f"{BackgroundColors.YELLOW}Failed {media_type}: "
                f"{BackgroundColors.CYAN}{format_url_for_log(str(candidate.get('url') or ''))}"
                f"{BackgroundColors.YELLOW} ({error}){Style.RESET_ALL}"
            )  # Output failure reason without signed query context

    downloaded_photos = sum(1 for item in media_results if item.get('downloaded') and item.get('type') == 'photo')  # Count successful photos
    downloaded_videos = sum(1 for item in media_results if item.get('downloaded') and item.get('type') == 'video')  # Count successful videos
    photo_complete = expected_photo_count <= 0 or downloaded_photos >= expected_photo_count  # Require all logically identified photos
    video_complete = expected_video_count <= 0 or downloaded_videos >= expected_video_count  # Require all logically identified videos
    complete = photo_complete and video_complete  # Complete only when every identified media item was saved

    metadata = {
        'scrape_schema_version': SCRAPE_SCHEMA_VERSION,
        'complete': complete,
        'post_id': post_id,
        'post_url': post_url,
        'profile_url': PROFILE_URL,
        'profile_username': PROFILE_USERNAME,
        'date': post_date.date().isoformat(),
        'datetime': post_date.isoformat(),
        'date_raw': date_raw or None,
        'title': title,
        'content': content,
        'output_directory': post_dir.relative_to(PROJECT_DIR).as_posix(),
        'expected_photo_indicators': expected_photo_count,
        'expected_video_indicators': expected_video_count,
        'photo_permalink_count': len(photo_permalinks),
        'video_permalink_count': len(video_permalinks),
        'photo_candidate_count': len(photo_candidates),
        'video_candidate_count': len(video_candidates),
        'media_count': len(media_results),
        'downloaded_media_count': sum(1 for item in media_results if item.get('downloaded')),
        'failed_media_count': sum(1 for item in media_results if not item.get('downloaded')),
        'media': media_results,
        'scraped_at': datetime.datetime.now().astimezone().isoformat(),
    }  # Build current-schema post metadata
    write_post_metadata(post_dir, metadata)  # Persist metadata after all media attempts

    if complete:  # Complete posts can be skipped on later passes/runs
        known_keys.update(post_keys)  # Mark all post keys complete
        print(
            f"{BackgroundColors.GREEN}Saved complete post: "
            f"{BackgroundColors.CYAN}{post_dir.relative_to(PROJECT_DIR).as_posix()}{Style.RESET_ALL}"
        )  # Log completed post
        return True, f'id:{post_id}'  # Metadata written and terminal for this browser session

    print(
        f"{BackgroundColors.YELLOW}Saved incomplete post metadata; missing media will remain retryable: "
        f"{BackgroundColors.CYAN}{post_dir.relative_to(PROJECT_DIR).as_posix()}{Style.RESET_ALL}"
    )  # Explain incomplete media state
    return True, ''  # Metadata written, but keep post retryable instead of suppressing later mounts


def scroll_profile_and_download(page: Page, context: BrowserContext) -> dict:
    """
    Incrementally scroll the profile timeline and archive every validated owner post.

    Discovery and processing are tracked separately. A URL or mounted-post identity contributes to end-of-feed
    discovery once, but it is not permanently suppressed until it is already complete or becomes
    complete in this session. Detached/incomplete posts can therefore be retried when Facebook
    remounts them later in the virtualized feed.

    :param page: Authenticated profile timeline page.
    :param context: Authenticated browser context.
    :return: Execution statistics.
    """

    page = ensure_scraping_profile_ready(page, context)  # Refuse to start against challenged session
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # Ensure the profile-specific output directory exists
    reindex_post_output_directories()  # Normalize existing indexed outputs before resume
    known_keys = load_existing_post_keys()  # Load only complete current-schema posts

    try:  # Always begin newest-first
        page.evaluate('window.scrollTo(0, 0)')  # Reset current Facebook view to top
        page.wait_for_timeout(1_000)  # Allow first batch to settle
    except Exception:  # Navigation already attempts the same reset
        pass  # Continue safely

    processed_posts = 0  # Count metadata writes during this browser session
    discovered_post_urls: set[str] = set()  # Track canonical owner-post URLs for feed-discovery progress
    finished_session_urls: set[str] = set()  # Track already-known/newly-complete URLs that need no more processing
    retry_counts: dict[str, int] = {}  # Bound retry attempts for detached/incomplete posts in one session
    no_new_discovery_scrolls = 0  # Track consecutive passes without new owner-post identities
    previous_scroll_y = -1  # Track actual viewport movement

    print(
        f"{BackgroundColors.GREEN}Previously completed current-schema post keys: "
        f"{BackgroundColors.CYAN}{len(known_keys)}{Style.RESET_ALL}"
    )  # Log resume state

    initial_diagnostics = collect_profile_timeline_diagnostics(page)  # Capture the exact DOM state handed to the scraper
    print(
        f"{BackgroundColors.GREEN}Initial timeline DOM: "
        f"{BackgroundColors.CYAN}{initial_diagnostics}{Style.RESET_ALL}"
    )  # Make zero-discovery failures actionable instead of silent

    for scroll_iteration in range(1, MAX_SCROLL_ITERATIONS + 1):  # Scroll until discovery/movement stabilizes
        page = ensure_scraping_profile_ready(page, context)  # Revalidate auth before DOM work
        articles = get_article_locator(page)  # Resolve broad mounted article-like containers
        current_count = articles.count()  # Count mounted candidates including comments
        top_level_count = 0  # Count actual root timeline articles
        new_discovered_this_iteration = 0  # Count new owner-post identities
        processed_this_iteration = 0  # Count metadata writes this pass

        for index in range(current_count):  # Inspect mounted candidates before virtualization removes them
            try:  # Isolate one article
                article = articles.nth(index)  # Resolve current locator
                if not is_top_level_timeline_article(article):  # Facebook comments are also role=article
                    continue  # Skip nested comment/reply article
                if not is_probable_timeline_post_article(article):  # Profile chrome/widgets can also use role=article
                    continue  # Process only actual root post cards
                top_level_count += 1  # Count validated root post container

                post_url = extract_post_permalink(article)  # Resolve canonical permalink when Facebook exposes one
                if post_url and url_has_comment_context(post_url):  # Reject explicit comment/reply context
                    continue  # Continue to next root article
                if not is_profile_owner_post_article(article, post_url):  # Require configured owner as author
                    continue  # Ignore other authors

                discovery_key = normalize_facebook_url(post_url) if post_url else build_mounted_article_discovery_key(article)  # Build URL or DOM fallback identity
                if not discovery_key:  # Detached/empty root cards cannot be tracked safely
                    continue  # Wait for a later mounted representation

                if discovery_key not in discovered_post_urls:  # First time this owner post has appeared
                    discovered_post_urls.add(discovery_key)  # Mark discovery
                    new_discovered_this_iteration += 1  # Reset end-of-feed confidence

                if discovery_key in finished_session_urls:  # Already complete/known in this session
                    continue  # Do not repeat expensive processing

                attempts = retry_counts.get(discovery_key, 0)  # Read previous retry count
                if attempts >= MAX_POST_PROCESS_RETRIES_PER_SESSION:  # Bound repeated incomplete/detached work
                    continue  # Leave for next execution rather than looping forever
                retry_counts[discovery_key] = attempts + 1  # Record this processing attempt

                processed, terminal_key = process_article(page, context, article, known_keys)  # Extract post/media
                if processed:  # Metadata was written/refreshed
                    processed_posts += 1  # Increment session total
                    processed_this_iteration += 1  # Increment pass total
                if terminal_key:  # Post is already complete or newly completed
                    finished_session_urls.add(discovery_key)  # Suppress future mounts safely
            except FacebookAuthenticationRequiredError:  # Never swallow manual verification requirement
                raise  # Browser lifecycle will reopen interactive auth
            except Exception as error:  # One malformed/detached post must not terminate export
                try:  # Distinguish real post failure from authentication interruption
                    page = ensure_scraping_profile_ready(page, context)  # Revalidate session
                except FacebookAuthenticationRequiredError:
                    raise  # Recover interactively instead of logging misleading DOM errors
                print(
                    f"{BackgroundColors.YELLOW}Post extraction failed at mounted index "
                    f"{BackgroundColors.CYAN}{index}{BackgroundColors.YELLOW}: "
                    f"{BackgroundColors.CYAN}{error}{Style.RESET_ALL}"
                )  # Log genuine per-post failure

        if new_discovered_this_iteration > 0:  # Feed still reveals unseen canonical owner URLs
            no_new_discovery_scrolls = 0  # Reset stability streak
        else:
            no_new_discovery_scrolls += 1  # Increase end-of-feed confidence

        try:  # Read current geometry before next incremental movement
            scroll_state = page.evaluate(
                """() => ({
                    y: window.scrollY || window.pageYOffset || 0,
                    height: document.documentElement.scrollHeight || document.body.scrollHeight || 0,
                    viewport: window.innerHeight || 0,
                })"""
            )  # Capture scroll geometry
            current_scroll_y = int(scroll_state.get('y') or 0)  # Normalize vertical position
            current_height = int(scroll_state.get('height') or 0)  # Normalize document height
            viewport_height = int(scroll_state.get('viewport') or 0)  # Normalize viewport height
            at_bottom = current_scroll_y + viewport_height >= max(0, current_height - 100)  # Detect current bottom
        except Exception as error:  # Geometry failure may indicate auth/page replacement
            page = ensure_scraping_profile_ready(page, context)  # Raise if authentication-related
            verbose_output(true_string=f"{BackgroundColors.YELLOW}Could not read timeline geometry: {BackgroundColors.CYAN}{error}{Style.RESET_ALL}")
            current_scroll_y = previous_scroll_y  # Preserve previous position
            at_bottom = False  # Continue attempting movement

        pending_retry_count = sum(
            1
            for url, attempts in retry_counts.items()
            if url not in finished_session_urls and attempts < MAX_POST_PROCESS_RETRIES_PER_SESSION
        )  # Report posts that remain retryable during this session

        print(
            f"{BackgroundColors.GREEN}Timeline pass {BackgroundColors.CYAN}{scroll_iteration}"
            f"{BackgroundColors.GREEN}: mounted {BackgroundColors.CYAN}{current_count}"
            f"{BackgroundColors.GREEN}, top-level {BackgroundColors.CYAN}{top_level_count}"
            f"{BackgroundColors.GREEN}, new posts {BackgroundColors.CYAN}{new_discovered_this_iteration}"
            f"{BackgroundColors.GREEN}, processed {BackgroundColors.CYAN}{processed_this_iteration}"
            f"{BackgroundColors.GREEN}, total discovered {BackgroundColors.CYAN}{len(discovered_post_urls)}"
            f"{BackgroundColors.GREEN}, pending retries {BackgroundColors.CYAN}{pending_retry_count}"
            f"{BackgroundColors.GREEN}, no-new streak {BackgroundColors.CYAN}{no_new_discovery_scrolls}/{NO_NEW_POST_SCROLL_LIMIT}"
            f"{Style.RESET_ALL}"
        )  # Provide root-post/discovery-oriented progress

        if no_new_discovery_scrolls >= NO_NEW_POST_SCROLL_LIMIT and (at_bottom or current_scroll_y == previous_scroll_y):  # Require discovery stability plus no further movement
            print(f"{BackgroundColors.GREEN}Timeline end/stability condition reached.{Style.RESET_ALL}")  # Log stop reason
            break  # Stop scrolling

        previous_scroll_y = current_scroll_y  # Preserve position before next movement
        page = ensure_scraping_profile_ready(page, context)  # Revalidate immediately before lazy-load scroll
        try:  # Scroll incrementally to avoid jumping over virtualized post batches
            page.evaluate(f'window.scrollBy(0, {SCROLL_STEP_PX})')  # Advance one controlled feed step
            page.wait_for_timeout(int(SCROLL_PAUSE_SECONDS * 1000))  # Allow new cards/media to mount
        except PlaywrightTimeoutError:  # Timeout should not abort long export
            page = ensure_scraping_profile_ready(page, context)  # Raise if auth challenge appeared
            time.sleep(SCROLL_PAUSE_SECONDS)  # Pause before next pass
        except Exception as error:  # Surface genuine scroll failures
            page = ensure_scraping_profile_ready(page, context)  # Raise instead if auth-related
            print(
                f"{BackgroundColors.YELLOW}Timeline scroll failed: "
                f"{BackgroundColors.CYAN}{error}{Style.RESET_ALL}"
            )  # Log non-auth scroll failure
            time.sleep(SCROLL_PAUSE_SECONDS)  # Allow page to recover

    if not discovered_post_urls:  # A configured profile known to contain posts must never silently succeed with zero discovery
        diagnostics = collect_profile_timeline_diagnostics(page)  # Capture final DOM selector counts
        raise RuntimeError(
            f"No Facebook posts were discovered from {PROFILE_URL}. "
            f"Current URL: {format_url_for_log(get_live_page_url(page))}. "
            f"DOM diagnostics: {diagnostics}. "
            f"The scraper stopped instead of reporting a false successful empty export."
        )  # Surface selector/profile-view failure explicitly

    if processed_posts == 0 and not known_keys:  # Discovery without one successful archive is also a failed run
        diagnostics = collect_profile_timeline_diagnostics(page)
        raise RuntimeError(
            f"Facebook posts were discovered ({len(discovered_post_urls)}), but none could be archived. "
            f"Profile: {PROFILE_DISPLAY_NAME} ({PROFILE_USERNAME}). "
            f"DOM diagnostics: {diagnostics}. "
            f"The run is considered failed instead of reporting a false successful empty export."
        )

    reindex_post_output_directories()  # Apply final oldest-to-newest indexes after new posts are known
    return {
        'saved_posts': processed_posts,
        'known_post_keys': len(known_keys),
        'encountered_post_keys': len(discovered_post_urls),
    }  # Return execution statistics


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
        end="\n",
    )  # Output the welcome message

    start_time = datetime.datetime.now()  # Get the start time of the program
    session = None  # Initialize browser session for safe cleanup
    migrate_flat_post_outputs_to_profile_directory()  # Convert pre-profile flat outputs before resume/counting logic runs
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # Ensure ./Outputs/{ProfileUsername}/ exists even on a clean first run
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
