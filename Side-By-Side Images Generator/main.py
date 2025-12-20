import atexit  # For playing a sound when the program finishes
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import warnings  # For ignoring warnings
from colorama import Style  # For coloring the terminal
from PIL import Image, ImageDraw, ImageFont  # For working with images

warnings.filterwarnings("ignore")  # Ignore warnings


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

# Constants:
FILES_FORMATS = [".jpg"]
FONT_PATH = "./Font/DejaVuSans-Bold.ttf"
INPUT_DIRECTORY = "Dataset"
OUTPUT_DIRECTORY = "Images"
DDMMYYYYFORMAT = True

# Functions:


# This function creates a directory if it does not exist
def create_directories(directory_name):
    if not os.path.exists(directory_name):  # If the directory does not exist
        os.makedirs(directory_name)  # Create the directory


# This function adds the image names to the images
def add_image_names(folder_path, image_path, OUTPUT_DIRECTORY):
    image = Image.open(f"./{image_path}")  # Open the image

    draw = ImageDraw.Draw(image)  # Draw the image

    # Font settings:
    font_path = FONT_PATH  # The font path
    font_size = 128  # The font size
    font = ImageFont.truetype(font_path, font_size)  # The font

    # Draw filename on the image (center left)
    text_height = image.height - font.getsize(folder_path)[1]  # Center vertically
    draw.text(
        (image.width / 2 - font.getsize(image_path)[0] / 2, text_height), image_path, font=font, fill="yellow"
    )  # Draw the filename

    # Save the image with the filename
    output_path = os.path.join(
        OUTPUT_DIRECTORY, f"labeled_{folder_path.replace('/', '_')}_{os.path.basename(image_path)}"
    )
    image.save(output_path)

    return output_path  # Return the output path


# This function gets the image files in the folder and returns the sorted image files list
def get_image_files_in_folder(folder_path):
    files = os.listdir(folder_path)  # Get the files in the folder
    image_files = [
        file
        for file in files
        if os.path.splitext(file)[1].lower() in FILES_FORMATS
        and not any(char.isalpha() for char in os.path.splitext(file)[0])
    ]
    image_files.sort()  # Sort the image files
    return image_files  # Return the sorted image files


# This function renames the files in the folder in the format "number.extension" and return the sorted new files list
def rename_files_numbered(folder_path, files):
    print(
        f"{BackgroundColors.GREEN}Renaming files in {BackgroundColors.CYAN}{folder_path}{Style.RESET_ALL}"
    )  # Output the renaming message
    renamed_files = []  # The renamed files list
    for index, filename in enumerate(files):  # Iterate through the files
        file_path = os.path.join(folder_path, filename)  # Get the file path
        os.rename(file_path, os.path.join(folder_path, f"{str(index + 1).zfill(2)}{os.path.splitext(filename)[1]}"))
        renamed_files.append(f"{str(index + 1).zfill(2)}{os.path.splitext(filename)[1]}")
    renamed_files.sort()  # Return the sorted renamed files list
    return renamed_files  # Return the sorted renamed files list


# This function combines the images vertically and rotates them
def find_common_files(folder1_files, folder2_files):
    return sorted(set(folder1_files) & set(folder2_files))  # Return the common files


# This function combines the images vertically and rotates them
def combine_and_rotate_images(image1, image2):
    combined_image = Image.new("RGB", (image1.width, image1.height + image2.height))  # Create a new image
    combined_image.paste(image2, (0, 0))  # Paste the first image
    combined_image.paste(image1, (0, image2.height))  # Paste the second image
    rotated_image = combined_image.rotate(-90, expand=True)  # Rotate the image
    return rotated_image  # Return the rotated image


# This function calls the functions to process the images
def process_images(folder1_path, folder2_path, output_directory):
    folder1_files = get_image_files_in_folder(folder1_path)  # Get the files in the first folder
    folder2_files = get_image_files_in_folder(folder2_path)  # Get the files in the second folder

    renamed_folder1_files = rename_files_numbered(folder1_path, folder1_files)  # Rename the files in the first folder
    renamed_folder2_files = rename_files_numbered(folder2_path, folder2_files)  # Rename the files in the second folder

    common_files = find_common_files(renamed_folder1_files, renamed_folder2_files)  # Find the common files

    for filename in common_files:  # Iterate through the common files
        image1_path = os.path.join(folder1_path, filename)  # Get the first image path
        image2_path = os.path.join(folder2_path, filename)  # Get the second image path

        labeled_image1_path = add_image_names(
            folder1_path, image1_path, output_directory
        )  # Add the image names to the first image
        labeled_image2_path = add_image_names(
            folder2_path, image2_path, output_directory
        )  # Add the image names to the second image

        labeled_image1 = Image.open(labeled_image1_path)  # Open the first labeled image
        labeled_image2 = Image.open(labeled_image2_path)  # Open the second labeled image

        combined_rotated_image = combine_and_rotate_images(
            labeled_image1, labeled_image2
        )  # Combine and rotate the images

        output_path = os.path.join(output_directory, f"combined_{filename}")  # The output path
        combined_rotated_image.save(output_path)  # Save the combined rotated image

        os.remove(labeled_image1_path)  # Remove the first labeled image
        os.remove(labeled_image2_path)  # Remove the second labeled image


# This function defines the command to play a sound when the program finishes
def play_sound():
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


# This is the Main function
def main():
    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Side-By-Side Images Generator{BackgroundColors.GREEN} program!{Style.RESET_ALL}\n"
    )  # Output the welcome message

    create_directories(OUTPUT_DIRECTORY)  # Create the output directory

    # Get the folders in the current directory
    directories = [f.path for f in os.scandir(INPUT_DIRECTORY) if f.is_dir()]  # Get the folders in the input directory

    if DDMMYYYYFORMAT:
        # Sort the folders by date the MM, then DD, then YYYY and ignore the rest of the name
        directories.sort(
            key=lambda x: (x.split(" ")[0].split(".")[1], x.split(" ")[0].split(".")[0], x.split(" ")[0].split(".")[2])
        )

    for index in range(len(directories) - 1):  # Iterate through the directories
        process_images(directories[index], directories[index + 1], OUTPUT_DIRECTORY)  # Combine the images

    print(
        f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
    )  # Output the end of the program message


# This is the standard boilerplate that calls the main() function.
if __name__ == "__main__":
    main()  # Call the main function
