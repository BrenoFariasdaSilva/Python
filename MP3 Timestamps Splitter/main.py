import atexit  # For playing a sound when the program finishes
import ffmpeg  # For splitting the MP3 file
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For regular expressions
import subprocess  # For running a command in the terminal
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

# Path Constants:
INPUT_DIR = "Input"  # The directory where the MP3 files are stored
OUTPUT_DIR = "Output"  # The directory where the split MP3 files will be stored
TIMESTAMP_DIR = "Timestamps"  # The directory where the timestamp files are stored
PROCESSED_PREFIX = "Processed - "  # The prefix to mark files as processed

# Sound Constants:
SOUND_COMMANDS = {
    "Darwin": "afplay",
    "Linux": "aplay",
    "Windows": "start",
}  # The commands to play a sound for each operating system
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav"  # The path to the sound file


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


def is_ffmpeg_installed():
    """
    Checks if FFmpeg is installed by running 'ffmpeg -version'.

    :return: bool - True if FFmpeg is installed, False otherwise.
    """

    try:  # Try to execute FFmpeg
        subprocess.run(
            ["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True
        )  # Run the command
        return True  # FFmpeg is installed
    except (subprocess.CalledProcessError, FileNotFoundError):  # If an error occurs
        return False  # FFmpeg is not installed


def install_ffmpeg_windows():
    """
    Installs FFmpeg on Windows using Chocolatey. If Chocolatey is not installed, it installs it first.

    :return: None
    """

    verbose_output(f"{BackgroundColors.GREEN}Checking for Chocolatey...{Style.RESET_ALL}")  # Output the verbose message

    choco_installed = (
        subprocess.run(["choco", "--version"], capture_output=True, text=True).returncode == 0
    )  # Check if Chocolatey is installed

    if not choco_installed:  # If Chocolatey is not installed
        verbose_output(f"{BackgroundColors.YELLOW}Chocolatey not found. Installing Chocolatey...{Style.RESET_ALL}")

        choco_install_cmd = (
            "powershell -NoProfile -ExecutionPolicy Bypass -Command "
            '"Set-ExecutionPolicy Bypass -Scope Process -Force; '
            "[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; "
            "iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))\""
        )

        subprocess.run(choco_install_cmd, shell=True, check=True)  # Install Chocolatey

        verbose_output(
            f"{BackgroundColors.GREEN}Chocolatey installed successfully. Restart your terminal if needed.{Style.RESET_ALL}"
        )

    verbose_output(f"{BackgroundColors.GREEN}Installing FFmpeg via Chocolatey...{Style.RESET_ALL}")
    subprocess.run(["choco", "install", "ffmpeg", "-y"], check=True)  # Install FFmpeg using Chocolatey

    verbose_output(
        f"{BackgroundColors.GREEN}FFmpeg installed successfully. Please restart your terminal if necessary.{Style.RESET_ALL}"
    )


def install_ffmpeg_linux():
    """
    Installs FFmpeg on Linux using the package manager.

    :return: None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Installing FFmpeg on Linux...{Style.RESET_ALL}"
    )  # Output the verbose message

    try:  # Try installing FFmpeg
        subprocess.run(["sudo", "apt", "update"], check=True)  # Update package list
        subprocess.run(["sudo", "apt", "install", "-y", "ffmpeg"], check=True)  # Install FFmpeg
        verbose_output(
            f"{BackgroundColors.GREEN}FFmpeg installed successfully.{Style.RESET_ALL}"
        )  # Output the verbose message
    except subprocess.CalledProcessError:  # If an error occurs
        print("Failed to install FFmpeg. Please install it manually using your package manager.")  # Inform the user


def install_ffmpeg_mac():
    """
    Installs FFmpeg on macOS using Homebrew.

    :return: None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Installing FFmpeg on macOS...{Style.RESET_ALL}"
    )  # Output the verbose message

    try:  # Try installing FFmpeg
        subprocess.run(["brew", "install", "ffmpeg"], check=True)  # Run the installation command
        print("FFmpeg installed successfully.")  # Inform the user
    except subprocess.CalledProcessError:  # If an error occurs
        print(
            "Homebrew not found or installation failed. Please install FFmpeg manually using 'brew install ffmpeg'."
        )  # Inform the user


