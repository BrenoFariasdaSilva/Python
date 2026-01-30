import atexit  # For playing a sound when the program finishes
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import pysubs2  # For handling subtitle timing
import re  # For parsing the offset string
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
OFFSET = "-00h00m00s5000ms"  # Offset to apply to all subtitles
REPLACE_EXISTING_SRT = True  # Set to True to replace existing .srt files
INPUT_DIRECTORY = "./Input"  # Input directory to search for subtitles

# Sound Constants:
SOUND_COMMANDS = {"Darwin": "afplay", "Linux": "aplay", "Windows": "start"}  # Commands to play a sound
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav"  # Path to sound file

# Exclusions:
EXCLUDE_DIRS = {".assets", ".venv"}  # Directories to exclude
EXCLUDE_FILES = {"./main.py", "./Makefile", "./requirements.txt"}  # Files to exclude


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
    )  # Output the verbose message

    return os.path.exists(filepath)  # Return True if the file or folder exists, False otherwise


def get_directories():
    """
    Get all directories (including subdirectories) inside the input directory that contain at least one .srt file.

    :param none
    :return: List of directories in absolute paths
    """

    input_dir_abs = os.path.abspath(INPUT_DIRECTORY)  # Ensure input directory is absolute and normalized
    matching_dirs = []  # Store directories that contain .srt files

    for root, dirs, files in os.walk(input_dir_abs):  # Walk through all subdirectories
        if any(file.lower().endswith(".srt") for file in files):  # Check if current dir has at least one .srt file
            matching_dirs.append(os.path.normpath(os.path.abspath(root)))  # Add the directory if it qualifies

    return matching_dirs  # Return the list of directories that contain .srt files


def parse_offset(offset_str):
    """
    Parses an offset string like +00h00m00s0500ms into milliseconds.

    :param offset_str: String offset (e.g. '+00h00m00s0500ms' or '-00h00m05s000ms')
    :return: Integer offset in milliseconds
    """

    sign = 1 if offset_str.startswith("+") else -1  # Determine the sign of the offset
    offset_str = offset_str[1:]  # Remove + or -

    # Use regex to safely extract all time units (defaulting to 0 if missing)
    match = re.match(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?(?:(\d+)ms)?", offset_str)  # Match the offset string
    if not match:  # If the offset string does not match the expected format
        raise ValueError(f"Invalid offset format: {offset_str}")

    hours = int(match.group(1) or 0)  # Extract hours or default to 0
    minutes = int(match.group(2) or 0)  # Extract minutes or default to 0
    seconds = int(match.group(3) or 0)  # Extract seconds or default to 0
    milliseconds = int(match.group(4) or 0)  # Extract milliseconds or default to 0

    total_ms = ((hours * 3600 + minutes * 60 + seconds) * 1000) + milliseconds  # Calculate total milliseconds

    return sign * total_ms  # Return the total milliseconds with the correct sign


def get_srt_file(base_name):
    """
    Returns the appropriate subtitle file name if it exists in the same directory
    or any subdirectory.

    :param base_name: The base name of the video file
    :return: The subtitle file name if it exists, None otherwise
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Searching for subtitle file for: {BackgroundColors.CYAN}{base_name}{Style.RESET_ALL}"
    )

    base_dir = os.path.dirname(os.path.abspath(base_name))  # Get directory of the video
    base_no_ext = os.path.splitext(os.path.basename(base_name))[0]  # Get file name without extension

    for root, _, files in os.walk(base_dir):  # Walk through all subdirs
        for file in files:  # For each file in the directory
            if file.startswith(base_no_ext) and file.endswith(
                ".srt"
            ):  # If the file matches the base name and has .srt extension
                return os.path.join(root, file)  # Return the full path to the subtitle file

    return None  # Return None if no subtitle file is found


def adjust_subtitle_timing(srt_file, offset_ms):
    """
    Adjusts the start and end times of all subtitles by offset_ms.

    :param srt_file: Subtitle file path
    :param offset_ms: Offset in milliseconds
    :return: None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Adjusting subtitle timing for: {BackgroundColors.CYAN}{srt_file}{Style.RESET_ALL}"
    )

    try:  # Try to adjust the subtitle timing
        srt_file = os.path.normpath(srt_file)  # Normalize the file path
        ext = os.path.splitext(srt_file)[1].lower()  # Get the file extension

        if ext != ".srt":  # If the file extension is not .srt
            print(
                f"{BackgroundColors.YELLOW}Skipping unsupported file: {BackgroundColors.CYAN}{srt_file}{Style.RESET_ALL}"
            )
            return  # Exit the function

        subs = pysubs2.load(srt_file, format_="srt", encoding="utf-8")  # Load the subtitle file
        subs.shift(ms=offset_ms)  # Shift the subtitle timing by offset_ms

        adjusted_path = (
            srt_file if REPLACE_EXISTING_SRT else os.path.splitext(srt_file)[0] + f"_offset{ext}"
        )  # Determine the adjusted file path
        subs.save(adjusted_path, format_="srt", encoding="utf-8")  # Save the adjusted subtitle file

        verbose_output(
            f"{BackgroundColors.GREEN}Adjusted subtitle saved as: {BackgroundColors.CYAN}{adjusted_path}{Style.RESET_ALL}"
        )

    except Exception as e:  # If an error occurs while adjusting the subtitle timing
        print(f"{BackgroundColors.RED}Error adjusting subtitle {srt_file}: {e}{Style.RESET_ALL}")


