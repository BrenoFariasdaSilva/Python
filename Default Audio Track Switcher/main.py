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
REMOVE_OTHER_AUDIO_TRACKS = False  # Set to True to remove other audio tracks after setting the default

DESIRED_LANGUAGES = {
    "English": ["english", "eng", "en"],  # Languages to prioritize when selecting default audio track
    "Brazilian Portuguese": ["brazilian", "portuguese", "pt-br", "pt"],  # Additional languages can be added here
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

    if VERBOSE and true_string != "":  # If the VERBOSE constant is set to True and the true_string is set
        print(true_string)  # Output the true statement string
    elif false_string != "":  # If the false_string is set
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

    cmd = [
        "ffprobe",  # Command to run ffprobe
        "-v",
        "error",  # Suppress unnecessary output
        "-select_streams",
        "a",  # Select audio streams
        "-show_entries",
        "stream=index:stream_tags=language",  # Show stream index and language tags
        "-of",
        "json",  # Output format as JSON
        video_path,  # Video file path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)  # Run the ffprobe command
    data = json.loads(result.stdout) if result.stdout else {}  # Parse the JSON output
    streams = data.get("streams", [])  # Get the list of audio streams

    tracks = []  # List to store audio track information
    for stream in streams:  # For each audio stream
        index = stream.get("index", None)  # Get the stream index
        language = stream.get("tags", {}).get("language", "und")  # Get the language tag, default to "und" (undefined)
        tracks.append({"index": index, "language": language})  # Add the track information to the list

    return tracks  # Return the list of audio tracks


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

    cmd = ["ffmpeg", "-y", "-i", video_path, "-map", "0:v"]  # Base command with video

    for idx in kept_indices:  # Map each kept audio track
        cmd += ["-map", f"0:a:{idx}"]  # Map audio track

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

    audio_tracks = get_audio_track_info(video_path)  # Get audio track information using ffprobe

    if len(audio_tracks) == 0:  # Check if any audio tracks were found
        print(
            f"{BackgroundColors.YELLOW}No audio tracks found for: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}"
        )
        return  # Skip this file

    desired_langs = get_desired_languages()  # Get list of desired languages
    kept_indices = []  # Indices of tracks to keep

    for i, track in enumerate(audio_tracks):  # For each audio track
        parts = track.split(",")  # Split the track info
        if len(parts) >= 3:  # If track info has enough parts
            lang = parts[2].lower().strip()  # Get language
            if lang in desired_langs:  # If language is desired
                kept_indices.append(i)  # Keep this track

    if not kept_indices:  # If no desired tracks found
        print(
            f"{BackgroundColors.YELLOW}No desired audio tracks found for: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}"
        )
        return  # Skip this file

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
    else:  # No English, use first kept
        default_track_index = kept_indices[0]  # Set first desired track as default
        print(
            f"{BackgroundColors.GREEN}Selected first desired audio track as default for: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}"
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

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Default Audio Track Switcher{BackgroundColors.GREEN}!{Style.RESET_ALL}\n"
    )

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
