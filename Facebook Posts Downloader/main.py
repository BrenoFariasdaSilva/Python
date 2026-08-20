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
    3. On the first execution, complete the entire Facebook authentication flow in
       the opened automation browser, including CAPTCHA, 2FA, checkpoints, and prompts.
       The script waits until the authenticated session is stable before continuing.
       That login is retained in ./.browser_profile/.
    4. The script navigates to PROFILE_URL only after authentication is confirmed and
       stores downloaded posts in ./Outputs/.

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
    - Authentication is considered complete only after Facebook session cookies are present,
      no login/challenge UI is detected, and that state remains stable for several seconds.
    - CAPTCHA, 2FA, recovery, checkpoint, and other interactive authentication steps are
      never bypassed; the browser remains open so the user can finish them manually.
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


# Execution Constants:
VERBOSE = False  # Set to True to output verbose messages

# Facebook Constants:
PROFILE_URL = "https://www.facebook.com/BrenoFariasDaSilva"  # Facebook profile containing the posts to download
PROFILE_DISPLAY_NAME = "Breno Farias"  # Display name used to remove author-only lines from title extraction
FACEBOOK_BASE_URL = "https://www.facebook.com/"  # Base URL used to resolve relative Facebook links
BROWSER_CHANNEL = "chrome"  # Prefer the locally installed stable Google Chrome browser
AUTOMATION_PROFILE_DIR = PROJECT_DIR / ".browser_profile"  # Dedicated persistent profile used by Playwright
OUTPUT_DIR = PROJECT_DIR / "Outputs"  # Root directory containing one subdirectory per downloaded post

# Browser Timing Constants:
PAGE_LOAD_TIMEOUT_MS = 60_000  # Maximum time allowed for normal page navigation
LOGIN_WAIT_SECONDS = 0  # Maximum authentication wait in seconds; 0 waits indefinitely until the user finishes every login step
AUTHENTICATION_POLL_SECONDS = 1.0  # Delay between authentication-state checks
AUTHENTICATION_STABLE_SECONDS = 8.0  # Continuous authenticated time required before accepting login as complete
PROFILE_READY_TIMEOUT_SECONDS = 60  # Maximum time to wait for the authenticated profile page to render usable content
SCROLL_PAUSE_SECONDS = 2.0  # Delay after each profile scroll to allow lazy-loaded posts to appear
NO_NEW_POST_SCROLL_LIMIT = 12  # Consecutive scrolls without new posts before the scraper stops
MAX_SCROLL_ITERATIONS = 10_000  # Hard safety limit protecting against endless scrolling
ARTICLE_SETTLE_MS = 350  # Small delay after bringing a post into the viewport
VIDEO_NETWORK_CAPTURE_MS = 2_000  # Time spent collecting video requests after a post becomes visible

# Output Constants:
POST_METADATA_FILENAME = "post.json"  # Metadata file written inside every post directory
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
    re.compile(r"/posts/(\d+)", re.IGNORECASE),
    re.compile(r"[?&]story_fbid=(\d+)", re.IGNORECASE),
    re.compile(r"/videos/(?:[^/]+/)?(\d+)", re.IGNORECASE),
    re.compile(r"[?&]fbid=(\d+)", re.IGNORECASE),
)  # Patterns used to recover stable post identifiers

POST_LINK_HINTS = (
    "/posts/",
    "/permalink/",
    "story_fbid=",
    "/videos/",
    "/photo/",
    "fbid=",
)  # URL fragments that identify likely post permalinks

MESSAGE_SELECTORS = (
    '[data-ad-preview="message"]',
    '[data-ad-comet-preview="message"]',
    'div[dir="auto"]',
)  # Selectors used in order to recover the textual body of each post

ARTICLE_SELECTORS = (
    'div[role="article"]',
    'div[data-pagelet^="FeedUnit_"]',
)  # Selectors used to locate loaded timeline posts

DATE_ELEMENT_SELECTORS = (
    "abbr[data-utime]",
    "time[datetime]",
    "a[aria-label]",
    "a[title]",
)  # Selectors containing likely machine-readable or human-readable post dates

SEE_MORE_TEXTS = (
    "See more",
    "Ver mais",
)  # Localized text labels used to expand truncated Facebook post bodies

LOGIN_URL_HINTS = (
    "/login",
    "/checkpoint",
    "/recover",
    "/two_factor",
    "/auth_platform",
    "/device-based",
    "/confirmemail",
)  # URL fragments indicating that Facebook authentication or account verification is still in progress

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


