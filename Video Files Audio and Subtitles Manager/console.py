"""
Shared console output utilities.
"""

import os  # Run platform sound commands.
import platform  # Detect current operating system.
from pathlib import Path  # Resolve sound paths.

try:  # Import colorama style object when installed.
    from colorama import Style as COLORAMA_STYLE  # Import concrete AnsiStyle instance.
except ImportError:  # Use plain output when colorama is unavailable.
    COLORAMA_STYLE = None  # Store missing colorama marker.


class BackgroundColors:  # Store terminal color constants.
    CYAN = "\033[96m"  # Store cyan foreground.
    GREEN = "\033[92m"  # Store green foreground.
    YELLOW = "\033[93m"  # Store yellow foreground.
    RED = "\033[91m"  # Store red foreground.
    BOLD = "\033[1m"  # Store bold style.
    UNDERLINE = "\033[4m"  # Store underline style.
    CLEAR_TERMINAL = "\033[H\033[J"  # Store terminal clear sequence.


STYLE_RESET = COLORAMA_STYLE.RESET_ALL if COLORAMA_STYLE is not None else ""  # Store reset string without assigning incompatible style types.
SOUND_COMMANDS = {"Darwin": "afplay", "Linux": "aplay", "Windows": "start"}  # Store platform sound commands.


def log_debug(message: str, verbose: bool = False) -> None:
    """
    Prints a debug message when verbose output is enabled.

    :param message: Message body.
    :param verbose: Verbose output flag.
    :return: None.
    """

    if verbose:  # Verify verbose output is enabled.
        print(f"{BackgroundColors.CYAN}[DEBUG]{STYLE_RESET} {message}")  # Print debug message.


def log_warning(message: str) -> None:
    """
    Prints a warning message.

    :param message: Message body.
    :return: None.
    """

    print(f"{BackgroundColors.YELLOW}[WARNING]{STYLE_RESET} {message}")  # Print warning message.


def log_error(message: str) -> None:
    """
    Prints an error message.

    :param message: Message body.
    :return: None.
    """

    print(f"{BackgroundColors.RED}[ERROR]{STYLE_RESET} {message}")  # Print error message.


def format_duration(total_seconds: float) -> str:
    """
    Formats a duration for display.

    :param total_seconds: Duration in seconds.
    :return: Human-readable duration.
    """

    safe_seconds = max(0, int(total_seconds))  # Normalize duration.
    hours, remainder = divmod(safe_seconds, 3600)  # Split hours.
    minutes, seconds = divmod(remainder, 60)  # Split minutes and seconds.
    if hours > 0:  # Verify hour display is needed.
        return f"{hours}h {minutes}m {seconds}s"  # Return hour format.
    if minutes > 0:  # Verify minute display is needed.
        return f"{minutes}m {seconds}s"  # Return minute format.
    return f"{seconds}s"  # Return seconds format.


def play_sound(script_dir: Path, sound_file: str) -> None:
    """
    Plays a notification sound when supported.

    :param script_dir: Project directory.
    :param sound_file: Sound file path.
    :return: None.
    """

    current_os = platform.system()  # Read operating system.
    if current_os == "Windows":  # Verify Windows should skip notification sound.
        return  # Skip Windows sound.
    sound_path = script_dir / sound_file  # Resolve configured sound path.
    if sound_path.exists() and current_os in SOUND_COMMANDS:  # Verify file and command exist.
        os.system(f"{SOUND_COMMANDS[current_os]} {sound_path}")  # Play sound through platform command.
