import atexit  # For playing a sound when the program finishes
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For regular expressions
import subprocess  # For running a command in the terminal
from colorama import Style  # For coloring the terminal
from pydub import AudioSegment  # For audio loading, slicing and exporting


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


def verify_filepath_exists(filepath=""):
    """
    Verify if a file or folder exists at the specified path.

    :param filepath: Path to the file or folder.
    :return: True if the file or folder exists, False otherwise.
    """

    return os.path.exists(filepath)  # Return True if path exists, False otherwise


def is_ffmpeg_installed():
    """
    Checks if FFmpeg is installed by running 'ffmpeg -version'.

    :param : No parameters.
    :return: True if ffmpeg is callable, False otherwise.
    """

    try:  # Try running ffmpeg to verify installation
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)  # Run ffmpeg
        return True  # ffmpeg ran successfully
    except (subprocess.CalledProcessError, FileNotFoundError):  # If running ffmpeg failed
        return False  # ffmpeg is not available


def verify_ffmpeg_is_installed():
    """
    Verifies ffmpeg presence and instructs the user if missing.

    :param : No parameters.
    :return: None
    """

    if is_ffmpeg_installed():  # If ffmpeg is present
        verbose_output(f"{BackgroundColors.GREEN}FFmpeg is installed.{Style.RESET_ALL}")  # Verbose notify
    else:  # If ffmpeg is missing
        print(f"{BackgroundColors.RED}FFmpeg is not installed or not in PATH. Please install FFmpeg.{Style.RESET_ALL}")  # Inform the user


def sanitize_filename(name=""):
    """
    Make a song name safe for use as a filename by replacing path separators and invalid characters.

    :param name: original song name.
    :return: sanitized filename-friendly song name.
    """

    sanitized = re.sub(r"[\\/]+", " - ", name)  # Replace path separators with ' - '
    sanitized = re.sub(r'[<>:"|?*]+', "-", sanitized)  # Replace characters invalid on Windows with '-'
    sanitized = re.sub(r"\s+", " ", sanitized).strip()  # Collapse multiple spaces and trim
    sanitized = re.sub(r"[-]{2,}", "-", sanitized)  # Collapse multiple hyphens to single
    sanitized = sanitized.strip(" .")  # Remove leading/trailing spaces and dots

    return sanitized or "untitled"  # Return 'untitled' if result is empty


def parse_timestamps(timestamps_file=""):
    """
    Parses timestamps from a file, ignoring track names and returning only normalized timestamps.

    :param timestamps_file: The path to the file containing the timestamps.
    :return: List of normalized timestamp strings in HH:MM:SS order.
    """

    if not timestamps_file or not os.path.isfile(timestamps_file):  # If timestamps file missing
        raise FileNotFoundError(f"Timestamp file not found: {timestamps_file}")  # Raise detailed error

    timestamps = []  # Prepare list for timestamp strings

    with open(timestamps_file, "r", encoding="utf-8") as fh:  # Open the timestamps file for reading
        for raw_line in fh:  # Iterate over each line in the file
            line = raw_line.strip()  # Trim whitespace from the line
            if not line:  # Skip empty lines
                continue  # Continue to next line

            match = re.search(r"(\d{1,2}:\d{2}(?::\d{2})?)", line)  # Search for timestamp pattern
            if not match:  # If no timestamp found on the line
                print(f"{BackgroundColors.RED}⚠️ Skipping malformed line (no timestamp): {line}{Style.RESET_ALL}")  # Warn user
                continue  # Skip the malformed line

            timestamp = match.group(1)  # Extract matched timestamp text
            parts = timestamp.split(":")  # Split into components
            if len(parts) == 2:  # If format is MM:SS
                hours = "00"  # Default hours to 00
                minutes = parts[0].zfill(2)  # Pad minutes
                seconds = parts[1].zfill(2)  # Pad seconds
            elif len(parts) == 3:  # If format is HH:MM:SS
                hours = parts[0].zfill(2)  # Pad hours
                minutes = parts[1].zfill(2)  # Pad minutes
                seconds = parts[2].zfill(2)  # Pad seconds
            else:  # Any other unexpected format
                print(f"{BackgroundColors.RED}⚠️ Skipping malformed timestamp: {timestamp}{Style.RESET_ALL}")  # Warn user
                continue  # Skip malformed timestamp

            normalized = f"{hours}:{minutes}:{seconds}"  # Compose normalized timestamp
            timestamps.append(normalized)  # Append normalized timestamp to list

    if not timestamps:  # If no valid timestamps were collected
        raise ValueError(f"No valid timestamps found in: {timestamps_file}")  # Raise a clear error

    return timestamps  # Return the list of normalized timestamps


