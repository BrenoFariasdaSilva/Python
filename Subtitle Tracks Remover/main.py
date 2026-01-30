"""
================================================================================
Subtitle Tracks Remover
================================================================================
Author      : Breno Farias da Silva
Created     : 2025-11-04
Description :
   This script scans all video files inside a specified directory and removes
   all subtitle tracks from them. It keeps all existing audio and video streams
   unchanged.

   The script works by:
      - Detecting all streams using ffprobe
      - Mapping only video and audio streams to the output
      - Saving changes to a temporary file and optionally replacing the original

Usage:
   1. Set the INPUT_DIR path and ensure FFmpeg/FFprobe are installed.
   2. Run the script:
         $ python main.py
   3. Processed files will overwrite originals if DELETE_OLD_FILES = True.
      Otherwise, files are saved with the suffix `_no_subs`.

Outputs:
   - Updated video files with all subtitles removed
   - Progress bar showing processing status per file
   - Console feedback for success or failure per video

Key Features:
   - Complete removal of all subtitle streams
   - Fully preserved audio and video streams
   - No re-encoding (stream copy)
   - Optional sound notification when finished

TODOs:
   - Support CLI arguments for input directory and options
   - Add logging and improved exception handling

Dependencies:
   - Python >= 3.8
   - FFmpeg and FFprobe in system PATH
   - colorama (for colored terminal output)
   - tqdm (for progress bar)

Assumptions & Notes:
   - Video and audio streams are untouched; all subtitle streams are removed
   - Supported formats: .mkv, .mp4, .avi, .mov
   - Works on Windows, Linux, and macOS (automatic FFmpeg installation included)
"""

import atexit  # For playing a sound when the program finishes
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import shutil  # For checking if a program is installed
import subprocess  # For running terminal commands
from colorama import Style  # For coloring the terminal
from tqdm import tqdm  # For displaying progress bars


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
INPUT_DIR = r"./Input"  # Path to the directory with video files
DELETE_OLD_FILES = True  # Set to True to replace original files with cleaned versions
FILES_FORMAT = (".mkv", ".mp4", ".avi", ".mov")  # Tuple of video file extensions to process

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


def remove_subtitles(full_path):
    """
    Removes all subtitle streams from the given video file.
    Works in-place by producing a temporary file and optionally replacing the original
    if DELETE_OLD_FILES is True.

    :param full_path: Path to the video file
    :return: True on success, False on failure
    """

    base, ext = os.path.splitext(full_path)  # Split file path into base and extension
    temp_output = f"{base}_no_subs{ext}"  # Temporary output file path

    # FFmpeg command to copy only video and audio streams, excluding subtitles
    cmd = [
        "ffmpeg",
        "-i",
        full_path,
        "-map",
        "0:v",  # Map all video streams
        "-map",
        "0:a",  # Map all audio streams
        "-c",
        "copy",  # Stream copy, no re-encoding
        temp_output,
        "-y",  # Output file, overwrite if exists
    ]

    try:  # Run ffmpeg command
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)  # Capture output
    except subprocess.CalledProcessError as e:  # Handle ffmpeg errors
        print(f"{BackgroundColors.RED}Failed to remove subtitles from {full_path}{Style.RESET_ALL}")
        if e.stderr:  # If there is stderr output
            print(f"{BackgroundColors.RED}ffmpeg stderr:\n{e.stderr}{Style.RESET_ALL}")
        return False  # Indicate failure

    if DELETE_OLD_FILES:  # Overwrite mode
        try:  # Attempt to replace the original file
            os.replace(temp_output, full_path)  # Replace original file with temp file
        except Exception as e:  # If replacement fails
            print(f"{BackgroundColors.RED}Failed to replace file: {e}{Style.RESET_ALL}")
            return False  # Indicate failure
    else:  # Keep both files
        print(f"{BackgroundColors.GREEN}Saved without subtitles as: {temp_output}{Style.RESET_ALL}")

    return True  # Indicate success


def process_videos_in_directory():
    """
    Processes all video files in the specified INPUT_DIR, removing all
    subtitle tracks from them.

    :param: None
    :return: None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Processing video files in directory: {BackgroundColors.CYAN}{INPUT_DIR}{Style.RESET_ALL}"
    )  # Output the verbose message

    video_files = []  # List to hold all video file paths
    for root, _, files in os.walk(INPUT_DIR):  # Walk through the input directory
        for file in files:  # Loop through all files
            if file.lower().endswith(FILES_FORMAT):  # Check for video file extensions
                video_files.append(os.path.join(root, file))  # Add the full file path to the list

    for full_path in tqdm(
        video_files, desc=f"Processing Videos", unit="file"
    ):  # Loop through all video files with a progress bar
        result = remove_subtitles(full_path)  # Remove all subtitle tracks
        if not result:  # If removing subtitles failed
            print(
                f"{BackgroundColors.RED}Failed to remove subtitles from: {BackgroundColors.CYAN}{full_path}{Style.RESET_ALL}"
            )
            continue  # Skip to the next file


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
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Subtitle Tracks Remover{BackgroundColors.GREEN} Program!{Style.RESET_ALL}"
    )  # Output the welcome message

    install_ffmpeg_and_ffprobe()  # Ensure ffmpeg and ffprobe are installed

    process_videos_in_directory()  # Process all videos in the input directory

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
