"""
================================================================================
Video Audio Track Switcher
================================================================================
Author      : Breno Farias da Silva
Created     : 2025-10-26
Description :
   This script recursively searches for video files in the specified input directory
   and processes their audio tracks: keeps only tracks in desired languages (from DESIRED_LANGUAGES),
   sets the default audio track to English if available, otherwise the first desired track.
   Undesired audio tracks are automatically removed.

   Key features include:
      - Recursive search for video files with specified extensions
      - Automatic detection and filtering of audio tracks by desired languages
      - Removal of undesired audio tracks
      - Setting the default audio track to English if available
      - Progress bar visualization for processing
      - Integration with ffmpeg for audio track manipulation

Usage:
   1. Set the INPUT_DIR constant to the folder containing your video files.
   2. Modify DESIRED_LANGUAGES to include the languages you want to keep.
   3. Execute the script:
         $ python main.py
   4. The script will automatically keep only desired language tracks and set English as default if present.

Outputs:
   - Video files in the same directory with only desired language audio tracks, English set as default if present

TODOs:
   - Add a dry-run mode to preview changes without modifying files
   - Add logging of processed files and errors
   - Allow customization of default language priority
   - Optimize for batch operations

Dependencies:
   - Python >= 3.9
   - colorama
   - tqdm
   - ffmpeg and ffprobe installed and available in PATH

Assumptions & Notes:
   - Each video file has at least one audio track
   - Videos are writable in-place
   - Tested on macOS, Linux, and Windows with ffmpeg/ffprobe available
   - Original file is replaced by the processed file
"""


import argparse  # For parsing command-line arguments
import atexit  # For playing a sound when the program finishes
import json  # For parsing JSON output from ffprobe
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For text normalization with regular expressions
import shutil  # For checking if a command exists
import signal  # For temporarily ignoring SIGINT during tqdm construction
import subprocess  # For running terminal commands
import unicodedata  # For removing accents during normalization
from colorama import Style  # For coloring the terminal
from tqdm import tqdm  # For displaying a progress bar


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
INPUT_DIR = "./Input/"  # Root directory to search for videos
VIDEO_FILE_EXTENSIONS = [".mkv", ".mp4", ".avi"]  # List of video file extensions to process
IGNORE_DIRS = ["Backup"]  # List of directory name keywords to ignore (case-insensitive)
IGNORE_FILE_PATTERNS = [
    ".tmp",  # Common temporary file marker
    ".part",  # Partial download extension
    ".partial",  # Partial download extension variant
    ".!ut",  # uTorrent temporary marker
    ".temp",  # Generic temp substring
]  # Substring patterns for incomplete/temporary files (case-insensitive)

# These will be set by command-line arguments in main()
REMOVE_OTHER_AUDIO_TRACKS = True  # Set to True to remove other audio tracks after setting the default
REMOVE_OTHER_SUBTITLE_TRACKS = True  # Set to True to remove other subtitle tracks
REMOVE_DESCRIPTIVE_STREAMS = True  # If True, remove descriptive/SDH streams (audio and subtitles) before selection

STREAM_TYPE_PRIORITY_ORDER = {
    "audio": ["English", "Portuguese"],  # Priority for audio tracks (English first)
    "subtitle": ["Portuguese", "English"],  # Priority for subtitle tracks (Portuguese first, then English)
}  # Desired languages in order of priority for each stream type

DESIRED_LANGUAGES = {  # Dictionary of desired languages with their corresponding language codes (case-insensitive)
    "English": ["english", "eng", "en",  "Inglês"],  # Languages to prioritize when selecting default audio track
    "Brazilian Portuguese": ["PT-BR FULL", "brazilian", "portuguese", "COMPLETA PT-BR", "PT-BR COMPLETA", "Português (Brasil)", "pt-br", "PT-BR FORCED", "pt"],  # Additional languages can be added here
}

UNDESIRED_LANGUAGES = {  # Dictionary of undesired languages with their corresponding language codes (case-insensitive)
    "Arabic": ["arabic", "ara", "ar", "ar-sa", "العربية"],
    "Bulgarian": ["bulgarian", "bul", "bg", "bg-bg", "български"],
    "Chinese Simplified": ["chinese", "chi", "zho", "zh", "zh-cn", "chs", "simplified chinese", "中文", "简体中文"],
    "Chinese Traditional": ["cht", "zh-tw", "traditional chinese", "繁體中文"],
    "Croatian": ["croatian", "hrv", "hr", "hr-hr", "hrvatski"],
    "Czech": ["czech", "cze", "ces", "cs", "cs-cz", "čeština"],
    "Danish": ["danish", "dan", "da", "da-dk", "dansk"],
    "Dutch": ["dutch", "nld", "nl", "nl-nl", "nederlands"],
    "Estonian": ["estonian", "est", "et", "et-ee", "eesti"],
    "Filipino": ["filipino", "fil", "tl", "tagalog", "tl-ph"],
    "Finnish": ["finnish", "fin", "fi", "fi-fi", "suomi"],
    "French": ["french", "fre", "fra", "fr", "fr-fr", "français"],
    "German": ["german", "ger", "deu", "de", "de-de", "deutsch"],
    "Greek": ["greek", "ell", "gre", "el", "el-gr", "ελληνικά"],
    "Hebrew": ["hebrew", "heb", "he", "he-il", "עברית"],
    "Hindi": ["hindi", "hin", "hi", "hi-in", "हिन्दी"],
    "Hungarian": ["hungarian", "hun", "hu", "hu-hu", "magyar"],
    "Indonesian": ["indonesian", "ind", "id", "id-id", "bahasa indonesia"],
    "Italian": ["italian", "ita", "it", "it-it", "italiano"],
    "Japanese": ["japanese", "jpn", "ja", "ja-jp", "日本語"],
    "Korean": ["korean", "kor", "ko", "ko-kr", "한국어"],
    "Latvian": ["latvian", "lav", "lv", "lv-lv", "latviešu"],
    "Lithuanian": ["lithuanian", "lit", "lt", "lt-lt", "lietuvių"],
    "Malay": ["malay", "msa", "may", "ms", "ms-my", "bahasa melayu"],
    "Norwegian": ["norwegian", "nor", "no", "nb", "nn", "no-no", "norsk"],
    "Persian": ["persian", "farsi", "fas", "per", "fa", "fa-ir", "فارسی"],
    "Polish": ["polish", "pol", "pl", "pl-pl", "polski"],
    "Romanian": ["romanian", "rum", "ron", "ro", "ro-ro", "română"],
    "Russian": ["russian", "rus", "ru", "ru-ru", "русский"],
    "Serbian": ["serbian", "srp", "sr", "sr-rs", "српски"],
    "Slovak": ["slovak", "slk", "slo", "sk", "sk-sk", "slovenčina"],
    "Slovenian": ["slovenian", "slv", "sl", "sl-si", "slovenščina"],
    "Spanish": ["spanish", "spa", "es", "es-es", "es-la", "latam", "castellano", "español"],
    "Swedish": ["swedish", "swe", "sv", "sv-se", "svenska"],
    "Thai": ["thai", "tha", "th", "th-th", "ไทย"],
    "Turkish": ["turkish", "tur", "tr", "tr-tr", "türkçe"],
    "Ukrainian": ["ukrainian", "ukraine", "ukr", "ua", "uk", "uk-ua", "українська"],
    "Vietnamese": ["vietnamese", "vie", "vi", "vi-vn", "tiếng việt"],
}

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


def get_desired_languages():
    """
    Get a flat list of all desired languages from DESIRED_LANGUAGES.

    :return: List of desired language codes
    """

    return [lang for langs in DESIRED_LANGUAGES.values() for lang in langs]  # Flatten the list of desired languages


def normalize_text(value):
    """
    Normalize text for robust language matching across inconsistent metadata.

    :param value: Raw metadata text
    :return: Normalized text
    """

    text = "" if value is None else str(value)  # Convert input to string safely
    text = text.lower()  # Convert text to lowercase
    text = unicodedata.normalize("NFKD", text)  # Normalize Unicode text for accent stripping
    text = "".join(ch for ch in text if not unicodedata.combining(ch))  # Remove combining accent marks
    text = re.sub(r"\b\d+(\.\d+)?\b", " ", text)  # Remove audio quality numeric markers such as 5.1 and 7.1
    text = re.sub(r"[\(\)\[\]\-_]", " ", text)  # Replace extra symbols with spaces
    text = re.sub(r"\s+", " ", text).strip()  # Normalize consecutive whitespace
    return text  # Return normalized text