def extract_post_permalink(article) -> str:
    """
    Extract the most likely canonical permalink from a loaded Facebook post element.

    :param article: Playwright locator representing a Facebook post.
    :return: Normalized post permalink or an empty string.
    """

    candidates = []  # Initialize candidate links

    try:  # Attempt to enumerate links inside the post
        links = article.locator("a[href]")  # Locate every anchor containing an href
        for index in range(links.count()):  # Iterate through loaded anchors
            try:  # Isolate per-anchor extraction failures
                href = links.nth(index).get_attribute("href") or ""  # Read the href attribute
                if not href or not is_probable_post_url(href):  # Ignore unrelated links
                    continue  # Continue to the next anchor

                normalized = normalize_facebook_url(href)  # Normalize the candidate URL
                score = 0  # Initialize a preference score
                lowered = normalized.lower()  # Normalize once for scoring

                if "/posts/" in lowered or "/permalink/" in lowered:  # Prefer explicit post permalinks
                    score += 100  # Assign highest priority
                if "story_fbid=" in lowered:  # Prefer story identifiers
                    score += 95  # Assign near-highest priority
                if "/videos/" in lowered:  # Prefer dedicated video post links
                    score += 90  # Assign high priority
                if "/photo/" in lowered or "fbid=" in lowered:  # Accept photo permalinks as a fallback
                    score += 70  # Assign medium priority
                if PROFILE_URL.lower().rstrip("/") in lowered:  # Prefer links belonging to the configured profile
                    score += 20  # Add profile ownership preference

                candidates.append((score, len(normalized), normalized))  # Store candidate metadata
            except Exception:  # Ignore malformed or detached anchors
                continue  # Continue scanning the remaining links
    except Exception:  # Handle detached or transient post elements
        return ""  # Return empty when link enumeration fails

    if not candidates:  # Verify at least one permalink candidate exists
        return ""  # Return empty when none can be resolved

    candidates.sort(key=lambda item: (-item[0], item[1], item[2]))  # Prefer highest score and shortest canonical URL
    return candidates[0][2]  # Return the strongest candidate


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
    Collect machine-readable and human-readable date strings from a Facebook post.

    :param article: Playwright locator representing a Facebook post.
    :return: Ordered list of distinct date candidates.
    """

    candidates = []  # Initialize date candidate list

    try:  # First inspect likely permalink anchors because they usually carry the post timestamp
        links = article.locator("a[href]")  # Locate anchors inside the post
        for index in range(min(links.count(), 100)):  # Bound work on unexpectedly complex posts
            try:  # Isolate individual link failures
                link = links.nth(index)  # Resolve the current link
                href = link.get_attribute("href") or ""  # Read its target
                if not is_probable_post_url(href):  # Ignore links unrelated to the post timestamp
                    continue  # Continue to the next link
                for attribute in ("aria-label", "title"):  # Inspect date-bearing accessibility attributes
                    value = normalize_whitespace(link.get_attribute(attribute) or "")  # Read and normalize the attribute
                    if value and value not in candidates:  # Preserve unique values only
                        candidates.append(value)  # Store the candidate
                text = normalize_whitespace(link.inner_text(timeout=500))  # Read visible relative/absolute date text
                if text and text not in candidates:  # Preserve unique visible date strings
                    candidates.append(text)  # Store the candidate
            except Exception:  # Ignore transient anchors
                continue  # Continue scanning
    except Exception:  # Continue with generic date elements when anchor enumeration fails
        pass  # No action required

    for selector in DATE_ELEMENT_SELECTORS:  # Inspect generic machine-readable date elements
        try:  # Isolate selector-specific failures
            elements = article.locator(selector)  # Locate matching elements
            for index in range(min(elements.count(), 50)):  # Bound extraction cost
                try:  # Isolate individual element failures
                    element = elements.nth(index)  # Resolve the current element
                    utime = element.get_attribute("data-utime") or ""  # Read Unix timestamp when present
                    datetime_value = element.get_attribute("datetime") or ""  # Read ISO datetime when present
                    aria_label = element.get_attribute("aria-label") or ""  # Read accessibility date label
                    title = element.get_attribute("title") or ""  # Read tooltip date label
                    text = element.inner_text(timeout=300) if element.is_visible() else ""  # Read visible date text

                    for value in (utime, datetime_value, aria_label, title, text):  # Iterate all discovered date forms
                        normalized = normalize_whitespace(value)  # Normalize candidate text
                        if normalized and normalized not in candidates:  # Avoid duplicate candidates
                            candidates.append(normalized)  # Preserve the candidate
                except Exception:  # Ignore detached date elements
                    continue  # Continue to the next element
        except Exception:  # Ignore selectors that no longer match current Facebook markup
            continue  # Continue to the next selector

    return candidates  # Return all collected date candidates


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

    :param page: Facebook profile page.
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


def has_facebook_session_cookie(context: BrowserContext) -> bool:
    """
    Determine whether the browser context contains Facebook's authenticated user cookie.

    :param context: Persistent browser context containing Facebook session state.
    :return: True when a non-empty c_user cookie is available for Facebook.
    """

    try:  # Read only cookies applicable to Facebook without writing or logging their values
        cookies = context.cookies([FACEBOOK_BASE_URL])  # Retrieve Facebook cookies from the persistent context
    except Exception:  # Treat cookie-read failures as unauthenticated instead of guessing
        return False  # Authentication cannot be positively confirmed

    for cookie in cookies:  # Inspect Facebook cookie metadata
        if cookie.get("name") == "c_user" and str(cookie.get("value") or "").strip():  # Verify the authenticated user cookie exists
            return True  # A Facebook user session is present

    return False  # No authenticated user cookie was found


def has_visible_authentication_challenge(page: Page) -> bool:
    """
    Detect visible Facebook login, CAPTCHA, 2FA, or checkpoint controls.

    :param page: Browser page currently involved in Facebook authentication.
    :return: True when an interactive authentication challenge is still visible.
    """

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


def is_facebook_authentication_in_progress(page: Page) -> bool:
    """
    Determine whether Facebook is still showing an authentication or verification flow.

    :param page: Browser page to inspect.
    :return: True when login, CAPTCHA, 2FA, recovery, or checkpoint work is still pending.
    """

    if page.is_closed():  # Verify the user has not closed the automation page
        return True  # A closed page cannot be considered authenticated

    current_url = (page.url or "").lower()  # Normalize the current URL

    if "facebook.com" not in current_url:  # Authentication is not complete while Facebook redirects elsewhere
        return True  # Wait for the flow to return to Facebook

    if any(hint in current_url for hint in LOGIN_URL_HINTS):  # Detect known login/challenge routes
        return True  # Authentication or verification is still in progress

    if has_visible_authentication_challenge(page):  # Detect interactive login/2FA/CAPTCHA controls
        return True  # Wait for the user to finish the challenge

    return False  # No current authentication-flow indicator was found


def is_facebook_authenticated(page: Page, context: BrowserContext) -> bool:
    """
    Positively verify that the current browser session is authenticated to Facebook.

    :param page: Browser page to inspect.
    :param context: Persistent browser context containing Facebook session state.
    :return: True only when a session cookie exists and no authentication flow is active.
    """

    if is_facebook_authentication_in_progress(page):  # Reject login/checkpoint/transient states first
        return False  # Authentication is not complete

    if not has_facebook_session_cookie(context):  # Require Facebook's authenticated-user session cookie
        return False  # Do not infer authentication merely because the login form disappeared

    return True  # Positive session evidence exists and no challenge is visible


def wait_for_facebook_login(page: Page, context: BrowserContext) -> None:
    """
    Wait until the complete Facebook authentication flow is finished and stable.

    The function intentionally waits through password entry, CAPTCHA, 2FA, recovery,
    checkpoints, approval prompts, and intermediate redirects. Authentication is accepted
    only after the session remains positively authenticated for AUTHENTICATION_STABLE_SECONDS.

    :param page: Playwright page displaying the Facebook authentication flow.
    :param context: Persistent browser context containing Facebook session state.
    :return: None
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
    last_status_output = 0.0  # Limit repeated waiting messages

    while deadline is None or time.monotonic() < deadline:  # Wait until authentication is stable or configured timeout expires
        if page.is_closed():  # Detect the user manually closing the controlled page
            raise RuntimeError("The Facebook authentication browser page was closed before authentication completed.")  # Stop with a precise error

        now = time.monotonic()  # Capture one monotonic timestamp for this iteration

        try:  # Authentication state can change repeatedly during CAPTCHA/2FA redirects
            authenticated = is_facebook_authenticated(page, context)  # Positively verify the current state
        except Exception:  # Treat transient browser/DOM errors as an unstable authentication state
            authenticated = False  # Continue waiting instead of advancing early

        if authenticated:  # A candidate authenticated state is currently present
            if authenticated_since is None:  # Start the stability window on the first positive observation
                authenticated_since = now  # Record the beginning of continuous authentication

            stable_for = now - authenticated_since  # Calculate continuous authenticated duration

            if stable_for >= AUTHENTICATION_STABLE_SECONDS:  # Require the state to remain valid across redirects/prompts
                print(
                    f"{BackgroundColors.GREEN}Facebook authentication confirmed and stable for "
                    f"{BackgroundColors.CYAN}{AUTHENTICATION_STABLE_SECONDS:.0f}s{BackgroundColors.GREEN}.{Style.RESET_ALL}"
                )  # Log only after positive stable confirmation
                return  # Continue to the profile only after the full login flow has settled
        else:  # Any challenge, missing cookie, redirect, or transient state invalidates the candidate
            authenticated_since = None  # Restart the stability window after the user finishes the remaining step

        if now - last_status_output >= 15.0:  # Provide occasional progress without flooding the terminal
            current_url = page.url or "<unknown>"  # Read the current browser location without exposing credentials
            print(
                f"{BackgroundColors.YELLOW}Authentication still in progress; waiting for completion. "
                f"{BackgroundColors.GREEN}Current page: {BackgroundColors.CYAN}{current_url}{Style.RESET_ALL}"
            )  # Make it clear the program has intentionally not advanced
            last_status_output = now  # Record the status-output time

        time.sleep(AUTHENTICATION_POLL_SECONDS)  # Poll slowly while the user interacts with Facebook

    raise TimeoutError(
        f"Facebook authentication was not fully completed and stable within {LOGIN_WAIT_SECONDS} seconds."
    )  # Fail only when the user explicitly configures a finite timeout


