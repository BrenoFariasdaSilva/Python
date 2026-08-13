"""
================================================================================
Video Files Audio and Subtitles Manager
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-13
Description :
    Small entry point for the modular video audio and subtitles manager.
"""

import atexit  # Register optional notification sound.
import datetime  # Measure application runtime.
from config import AppConfig, parse_arguments  # Load CLI and application configuration.
from console import BackgroundColors, STYLE_RESET, format_duration, log_error, log_warning, play_sound  # Use shared console behavior.
from command_runner import CommandRunner  # Execute external commands.
from processor import VideoProcessor  # Coordinate video processing workflow.


def main() -> None:
    """
    Runs the application entry point.

    :return: None.
    """

    print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Video Files Audio and Subtitles Manager{BackgroundColors.GREEN}!{STYLE_RESET}\n")  # Print welcome message.
    start_time = datetime.datetime.now()  # Store start timestamp.
    config = AppConfig.from_args(parse_arguments())  # Build runtime configuration from CLI.
    runner = CommandRunner(config.verbose)  # Create command runner with verbose setting.

    if not runner.has_required_commands(("ffmpeg", "ffprobe")):  # Verify required media commands exist.
        return  # Stop when required tools are missing.
    if not config.input_directory.exists() or not config.input_directory.is_dir():  # Verify input directory exists.
        log_error(f"Input directory not found or invalid: {config.input_directory}")  # Report invalid input directory.
        return  # Stop when input directory is invalid.

    processor = VideoProcessor(config, runner)  # Create workflow orchestrator.
    statuses = processor.process_all()  # Process all discovered videos.
    if not statuses:  # Verify at least one video was processed.
        log_warning(f"No video files processed in {config.input_directory}")  # Report empty processing result.
        return  # Stop after empty processing result.

    finish_time = datetime.datetime.now()  # Store finish timestamp.
    modified_count = sum(1 for status in statuses if status.audio_modified)  # Count audio modifications.
    ptbr_count = sum(1 for status in statuses if status.ptbr_available)  # Count PT-BR availability.
    print(f"\n{BackgroundColors.GREEN}Videos processed: {BackgroundColors.CYAN}{len(statuses)}{STYLE_RESET}")  # Print processed count.
    print(f"{BackgroundColors.GREEN}Audio defaults modified: {BackgroundColors.CYAN}{modified_count}{STYLE_RESET}")  # Print audio modification count.
    print(f"{BackgroundColors.GREEN}Videos with PT-BR subtitles available: {BackgroundColors.CYAN}{ptbr_count}{STYLE_RESET}")  # Print PT-BR count.
    print(f"{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{format_duration((finish_time - start_time).total_seconds())}{STYLE_RESET}")  # Print execution duration.
    if config.play_sound:  # Verify sound notification is enabled.
        atexit.register(play_sound, config.script_dir, config.sound_file)  # Register notification sound.


if __name__ == "__main__":  # Detect direct execution.
    main()  # Run entry point.