def verify_ffmpeg_is_installed():
    """
    Checks if FFmpeg is installed and installs it if missing.

    :return: None
    """

    INSTALL_COMMANDS = {  # Installation commands for different platforms
        "Windows": install_ffmpeg_windows,  # Windows
        "Linux": install_ffmpeg_linux,  # Linux
        "Darwin": install_ffmpeg_mac,  # macOS
    }

    if is_ffmpeg_installed():  # If FFmpeg is already installed
        verbose_output(f"{BackgroundColors.GREEN}FFmpeg is installed.{Style.RESET_ALL}")  # Output the verbose message
    else:  # If FFmpeg is not installed
        verbose_output(
            f"{BackgroundColors.RED}FFmpeg is not installed. Installing FFmpeg...{Style.RESET_ALL}"
        )  # Output the verbose message
        if platform.system() in INSTALL_COMMANDS:  # If the platform is supported
            INSTALL_COMMANDS[platform.system()]()  # Call the corresponding installation function
        else:  # If the platform is not supported
            print(
                f"Installation for {platform.system()} is not implemented. Please install FFmpeg manually."
            )  # Inform the user


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


def list_valid_mp3_files():
    """
    Lists MP3 files that have a matching timestamp file.

    :return: List of valid MP3 files
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Listing all MP3 files in the {BackgroundColors.CYAN}{INPUT_DIR}{BackgroundColors.YELLOW} directory...{Style.RESET_ALL}"
    )  # Output the verbose message

    mp3_files = [
        f for f in os.listdir(INPUT_DIR) if f.lower().endswith(".mp3")
    ]  # List of all MP3 files in the Input directory
    valid_files = []  # List of valid MP3 files with matching timestamp files

    for file in mp3_files:  # Iterate over each MP3 file
        base_name = os.path.splitext(file)[0]  # Get the base name of the file (without extension)
        timestamp_path = os.path.join(TIMESTAMP_DIR, f"{base_name}.txt")  # Path to the timestamp file

        if os.path.exists(timestamp_path):  # Check if the timestamp file exists
            valid_files.append(file)  # Add the MP3 file to the list of valid files
        else:  # If the timestamp file doesn't exist or the MP3 file is already processed
            print(
                f"⚠️ No timestamp file for: {file}. Please add a corresponding timestamp file (Skipping)"
            )  # Print a warning message

    return valid_files  # Return the list of valid MP3 files


def normalize_timestamp(timestamp):
    """
    Normalizes a timestamp to ensure it is in the format hh:mm:ss.

    :param timestamp: The timestamp to normalize
    :return: The normalized timestamp
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Normalizing the timestamp: {BackgroundColors.CYAN}{timestamp}{Style.RESET_ALL}"
    )  # Output the verbose message

    match = re.match(
        r"(?:(\d{1,2}):)?(\d{1,2}):(\d{1,2})", timestamp
    )  # Match the timestamp format, supporting both "mm:ss" and "hh:mm:ss"

    if not match:  # If the format doesn't match
        return timestamp  # Return as is if the format is incorrect

    hours, minutes, seconds = match.groups()  # Get the hours, minutes, and seconds from the match

    if not hours:  # If hours are missing (meaning we had "mm:ss"), default to "00"
        hours = "00"  # Default hours to "00"

    hours = hours.zfill(2)  # Fill the hours with leading zeros if needed
    minutes = minutes.zfill(2)  # Fill the minutes with leading zeros if needed
    seconds = seconds.zfill(2)  # Fill the seconds with leading zeros if needed

    return f"{hours}:{minutes}:{seconds}"  # Return the normalized timestamp