def wait_for_profile_ready(page: Page, context: BrowserContext) -> None:
    """
    Wait until the authenticated Facebook profile page has rendered usable main/timeline content.

    :param page: Browser page opened at PROFILE_URL.
    :param context: Persistent authenticated browser context.
    :return: None
    """

    deadline = time.monotonic() + PROFILE_READY_TIMEOUT_SECONDS  # Bound post-authentication profile rendering
    target_prefix = PROFILE_URL.lower().rstrip("/")  # Normalize the configured profile URL

    while time.monotonic() < deadline:  # Wait for Facebook's client-rendered profile to become usable
        if page.is_closed():  # Detect manual closure
            raise RuntimeError("The Facebook browser page was closed while waiting for the profile to load.")  # Stop clearly

        if not is_facebook_authenticated(page, context):  # Authentication may be challenged again after navigating to the profile
            print(
                f"{BackgroundColors.YELLOW}Facebook requested additional authentication after profile navigation; "
                f"waiting for completion.{Style.RESET_ALL}"
            )  # Explain why scraping has not started
            wait_for_facebook_login(page, context)  # Wait through the new challenge before continuing
            continue  # Re-evaluate profile readiness afterward

        current_url = (page.url or "").lower().rstrip("/")  # Normalize the current location
        if not current_url.startswith(target_prefix):  # Wait until the configured profile navigation has settled
            time.sleep(AUTHENTICATION_POLL_SECONDS)  # Allow client-side redirects to finish
            continue  # Re-check the URL

        try:  # Verify that Facebook rendered the authenticated profile's main content
            has_main_content = page.locator('div[role="main"]').count() > 0  # Detect the main profile region
            has_timeline_articles = any(page.locator(selector).count() > 0 for selector in ARTICLE_SELECTORS)  # Detect loaded posts

            if has_main_content or has_timeline_articles:  # Either signal proves that the authenticated profile UI rendered
                return  # The page is safe to hand to the scraper
        except Exception:  # Ignore transient client-side rerenders
            pass  # Continue polling until the page stabilizes

        time.sleep(AUTHENTICATION_POLL_SECONDS)  # Wait before checking the rendered profile again

    raise TimeoutError(
        f"Facebook authentication is valid, but the profile did not render usable content within "
        f"{PROFILE_READY_TIMEOUT_SECONDS} seconds. Current URL: {page.url}"
    )  # Do not silently run an empty scraper against an unusable page


def find_existing_facebook_page(context: BrowserContext) -> Page | None:
    """
    Find an existing Facebook page inside a connected browser context.

    :param context: Persistent browser context used by the downloader.
    :return: Existing Facebook page or None.
    """

    profile_prefix = PROFILE_URL.lower().rstrip("/")  # Normalize the configured profile URL

    for page in context.pages:  # Prefer the exact configured profile tab
        try:  # Protect against pages closing during enumeration
            if (page.url or "").lower().rstrip("/").startswith(profile_prefix):  # Match the configured profile
                return page  # Return the already-open profile tab
        except Exception:  # Ignore closed pages
            continue  # Continue scanning

    for page in context.pages:  # Otherwise reuse any authenticated Facebook tab
        try:  # Protect against pages closing during enumeration
            if "facebook.com" in (page.url or "").lower():  # Match a Facebook page
                return page  # Return the existing Facebook tab
        except Exception:  # Ignore closed pages
            continue  # Continue scanning

    return None  # No reusable Facebook page was found


