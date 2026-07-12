"""
================================================================================
Audio Track Offset Syncronization
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-07-11
Description :
    Extract configured audio tracks from two MKV sources, estimate their temporal
    offset through waveform cross-correlation, and create a synchronized MP3 copy.
    Subtitle streams from both sources are extracted concurrently while the audio
    workflow runs, with codec-aware output formats and isolated temporary files.

    Key features include:
        - Direct MKV paths or directories containing exactly one MKV file.
        - Zero-based audio-track selection validated through FFprobe.
        - Parallel audio and subtitle extraction through ThreadPoolExecutor.
        - FFT-based offset estimation through librosa, NumPy, and SciPy.
        - Codec-aware subtitle extraction to SRT, SUP, or Matroska subtitle files.
        - Atomic replacement of generated media outputs after validation.
        - Synchronized MP3 copies in the target and reference media directories.
        - Terminal output with execution-time reporting.

Usage:
    1. Configure REFERENCE_FILE and TO_SYNCRONIZE_FILE below.
    2. Ensure ffmpeg and ffprobe are available through the system PATH.
    3. Run the script with: python main.py

Outputs:
    - original.mp3 beside the reference MKV file.
    - to_syncronize.mp3 beside the target MKV file.
    - syncronized.mp3 beside both configured MKV files when directories differ.
    - Extracted subtitle files beside their source MKV files.

Dependencies:
    - Python >= 3.10
    - FFmpeg and FFprobe
    - librosa
    - NumPy
    - SciPy

Assumptions & Notes:
    - Audio indexes are zero-based among audio streams, not global stream indexes.
    - Offset analysis uses the first ANALYSIS_DURATION_SECONDS seconds of each MP3.
    - Text subtitles are converted to SRT, PGS subtitles are copied to SUP, and
      other subtitle codecs are copied losslessly to Matroska subtitle files.
    - Existing output files are replaced only after a new temporary output passes
      file validation.
"""

from __future__ import annotations  # Enable postponed annotation evaluation.

import atexit  # Register shutdown actions after successful execution.
import datetime  # Capture and format execution timestamps.
import json  # Parse FFprobe subtitle metadata.
import os  # Normalize platform-specific paths and inspect directories.
import platform  # Identify the operating system for sound playback.
import re  # Sanitize subtitle filename components.
import shutil  # Locate executables and copy synchronized audio files.
import subprocess  # Execute FFmpeg, FFprobe, and sound commands.
import uuid  # Generate collision-resistant temporary output filenames.
from collections.abc import Mapping  # Type configuration mappings.
from concurrent.futures import Future, ThreadPoolExecutor  # Run media extraction tasks concurrently.
from pathlib import Path  # Resolve and manipulate filesystem paths.
from typing import Any, TypeAlias  # Define reusable static types.

import librosa  # Decode and resample extracted audio for analysis.
import numpy as np  # Normalize waveforms and locate the strongest correlation.
from numpy.typing import NDArray  # Type NumPy audio arrays.
from scipy.signal import correlate, correlation_lags  # Calculate full waveform cross-correlation.


class BackgroundColors:  # Store ANSI escape sequences used by terminal messages.
    CYAN = "\033[96m"  # Represent cyan terminal text.
    GREEN = "\033[92m"  # Represent green terminal text.
    YELLOW = "\033[93m"  # Represent yellow terminal text.
    RED = "\033[91m"  # Represent red terminal text.
    BOLD = "\033[1m"  # Enable bold terminal text.
    UNDERLINE = "\033[4m"  # Enable underlined terminal text.
    CLEAR_TERMINAL = "\033[H\033[J"  # Clear the active terminal viewport.
    RESET = "\033[0m"  # Reset terminal formatting.


AudioArray: TypeAlias = NDArray[np.float32]  # Represent normalized mono audio samples.
SubtitleTrack: TypeAlias = tuple[int, str, str]  # Represent subtitle index, codec, and language.
SubtitleSpecification: TypeAlias = tuple[Path, int, str, str, Path, list[str]]  # Represent one subtitle extraction task.
SubtitleResult: TypeAlias = tuple[Path | None, str | None]  # Represent one subtitle output or warning.

VERBOSE = False  # Control optional diagnostic output.

SOUND_COMMANDS: dict[str, str] = {  # Map supported operating systems to sound executables.
    "Darwin": "afplay",  # Use afplay on macOS.
    "Linux": "aplay",  # Use aplay on Linux.
    "Windows": "start",  # Preserve the template Windows sound command mapping.
}
SOUND_FILE = Path("./.assets/Sounds/NotificationSound.wav")  # Configure the completion sound path.

RUN_FUNCTIONS: dict[str, bool] = {  # Configure optional execution behavior.
    "Play Sound": True,  # Enable completion sound registration after successful execution.
}

REFERENCE_FILE: dict[str, object] = {  # Configure the reference MKV source and audio index.
    "path": Path(  # Preserve the configured reference media path.
        r"D:\Sem Backup\Download\Torrent\Completed\Horrible Bosses 2011 Extended Ai Upscaled BluRay.60FPS\Horrible Bosses 2011 Extended Ai Upscaled BluRay.60FPS.mkv"  # Store the complete reference MKV path.
    ),
    "index": 0,  # Select the first audio track from the reference MKV.
}

TO_SYNCRONIZE_FILE: dict[str, object] = {  # Configure the target MKV source and audio index.
    "path": Path(  # Preserve the configured target media path.
        r"D:\Sem Backup\Download\Torrent\Completed\Quero Matar Meu Chefe (2011) BluRay 720p Dual Audio - ramonTPB\Quero Matar Meu Chefe (2011) BluRay 720p Dual Audio ramonTPB.mkv"  # Store the complete target MKV path.
    ),
    "index": 1,  # Select the second audio track from the target MKV.
}

SAMPLE_RATE = 8_000  # Configure the analysis sample rate in hertz.
ANALYSIS_DURATION_SECONDS = 300  # Limit waveform analysis to the first five minutes.
MINIMUM_OFFSET_SECONDS = 0.001  # Ignore offsets smaller than one millisecond.

REFERENCE_AUDIO_FILENAME = "original.mp3"  # Configure the extracted reference-audio filename.
TO_SYNCRONIZE_AUDIO_FILENAME = "to_syncronize.mp3"  # Configure the extracted target-audio filename.
SYNCRONIZED_AUDIO_FILENAME = "syncronized.mp3"  # Configure the synchronized-audio filename.

TEXT_SUBTITLE_CODECS: set[str] = {  # Define subtitle codecs that FFmpeg can convert to SRT.
    "ass",  # Convert Advanced SubStation Alpha subtitles.
    "eia_608",  # Convert EIA-608 closed captions.
    "eia_708",  # Convert EIA-708 closed captions.
    "jacosub",  # Convert JACOsub subtitles.
    "microdvd",  # Convert MicroDVD subtitles.
    "mov_text",  # Convert QuickTime text subtitles.
    "mpl2",  # Convert MPL2 subtitles.
    "pjs",  # Convert PJS subtitles.
    "realtext",  # Convert RealText subtitles.
    "sami",  # Convert SAMI subtitles.
    "ssa",  # Convert SubStation Alpha subtitles.
    "subrip",  # Convert SubRip subtitles.
    "subviewer",  # Convert SubViewer subtitles.
    "subviewer1",  # Convert SubViewer 1 subtitles.
    "text",  # Convert generic text subtitles.
    "ttml",  # Convert Timed Text Markup Language subtitles.
    "vplayer",  # Convert VPlayer subtitles.
    "webvtt",  # Convert WebVTT subtitles.
}

LANGUAGE_NAMES: dict[str, str] = {  # Map common subtitle language tags to display names.
    "ara": "Arabic",  # Map the ISO 639-2 Arabic tag.
    "ar": "Arabic",  # Map the ISO 639-1 Arabic tag.
    "chi": "Chinese",  # Map the legacy ISO 639-2 Chinese tag.
    "zho": "Chinese",  # Map the modern ISO 639-2 Chinese tag.
    "zh": "Chinese",  # Map the ISO 639-1 Chinese tag.
    "dut": "Dutch",  # Map the legacy ISO 639-2 Dutch tag.
    "nld": "Dutch",  # Map the modern ISO 639-2 Dutch tag.
    "nl": "Dutch",  # Map the ISO 639-1 Dutch tag.
    "eng": "English",  # Map the ISO 639-2 English tag.
    "en": "English",  # Map the ISO 639-1 English tag.
    "fre": "French",  # Map the legacy ISO 639-2 French tag.
    "fra": "French",  # Map the modern ISO 639-2 French tag.
    "fr": "French",  # Map the ISO 639-1 French tag.
    "ger": "German",  # Map the legacy ISO 639-2 German tag.
    "deu": "German",  # Map the modern ISO 639-2 German tag.
    "de": "German",  # Map the ISO 639-1 German tag.
    "hin": "Hindi",  # Map the ISO 639-2 Hindi tag.
    "hi": "Hindi",  # Map the ISO 639-1 Hindi tag.
    "ita": "Italian",  # Map the ISO 639-2 Italian tag.
    "it": "Italian",  # Map the ISO 639-1 Italian tag.
    "jpn": "Japanese",  # Map the ISO 639-2 Japanese tag.
    "ja": "Japanese",  # Map the ISO 639-1 Japanese tag.
    "kor": "Korean",  # Map the ISO 639-2 Korean tag.
    "ko": "Korean",  # Map the ISO 639-1 Korean tag.
    "por": "PT-BR",  # Map generic Portuguese to Brazilian Portuguese.
    "pt": "PT-BR",  # Map generic short Portuguese to Brazilian Portuguese.
    "pt-br": "PT-BR",  # Map the normalized Brazilian Portuguese tag.
    "pt_br": "PT-BR",  # Map the underscore Brazilian Portuguese tag.
    "pob": "PT-BR",  # Map the common Brazilian Portuguese alias.
    "ptb": "PT-BR",  # Map the alternate Brazilian Portuguese alias.
    "rum": "Romanian",  # Map the legacy ISO 639-2 Romanian tag.
    "ron": "Romanian",  # Map the modern ISO 639-2 Romanian tag.
    "ro": "Romanian",  # Map the ISO 639-1 Romanian tag.
    "rus": "Russian",  # Map the ISO 639-2 Russian tag.
    "ru": "Russian",  # Map the ISO 639-1 Russian tag.
    "spa": "Spanish",  # Map the ISO 639-2 Spanish tag.
    "es": "Spanish",  # Map the ISO 639-1 Spanish tag.
    "tur": "Turkish",  # Map the ISO 639-2 Turkish tag.
    "tr": "Turkish",  # Map the ISO 639-1 Turkish tag.
    "und": "Unknown",  # Map an undefined language tag.
}


