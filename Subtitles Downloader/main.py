import atexit  # For playing a sound when the program finishes
import importlib  # For importing a module
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import shutil  # For checking if a command exists in the system path
import subprocess  # Import subprocess for running commands
import sys  # For getting the system path
from colorama import Style  # For coloring the terminal
from tqdm import tqdm  # Import tqdm for progress bar


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
SKIP_EVERY_LANGUAGES_IF_FOUND = False  # Set to True to skip other language families if subtitles are found in one
LANGUAGES = {  # Dictionary of languages and their possible subtitle codes
    "Portuguese": ["pt-BR", "pt", "pt-PT"],  # Portuguese subtitle codes
    "English": ["eng", "en", "en-US"],  # English subtitle codes
}

# Sound Constants:
SOUND_COMMANDS = {
    "Darwin": "afplay",
    "Linux": "aplay",
    "Windows": "start",
}  # The commands to play a sound for each operating system
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav"  # The path to the sound file

# List of directories to exclude
EXCLUDE_DIRS = {"./.assets", "./venv"}  # Directories to exclude

# Input Direectory:
INPUT_DIRECTORY = "./Input"  # The input directory


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


def resolve_entry_with_trailing_space(current_path: str, entry: str, stripped_part: str) -> str:
    """
    Resolve and optionally rename a directory entry with trailing spaces.

    :param current_path: Current directory path.
    :param entry: Directory entry name.
    :param stripped_part: Normalized target name without surrounding spaces.
    :return: Resolved path after optional rename.
    """

    try:  # Wrap full function logic to ensure safe execution
        resolved = os.path.join(current_path, entry)  # Build resolved path

        if entry != stripped_part:  # Verify trailing spaces exist
            corrected = os.path.join(current_path, stripped_part)  # Build corrected path
            try:  # Attempt to rename entry
                os.rename(resolved, corrected)  # Rename entry to stripped version
                verbose_output(true_string=f"{BackgroundColors.GREEN}Renamed: {BackgroundColors.CYAN}{resolved}{BackgroundColors.GREEN} -> {BackgroundColors.CYAN}{corrected}{Style.RESET_ALL}")  # Log rename
                resolved = corrected  # Update resolved path after rename
            except Exception:  # Handle rename failure
                verbose_output(true_string=f"{BackgroundColors.RED}Failed to rename: {BackgroundColors.CYAN}{resolved}{Style.RESET_ALL}")  # Log failure

        return resolved  # Return resolved path
    except Exception:  # Catch unexpected errors
        return os.path.join(current_path, entry)  # Return fallback resolved path


def resolve_full_trailing_space_path(filepath: str) -> str:
    """
    Resolve trailing space issues across all path components.

    :param filepath: Path to resolve potential trailing space mismatches.
    :return: Corrected full path if matches are found, otherwise original filepath.
    """

    try:  # Wrap full function logic to ensure safe execution
        verbose_output(true_string=f"{BackgroundColors.GREEN}Resolving full trailing space path for: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}")  # Log start

        if not isinstance(filepath, str) or not filepath:  # Verify filepath validity
            verbose_output(true_string=f"{BackgroundColors.YELLOW}Invalid filepath provided, skipping resolution.{Style.RESET_ALL}")  # Log invalid input
            return filepath  # Return original

        filepath = os.path.expanduser(filepath)  # Expand ~ to user directory
        parts = filepath.split(os.sep)  # Split path into components

        if not parts:  # Verify path parts exist
            return filepath  # Return original

        if filepath.startswith(os.sep):  # Handle absolute paths
            current_path = os.sep  # Start from root
            parts = parts[1:]  # Remove empty root part
        else:
            current_path = parts[0] if parts[0] else os.getcwd()  # Initialize base
            parts = parts[1:] if parts[0] else parts  # Adjust parts

        for part in parts:  # Iterate over each path component
            if part == "":  # Skip empty parts
                continue  # Continue iteration

            try:  # Attempt to list current directory
                entries = os.listdir(current_path) if os.path.isdir(current_path) else []  # List current directory entries
            except Exception:  # Handle failure to list directory contents
                verbose_output(true_string=f"{BackgroundColors.RED}Failed to list directory: {BackgroundColors.CYAN}{current_path}{Style.RESET_ALL}")  # Log failure
                return filepath  # Return original

            stripped_part = part.strip()  # Normalize current part
            match_found = False  # Initialize match flag

            for entry in entries:  # Iterate directory entries
                try:  # Attempt safe comparison for each entry
                    if entry.strip() == stripped_part:  # Compare stripped names
                        current_path = resolve_entry_with_trailing_space(current_path, entry, stripped_part)  # Resolve entry and update current path
                        match_found = True  # Mark match
                        break  # Stop searching
                except Exception:  # Handle any unexpected error during comparison
                    continue  # Continue on error

            if not match_found:  # If no match found for this segment
                verbose_output(true_string=f"{BackgroundColors.YELLOW}No match for segment: {BackgroundColors.CYAN}{part}{Style.RESET_ALL}")  # Log miss
                return filepath  # Return original

        return current_path  # Return fully resolved path

    except Exception:  # Catch unexpected errors to maintain stability
        verbose_output(true_string=f"{BackgroundColors.RED}Error resolving full path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}")  # Log error
        return filepath  # Return original


