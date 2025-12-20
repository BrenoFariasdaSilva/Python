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


# Sound Constants:
SOUND_COMMANDS = {
    "Darwin": "afplay",
    "Linux": "aplay",
    "Windows": "start",
}  # The commands to play a sound for each operating system
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav"  # The path to the sound file

# Filename Constants:
INPUT_PYTHON_FILE = "./input.py"  # The path to the input Python file
OUTPUT_PYTHON_FILE = "./input.py"  # The path to the output Python file


def play_sound():
    """
    Plays a sound when the program finishes.

    :return: None
    """

    if os.path.exists(SOUND_FILE):
        if platform.system() in SOUND_COMMANDS:  # If the platform.system() is in the SOUND_COMMANDS dictionary
            os.system(f"{SOUND_COMMANDS[platform.system()]} {SOUND_FILE}")
        else:  # If the platform.system() is not in the SOUND_COMMANDS dictionary
            print(
                f"{BackgroundColors.RED}The {BackgroundColors.CYAN}platform.system(){BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}"
            )
    else:  # If the sound file does not exist
        print(
            f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}"
        )


# Register the function to play a sound when the program finishes
atexit.register(play_sound)


def fix_double_space_comment(code):
    """
    Fixes double spaces before a hashtag comment in the given code string.

    :param code: The input code as a string.
    :return: The modified code with a single space before hashtag comments.
    """

    # Regular expression to find a non-space character followed by double spaces and a hashtag
    pattern = re.compile(r"(\S)  #")

    # Replace double spaces with a single space while keeping the non-space character
    fixed_code = pattern.sub(r"\1 #", code)

    return fixed_code  # Return the fixed code


def main():
    """
    Main function.

    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Python Double Comments Remover{BackgroundColors.GREEN}!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the Welcome message

    # Read the python code from the current dir named main.py
    code = open(INPUT_PYTHON_FILE, "r").read()

    fixed_code = fix_double_space_comment(code)  # Fix the double space comments in the code

    open(OUTPUT_PYTHON_FILE, "w").write(fixed_code)  # Write the fixed code to a new file

    print(
        f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
    )  # Output the end of the program message


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