def get_normalized_desired_language_aliases():
    """
    Build normalized language alias lists from DESIRED_LANGUAGES.

    :param none
    :return: Dict with canonical language key and normalized aliases
    """

    normalized_aliases = {}  # Initialize mapping for canonical language aliases
    for language_key, aliases in DESIRED_LANGUAGES.items():  # Iterate each canonical language and aliases
        ordered_aliases = []  # Initialize ordered alias container for this language
        seen_aliases = set()  # Initialize set to avoid duplicate aliases
        key_alias = normalize_text(language_key)  # Normalize canonical language key as an alias
        if key_alias != "" and key_alias not in seen_aliases:  # Verify canonical alias is valid and unique
            ordered_aliases.append(key_alias)  # Add canonical normalized key alias
            seen_aliases.add(key_alias)  # Mark canonical alias as seen
        for alias in aliases:  # Iterate configured aliases for this language
            normalized_alias = normalize_text(alias)  # Normalize alias text with the same pipeline
            if normalized_alias == "":  # Verify alias is not empty after normalization
                continue  # Continue to next alias when normalized alias is empty
            if normalized_alias in seen_aliases:  # Verify alias has not already been added
                continue  # Continue to next alias when alias is duplicated
            ordered_aliases.append(normalized_alias)  # Add normalized alias preserving order
            seen_aliases.add(normalized_alias)  # Mark normalized alias as seen
        normalized_aliases[language_key] = ordered_aliases  # Save normalized alias list for canonical key
    return normalized_aliases  # Return normalized alias mapping


def detect_language(raw_lang, raw_title, stream_type):
    """
    Detect canonical language name from raw language/title metadata.

    :param raw_lang: Raw language metadata from tags
    :param raw_title: Raw title metadata from tags
    :param stream_type: Stream type key ('audio' or 'subtitle')
    :return: Canonical language key from DESIRED_LANGUAGES or None
    """

    normalized_lang = normalize_text(raw_lang)  # Normalize raw language text
    normalized_title = normalize_text(raw_title)  # Normalize raw title text
    values = [normalized_lang, normalized_title]  # Build candidate normalized values list
    normalized_aliases = get_normalized_desired_language_aliases()  # Build normalized desired language aliases
    priority_names = resolve_priority_list(stream_type)  # Resolve configured priority names for stream type
    ordered_languages = []  # Initialize ordered canonical language list
    for language_name in priority_names:  # Iterate language names in configured priority order
        if language_name in DESIRED_LANGUAGES and language_name not in ordered_languages:  # Verify canonical priority language exists and is unique
            ordered_languages.append(language_name)  # Add priority language to ordered scan list
    for language_name in DESIRED_LANGUAGES.keys():  # Iterate remaining canonical desired languages
        if language_name not in ordered_languages:  # Verify language was not already inserted by priority
            ordered_languages.append(language_name)  # Add remaining language after priority languages
    for language_name in ordered_languages:  # Iterate canonical language names in deterministic order
        aliases = normalized_aliases.get(language_name, [])  # Get normalized aliases for current language
        for alias in aliases:  # Iterate aliases for this canonical language
            if alias == "":  # Verify alias is not empty
                continue  # Continue to next alias if empty
            for value in values:  # Iterate normalized metadata values
                if value == "":  # Verify current value has content
                    continue  # Continue to next value when empty
                if alias in value:  # Verify alias appears in normalized metadata
                    return language_name  # Return detected canonical language immediately
    return None  # Return None when no canonical language match is found


def install_chocolatey():
    """
    Installs Chocolatey on Windows if it is not already installed.

    :param none
    :return: None
    """

    if shutil.which("choco") is not None:  # Chocolatey already installed
        verbose_output(f"{BackgroundColors.GREEN}Chocolatey is already installed.{Style.RESET_ALL}")
        return

    print(
        f"{BackgroundColors.GREEN}Installing {BackgroundColors.CYAN}Chocolatey{BackgroundColors.GREEN} via {BackgroundColors.CYAN}PowerShell{BackgroundColors.GREEN}...{Style.RESET_ALL}"
    )

    command = (  # PowerShell command to install Chocolatey
        "powershell -NoProfile -InputFormat None -ExecutionPolicy Bypass -Command "
        '"Set-ExecutionPolicy Bypass -Scope Process -Force; '
        "[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; "
        "iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))\""
    )

    os.system(command)  # Run the command to install Chocolatey


def install_ffmpeg_and_ffprobe():
    """
    Installs ffmpeg and ffprobe according to the OS.

    :param none
    :return: None
    """

    current_os = platform.system()  # Get the current operating system

    verbose_output(
        f"{BackgroundColors.GREEN}Installing ffmpeg and ffprobe in the current operating system: {BackgroundColors.CYAN}{current_os}{Style.RESET_ALL}"
    )  # Output the verbose message

    if (
        shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
    ):  # If ffmpeg and ffprobe are already installed
        verbose_output(
            f"{BackgroundColors.GREEN}ffmpeg and ffprobe are already installed.{Style.RESET_ALL}"
        )  # Output the verbose message
        return  # Exit the function

    if current_os == "Darwin":  # MacOS
        print(
            f"{BackgroundColors.GREEN}Installing {BackgroundColors.CYAN}ffmpeg and ffprobe{BackgroundColors.GREEN} via {BackgroundColors.CYAN}Homebrew{BackgroundColors.GREEN}...{Style.RESET_ALL}"
        )
        os.system("brew install ffmpeg")  # Install ffmpeg (includes ffprobe) via Homebrew
    elif current_os == "Linux":  # Linux
        print(
            f"{BackgroundColors.GREEN}Installing {BackgroundColors.CYAN}ffmpeg and ffprobe{BackgroundColors.GREEN} via {BackgroundColors.CYAN}apt{BackgroundColors.GREEN}...{Style.RESET_ALL}"
        )
        os.system("sudo apt update -y && sudo apt install -y ffmpeg")  # Install ffmpeg (includes ffprobe) via apt
    elif current_os == "Windows":  # Windows via Chocolatey
        if shutil.which("choco") is None:  # If Chocolatey is not installed
            install_chocolatey()  # Install Chocolatey first
        print(
            f"{BackgroundColors.GREEN}Installing {BackgroundColors.CYAN}ffmpeg and ffprobe{BackgroundColors.GREEN} via {BackgroundColors.CYAN}Chocolatey{BackgroundColors.GREEN}...{Style.RESET_ALL}"
        )
        subprocess.run(
            ["choco", "install", "ffmpeg", "-y"], check=True
        )  # Install ffmpeg (includes ffprobe) via Chocolatey
    else:  # Unsupported OS
        print(
            f"{BackgroundColors.RED}Unsupported OS for automatic ffmpeg installation.{Style.RESET_ALL}"
        )  # Output the error message
        return  # Exit the function

    if (
        shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None
    ):  # If ffmpeg and ffprobe were successfully installed
        print(
            f"{BackgroundColors.GREEN}ffmpeg and ffprobe installed successfully.{Style.RESET_ALL}"
        )  # Output the success message
    else:  # If the installation failed
        print(
            f"{BackgroundColors.RED}Failed to install ffmpeg and ffprobe. Please install them manually.{Style.RESET_ALL}"
        )  # Output the error message


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


def should_ignore_directory(dirpath):
    """
    Determine whether the directory should be ignored based on IGNORE_DIRS.

    :param dirpath: Path to the directory to evaluate
    :return: True if the directory name contains any IGNORE_DIRS keyword (case-insensitive), False otherwise
    """

    dirname = os.path.basename(dirpath)  # Get the directory name from the full path
    lower_name = dirname.lower()  # Normalize to lowercase for case-insensitive matching
    for keyword in IGNORE_DIRS:  # Iterate configured ignore keywords
        if keyword.lower() in lower_name:  # Check for substring-based, case-insensitive match
            verbose_output(
                f"{BackgroundColors.YELLOW}Ignoring directory: {BackgroundColors.CYAN}{dirpath}{BackgroundColors.YELLOW} (matches IGNORE_DIRS keyword '{keyword}'){Style.RESET_ALL}"
            )  # Verbose message explaining why the directory is ignored
            return True  # Indicate the directory should be ignored
    return False  # Indicate the directory should not be ignored


def should_ignore_file(filename):
    """
    Determine whether the file should be ignored based on IGNORE_FILE_PATTERNS.

    :param filename: Name of the file to evaluate
    :return: True if the filename ends with any IGNORE_FILE_PATTERNS extension (case-insensitive), False otherwise
    """

    lower_name = filename.lower()  # Normalize filename to lowercase for case-insensitive matching
    for pattern in IGNORE_FILE_PATTERNS:  # Iterate configured ignore file patterns
        lower_pattern = pattern.lower()  # Normalize pattern to lowercase for case-insensitive comparison
        if lower_name.endswith(lower_pattern):  # Verify filename ends with the extension pattern
            verbose_output(
                f"{BackgroundColors.YELLOW}Skipping temporary/incomplete file: {BackgroundColors.CYAN}{filename}{BackgroundColors.YELLOW} (matches pattern '{pattern}'){Style.RESET_ALL}"
            )  # Verbose message explaining why file is skipped
            return True  # Indicate the file should be ignored

    return False  # Indicate the file should not be ignored