def launch_browser_session(playwright: Playwright) -> BrowserSession:
    """
    Launch the dedicated persistent browser profile used for Facebook automation.

    :param playwright: Active Playwright instance.
    :return: BrowserSession containing the page and context used by the downloader.
    """

    AUTOMATION_PROFILE_DIR.mkdir(parents=True, exist_ok=True)  # Ensure the persistent automation profile exists

    print(
        f"{BackgroundColors.GREEN}Launching persistent automation profile: "
        f"{BackgroundColors.CYAN}{AUTOMATION_PROFILE_DIR.as_posix()}{Style.RESET_ALL}"
    )  # Log the browser profile used by Playwright

    try:  # Prefer the locally installed stable Google Chrome browser
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(AUTOMATION_PROFILE_DIR),
            channel=BROWSER_CHANNEL,
            headless=False,
            no_viewport=True,
            args=["--start-maximized"],
        )  # Launch Chrome with the project's dedicated persistent profile
    except Exception as chrome_error:  # Fall back to Playwright Chromium when stable Chrome cannot be launched
        verbose_output(
            true_string=f"{BackgroundColors.YELLOW}Stable Chrome launch failed: {BackgroundColors.CYAN}{chrome_error}{Style.RESET_ALL}"
        )  # Log the stable Chrome failure only in verbose mode

        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(AUTOMATION_PROFILE_DIR),
            headless=False,
            no_viewport=True,
            args=["--start-maximized"],
        )  # Launch bundled Chromium using the same persistent profile

    page = find_existing_facebook_page(context) or (context.pages[0] if context.pages else context.new_page())  # Resolve the page to control
    return BrowserSession(context=context, page=page)  # Return the locally managed browser session


def navigate_to_profile(page: Page, context: BrowserContext) -> None:
    """
    Authenticate completely, navigate to the configured Facebook profile, and wait until it is usable.

    :param page: Browser page used by the downloader.
    :param context: Persistent browser context containing Facebook authentication state.
    :return: None
    """

    page.set_default_timeout(10_000)  # Configure a conservative default action timeout
    page.set_default_navigation_timeout(PAGE_LOAD_TIMEOUT_MS)  # Configure page navigation timeout

    target_prefix = PROFILE_URL.lower().rstrip("/")  # Normalize configured profile URL
    current_url = (page.url or "").lower().rstrip("/")  # Normalize current page URL

    if "facebook.com" not in current_url:  # Open Facebook first when the persistent browser starts on a blank/non-Facebook page
        page.goto(FACEBOOK_BASE_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)  # Enter Facebook without interrupting a later login flow

    wait_for_facebook_login(page, context)  # Wait through the entire password/CAPTCHA/2FA/checkpoint flow

    current_url = (page.url or "").lower().rstrip("/")  # Re-read the location after authentication finishes
    if not current_url.startswith(target_prefix):  # Navigate to the requested profile only after authentication is stable
        page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)  # Open the configured profile

    if not is_facebook_authenticated(page, context):  # Facebook can request another challenge when the profile is opened
        wait_for_facebook_login(page, context)  # Wait through any additional account verification
        if not (page.url or "").lower().rstrip("/").startswith(target_prefix):  # Return to the profile after the challenge completes
            page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)  # Re-open the configured profile

    wait_for_profile_ready(page, context)  # Require authenticated main/timeline content before scraping begins

    print(
        f"{BackgroundColors.GREEN}Profile loaded and authenticated: {BackgroundColors.CYAN}{PROFILE_URL}{Style.RESET_ALL}"
    )  # Log successful authentication and profile readiness


def load_existing_post_keys() -> set[str]:
    """
    Load identifiers from previously written post.json files so reruns can skip completed posts.

    :param: None
    :return: Set containing known post identifiers and normalized post URLs.
    """

    known_keys = set()  # Initialize existing identifier set

    if not OUTPUT_DIR.exists():  # Verify an output directory already exists
        return known_keys  # Nothing has been downloaded yet

    for metadata_file in OUTPUT_DIR.glob(f"*/{POST_METADATA_FILENAME}"):  # Iterate existing post metadata files
        try:  # Isolate malformed or interrupted metadata files
            with metadata_file.open("r", encoding="utf-8") as file:  # Open metadata safely
                metadata = json.load(file)  # Parse JSON metadata

            post_id = str(metadata.get("post_id") or "").strip()  # Read the stored post identifier
            post_url = normalize_facebook_url(str(metadata.get("post_url") or ""))  # Normalize the stored permalink

            if post_id:  # Preserve stable numeric/hash identifier
                known_keys.add(f"id:{post_id}")  # Store identifier key
            if post_url:  # Preserve permalink as a second deduplication mechanism
                known_keys.add(f"url:{post_url}")  # Store URL key
        except Exception as error:  # A damaged metadata file should be visible but must not abort all downloads
            print(
                f"{BackgroundColors.YELLOW}Skipping unreadable metadata file: "
                f"{BackgroundColors.CYAN}{metadata_file.as_posix()}"
                f"{BackgroundColors.YELLOW} ({error}){Style.RESET_ALL}"
            )  # Log the damaged file

    return known_keys  # Return the discovered keys


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


