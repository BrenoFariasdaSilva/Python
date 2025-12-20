import atexit  # For playing a sound when the program finishes
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For cleaning song names using regular expressions
import shutil  # For moving files to folders
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
INPUT_DIR = "./Input"  # The directory where the .mp3 files are located

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


def clean_song_name(name):
    """
    Cleans the song name by replacing dollar signs with 's', removing unwanted suffixes and patterns, collapses multiple spaces into a single space.
    Ensures no trailing space or dash before the file extension.

    :param name: The original song name
    :return: The cleaned song name
    """

    name = name.replace("$", "s")  # Replace dollar signs with 's'

    blacklist = [
        # Parentheses, brackets, braces containing keywords or phrases
        r"\s*[\(\[\{].*?\b(official|clip|video|remaster(ed)? version|remaster(ed)?|version|edit|full mix|mix|from|single|lyrics|audio|hd|live|remix|radio edit|clean version|explicit version|bonus track|demo|instrumental|karaoke|acoustic|cover|feat\.?|ft\.?|with|vs\.?|intro|outro|rework|extended|session|take|uncut|uncensored|dub|tv size|original|album version|alternative|b-side|promo|single version|mono|stereo|highlight|sample|snippet|preview|dubstep|trap|drum and bass|dub mix|vinyl|bootleg|re-recorded|re-release|video clip|music video|concert|festival|remastered edition|version 2|version 3)\b.*?[\)\]\}]",
        # Dash or hyphen followed by keywords or phrases
        r"\s*-\s*.*?\b(official|clip|video|remaster(ed)? version|remaster(ed)?|version|edit|full mix|mix|from|single|lyrics|audio|hd|live|remix|radio edit|clean version|explicit version|bonus track|demo|instrumental|karaoke|acoustic|cover|feat\.?|ft\.?|with|vs\.?|intro|outro|rework|extended|session|take|uncut|uncensored|dub|tv size|original|album version|alternative|b-side|promo|single version|mono|stereo|highlight|sample|snippet|preview|dubstep|trap|drum and bass|dub mix|vinyl|bootleg|re-recorded|re-release|video clip|music video|concert|festival|remastered edition|version 2|version 3)\b.*?$",
        # Years, e.g. 2005, 1999
        r"\b(19|20)\d{2}\b",
        # Common standalone descriptors and phrases
        r"\b(official|lyrics|video|audio|live|remix|edit|version|clip|feat\.?|ft\.?|acoustic|cover|instrumental|clean|explicit|radio edit|demo|karaoke|bonus track|uncut|rework|extended|session|take|vinyl|bootleg|re-recorded|re-release|concert|festival|remastered version|remastered|album version|alternative|promo|b-side)\b",
    ]

    for pattern in blacklist:  # Iterate over each pattern in the blacklist
        name = re.sub(pattern, "", name, flags=re.IGNORECASE).strip()  # Remove the pattern and strip whitespace

    name = re.sub(r"\s+", " ", name)  # Collapse multiple consecutive whitespace characters into a single space

    name = re.sub(
        r"[\s\-]+(?=\.\w{2,4}$)", "", name
    )  # Remove trailing spaces or dashes BEFORE file extension (e.g. ".mp3", ".flac", ".wav", ".ogg")

    return name.strip()  # Strip any leading or trailing whitespace from the cleaned name


def fix_apostrophes(text):
    """
    Fixes apostrophes in the text by converting uppercase letters after apostrophes to lowercase.

    :param text: The text to fix
    :return: The fixed text
    """

    return re.sub(
        r"(?<=')([A-Z])", lambda m: m.group(1).lower(), text
    )  # Convert uppercase letters after apostrophes to lowercase


def organize_mp3_files(input_dir=INPUT_DIR):
    """
    Organizes all .mp3 files from the ./Input directory into folders by artist inside the same directory
    and cleans the song names.

    :param input_dir: The directory where the .mp3 files are located (default is ./Input)
    :return: None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Organizing .mp3 files in the directory: {BackgroundColors.CYAN}{input_dir}{Style.RESET_ALL}"
    )  # Output the verbose message

    for file in os.listdir(input_dir):  # Iterate over all files in the ./Input directory
        if file.endswith(".mp3"):  # Check if the file is an .mp3 file
            parts = file.rsplit(".mp3", 1)[0].split(" - ", 1)  # Split on the first " - "
            if len(parts) < 2:
                continue  # Skip if not in expected format

            artist = fix_apostrophes(parts[0].strip().title())  # Get the artist name and capitalize it
            full_song_part = parts[1].strip()  # Get the raw song part

            song_name = (
                fix_apostrophes(clean_song_name(full_song_part).title()) + ".mp3"
            )  # Clean the song name and add extension

            artist_dir = os.path.join(input_dir, artist)  # Artist folder inside ./Input
            if not os.path.exists(artist_dir):  # Verify if the artist directory exists
                os.makedirs(artist_dir)  # Create a directory for the artist

            src = os.path.join(input_dir, file)  # Source path in ./Input
            dst = os.path.join(artist_dir, song_name)  # Destination path inside artist folder in ./Input
            shutil.move(src, dst)  # Move and rename the file
            print(f"Moved: {src} → {dst}")  # Output the move operation


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
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}MP3 Musics Organizer{BackgroundColors.GREEN}!{Style.RESET_ALL}"
    )  # Output the welcome message

    if not verify_filepath_exists(INPUT_DIR):
        print(
            f"{BackgroundColors.RED}Input directory {BackgroundColors.CYAN}{INPUT_DIR}{BackgroundColors.RED} does not exist. Please create it and add your .mp3 files.{Style.RESET_ALL}"
        )
        return  # If the input directory does not exist, output an error message and return

    organize_mp3_files()  # Organize the mp3 files

    print(
        f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}MP3 organization complete.{Style.RESET_ALL}"
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