def process_directory(directory, offset_ms):
    """
    Processes all subtitles in a directory and applies the offset.

    :param directory: Directory path
    :param offset_ms: Offset in milliseconds
    :return: None
    """

    verbose_output(f"{BackgroundColors.GREEN}Processing directory: {BackgroundColors.CYAN}{directory}{Style.RESET_ALL}")

    directory_abs = os.path.normpath(os.path.abspath(directory))  # Get absolute path of the directory
    srt_files = [
        os.path.join(directory_abs, f) for f in os.listdir(directory_abs) if f.lower().endswith(".srt")
    ]  # List of .srt files in the directory

    for srt_file in tqdm(
        srt_files,
        desc=f"{BackgroundColors.GREEN}Adjusting subtitles in {BackgroundColors.CYAN}{os.path.basename(directory_abs)}",
        unit="file",
    ):  # For each .srt file in the directory with a progress bar
        adjust_subtitle_timing(srt_file, offset_ms)  # Adjust the subtitle timing


def process_all_directories(directories, offset_ms):
    """
    Applies offset adjustment to all subtitle files in the directories.

    :param directories: List of directories
    :param offset_ms: Offset in milliseconds
    :return: None
    """

    for directory in directories:  # For each directory in the list of directories
        process_directory(directory, offset_ms)  # Process the directory

    print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}All subtitles adjusted successfully.{Style.RESET_ALL}")


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
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Subtitle Offset Adjuster{BackgroundColors.GREEN}!{Style.RESET_ALL}\n"
    )

    os.makedirs(INPUT_DIRECTORY, exist_ok=True)  # Ensure the input directory exists

    dirs = get_directories()  # Get all directories with .srt files
    if not dirs:  # If no directories were found
        print(
            f"{BackgroundColors.RED}No directories found in {BackgroundColors.CYAN}Input{BackgroundColors.RED}. Please add .srt files to adjust.{Style.RESET_ALL}"
        )
        return  # Exit the program

    offset_ms = parse_offset(OFFSET)  # Parse the offset string into milliseconds
    verbose_output(
        f"{BackgroundColors.GREEN}Applying offset of {BackgroundColors.CYAN}{OFFSET}{BackgroundColors.GREEN} ({offset_ms} ms){Style.RESET_ALL}"
    )

    process_all_directories(dirs, offset_ms)  # Process all directories

    print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}")
    atexit.register(play_sound)


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
