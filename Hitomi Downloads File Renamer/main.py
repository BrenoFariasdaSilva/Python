import atexit  # For playing a sound when the program finishes
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For regular expressions
from colorama import Style  # For coloring the terminal


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


def clean_filename(filename):
    """
    Removes the last whitespace before the opening brace, the content between the braces, the braces themselves, and any emojis from the filename.

    :param filename: The filename to clean.
    :return: The cleaned filename.
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Cleaning the filename: {BackgroundColors.CYAN}{filename}{Style.RESET_ALL}"
    )  # Output the verbose message

    pattern = r"\s*\([^)]*\)"  # Regular expression to match a space, opening brace, content, and closing brace.

    emoji_pattern = re.compile(  # Regular expression to match emojis.
        r"[\U0001F600-\U0001F64F"  # Emoticons
        r"|\U0001F300-\U0001F5FF"  # Symbols & Pictographs
        r"|\U0001F680-\U0001F6FF"  # Transport & Map Symbols
        r"|\U0001F1E0-\U0001F1FF"  # Flags (iOS)
        r"|\U00002700-\U000027BF"  # Dingbats
        r"|\U00002600-\U000026FF"  # Miscellaneous Symbols
        r"|\U00002B50-\U00002B55"  # Stars
        r"|\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        r"|\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        r"|\U00002500-\U00002BEF"  # Miscellaneous Symbols
        r"|\U0001F100-\U0001F1FF"  # Enclosed Alphanumeric Supplement
        r"]+",
        flags=re.UNICODE,  # Flags
    )  # Emojis

    filename = re.sub(pattern, "", filename)  # Remove the pattern from the filename.

    return emoji_pattern.sub("", filename)  # Remove the emojis from the filename.


def rename_files_in_dir_recursively(base_dir):
    """
    Renames files in the given directory and its subdirectories recursively to remove
    patterns like " (some_text)" and emojis.

    :param base_dir: The base directory to start renaming files.
    :return None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Renaming files in the directory: {BackgroundColors.CYAN}{base_dir}{Style.RESET_ALL}"
    )  # Output the verbose message

    for root, dirs, files in os.walk(base_dir):  # Recursively traverses directories
        for file in files:  # For each file in the directory
            original_path = os.path.join(root, file)  # Get the original path of the file
            cleaned_filename = clean_filename(file)  # Clean the filename

            if file != cleaned_filename:  # Rename only if the name was changed.
                new_path = os.path.join(root, cleaned_filename)  # Get the new path of the file
                try:  # Try to rename the file
                    os.rename(original_path, new_path)  # Rename the file
                    print(
                        f"{BackgroundColors.GREEN}Renamed file {BackgroundColors.CYAN}{original_path}{BackgroundColors.GREEN} to {BackgroundColors.CYAN}{new_path}{Style.RESET_ALL}"
                    )  # Output the success message
                except Exception as e:
                    print(
                        f"{BackgroundColors.RED}Error renaming file {BackgroundColors.CYAN}{original_path}{BackgroundColors.RED} to {BackgroundColors.CYAN}{new_path}{BackgroundColors.RED}: {e}{Style.RESET_ALL}"
                    )  # Output the error message


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


def main():
    """
    Main function.

    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Hitomi Downloader File Renamer{BackgroundColors.GREEN}!{Style.RESET_ALL}"
    )  # Output the welcome message

    root_directory = os.getcwd()  # Get the current working directory
    rename_files_in_dir_recursively(
        root_directory
    )  # Rename files in the current directory and its subdirectories recursively

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