def verify_filepath_exists(filepath):
    """
    Verify if a file or folder exists at the specified path.

    :param filepath: Path to the file or folder
    :return: True if the file or folder exists, False otherwise
    """

    try:  # Wrap full function logic to ensure production-safe monitoring
        verbose_output(
            f"{BackgroundColors.GREEN}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}"
        )  # Output the verbose message
        
        if not isinstance(filepath, str) or not filepath.strip():  # Verify for non-string or empty/whitespace-only input   
            verbose_output(true_string=f"{BackgroundColors.YELLOW}Invalid filepath provided, skipping existence verification.{Style.RESET_ALL}")  # Log invalid input
            return False  # Return False for invalid input

        if os.path.exists(filepath):  # Fast path: original input exists
            return True  # Return True immediately

        candidate = str(filepath).strip()  # Normalize input to string and strip surrounding whitespace

        if (candidate.startswith("'") and candidate.endswith("'")) or (
            candidate.startswith('"') and candidate.endswith('"')
        ):  # Handle quoted paths from config files
            candidate = candidate[1:-1].strip()  # Remove wrapping quotes and trim again

        candidate = os.path.expanduser(candidate)  # Expand ~ to user home directory
        candidate = os.path.normpath(candidate)  # Normalize path separators and structure

        if os.path.exists(candidate):  # Verify normalized candidate directly
            return True  # Return True if normalized path exists

        repo_dir = os.path.dirname(os.path.abspath(__file__))  # Resolve repository directory
        cwd = os.getcwd()  # Capture current working directory

        alt = candidate.lstrip(os.sep) if candidate.startswith(os.sep) else candidate  # Prepare relative-safe path

        repo_candidate = os.path.join(repo_dir, alt)  # Build repo-relative candidate
        cwd_candidate = os.path.join(cwd, alt)  # Build cwd-relative candidate

        for path_variant in (repo_candidate, cwd_candidate):  # Iterate alternative base paths
            try:
                normalized_variant = os.path.normpath(path_variant)  # Normalize variant
                if os.path.exists(normalized_variant):  # Verify existence
                    return True  # Return True if found
            except Exception:
                continue  # Continue safely on error

        try:  # Attempt absolute path resolution as fallback
            abs_candidate = os.path.abspath(candidate)  # Build absolute path
            if os.path.exists(abs_candidate):  # Verify existence
                return True  # Return True if found
        except Exception:
            pass  # Ignore resolution errors

        for path_variant in (candidate, repo_candidate, cwd_candidate):  # Attempt trailing-space resolution on all variants
            try:  # Attempt to resolve trailing space issues across path components for this variant
                resolved = resolve_full_trailing_space_path(path_variant)  # Resolve trailing space issues across path components
                if resolved != path_variant and os.path.exists(resolved):  # Verify resolved path exists
                    verbose_output(
                        f"{BackgroundColors.YELLOW}Resolved trailing space mismatch: {BackgroundColors.CYAN}{path_variant}{BackgroundColors.YELLOW} -> {BackgroundColors.CYAN}{resolved}{Style.RESET_ALL}"
                    )  # Log successful resolution
                    return True  # Return True if corrected path exists
            except Exception:  # Catch any exception during trailing space resolution   
                continue  # Continue safely on error

        return False  # Not found after all resolution strategies
    except Exception as e:  # Catch any exception to ensure logging and Telegram alert
        print(str(e))  # Print error to terminal for server logs
        raise  # Re-raise to preserve original failure semantics