def parse_timestamps(timestamps_file):
    """
    Parses timestamps from a file, handling both "name timestamp" and "timestamp name" formats.

    :param timestamps_file: The path to the file containing the timestamps
    :return: List of parsed timestamps
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Parsing timestamps from the file: {BackgroundColors.CYAN}{timestamps_file}{Style.RESET_ALL}"
    )  # Output the verbose message

    timestamps = []  # List to store the parsed timestamps

    with open(timestamps_file, "r", encoding="utf-8") as file:  # Open the timestamp file
        for line in file:  # Iterate over each line in the file
            line = line.strip()  # Remove leading and trailing whitespaces
            if not line:  # If the line is empty
                continue  # Skip to the next line

            match = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?)", line)  # Match the timestamp format (e.g., 00:00:00)
            if not match:  # If the timestamp format is not found
                print(
                    f"{BackgroundColors.RED}⚠️ Skipping line with missing timestamp: {line}{Style.RESET_ALL}"
                )  # Print a warning message
                continue  # Skip to the next line

            timestamp = match.group(1)  # Get the timestamp from the match
            song_name = line.replace(timestamp, "").strip(
                " -"
            )  # Get the song name by removing the timestamp and leading/trailing hyphens

            if not song_name:  # If the song name is empty
                print(
                    f"{BackgroundColors.RED}⚠️ Skipping line with missing song name: {line}{Style.RESET_ALL}"
                )  # Print a warning message
                continue  # Skip to the next line

            song_name = song_name.title()  # Capitalize the song name
            timestamp = normalize_timestamp(timestamp)  # Normalize the timestamp format (e.g., 1.00.53 -> 01:00:53)
            timestamps.append((song_name, timestamp))  # Append the song name and timestamp to the list

    return timestamps  # Return the list of parsed timestamps


def write_updated_timestamps(timestamps, timestamps_file):
    """
    Writes the updated timestamps with capitalized song names.

    :param timestamps: List of parsed timestamps
    :param timestamps_file: The path to the file containing the timestamps
    :return: None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Writing updated timestamps to the file: {BackgroundColors.CYAN}{timestamps_file}{Style.RESET_ALL}"
    )  # Output the verbose message

    with open(timestamps_file, "w", encoding="utf-8") as file:  # Open the timestamp file for writing
        for song_name, timestamp in timestamps:  # Iterate over each song name and timestamp
            file.write(f"{timestamp} {song_name}\n")  # Write the updated timestamp and song name to the file

    print(
        f"{BackgroundColors.GREEN}Updated timestamps written to: {BackgroundColors.CYAN}{timestamps_file}{Style.RESET_ALL}"
    )  # Output the success message


def clean_timestamp_file(timestamps_file):
    """
    Reads the timestamp file, removes any blank lines, and returns the cleaned list.

    :param timestamps_file: The path to the file containing the timestamps
    :return: List of cleaned lines
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Cleaning the timestamp file: {BackgroundColors.CYAN}{timestamps_file}{Style.RESET_ALL}"
    )  # Output the verbose message

    with open(timestamps_file, "r", encoding="utf-8") as file:  # Open the timestamp file for reading
        lines = [
            line.strip() for line in file if line.strip()
        ]  # Remove leading and trailing whitespaces from each line

    return lines  # Return the cleaned list of lines


def split_mp3(mp3_path, timestamps_file, output_subdir):
    """
    Splits the MP3 file based on cleaned timestamps into a specific output subdirectory.

    :param mp3_path: The path to the MP3 file
    :param timestamps_file: The path to the file containing the timestamps
    :param output_subdir: The path to the output subdirectory
    :return: True if the MP3 file was successfully split, False otherwise
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Splitting the MP3 file: {BackgroundColors.CYAN}{mp3_path}{Style.RESET_ALL}"
    )  # Output the verbose message

    if os.path.basename(mp3_path).startswith("Processed -"):  # Skip already processed files
        verbose_output(
            f"{BackgroundColors.YELLOW}Skipping already processed file: {BackgroundColors.CYAN}{mp3_path}{Style.RESET_ALL}"
        )  # Output the verbose message
        return False  # Indicate that processing was skipped

    os.makedirs(output_subdir, exist_ok=True)  # Create the output subdirectory if it doesn't exist

    timestamps_lines = clean_timestamp_file(timestamps_file)  # Clean the timestamp file
    timestamps = []  # List to store the timestamps

    for line in timestamps_lines:  # Iterate over each line in the cleaned timestamp file
        time_part, song_name = line.split(maxsplit=1)  # Split the line into time and song name
        timestamps.append((song_name.strip(), time_part.strip()))  # Append the song name and timestamp to the list

    try:  # Try to split the MP3 file
        for i, (song_name, start_time) in enumerate(timestamps):  # Iterate over each song name and start time
            next_start_time = (
                timestamps[i + 1][1] if i + 1 < len(timestamps) else None
            )  # Get the next start time if it exists
            duration_option = (
                {"ss": start_time, "to": next_start_time} if next_start_time else {"ss": start_time}
            )  # Set the duration option based on the start and next start time

            song_filename = f"{str(i+1).zfill(2)} - {song_name}.mp3"  # Create the song filename
            output_path = os.path.join(output_subdir, song_filename)  # Path to the output file

            ffmpeg.input(mp3_path, **duration_option).output(output_path, format="mp3", loglevel="error").run(
                overwrite_output=True
            )  # Run ffmpeg and catch errors

            print(f"{BackgroundColors.GREEN}✅ Split: {BackgroundColors.CYAN}{song_filename}{Style.RESET_ALL}")

    except ffmpeg.Error as e:  # If an error occurs while splitting the MP3 file
        print(
            f"{BackgroundColors.RED}Error splitting the MP3 file: {BackgroundColors.CYAN}{mp3_path}{BackgroundColors.RED}. {e}{Style.RESET_ALL}"
        )
        return False  # Indicate failure

    return True  # Indicate success


