import atexit  # For playing a sound when the program finishes
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import pyheif  # For reading HEIC files
from colorama import Style  # For coloring the terminal
from PIL import Image  # For reading and writing images


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
SAME_PLACE_CONVERSION = True  # Set to True to convert files in the same folder and use the suffix for the output files
INPUT_FILE_EXTENSIONS = [".heic", ".jpg", ".jpeg", ".webp"]  # Extensions to convert
OUTPUT_FILE_EXTENSION = ".png"  # The output file extension to save as
OUTPUT_FILE_SUFFIX = "_converted"  # The suffix to add to the output file name

# Path Constants:
START_PATH = os.getcwd()  # The path where the program is executed
RELATIVE_INPUT_FOLDER = "./Inputs/"  # The relative path to the input folder
RELATIVE_OUTPUT_FOLDER = "./Outputs/"  # The relative path to the output folder
FULL_INPUT_FOLDER = os.path.join(START_PATH, RELATIVE_INPUT_FOLDER)  # The full path to the input folder
FULL_OUTPUT_FOLDER = os.path.join(START_PATH, RELATIVE_OUTPUT_FOLDER)  # The full path to the output folder

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


def create_directory(full_directory_name, relative_directory_name):
    """
    Creates a directory.

    :param full_directory_name: Name of the directory to be created.
    :param relative_directory_name: Relative name of the directory to be created that will be shown in the terminal.
    :return: None
    """

    verbose_output(
        true_string=f"{BackgroundColors.GREEN}Creating the {BackgroundColors.CYAN}{relative_directory_name}{BackgroundColors.GREEN} directory...{Style.RESET_ALL}"
    )

    if os.path.isdir(full_directory_name):  # Verify if the directory already exists
        return  # Return if the directory already exists
    try:  # Try to create the directory
        os.makedirs(full_directory_name)  # Create the directory
    except OSError:  # If the directory cannot be created
        print(
            f"{BackgroundColors.GREEN}The creation of the {BackgroundColors.CYAN}{relative_directory_name}{BackgroundColors.GREEN} directory failed.{Style.RESET_ALL}"
        )


def convert_photos_to_specified_format(
    input_folder=FULL_INPUT_FOLDER,
    output_folder=FULL_OUTPUT_FOLDER,
    searched_extensions=INPUT_FILE_EXTENSIONS,
    output_extension=OUTPUT_FILE_EXTENSION,
):
    """
    Converts photos to the specified format while preserving quality. Searches recursively within the input folder.

    :param input_folder: The folder containing the photos in the INPUT_FILE_EXTENSIONS formats.
    :param output_folder: The folder to save the converted files, if the SAME_PLACE_CONVERSION constant is False.
    :param searched_extensions: List of file extensions to search for.
    :param output_extension: The target image format (e.g., "PNG", "JPEG").
    :return: Number of files converted.
    """

    verbose_output(
        f"{BackgroundColors.YELLOW}Converting photos to {BackgroundColors.CYAN}{output_extension.upper()}{BackgroundColors.YELLOW} format while preserving quality (recursive search)...{Style.RESET_ALL}"
    )  # Output the verbose message

    file_count = 0  # The number of files converted

    for root, dirs, files in os.walk(input_folder):  # Walk recursively through all directories and files
        for filename in files:  # For each file found
            if filename.lower().endswith(tuple(searched_extensions)):  # If the file has a searched extension
                file_count += 1  # Increment the file count

                input_path = os.path.join(root, filename)  # Get the full path of the input file

                try:  # Try to open and process the image
                    if filename.lower().endswith(".heic"):  # Only HEIC needs pyheif
                        heif_file = pyheif.read(input_path)  # Read the HEIC file
                        image = Image.frombytes(  # Create an image from the HEIC file
                            heif_file.mode,
                            heif_file.size,
                            heif_file.data,
                            "raw",
                            heif_file.mode,
                            heif_file.stride,
                        )
                    else:
                        image = Image.open(input_path)  # For other formats, use PIL directly
                        image = image.convert("RGB")  # Ensure consistent mode

                    if SAME_PLACE_CONVERSION:  # If the conversion should happen in the same place
                        output_name = f"{os.path.splitext(input_path)[0]}{OUTPUT_FILE_SUFFIX}{output_extension.lower()}"  # Save in the same folder with suffix
                        relative_input_path = os.path.relpath(input_path, input_folder)  # Relative path for printing
                        relative_output_name = os.path.relpath(output_name, input_folder)  # Relative path for printing
                    else:  # Otherwise, save in the output folder maintaining relative structure
                        relative_path = os.path.relpath(root, input_folder)  # Get relative subpath
                        output_dir = os.path.join(
                            output_folder, relative_path
                        )  # Create corresponding subdirectory in output
                        os.makedirs(output_dir, exist_ok=True)  # Create output directory if it doesn't exist
                        output_name = os.path.join(
                            output_dir, f"{os.path.splitext(filename)[0]}{output_extension.lower()}"
                        )  # Define output file path
                        relative_input_path = os.path.relpath(input_path, input_folder)  # Relative path for printing
                        relative_output_name = os.path.relpath(output_name, output_folder)  # Relative path for printing

                    print(
                        f"{BackgroundColors.GREEN}{file_count:02d} - Converting {BackgroundColors.CYAN}{relative_input_path}{BackgroundColors.GREEN} to {BackgroundColors.CYAN}{relative_output_name}{BackgroundColors.GREEN}.{Style.RESET_ALL}"
                    )

                    image.save(
                        output_name, output_extension.strip(".").upper(), quality=100
                    )  # Save the image in the specified format, keeping full quality

                except Exception as e:  # Skip files that cannot be processed
                    relative_input_path = os.path.relpath(input_path, input_folder)  # Relative path for printing
                    print(
                        f"{BackgroundColors.RED}Skipping file {BackgroundColors.CYAN}{relative_input_path}{BackgroundColors.RED}: {e}{Style.RESET_ALL}"
                    )
                    continue  # Move to the next file

    return file_count  # Return the number of files converted


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
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Photo File Extension Converter{BackgroundColors.GREEN}!{Style.RESET_ALL}\n"
    )  # Output the welcome message

    create_directory(FULL_INPUT_FOLDER, RELATIVE_INPUT_FOLDER)  # Create the input directory
    create_directory(FULL_OUTPUT_FOLDER, RELATIVE_OUTPUT_FOLDER)  # Create the output directory

    converted_files_count = convert_photos_to_specified_format(
        input_folder=FULL_INPUT_FOLDER,
        output_folder=FULL_OUTPUT_FOLDER,
        searched_extensions=INPUT_FILE_EXTENSIONS,
        output_extension=OUTPUT_FILE_EXTENSION,
    )  # Convert the photos and get the number of files converted

    if converted_files_count == 0:  # If no files were converted
        print(
            f"{BackgroundColors.RED}No photo files found in the folder: {BackgroundColors.CYAN}{RELATIVE_INPUT_FOLDER}{Style.RESET_ALL}"
        )
    else:  # If files were converted
        print(
            f"{BackgroundColors.GREEN}Successfully converted {converted_files_count} photo file(s) to {OUTPUT_FILE_EXTENSION.lower()} format.{Style.RESET_ALL}"
        )

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
