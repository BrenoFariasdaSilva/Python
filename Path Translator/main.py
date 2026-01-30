import atexit  # For playing a sound when the program finishes
import os  # For path handling and walking directories
import platform  # For getting the operating system name
from colorama import Style  # For terminal styling
from deep_translator import GoogleTranslator  # For translating text


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

# File Constants:
CURRENT_FILE = os.path.basename(__file__)  # Get the current file name

# Input constant for the list of directories to search. Empty list or list with empty string means current directory.
SEARCH_DIRS = [""]  # Set this to a list of directory paths or leave empty for the current directory.


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


def is_english(text):
    """
    Checks whether a given string is likely written in English.

    :param text: Input string to check
    :return: True if the string is likely English, False otherwise
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Checking if the string is in English: {BackgroundColors.CYAN}{text}{Style.RESET_ALL}"
    )  # Output the verbose message

    try:  # Try to detect the language of the text
        translated = GoogleTranslator(source="auto", target="en").translate(text)  # Translate the text to English
        return (
            text.lower() == translated.lower()
        )  # Check if the original text is equal to the translated text (case insensitive)
    except Exception as e:  # If an error occurs during language detection
        print(
            f"{BackgroundColors.RED}⚠️ Failed to detect language for: {text}: {e}{Style.RESET_ALL}"
        )  # Output the error message
        return True  # fallback: assume it's English to avoid unnecessary renaming


def safe_translate(text):
    """
    Safely translates a given string to English using GoogleTranslator.

    :param text: String to translate
    :return: Translated string, or original text if translation fails
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Translating text: {BackgroundColors.CYAN}{text}{Style.RESET_ALL}"
    )  # Output the verbose message

    try:  # Try to translate the text
        translated = GoogleTranslator(source="auto", target="en").translate(text)  # Translate the text to English
        verbose_output(
            f'{BackgroundColors.GREEN}Translated "{text}" → "{translated}"{Style.RESET_ALL}'
        )  # Output the translated text
        return translated  # Return the translated text
    except Exception as e:  # If an error occurs during translation
        print(
            f'{BackgroundColors.RED}❌ Failed to translate text "{BackgroundColors.CYAN}{text}{BackgroundColors.RED}": {e}{Style.RESET_ALL}'
        )  # Output the error message
        return text  # Fallback to original


def rename_path_if_needed(path):
    """
    Renames a file or directory if its name is not in English.

    :param path: Path to file or folder
    :return: New path if renamed, original path otherwise
    """

    verbose_output(f"{BackgroundColors.GREEN}Renaming path if needed: {BackgroundColors.CYAN}{path}{Style.RESET_ALL}")

    base = os.path.basename(path)  # Get the base name of the path

    if not is_english(base):  # If the base name is not in English
        translated_name = safe_translate(base)  # Translate the base name to English
        parent = os.path.dirname(path)  # Get the parent directory of the path
        new_path = os.path.join(parent, translated_name)  # Create the new path with the translated name

        try:  # Try to rename the file or directory
            os.rename(path, new_path)  # Rename the file or directory
            print(
                f'{BackgroundColors.GREEN}📁 Renamed: "{BackgroundColors.CYAN}{base}{BackgroundColors.GREEN}" → "{BackgroundColors.CYAN}{translated_name}{BackgroundColors.GREEN}"{Style.RESET_ALL}'
            )  # Output the renamed path
            return new_path  # Return the new path
        except Exception as e:  # If an error occurs during renaming
            print(
                f'{BackgroundColors.RED}❌ Failed to rename "{BackgroundColors.CYAN}{path}{BackgroundColors.RED}": {e}{Style.RESET_ALL}'
            )  # Output the error message

    return path  # Return the original path if no renaming was done


def walk_and_translate(root="."):
    """
    Walks through the directory structure and renames files/folders with CJK names.

    :param root: Root path to begin walking
    :return: None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Walking through the directory structure starting from: {BackgroundColors.CYAN}{root}{Style.RESET_ALL}"
    )  # Output the verbose message

    for dirpath, dirnames, filenames in os.walk(root, topdown=False):  # Walk through the directory structure
        for filename in filenames:  # For each file in the directory
            if filename == CURRENT_FILE:  # Skip the current file
                continue  # Skip the current file

            old_path = os.path.join(dirpath, filename)  # Get the full path of the file
            rename_path_if_needed(old_path)  # Rename the file if needed

        for dirname in dirnames:  # For each directory in the directory
            old_dir = os.path.join(dirpath, dirname)  # Get the full path of the directory
            rename_path_if_needed(old_dir)  # Rename the directory if needed

    rename_path_if_needed(root)  # Rename the root directory if needed


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

    global SEARCH_DIRS  # Declare SEARCH_DIRS as global to modify it
    if not SEARCH_DIRS or SEARCH_DIRS == [""]:  # If the SEARCH_DIRS list is empty or contains an empty string
        SEARCH_DIRS = [os.path.join(os.getcwd(), "Input")]  # Set SEARCH_DIRS to the "./Input" directory

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Translating and renaming paths in {BackgroundColors.CYAN}{SEARCH_DIRS}{BackgroundColors.GREEN} directory(s) to English...{Style.RESET_ALL}"
    )  # Output the welcome message

    for directory in SEARCH_DIRS:  # Iterate through all directories in SEARCH_DIRS
        walk_and_translate(directory)  # Walk through the directory structure and rename files/folders with CJK names

    print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}✅ Translation and renaming completed.{Style.RESET_ALL}")

    atexit.register(play_sound)  # Register the function to play a sound when the program finishes


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()