def convert_timestamp_to_milliseconds(timestamp=""):
    """
    Converts a HH:MM:SS timestamp string into milliseconds.

    :param timestamp: Timestamp string in HH:MM:SS format.
    :return: Integer milliseconds equivalent of the timestamp.
    """

    if not timestamp:  # If timestamp is empty
        raise ValueError("Empty timestamp provided")  # Raise error for clarity

    parts = timestamp.split(":")  # Split timestamp into components
    if len(parts) != 3:  # If the timestamp is not in HH:MM:SS format
        raise ValueError(f"Timestamp must be HH:MM:SS, got: {timestamp}")  # Raise descriptive error

    hours = int(parts[0])  # Convert hours to integer
    minutes = int(parts[1])  # Convert minutes to integer
    seconds = int(parts[2])  # Convert seconds to integer
    milliseconds = ((hours * 3600) + (minutes * 60) + seconds) * 1000  # Compute total milliseconds

    return milliseconds  # Return computed milliseconds


def build_time_pairs(timestamps=None):
    """
    Builds (start, end) millisecond pairs from a list of normalized timestamps.

    :param timestamps: List of timestamp strings in HH:MM:SS order.
    :return: List of (start_ms, end_ms) tuples.
    """

    if timestamps is None:  # If None provided for timestamps
        timestamps = []  # Default to empty list

    pairs = []  # Prepare result list for pairs
    prev_end = 0  # Track previous end to avoid overlaps

    for i in range(0, len(timestamps) - 1, 2):  # Iterate in steps of two to build pairs
        start_ts = timestamps[i]  # Get start timestamp from current index
        end_ts = timestamps[i + 1]  # Get end timestamp from next index
        try:  # Try converting timestamps to milliseconds
            start_ms = convert_timestamp_to_milliseconds(start_ts)  # Convert start timestamp
            end_ms = convert_timestamp_to_milliseconds(end_ts)  # Convert end timestamp
        except ValueError as e:  # If conversion fails
            print(f"{BackgroundColors.RED}⚠️ Skipping invalid timestamp pair: {start_ts} - {end_ts}. Reason: {e}{Style.RESET_ALL}")  # Warn and continue
            continue  # Skip malformed pair

        if start_ms >= end_ms:  # If start is not before end
            print(f"{BackgroundColors.RED}⚠️ Skipping non-positive duration pair: {start_ts} -> {end_ts}{Style.RESET_ALL}")  # Warn and continue
            continue  # Skip the invalid duration

        if start_ms < prev_end:  # If this pair would overlap previous pair
            start_ms = prev_end  # Adjust start to the previous end to avoid overlap

        if start_ms >= end_ms:  # If adjusting removed the duration
            print(f"{BackgroundColors.YELLOW}⚠️ Adjusted pair has zero or negative duration, skipping{Style.RESET_ALL}")  # Warn and continue
            continue  # Skip the pair

        pairs.append((start_ms, end_ms))  # Append validated pair to pairs list
        prev_end = end_ms  # Update previous end to current end to prevent overlaps

    return pairs  # Return the list of millisecond pairs


def extract_segments(mp3_path="", pairs=None):
    """
    Extracts audio segments from an MP3 file given millisecond (start,end) pairs.

    :param mp3_path: Path to the source MP3 file.
    :param pairs: List of (start_ms, end_ms) tuples.
    :return: List of AudioSegment objects representing extracted segments.
    """

    if pairs is None:  # If no pairs provided
        pairs = []  # Default to empty list

    if not mp3_path or not os.path.isfile(mp3_path):  # If mp3 file missing
        raise FileNotFoundError(f"MP3 file not found: {mp3_path}")  # Raise a clear error

    try:  # Attempt to load the audio file into memory
        audio = AudioSegment.from_file(mp3_path, format="mp3")  # Load the full MP3 file as AudioSegment
    except Exception as e:  # Catch any error loading audio
        raise RuntimeError(f"Failed to load audio file: {e}")  # Raise conversion error

    segments = []  # Container for extracted segments

    for (start_ms, end_ms) in pairs:  # Iterate over each millisecond pair
        if start_ms < 0:  # If start time is negative
            start_ms = 0  # Clamp negative start to 0
        if end_ms > len(audio):  # If end time exceeds audio length
            end_ms = len(audio)  # Clamp end to audio length

        segment = audio[start_ms:end_ms]  # Slice the AudioSegment for the given range
        segments.append(segment)  # Append the extracted segment to list

    return segments  # Return list of segments