def create_progress_bar(iterable, **kwargs):
    """
    Safely create and return a tqdm progress bar for the given iterable.

    This factory isolates tqdm construction to prevent KeyboardInterrupt from
    interrupting tqdm.__init__ (which can leave a partially-initialized
    tqdm instance whose destructor raises AttributeError). The factory:
       - Temporarily ignores SIGINT while constructing the tqdm instance.
       - Catches any exception raised during construction and returns None.
       - Restores the original SIGINT handler in all cases.

    :param iterable: Iterable or sequence to wrap with a progress bar
    :param kwargs: Keyword arguments forwarded to ``tqdm`` constructor
    :return: A fully constructed ``tqdm`` instance or ``None`` on failure
    """

    prev_handler = None  # Save holder for previous SIGINT handler
    try:
        prev_handler = signal.getsignal(signal.SIGINT)  # Save previous SIGINT handler
        signal.signal(signal.SIGINT, signal.SIG_IGN)  # Ignore SIGINT during construction
    except Exception:  # If signal operations are unsupported, continue without changing handler
        prev_handler = None  # Ensure prev_handler exists even if saving failed

    try:
        try:
            bar = tqdm(iterable, **kwargs)  # Attempt to construct tqdm while SIGINT is ignored
        except Exception:  # Catch any error during tqdm construction
            verbose_output(
                f"{BackgroundColors.YELLOW}tqdm initialization failed, falling back to simple iteration.{Style.RESET_ALL}"
            )  # Verbose message when tqdm cannot be created
            return None  # Return None to indicate construction failure
    finally:
        if prev_handler is not None:  # Only attempt restore if previous handler was saved
            try:
                signal.signal(signal.SIGINT, prev_handler)  # Restore original SIGINT handler
            except Exception:
                pass  # Ignore restore errors to avoid masking earlier exceptions

    return bar  # Return the successfully constructed progress bar


def find_videos(input_dir, extensions):
    """
    Recursively find all videos in the input directory with specified extensions.

    :param input_dir: Root directory
    :param extensions: List of video file extensions
    :return: List of video file paths
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Searching for video files in the directory: {BackgroundColors.CYAN}{input_dir}{Style.RESET_ALL}"
    )  # Output the verbose message

    videos = []  # List to store video file paths

    for root, dirs, files in os.walk(input_dir):  # Walk through the directory
        if should_ignore_directory(root):  # Skip entire directory and its subdirectories if it matches IGNORE_DIRS
            dirs[:] = []  # Prevent descending into subdirectories under the ignored directory
            continue  # Continue to next iteration so no files in this directory are processed
        for file in files:  # For each file in the directory
            if should_ignore_file(file):  # Skip files that match temporary/incomplete patterns
                continue  # Continue to next file without adding to the list
            if any(file.lower().endswith(ext) for ext in extensions):  # If the file has a valid video extension
                videos.append(os.path.join(root, file))  # Add the video file path to the list

    return videos  # Return the list of video file paths


def get_audio_tracks(video_path):
    """
    Retrieve a list of audio tracks in the video using ffprobe.

    :param video_path: Path to the video file
    :return: List of dictionaries containing track index, language, and codec
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Retrieving audio tracks for video: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}"
    )  # Output the verbose message

    cmd = ["ffprobe", "-v", "error", "-show_streams", "-of", "json", video_path]  # Build ffprobe command to list all streams
    result = subprocess.run(cmd, capture_output=True, text=True)  # Run ffprobe and capture JSON output
    data = json.loads(result.stdout) if result.stdout else {}  # Parse ffprobe JSON output
    streams = data.get("streams", [])  # Extract streams list from ffprobe output

    tracks = []  # Prepare list to hold audio stream information
    audio_count = 0  # Counter for audio stream physical positions
    for stream in streams:  # Iterate over each stream entry
        if stream.get("codec_type") == "audio":  # Only handle audio streams here
            index = stream.get("index", None)  # Get global stream index from ffprobe
            codec_name = stream.get("codec_name", "")  # Get codec name for structured output
            channels = stream.get("channels")  # Get channel count for structured output
            tags = stream.get("tags", {}) or {}  # Get tags dict for language/title metadata
            raw_lang = tags.get("language") or tags.get("LANGUAGE") or tags.get("lang") or ""  # Extract raw language tag with fallbacks
            raw_title = tags.get("title") or ""  # Extract raw title tag with fallback
            detected_language = detect_language(raw_lang, raw_title, "audio")  # Detect canonical language from normalized metadata
            disposition = stream.get("disposition", {}) or {}  # Get disposition dict if present
            tracks.append({  # Append detailed audio track info for classification
                "index": index,  # Structured stream index field
                "global_index": index,  # Global stream index for ffmpeg mapping
                "audio_pos": audio_count,  # Physical position among audio streams (0-based)
                "language": detected_language,  # Canonical detected language key or None
                "raw_language": raw_lang,  # Raw language metadata text
                "raw_title": raw_title,  # Raw title metadata text
                "codec": codec_name,  # Audio codec name
                "channels": channels,  # Audio channel count
                "tags": tags,  # Raw tags mapping
                "title": raw_title,  # Title metadata preserved for compatibility
                "disposition": disposition,  # Disposition flags
            })
            verbose_output(
                f"{BackgroundColors.CYAN}[DEBUG]{Style.RESET_ALL} Audio Stream {BackgroundColors.YELLOW}{audio_count}{Style.RESET_ALL}: "  # Colored debug tag and stream index
                f"detected_lang={BackgroundColors.GREEN}{detected_language}{Style.RESET_ALL} "  # Colored detected language
                f"raw=\"{BackgroundColors.CYAN}{raw_title}{Style.RESET_ALL}\" "  # Colored raw title
                f"codec={BackgroundColors.YELLOW}{codec_name}{Style.RESET_ALL} "  # Colored codec name
                f"channels={BackgroundColors.CYAN}{channels}{Style.RESET_ALL}"
            )  # Output per-audio debug log with normalized detection (colored)
            audio_count += 1  # Increment physical audio position counter

    return tracks  # Return the list of detailed audio tracks


def get_subtitle_tracks(video_path):
    """
    Retrieve all subtitle streams with metadata for classification.

    :param video_path: Path to the video file
    :return: List of subtitle stream dicts with global index and sub_pos
    """

    cmd = ["ffprobe", "-v", "error", "-show_streams", "-of", "json", video_path]  # Build ffprobe command to list all streams
    result = subprocess.run(cmd, capture_output=True, text=True)  # Run ffprobe and capture JSON output
    data = json.loads(result.stdout) if result.stdout else {}  # Parse ffprobe JSON output
    streams = data.get("streams", [])  # Extract streams list from ffprobe output

    subs = []  # Prepare list to hold subtitle stream information
    sub_count = 0  # Counter for subtitle stream positions
    for stream in streams:  # Iterate over each stream entry
        if stream.get("codec_type") == "subtitle":  # Only handle subtitle streams here
            index = stream.get("index", None)  # Get global stream index from ffprobe
            codec_name = stream.get("codec_name", "")  # Get subtitle codec name for structured output
            channels = stream.get("channels")  # Get subtitle channels value if provided
            tags = stream.get("tags", {}) or {}  # Get tags dict for language/title metadata
            raw_lang = tags.get("language") or tags.get("LANGUAGE") or tags.get("lang") or ""  # Extract raw language tag with fallbacks
            raw_title = tags.get("title") or ""  # Extract raw title tag with fallback
            detected_language = detect_language(raw_lang, raw_title, "subtitle")  # Detect canonical language from normalized metadata
            disposition = stream.get("disposition", {}) or {}  # Get disposition dict if present
            subs.append({  # Append detailed subtitle track info for classification
                "index": index,  # Structured stream index field
                "global_index": index,  # Global stream index for ffmpeg mapping
                "sub_pos": sub_count,  # Physical position among subtitle streams (0-based)
                "language": detected_language,  # Canonical detected language key or None
                "raw_language": raw_lang,  # Raw language metadata text
                "raw_title": raw_title,  # Raw title metadata text
                "codec": codec_name,  # Subtitle codec name
                "channels": channels,  # Subtitle channels value for structural parity
                "tags": tags,  # Raw tags mapping
                "title": raw_title,  # Title metadata preserved for compatibility
                "disposition": disposition,  # Disposition flags
            })
            verbose_output(f"[DEBUG] Subtitle Stream {sub_count}: detected_lang={detected_language} raw=\"{raw_title}\" codec={codec_name}")  # Output per-subtitle debug log with normalized detection
            sub_count += 1  # Increment physical subtitle position counter

    return subs  # Return the list of detailed subtitle tracks


def classify_streams(video_path):
    """
    Classify audio and subtitle streams as DESIRED or UNDESIRED using DESIRED_LANGUAGES and UNDESIRED_LANGUAGES.

    :param video_path: Path to the video file
    :return: Tuple (audio_streams, subtitle_streams) each being a list of dicts with 'classification'
    """

    audio_streams = get_audio_tracks(video_path)  # Get detailed audio streams for the file
    subtitle_streams = get_subtitle_tracks(video_path)  # Get detailed subtitle streams for the file

    for a in audio_streams:  # Classify each audio stream
        if a.get("language") in DESIRED_LANGUAGES:  # Verify detected canonical language belongs to desired set
            a["classification"] = "desired"  # Label the audio stream as desired
        else:  # Otherwise classify as undesired per strict mode
            a["classification"] = "undesired"  # Label the audio stream as undesired

    for s in subtitle_streams:  # Classify each subtitle stream
        if s.get("language") in DESIRED_LANGUAGES:  # Verify detected canonical language belongs to desired set
            s["classification"] = "desired"  # Label the subtitle stream as desired
        else:  # Otherwise classify as undesired per strict mode
            s["classification"] = "undesired"  # Label the subtitle stream as undesired

    return audio_streams, subtitle_streams  # Return classified audio and subtitle stream lists


