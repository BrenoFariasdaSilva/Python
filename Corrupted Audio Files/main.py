import atexit  # For playing a sound when the program finishes
import ffmpeg  # For decoding audio files
import os  # For running a command in the terminal
import platform  # For getting the operating system name
from colorama import Style  # For coloring the terminal
from mutagen import File  # For reading audio file metadata
from tqdm import tqdm  # For creating a progress bar


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

# Sound Constants:
SOUND_COMMANDS = {
    "Darwin": "afplay",
    "Linux": "aplay",
    "Windows": "start",
}  # The commands to play a sound for each operating system
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav"  # The path to the sound file


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


def play_sound():
    """
    Plays a sound when the program finishes and skips if the operating system is Windows.
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


def find_audio_files(directory):
    """
    Recursively find all audio files (any format supported by Mutagen) in the given directory.

    :param directory: The directory to search for audio files.
    :return: A list of audio files found in the directory.
    """

    verbose_output(
        f"{BackgroundColors.YELLOW}Finding audio files in the directory: {BackgroundColors.CYAN}{directory}{Style.RESET_ALL}"
    )  # Output the verbose message

    audio_files = []  # Initialize an empty list to store audio files

    for root, _, files in os.walk(directory):  # Recursively walk through the directory
        for file in files:  # Iterate over the files in the current directory
            if file.lower().endswith(
                (".mp3", ".flac", ".ogg", ".aac", ".wav", ".m4a", ".wma")
            ):  # Check if the file is an audio file
                audio_files.append(os.path.join(root, file))  # Add the audio file to the list

    return audio_files  # Return the list of audio files


def check_audio_integrity(audio_files):
    """
    Check each audio file for corruption by verifying metadata, length, file size, bitrate, and attempting playback.

    :param audio_files: A list of audio files to check.
    :return: A list of corrupted audio files.
    """

    corrupted_files = []  # Initialize an empty list to store corrupted files

    for file in tqdm(
        audio_files, desc=f"{BackgroundColors.GREEN}Searching for corrupted audio files{Style.RESET_ALL}", unit="file"
    ):  # Iterate over the audio files with a progress bar
        try:  # Try to check the integrity of the audio file
            if os.path.getsize(file) == 0:  # Check if the file size is zero
                raise ValueError(f"File size is zero: {file}")  # Raise an exception if the file size is zero

            audio = File(file)  # Use Mutagen's File method, which automatically detects the audio format

            if audio.info.length <= 0:  # Check the length of the audio file
                raise ValueError(f"Invalid audio length: {file}")  # Raise an exception if the audio length is invalid

            if audio.info.bitrate <= 0:  # Check bitrate (only available in certain formats, such as MP3, FLAC, etc.)
                raise ValueError(f"Invalid bitrate: {file}")  # Raise an exception if the bitrate is invalid

            try:  # Attempt to decode the file using ffmpeg
                ffmpeg.input(file).output("-", format="null").run(quiet=True)  # Use ffmpeg to decode the audio file
            except ffmpeg.Error as e:  # If ffmpeg raises an error
                raise ValueError(
                    f"Corrupted audio file: {file}"
                ) from e  # Raise an exception indicating a corrupted audio file

        except Exception as e:  # If an exception is raised
            print(
                f"{BackgroundColors.RED}Corrupted audio file detected: {BackgroundColors.CYAN}{file}{Style.RESET_ALL}"
            )  # Output the corrupted audio file
            corrupted_files.append(file)  # Add the corrupted file to the list

    return corrupted_files  # Return the list of corrupted files


def main():
    """
    Main function.

    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Corrupted Audio Files Checker{BackgroundColors.GREEN}!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the Welcome message

    directory = os.getcwd()  # Get the current working directory
    audio_files = find_audio_files(directory)  # Find all audio files in the current directory

    if not audio_files:  # If no audio files are found
        print(
            f"{BackgroundColors.RED}No audio files found in the directory: {BackgroundColors.CYAN}{directory}{Style.RESET_ALL}"
        )
        return  # Exit the program

    corrupted_files = check_audio_integrity(audio_files)  # Check the integrity of the audio files

    if corrupted_files:  # If there are corrupted audio files
        print(f"\n{BackgroundColors.RED}Corrupted audio files detected:{Style.RESET_ALL}")
        for file in corrupted_files:  # Output the corrupted audio files
            print(file)  # Output the corrupted audio file
    else:  # If there are no corrupted audio files
        print(f"\n{BackgroundColors.GREEN}No corrupted audio files detected.{Style.RESET_ALL}")

    print(
        f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
    )  # Output the end of the program message

    atexit.register(play_sound)  # Register the function to play a sound when the program finishes


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