def merge_segments(segments=None):
    """
    Concatenates a list of AudioSegment objects preserving order.

    :param segments: List of AudioSegment objects.
    :return: Single AudioSegment representing the merged audio.
    """

    if segments is None:  # If segments not provided
        segments = []  # Default to empty list

    if not segments:  # If there are no segments to merge
        return AudioSegment.silent(duration=0)  # Return an empty silent AudioSegment

    merged = segments[0]  # Start merged audio from the first segment
    for seg in segments[1:]:  # Iterate over the remaining segments
        merged = merged + seg  # Concatenate the next segment to the merged audio

    return merged  # Return the concatenated AudioSegment


def export_final_file(audio_segment=None, output_path=""):
    """
    Exports the provided AudioSegment to an MP3 file safely using a temporary replace.

    :param audio_segment: The AudioSegment to export.
    :param output_path: The final output file path.
    :return: None
    """

    if audio_segment is None:  # If no audio to export
        raise ValueError("No audio segment provided for export")  # Raise clear error

    if not output_path:  # If no output path provided
        raise ValueError("No output path specified")  # Raise clear error

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)  # Ensure output directory exists

    temp_path = output_path + ".tmp.mp3"  # Create a temporary file path for safe export

    try:  # Attempt to export to temporary file first
        audio_segment.export(temp_path, format="mp3")  # Export merged audio to temporary path as MP3
        os.replace(temp_path, output_path)  # Atomically replace any existing file with the temp file
    except Exception as e:  # If export failed
        if os.path.exists(temp_path):  # If temp file exists after failure
            try:  # Attempt to remove temp file
                os.remove(temp_path)  # Remove temporary file
            except Exception:  # Ignore cleanup errors
                pass  # No-op on cleanup errors
        raise RuntimeError(f"Failed to export final MP3: {e}")  # Raise explanatory error


def mark_as_processed(mp3_file="", timestamp_file=""):
    """
    Renames both the MP3 file and its corresponding timestamp file to mark them as processed.

    :param mp3_file: The name of the MP3 file.
    :param timestamp_file: The path to the timestamp file.
    :return: None
    """

    if not mp3_file:  # If mp3 filename not provided
        return  # Nothing to do

    src_mp3 = os.path.join(INPUT_DIR, mp3_file)  # Compute source mp3 path
    dest_mp3 = os.path.join(INPUT_DIR, PROCESSED_PREFIX + mp3_file)  # Compute processed mp3 destination path
    if os.path.exists(src_mp3) and not mp3_file.startswith(PROCESSED_PREFIX):  # If source exists and is not already processed
        os.replace(src_mp3, dest_mp3)  # Rename source to processed path

    if timestamp_file and os.path.exists(timestamp_file):  # If timestamp file exists
        dest_ts = os.path.join(TIMESTAMP_DIR, PROCESSED_PREFIX + os.path.basename(timestamp_file))  # Destination for processed timestamp
        if not os.path.basename(timestamp_file).startswith(PROCESSED_PREFIX):  # If not already marked processed
            os.replace(timestamp_file, dest_ts)  # Rename timestamp file


def play_sound():
    """
    Plays a sound when the program finishes; skipped on Windows.

    :param : No parameters.
    :return: None
    """

    current_os = platform.system()  # Detect current operating system
    if current_os == "Windows":  # Skip sound on Windows by design
        return  # No-op for Windows

    if not verify_filepath_exists(SOUND_FILE):  # If sound file does not exist
        return  # No-op when sound asset missing

    if current_os in SOUND_COMMANDS:  # If we have a command for this OS
        os.system(f"{SOUND_COMMANDS[current_os]} {SOUND_FILE}")  # Play the sound using system command