def resolve_priority_list(stream_type):
    """
    Resolve the configured priority list for a stream type.

    :param stream_type: "audio" or "subtitle"
    :return: List of priority names in order
    """

    return STREAM_TYPE_PRIORITY_ORDER.get(stream_type, [])  # Return configured priority names or empty list


def build_candidate_aliases(preferred):
    """
    Build a list of candidate alias strings for a preferred display name.

    :param preferred: Preferred display name (e.g., 'English', 'Portuguese')
    :return: List of alias strings to match against stream metadata
    """

    candidates = [preferred.lower()]  # Start with the preferred name lowercased
    for aliases in DESIRED_LANGUAGES.values():  # Iterate known desired language alias lists
        for al in aliases:  # For each alias in the alias list
            try:  # Guard against non-string alias values
                if preferred.lower() in al.lower():  # If alias text references the preferred name
                    candidates.append(al.lower())  # Add matching alias to candidates
            except Exception:  # Ignore problematic alias entries
                continue  # Continue processing other aliases
    return candidates  # Return accumulated candidate alias strings


def stream_matches_candidates(stream, candidates):
    """
    Check whether a stream's metadata matches any candidate alias.

    :param stream: Stream metadata dict with keys 'language', 'title', 'tags'
    :param candidates: Iterable of candidate alias strings
    :return: True if any candidate appears in any metadata field
    """

    values = [str(stream.get("language", "")).lower(), str(stream.get("title", "")).lower()]  # Collect language and title
    for v in stream.get("tags", {}).values():  # Iterate all tag values to include them
        try:  # Guard conversion to string
            values.append(str(v).lower())  # Append lowercased tag value
        except Exception:  # Ignore problematic tag values
            continue  # Continue collecting other tags
    return any(cand in v for cand in candidates for v in values)  # Return True if any candidate appears


def is_descriptive_stream(stream):
    """
    Detect whether a stream is descriptive (SDH, audio description, commentary).

    :param stream: Stream metadata dict
    :return: True if descriptive keywords are found, False otherwise
    """
    
    keywords = ["sdh", "descriptive", "hearing impaired", "hearing", "commentary", "audio description", "described video"]  # Descriptive keywords to match
    values = [str(stream.get("title", "")).lower()]  # Start with title normalized
    values.append(str(stream.get("language", "")).lower())  # Append language normalized
    tags = stream.get("tags", {}) or {}  # Safely get tags dict or empty
    
    for v in tags.values():  # Iterate over all tag values
        try:  # Guard conversion to string for each tag value
            values.append(str(v).lower())  # Append lowercased tag value
        except Exception:  # Ignore problematic tag value conversions
            continue  # Continue with next tag value
    
    disp = stream.get("disposition", {}) or {}  # Safely get disposition dict or empty
    
    try:  # Guard numeric/coercion checks on disposition flags
        for key in ("hearing_impaired", "commentary", "descriptive", "audio_description", "described"):  # Keys to inspect
            if key in disp and disp.get(key) is not None:  # If disposition key exists and is not None
                val = disp.get(key)  # Get raw disposition value
                sval = str(val).lower()  # Normalize disposition value to string
                
                if sval in ("1", "true", "yes"):  # Treat these as affirmative indicators
                    return True  # Disposition indicates descriptive stream
    except Exception:  # Ignore any unexpected disposition parsing issues
        pass  # Continue to keyword scanning if disposition checks fail
    
    for val in values:  # Evaluate all collected metadata values for keywords
        for kw in keywords:  # Iterate descriptive keywords
            if kw in val:  # If keyword is present in any metadata value
                return True  # Mark stream as descriptive
    
    return False  # No descriptive indicators found


def filter_descriptive_streams(streams):
    """
    Filter out descriptive streams if REMOVE_DESCRIPTIVE_STREAMS is enabled.

    :param streams: List of stream dicts
    :return: Filtered list of stream dicts
    """
    
    filtered = streams  # Initialize filtered list with original streams
    
    if REMOVE_DESCRIPTIVE_STREAMS:  # Only remove descriptive streams when configured
        filtered = [s for s in streams if not is_descriptive_stream(s)]  # Build new list excluding descriptive streams
    
    return filtered  # Return the filtered (or original) list


def filter_desired_streams(streams):
    """
    Return only streams classified as 'desired'.

    :param streams: List of stream dicts
    :return: List of streams with classification == 'desired'
    """
    
    prefiltered = filter_descriptive_streams(streams)  # Ensure descriptive streams removed before classification filtering
    
    return [s for s in prefiltered if s.get("classification") == "desired"]  # Return only streams explicitly marked desired


def select_best_stream(streams, kept_positions, priority_names, pos_key):
    """
    Select the best physical stream position following the given priority names.

    :param streams: List of stream dicts
    :param kept_positions: List of physical positions to consider
    :param priority_names: Ordered list of display names to prefer
    :param pos_key: Physical position key name ('audio_pos' or 'sub_pos')
    :return: Selected physical position integer or None
    """
    
    filtered_streams = filter_descriptive_streams(streams)  # Remove descriptive streams before priority selection
    candidate_streams = [s for s in filtered_streams if s.get(pos_key) in kept_positions]  # Keep only streams that remain mapped
    
    for preferred in priority_names:  # Iterate language priorities in configured order
        for s in candidate_streams:  # Iterate candidate streams in original physical order
            if s.get("language") == preferred:  # Verify canonical detected language matches current priority language
                return s.get(pos_key)  # Return matching stream physical position immediately
    
    if len(candidate_streams) > 0:  # Verify at least one candidate stream exists for fallback
        return candidate_streams[0].get(pos_key)  # Fallback to the first available candidate stream
    
    return None  # Return None when there are no candidate streams to select


def resolve_canonical_language_from_priority_name(priority_name):
    """
    Resolve a priority display name to a canonical DESIRED_LANGUAGES key.

    :param priority_name: Priority name from STREAM_TYPE_PRIORITY_ORDER
    :return: Canonical DESIRED_LANGUAGES key or None
    """

    if priority_name in DESIRED_LANGUAGES:  # Verify direct canonical key match first
        return priority_name  # Return canonical key immediately when exact key exists

    normalized_priority_name = normalize_text(priority_name)  # Normalize priority text for robust alias matching
    normalized_aliases = get_normalized_desired_language_aliases()  # Build normalized alias mapping for canonical lookup
    for language_name, aliases in normalized_aliases.items():  # Iterate canonical language keys and aliases
        for alias in aliases:  # Iterate normalized aliases for the current canonical language
            if alias == "":  # Verify alias contains meaningful content before comparing
                continue  # Continue to next alias when current alias is empty
            if alias == normalized_priority_name or normalized_priority_name in alias or alias in normalized_priority_name:  # Verify alias relation between priority name and canonical alias
                return language_name  # Return canonical language key when alias relation matches

    return None  # Return None when no canonical language can be resolved


def get_ordered_language_aliases_for_priority(language_name):
    """
    Build normalized aliases for a canonical language preserving DESIRED_LANGUAGES order.

    :param language_name: Canonical DESIRED_LANGUAGES key
    :return: Ordered list of normalized aliases from DESIRED_LANGUAGES values
    """

    ordered_aliases = []  # Initialize ordered alias list for scoring
    seen_aliases = set()  # Initialize set for duplicate suppression
    for alias in DESIRED_LANGUAGES.get(language_name, []):  # Iterate configured aliases in declaration order
        normalized_alias = normalize_text(alias)  # Normalize alias text for robust case-insensitive matching
        if normalized_alias == "":  # Verify normalized alias has content
            continue  # Continue to next alias when normalized alias is empty
        if normalized_alias in seen_aliases:  # Verify alias has not already been added
            continue  # Continue to next alias when duplicate alias is found
        ordered_aliases.append(normalized_alias)  # Append alias preserving DESIRED_LANGUAGES ordering
        seen_aliases.add(normalized_alias)  # Mark alias as added to keep scoring deterministic

    return ordered_aliases  # Return ordered normalized aliases for scoring