def verbose_output(true_string: str = "", false_string: str = "") -> None:  # Define the verbose_output operation.
    """
    Output a message according to the verbose configuration.

    :param true_string: Message emitted when verbose output is enabled.
    :param false_string: Message emitted when verbose output is disabled.
    :return: None.
    """

    if VERBOSE and true_string != "":  # Emit the verbose message when enabled and provided.
        print(true_string)  # Write the verbose message to the terminal.
    elif false_string != "":  # Emit the fallback message when provided.
        print(false_string)  # Write the fallback message to the terminal.


def resolve_entry_with_trailing_space(current_path: str, entry: str, stripped_part: str) -> str:  # Define the resolve_entry_with_trailing_space operation.
    """
    Resolve and optionally rename one directory entry containing trailing spaces.

    :param current_path: Current directory path.
    :param entry: Existing directory entry name.
    :param stripped_part: Normalized target name without surrounding spaces.
    :return: Resolved path after an optional rename attempt.
    """

    try:  # Isolate path-resolution failures from the calling fallback flow.
        resolved = os.path.join(current_path, entry)  # Build the existing entry path.

        if entry != stripped_part:  # Validate that the entry contains removable surrounding spaces.
            corrected = os.path.join(current_path, stripped_part)  # Build the normalized entry path.

            try:  # Attempt to rename the entry to its normalized form.
                os.rename(resolved, corrected)  # Rename the filesystem entry.
                verbose_output(  # Emit the successful rename only in verbose mode.
                    true_string=(  # Build the formatted rename message.
                        f"{BackgroundColors.GREEN}Renamed: {BackgroundColors.CYAN}"  # Add the message prefix.
                        f"{resolved}{BackgroundColors.GREEN} -> {BackgroundColors.CYAN}"  # Add the source and separator.
                        f"{corrected}{BackgroundColors.RESET}"  # Add the destination and reset formatting.
                    )
                )
                resolved = corrected  # Continue resolution from the normalized path.
            except Exception:  # Preserve the original path when the rename operation fails.
                verbose_output(  # Emit the failed rename only in verbose mode.
                    true_string=(  # Build the formatted failure message.
                        f"{BackgroundColors.RED}Failed to rename: {BackgroundColors.CYAN}"  # Add the failure prefix.
                        f"{resolved}{BackgroundColors.RESET}"  # Add the unresolved path and reset formatting.
                    )
                )

        return resolved  # Return the resolved or original entry path.
    except Exception:  # Recover from unexpected path construction failures.
        return os.path.join(current_path, entry)  # Return the direct fallback path.


def resolve_full_trailing_space_path(filepath: str) -> str:  # Define the resolve_full_trailing_space_path operation.
    """
    Resolve trailing-space mismatches across every path component.

    :param filepath: Path that may contain component spacing mismatches.
    :return: Corrected full path when resolvable, otherwise the original path.
    """

    try:  # Contain all path traversal failures within the fallback behavior.
        verbose_output(  # Emit the path-resolution start only in verbose mode.
            true_string=(  # Build the formatted path-resolution message.
                f"{BackgroundColors.GREEN}Resolving full trailing space path for: "  # Add the message prefix.
                f"{BackgroundColors.CYAN}{filepath}{BackgroundColors.RESET}"  # Add the path and reset formatting.
            )
        )

        if not isinstance(filepath, str) or not filepath:  # Validate that the supplied path is a nonempty string.
            verbose_output(  # Emit invalid input only in verbose mode.
                true_string=(  # Build the invalid-input message.
                    f"{BackgroundColors.YELLOW}Invalid filepath provided, skipping resolution."  # Add the warning text.
                    f"{BackgroundColors.RESET}"  # Reset terminal formatting.
                )
            )

            return filepath  # Preserve invalid input unchanged.

        expanded_filepath = os.path.expanduser(filepath)  # Expand a leading home-directory marker.
        parts = expanded_filepath.split(os.sep)  # Split the path into platform-specific components.

        if not parts:  # Validate that path splitting produced at least one component.
            return expanded_filepath  # Return the expanded path when no components exist.

        if expanded_filepath.startswith(os.sep):  # Detect an absolute path rooted at the filesystem separator.
            current_path = os.sep  # Begin traversal from the filesystem root.
            parts = parts[1:]  # Remove the empty root component.
        else:  # Handle relative and drive-relative paths.
            current_path = parts[0] if parts[0] else os.getcwd()  # Select the first component or working directory.
            parts = parts[1:] if parts[0] else parts  # Remove the selected base component when present.

        for part in parts:  # Traverse each remaining path component in order.
            if part == "":  # Ignore empty components created by repeated separators.
                continue  # Continue with the next path component.

            try:  # Attempt to inspect entries under the current path.
                entries = os.listdir(current_path) if os.path.isdir(current_path) else []  # Read entries only from directories.
            except Exception:  # Preserve the original path when directory inspection fails.
                verbose_output(  # Emit the directory failure only in verbose mode.
                    true_string=(  # Build the directory failure message.
                        f"{BackgroundColors.RED}Failed to list directory: {BackgroundColors.CYAN}"  # Add the failure prefix.
                        f"{current_path}{BackgroundColors.RESET}"  # Add the directory and reset formatting.
                    )
                )

                return expanded_filepath  # Return the expanded original path.

            stripped_part = part.strip()  # Normalize surrounding spaces from the requested component.
            match_found = False  # Track whether a matching filesystem entry is discovered.

            for entry in entries:  # Compare every current directory entry with the normalized component.
                try:  # Contain unexpected entry-comparison failures.
                    if entry.strip() == stripped_part:  # Compare normalized entry and component names.
                        current_path = resolve_entry_with_trailing_space(  # Resolve the matching entry path.
                            current_path,  # Pass the current directory path.
                            entry,  # Pass the actual filesystem entry name.
                            stripped_part,  # Pass the normalized component name.
                        )
                        match_found = True  # Record the successful component match.
                        break  # Stop scanning entries after the first match.
                except Exception:  # Ignore one malformed or inaccessible entry.
                    continue  # Continue scanning the remaining entries.

            if not match_found:  # Detect a component that cannot be resolved.
                verbose_output(  # Emit the unresolved component only in verbose mode.
                    true_string=(  # Build the unresolved-component message.
                        f"{BackgroundColors.YELLOW}No match for segment: {BackgroundColors.CYAN}"  # Add the warning prefix.
                        f"{part}{BackgroundColors.RESET}"  # Add the segment and reset formatting.
                    )
                )

                return expanded_filepath  # Return the expanded original path after a failed match.

        return current_path  # Return the completely resolved path.
    except Exception:  # Recover from any unexpected full-path resolution failure.
        verbose_output(  # Emit the unexpected failure only in verbose mode.
            true_string=(  # Build the unexpected failure message.
                f"{BackgroundColors.RED}Error resolving full path: {BackgroundColors.CYAN}"  # Add the failure prefix.
                f"{filepath}{BackgroundColors.RESET}"  # Add the original path and reset formatting.
            )
        )

        return filepath  # Preserve the original path after an unexpected failure.