def mark_as_processed(mp3_file, timestamp_file):
    """
    Renames both the MP3 file and its corresponding timestamp file to mark them as processed.

    :param mp3_file: The name of the MP3 file
    :param timestamp_file: The path to the timestamp file
    :return: None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Marking the MP3 file and timestamp file as processed...{Style.RESET_ALL}"
    )  # Output the verbose message

    processed_mp3 = os.path.join(INPUT_DIR, PROCESSED_PREFIX + mp3_file)  # Path to the processed MP3 file
    if not mp3_file.startswith(PROCESSED_PREFIX):  # If the MP3 file doesn't start with the processed prefix
        os.rename(os.path.join(INPUT_DIR, mp3_file), processed_mp3)  # Rename the MP3 file to mark it as processed
        print(
            f"{BackgroundColors.GREEN}✅ Marked as processed: {BackgroundColors.CYAN}{processed_mp3}{Style.RESET_ALL}"
        )
    else:  # If the MP3 file already starts with the processed prefix
        print(
            f"{BackgroundColors.YELLOW}⚠️ MP3 file already processed: {BackgroundColors.CYAN}{processed_mp3}{Style.RESET_ALL}"
        )

    processed_timestamp = os.path.join(
        TIMESTAMP_DIR, PROCESSED_PREFIX + os.path.basename(timestamp_file)
    )  # Path to the processed timestamp file
    if not timestamp_file.startswith(PROCESSED_PREFIX):  # If the timestamp file doesn't start with the processed prefix
        os.rename(timestamp_file, processed_timestamp)  # Rename the timestamp file to mark it as processed
        print(
            f"{BackgroundColors.GREEN}✅ Marked as processed: {BackgroundColors.CYAN}{processed_timestamp}{Style.RESET_ALL}"
        )
    else:
        print(
            f"{BackgroundColors.YELLOW}⚠️ Timestamp file already processed: {BackgroundColors.CYAN}{processed_timestamp}{Style.RESET_ALL}"
        )


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
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}MP3 Splitter{BackgroundColors.GREEN}!{Style.RESET_ALL}"
    )  # Output the welcome message

    os.makedirs(TIMESTAMP_DIR, exist_ok=True)  # Create the Timestamps directory if it doesn't exist
    mp3_files = list_valid_mp3_files()  # List the valid MP3 files
    
    verify_ffmpeg_is_installed()  # Verify ffmpeg is installed
    
    if not mp3_files:  # If no valid MP3 files are found
        print(
            f"{BackgroundColors.RED}No valid MP3 files found in the {BackgroundColors.CYAN}Input{BackgroundColors.RED} directory. Please add MP3 files with corresponding timestamp files.{Style.RESET_ALL}"
        )  # Output the error message
        return  # Exit the program

    for mp3_file in mp3_files:  # Iterate over each valid MP3 file
        base_name = os.path.splitext(mp3_file)[0]  # Get the base name of the file (without extension)
        timestamps_file = os.path.join(TIMESTAMP_DIR, f"{base_name}.txt")  # Path to the timestamp file
        output_subdir = os.path.join(OUTPUT_DIR, base_name)  # Path to the output subdirectory

        print(f"\n{BackgroundColors.BOLD}Processing {mp3_file}...{Style.RESET_ALL}")  # Output the processing message
        timestamps = parse_timestamps(timestamps_file)  # Parse the timestamps from the timestamp file

        if not timestamps:  # If no valid timestamps are found
            print(
                f"{BackgroundColors.RED}No valid timestamps found in the {BackgroundColors.CYAN}{timestamps_file}{BackgroundColors.RED} file. Please add valid timestamps.{Style.RESET_ALL}"
            )  # Output the error message
            continue  # Skip to the next MP3 file

        write_updated_timestamps(timestamps, timestamps_file)  # Write the updated timestamps to the timestamp file

        print(f"\n{BackgroundColors.BOLD}Splitting {mp3_file}...{Style.RESET_ALL}")  # Output the splitting message
        if split_mp3(os.path.join(INPUT_DIR, mp3_file), timestamps_file, output_subdir):  # Split the MP3 file
            mark_as_processed(mp3_file, timestamps_file)  # Mark the MP3 file and timestamp file as processed
        else:  # If an error occurs while splitting the MP3 file
            print(
                f"{BackgroundColors.RED}Error splitting {BackgroundColors.CYAN}{mp3_file}{BackgroundColors.RED}. Please check the timestamps and try again.{Style.RESET_ALL}"
            )  # Output the error message

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