def list_valid_mp3_files():
    """
    Lists MP3 files that have a matching timestamp file in the TIMESTAMP_DIR.

    :param : No parameters.
    :return: List of valid MP3 filenames.
    """

    if not os.path.isdir(INPUT_DIR):  # If input directory does not exist
        return []  # Return empty list

    mp3_files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith('.mp3')]  # List all mp3 files in input dir
    valid = []  # Prepare list for valid mp3 files that have timestamps

    for f in mp3_files:  # Iterate mp3 files
        base = os.path.splitext(f)[0]  # Extract base filename without extension
        ts_path = os.path.join(TIMESTAMP_DIR, f"{base}.txt")  # Expected timestamp path for this mp3
        if os.path.isfile(ts_path):  # If corresponding timestamp file exists
            valid.append(f)  # Add to valid list
        else:  # If timestamp file missing
            print(f"{BackgroundColors.YELLOW}⚠️ No timestamp file for: {f} (skipping){Style.RESET_ALL}")  # Notify and skip

    return valid  # Return the valid files list


def main():
    """
    Main function which orchestrates reading timestamps, extracting segments, merging, and exporting a single MP3 per source.

    :param : No parameters.
    :return: None
    """

    print(f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}MP3 Timestamp-Based Merger{BackgroundColors.GREEN}!{Style.RESET_ALL}")  # Print welcome banner

    os.makedirs(TIMESTAMP_DIR, exist_ok=True)  # Ensure timestamp directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)  # Ensure output directory exists

    verify_ffmpeg_is_installed()  # Verify ffmpeg availability for pydub

    mp3_files = list_valid_mp3_files()  # Get MP3 files with matching timestamp files
    if not mp3_files:  # If no files to process
        print(f"{BackgroundColors.RED}No valid MP3 files found in {INPUT_DIR} with corresponding timestamps in {TIMESTAMP_DIR}.{Style.RESET_ALL}")  # Inform user and exit
        return  # Exit main

    for mp3_file in mp3_files:  # Iterate each valid mp3 file
        print(f"\n{BackgroundColors.BOLD}Processing {mp3_file}...{Style.RESET_ALL}")  # Announce processing of the file
        base = os.path.splitext(mp3_file)[0]  # Compute base name without extension
        ts_path = os.path.join(TIMESTAMP_DIR, f"{base}.txt")  # Compute timestamp file path
        src_mp3_path = os.path.join(INPUT_DIR, mp3_file)  # Compute source mp3 full path

        try:  # Wrap per-file processing to continue on errors
            timestamps = parse_timestamps(ts_path)  # Parse timestamps (ignoring track names)
            pairs = build_time_pairs(timestamps)  # Build start/end millisecond pairs from timestamps
            if not pairs:  # If no valid pairs could be built
                print(f"{BackgroundColors.RED}No valid start/end pairs for {mp3_file} (need pairs of timestamps).{Style.RESET_ALL}")  # Warn and skip
                continue  # Continue to next mp3 file

            segments = extract_segments(src_mp3_path, pairs)  # Extract each segment from the source MP3
            if not segments:  # If extraction produced no segments
                print(f"{BackgroundColors.RED}No audio segments extracted for {mp3_file}.{Style.RESET_ALL}")  # Warn and skip
                continue  # Continue to next file

            merged = merge_segments(segments)  # Merge extracted segments into a single AudioSegment

            output_name = sanitize_filename(base + OUTPUT_FILE_SUFFIX) + ".mp3"  # Compose sanitized output filename
            output_path = os.path.join(OUTPUT_DIR, output_name)  # Compute output path for final mp3

            export_final_file(merged, output_path)  # Export merged audio to final MP3 path

            print(f"{BackgroundColors.GREEN}✅ Exported merged file: {BackgroundColors.CYAN}{output_path}{Style.RESET_ALL}")  # Confirm export

            mark_as_processed(mp3_file, ts_path)  # Mark source mp3 and timestamp file as processed

        except Exception as e:  # If any unexpected error occurs during processing
            print(f"{BackgroundColors.RED}Error processing {mp3_file}: {e}{Style.RESET_ALL}")  # Print error message and continue

    print(f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}")  # Final status message
    atexit.register(play_sound)  # Register the sound notification at exit


if __name__ == "__main__":
    main()  # Execute main when run as script
