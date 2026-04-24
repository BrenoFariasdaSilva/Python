"""
================================================================================
Image Color Transformer
================================================================================
Author      : Breno Farias da Silva
Created     : 2025-10-19
Description :
   This script recursively searches within the INPUT_PATH constant folder for all
   images named according to the TARGET_FILENAME constant (case-insensitive). For each match, it applies
   automatic visual enhancements such as brightness, contrast, and saturation
   adjustments and then saves the result as OUTPUT_FILENAME.<ext> in the same directory
   as the original image.

   Key features include:
      - Recursive folder traversal to find according to the TARGET_FILENAME constant images
      - Automatic enhancement (brightness, contrast, saturation)
      - Safe OpenCV-based image reading and writing
      - Clear and structured terminal output for each processed file

Usage:
   1. Place this script in the same directory containing the INPUT_PATH folder.
   2. Ensure you have Python and OpenCV installed:
         $ pip install opencv-python numpy
   3. Run the script:
         $ python PS2_Box_Image_Enhancer.py
   4. The enhanced images will appear beside the originals.

Outputs:
   - Box.<ext> files saved in their respective game folders (e.g., “Box.png”)
   - Console logs indicating progress and results

Dependencies:
   - Python >= 3.8
   - opencv-python
   - numpy
   - colorama (for optional terminal color output)
"""

import atexit  # For playing a sound when the program finishes
import cv2  # For image processing
import numpy as np  # For numerical operations
import os  # For file existence and path operations
import platform  # For getting the operating system name
from colorama import Style  # For coloring the terminal
from pathlib import Path  # For path manipulation


# Macros:
class BackgroundColors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    CLEAR_TERMINAL = "\033[H\033[J"


# Execution Constants:
VERBOSE = False  # Set to True to output verbose messages
INPUT_PATH = Path("./PS2 Roms/")  # Root folder path to search for images
TARGET_FILENAME = "Box - Modify"  # Target filename to search for (case-insensitive)
OUTPUT_FILENAME = "Box"  # Output filename (without extension)

# Sound Constants:
SOUND_COMMANDS = {"Darwin": "afplay", "Linux": "aplay", "Windows": "start"}
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav"

# Run Functions:
RUN_FUNCTIONS = {
    "Play Sound": True,  # Play a sound when the program finishes
}

# Enhancement Constants:
BRIGHTNESS_OFFSET = 0.0  # +15% would be 0.15
CONTRAST_GAIN = 1.5  # +50%
SATURATION_GAIN = 1.25  # +25%

# Supported Formats:
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}


def read_rgb(path: Path):
    """
    Reads an image as an RGB array.

    :param path: Path to the image file.
    :return: RGB image as a NumPy array.
    """

    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)  # Read the image using OpenCV

    if img is None:  # If the image could not be read'
        raise FileNotFoundError(f"Cannot read image: {path}")  # Raise an error

    if img.ndim == 3 and img.shape[-1] == 4:  # If the image has an alpha channel
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)  # Convert BGRA to BGR

    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)  # Convert BGR to RGB


def enhance_image(img_rgb):
    """
    Applies brightness, contrast, and saturation enhancements.

    :param img_rgb: Input RGB image as a NumPy array.
    :return: Enhanced RGB image as a NumPy array.
    """

    img = img_rgb.astype(np.float32) / 255.0  # Normalize to [0, 1]

    img += BRIGHTNESS_OFFSET  # Brightness
    img = np.clip(img, 0, 1)  # Clip to [0, 1]

    mean = np.mean(img, axis=(0, 1), keepdims=True)  # Contrast
    img = (img - mean) * CONTRAST_GAIN + mean  # Adjust contrast
    img = np.clip(img, 0, 1)  # Clip to [0, 1]

    hsv = cv2.cvtColor((img * 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)  # Saturation
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * SATURATION_GAIN, 0, 255)  # Adjust saturation
    img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32) / 255.0  # Convert back to RGB

    return (img * 255).astype(np.uint8)  # Convert back to uint8


def save_rgb(img_rgb):
    """
    Saves an RGB image to disk.

    :param img_rgb: RGB image as a NumPy array.
    :return: None
    """

    cv2.imwrite(str(os.path), cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR))


def process_image(img_path: Path):
    """
    Enhances and saves the given image as Box.<ext>.

    :param img_path: Path to the image file to be processed.
    :return: None
    """

    original = read_rgb(img_path)  # Read the original image
    enhanced = enhance_image(original)  # Enhance the image
    output_path = img_path.parent / f"{OUTPUT_FILENAME}{img_path.suffix}"  # Define the output path
    save_rgb(output_path, enhanced)  # Save the enhanced image
    print(
        f"{BackgroundColors.GREEN} Saved enhanced image: {BackgroundColors.CYAN}{output_path}{Style.RESET_ALL}\n"
    )  # Output the saved message


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
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Image Color Enhancer{BackgroundColors.GREEN}!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the Welcome message

    if not INPUT_PATH.exists():  # If the root folder does not exist
        print(f"{BackgroundColors.RED}Folder not found: {INPUT_PATH}{Style.RESET_ALL}")
        return

    for img_path in INPUT_PATH.rglob("*"):  # Recursively search for all files in the root folder
        if img_path.is_file() and img_path.suffix.lower() in IMAGE_EXTS:  # If the file is an image
            if (
                img_path.stem.lower() == TARGET_FILENAME.lower()
            ):  # If the file name is the same as the TARGET_FILENAME (case-insensitive)
                print(f" {BackgroundColors.GREEN}Processing: {BackgroundColors.CYAN}{img_path}{Style.RESET_ALL}")
                process_image(img_path)  # Process the image

    print(
        f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
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