def verify_filepath_exists(filepath: str | Path) -> bool:  # Define the verify_filepath_exists operation.
    """
    Verify whether a file or directory exists through normalized path variants.

    :param filepath: Path to the file or directory.
    :return: True when a resolvable path exists, otherwise False.
    """

    try:  # Contain path normalization errors within a deterministic result.
        filepath_string = str(filepath)  # Convert pathlib values to their string representation.
        verbose_output(  # Emit the existence verification only in verbose mode.
            true_string=(  # Build the formatted verification message.
                f"{BackgroundColors.GREEN}Verifying if the file or folder exists at the path: "  # Add the message prefix.
                f"{BackgroundColors.CYAN}{filepath_string}{BackgroundColors.RESET}"  # Add the path and reset formatting.
            )
        )

        if not filepath_string.strip():  # Reject empty and whitespace-only paths.
            verbose_output(  # Emit invalid input only in verbose mode.
                true_string=(  # Build the invalid-input warning.
                    f"{BackgroundColors.YELLOW}Invalid filepath provided, skipping existence verification."  # Add the warning text.
                    f"{BackgroundColors.RESET}"  # Reset terminal formatting.
                )
            )

            return False  # Report that an empty path does not exist.

        if os.path.exists(filepath_string):  # Use the original path as the fastest existence path.
            return True  # Report the original path as existing.

        candidate = filepath_string.strip()  # Remove surrounding whitespace from the path.

        if (candidate.startswith("'") and candidate.endswith("'")) or (  # Detect single-quoted or double-quoted paths.
            candidate.startswith('"') and candidate.endswith('"')  # Detect matching double quotes.
        ):
            candidate = candidate[1:-1].strip()  # Remove wrapping quotes and normalize remaining whitespace.

        candidate = os.path.expanduser(candidate)  # Expand a leading home-directory marker.
        candidate = os.path.normpath(candidate)  # Normalize separators and path structure.

        if os.path.exists(candidate):  # Validate the normalized candidate directly.
            return True  # Report the normalized candidate as existing.

        repository_directory = os.path.dirname(os.path.abspath(__file__))  # Resolve the script directory.
        current_working_directory = os.getcwd()  # Capture the active working directory.
        relative_candidate = candidate.lstrip(os.sep) if candidate.startswith(os.sep) else candidate  # Build a relative-safe variant.
        repository_candidate = os.path.join(repository_directory, relative_candidate)  # Build the script-relative variant.
        working_directory_candidate = os.path.join(current_working_directory, relative_candidate)  # Build the working-directory variant.

        for path_variant in (repository_candidate, working_directory_candidate):  # Inspect both alternative base directories.
            try:  # Contain normalization failures for one path variant.
                normalized_variant = os.path.normpath(path_variant)  # Normalize the current alternative path.

                if os.path.exists(normalized_variant):  # Validate whether the alternative path exists.
                    return True  # Report the resolved alternative path as existing.
            except Exception:  # Ignore one invalid alternative path.
                continue  # Continue with the next alternative path.

        try:  # Attempt absolute path resolution as a final direct fallback.
            absolute_candidate = os.path.abspath(candidate)  # Build an absolute candidate path.

            if os.path.exists(absolute_candidate):  # Validate the absolute candidate path.
                return True  # Report the absolute path as existing.
        except Exception:  # Ignore absolute path conversion failures.
            pass  # Continue to trailing-space resolution.

        for path_variant in (candidate, repository_candidate, working_directory_candidate):  # Inspect trailing-space variants.
            try:  # Contain failures from one trailing-space resolution attempt.
                resolved = resolve_full_trailing_space_path(path_variant)  # Resolve component spacing mismatches.

                if resolved != path_variant and os.path.exists(resolved):  # Validate a changed and existing resolved path.
                    verbose_output(  # Emit the resolved mismatch only in verbose mode.
                        true_string=(  # Build the resolved-mismatch message.
                            f"{BackgroundColors.YELLOW}Resolved trailing space mismatch: "  # Add the message prefix.
                            f"{BackgroundColors.CYAN}{path_variant}{BackgroundColors.YELLOW} -> "  # Add the original path and separator.
                            f"{BackgroundColors.CYAN}{resolved}{BackgroundColors.RESET}"  # Add the resolved path and reset formatting.
                        )
                    )

                    return True  # Report the trailing-space-resolved path as existing.
            except Exception:  # Ignore one trailing-space resolution failure.
                continue  # Continue with the remaining path variants.

        return False  # Report that no path variant exists.
    except Exception as error:  # Preserve unexpected failures after recording their message.
        print(str(error))  # Write the unexpected path error to the terminal.
        raise  # Re-raise the original exception without changing its traceback.


def to_seconds(obj: object) -> float | None:  # Define the to_seconds operation.
    """
    Convert supported time-like values to seconds.

    :param obj: Numeric, datetime, or timedelta value to convert.
    :return: Equivalent seconds, or None when conversion is unsupported.
    """

    if obj is None:  # Reject an absent value.
        return None  # Report that no conversion is available.

    if isinstance(obj, (int, float)):  # Accept numeric seconds and timestamps directly.
        return float(obj)  # Return the numeric value as floating-point seconds.

    if isinstance(obj, datetime.timedelta):  # Accept duration objects.
        return float(obj.total_seconds())  # Convert the duration to total seconds.

    if isinstance(obj, datetime.datetime):  # Accept absolute datetime objects.
        return float(obj.timestamp())  # Convert the datetime to a Unix timestamp.

    return None  # Report unsupported value types.