def collect_image_candidates(article) -> list[dict]:
    """
    Collect likely post images while excluding small avatars, icons, and reaction graphics.

    :param article: Playwright locator representing a Facebook post.
    :return: List of image candidate dictionaries.
    """

    candidates = []  # Initialize image candidate list
    seen_urls = set()  # Track media URLs within the current post

    try:  # Enumerate images currently rendered inside the post
        images = article.locator("img[src]")  # Locate image elements with resolved sources
        for index in range(min(images.count(), 100)):  # Bound work for unusually complex posts
            try:  # Isolate individual image failures
                image = images.nth(index)  # Resolve the current image
                info = image.evaluate(
                    """element => ({
                        src: element.currentSrc || element.src || "",
                        width: element.naturalWidth || element.width || 0,
                        height: element.naturalHeight || element.height || 0,
                        displayWidth: element.clientWidth || 0,
                        displayHeight: element.clientHeight || 0,
                        alt: element.alt || ""
                    })"""
                )  # Read resolved source and intrinsic dimensions

                src = str(info.get("src") or "")  # Normalize media source
                width = int(info.get("width") or 0)  # Normalize intrinsic width
                height = int(info.get("height") or 0)  # Normalize intrinsic height
                display_width = int(info.get("displayWidth") or 0)  # Read rendered width for avatar/icon filtering
                display_height = int(info.get("displayHeight") or 0)  # Read rendered height for avatar/icon filtering
                alt = normalize_whitespace(str(info.get("alt") or ""))  # Normalize alternative text

                if not src.startswith(("http://", "https://")):  # Ignore data/blob/UI sources
                    continue  # Continue to the next image
                if src in seen_urls:  # Ignore duplicate responsive image references
                    continue  # Continue to the next image
                if width < 200 or height < 150:  # Exclude intrinsically tiny icons and reactions
                    continue  # Continue to the next image
                if max(display_width, display_height) < 160:  # Exclude high-resolution avatars rendered as tiny UI elements
                    continue  # Continue to the next image
                if "emoji.php" in src.lower():  # Exclude Facebook emoji rendering endpoints
                    continue  # Continue to the next image

                seen_urls.add(src)  # Mark the image source as discovered
                candidates.append(
                    {
                        "type": "photo",
                        "url": src,
                        "width": width,
                        "height": height,
                        "display_width": display_width,
                        "display_height": display_height,
                        "alt": alt,
                    }
                )  # Store the image candidate
            except Exception:  # Ignore detached image elements
                continue  # Continue to the next image
    except Exception:  # Return what was discovered before a post became detached
        pass  # No further action required

    candidates.sort(key=lambda item: (item["width"] * item["height"]), reverse=True)  # Prefer full-size media before previews
    return candidates  # Return all likely post images


def collect_video_element_candidates(article) -> list[dict]:
    """
    Collect directly resolved HTTP(S) video URLs from video elements inside a Facebook post.

    :param article: Playwright locator representing a Facebook post.
    :return: List of video candidate dictionaries.
    """

    candidates = []  # Initialize video candidate list
    seen_urls = set()  # Track duplicate video sources

    try:  # Enumerate loaded video elements
        videos = article.locator("video")  # Locate post video elements
        for index in range(min(videos.count(), 20)):  # Bound work for posts with embedded galleries
            try:  # Isolate individual video extraction failures
                video = videos.nth(index)  # Resolve the current video
                info = video.evaluate(
                    """element => ({
                        src: element.currentSrc || element.src || "",
                        poster: element.poster || "",
                        width: element.videoWidth || element.clientWidth || 0,
                        height: element.videoHeight || element.clientHeight || 0
                    })"""
                )  # Read the browser-resolved video URL

                src = str(info.get("src") or "")  # Normalize source URL
                if src.startswith(("http://", "https://")) and src not in seen_urls:  # Preserve direct downloadable URLs
                    seen_urls.add(src)  # Mark source as discovered
                    candidates.append(
                        {
                            "type": "video",
                            "url": src,
                            "width": int(info.get("width") or 0),
                            "height": int(info.get("height") or 0),
                        }
                    )  # Store direct video source
            except Exception:  # Ignore detached video elements
                continue  # Continue to the next video
    except Exception:  # Return any already collected direct sources
        pass  # No further action required

    return candidates  # Return direct HTTP(S) video sources