def is_package_installed(package_name):
    """
    Checks if the specified package is installed.

    :param package_name: Name of the package to check.
    :return: True if the package is installed, False otherwise.
    """

    try:  # Try to import the package
        importlib.import_module(package_name)  # Import the package
        return True  # Return True if the package is installed
    except ImportError:  # If the package is not installed
        return False  # Return False if the package is not installed


def install_package_with_pipx(package_name):
    """
    Installs a package using pipx.

    :param package_name: Name of the package to install.
    :return: None
    """

    try:  # Try to install the package using pipx
        subprocess.check_call([sys.executable, "-m", "pipx", "install", package_name])  # Install the package using pipx
        print(
            f"{BackgroundColors.GREEN}{package_name} installed successfully using pipx!{Style.RESET_ALL}"
        )  # Output the success message
    except subprocess.CalledProcessError:  # If the process fails
        print(
            f"{BackgroundColors.RED}Failed to install {package_name} using pipx.{Style.RESET_ALL}"
        )  # Output the failure message


def install_package_with_pip(package_name):
    """
    Installs a package using pip.

    :param package_name: Name of the package to install.
    :return: None
    """

    try:  # Try to install the package using pip
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name])  # Install the package using pip
        print(
            f"{BackgroundColors.GREEN}{package_name} installed successfully using pip!{Style.RESET_ALL}"
        )  # Output the success message
    except subprocess.CalledProcessError:  # If the process fails
        print(
            f"{BackgroundColors.RED}Failed to install {package_name} using pip.{Style.RESET_ALL}"
        )  # Output the failure message


def check_and_install_package(package_name="subliminal"):
    """
    Checks if the specified package is installed and installs it if not.

    :param package_name: Name of the package to check and install.
    :return: None
    """

    verbose_output(
        f"{BackgroundColors.GREEN}Checking if the package {BackgroundColors.CYAN}{package_name}{BackgroundColors.GREEN} is installed...{Style.RESET_ALL}"
    )  # Output the verbose message

    if is_package_installed(package_name):  # Check if the package is installed
        verbose_output(
            f"{BackgroundColors.CYAN}{package_name}{BackgroundColors.GREEN} is already installed.{Style.RESET_ALL}"
        )  # Output the verbose message
    else:
        verbose_output(
            f"{BackgroundColors.CYAN}{package_name}{BackgroundColors.YELLOW} is not installed. Installing...{Style.RESET_ALL}"
        )
        install_package_with_pipx(package_name)  # Try installing with pipx
        if not is_package_installed(package_name):  # If the package is not installed
            install_package_with_pip(package_name)  # Fallback to pip if pipx fails


def get_directories():
    """
    Get all subdirectories inside the input directory.
    Excludes the INPUT_DIRECTORY itself if it contains subdirectories.

    :return: List of absolute paths to subdirectories
    """

    dirs = [
        os.path.normpath(os.path.abspath(root)) for root, _, _ in os.walk(INPUT_DIRECTORY)
    ]  # Collect all directories
    if (
        len(dirs) > 1 and os.path.normpath(os.path.abspath(INPUT_DIRECTORY)) in dirs
    ):  # If root dir has subdirs, remove itself
        dirs.remove(os.path.normpath(os.path.abspath(INPUT_DIRECTORY)))  # Remove the root input directory
    return dirs  # Return only valid subdirectories


