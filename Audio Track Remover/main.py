"""
================================================================================
Remove Non-Default Audio Tracks from Video Files
================================================================================
Author      : Breno Farias da Silva
Created     : 2025-11-04
Description :
   This script removes all non-default audio tracks from video files located
   in the specified input directory. It identifies the default audio track
   using ffprobe and creates a cleaned version of each video file that contains
   only the video and the default audio stream.

   Key features include:
      - Automatic detection of the default audio stream in each video file
      - Removal of all other (non-default) audio tracks using FFmpeg
      - Optional replacement of original files after processing
      - Cross-platform structure and reusable utility functions
      - Sound notification when the script finishes (optional)

Usage:
   1. Set the INPUT_DIR path and verify FFmpeg is installed on your system.
   2. Run the script via terminal:
         $ python remove_audio_tracks.py
   3. Cleaned video files will be saved with the suffix "_clean" unless
      DELETE_OLD_FILES is set to True.

Outputs:
   - Cleaned video files (e.g., MyVideo_clean.mkv)
   - Optional replacement of original files if DELETE_OLD_FILES = True

TODOs:
   - Add support for subtitle track preservation
   - Implement CLI arguments for input directory and flags
   - Add logging and exception handling mechanisms

Dependencies:
   - Python >= 3.8
   - FFmpeg (installed and available in system PATH)
   - colorama (for terminal styling)

Assumptions & Notes:
   - Only video and the default audio track are preserved
   - Video formats supported: .mkv, .mp4, .avi, .mov
   - Tested on Windows; compatible with Linux and macOS
"""

import atexit  # For playing a sound when the program finishes
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import shutil  # For checking if a program is installed
import subprocess  # For running terminal commands
from colorama import Style  # For coloring the terminal
from tqdm import tqdm  # For progress bar


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
DELETE_OLD_FILES = False  # Set to True to replace original files with cleaned versions

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


def get_default_audio_index(file_path):
    """
    Retrieves the index of the default audio stream using ffprobe.

    :param file_path: Absolute path to the video file
    :return: Index of the default audio track, or first audio track if no default is found
    """

    cmd = [  # ffprobe command to get audio stream indices and default flags
        "ffprobe",
        "-v",
        "error",  # Suppress unnecessary output
        "-select_streams",
        "a",  # Select only audio streams
        "-show_entries",
        "stream=index:stream_tags=default",  # Show stream index and default tag
        "-of",
        "default=noprint_wrappers=1:nokey=1",  # Output format
        file_path,  # Input file
    ]

    result = (
        subprocess.run(cmd, capture_output=True, text=True).stdout.strip().split("\n")
    )  # Run ffprobe command and capture output

    default_index = None  # Initialize default index variable
    for i in range(0, len(result), 2):  # Iterate in pairs (index, default_flag)
        index = result[i].strip()  # Get the stream index
        is_default = result[i + 1].strip() if i + 1 < len(result) else "0"  # Get the default flag
        if is_default == "1":  # If this stream is marked as default
            default_index = index  # Set the default index
            break  # Exit the loop

    return (
        default_index if default_index is not None else result[0] if result else "0"
    )  # Return default index or first audio index or "0" if no audio streams