def calculate_execution_time(start_time: object, finish_time: object | None = None) -> str:  # Define the calculate_execution_time operation.
    """
    Calculate a human-readable execution duration.

    :param start_time: Start timestamp or direct duration value.
    :param finish_time: Optional finish timestamp.
    :return: Duration formatted with days, hours, minutes, and seconds as needed.
    """

    if finish_time is None:  # Interpret the first argument as a direct duration.
        total_seconds = to_seconds(start_time)  # Convert the direct duration to seconds.

        if total_seconds is None:  # Detect an unsupported direct duration type.
            try:  # Attempt final numeric coercion.
                total_seconds = float(start_time)  # Convert a numeric-compatible value to seconds.
            except (TypeError, ValueError):  # Recover from unsupported numeric conversion.
                total_seconds = 0.0  # Use zero seconds as the deterministic fallback.
    else:  # Interpret both arguments as start and finish timestamps.
        start_seconds = to_seconds(start_time)  # Convert the start value to seconds.
        finish_seconds = to_seconds(finish_time)  # Convert the finish value to seconds.

        if start_seconds is not None and finish_seconds is not None:  # Validate both timestamp conversions.
            total_seconds = finish_seconds - start_seconds  # Calculate elapsed seconds.
        else:  # Recover when either timestamp conversion is unsupported.
            try:  # Attempt direct numeric coercion for both values.
                total_seconds = float(finish_time) - float(start_time)  # Calculate a numerically coerced duration.
            except (TypeError, ValueError):  # Recover from unsupported numeric conversion.
                total_seconds = 0.0  # Use zero seconds as the deterministic fallback.

    if total_seconds < 0:  # Normalize inverted timestamps to a positive duration.
        total_seconds = abs(total_seconds)  # Convert the duration to its absolute value.

    days = int(total_seconds // 86_400)  # Calculate complete elapsed days.
    hours = int((total_seconds % 86_400) // 3_600)  # Calculate remaining elapsed hours.
    minutes = int((total_seconds % 3_600) // 60)  # Calculate remaining elapsed minutes.
    seconds = int(total_seconds % 60)  # Calculate remaining elapsed seconds.

    if days > 0:  # Include days when the duration spans at least one day.
        return f"{days}d {hours}h {minutes}m {seconds}s"  # Return the complete day-based duration.

    if hours > 0:  # Include hours when the duration spans at least one hour.
        return f"{hours}h {minutes}m {seconds}s"  # Return the hour-based duration.

    if minutes > 0:  # Include minutes when the duration spans at least one minute.
        return f"{minutes}m {seconds}s"  # Return the minute-based duration.

    return f"{seconds}s"  # Return a seconds-only duration.


def play_sound() -> None:  # Define the play_sound operation.
    """
    Play the configured completion sound on supported non-Windows systems.

    :return: None.
    """

    current_os = platform.system()  # Identify the active operating system.

    if current_os == "Windows":  # Preserve the template behavior that skips sound on Windows.
        return  # Finish without launching a sound command.

    if not verify_filepath_exists(SOUND_FILE):  # Validate that the configured sound file exists.
        print(  # Report the missing sound file.
            f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}"  # Add the missing-file path.
            f"{BackgroundColors.RED} not found. Make sure the file exists."  # Add the remediation message.
            f"{BackgroundColors.RESET}"  # Reset terminal formatting.
        )

        return  # Finish after reporting the missing sound file.

    sound_command = SOUND_COMMANDS.get(current_os)  # Resolve the sound executable for the current platform.

    if sound_command is None:  # Detect an unsupported operating system.
        print(  # Report the unsupported operating system.
            f"{BackgroundColors.RED}The {BackgroundColors.CYAN}{current_os}"  # Add the operating-system name.
            f"{BackgroundColors.RED} is not in the {BackgroundColors.CYAN}"  # Add the configuration reference.
            f"SOUND_COMMANDS{BackgroundColors.RED} dictionary. Please add it!"  # Add the remediation message.
            f"{BackgroundColors.RESET}"  # Reset terminal formatting.
        )

        return  # Finish after reporting the unsupported operating system.

    try:  # Attempt noninteractive sound playback without invoking a shell.
        subprocess.run(  # Execute the platform sound command.
            [sound_command, str(SOUND_FILE)],  # Pass the executable and sound path as separate arguments.
            check=False,  # Avoid converting an optional sound failure into a program failure.
            stdout=subprocess.DEVNULL,  # Suppress sound-command standard output.
            stderr=subprocess.DEVNULL,  # Suppress sound-command standard error.
        )
    except OSError as error:  # Recover from a missing or inaccessible sound executable.
        print(  # Report the optional sound playback failure.
            f"{BackgroundColors.YELLOW}Unable to play the completion sound: "  # Add the warning prefix.
            f"{error}{BackgroundColors.RESET}"  # Add the operating-system error and reset formatting.
        )


def validate_dependencies() -> None:  # Define the validate_dependencies operation.
    """
    Validate that FFmpeg and FFprobe are available through the system PATH.

    :return: None.
    """

    missing_dependencies = [  # Collect required executables that cannot be resolved.
        executable  # Preserve the missing executable name.
        for executable in ("ffmpeg", "ffprobe")  # Inspect both required FFmpeg executables.
        if shutil.which(executable) is None  # Retain executables absent from the active PATH.
    ]

    if missing_dependencies:  # Detect one or more unavailable executables.
        missing = ", ".join(missing_dependencies)  # Format the unavailable executable names.
        raise RuntimeError(  # Stop execution with an actionable dependency error.
            f"Required executable(s) not found in PATH: {missing}. "  # Identify missing executables.
            "Install FFmpeg and ensure both ffmpeg and ffprobe are available."  # Explain the required remediation.
        )


def resolve_file_configuration(configuration: Mapping[str, object], configuration_name: str) -> tuple[Path, int]:  # Define the resolve_file_configuration operation.
    """
    Resolve one configured MKV path and zero-based audio-track index.

    :param configuration: Mapping containing path and optional index values.
    :param configuration_name: Display name used in validation errors.
    :return: Resolved MKV path and validated audio-track index.
    """

    path_value = configuration.get("path")  # Read the configured media path.
    index_value = configuration.get("index", 0)  # Read the configured audio index with a zero fallback.

    if not isinstance(path_value, (str, Path)):  # Validate the configured path value type.
        raise TypeError(  # Reject unsupported path values.
            f'{configuration_name}["path"] must be a string or pathlib.Path.'  # Describe the required path type.
        )

    if isinstance(index_value, bool) or not isinstance(index_value, int):  # Reject booleans and noninteger indexes.
        raise TypeError(f'{configuration_name}["index"] must be an integer.')  # Describe the required index type.

    if index_value < 0:  # Reject negative zero-based indexes.
        raise ValueError(  # Report the invalid negative index.
            f'{configuration_name}["index"] cannot be negative: {index_value}'  # Include the rejected value.
        )

    configured_path = Path(path_value).expanduser().resolve()  # Expand and normalize the configured path.

    if not configured_path.exists():  # Validate that the normalized path exists.
        raise FileNotFoundError(  # Stop execution when the configured path is absent.
            f"Path configured in {configuration_name} was not found: "  # Identify the affected configuration.
            f"{configured_path}"  # Include the normalized missing path.
        )

    if configured_path.is_file():  # Handle a directly configured media file.
        if configured_path.suffix.casefold() != ".mkv":  # Validate the extension case-insensitively.
            raise ValueError(  # Reject direct files that are not MKV containers.
                f"File configured in {configuration_name} is not an MKV file: "  # Identify the invalid configuration.
                f"{configured_path}"  # Include the rejected file path.
            )

        mkv_path = configured_path  # Preserve the validated direct MKV path.
    elif configured_path.is_dir():  # Handle a directory expected to contain one direct MKV file.
        mkv_files = sorted(  # Collect direct MKV children in deterministic order.
            (  # Build a filtered generator of direct MKV files.
                candidate  # Preserve each matching candidate path.
                for candidate in configured_path.iterdir()  # Inspect direct directory children only.
                if candidate.is_file() and candidate.suffix.casefold() == ".mkv"  # Retain case-insensitive MKV files.
            ),
            key=lambda candidate: candidate.name.casefold(),  # Sort filenames case-insensitively.
        )

        if not mkv_files:  # Detect a directory without a direct MKV file.
            raise FileNotFoundError(  # Stop execution when no MKV candidate exists.
                "No MKV file was found directly inside the directory configured "  # Describe the missing media condition.
                f"in {configuration_name}: {configured_path}"  # Identify the affected directory.
            )

        if len(mkv_files) > 1:  # Detect an ambiguous directory with multiple direct MKV files.
            matches = "\n".join(  # Format every ambiguous MKV filename.
                f"  - {candidate.name}"  # Format one matching filename.
                for candidate in mkv_files  # Iterate through all matching MKV files.
            )
            raise ValueError(  # Require the user to select one exact MKV path.
                "Multiple MKV files were found directly inside the directory "  # Describe the ambiguity.
                f"configured in {configuration_name}: {configured_path}\n"  # Identify the affected directory.
                f"Specify the exact MKV file instead. Matches:\n{matches}"  # List all ambiguous candidates.
            )

        mkv_path = mkv_files[0]  # Select the only direct MKV file.
        print(  # Report directory-to-file resolution.
            f"{configuration_name}: directory resolved to MKV file: "  # Identify the configuration source.
            f"{mkv_path}"  # Include the resolved MKV path.
        )
    else:  # Handle special filesystem objects that are neither regular files nor directories.
        raise ValueError(  # Reject unsupported filesystem object types.
            f"Path configured in {configuration_name} is neither a regular file "  # Describe the invalid object type.
            f"nor a directory: {configured_path}"  # Include the rejected path.
        )

    return mkv_path, index_value  # Return the validated MKV path and audio index.


def run_ffmpeg(command: list[str]) -> None:  # Define the run_ffmpeg operation.
    """
    Execute one FFmpeg command and convert process failures to runtime errors.

    :param command: Complete FFmpeg argument vector.
    :return: None.
    """

    print("Executing:")  # Introduce the exact FFmpeg command.
    print(subprocess.list2cmdline(command))  # Render the command using platform-aware quoting.

    try:  # Execute FFmpeg while preserving the original process output streams.
        subprocess.run(command, check=True)  # Raise an exception when FFmpeg returns a nonzero exit code.
    except subprocess.CalledProcessError as error:  # Convert FFmpeg process failures to a stable exception type.
        raise RuntimeError(  # Raise a concise application-level FFmpeg error.
            f"FFmpeg failed with exit code {error.returncode}."  # Include the process exit code.
        ) from error
    except OSError as error:  # Convert executable launch failures to a stable exception type.
        raise RuntimeError(f"FFmpeg could not be started: {error}") from error  # Preserve the operating-system details.


def run_ffprobe(command: list[str], context: str) -> subprocess.CompletedProcess[str]:  # Define the run_ffprobe operation.
    """
    Execute one FFprobe command and capture UTF-8 output.

    :param command: Complete FFprobe argument vector.
    :param context: Human-readable operation description used in failures.
    :return: Successful completed FFprobe process.
    """

    try:  # Execute FFprobe with captured text output.
        return subprocess.run(  # Return the successful completed process.
            command,  # Pass the complete FFprobe argument vector.
            check=True,  # Raise an exception when FFprobe returns a nonzero exit code.
            capture_output=True,  # Capture standard output and standard error.
            text=True,  # Decode captured streams to strings.
            encoding="utf-8",  # Decode captured streams as UTF-8.
            errors="replace",  # Replace malformed byte sequences deterministically.
        )
    except subprocess.CalledProcessError as error:  # Convert FFprobe process failures to runtime errors.
        details = error.stderr.strip() or "No FFprobe error output was provided."  # Preserve diagnostic stderr when available.
        raise RuntimeError(f"FFprobe could not {context}: {details}") from error  # Raise the contextualized probe failure.
    except OSError as error:  # Convert executable launch failures to runtime errors.
        raise RuntimeError(f"FFprobe could not be started while attempting to {context}: {error}") from error  # Preserve launch details.


def get_audio_track_count(mkv_path: Path) -> int:  # Define the get_audio_track_count operation.
    """
    Count audio streams in one MKV file through FFprobe.

    :param mkv_path: MKV file whose audio streams will be counted.
    :return: Number of audio streams found.
    """

    command = [  # Build the FFprobe audio-stream query.
        "ffprobe",  # Select the FFprobe executable.
        "-v",  # Configure FFprobe output verbosity.
        "error",  # Emit errors only.
        "-select_streams",  # Restrict output to selected stream types.
        "a",  # Select every audio stream.
        "-show_entries",  # Restrict returned stream fields.
        "stream=index",  # Return each selected stream index.
        "-of",  # Configure the output format.
        "csv=p=0",  # Emit one index per line without a header.
        str(mkv_path),  # Pass the MKV input path.
    ]
    result = run_ffprobe(command, f"inspect audio tracks in {mkv_path}")  # Execute the audio-stream query.

    return sum(1 for line in result.stdout.splitlines() if line.strip())  # Count nonempty stream-index lines.


def validate_audio_track_index(mkv_path: Path, audio_index: int) -> None:  # Define the validate_audio_track_index operation.
    """
    Validate a zero-based audio-track index against one MKV file.

    :param mkv_path: MKV file containing the requested audio track.
    :param audio_index: Zero-based index among audio streams.
    :return: None.
    """

    audio_track_count = get_audio_track_count(mkv_path)  # Count available audio streams.

    if audio_track_count == 0:  # Detect an MKV file without audio streams.
        raise ValueError(f"No audio tracks were found in the MKV file: {mkv_path}")  # Reject the unusable media file.

    if audio_index >= audio_track_count:  # Detect an index beyond the final audio stream.
        raise IndexError(  # Report the complete valid index range.
            f"Audio-track index {audio_index} does not exist in {mkv_path}. "  # Identify the rejected index and file.
            f"The file has {audio_track_count} audio track(s), so the valid "  # Include the audio-stream count.
            f"indexes are 0 through {audio_track_count - 1}."  # Include the valid zero-based range.
        )


def get_subtitle_tracks(mkv_path: Path) -> list[SubtitleTrack]:  # Define the get_subtitle_tracks operation.
    """
    Read subtitle stream indexes, codecs, and languages from one MKV file.

    :param mkv_path: MKV file whose subtitle streams will be inspected.
    :return: Ordered subtitle stream metadata tuples.
    """

    command = [  # Build the FFprobe subtitle metadata query.
        "ffprobe",  # Select the FFprobe executable.
        "-v",  # Configure FFprobe output verbosity.
        "error",  # Emit errors only.
        "-select_streams",  # Restrict output to selected stream types.
        "s",  # Select every subtitle stream.
        "-show_entries",  # Restrict returned stream fields.
        "stream=codec_name:stream_tags=language,title",  # Return codec and language metadata.
        "-of",  # Configure the output format.
        "json",  # Emit structured JSON.
        str(mkv_path),  # Pass the MKV input path.
    ]
    result = run_ffprobe(command, f"inspect subtitle tracks in {mkv_path}")  # Execute the subtitle metadata query.

    try:  # Parse FFprobe JSON output.
        probe_data: Any = json.loads(result.stdout)  # Decode the captured JSON document.
    except json.JSONDecodeError as error:  # Convert malformed FFprobe JSON to a runtime error.
        raise RuntimeError(  # Report the invalid FFprobe response.
            f"FFprobe returned invalid JSON while inspecting {mkv_path}."  # Identify the affected MKV file.
        ) from error

    if not isinstance(probe_data, dict):  # Validate the expected top-level JSON object.
        raise RuntimeError(f"FFprobe returned an invalid subtitle metadata structure for {mkv_path}.")  # Reject unexpected JSON shapes.

    streams_value = probe_data.get("streams", [])  # Read the subtitle stream collection.

    if not isinstance(streams_value, list):  # Validate the expected stream list.
        raise RuntimeError(f"FFprobe returned an invalid subtitle stream list for {mkv_path}.")  # Reject malformed stream metadata.

    tracks: list[SubtitleTrack] = []  # Initialize ordered subtitle metadata results.

    for subtitle_index, stream_value in enumerate(streams_value):  # Enumerate subtitle streams by subtitle-relative index.
        if not isinstance(stream_value, dict):  # Validate the expected stream object.
            raise RuntimeError(f"FFprobe returned an invalid subtitle stream entry for {mkv_path}.")  # Reject malformed stream entries.

        tags_value = stream_value.get("tags")  # Read optional subtitle tags.
        tags = tags_value if isinstance(tags_value, dict) else {}  # Use an empty tag mapping when metadata is absent.
        codec_name = str(stream_value.get("codec_name") or "unknown").casefold()  # Normalize the subtitle codec name.
        language = get_subtitle_language_name(  # Resolve a stable language display name.
            language_tag=str(tags.get("language") or "und"),  # Pass the language tag or undefined fallback.
            title=str(tags.get("title") or ""),  # Pass the optional subtitle title.
        )
        tracks.append((subtitle_index, codec_name, language))  # Preserve the subtitle-relative index and metadata.

    return tracks  # Return all discovered subtitle streams in source order.


def get_subtitle_language_name(language_tag: str, title: str) -> str:  # Define the get_subtitle_language_name operation.
    """
    Resolve a subtitle display language from its metadata tag and title.

    :param language_tag: Raw subtitle language tag.
    :param title: Raw subtitle title metadata.
    :return: Normalized language display name.
    """

    normalized_tag = language_tag.strip().lower().replace("_", "-")  # Normalize tag spacing, case, and separators.
    normalized_title = title.strip().lower()  # Normalize title spacing and case.

    if any(value in normalized_title for value in ("brazil", "brasil")):  # Detect Brazilian Portuguese title metadata.
        return "PT-BR"  # Return the Brazilian Portuguese display name.

    if any(  # Detect European Portuguese title metadata.
        value in normalized_title  # Compare one recognized title fragment.
        for value in ("portugal", "european portuguese", "português europeu")  # Inspect recognized European Portuguese markers.
    ):
        return "PT-PT"  # Return the European Portuguese display name.

    if normalized_tag in {"pt-pt", "por-pt"}:  # Detect explicit European Portuguese tags.
        return "PT-PT"  # Return the European Portuguese display name.

    mapped_name = LANGUAGE_NAMES.get(normalized_tag)  # Resolve a known language-tag mapping.

    if mapped_name is not None:  # Detect a recognized language tag.
        return mapped_name  # Return the mapped display name.

    if normalized_tag and normalized_tag != "und":  # Preserve unknown but defined language tags.
        return normalized_tag.upper()  # Return the normalized tag in uppercase form.

    if title.strip():  # Use title metadata when no usable language tag exists.
        return title.strip()  # Return the original title without surrounding whitespace.

    return "Unknown"  # Return the deterministic language fallback.


def sanitize_filename_component(value: str) -> str:  # Define the sanitize_filename_component operation.
    """
    Sanitize one value for safe use inside a filename.

    :param value: Raw filename component.
    :return: Filesystem-safe nonempty filename component.
    """

    sanitized = re.sub("[<>:\"/\\\\|?*\\x00-\\x1f]", "-", value)  # Replace reserved characters and control bytes.
    sanitized = re.sub(r"\s+", " ", sanitized).strip(" .-")  # Collapse whitespace and trim unsafe boundary characters.

    return sanitized or "Unknown"  # Return a deterministic fallback for an empty result.


def get_subtitle_output_configuration(mkv_path: Path, subtitle_index: int, codec_name: str, language: str) -> tuple[Path, list[str]]:  # Define the get_subtitle_output_configuration operation.
    """
    Resolve the output path and FFmpeg codec arguments for one subtitle stream.

    :param mkv_path: Source MKV path.
    :param subtitle_index: Zero-based index among subtitle streams.
    :param codec_name: Normalized FFprobe subtitle codec name.
    :param language: Normalized subtitle language display name.
    :return: Subtitle output path and FFmpeg codec arguments.
    """

    filename_prefix = f"{subtitle_index}-{sanitize_filename_component(language)}"  # Build the stable subtitle filename prefix.

    if codec_name == "hdmv_pgs_subtitle":  # Detect Blu-ray PGS image subtitles.
        return (  # Return raw SUP extraction configuration.
            mkv_path.parent / f"{filename_prefix}.sup",  # Place the SUP file beside the source MKV.
            ["-c:s", "copy", "-f", "sup"],  # Copy the PGS stream into the SUP muxer.
        )

    if codec_name in TEXT_SUBTITLE_CODECS:  # Detect subtitle codecs that support text conversion.
        return (  # Return SRT conversion configuration.
            mkv_path.parent / f"{filename_prefix}.srt",  # Place the SRT file beside the source MKV.
            ["-c:s", "srt"],  # Convert the selected subtitle stream to SubRip.
        )

    return (  # Return lossless Matroska subtitle configuration for other codecs.
        mkv_path.parent / f"{filename_prefix}.mks",  # Place the subtitle-only Matroska file beside the source MKV.
        ["-c:s", "copy"],  # Copy the selected subtitle codec without text conversion.
    )


def get_path_identity(path: Path) -> str:  # Define the get_path_identity operation.
    """
    Build a platform-normalized identity for output-path collision detection.

    :param path: Filesystem path to normalize.
    :return: Normalized absolute path identity.
    """

    return os.path.normcase(str(path.resolve()))  # Normalize absolute path case according to the active platform.


def reserve_subtitle_output_path(output_path: Path, mkv_path: Path, occupied_paths: set[str]) -> Path:  # Define the reserve_subtitle_output_path operation.
    """
    Reserve a unique subtitle output path across concurrently submitted tasks.

    :param output_path: Preferred subtitle output path.
    :param mkv_path: Source MKV used to disambiguate collisions.
    :param occupied_paths: Mutable set of already reserved path identities.
    :return: Reserved collision-free subtitle output path.
    """

    preferred_identity = get_path_identity(output_path)  # Normalize the preferred output path.

    if preferred_identity not in occupied_paths:  # Preserve the established filename when no collision exists.
        occupied_paths.add(preferred_identity)  # Reserve the preferred output path.

        return output_path  # Return the unchanged preferred output path.

    source_prefix = sanitize_filename_component(mkv_path.stem)  # Build a source-specific collision prefix.
    candidate = output_path.with_name(f"{source_prefix}-{output_path.name}")  # Build the first disambiguated filename.
    sequence = 2  # Initialize a numeric suffix for repeated collisions.

    while get_path_identity(candidate) in occupied_paths:  # Continue until a unique path identity is found.
        candidate = output_path.with_name(  # Build the next source-specific candidate filename.
            f"{source_prefix}-{sequence}-{output_path.name}"  # Add the current numeric collision suffix.
        )
        sequence += 1  # Advance the collision suffix for another iteration.

    occupied_paths.add(get_path_identity(candidate))  # Reserve the disambiguated output path.
    print(  # Report the path adjustment caused by a proven collision.
        f"Subtitle output collision resolved for {mkv_path.name}: "  # Identify the affected source MKV.
        f"{candidate.name}"  # Include the selected collision-free filename.
    )

    return candidate  # Return the reserved collision-free output path.


def build_subtitle_specifications(subtitle_sources: list[Path]) -> list[SubtitleSpecification]:  # Define the build_subtitle_specifications operation.
    """
    Build collision-free subtitle extraction specifications for all source MKVs.

    :param subtitle_sources: Ordered MKV files whose subtitle streams will be extracted.
    :return: Ordered subtitle extraction specifications.
    """

    subtitle_specifications: list[SubtitleSpecification] = []  # Initialize all subtitle extraction tasks.
    occupied_paths: set[str] = set()  # Track output paths reserved by earlier tasks.

    for mkv_path in subtitle_sources:  # Inspect subtitle metadata for each source MKV.
        tracks = get_subtitle_tracks(mkv_path)  # Read subtitle indexes, codecs, and languages.

        if not tracks:  # Detect a source MKV without subtitle streams.
            print(f"No subtitle tracks found in {mkv_path.name}.")  # Report the absence of subtitles.
            continue  # Continue with the next source MKV.

        for subtitle_index, codec_name, language in tracks:  # Build one extraction task per subtitle stream.
            preferred_output_path, codec_arguments = get_subtitle_output_configuration(  # Resolve codec-aware output settings.
                mkv_path=mkv_path,  # Pass the subtitle source MKV.
                subtitle_index=subtitle_index,  # Pass the subtitle-relative stream index.
                codec_name=codec_name,  # Pass the normalized subtitle codec.
                language=language,  # Pass the normalized subtitle language.
            )
            reserved_output_path = reserve_subtitle_output_path(  # Prevent concurrent tasks from sharing an output file.
                output_path=preferred_output_path,  # Pass the established preferred output path.
                mkv_path=mkv_path,  # Pass the source MKV for collision disambiguation.
                occupied_paths=occupied_paths,  # Pass the shared reserved-path collection.
            )
            subtitle_specifications.append(  # Preserve the complete extraction task arguments.
                (  # Build one immutable subtitle task tuple.
                    mkv_path,  # Store the source MKV path.
                    subtitle_index,  # Store the subtitle-relative stream index.
                    codec_name,  # Store the normalized subtitle codec.
                    language,  # Store the normalized subtitle language.
                    reserved_output_path,  # Store the collision-free output path.
                    codec_arguments,  # Store the codec-specific FFmpeg arguments.
                )
            )

    return subtitle_specifications  # Return all planned subtitle extraction tasks.


def create_temporary_output_path(output_path: Path) -> Path:  # Define the create_temporary_output_path operation.
    """
    Create a unique temporary path that preserves the final media extension.

    :param output_path: Final output path.
    :return: Unique temporary path in the same directory.
    """

    unique_token = uuid.uuid4().hex  # Generate a collision-resistant temporary filename token.

    return output_path.with_name(  # Place the temporary file beside the final output.
        f".{output_path.stem}.{unique_token}.partial{output_path.suffix}"  # Preserve the final extension for FFmpeg format detection.
    )


def remove_file_if_present(path: Path) -> None:  # Define the remove_file_if_present operation.
    """
    Remove one file when it exists.

    :param path: File path to remove.
    :return: None.
    """

    try:  # Attempt cleanup without masking the primary workflow failure.
        if path.exists():  # Detect an existing file or filesystem entry.
            path.unlink()  # Remove the existing path.
    except OSError as error:  # Report cleanup failures without replacing the primary exception.
        print(f"Warning: unable to remove temporary file {path}: {error}")  # Preserve the cleanup diagnostic.


def finalize_output_file(temporary_path: Path, output_path: Path, description: str) -> None:  # Define the finalize_output_file operation.
    """
    Validate a temporary media output and atomically replace its final path.

    :param temporary_path: Temporary output generated by FFmpeg or file copying.
    :param output_path: Final destination path.
    :param description: Human-readable output description used in failures.
    :return: None.
    """

    if not temporary_path.is_file() or temporary_path.stat().st_size == 0:  # Validate the temporary output file and size.
        remove_file_if_present(temporary_path)  # Remove an invalid temporary output.
        raise RuntimeError(f"The operation did not generate a valid {description}: {output_path}")  # Report the invalid output.

    try:  # Replace the final output only after temporary-file validation.
        temporary_path.replace(output_path)  # Atomically replace the final path on the same filesystem.
    except OSError:  # Clean the temporary file when final replacement fails.
        remove_file_if_present(temporary_path)  # Remove the uncommitted temporary output.
        raise  # Preserve the original filesystem replacement failure.

    if not output_path.is_file() or output_path.stat().st_size == 0:  # Validate the committed final output.
        remove_file_if_present(output_path)  # Remove an invalid committed output.
        raise RuntimeError(f"The operation did not commit a valid {description}: {output_path}")  # Report the invalid final file.


def extract_subtitle_track(  # Define the extract_subtitle_track operation.
    mkv_path: Path,
    subtitle_index: int,
    codec_name: str,
    language: str,
    output_path: Path,
    codec_arguments: list[str],
) -> SubtitleResult:
    """
    Extract one subtitle stream with codec-aware output handling.

    :param mkv_path: Source MKV path.
    :param subtitle_index: Zero-based index among subtitle streams.
    :param codec_name: Normalized subtitle codec name.
    :param language: Normalized subtitle language display name.
    :param output_path: Final subtitle output path.
    :param codec_arguments: FFmpeg codec and muxer arguments.
    :return: Extracted path and no warning, or no path and a warning message.
    """

    print(  # Report the subtitle extraction task.
        f"Extracting subtitle track {subtitle_index} "  # Include the subtitle-relative stream index.
        f"({language}, {codec_name}) from {mkv_path.name} "  # Include language, codec, and source filename.
        f"to {output_path}..."  # Include the final destination path.
    )
    temporary_path = create_temporary_output_path(output_path)  # Allocate an isolated temporary subtitle path.
    command = [  # Build the FFmpeg subtitle extraction command.
        "ffmpeg",  # Select the FFmpeg executable.
        "-hide_banner",  # Suppress the FFmpeg build banner.
        "-nostdin",  # Prevent FFmpeg from reading interactive input.
        "-y",  # Allow replacement of the unique temporary path.
        "-i",  # Introduce the input media path.
        str(mkv_path),  # Pass the source MKV path.
        "-map",  # Select one source stream.
        f"0:s:{subtitle_index}",  # Select the subtitle-relative stream index.
        "-vn",  # Disable video output.
        "-an",  # Disable audio output.
        "-dn",  # Disable data-stream output.
        "-map_metadata",  # Configure metadata mapping.
        "-1",  # Remove inherited container metadata.
        "-map_chapters",  # Configure chapter mapping.
        "-1",  # Remove inherited chapters.
        *codec_arguments,  # Apply codec-specific subtitle output arguments.
        str(temporary_path),  # Write to the isolated temporary path.
    ]

    try:  # Extract and validate the selected subtitle stream.
        run_ffmpeg(command)  # Execute the subtitle extraction command.
        finalize_output_file(temporary_path, output_path, "subtitle file")  # Commit the validated subtitle output.
    except Exception as error:  # Convert one subtitle failure into a nonfatal warning result.
        remove_file_if_present(temporary_path)  # Remove any temporary subtitle residue.
        warning = (  # Build the complete subtitle extraction warning.
            f"Subtitle track {subtitle_index} ({language}, {codec_name}) in "  # Identify the failed subtitle stream.
            f"{mkv_path.name} could not be extracted: {error}"  # Include the source filename and failure reason.
        )
        print(f"Warning: {warning}")  # Report the nonfatal subtitle extraction warning.

        return None, warning  # Return the warning without an output path.

    print(f"Subtitle extracted: {output_path}")  # Report the committed subtitle output.

    return output_path, None  # Return the extracted path without a warning.


def extract_audio_track(mkv_path: Path, audio_index: int, output_path: Path) -> None:  # Define the extract_audio_track operation.
    """
    Extract one zero-based MKV audio stream to a high-quality MP3 file.

    :param mkv_path: Source MKV path.
    :param audio_index: Zero-based index among audio streams.
    :param output_path: Final MP3 output path.
    :return: None.
    """

    print(  # Report the audio extraction task.
        f"Extracting audio track {audio_index} from {mkv_path.name} "  # Include the audio-relative stream index and source filename.
        f"to {output_path}..."  # Include the final destination path.
    )
    temporary_path = create_temporary_output_path(output_path)  # Allocate an isolated temporary MP3 path.
    command = [  # Build the FFmpeg audio extraction command.
        "ffmpeg",  # Select the FFmpeg executable.
        "-hide_banner",  # Suppress the FFmpeg build banner.
        "-nostdin",  # Prevent FFmpeg from reading interactive input.
        "-y",  # Allow replacement of the unique temporary path.
        "-i",  # Introduce the input media path.
        str(mkv_path),  # Pass the source MKV path.
        "-map",  # Select one source stream.
        f"0:a:{audio_index}",  # Select the audio-relative stream index.
        "-vn",  # Disable video output.
        "-sn",  # Disable subtitle output.
        "-dn",  # Disable data-stream output.
        "-map_metadata",  # Configure metadata mapping.
        "-1",  # Remove inherited container metadata.
        "-map_chapters",  # Configure chapter mapping.
        "-1",  # Remove inherited chapters.
        "-c:a",  # Configure the audio encoder.
        "libmp3lame",  # Encode the selected stream as MP3.
        "-q:a",  # Configure variable bitrate quality.
        "0",  # Select the highest LAME variable bitrate quality.
        str(temporary_path),  # Write to the isolated temporary MP3 path.
    ]

    try:  # Extract and validate the selected audio stream.
        run_ffmpeg(command)  # Execute the audio extraction command.
        finalize_output_file(temporary_path, output_path, "audio file")  # Commit the validated MP3 output.
    except Exception:  # Clean temporary output before preserving the original failure.
        remove_file_if_present(temporary_path)  # Remove any temporary MP3 residue.
        raise  # Re-raise the original extraction or validation failure.


def load_audio_for_analysis(audio_path: Path) -> AudioArray:  # Define the load_audio_for_analysis operation.
    """
    Load, center, and peak-normalize one MP3 waveform for offset analysis.

    :param audio_path: MP3 path to decode and normalize.
    :return: Mono float32 waveform sampled at SAMPLE_RATE.
    """

    audio, loaded_sample_rate = librosa.load(  # Decode and resample the requested analysis segment.
        audio_path,  # Pass the extracted MP3 path.
        sr=SAMPLE_RATE,  # Resample audio to the configured analysis rate.
        mono=True,  # Downmix all channels to one waveform.
        duration=ANALYSIS_DURATION_SECONDS,  # Limit analysis to the configured duration.
    )
    audio = np.asarray(audio, dtype=np.float32)  # Normalize the decoded waveform dtype.

    if loaded_sample_rate != SAMPLE_RATE:  # Validate the sample rate returned by librosa.
        raise RuntimeError(  # Reject an unexpected decoder sample rate.
            f"librosa returned {loaded_sample_rate} Hz instead of {SAMPLE_RATE} Hz for {audio_path}."  # Include both rates and the source path.
        )

    if audio.size == 0:  # Detect an empty decoded waveform.
        raise ValueError(f"No audio data could be read from: {audio_path}")  # Reject unusable audio input.

    audio = np.asarray(audio - np.mean(audio), dtype=np.float32)  # Remove the waveform direct-current component.
    peak = float(np.max(np.abs(audio)))  # Calculate the absolute waveform peak.

    if peak > 0:  # Avoid division when the waveform contains only silence.
        audio = np.asarray(audio / peak, dtype=np.float32)  # Normalize the waveform peak to one.

    return audio  # Return the normalized analysis waveform.


def calculate_offset_seconds(reference_path: Path, target_path: Path) -> float:  # Define the calculate_offset_seconds operation.
    """
    Calculate the target-audio offset relative to the reference waveform.

    :param reference_path: Extracted reference MP3 path.
    :param target_path: Extracted target MP3 path.
    :return: Signed offset in seconds; positive values require target trimming.
    """

    print(f"Loading reference audio: {reference_path}")  # Report reference waveform loading.
    reference_audio = load_audio_for_analysis(reference_path)  # Decode and normalize the reference waveform.
    print(f"Loading audio to syncronize: {target_path}")  # Report target waveform loading.
    target_audio = load_audio_for_analysis(target_path)  # Decode and normalize the target waveform.
    print("Calculating audio correlation...")  # Report the correlation operation.
    correlation = correlate(  # Calculate full cross-correlation through the FFT implementation.
        reference_audio,  # Pass the reference waveform as the first signal.
        target_audio,  # Pass the target waveform as the second signal.
        mode="full",  # Evaluate every relative alignment.
        method="fft",  # Use FFT convolution for long waveforms.
    )
    lags = correlation_lags(  # Build lag values corresponding to the correlation array.
        reference_audio.size,  # Pass the reference waveform length.
        target_audio.size,  # Pass the target waveform length.
        mode="full",  # Match the full correlation mode.
    )
    best_lag_samples = int(lags[int(np.argmax(np.abs(correlation)))])  # Select the lag with maximum absolute correlation.

    return -best_lag_samples / SAMPLE_RATE  # Convert lag samples to the target correction offset in seconds.


def synchronize_audio(target_path: Path, offset_seconds: float, output_path: Path) -> None:  # Define the synchronize_audio operation.
    """
    Trim or delay the target MP3 according to the detected offset.

    :param target_path: Extracted target MP3 path.
    :param offset_seconds: Signed target correction offset in seconds.
    :param output_path: Final synchronized MP3 path.
    :return: None.
    """

    audio_filter: str | None = None  # Initialize the optional FFmpeg audio filter.

    if abs(offset_seconds) < MINIMUM_OFFSET_SECONDS:  # Detect an offset below the configured correction threshold.
        print("No meaningful offset was detected; re-encoding the target audio.")  # Report threshold-based re-encoding.
    elif offset_seconds > 0:  # Detect target content that occurs later than the reference content.
        print(  # Report the target trimming operation.
            f"Target content occurs {offset_seconds:.6f} seconds later. "  # Include the detected positive offset.
            "Trimming the beginning of the target audio."  # Explain the required correction.
        )
        audio_filter = (  # Build the target trimming and timestamp reset filter.
            f"atrim=start={offset_seconds:.6f},"  # Trim the delayed beginning of the target waveform.
            "asetpts=PTS-STARTPTS"  # Reset output timestamps to start at zero.
        )
    else:  # Detect target content that occurs earlier than the reference content.
        delay_milliseconds = round(abs(offset_seconds) * 1_000)  # Convert the required silence duration to milliseconds.
        print(  # Report the target delay operation.
            f"Target content occurs {abs(offset_seconds):.6f} seconds earlier. "  # Include the detected negative offset magnitude.
            f"Adding {delay_milliseconds} ms of silence."  # Explain the required correction.
        )
        audio_filter = f"adelay={delay_milliseconds}:all=1"  # Delay every audio channel by the required duration.

    temporary_path = create_temporary_output_path(output_path)  # Allocate an isolated temporary synchronized MP3 path.
    command = [  # Build the base FFmpeg synchronization command.
        "ffmpeg",  # Select the FFmpeg executable.
        "-hide_banner",  # Suppress the FFmpeg build banner.
        "-nostdin",  # Prevent FFmpeg from reading interactive input.
        "-y",  # Allow replacement of the unique temporary path.
        "-i",  # Introduce the input audio path.
        str(target_path),  # Pass the extracted target MP3 path.
        "-map",  # Select one source stream.
        "0:a:0",  # Select the only audio stream in the extracted target MP3.
        "-vn",  # Disable video output.
        "-sn",  # Disable subtitle output.
        "-dn",  # Disable data-stream output.
    ]

    if audio_filter is not None:  # Apply a correction filter only when a meaningful offset exists.
        command.extend(["-af", audio_filter])  # Append the calculated trim or delay filter.

    command.extend(  # Append output metadata and encoding arguments.
        [  # Define the final FFmpeg synchronization arguments.
            "-map_metadata",  # Configure metadata mapping.
            "-1",  # Remove inherited metadata.
            "-map_chapters",  # Configure chapter mapping.
            "-1",  # Remove inherited chapters.
            "-c:a",  # Configure the audio encoder.
            "libmp3lame",  # Encode synchronized audio as MP3.
            "-q:a",  # Configure variable bitrate quality.
            "0",  # Select the highest LAME variable bitrate quality.
            str(temporary_path),  # Write to the isolated temporary synchronized path.
        ]
    )

    try:  # Generate and validate the synchronized MP3 output.
        run_ffmpeg(command)  # Execute the synchronization command.
        finalize_output_file(temporary_path, output_path, "syncronized audio file")  # Commit the validated synchronized MP3.
    except Exception:  # Clean temporary output before preserving the original failure.
        remove_file_if_present(temporary_path)  # Remove any temporary synchronized MP3 residue.
        raise  # Re-raise the original synchronization or validation failure.


def copy_synchronized_audio(output_path: Path, reference_mkv_path: Path) -> Path:  # Define the copy_synchronized_audio operation.
    """
    Copy the synchronized MP3 beside the reference MKV when directories differ.

    :param output_path: Synchronized MP3 beside the target MKV.
    :param reference_mkv_path: Reference MKV used to resolve the second destination.
    :return: Validated synchronized MP3 path beside the reference MKV.
    """

    reference_output_path = reference_mkv_path.parent / SYNCRONIZED_AUDIO_FILENAME  # Resolve the reference-directory destination.

    if reference_output_path == output_path:  # Detect sources that share one directory.
        if not output_path.is_file() or output_path.stat().st_size == 0:  # Validate the shared synchronized MP3.
            raise RuntimeError(f"The synchronized audio is invalid: {output_path}")  # Reject a missing or empty shared output.

        return output_path  # Return the existing shared synchronized MP3 path.

    temporary_path = create_temporary_output_path(reference_output_path)  # Allocate an isolated temporary copy path.

    try:  # Copy and validate the synchronized MP3 in the reference directory.
        shutil.copy2(output_path, temporary_path)  # Copy file data and metadata to the temporary path.
        finalize_output_file(temporary_path, reference_output_path, "syncronized audio copy")  # Commit the validated reference copy.
    except Exception:  # Clean temporary copy output before preserving the original failure.
        remove_file_if_present(temporary_path)  # Remove any temporary reference-copy residue.
        raise  # Re-raise the original copy or validation failure.

    return reference_output_path  # Return the committed reference-directory copy path.


def execute_media_workflow(  # Define the execute_media_workflow operation.
    reference_mkv_path: Path,
    reference_audio_index: int,
    target_mkv_path: Path,
    target_audio_index: int,
    reference_audio_path: Path,
    target_audio_path: Path,
    output_path: Path,
    subtitle_specifications: list[SubtitleSpecification],
) -> tuple[float, list[SubtitleResult]]:
    """
    Execute parallel extraction, offset analysis, and target synchronization.

    :param reference_mkv_path: Resolved reference MKV path.
    :param reference_audio_index: Zero-based reference audio index.
    :param target_mkv_path: Resolved target MKV path.
    :param target_audio_index: Zero-based target audio index.
    :param reference_audio_path: Final extracted reference MP3 path.
    :param target_audio_path: Final extracted target MP3 path.
    :param output_path: Final synchronized MP3 path beside the target MKV.
    :param subtitle_specifications: Planned subtitle extraction task arguments.
    :return: Detected offset and completed subtitle extraction results.
    """

    total_extraction_tasks = 2 + len(subtitle_specifications)  # Count audio and subtitle extraction tasks.
    print(  # Report the complete parallel extraction plan.
        f"Starting {total_extraction_tasks} extraction task(s) in parallel: "  # Include the total task count.
        f"2 audio track(s) and {len(subtitle_specifications)} subtitle track(s)."  # Include audio and subtitle task counts.
    )
    subtitle_futures: list[Future[SubtitleResult]] = []  # Initialize submitted subtitle task futures.

    with ThreadPoolExecutor(  # Create the shared extraction worker pool.
        max_workers=total_extraction_tasks,  # Allow every planned extraction task to begin without queueing.
        thread_name_prefix="media-extraction",  # Assign recognizable worker thread names.
    ) as executor:
        reference_audio_future: Future[None] = executor.submit(  # Submit reference audio extraction.
            extract_audio_track,  # Execute the audio extraction function.
            reference_mkv_path,  # Pass the reference MKV path.
            reference_audio_index,  # Pass the reference audio index.
            reference_audio_path,  # Pass the reference MP3 destination.
        )
        target_audio_future: Future[None] = executor.submit(  # Submit target audio extraction.
            extract_audio_track,  # Execute the audio extraction function.
            target_mkv_path,  # Pass the target MKV path.
            target_audio_index,  # Pass the target audio index.
            target_audio_path,  # Pass the target MP3 destination.
        )

        for subtitle_specification in subtitle_specifications:  # Submit every subtitle extraction task.
            subtitle_future = executor.submit(  # Submit one codec-aware subtitle extraction.
                extract_subtitle_track,  # Execute the subtitle extraction function.
                *subtitle_specification,  # Pass the complete planned task arguments.
            )
            subtitle_futures.append(subtitle_future)  # Preserve the submitted subtitle future.

        reference_audio_future.result()  # Wait for the required reference MP3 extraction.
        target_audio_future.result()  # Wait for the required target MP3 extraction.
        offset_seconds = calculate_offset_seconds(  # Calculate the signed target correction offset.
            reference_path=reference_audio_path,  # Pass the extracted reference MP3.
            target_path=target_audio_path,  # Pass the extracted target MP3.
        )
        print(f"Detected offset: {offset_seconds:+.6f} seconds")  # Report the signed detected offset.
        synchronize_audio(  # Generate the corrected target MP3 while subtitle tasks continue.
            target_path=target_audio_path,  # Pass the extracted target MP3.
            offset_seconds=offset_seconds,  # Pass the detected correction offset.
            output_path=output_path,  # Pass the synchronized MP3 destination.
        )
        subtitle_results = [  # Collect every subtitle result before closing the executor.
            subtitle_future.result()  # Wait for and preserve one subtitle extraction result.
            for subtitle_future in subtitle_futures  # Iterate through submitted subtitle futures in source order.
        ]

    return offset_seconds, subtitle_results  # Return the detected offset and subtitle outcomes.


def display_completion_summary(  # Define the display_completion_summary operation.
    reference_audio_path: Path,
    target_audio_path: Path,
    output_path: Path,
    reference_output_path: Path,
    subtitle_results: list[SubtitleResult],
) -> None:
    """
    Display generated media paths and subtitle extraction totals.

    :param reference_audio_path: Extracted reference MP3 path.
    :param target_audio_path: Extracted target MP3 path.
    :param output_path: Synchronized MP3 path beside the target MKV.
    :param reference_output_path: Synchronized MP3 path beside the reference MKV.
    :param subtitle_results: Completed subtitle extraction outcomes.
    :return: None.
    """

    extracted_subtitles = [  # Collect successful subtitle output paths.
        path  # Preserve one successful subtitle path.
        for path, warning in subtitle_results  # Inspect each subtitle path and warning pair.
        if path is not None and warning is None  # Retain only successful extraction outcomes.
    ]
    subtitle_warnings = [  # Collect nonfatal subtitle warning messages.
        warning  # Preserve one warning message.
        for path, warning in subtitle_results  # Inspect each subtitle path and warning pair.
        if path is None and warning is not None  # Retain only failed extraction outcomes.
    ]
    print("\nCompleted successfully.")  # Report successful completion of the required audio workflow.
    print(f"Reference audio:       {reference_audio_path}")  # Report the extracted reference MP3 path.
    print(f"Audio to syncronize:   {target_audio_path}")  # Report the extracted target MP3 path.
    print(f"Syncronized audio:     {output_path}")  # Report the target-directory synchronized MP3 path.
    print(f"Reference copy:        {reference_output_path}")  # Report the reference-directory synchronized MP3 path.
    print(f"Subtitles extracted:   {len(extracted_subtitles)}")  # Report the successful subtitle count.

    if subtitle_warnings:  # Detect one or more nonfatal subtitle extraction failures.
        print(f"Subtitle warnings:     {len(subtitle_warnings)}")  # Report the nonfatal subtitle warning count.


def main() -> None:  # Define the main operation.
    """
    Execute the complete audio-track offset synchronization workflow.

    :return: None.
    """

    print(  # Display the template-style program banner.
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}"  # Clear the terminal and enable bold formatting.
        f"{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}"  # Add the welcome-message prefix.
        f"Audio Track Offset Syncronization{BackgroundColors.GREEN} program!"  # Add the project title and suffix.
        f"{BackgroundColors.RESET}",  # Reset terminal formatting.
        end="\n\n",  # Separate the banner from workflow output.
    )
    start_time = datetime.datetime.now()  # Capture the program start timestamp.
    validate_dependencies()  # Validate required FFmpeg executables before media inspection.
    reference_mkv_path, reference_audio_index = resolve_file_configuration(  # Resolve reference media configuration.
        REFERENCE_FILE,  # Pass the reference path and audio-index mapping.
        "REFERENCE_FILE",  # Pass the reference configuration display name.
    )
    target_mkv_path, target_audio_index = resolve_file_configuration(  # Resolve target media configuration.
        TO_SYNCRONIZE_FILE,  # Pass the target path and audio-index mapping.
        "TO_SYNCRONIZE_FILE",  # Pass the target configuration display name.
    )

    if reference_mkv_path == target_mkv_path and reference_audio_index == target_audio_index:  # Detect identical source and audio selection.
        raise ValueError(  # Reject a workflow without distinct audio inputs.
            "REFERENCE_FILE and TO_SYNCRONIZE_FILE point to the same MKV "  # Identify the duplicate media configuration.
            "and the same audio-track index."  # Identify the duplicate audio selection.
        )

    validate_audio_track_index(reference_mkv_path, reference_audio_index)  # Validate the reference audio selection.
    validate_audio_track_index(target_mkv_path, target_audio_index)  # Validate the target audio selection.
    reference_audio_path = reference_mkv_path.parent / REFERENCE_AUDIO_FILENAME  # Resolve the reference MP3 destination.
    target_audio_path = target_mkv_path.parent / TO_SYNCRONIZE_AUDIO_FILENAME  # Resolve the target MP3 destination.
    output_path = target_mkv_path.parent / SYNCRONIZED_AUDIO_FILENAME  # Resolve the target synchronized MP3 destination.
    subtitle_sources = [reference_mkv_path]  # Initialize subtitle sources with the reference MKV.

    if target_mkv_path != reference_mkv_path:  # Avoid extracting one MKV subtitle set twice.
        subtitle_sources.append(target_mkv_path)  # Add the distinct target MKV as a subtitle source.

    subtitle_specifications = build_subtitle_specifications(subtitle_sources)  # Plan codec-aware collision-free subtitle tasks.
    detected_offset, subtitle_results = execute_media_workflow(  # Execute extraction, analysis, and synchronization.
        reference_mkv_path=reference_mkv_path,  # Pass the resolved reference MKV path.
        reference_audio_index=reference_audio_index,  # Pass the validated reference audio index.
        target_mkv_path=target_mkv_path,  # Pass the resolved target MKV path.
        target_audio_index=target_audio_index,  # Pass the validated target audio index.
        reference_audio_path=reference_audio_path,  # Pass the reference MP3 destination.
        target_audio_path=target_audio_path,  # Pass the target MP3 destination.
        output_path=output_path,  # Pass the target synchronized MP3 destination.
        subtitle_specifications=subtitle_specifications,  # Pass every planned subtitle extraction task.
    )
    reference_output_path = copy_synchronized_audio(  # Create or validate the reference-directory synchronized copy.
        output_path=output_path,  # Pass the target-directory synchronized MP3.
        reference_mkv_path=reference_mkv_path,  # Pass the reference MKV used to resolve the second destination.
    )
    display_completion_summary(  # Display all generated paths and subtitle totals.
        reference_audio_path=reference_audio_path,  # Pass the extracted reference MP3 path.
        target_audio_path=target_audio_path,  # Pass the extracted target MP3 path.
        output_path=output_path,  # Pass the target synchronized MP3 path.
        reference_output_path=reference_output_path,  # Pass the reference synchronized MP3 path.
        subtitle_results=subtitle_results,  # Pass completed subtitle outcomes.
    )
    print(f"Detected correction:   {detected_offset:+.6f} seconds")  # Repeat the final signed correction in the summary.
    finish_time = datetime.datetime.now()  # Capture the successful program finish timestamp.
    print(  # Display template-style execution timing.
        f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}"  # Add the start-time label.
        f"{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n"  # Add the formatted start timestamp.
        f"{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}"  # Add the finish-time label.
        f"{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n"  # Add the formatted finish timestamp.
        f"{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}"  # Add the duration label.
        f"{calculate_execution_time(start_time, finish_time)}{BackgroundColors.RESET}"  # Add the formatted duration and reset formatting.
    )
    print(  # Display the template-style completion message.
        f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished."  # Add the successful completion text.
        f"{BackgroundColors.RESET}"  # Reset terminal formatting.
    )
    atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None  # Register optional completion sound playback.


if __name__ == "__main__":  # Execute the workflow only when this file is run directly.
    main()  # Invoke the program entry point.
