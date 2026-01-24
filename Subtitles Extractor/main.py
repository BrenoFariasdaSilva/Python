"""
================================================================================
Subtitles Extractor
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-01-24
Description :
    Recursively searches for video files in the input directory and extracts all subtitle streams from each video file into .srt files. Each subtitle file is named after the video, with language and descriptive information. Progress bars are shown for processing. Logging is performed to both terminal and file.

    Key features include:
        - Recursive search for video files (.mkv, .mp4, .avi)
        - Extraction of all subtitle streams using ffprobe and ffmpeg
        - Output .srt files named with video, language, and descriptive info
        - Progress bar for file processing (tqdm)
        - Logging to terminal and file (Logger)
        - Notification sound on completion (optional)

Usage:
    1. Place video files in the INPUT_DIR directory (default: ./Input/).
    2. Ensure ffmpeg and ffprobe are installed and available in PATH.
    3. Run the script via Makefile or Python:
            $ make <target>   or   $ python main.py
    4. Extracted subtitles will be saved alongside each video file.

Outputs:
    - .srt files for each subtitle stream, named <video>.<language>[_descriptive].srt
    - Log file in ./Logs/main.log

TODOs:
    - Implement CLI argument parsing for input directory and options
    - Extend support for additional video formats
    - Add parallel processing for faster extraction
    - Improve error handling and reporting

Dependencies:
    - Python >= 3.7
    - tqdm
    - colorama
    - ffmpeg, ffprobe (external)

Assumptions & Notes:
    - Video files are placed in INPUT_DIR or its subdirectories
    - ffmpeg and ffprobe must be installed and in PATH
    - Output .srt files are saved in the same directory as the video
    - Sound notification is disabled on Windows
    - Logging is redirected to both terminal and file
"""

import atexit  # For playing a sound when the program finishes
import datetime  # For getting the current date and time
import json  # For handling JSON data
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import subprocess  # For running subprocess commands
import sys  # For system-specific parameters and functions
from colorama import Style  # For coloring the terminal
from Logger import Logger  # For logging output to both terminal and file
from pathlib import Path  # For handling file paths
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
INPUT_DIR = "./Input/"  # The input directory path
VIDEO_FILE_EXTENSIONS = [".mkv", ".mp4", ".avi"]  # List of video file extensions to process
SRT_OPTIONS = {  # Dictionary of languages and their possible subtitle codes
    "Portuguese": ["pt-BR", "pt", "pt-PT"],  # Portuguese subtitle codes
    "English": ["eng", "en", "en-US"],  # English subtitle codes
}

# Logger Setup:
logger = Logger(f"./Logs/{Path(__file__).stem}.log", clean=True)  # Create a Logger instance
sys.stdout = logger  # Redirect stdout to the logger
sys.stderr = logger  # Redirect stderr to the logger

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


def find_video_files(input_dir, extensions):
    """
    Recursively find all video files in the input directory with the given extensions.

    :param input_dir: Directory to search
    :param extensions: List of file extensions
    :return: List of file paths
    """
    
    video_files = []
    for root, _, files in os.walk(input_dir):
        for file in files:
            if any(file.lower().endswith(ext) for ext in extensions):
                video_files.append(os.path.join(root, file))
                
    return video_files


def get_video_name_and_dir(video_path):
    """
    Returns the base name and directory of the video file.
    """
    
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    video_dir = os.path.dirname(video_path)
    return video_name, video_dir