def compute_stream_language_alias_priority_score(stream, ordered_aliases):
    """
    Compute stream score using first matching alias index from ordered aliases.

    :param stream: Stream metadata dict
    :param ordered_aliases: Ordered normalized alias list for target language
    :return: Integer score where lower is better
    """

    metadata_values = []  # Initialize metadata values container for substring matching
    metadata_values.append(normalize_text(stream.get("raw_title", "")))  # Add normalized raw title metadata
    metadata_values.append(normalize_text(stream.get("title", "")))  # Add normalized title metadata fallback
    metadata_values.append(normalize_text(stream.get("raw_language", "")))  # Add normalized raw language metadata
    for value in (stream.get("tags", {}) or {}).values():  # Iterate all tag values for broader metadata matching
        metadata_values.append(normalize_text(value))  # Add normalized tag value for substring scoring

    fallback_score = len(ordered_aliases) + 1000  # Define deterministic fallback score for non-matching aliases
    for alias_index, alias in enumerate(ordered_aliases):  # Iterate aliases in strict declaration order for scoring
        if alias == "":  # Verify alias has content before comparing
            continue  # Continue to next alias when alias is empty
        for metadata_value in metadata_values:  # Iterate normalized metadata values for substring match
            if metadata_value == "":  # Verify metadata value has content before comparing
                continue  # Continue to next metadata value when empty
            if alias in metadata_value:  # Verify ordered alias appears as substring in metadata value
                return alias_index  # Return first alias index as strict priority score

    return fallback_score  # Return fallback score when no alias match is found


def subtitle_stream_matches_language_aliases(stream, ordered_aliases):
    """
    Verify whether subtitle metadata matches any alias from a canonical language group.

    :param stream: Subtitle stream metadata dict
    :param ordered_aliases: Ordered normalized alias list for a canonical language
    :return: True when at least one alias matches subtitle metadata, False otherwise
    """

    metadata_values = []  # Initialize metadata values container for alias matching
    metadata_values.append(normalize_text(stream.get("raw_title", "")))  # Add normalized raw title metadata
    metadata_values.append(normalize_text(stream.get("title", "")))  # Add normalized title metadata fallback
    metadata_values.append(normalize_text(stream.get("raw_language", "")))  # Add normalized raw language metadata
    for value in (stream.get("tags", {}) or {}).values():  # Iterate all tag values for additional metadata matching
        metadata_values.append(normalize_text(value))  # Add normalized tag value to metadata candidates

    for alias in ordered_aliases:  # Iterate aliases in configured priority order
        if alias == "":  # Verify alias contains meaningful content before matching
            continue  # Continue to next alias when alias is empty
        for metadata_value in metadata_values:  # Iterate metadata values to evaluate substring match
            if metadata_value == "":  # Verify metadata value contains content before matching
                continue  # Continue to next metadata value when empty
            if alias in metadata_value:  # Verify alias appears in subtitle metadata value
                return True  # Return True immediately when alias metadata match is found

    return False  # Return False when no aliases match subtitle metadata


def select_best_subtitle_stream(streams, kept_positions, priority_names, pos_key):
    """
    Select the best subtitle position by stream-type priority then alias priority score.

    :param streams: List of subtitle stream dicts
    :param kept_positions: List of subtitle positions to consider
    :param priority_names: Ordered priority names from STREAM_TYPE_PRIORITY_ORDER['subtitle']
    :param pos_key: Physical position key name ('sub_pos')
    :return: Selected subtitle physical position integer or None
    """

    filtered_streams = filter_descriptive_streams(streams)  # Remove descriptive streams before subtitle selection
    candidate_streams = [s for s in filtered_streams if s.get(pos_key) in kept_positions]  # Keep only mapped subtitle candidates

    for preferred in priority_names:  # Iterate configured subtitle language priorities in order
        canonical_language = resolve_canonical_language_from_priority_name(preferred)  # Resolve priority display name to canonical desired language
        if canonical_language is None:  # Verify canonical language was resolved for current priority name
            continue  # Continue to next priority name when canonical language resolution fails
        language_aliases = get_ordered_language_aliases_for_priority(canonical_language)  # Get strict ordered aliases for intra-language scoring
        ranked_candidates = []  # Initialize ranked candidate tuples for current language

        for stream_order, stream in enumerate(candidate_streams):  # Iterate candidates preserving existing stream order for tie-breaking
            if not subtitle_stream_matches_language_aliases(stream, language_aliases):  # Verify subtitle metadata matches current canonical language aliases
                continue  # Continue to next stream when language group does not match
            priority_score = compute_stream_language_alias_priority_score(stream, language_aliases)  # Compute intra-language alias priority score
            ranked_candidates.append((priority_score, stream_order, stream.get(pos_key)))  # Store score, stable order, and stream position

        if len(ranked_candidates) > 0:  # Verify at least one candidate exists for current language priority
            ranked_candidates.sort(key=lambda item: (item[0], item[1]))  # Sort by strict alias score then existing stream order tie-breaker
            return ranked_candidates[0][2]  # Return best subtitle position for current language priority

    if len(candidate_streams) > 0:  # Verify at least one subtitle candidate exists for fallback
        return candidate_streams[0].get(pos_key)  # Fallback to first candidate preserving existing behavior when no priority language matches

    return None  # Return None when no subtitle candidates are available


def find_best_stream_by_priority(streams, kept_positions, priority_names, pos_key):
    """
    Select the best stream physical position based on priority names.

    :param streams: List of stream dicts
    :param kept_positions: List of physical positions that will be kept
    :param priority_names: Ordered list of display names to prefer
    :param pos_key: Key name for the physical position ('audio_pos' or 'sub_pos')
    :return: Selected physical position integer or None
    """

    for preferred in priority_names:  # Iterate each preferred name in priority order
        candidates = build_candidate_aliases(preferred)  # Build candidate aliases for this preferred name
        for s in streams:  # Scan streams for a matching candidate
            if s.get("classification") != "desired":  # Skip streams not classified as desired
                continue  # Continue to next stream
            pos = s.get(pos_key)  # Get the physical position value
            if pos not in kept_positions:  # Skip streams not in the kept list
                continue  # Continue to next stream
            if stream_matches_candidates(s, candidates):  # If metadata matches any candidate alias
                return pos  # Return the matched physical position immediately
    return None  # No prioritized stream found


def find_original_default_position(streams, pos_key):
    """
    Find the original default stream physical position from source dispositions.

    :param streams: List of stream dicts
    :param pos_key: Key name for the physical position ('audio_pos' or 'sub_pos')
    :return: Physical position int or None if none marked default
    """

    for s in streams:  # Iterate streams to find original default disposition
        try:  # Guard access to disposition structure
            if int(s.get("disposition", {}).get("default", 0)) == 1:  # Check ffprobe default flag
                return s.get(pos_key)  # Return the original physical position
        except Exception:  # Ignore malformed disposition values
            continue  # Continue scanning streams
    return None  # No original default found


def find_current_default_stream(streams):
    """
    Find the current default stream from disposition metadata.

    :param streams: List of stream dicts
    :return: Stream dict marked as default or None
    """

    for stream in streams:  # Iterate stream list to locate the stream marked as default.
        try:  # Guard disposition coercion for malformed metadata values.
            if int(stream.get("disposition", {}).get("default", 0)) == 1:  # Verify ffprobe default flag is enabled.
                return stream  # Return stream immediately when default disposition is present.
        except Exception:  # Ignore malformed disposition values and continue scanning.
            continue  # Continue iteration when disposition parsing fails.

    return None  # Return None when no default stream is marked.


def resolve_priority_canonical_language(stream_type):
    """
    Resolve the highest-priority configured language to a canonical desired key.

    :param stream_type: Stream type key ('audio' or 'subtitle')
    :return: Canonical language key from DESIRED_LANGUAGES or None
    """

    priority_names = resolve_priority_list(stream_type)  # Resolve ordered priority names for the requested stream type.
    if len(priority_names) == 0:  # Verify at least one configured priority exists.
        return None  # Return None when no priority language is configured.

    top_priority_name = priority_names[0]  # Read the highest-priority display name from configuration.
    if top_priority_name in DESIRED_LANGUAGES:  # Verify top priority already matches a canonical desired language key.
        return top_priority_name  # Return canonical key directly when an exact key match exists.

    normalized_priority = normalize_text(top_priority_name)  # Normalize top priority text for robust alias comparison.
    normalized_aliases = get_normalized_desired_language_aliases()  # Build normalized alias map for desired languages.

    for language_name, aliases in normalized_aliases.items():  # Iterate canonical language aliases for fuzzy canonical resolution.
        for alias in aliases:  # Iterate each normalized alias for the current canonical language.
            if alias == "":  # Verify alias has meaningful content before comparison.
                continue  # Continue to next alias when normalized alias is empty.
            if alias == normalized_priority or normalized_priority in alias or alias in normalized_priority:  # Verify alias relation between priority value and canonical aliases.
                return language_name  # Return canonical language key when alias relation matches.

    return None  # Return None when no canonical desired language can be resolved.