def download_subtitles(directory, languages=LANGUAGES):
    """
    Download subtitles for the specified directory in multiple language groups.
    Tries language variants for each group until one variant succeeds, then
    proceeds to the next language family.

    :param directory: The directory to download subtitles for
    :param languages: Dictionary of language families and their variants
    :return: None
    """

    venv_bin = os.path.join(
        sys.prefix, "bin" if os.name != "nt" else "Scripts"
    )  # Define the virtual environment bin/Scripts path depending on OS
    subliminal_cmd = os.path.join(venv_bin, "subliminal")  # Define the path to the subliminal command inside the venv

    if not shutil.which(subliminal_cmd):  # If the subliminal command is not found in venv
        subliminal_cmd = "subliminal"  # Fallback to the system-wide installation

    for lang_family, variants in languages.items():  # Loop through each language family and its variants
        print(
            f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Trying to download {BackgroundColors.CYAN}{lang_family}{BackgroundColors.GREEN} subtitles for {BackgroundColors.CYAN}{directory}{Style.RESET_ALL}"
        )  # Output the language family being processed

        success = False  # Initialize success flag for the current language family

        for variant in variants:  # Loop through each variant of the current language family
            command = f'"{subliminal_cmd}" download -l {variant} -m 50 "{directory}"'  # Build the subliminal command with the current language variant

            try:  # Try to execute the command
                result = subprocess.run(
                    command, shell=True, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )  # Execute the subliminal command silently and store the result
                if result.returncode == 0:  # If the command executed successfully
                    print(
                        f"{BackgroundColors.GREEN}Successfully downloaded subtitles for {BackgroundColors.CYAN}{directory}{BackgroundColors.GREEN} using {BackgroundColors.CYAN}{variant}{Style.RESET_ALL}"
                    )  # Output the success message for the variant
                    success = True  # Mark success for this language family
                    if (
                        SKIP_EVERY_LANGUAGES_IF_FOUND
                    ):  # If configured to stop processing after finding subtitles for one language family
                        verbose_output(
                            f"{BackgroundColors.CYAN}{lang_family}{BackgroundColors.GREEN} subtitles found; skipping remaining language families for {BackgroundColors.CYAN}{directory}.{Style.RESET_ALL}"
                        )  # Verbose message for global skip
                        return  # Stop the entire subtitle downloading process
                    break  # Stop trying other variants of this language family after success
                else:  # If the command did not succeed
                    verbose_output(
                        f"{BackgroundColors.YELLOW}No subtitles found for {BackgroundColors.CYAN}{variant}.{Style.RESET_ALL}"
                    )  # Verbose message when variant yields no subtitles
            except subprocess.CalledProcessError:  # Handle command execution errors
                verbose_output(
                    f"{BackgroundColors.RED}Error while downloading subtitles for {BackgroundColors.CYAN}{variant}.{Style.RESET_ALL}"
                )  # Verbose message on command error

        if not success:  # If no variant succeeded for the current language family
            verbose_output(
                f"{BackgroundColors.YELLOW}No subtitles found for {BackgroundColors.CYAN}{lang_family}{BackgroundColors.YELLOW} in {BackgroundColors.CYAN}{directory}.{Style.RESET_ALL}"
            )  # Verbose warning for the language family
        else:  # If at least one variant succeeded for the current language family
            verbose_output(
                f"{BackgroundColors.CYAN}{lang_family}{BackgroundColors.GREEN} subtitles found; moving to next language family.{Style.RESET_ALL}"
            )  # Verbose info that we will continue to next language family


def process_directories(dirs):
    """
    Process directories to download subtitles.

    :param dirs: List of directories to process
    :return: None
    """

    for directory in tqdm(
        dirs, desc=f"{BackgroundColors.GREEN}Processing directories to download subtitles{Style.RESET_ALL}", unit="dir"
    ):  # Loop through directories with a progress bar
        download_subtitles(directory)  # Download subtitles for the directory

    print(
        f"{BackgroundColors.GREEN}All subtitles downloaded successfully!{Style.RESET_ALL}"
    )  # Output the success message


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
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Subtitles Downloader{BackgroundColors.GREEN}!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the Welcome message

    os.makedirs(INPUT_DIRECTORY, exist_ok=True)  # Create the input directory if it does

    check_and_install_package()  # Check and install the subliminal package

    dirs = get_directories()  # Get all directories in the current directory, excluding the specified ones

    if len(dirs) == 0:  # If no directories are found
        print(
            f"{BackgroundColors.RED}No directories found in the {BackgroundColors.CYAN}Input{BackgroundColors.RED} directory. Please add directories to download subtitles.{Style.RESET_ALL}"
        )
        return  # Return if no directories are found

    process_directories(dirs)  # Process directories to download subtitles

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