def get_subtitle_streams(video_path):
    """
    Uses ffprobe to get subtitle streams from a video file.
    Returns a list of stream dicts.
    """
    
    ffprobe_cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "s",
        "-show_entries", "stream=index:stream_tags=language,title:stream=codec_name",
        "-of", "json",
        video_path
    ]
    try:
        result = subprocess.run(ffprobe_cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        return info.get("streams", [])
    except Exception as e:
        print(f"{BackgroundColors.RED}Failed to probe {video_path}: {e}{Style.RESET_ALL}")
        return []

def get_subtitle_metadata(stream):
    """
    Extracts language, title, and descriptive info from a subtitle stream dict.
    Returns (lang_label, desc_label, idx).
    """
    
    idx = stream.get("index")
    tags = stream.get("tags", {})
    lang = tags.get("language", "und")
    title = tags.get("title", "")
    codec = stream.get("codec_name", "unknown")
    is_descriptive = "descript" in title.lower() or "sdh" in title.lower() or "cc" in title.lower()

    lang_label = None
    for lang_name, codes in SRT_OPTIONS.items():
        if lang in codes:
            lang_label = lang_name
            break
    if not lang_label:
        lang_label = lang

    desc_label = "_descriptive" if is_descriptive else ""
    return lang_label, desc_label, idx, codec

def extract_subtitle_stream(video_path, video_dir, video_name, lang_label, desc_label, idx, codec):
    """
    Uses ffmpeg to extract a single subtitle stream to an .srt or .sup file, depending on codec.
    """
    # Ensure unique filename by appending stream index if needed
    suffix = f"_{idx}" if idx is not None else ""
    # If codec is PGS or DVD, extract as .sup file
    if codec in {"hdmv_pgs_subtitle", "dvd_subtitle"}:
        sup_filename = f"{video_name}.{lang_label}{desc_label}{suffix}.sup"
        sup_path = os.path.join(video_dir, sup_filename)
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-map", f"0:s:{idx}",
            "-c:s", "copy",
            sup_path
        ]
        try:
            subprocess.run(ffmpeg_cmd, capture_output=True, check=True)
            print(f"{BackgroundColors.YELLOW}Extracted bitmap subtitle: {sup_path} (OCR required for text conversion){Style.RESET_ALL}")
        except Exception as e:
            print(f"{BackgroundColors.RED}Failed to extract bitmap subtitles from stream {idx} in {video_path}: {e}{Style.RESET_ALL}")
    else:
        srt_filename = f"{video_name}.{lang_label}{desc_label}{suffix}.srt"
        srt_path = os.path.join(video_dir, srt_filename)
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-i", video_path,
            "-map", f"0:s:{idx}",
            srt_path
        ]
        try:
            subprocess.run(ffmpeg_cmd, capture_output=True, check=True)
            print(f"{BackgroundColors.GREEN}Extracted: {srt_path}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{BackgroundColors.RED}Failed to extract subtitles from stream {idx} in {video_path}: {e}{Style.RESET_ALL}")

def extract_subtitles(video_path):
    """
    Extracts all subtitle streams from a video file and saves them as .srt files.

    :param video_path: Path to the video file
    :return: None
    """
    
    video_name, video_dir = get_video_name_and_dir(video_path)
    streams = get_subtitle_streams(video_path)
    # Supported subtitle codecs for .srt extraction
    supported_codecs = {"subrip", "text", "ass", "ssa", "hdmv_pgs_subtitle", "dvd_subtitle"}
    allowed_langs = set()
    for codes in SRT_OPTIONS.values():
        allowed_langs.update(codes)
    for stream in streams:
        lang_label, desc_label, idx, codec = get_subtitle_metadata(stream)
        tags = stream.get("tags", {})
        lang = tags.get("language", "und")
        if lang not in allowed_langs:
            print(f"{BackgroundColors.YELLOW}Skipping stream {idx} ({lang}) in {video_path}: language not in SRT_OPTIONS{Style.RESET_ALL}")
            continue
        if codec not in supported_codecs:
            print(f"{BackgroundColors.YELLOW}Skipping stream {idx} ({lang_label}) in {video_path}: unsupported codec '{codec}'{Style.RESET_ALL}")
            continue
        extract_subtitle_stream(video_path, video_dir, video_name, lang_label, desc_label, idx, codec)


def extract_subtitles_from_videos(video_files):
    """
    Extract subtitles from each video file, showing a progress bar.

    :param video_files: List of video file paths
    :return: None
    """

    for video_path in tqdm(video_files, desc="Processing videos", unit="file"):
        extract_subtitles(video_path)


def calculate_execution_time(start_time, finish_time):
    """
    Calculates the execution time between start and finish times and formats it as hh:mm:ss.

    :param start_time: The start datetime object
    :param finish_time: The finish datetime object
    :return: String formatted as hh:mm:ss representing the execution time
    """

    delta = finish_time - start_time  # Calculate the time difference
    hours, remainder = divmod(delta.seconds, 3600)  # Calculate the hours, minutes and seconds
    minutes, seconds = divmod(remainder, 60)  # Calculate the minutes and seconds
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"  # Format the execution time


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
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Subtitles Extractor{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
    )
    start_time = datetime.datetime.now()

    # Step 1: Find all video files recursively
    video_files = find_video_files(INPUT_DIR, VIDEO_FILE_EXTENSIONS)
    if not video_files:
        print(f"{BackgroundColors.YELLOW}No video files found in {BackgroundColors.CYAN}{INPUT_DIR}{Style.RESET_ALL}")
        return

    print(f"{BackgroundColors.GREEN}Found {len(video_files)} video file(s) to process.{Style.RESET_ALL}")

    # Step 2: Extract subtitles from each video file with a progress bar
    extract_subtitles_from_videos(video_files)

    finish_time = datetime.datetime.now()
    print(
        f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"
    )
    print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}")

    (
        atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None
    )


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