def detect_stream_language_for_validation(stream, stream_type):
    """
    Detect canonical stream language using tags, title, codec, and fuzzy aliases.

    :param stream: Stream metadata dict
    :param stream_type: Stream type key ('audio' or 'subtitle')
    :return: Canonical language key from DESIRED_LANGUAGES or None
    """

    tags = stream.get("tags", {}) or {}  # Resolve stream tags mapping with empty fallback.
    raw_lang = stream.get("raw_language") or tags.get("language") or tags.get("LANGUAGE") or tags.get("lang") or ""  # Resolve raw language metadata with fallbacks.
    raw_title = stream.get("raw_title") or stream.get("title") or tags.get("title") or ""  # Resolve raw title metadata with fallbacks.
    detected_language = detect_language(raw_lang, raw_title, stream_type)  # Reuse existing normalized language detector first.
    if detected_language is not None:  # Verify canonical language was resolved from standard metadata fields.
        return detected_language  # Return detected canonical language immediately when available.

    normalized_aliases = get_normalized_desired_language_aliases()  # Build normalized desired language aliases for fallback matching.
    metadata_values = []  # Initialize metadata value list for fuzzy fallback matching.
    metadata_values.append(normalize_text(stream.get("codec", "")))  # Append normalized codec name to fallback candidates.
    metadata_values.append(normalize_text(raw_lang))  # Append normalized raw language value to fallback candidates.
    metadata_values.append(normalize_text(raw_title))  # Append normalized raw title value to fallback candidates.
    for value in tags.values():  # Iterate all tag values for additional fuzzy matching input.
        metadata_values.append(normalize_text(value))  # Append normalized tag value to fallback candidates.

    priority_names = resolve_priority_list(stream_type)  # Resolve configured priority language names for deterministic ordering.
    ordered_languages = []  # Initialize ordered canonical language scan list.
    for language_name in priority_names:  # Iterate configured priority names first.
        if language_name in DESIRED_LANGUAGES and language_name not in ordered_languages:  # Verify language is canonical and not duplicated.
            ordered_languages.append(language_name)  # Append canonical priority language to ordered scan list.
    for language_name in DESIRED_LANGUAGES.keys():  # Iterate remaining canonical desired language keys.
        if language_name not in ordered_languages:  # Verify language key has not already been added.
            ordered_languages.append(language_name)  # Append remaining canonical language after priority languages.

    for language_name in ordered_languages:  # Iterate canonical language keys in deterministic order.
        for alias in normalized_aliases.get(language_name, []):  # Iterate normalized aliases for current canonical language.
            if alias == "":  # Verify alias is not empty before metadata comparison.
                continue  # Continue to next alias when normalized alias is empty.
            for metadata_value in metadata_values:  # Iterate normalized metadata values for substring matching.
                if metadata_value == "":  # Verify metadata value has content before matching.
                    continue  # Continue to next metadata value when empty.
                if alias in metadata_value:  # Verify alias appears in current normalized metadata value.
                    return language_name  # Return canonical language key when a fuzzy match is found.

    return None  # Return None when language detection cannot resolve a canonical desired language.


def should_skip_processing_for_correct_defaults(video_path, audio_streams, subtitle_streams):
    """
    Determine whether processing can be skipped when default streams already match priority.

    :param video_path: Path to the video file
    :param audio_streams: List of parsed audio stream dicts
    :param subtitle_streams: List of parsed subtitle stream dicts
    :return: True when both default audio and subtitle streams already match highest priority
    """

    default_audio_stream = find_current_default_stream(audio_streams)  # Resolve currently flagged default audio stream.
    default_subtitle_stream = find_current_default_stream(subtitle_streams)  # Resolve currently flagged default subtitle stream.
    desired_audio_language = resolve_priority_canonical_language("audio")  # Resolve canonical top-priority audio language from configuration.
    desired_subtitle_language = resolve_priority_canonical_language("subtitle")  # Resolve canonical top-priority subtitle language from configuration.

    if default_audio_stream is None or default_subtitle_stream is None:  # Verify both default streams exist before skip decision.
        return False  # Return False when one of the default streams is missing.
    if desired_audio_language is None or desired_subtitle_language is None:  # Verify top-priority canonical languages were resolved from configuration.
        return False  # Return False when priority canonical languages cannot be resolved.

    current_audio_language = detect_stream_language_for_validation(default_audio_stream, "audio")  # Detect canonical language for current default audio stream.
    current_subtitle_language = detect_stream_language_for_validation(default_subtitle_stream, "subtitle")  # Detect canonical language for current default subtitle stream.
    desired_subtitle_positions = [s.get("sub_pos") for s in subtitle_streams if s.get("classification") == "desired"]  # Compute desired subtitle positions for strict default verification.
    subtitle_priorities = resolve_priority_list("subtitle")  # Resolve configured subtitle priorities for strict default verification.
    expected_subtitle_pos = select_best_subtitle_stream(subtitle_streams, desired_subtitle_positions, subtitle_priorities, "sub_pos")  # Resolve expected default subtitle position using strict intra-language priority.
    current_default_subtitle_pos = default_subtitle_stream.get("sub_pos")  # Resolve current default subtitle position for equality verification.

    if current_audio_language == desired_audio_language and current_subtitle_language == desired_subtitle_language and expected_subtitle_pos == current_default_subtitle_pos:  # Verify both defaults match priority language and subtitle variant priority.
        verbose_output(f"[DEBUG] Skipping file as default streams already match desired priority: {os.path.basename(video_path)}")  # Output debug skip log in the existing format.
        return True  # Return True to skip remuxing for this file.

    return False  # Return False when at least one default stream does not match configured priority.


def apply_prune_and_set_defaults(video_path, audio_streams, subtitle_streams):
    """
    Build and run ffmpeg command to keep only DESIRED tracks and set defaults accordingly.

    :param video_path: Path to the video file
    :param audio_streams: Classified audio streams list
    :param subtitle_streams: Classified subtitle streams list
    :return: None
    """

    root, ext = os.path.splitext(video_path)  # Split the file path and extension
    ext = ext.lower()  # Normalize extension to lowercase
    temp_file = root + ".tmp" + ext  # Build temporary output path

    kept_audio_positions = [a.get("audio_pos") for a in audio_streams if a.get("classification") == "desired"]  # Compute desired audio positions
    kept_sub_positions = [s.get("sub_pos") for s in subtitle_streams if s.get("classification") == "desired"]  # Compute desired subtitle positions

    if not kept_audio_positions:  # If no desired audio streams were found then abort per strict rules
        print(f"{BackgroundColors.YELLOW}No desired audio tracks found for: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}")  # Notify user
        return  # Exit without changes

    audio_priorities = resolve_priority_list("audio")  # Resolve audio priority names from config
    default_audio_pos = select_best_stream(audio_streams, kept_audio_positions, audio_priorities, "audio_pos")  # Find best audio by priority using new helper
    
    if default_audio_pos is None:  # If no prioritized audio found
        default_audio_pos = find_original_default_position(audio_streams, "audio_pos")  # Fallback to original default if present
    subtitle_priorities = resolve_priority_list("subtitle")  # Resolve subtitle priority names from config
    default_sub_pos = select_best_subtitle_stream(subtitle_streams, kept_sub_positions, subtitle_priorities, "sub_pos")  # Find best subtitle by stream priority and intra-language alias score
    
    if default_sub_pos is None:  # If no prioritized subtitle found
        default_sub_pos = find_original_default_position(subtitle_streams, "sub_pos")  # Fallback to original default if present

    selected_audio_stream = next((a for a in audio_streams if a.get("audio_pos") == default_audio_pos), None)  # Resolve selected audio stream metadata for debug output
    selected_subtitle_stream = next((s for s in subtitle_streams if s.get("sub_pos") == default_sub_pos), None)  # Resolve selected subtitle stream metadata for debug output
    selected_audio_index = selected_audio_stream.get("index") if selected_audio_stream is not None else None  # Resolve selected audio stream index safely
    selected_subtitle_index = selected_subtitle_stream.get("index") if selected_subtitle_stream is not None else None  # Resolve selected subtitle stream index safely
    selected_audio_lang = selected_audio_stream.get("language") if selected_audio_stream is not None else None  # Resolve selected audio language safely
    selected_subtitle_lang = selected_subtitle_stream.get("language") if selected_subtitle_stream is not None else None  # Resolve selected subtitle language safely
    verbose_output(f"[DEBUG] Selected audio stream: {selected_audio_index} (lang={selected_audio_lang})")  # Output final selected audio stream debug log
    verbose_output(f"[DEBUG] Selected subtitle stream: {selected_subtitle_index} (lang={selected_subtitle_lang})")  # Output final selected subtitle stream debug log

    cmd = ["ffmpeg", "-y", "-i", video_path, "-map", "0", "-map", "-0:a"]  # Start command by mapping all and dropping audio
    cmd += ["-map", "-0:s"]  # Drop all subtitle streams to re-add only desired ones

    for pos in kept_audio_positions:  # Re-add each desired audio stream by physical position
        cmd += ["-map", f"0:a:{pos}"]  # Map desired audio stream

    for pos in kept_sub_positions:  # Re-add each desired subtitle stream by physical position
        cmd += ["-map", f"0:s:{pos}"]  # Map desired subtitle stream

    cmd += ["-c", "copy"]  # Use stream copy to avoid re-encoding

    if default_audio_pos is not None:  # Only modify audio dispositions when a default has been determined
        for i, pos in enumerate(kept_audio_positions):  # Set dispositions for audio streams in new output order
            if pos == default_audio_pos:  # If this mapped audio is the chosen default
                cmd += [f"-disposition:a:{i}", "default"]  # Set default disposition for this audio
            else:  # Otherwise clear default flag
                cmd += [f"-disposition:a:{i}", "0"]  # Clear default disposition for this audio

    if default_sub_pos is not None:  # Only modify subtitle dispositions when a default has been determined
        for i, pos in enumerate(kept_sub_positions):  # Iterate subtitle outputs to set dispositions
            if pos == default_sub_pos:  # If this mapped subtitle is chosen as default
                cmd += [f"-disposition:s:{i}", "default"]  # Set default subtitle disposition
            else:  # Otherwise clear default flag
                cmd += [f"-disposition:s:{i}", "0"]  # Clear default disposition for this subtitle

    cmd += [temp_file]  # Add temporary output path to command

    verbose_output(f"{BackgroundColors.GREEN}Executing ffmpeg prune command:{BackgroundColors.CYAN} {' '.join(cmd)}{Style.RESET_ALL}")  # Verbose output of ffmpeg command

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # Execute ffmpeg silently

    if not verify_filepath_exists(temp_file):  # If temporary file creation failed then report and retry with output
        print(f"{BackgroundColors.RED}Failed to create temporary file for: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}")  # Report error
        subprocess.run(cmd)  # Retry command with visible output for diagnostics
        return  # Exit to avoid replacing original

    os.replace(temp_file, video_path)  # Replace original with pruned file


