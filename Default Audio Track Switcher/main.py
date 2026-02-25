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
import shutil  # For checking if a command exists
import subprocess  # For running terminal commands
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

# These will be set by command-line arguments in main()
REMOVE_OTHER_AUDIO_TRACKS = True  # Set to True to remove other audio tracks after setting the default
REMOVE_SUBTITLE_TRACKS = True  # Set to True to remove all subtitle tracks

DESIRED_LANGUAGES = {  # Dictionary of desired languages with their corresponding language codes (case-insensitive)
    "English": ["english", "eng", "en"],  # Languages to prioritize when selecting default audio track
    "Brazilian Portuguese": ["brazilian", "portuguese", "pt-br", "pt"],  # Additional languages can be added here
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
            tags = stream.get("tags", {}) or {}  # Get tags dict for language/title metadata
            language = tags.get("language") or tags.get("lang") or "und"  # Prefer language tag or fallback
            title = tags.get("title", "")  # Get title tag if present
            disposition = stream.get("disposition", {}) or {}  # Get disposition dict if present
            tracks.append({  # Append detailed audio track info for classification
                "global_index": index,  # Global stream index for ffmpeg mapping
                "audio_pos": audio_count,  # Physical position among audio streams (0-based)
                "tags": tags,  # Raw tags mapping
                "language": language,  # Primary language value discovered
                "title": title,  # Title metadata if present
                "disposition": disposition,  # Disposition flags
            })
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
            tags = stream.get("tags", {}) or {}  # Get tags dict for language/title metadata
            language = tags.get("language") or tags.get("lang") or "und"  # Prefer language tag or fallback
            title = tags.get("title", "")  # Get title tag if present
            disposition = stream.get("disposition", {}) or {}  # Get disposition dict if present
            subs.append({  # Append detailed subtitle track info for classification
                "global_index": index,  # Global stream index for ffmpeg mapping
                "sub_pos": sub_count,  # Physical position among subtitle streams (0-based)
                "tags": tags,  # Raw tags mapping
                "language": language,  # Primary language value discovered
                "title": title,  # Title metadata if present
                "disposition": disposition,  # Disposition flags
            })
            sub_count += 1  # Increment physical subtitle position counter

    return subs  # Return the list of detailed subtitle tracks


def classify_streams(video_path):
    """
    Classify audio and subtitle streams as DESIRED or UNDESIRED using DESIRED_LANGUAGES and UNDESIRED_LANGUAGES.

    :param video_path: Path to the video file
    :return: Tuple (audio_streams, subtitle_streams) each being a list of dicts with 'classification'
    """

    desired_aliases = {alias.lower() for aliases in DESIRED_LANGUAGES.values() for alias in aliases}  # Build set of desired aliases
    undesired_aliases = {alias.lower() for aliases in UNDESIRED_LANGUAGES.values() for alias in aliases}  # Build set of undesired aliases

    audio_streams = get_audio_tracks(video_path)  # Get detailed audio streams for the file
    subtitle_streams = get_subtitle_tracks(video_path)  # Get detailed subtitle streams for the file

    for a in audio_streams:  # Classify each audio stream
        matched_desired = False  # Flag marking desired match
        matched_undesired = False  # Flag marking undesired match
        values = []  # List of metadata values to match against aliases
        values.append(str(a.get("language", "")).lower())  # Add language tag to matching values
        values.append(str(a.get("title", "")).lower())  # Add title tag to matching values
        for v in a.get("tags", {}).values():  # Add all tag values to the matching pool
            try:  # Ensure safe conversion to string
                values.append(str(v).lower())  # Append tag value lowercased
            except Exception:  # Ignore any problematic tag values
                continue  # Continue on tag parsing error

        for v in values:  # Evaluate all collected metadata values
            if any(alias in v for alias in desired_aliases):  # If any desired alias is found
                matched_desired = True  # Mark as desired
                break  # Stop searching for this stream
            if any(alias in v for alias in undesired_aliases):  # If any undesired alias is found
                matched_undesired = True  # Mark as undesired
                break  # Stop searching for this stream

        if matched_desired:  # If desired matched then classify as desired
            a["classification"] = "desired"  # Label the audio stream as desired
        else:  # Otherwise classify as undesired per strict mode
            a["classification"] = "undesired"  # Label the audio stream as undesired

    for s in subtitle_streams:  # Classify each subtitle stream
        matched_desired = False  # Flag marking desired match
        matched_undesired = False  # Flag marking undesired match
        values = []  # List of metadata values to match against aliases
        values.append(str(s.get("language", "")).lower())  # Add language tag to matching values
        values.append(str(s.get("title", "")).lower())  # Add title tag to matching values
        for v in s.get("tags", {}).values():  # Add all tag values to the matching pool
            try:  # Ensure safe conversion to string
                values.append(str(v).lower())  # Append tag value lowercased
            except Exception:  # Ignore any problematic tag values
                continue  # Continue on tag parsing error

        for v in values:  # Evaluate all collected metadata values
            if any(alias in v for alias in desired_aliases):  # If any desired alias is found
                matched_desired = True  # Mark as desired
                break  # Stop searching for this stream
            if any(alias in v for alias in undesired_aliases):  # If any undesired alias is found
                matched_undesired = True  # Mark as undesired
                break  # Stop searching for this stream

        if matched_desired:  # If desired matched then classify as desired
            s["classification"] = "desired"  # Label the subtitle stream as desired
        else:  # Otherwise classify as undesired per strict mode
            s["classification"] = "undesired"  # Label the subtitle stream as undesired

    return audio_streams, subtitle_streams  # Return classified audio and subtitle stream lists


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

    default_audio_pos = kept_audio_positions[0]  # Choose first desired audio position as default
    default_sub_pos = kept_sub_positions[0] if kept_sub_positions else None  # Choose first desired subtitle if present

    cmd = ["ffmpeg", "-y", "-i", video_path, "-map", "0", "-map", "-0:a"]  # Start command by mapping all and dropping audio
    cmd += ["-map", "-0:s"]  # Drop all subtitle streams to re-add only desired ones

    for pos in kept_audio_positions:  # Re-add each desired audio stream by physical position
        cmd += ["-map", f"0:a:{pos}"]  # Map desired audio stream

    for pos in kept_sub_positions:  # Re-add each desired subtitle stream by physical position
        cmd += ["-map", f"0:s:{pos}"]  # Map desired subtitle stream

    cmd += ["-c", "copy"]  # Use stream copy to avoid re-encoding

    for i, pos in enumerate(kept_audio_positions):  # Set dispositions for audio streams in new output order
        if pos == default_audio_pos:  # If this mapped audio is the chosen default
            cmd += [f"-disposition:a:{i}", "default"]  # Set default disposition for this audio
        else:  # Otherwise clear default flag
            cmd += [f"-disposition:a:{i}", "0"]  # Clear default disposition for this audio

    if default_sub_pos is not None:  # Only set subtitle dispositions if a desired subtitle default exists
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

    if REMOVE_SUBTITLE_TRACKS:
        cmd += ["-map", "-0:s"]

    for idx in kept_indices:  # Map each kept audio track
        cmd += ["-map", f"0:a:{idx}"]  # Re-add desired audio tracks

    cmd += ["-c", "copy"]  # Copy codecs

    for i, idx in enumerate(kept_indices):  # Set dispositions
        if idx == default_track_index:  # If this is the default track
            cmd += ["-disposition:a:" + str(i), "default"]  # Set as default
        else:  # If this is not the default track
            cmd += ["-disposition:a:" + str(i), "0"]  # Unset default

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
    global REMOVE_OTHER_AUDIO_TRACKS, REMOVE_SUBTITLE_TRACKS

    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Process video files and manage audio tracks and subtitles."
    )
    parser.add_argument(
        "--remove-other-audio",
        action="store_true",
        help="Remove audio tracks not in the desired languages list"
    )
    parser.add_argument(
        "--remove-subtitles",
        action="store_true",
        help="Remove all subtitle tracks from the video files"
    )
    args = parser.parse_args()

    # Update global constants based on arguments
    REMOVE_OTHER_AUDIO_TRACKS = args.remove_other_audio
    REMOVE_SUBTITLE_TRACKS = args.remove_subtitles

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Default Audio Track Switcher{BackgroundColors.GREEN}!{Style.RESET_ALL}\n"
    )

    if REMOVE_OTHER_AUDIO_TRACKS:
        print(f"{BackgroundColors.YELLOW}Mode: Removing non-desired audio tracks{Style.RESET_ALL}")
    if REMOVE_SUBTITLE_TRACKS:
        print(f"{BackgroundColors.YELLOW}Mode: Removing subtitle tracks{Style.RESET_ALL}")
    if REMOVE_OTHER_AUDIO_TRACKS or REMOVE_SUBTITLE_TRACKS:
        print()  # Add blank line for spacing

    install_ffmpeg_and_ffprobe()  # Ensure ffmpeg and ffprobe are installed

    if not verify_filepath_exists(INPUT_DIR):  # If the input directory does not exist
        print(f"{BackgroundColors.RED}Input directory not found: {BackgroundColors.CYAN}{INPUT_DIR}{Style.RESET_ALL}")
        return  # Exit the program

    videos = find_videos(INPUT_DIR, VIDEO_FILE_EXTENSIONS)  # Find all videos in the input directory
    if not videos:  # If no videos were found
        print(f"{BackgroundColors.YELLOW}No video files found in {INPUT_DIR}{Style.RESET_ALL}")
        return  # Exit the program

    pbar = tqdm(
        videos,
        desc=f"{BackgroundColors.GREEN}Processing Video Files from {BackgroundColors.CYAN}{INPUT_DIR}{BackgroundColors.GREEN}...{Style.RESET_ALL}",
    )  # Initialize progress bar
    for video in pbar:  # For each video found
        pbar.set_description(
            f"{BackgroundColors.GREEN}Processing: {BackgroundColors.CYAN}{os.path.basename(video)}{Style.RESET_ALL}"
        )  # Update description with current file name
        swap_audio_tracks(video)  # Swap the audio tracks

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