def capture_video_network_candidates(page: Page, article) -> list[dict]:
    """
    Capture likely video media requests triggered while a specific post is visible.

    :param page: Facebook page containing the post.
    :param article: Playwright locator representing the Facebook post.
    :return: List of captured video URL candidates.
    """

    try:  # Avoid listening to unrelated page media when this post contains no video element
        if article.locator("video").count() == 0:  # Verify the current post actually contains video playback
            return []  # Do not capture neighboring autoplay/background media
    except Exception:  # Detached articles cannot provide reliable media attribution
        return []  # Return no network candidates

    captured = []  # Initialize captured response list
    seen_urls = set()  # Track duplicate response URLs

    def handle_response(response: Response) -> None:
        """Collect media-like responses without reading their bodies."""

        try:  # Protect the page event loop from response parsing errors
            url = response.url or ""  # Read the response URL
            if not url.startswith(("http://", "https://")):  # Ignore unsupported response schemes
                return  # Do not process the response

            headers = response.headers  # Read already-available response headers
            content_type = (headers.get("content-type") or "").lower()  # Normalize content type
            resource_type = response.request.resource_type  # Read Playwright resource classification

            if not (
                content_type.startswith("video/")
                or resource_type == "media"
                or (".mp4" in url.lower() and "fbcdn" in url.lower())
            ):  # Keep only likely video responses
                return  # Ignore unrelated traffic

            if url in seen_urls:  # Avoid duplicate range requests for the exact same URL
                return  # Ignore duplicate response
            seen_urls.add(url)  # Mark response URL as captured
            captured.append({"type": "video", "url": url})  # Store the candidate
        except Exception:  # Never allow a response-listener failure to abort browser automation
            return  # Ignore the malformed response

    page.on("response", handle_response)  # Start collecting media traffic

    try:  # Trigger lazy video loading for the current post
        article.scroll_into_view_if_needed(timeout=3_000)  # Bring the post into the viewport
        page.wait_for_timeout(ARTICLE_SETTLE_MS)  # Allow viewport-triggered requests to begin

        videos = article.locator("video")  # Locate videos in the current post
        for index in range(min(videos.count(), 5)):  # Trigger only a few videos per post
            try:  # Isolate browser playback restrictions
                videos.nth(index).evaluate(
                    """element => {
                        element.muted = true;
                        const promise = element.play();
                        if (promise && promise.catch) promise.catch(() => {});
                    }"""
                )  # Ask the browser to start enough playback to resolve network media
            except Exception:  # Playback may be blocked or the element may detach
                continue  # Continue with network traffic already observed

        page.wait_for_timeout(VIDEO_NETWORK_CAPTURE_MS)  # Capture media requests for a bounded interval
    finally:  # Always unregister the listener
        try:  # Protect cleanup when the page closes unexpectedly
            page.remove_listener("response", handle_response)  # Stop collecting responses
        except Exception:  # Ignore listener-cleanup failures
            pass  # No further action required

    return captured  # Return captured media URLs


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
    Download one Facebook media URL using a streaming HTTP request and in-memory browser authentication.

    :param context: Browser context containing the authenticated Facebook session.
    :param page: Browser page used to obtain the current browser User-Agent.
    :param candidate: Media candidate containing type and URL.
    :param output_path_without_extension: Destination path without extension.
    :param referer: Facebook post URL used as the HTTP Referer header.
    :return: Tuple containing saved path and an error string.
    """

    url = str(candidate.get("url") or "").strip()  # Resolve media URL
    media_type = str(candidate.get("type") or "").strip()  # Resolve logical media type

    if not url.startswith(("http://", "https://")):  # Verify direct HTTP(S) media can be requested
        return None, f"Unsupported media URL scheme: {url[:80]}"  # Report unsupported blob/data URLs explicitly

    temporary_path = output_path_without_extension.with_suffix(".download")  # Use a temporary file until validation completes
    session = build_authenticated_requests_session(context, url)  # Build an ephemeral authenticated streaming session

    try:  # Resolve the same User-Agent used by the browser when possible
        user_agent = str(page.evaluate("navigator.userAgent"))  # Read current browser User-Agent
    except Exception:  # Use a normal browser-compatible fallback only if the page is unavailable
        user_agent = "Mozilla/5.0"  # Minimal fallback User-Agent

    headers = {
        "Referer": referer or PROFILE_URL,
        "User-Agent": user_agent,
        "Accept": "*/*",
    }  # Build browser-like request headers without exposing credentials

    try:  # Stream media to disk so large videos do not consume equivalent RAM
        with session.get(
            url,
            headers=headers,
            stream=True,
            allow_redirects=True,
            timeout=(30, 120),
        ) as response:  # Open the media response

            if not 200 <= response.status_code < 300:  # Verify an HTTP success status
                return None, f"HTTP {response.status_code} while downloading {url}"  # Report the server failure

            content_type = (response.headers.get("content-type") or "").split(";", 1)[0].strip().lower()  # Normalize MIME type
            content_length = response.headers.get("content-length", "")  # Read expected size when available
            content_range = response.headers.get("content-range", "")  # Detect partial/range-only video responses

            if media_type == "photo" and content_type and not content_type.startswith("image/"):  # Prevent HTML/error pages from being saved as photos
                return None, f"Unexpected photo Content-Type '{content_type}' for {url}"  # Report MIME mismatch

            if media_type == "video" and content_type and not (
                content_type.startswith("video/") or content_type == "application/octet-stream"
            ):  # Prevent HTML/error pages from being saved as videos
                return None, f"Unexpected video Content-Type '{content_type}' for {url}"  # Report MIME mismatch

            if media_type == "video" and (response.status_code == 206 or content_range):  # Reject isolated byte-range media segments
                return None, f"Facebook exposed only a partial video response ({content_range or 'HTTP 206'}) for {url}"  # Avoid corrupt video files

            if content_length.isdigit() and int(content_length) > MAX_MEDIA_FILE_SIZE_BYTES:  # Enforce configured safety ceiling
                return None, f"Media exceeds {MAX_MEDIA_FILE_SIZE_BYTES} bytes: {url}"  # Skip unexpectedly huge files

            total_written = 0  # Track actual streamed size
            with temporary_path.open("wb") as file:  # Open temporary destination
                for chunk in response.iter_content(chunk_size=1024 * 1024):  # Stream one MiB chunks
                    if not chunk:  # Ignore HTTP keep-alive chunks
                        continue  # Continue streaming
                    total_written += len(chunk)  # Update actual downloaded size
                    if total_written > MAX_MEDIA_FILE_SIZE_BYTES:  # Enforce size ceiling during transfer
                        raise ValueError(f"Downloaded media exceeds {MAX_MEDIA_FILE_SIZE_BYTES} bytes.")  # Abort oversized transfer
                    file.write(chunk)  # Persist chunk immediately

            if total_written == 0:  # Reject empty files
                return None, f"Downloaded media body was empty: {url}"  # Report invalid empty response

            extension = extension_from_response(content_type, str(response.url or url), media_type)  # Resolve final file extension
            output_path = output_path_without_extension.with_suffix(extension)  # Build final media path
            os.replace(temporary_path, output_path)  # Atomically promote completed media file
            return output_path, ""  # Return successful output path
    except Exception as error:  # Capture network and filesystem failures per media item
        return None, str(error)  # Return the error for JSON reporting
    finally:  # Always clean temporary resources
        try:  # Remove incomplete temporary downloads
            if temporary_path.exists():  # Verify a partial file remains
                temporary_path.unlink()  # Delete the partial file
        except Exception:  # Cleanup failure should not hide the original download result
            pass  # No further action required
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
    Extract and download one loaded Facebook post.

    :param page: Facebook profile page.
    :param context: Authenticated browser context.
    :param article: Playwright locator representing the post.
    :param known_keys: Cross-run and current-run deduplication keys.
    :return: Tuple containing whether a new post was saved and its primary key.
    """

    try:  # Bring the post into view before reading lazy-loaded media
        article.scroll_into_view_if_needed(timeout=3_000)  # Ensure the post and media are mounted
        page.wait_for_timeout(ARTICLE_SETTLE_MS)  # Allow the DOM to settle
    except Exception:  # A detached article will be retried naturally during later scrolling
        return False, ""  # Report no saved post

    post_url = extract_post_permalink(article)  # Resolve the most likely permalink
    if not post_url:  # Reject nested comments/UI articles that do not expose a supported post permalink
        return False, ""  # Only top-level post-like containers should be archived
    content = extract_post_content(article)  # Extract post body
    post_date, date_raw = resolve_post_date(article)  # Resolve exact or relative post date
    if post_date is None and post_url:  # Use a dedicated post page only when the timeline card lacks a safe date
        post_date, date_raw = resolve_post_date_from_permalink(context, post_url)  # Retry date extraction from permalink
    post_id = extract_post_id(post_url)  # Extract stable numeric identifier

    if not post_id:  # Build a deterministic key for URL formats without numeric identifiers
        post_id = build_fallback_post_key(post_url, content, date_raw)  # Generate fallback identifier

    post_keys = build_post_keys(post_id, post_url)  # Build deduplication keys
    if post_keys and post_keys.intersection(known_keys):  # Skip posts already completed in a previous or current run
        return False, next(iter(post_keys))  # Return one key for diagnostics

    if post_date is None:  # Never create an incorrect date-based directory
        print(
            f"{BackgroundColors.YELLOW}Skipping post because its date could not be resolved safely: "
            f"{BackgroundColors.CYAN}{post_url or post_id}{Style.RESET_ALL}"
        )  # Log explicit date-resolution failure
        return False, f"id:{post_id}"  # Return its key so the caller can observe the post was encountered

    title = derive_post_title(content, post_id)  # Derive requested directory title
    post_dir = choose_post_output_directory(post_date, title, post_id)  # Resolve collision-safe output path
    post_dir.mkdir(parents=True, exist_ok=True)  # Create the post directory before downloading media

    image_candidates = collect_image_candidates(article)  # Collect rendered post images
    direct_video_candidates = collect_video_element_candidates(article)  # Collect directly exposed video URLs
    network_video_candidates = capture_video_network_candidates(page, article)  # Capture lazy media requests
    media_candidates = deduplicate_media_candidates(image_candidates + direct_video_candidates + network_video_candidates)  # Merge media sources

    media_results = []  # Initialize downloaded media metadata
    counters = {"photo": 0, "video": 0}  # Track deterministic filenames by media type

    for candidate in media_candidates:  # Download each discovered media source
        media_type = candidate["type"]  # Read logical media type
        if media_type not in counters:  # Ignore unexpected media categories
            continue  # Continue to the next candidate

        counters[media_type] += 1  # Allocate the next deterministic media number
        filename_prefix = "photo" if media_type == "photo" else "video"  # Resolve filename prefix
        output_without_extension = post_dir / f"{filename_prefix}_{counters[media_type]:03d}"  # Build destination stem

        saved_path, error = download_media(
            context,
            page,
            candidate,
            output_without_extension,
            post_url or PROFILE_URL,
        )  # Stream media using in-memory authentication from the browser context

        media_result = {
            "type": media_type,
            "source_url": candidate.get("url", ""),
            "filename": saved_path.name if saved_path else None,
            "downloaded": saved_path is not None,
            "error": error or None,
        }  # Build transparent per-media result

        if candidate.get("width"):  # Preserve source width when known
            media_result["width"] = candidate["width"]  # Store width
        if candidate.get("height"):  # Preserve source height when known
            media_result["height"] = candidate["height"]  # Store height
        if candidate.get("display_width") is not None:  # Preserve rendered width when known
            media_result["display_width"] = candidate.get("display_width")  # Store rendered width
        if candidate.get("display_height") is not None:  # Preserve rendered height when known
            media_result["display_height"] = candidate.get("display_height")  # Store rendered height
        if candidate.get("alt"):  # Preserve source alternative text when known
            media_result["alt"] = candidate["alt"]  # Store alt text

        media_results.append(media_result)  # Preserve download outcome

        if saved_path:  # Log successful media downloads
            print(
                f"{BackgroundColors.GREEN}Downloaded {media_type}: "
                f"{BackgroundColors.CYAN}{saved_path.relative_to(PROJECT_DIR).as_posix()}{Style.RESET_ALL}"
            )  # Output saved path
        else:  # Log media failures without aborting the post
            print(
                f"{BackgroundColors.YELLOW}Failed {media_type}: "
                f"{BackgroundColors.CYAN}{candidate.get('url', '')}"
                f"{BackgroundColors.YELLOW} ({error}){Style.RESET_ALL}"
            )  # Output failure reason

    metadata = {
        "post_id": post_id,
        "post_url": post_url or None,
        "profile_url": PROFILE_URL,
        "date": post_date.date().isoformat(),
        "datetime": post_date.isoformat(),
        "date_raw": date_raw or None,
        "title": title,
        "content": content,
        "output_directory": post_dir.relative_to(PROJECT_DIR).as_posix(),
        "media_count": len(media_results),
        "downloaded_media_count": sum(1 for item in media_results if item["downloaded"]),
        "failed_media_count": sum(1 for item in media_results if not item["downloaded"]),
        "media": media_results,
        "scraped_at": datetime.datetime.now().astimezone().isoformat(),
    }  # Build complete per-post metadata

    write_post_metadata(post_dir, metadata)  # Persist metadata after media attempts
    known_keys.update(post_keys)  # Mark the post completed only after metadata is written

    print(
        f"{BackgroundColors.GREEN}Saved post: "
        f"{BackgroundColors.CYAN}{post_dir.relative_to(PROJECT_DIR).as_posix()}{Style.RESET_ALL}"
    )  # Log completed post

    return True, f"id:{post_id}"  # Report successful new post