def select_audio_track(tracks):
    """
    Display available audio tracks and prompt the user to select one as default.

    :param tracks: List of audio track dictionaries
    :return: Selected track index
    """

    print(f"\n{BackgroundColors.BOLD}{BackgroundColors.CYAN}Available audio tracks:{Style.RESET_ALL}")
    for i, track in enumerate(tracks):  # For each audio track
        print(
            f"   {BackgroundColors.YELLOW}[{i}] Index {track['index']} | Language: {track['language']}{Style.RESET_ALL}"
        )

    while True:  # Loop until a valid selection is made
        choice = input(f"{BackgroundColors.GREEN}Select the track number to set as default:{Style.RESET_ALL} ")
        if choice.isdigit() and 0 <= int(choice) < len(tracks):  # If the choice is valid
            return tracks[int(choice)]["index"]  # Return the selected track index
        print(f"{BackgroundColors.RED}Invalid selection. Please try again.{Style.RESET_ALL}")


def get_audio_track_info(video_path):
    """
    Retrieve audio track information from a video file using ffprobe.

    :param video_path: Path to the video file
    :return: List of audio track strings (format: index,language,default_flag)
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Retrieving audio track information for: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}"
    )  # Output the verbose message

    probe_cmd = [  # ffprobe command to get audio track info
        "ffprobe",  # Command to run ffprobe
        "-v",
        "error",  # Suppress unnecessary output
        "-select_streams",
        "a",  # Select audio streams
        "-show_entries",
        "stream=index:stream_tags=language:disposition=default",  # Show stream index, language tags, and default disposition
        "-of",
        "csv=p=0",  # Output format as CSV without prefix
        video_path,  # Video file path
    ]

    result = subprocess.run(probe_cmd, capture_output=True, text=True)  # Run ffprobe and capture output
    return result.stdout.strip().splitlines()  # Get audio track info


def is_english_track_default(audio_tracks):
    """
    Check if an English audio track is already set as default.

    :param audio_tracks: List of audio track strings
    :return: True if English track is default, False otherwise
    """

    for i, track in enumerate(audio_tracks):  # For each audio track
        track_info = track.split(",")  # Split the track info
        if len(track_info) >= 3:  # If track info has enough parts
            language = (
                track_info[2].lower().strip() if len(track_info[2].strip()) > 0 else "und"
            )  # Get language or "und"
            is_default = track_info[1].strip() == "1"  # Check if track is default
            if is_default and language in DESIRED_LANGUAGES.get("English", []):  # If default and language is English
                return True  # English track is already default

    return False  # English track is not default


def find_english_track_index(audio_tracks):
    """
    Find the index of the first English audio track.

    :param audio_tracks: List of audio track strings
    :return: Index of English track if found, None otherwise
    """

    for i, track in enumerate(audio_tracks):  # For each audio track
        track_info = track.split(",")  # Split the track info
        if len(track_info) >= 3:  # If track info has enough parts
            language = track_info[2].lower().strip()  # Get language
            if language in ["english", "eng", "en"]:  # Check if language is English (case-insensitive)
                verbose_output(
                    f"{BackgroundColors.GREEN}Automatically detected English audio track at index {i}{Style.RESET_ALL}"
                )
                return i  # Return the English track index

    return None  # No English track found


def prompt_user_track_selection(audio_tracks, video_path):
    """
    Prompt the user to manually select an audio track.

    :param audio_tracks: List of audio track strings
    :param video_path: Path to the video file (for display)
    :return: Selected track index, or None if invalid input
    """

    print(f"\n{BackgroundColors.CYAN}Audio tracks found in:{BackgroundColors.GREEN} {video_path}{Style.RESET_ALL}")
    for i, track in enumerate(audio_tracks):  # For each audio track
        print(f"   [{i}] {track}")  # Display track info

    try:  # Get user input for track selection
        default_track_index = int(
            input(f"{BackgroundColors.YELLOW}Select the track index to set as default:{Style.RESET_ALL} ")
        )  # Get user input for the track index
    except ValueError:  # If input is not a valid integer
        print(f"{BackgroundColors.RED}Invalid input. Skipping file.{Style.RESET_ALL}")
        return None  # Skip this file

    if default_track_index < 0 or default_track_index >= len(audio_tracks):
        print(f"{BackgroundColors.RED}Invalid track index. Skipping file.{Style.RESET_ALL}")
        return None  # Skip this file

    return default_track_index  # Return the selected track index


def determine_default_track(audio_tracks, video_path):
    """
    Determine which audio track should be set as default.
    Prioritizes English tracks, then prompts user if needed.

    :param audio_tracks: List of audio track strings
    :param video_path: Path to the video file
    :return: Index of the track to set as default, or None if operation should be skipped
    """

    num_tracks = len(audio_tracks)  # Number of audio tracks found

    english_track_index = find_english_track_index(audio_tracks)  # Try to automatically detect English audio track

    if english_track_index is not None:  # If English track was found, use it automatically
        print(
            f"{BackgroundColors.GREEN}Automatically selected English audio track for: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}"
        )
        return english_track_index  # Return the English track index

    if num_tracks > 2:  # Otherwise, ask for user input if more than two tracks
        return prompt_user_track_selection(audio_tracks, video_path)  # Prompt user to select track

    return 1 if num_tracks == 2 else 0  # For 1 or 2 tracks, swap only if there are 2 tracks


def apply_audio_track_default(video_path, audio_tracks, default_track_index, kept_indices):
    """
    Apply the default audio track disposition to the video file using ffmpeg, keeping only desired tracks.

    :param video_path: Path to the video file
    :param audio_tracks: List of audio track strings
    :param default_track_index: Index of the track to set as default
    :param kept_indices: List of indices of tracks to keep
    :return: None
    """

    root, ext = os.path.splitext(video_path)  # Split the file path and extension
    ext = ext.lower()  # Ensure lowercase extension
    video_path = (
        video_path if video_path.endswith(ext) else os.rename(video_path, root + ext) or (root + ext)
    )  # Rename if needed
    temp_file = root + ".tmp" + ext  # Temporary file path with correct extension order

    cmd = ["ffmpeg", "-y", "-i", video_path, "-map", "0", "-map", "-0:a"]  # Base mapping preserving subs

    subtitle_streams = []  # Initialize subtitle stream container for default selection in fallback mode
    default_sub_pos = None  # Initialize default subtitle position for disposition assignment
    if not REMOVE_OTHER_SUBTITLE_TRACKS:  # Only compute subtitle default when subtitle streams are preserved
        try:  # Guard subtitle parsing and selection path to keep fallback resilient
            _, subtitle_streams = classify_streams(video_path)  # Collect classified subtitle streams from current input file
            kept_sub_positions = [s.get("sub_pos") for s in subtitle_streams if s.get("classification") == "desired"]  # Compute desired subtitle positions for default selection
            subtitle_priorities = resolve_priority_list("subtitle")  # Resolve configured subtitle priorities in declared order
            default_sub_pos = select_best_subtitle_stream(subtitle_streams, kept_sub_positions, subtitle_priorities, "sub_pos")  # Resolve best subtitle default using metadata alias priority
        except Exception:  # Preserve original fallback behavior when subtitle parsing fails
            subtitle_streams = []  # Reset subtitle stream list on selection failure
            default_sub_pos = None  # Keep subtitle default unset on selection failure

    if REMOVE_OTHER_SUBTITLE_TRACKS:
        cmd += ["-map", "-0:s"]

    for idx in kept_indices:  # Map each kept audio track
        cmd += ["-map", f"0:a:{idx}"]  # Re-add desired audio tracks

    cmd += ["-c", "copy"]  # Copy codecs

    for i, idx in enumerate(kept_indices):  # Set dispositions
        if idx == default_track_index:  # If this is the default track
            cmd += ["-disposition:a:" + str(i), "default"]  # Set as default
        else:  # If this is not the default track
            cmd += ["-disposition:a:" + str(i), "0"]  # Unset default

    if not REMOVE_OTHER_SUBTITLE_TRACKS and len(subtitle_streams) > 0:  # Only set subtitle dispositions when subtitle streams are preserved
        for i, _ in enumerate(subtitle_streams):  # Iterate subtitle outputs in preserved stream order
            if default_sub_pos is not None and i == default_sub_pos:  # Verify this subtitle is the selected default stream
                cmd += ["-disposition:s:" + str(i), "default"]  # Set selected subtitle as default
            else:  # For non-selected subtitle streams
                cmd += ["-disposition:s:" + str(i), "0"]  # Clear subtitle default and forced flags

    cmd += [temp_file]  # Output file

    verbose_output(
        f"{BackgroundColors.GREEN}Executing ffmpeg command:{BackgroundColors.CYAN} {' '.join(cmd)}{Style.RESET_ALL}"
    )  # Output the ffmpeg command if verbose is True

    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)  # Run ffmpeg silently

    if not verify_filepath_exists(temp_file):  # If the temporary file was not created
        print(
            f"{BackgroundColors.RED}Failed to create temporary file for: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}"
        )  # Output the error message
        print(
            f"{BackgroundColors.YELLOW}Retrying ffmpeg with error output enabled...{Style.RESET_ALL}"
        )  # Notify user of retry
        subprocess.run(cmd)  # Retry with visible output for debugging
        return  # Exit the function to prevent file replacement

    os.replace(temp_file, video_path)  # Replace the original file with the modified file


def swap_audio_tracks(video_path):
    """
    Process the audio tracks in the video: keep only desired languages, set English as default if available.
    Requires ffmpeg and ffprobe installed and available in PATH.

    :param video_path: Path to the video file
    :return: None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Processing audio tracks for video: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}"
    )  # Output the verbose message

    if REMOVE_OTHER_AUDIO_TRACKS:  # If strict removal mode is enabled
        audio_streams, subtitle_streams = classify_streams(video_path)  # Classify audio and subtitle streams
        if not audio_streams:  # If no audio streams were found
            print(
                f"{BackgroundColors.YELLOW}No audio tracks found for: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}"
            )
            return  # Skip this file

        if should_skip_processing_for_correct_defaults(video_path, audio_streams, subtitle_streams):  # Verify whether both current defaults already match highest-priority desired languages.
            return  # Skip remuxing when default streams already match configured priority.

        apply_prune_and_set_defaults(video_path, audio_streams, subtitle_streams)  # Prune non-desired and set defaults
        return  # Return after pruning operation

    # Fallback behavior when not removing other audio tracks: preserve original logic
    audio_tracks = get_audio_track_info(video_path)  # Get audio track information using ffprobe

    if len(audio_tracks) == 0:  # Check if any audio tracks were found
        print(
            f"{BackgroundColors.YELLOW}No audio tracks found for: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}"
        )
        return  # Skip this file

    desired_langs = get_desired_languages()  # Get list of desired languages

    kept_indices = list(range(len(audio_tracks)))  # Keep all track indices by default

    english_langs = DESIRED_LANGUAGES.get("English", [])  # Get English language codes
    english_index = None  # Index of English track if found
    for i in kept_indices:  # For each kept track
        parts = audio_tracks[i].split(",")  # Split the track info
        lang = parts[2].lower().strip()  # Get language
        if lang in english_langs:  # If language is English
            english_index = i  # Set English track index
            break  # Stop searching

    if english_index is not None:  # If English track found
        default_track_index = english_index  # Set English as default
        print(
            f"{BackgroundColors.GREEN}Automatically selected English audio track for: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}"
        )
    else:  # No English, use first track from kept set
        default_track_index = kept_indices[0]  # Set first track as default
        print(
            f"{BackgroundColors.GREEN}Selected first audio track as default for: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}"
        )

    apply_audio_track_default(video_path, audio_tracks, default_track_index, kept_indices)  # Apply the changes


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
    
    global REMOVE_OTHER_AUDIO_TRACKS, REMOVE_OTHER_SUBTITLE_TRACKS, REMOVE_DESCRIPTIVE_STREAMS  # Make descriptive config writable

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Process video files and manage audio tracks and subtitles."
    )
    parser.add_argument(
        "--remove-other-audio",
        action="store_true",  # Use presence to set True when explicitly passed
        default=None,  # Default to None so absence does not override constants
        help="Remove audio tracks not in the desired languages list"
    )
    parser.add_argument(
        "--remove-other-subtitles",
        action="store_true",  # Use presence to set True when explicitly passed
        default=None,  # Default to None so absence does not override constants
        help="Remove non-desired subtitle tracks from the video files"
    )
    parser.add_argument(
        "--remove-descriptive-streams",
        action="store_true",  # Use presence to set True when explicitly passed
        default=None,  # Default to None so absence does not override constants
        help="Remove descriptive/SDH streams before selection"
    )
    args = parser.parse_args()

    if args.remove_other_audio is not None:  # Only override when flag explicitly present
        REMOVE_OTHER_AUDIO_TRACKS = args.remove_other_audio  # Override global constant accordingly
    if args.remove_other_subtitles is not None:  # Only override when flag explicitly present
        REMOVE_OTHER_SUBTITLE_TRACKS = args.remove_other_subtitles  # Override global constant accordingly
    if args.remove_descriptive_streams is not None:  # Only override when flag explicitly present
        REMOVE_DESCRIPTIVE_STREAMS = args.remove_descriptive_streams  # Override global constant accordingly

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Default Audio Track Switcher{BackgroundColors.GREEN}!{Style.RESET_ALL}\n"
    )

    if REMOVE_OTHER_AUDIO_TRACKS:  # If audio track removal is enabled, print the mode
        print(f"{BackgroundColors.GREEN}Mode: {BackgroundColors.CYAN}Removing Non-Desired Audio Tracks{Style.RESET_ALL}")
    if REMOVE_OTHER_SUBTITLE_TRACKS:  # If subtitle removal is enabled, print the mode
        print(f"{BackgroundColors.GREEN}Mode: {BackgroundColors.CYAN}Removing Non-Desired Subtitle Tracks{Style.RESET_ALL}")
    if REMOVE_DESCRIPTIVE_STREAMS:  # If descriptive stream filtering is enabled, print the mode
        print(f"{BackgroundColors.GREEN}Mode: {BackgroundColors.CYAN}Filtering Descriptive Streams{Style.RESET_ALL}")

    print()  # Add a newline for better separation before processing starts

    install_ffmpeg_and_ffprobe()  # Ensure ffmpeg and ffprobe are installed

    if not verify_filepath_exists(INPUT_DIR):  # If the input directory does not exist
        print(f"{BackgroundColors.RED}Input directory not found: {BackgroundColors.CYAN}{INPUT_DIR}{Style.RESET_ALL}")
        return  # Exit the program

    videos = find_videos(INPUT_DIR, VIDEO_FILE_EXTENSIONS)  # Find all videos in the input directory
    if not videos:  # If no videos were found
        print(f"{BackgroundColors.YELLOW}No video files found in {INPUT_DIR}{Style.RESET_ALL}")
        return  # Exit the program

    pbar = None  # Initialize pbar variable to None
    iterator = None  # Initialize iterator variable to None
    try:  # Begin outer try block to ensure cleanup
        pbar = create_progress_bar(
            videos,  # Iterable to wrap in progress bar
            desc=f"{BackgroundColors.GREEN}Processing Video Files from {BackgroundColors.CYAN}{INPUT_DIR}{BackgroundColors.GREEN}...{Style.RESET_ALL}",  # Description shown on the left
            bar_format=f"{{l_bar}}{BackgroundColors.CYAN}{{bar}}{Style.RESET_ALL}{{r_bar}}",  # Color only the progress bar itself in cyan
        )  # Create tqdm safely via factory

        iterator = pbar if pbar is not None else videos  # Choose the appropriate iterator for processing

        try:  # Iterate over files and handle user interruptions
            for video in iterator:  # Iterate over chosen iterator (tqdm or list)
                try:  # Attempt to compute the path to display in the progress bar
                    rel_path = os.path.relpath(video, INPUT_DIR)  # Compute relative path from INPUT_DIR
                except Exception:  # Fallback when relpath computation fails
                    rel_path = os.path.basename(video)  # Use basename as safe fallback
                if pbar is not None and hasattr(pbar, "set_description"):  # Update tqdm description only if available
                    pbar.set_description(f"{BackgroundColors.GREEN}Processing: {BackgroundColors.CYAN}{rel_path}{Style.RESET_ALL}")  # Update description with relative path
                swap_audio_tracks(video)  # Process the audio tracks for this video
        except KeyboardInterrupt:  # Handle user interrupt (Ctrl+C) gracefully
            print(f"{BackgroundColors.RED}Interrupted by user. Exiting...{Style.RESET_ALL}")  # Notify user of interruption
    finally:  # Ensure resources are cleaned up regardless of errors
        if pbar is not None and hasattr(pbar, "close"):  # If a tqdm bar was created, ensure it is closed
            pbar.close()  # Close tqdm to avoid broken destructor issues

    print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}All videos processed successfully.{Style.RESET_ALL}")

    (
        atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None
    )  # Register the play_sound function to be called when the program finishes


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