def get_audio_stream_indices(file_path):
    """
    Retrieve all audio stream indices from the specified video file using ffprobe.

    :param file_path: The path to the video file to probe
    :return: List of integers representing audio stream indices (empty if none are found or an error occurs)
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Retrieving audio stream indices for: {BackgroundColors.CYAN}{file_path}{Style.RESET_ALL}"
    )

    try:  # Prepare and execute ffprobe command to list audio stream indices
        probe_cmd = [
            "ffprobe",
            "-v",
            "error",  # Suppress non-error output
            "-select_streams",
            "a",  # Focus only on audio streams
            "-show_entries",
            "stream=index",  # Display only the stream index
            "-of",
            "default=noprint_wrappers=1:nokey=1",  # Format output with plain values
            file_path,  # File to analyze
        ]
        result = subprocess.run(
            probe_cmd, capture_output=True, text=True, check=True
        ).stdout.strip()  # Run and capture output
        return [int(x) for x in result.splitlines() if x.strip() != ""]  # Convert each line into an integer index
    except Exception:  # In case of failure (e.g., no audio streams or ffprobe error)
        return []  # Return an empty list gracefully


def build_audio_map_arguments(default_track, audio_indices):
    """
    Build the ffmpeg '-map' arguments to exclude non-default audio tracks while keeping all other streams.

    :param default_track: The index of the default audio stream to keep
    :param audio_indices: List of all audio stream indices
    :return: List of arguments to be appended to the ffmpeg command
    """

    ffmpeg_map_args = ["-map", "0"]  # Start by mapping all streams (audio, video, subtitles, etc.)
    for idx in audio_indices:  # Loop through audio stream indices
        if str(idx) != str(default_track):  # If this is not the default audio track
            ffmpeg_map_args.extend(["-map", f"-0:a:{idx}"])  # Exclude it using negative mapping

    return ffmpeg_map_args  # Return the complete argument list


def build_clean_output_path(file_path):
    """
    Build the temporary output path for the cleaned file by appending '_clean' to the original filename.

    :param file_path: The original file path
    :return: New file path with '_clean' added before the extension
    """

    base, ext = os.path.splitext(file_path)  # Split into base name and extension
    return f"{base}_clean{ext}"  # Return modified filename


def run_ffmpeg_command(cmd, file_path, temp_output):
    """
    Run the ffmpeg command to remove non-default audio tracks and handle any errors.

    :param cmd: The complete ffmpeg command to execute
    :param file_path: The original file path (for error reporting)
    :param temp_output: Path to the temporary cleaned file
    :return: True if ffmpeg executes successfully, False otherwise
    """

    verbose_output(f"{BackgroundColors.CYAN}Running: {' '.join(cmd)}{Style.RESET_ALL}")  # Print the executed command

    try:  # Execute ffmpeg with suppressed output
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True  # Success
    except subprocess.CalledProcessError as e:  # Handle ffmpeg execution errors
        print(f"{BackgroundColors.RED}ffmpeg failed for {file_path}: {e}{Style.RESET_ALL}")
        if os.path.exists(temp_output):  # If a temp file exists, clean it up
            try:  # Attempt to remove temp file
                os.remove(temp_output)  # Remove temp file
            except Exception:  # If cleanup fails
                pass  # Ignore cleanup failure
        return False  # Indicate failure


def replace_original_file(file_path, temp_output, pbar=None):
    """
    Replace the original file with the cleaned file if DELETE_OLD_FILES is True.
    Otherwise, keep both files.

    :param file_path: The path of the original file
    :param temp_output: The path of the cleaned file
    :param pbar: Optional progress bar object for status updates
    :return: None
    """

    if DELETE_OLD_FILES:  # Overwrite mode
        try:  # Attempt to replace the original file
            os.remove(file_path)  # Remove the original file
            os.rename(temp_output, file_path)  # Rename temp file to original name
            if pbar:  # Update progress bar if available
                pbar.set_postfix_str("Replaced original", refresh=True)  # Update progress bar
        except Exception as e:  # If replacement fails
            if pbar:  # Update progress bar if available
                pbar.set_postfix_str("Failed to replace", refresh=True)  # Update progress bar
            else:  # Print error message if no progress bar
                print(f"{BackgroundColors.RED}Failed to replace original file for {file_path}: {e}{Style.RESET_ALL}")
            if os.path.exists(temp_output):  # Attempt cleanup
                try:  # Remove temp file
                    os.remove(temp_output)  # Remove temp file
                except Exception:  # If cleanup fails
                    pass
    else:  # Keep both versions
        if pbar:  # Update progress bar if available
            pbar.set_postfix_str("Saved clean version", refresh=True)  # Update progress bar
        else:  # Print message if no progress bar
            print(f"{BackgroundColors.GREEN}Saved cleaned file as: {temp_output}{Style.RESET_ALL}")


def remove_other_audio_tracks(file_path, pbar=None):
    """
    Keeps only the default audio track (as identified by get_default_audio_index())
    and removes all other audio streams. Subtitle tracks and all other stream types are preserved.

    :param file_path: The full path of the video file to process
    :param pbar: Optional progress bar object for status updates
    :return: None
    """

    default_track = get_default_audio_index(file_path)  # Identify the default audio track
    verbose_output(f"Default audio track for {file_path}: {default_track}")  # Inform which track is the default

    audio_indices = get_audio_stream_indices(file_path)  # Retrieve all audio stream indices
    if not audio_indices:  # If no audio tracks are found
        verbose_output(f"{BackgroundColors.YELLOW}No audio streams found in {file_path}{Style.RESET_ALL}")
        if pbar:  # Update progress bar if available
            pbar.set_postfix_str("No audio streams", refresh=True)
        return  # Exit the function

    ffmpeg_map_args = build_audio_map_arguments(default_track, audio_indices)  # Build '-map' exclusion arguments
    temp_output = build_clean_output_path(file_path)  # Prepare temporary output filename

    cmd = ["ffmpeg", "-i", file_path] + ffmpeg_map_args + ["-c", "copy", temp_output, "-y"]  # Build ffmpeg command

    if run_ffmpeg_command(cmd, file_path, temp_output):  # If ffmpeg executed successfully
        replace_original_file(file_path, temp_output, pbar)  # Replace or keep original depending on settings
    elif pbar:  # If ffmpeg failed and progress bar is available
        pbar.set_postfix_str("Processing failed", refresh=True)  # Update progress bar


def process_videos_in_directory():
    """
    Processes all video files in the specified INPUT_DIR, removing all non-default
    audio tracks from each.

    :param: None
    :return: None
    """

    # First, collect all video files
    video_files = []
    for root, _, files in os.walk(INPUT_DIR):  # Walk through the input directory
        for file in files:  # Loop through all files
            if file.lower().endswith((".mkv", ".mp4", ".avi", ".mov")):  # Check for video file extensions
                full_path = os.path.join(root, file)  # Get the full file path
                video_files.append(full_path)  # Add to the list

    # Process files with a progress bar
    if video_files:
        with tqdm(
            total=len(video_files),
            desc="Processing videos",
            unit="file",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
            colour="green",
        ) as pbar:
            for full_path in video_files:
                # Update progress bar description with current file
                filename = os.path.basename(full_path)
                pbar.set_description(f"Processing: {filename[:50]}")  # Limit filename length
                remove_other_audio_tracks(full_path, pbar)  # Remove non-default audio tracks
                pbar.update(1)  # Update progress bar
    else:
        print(f"{BackgroundColors.YELLOW}No video files found in {INPUT_DIR}{Style.RESET_ALL}")


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
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Audio Track Cleaner{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
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