def scroll_profile_and_download(page: Page, context: BrowserContext) -> dict:
    """
    Scroll the configured Facebook profile and download every newly discovered post.

    :param page: Facebook profile page.
    :param context: Authenticated browser context.
    :return: Execution statistics.
    """

    if not is_facebook_authenticated(page, context):  # Refuse to scrape if Facebook authentication is no longer valid
        raise RuntimeError("Facebook authentication is not valid at the start of timeline processing.")  # Prevent misleading zero-post runs

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # Ensure the output root exists
    known_keys = load_existing_post_keys()  # Load cross-run deduplication state

    saved_posts = 0  # Count posts saved during this execution
    encountered_posts = set()  # Track current-run post elements/keys
    no_new_scrolls = 0  # Track consecutive scrolls without new content
    previous_scroll_height = 0  # Track document height for end-of-feed detection

    print(
        f"{BackgroundColors.GREEN}Previously downloaded post keys: "
        f"{BackgroundColors.CYAN}{len(known_keys)}{Style.RESET_ALL}"
    )  # Log resume state

    for scroll_iteration in range(1, MAX_SCROLL_ITERATIONS + 1):  # Scroll until the timeline reaches a stable end
        articles = get_article_locator(page)  # Resolve currently mounted timeline posts
        current_count = articles.count()  # Count loaded/mounted posts
        new_this_iteration = 0  # Track new posts found before this scroll

        verbose_output(
            true_string=f"{BackgroundColors.GREEN}Scroll {BackgroundColors.CYAN}{scroll_iteration}"
            f"{BackgroundColors.GREEN}: mounted posts = {BackgroundColors.CYAN}{current_count}{Style.RESET_ALL}"
        )  # Output verbose scroll diagnostics

        for index in range(current_count):  # Process every currently mounted post before Facebook virtualizes it away
            try:  # Isolate individual post failures
                article = articles.nth(index)  # Resolve current post locator
                post_url = extract_post_permalink(article)  # Build a cheap pre-processing identity
                preliminary_id = extract_post_id(post_url)  # Extract fast numeric identifier when available
                preliminary_key = f"id:{preliminary_id}" if preliminary_id else (f"url:{post_url}" if post_url else "")  # Build fast key

                if preliminary_key and preliminary_key in encountered_posts:  # Avoid repeatedly processing the same mounted post
                    continue  # Continue to the next post

                saved, processed_key = process_article(page, context, article, known_keys)  # Extract and persist the post
                if preliminary_key:  # Mark cheap identity as encountered
                    encountered_posts.add(preliminary_key)  # Store current-run identity
                if processed_key:  # Mark final identity as encountered
                    encountered_posts.add(processed_key)  # Store final identity

                if saved:  # Count newly persisted posts
                    saved_posts += 1  # Increment total saved posts
                    new_this_iteration += 1  # Increment iteration count
            except Exception as error:  # One malformed post must not terminate the entire timeline export
                print(
                    f"{BackgroundColors.YELLOW}Post extraction failed at mounted index "
                    f"{BackgroundColors.CYAN}{index}{BackgroundColors.YELLOW}: "
                    f"{BackgroundColors.CYAN}{error}{Style.RESET_ALL}"
                )  # Log the post-level error
                continue  # Continue to the next post

        if new_this_iteration > 0:  # Reset stability counter when new posts were saved
            no_new_scrolls = 0  # New timeline content is still being discovered
        else:  # No new posts were saved during this pass
            no_new_scrolls += 1  # Increase end-of-feed confidence

        try:  # Read current page height before scrolling
            current_scroll_height = int(page.evaluate("document.documentElement.scrollHeight"))  # Capture loaded document height
        except Exception:  # Use zero if Facebook is navigating unexpectedly
            current_scroll_height = 0  # Reset height observation

        print(
            f"{BackgroundColors.GREEN}Timeline pass {BackgroundColors.CYAN}{scroll_iteration}"
            f"{BackgroundColors.GREEN}: new posts {BackgroundColors.CYAN}{new_this_iteration}"
            f"{BackgroundColors.GREEN}, total saved {BackgroundColors.CYAN}{saved_posts}"
            f"{BackgroundColors.GREEN}, no-new streak {BackgroundColors.CYAN}{no_new_scrolls}/{NO_NEW_POST_SCROLL_LIMIT}{Style.RESET_ALL}"
        )  # Provide visible progress

        if no_new_scrolls >= NO_NEW_POST_SCROLL_LIMIT and current_scroll_height <= previous_scroll_height:  # Confirm both content and height stabilized
            print(f"{BackgroundColors.GREEN}Timeline end/stability condition reached.{Style.RESET_ALL}")  # Log stop reason
            break  # Stop scrolling

        previous_scroll_height = max(previous_scroll_height, current_scroll_height)  # Preserve maximum observed document height

        try:  # Scroll close to the bottom to trigger Facebook lazy loading
            page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")  # Move to the current timeline bottom
            page.wait_for_timeout(int(SCROLL_PAUSE_SECONDS * 1000))  # Wait for the next post batch
        except PlaywrightTimeoutError:  # A timeout should not immediately abort a long export
            time.sleep(SCROLL_PAUSE_SECONDS)  # Pause before another extraction attempt
        except Exception as error:  # Surface unexpected scroll failures
            print(
                f"{BackgroundColors.YELLOW}Timeline scroll failed: "
                f"{BackgroundColors.CYAN}{error}{Style.RESET_ALL}"
            )  # Log the failure
            time.sleep(SCROLL_PAUSE_SECONDS)  # Allow the page to recover

    return {
        "saved_posts": saved_posts,
        "known_post_keys": len(known_keys),
        "encountered_post_keys": len(encountered_posts),
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
        end="\n\n",
    )  # Output the welcome message

    start_time = datetime.datetime.now()  # Get the start time of the program
    session = None  # Initialize browser session for safe cleanup

    try:  # Execute the complete Facebook export workflow
        with sync_playwright() as playwright:  # Start Playwright runtime
            session = launch_browser_session(playwright)  # Launch the persistent automation browser
            navigate_to_profile(session.page, session.context)  # Complete authentication and open the configured Facebook profile
            statistics = scroll_profile_and_download(session.page, session.context)  # Download discovered posts

            print(
                f"\n{BackgroundColors.GREEN}Saved posts this run: "
                f"{BackgroundColors.CYAN}{statistics['saved_posts']}\n"
                f"{BackgroundColors.GREEN}Known post keys after run: "
                f"{BackgroundColors.CYAN}{statistics['known_post_keys']}{Style.RESET_ALL}"
            )  # Output export statistics

            close_browser_session(session)  # Close the persistent automation browser
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
