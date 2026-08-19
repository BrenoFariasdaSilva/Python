r"""
================================================================================
Video Duplicate Segments Finder
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-19
Description :
    Finds repeated subsections inside one or more video files by comparing
    perceptual video fingerprints, normalized audio fingerprints, or both.
    The detector is designed for edited compilations where repeated material may
    originate from different source resolutions but has been scaled or fitted
    into a constant final video frame.

    Key features include:
        - Recursive processing of supported video files under ./Inputs/.
        - Optional processing of one explicitly configured or command-line video file.
        - Independent USE_VIDEO and USE_AUDIO controls, enabled together by default.
        - Configurable minimum repeated subsection duration and confidence threshold.
        - Scale- and compression-tolerant video fingerprints based on low-frequency
          luminance and edge DCT information instead of raw pixel equality.
        - Volume-tolerant audio fingerprints based on normalized spectral-band energy.
        - KD-tree candidate-offset discovery to avoid naive all-pairs sequence scans.
        - Full temporal validation of candidate offsets before reporting duplicates.
        - JSON reports containing repeated ranges, duration, offset, and confidence.
        - Inline tqdm progress bars with green static text and cyan dynamic filenames.

Usage:
    1. Configure INPUT_DIR, INPUT_VIDEO_FILE, USE_VIDEO, USE_AUDIO,
       MINIMUM_SUBSECTION_SIZE_S, and CONFIDENCE_PERCENTAGE as needed.
    2. Ensure FFmpeg and FFprobe are installed and available through the system PATH.
    3. Execute the script through the project Makefile or directly with Python:
        $ make run   or   $ python main.py
    4. Optionally provide one video path on the command line to override
       INPUT_VIDEO_FILE and INPUT_DIR:
        $ python main.py "D:/Videos/Compilation.mkv"
    5. Review one JSON report per processed video inside ./Outputs/.

Outputs:
    - ./Outputs/<input-name>-duplicates.json containing duplicate subsection results.
    - ./Logs/main.log containing permanent status, warning, and summary messages.

TODOs:
    - Add optional GPU-assisted fingerprint extraction for very large libraries.
    - Add optional cross-file duplicate segment comparison.
    - Add optional HTML timeline visualization for reported repeated segments.
    - Add optional adaptive sample intervals for extremely long source videos.

Dependencies:
    - Python >= 3.10.
    - FFmpeg and FFprobe available through the system PATH.
    - colorama.
    - numpy.
    - scipy.
    - tqdm.
    - Project Logger module.

Assumptions & Notes:
    - Duplicate detection is performed within each video independently.
    - INPUT_VIDEO_FILE, when configured, takes precedence over INPUT_DIR.
    - A command-line video path takes precedence over INPUT_VIDEO_FILE.
    - At least one of USE_VIDEO or USE_AUDIO must be enabled.
    - Video comparison intentionally uses perceptual low-frequency structure instead
      of exact pixels so source-resolution differences, fitting, and normal encoding
      differences do not automatically prevent a match.
    - Audio comparison normalizes spectral shape so ordinary volume differences are
      less important than the underlying audio content.
    - CONFIDENCE_PERCENTAGE represents the average fingerprint similarity required
      across a complete reported subsection; it is not a statistical probability.
    - Repeated ranges are required to be non-overlapping within a reported pair.
"""


import argparse  # For optionally selecting one video file from the command line
import atexit  # For playing a sound when the program finishes
import datetime  # For getting the current date and time
import json  # For writing duplicate subsection reports
import math  # For converting durations into deterministic sample counts
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For sanitizing generated report filenames
import shutil  # For locating FFmpeg and FFprobe executables
import subprocess  # For decoding media fingerprints through FFmpeg and FFprobe
import sys  # For system-specific parameters and functions
import tempfile  # For safely capturing subprocess diagnostics without pipe deadlocks
from collections import Counter  # For ranking candidate repeated temporal offsets
from colorama import Style  # For coloring the terminal
from Logger import Logger  # For logging output to both terminal and file
from pathlib import Path  # For handling file paths
from scipy.fft import dctn  # For extracting scale-tolerant low-frequency visual structure
from scipy.spatial import cKDTree  # For efficiently locating similar fingerprint samples
from tqdm import tqdm  # For inline-updated progress bars
import numpy as np  # For numerical fingerprint extraction and similarity calculations


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
INPUT_DIR = f"./Inputs/"  # Default directory recursively searched when no single video file is selected
INPUT_VIDEO_FILE: str | None = None  # Optional single video path that takes precedence over INPUT_DIR when configured
OUTPUT_DIR = Path("./Outputs/")  # Directory receiving one JSON report per processed input video
USE_VIDEO = True  # Set to True to use perceptual video information when finding repeated subsections
USE_AUDIO = True  # Set to True to use audio information when finding repeated subsections
MINIMUM_SUBSECTION_SIZE_S = 5.0  # Minimum duplicate subsection duration in seconds
CONFIDENCE_PERCENTAGE = 95.0  # Minimum average subsection similarity percentage required for a reported duplicate
SAMPLE_INTERVAL_S = 0.25  # Temporal fingerprint spacing; 0.25 seconds provides four comparison samples per second
VIDEO_FRAME_SIZE = 32  # Width and height of FFmpeg-decoded grayscale frames used for compact perceptual fingerprints
VIDEO_DCT_SIZE = 6  # Low-frequency luminance DCT square retained from each normalized frame
VIDEO_EDGE_DCT_SIZE = 4  # Low-frequency edge DCT square retained from each normalized frame
VIDEO_CANDIDATE_DIMENSIONS = 24  # Leading video fingerprint dimensions used during fast KD-tree candidate discovery
AUDIO_SAMPLE_RATE = 16000  # Mono PCM sample rate used for audio fingerprint extraction
AUDIO_WINDOW_SIZE_S = 0.50  # Audio analysis window duration; overlapping windows improve time-offset tolerance
AUDIO_FREQUENCY_BANDS = 18  # Number of logarithmic spectral bands retained per audio fingerprint
AUDIO_MIN_FREQUENCY_HZ = 80.0  # Lowest frequency represented by audio fingerprints
AUDIO_MAX_FREQUENCY_HZ = 7600.0  # Highest frequency represented by audio fingerprints at the configured sample rate
MAX_NEIGHBORS_PER_SAMPLE = 20  # Maximum similar samples inspected per timeline sample during candidate discovery
MAX_CANDIDATE_OFFSETS = 512  # Maximum temporal offsets fully validated after KD-tree voting
CANDIDATE_CONFIDENCE_MARGIN_PERCENTAGE = 15.0  # Candidate stage may be this much less strict than the final confidence threshold
MAX_WINDOW_GAP_S = 0.50  # Maximum gap between qualifying minimum windows that may be merged into one duplicate subsection
MAX_REPORTED_DUPLICATES_PER_FILE = 500  # Safety cap preventing pathological repetitive media from producing unbounded reports
FFMPEG = "ffmpeg"  # FFmpeg executable name or path
FFPROBE = "ffprobe"  # FFprobe executable name or path
SUPPORTED_VIDEO_EXTENSIONS = frozenset(  # Supported video containers discovered beneath INPUT_DIR
    {
        ".3g2", ".3gp", ".avi", ".flv", ".m2ts", ".m4v", ".mkv", ".mk3d", ".mov",
        ".mp4", ".mpeg", ".mpg", ".mts", ".ogv", ".ts", ".vob", ".webm", ".wmv",
    }
)


# Logger Setup:
logger = Logger(f"./Logs/{Path(__file__).stem}.log", clean=True)  # Create a Logger instance
sys.stdout = logger  # Redirect stdout to the logger
sys.stderr = logger  # Redirect stderr to the logger


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


# Functions Definitions:


def log_line(message=""):
    """
    Writes exactly one permanent line through the project Logger.

    :param message: Message to write to the terminal and log file.
    :return: None
    """

    logger.write(message)  # Use one Logger write so the Logger's newline behavior does not duplicate print newlines


def verbose_output(true_string="", false_string=""):
    """
    Outputs a message if the VERBOSE constant is set to True.

    :param true_string: The string to be outputted if the VERBOSE constant is set to True.
    :param false_string: The string to be outputted if the VERBOSE constant is set to False.
    :return: None
    """

    if VERBOSE and true_string != "":  # If VERBOSE is True and a true_string was provided
        log_line(true_string)  # Output the true statement string
    elif false_string != "":  # If a false_string was provided
        log_line(false_string)  # Output the false statement string


def resolve_executable(executable_name: str) -> str:
    """
    Resolves one required external executable from an explicit path or system PATH.

    :param executable_name: Configured executable name or filesystem path.
    :return: Resolved executable path.
    """

    configured_path = Path(executable_name)  # Interpret the configured value as a possible direct path

    if configured_path.is_file():  # Prefer an explicit executable path when it exists
        return str(configured_path)  # Return the direct executable path

    resolved_path = shutil.which(executable_name)  # Search the process PATH for the configured executable

    if resolved_path is None:  # Reject execution when the required binary cannot be located
        raise FileNotFoundError(f"Required executable not found: {executable_name}")  # Report the missing external dependency

    return resolved_path  # Return the executable discovered through PATH


def validate_configuration() -> None:
    """
    Validates constants that control duplicate subsection detection.

    :return: None
    """

    if not USE_VIDEO and not USE_AUDIO:  # Require at least one comparison modality
        raise ValueError("At least one of USE_VIDEO or USE_AUDIO must be True.")  # Prevent a detector with no usable information source

    if MINIMUM_SUBSECTION_SIZE_S <= 0:  # Reject zero or negative duplicate durations
        raise ValueError("MINIMUM_SUBSECTION_SIZE_S must be greater than 0.")  # Require a positive subsection duration

    if not 0 < CONFIDENCE_PERCENTAGE <= 100:  # Validate the requested final confidence range
        raise ValueError("CONFIDENCE_PERCENTAGE must be greater than 0 and at most 100.")  # Reject impossible confidence values

    if SAMPLE_INTERVAL_S <= 0:  # Require a positive timeline sample interval
        raise ValueError("SAMPLE_INTERVAL_S must be greater than 0.")  # Prevent division-by-zero and invalid FFmpeg filters

    if AUDIO_WINDOW_SIZE_S < SAMPLE_INTERVAL_S:  # Require an audio window that can advance by the configured hop
        raise ValueError("AUDIO_WINDOW_SIZE_S must be greater than or equal to SAMPLE_INTERVAL_S.")  # Reject invalid overlapping-window configuration

    if VIDEO_FRAME_SIZE < VIDEO_DCT_SIZE or VIDEO_FRAME_SIZE < VIDEO_EDGE_DCT_SIZE:  # Validate DCT extraction dimensions
        raise ValueError("VIDEO_FRAME_SIZE must be at least as large as the configured DCT sizes.")  # Prevent invalid DCT slices


def parse_cli_video_file() -> str | None:
    """
    Parses an optional command-line video path.

    :return: Command-line video path or None when no positional input was provided.
    """

    parser = argparse.ArgumentParser(  # Create a minimal optional single-file command-line interface
        description="Find duplicate subsections inside video files using perceptual video and/or audio fingerprints."
    )
    parser.add_argument(  # Add an optional positional path that overrides configured input constants
        "video_file",
        nargs="?",
        help="Optional video file to process instead of INPUT_VIDEO_FILE or INPUT_DIR.",
    )
    arguments = parser.parse_args()  # Parse the current process arguments

    return arguments.video_file  # Return the optional command-line path


def collect_input_videos(cli_video_file: str | None) -> list[Path]:
    """
    Resolves the requested single video or recursively discovers videos beneath INPUT_DIR.

    :param cli_video_file: Optional command-line video path.
    :return: Sorted list of input video files.
    """

    configured_single_file = cli_video_file or INPUT_VIDEO_FILE  # Apply command line, then configured single-file precedence

    if configured_single_file:  # Process one explicitly selected file
        video_path = Path(configured_single_file).expanduser()  # Normalize the requested input path

        if not video_path.is_file():  # Require the configured path to exist as a file
            raise FileNotFoundError(f"Configured input video does not exist: {video_path}")  # Reject a missing single-file input

        if video_path.suffix.lower() not in SUPPORTED_VIDEO_EXTENSIONS:  # Reject unsupported single-file containers
            raise ValueError(f"Unsupported video extension for input file: {video_path}")  # Report the unsupported container

        return [video_path]  # Return the explicitly selected video only

    input_directory = Path(INPUT_DIR).expanduser()  # Normalize the configured recursive input directory

    if not input_directory.is_dir():  # Require the default input directory to exist
        raise NotADirectoryError(f"INPUT_DIR does not exist or is not a directory: {input_directory}")  # Report the invalid input root

    video_files = [  # Recursively collect supported video files
        path
        for path in input_directory.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_VIDEO_EXTENSIONS
    ]

    return sorted(video_files, key=lambda path: str(path).casefold())  # Return deterministic case-insensitive path ordering


def run_capture(command: list[str], command_name: str) -> subprocess.CompletedProcess[str]:
    """
    Executes a command while suppressing successful output and preserving diagnostics on failure.

    :param command: Complete subprocess argument list.
    :param command_name: Human-readable executable name used in errors.
    :return: Completed subprocess result.
    """

    result = subprocess.run(  # Execute without leaking routine output into tqdm progress bars
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:  # Reject unsuccessful external-tool execution
        diagnostic_output = (result.stderr or result.stdout or "").strip()  # Preserve the most useful available diagnostic output
        diagnostic_suffix = f"\n\n{command_name} output:\n{diagnostic_output}" if diagnostic_output else ""  # Add diagnostics only when present
        raise RuntimeError(f"{command_name} failed with exit code {result.returncode}.{diagnostic_suffix}")  # Raise one readable failure

    return result  # Return captured successful output to the caller


def probe_media(ffprobe_executable: str, video_path: Path) -> dict:
    """
    Reads duration and available stream types from one media file.

    :param ffprobe_executable: Resolved FFprobe executable path.
    :param video_path: Media file to inspect.
    :return: Dictionary containing duration and stream-presence metadata.
    """

    command = [  # Build a compact FFprobe metadata request
        ffprobe_executable,
        "-v", "error",
        "-print_format", "json",
        "-show_entries", "format=duration:stream=codec_type,duration",
        str(video_path),
    ]
    result = run_capture(command, "FFprobe")  # Execute FFprobe and capture its JSON output

    try:  # Parse FFprobe JSON output defensively
        media_info = json.loads(result.stdout)
    except json.JSONDecodeError as exception:  # Handle malformed FFprobe output
        raise RuntimeError(f"FFprobe returned invalid JSON for: {video_path}") from exception  # Preserve the affected media path

    streams = media_info.get("streams")  # Read the stream collection
    stream_list = streams if isinstance(streams, list) else []  # Normalize absent stream metadata to an empty list
    has_video = any(isinstance(stream, dict) and stream.get("codec_type") == "video" for stream in stream_list)  # Detect video
    has_audio = any(isinstance(stream, dict) and stream.get("codec_type") == "audio" for stream in stream_list)  # Detect audio
    duration_candidates: list[float] = []  # Collect valid container and stream durations
    format_info = media_info.get("format")  # Read container metadata

    if isinstance(format_info, dict):  # Handle a dictionary-shaped format record
        try:  # Parse the container duration when available
            duration_candidates.append(float(format_info.get("duration")))
        except (TypeError, ValueError):  # Ignore absent or malformed duration values
            pass

    for stream in stream_list:  # Inspect per-stream durations as a fallback
        if not isinstance(stream, dict):  # Ignore malformed stream records
            continue

        try:  # Parse one stream duration when available
            duration_candidates.append(float(stream.get("duration")))
        except (TypeError, ValueError):  # Ignore missing or malformed duration values
            continue

    duration_candidates = [duration for duration in duration_candidates if math.isfinite(duration) and duration > 0]  # Retain positive finite durations only

    if not duration_candidates:  # Require a usable timeline duration
        raise RuntimeError(f"Could not determine a positive duration for: {video_path}")  # Reject media with unavailable timing information

    return {"duration_s": max(duration_candidates), "has_video": has_video, "has_audio": has_audio}  # Return normalized media metadata


def normalize_rows(matrix: np.ndarray) -> np.ndarray:
    """
    L2-normalizes feature rows while preserving all-zero rows safely.

    :param matrix: Two-dimensional feature matrix.
    :return: Row-normalized float32 matrix.
    """

    if matrix.size == 0:  # Preserve empty matrices without reduction errors
        return matrix.astype(np.float32, copy=False)  # Return an empty float32 matrix

    normalized = matrix.astype(np.float32, copy=True)  # Copy features into a predictable numerical type
    norms = np.linalg.norm(normalized, axis=1, keepdims=True)  # Calculate row magnitudes
    nonzero_rows = norms[:, 0] > 1e-12  # Identify rows with meaningful magnitude
    normalized[nonzero_rows] /= norms[nonzero_rows]  # Normalize only nonzero rows

    return normalized  # Return the safe normalized matrix


def normalize_vector(vector: np.ndarray) -> np.ndarray:
    """
    L2-normalizes one feature vector.

    :param vector: One-dimensional feature vector.
    :return: Normalized float32 vector.
    """

    feature = np.asarray(vector, dtype=np.float32)  # Convert the input into a predictable floating-point vector
    norm = float(np.linalg.norm(feature))  # Calculate vector magnitude

    if norm <= 1e-12:  # Preserve an all-zero vector safely
        return feature  # Return the unchanged zero vector

    return feature / norm  # Return a unit-length fingerprint


def build_video_fingerprint(frame_bytes: bytes) -> np.ndarray:
    """
    Builds one perceptual video fingerprint from a normalized grayscale FFmpeg frame.

    :param frame_bytes: VIDEO_FRAME_SIZE squared grayscale bytes.
    :return: Unit-normalized luminance and edge DCT fingerprint.
    """

    frame = np.frombuffer(frame_bytes, dtype=np.uint8).reshape(VIDEO_FRAME_SIZE, VIDEO_FRAME_SIZE).astype(np.float32)  # Decode the compact grayscale frame
    mean_value = float(frame.mean())  # Measure average luminance for flat-frame handling
    standard_deviation = float(frame.std())  # Measure contrast before normalization
    luminance_feature_size = VIDEO_DCT_SIZE * VIDEO_DCT_SIZE - 1  # Calculate retained non-DC luminance coefficients
    edge_feature_size = VIDEO_EDGE_DCT_SIZE * VIDEO_EDGE_DCT_SIZE - 1  # Calculate retained non-DC edge coefficients
    feature_size = luminance_feature_size + edge_feature_size  # Calculate the final visual fingerprint length

    if standard_deviation < 1.0:  # Handle nearly uniform black, white, or flat-color frames explicitly
        flat_feature = np.zeros(feature_size, dtype=np.float32)  # Initialize a deterministic flat-frame fingerprint
        normalized_level = min(1.0, max(0.0, mean_value / 255.0))  # Convert luminance into a zero-to-one range
        flat_feature[0] = 1.0 - normalized_level  # Encode darkness
        flat_feature[1] = normalized_level  # Encode brightness
        return normalize_vector(flat_feature)  # Return a nonzero flat-frame representation

    normalized_frame = (frame - mean_value) / standard_deviation  # Remove brightness and contrast differences before structural analysis
    luminance_dct = dctn(normalized_frame, type=2, norm="ortho")[:VIDEO_DCT_SIZE, :VIDEO_DCT_SIZE].reshape(-1)[1:]  # Retain low-frequency luminance structure
    gradient_y, gradient_x = np.gradient(normalized_frame)  # Calculate vertical and horizontal normalized-frame gradients
    edge_magnitude = np.hypot(gradient_x, gradient_y)  # Combine gradients into an edge-strength image
    edge_standard_deviation = float(edge_magnitude.std())  # Measure edge contrast

    if edge_standard_deviation > 1e-6:  # Normalize useful edge structure
        edge_magnitude = (edge_magnitude - edge_magnitude.mean()) / edge_standard_deviation  # Remove edge-level scale differences
    else:  # Handle frames with effectively no edge variation
        edge_magnitude = edge_magnitude - edge_magnitude.mean()  # Preserve a stable near-zero edge surface

    edge_dct = dctn(edge_magnitude, type=2, norm="ortho")[:VIDEO_EDGE_DCT_SIZE, :VIDEO_EDGE_DCT_SIZE].reshape(-1)[1:]  # Retain low-frequency edge structure
    fingerprint = np.concatenate((luminance_dct, edge_dct)).astype(np.float32)  # Combine luminance and edge descriptors

    return normalize_vector(fingerprint)  # Return one unit-length perceptual video fingerprint


def read_exact(stream, byte_count: int) -> bytes:
    """
    Reads up to an exact number of bytes from a binary stream.

    :param stream: Binary stream returned by subprocess stdout.
    :param byte_count: Requested byte count.
    :return: Bytes read, which may be shorter only at end-of-stream.
    """

    chunks: list[bytes] = []  # Collect partial reads safely
    remaining = byte_count  # Track bytes still required

    while remaining > 0:  # Continue until the requested byte count or EOF
        chunk = stream.read(remaining)  # Read the remaining number of requested bytes
        if not chunk:  # Stop when the stream reaches EOF
            break
        chunks.append(chunk)  # Preserve the newly read bytes
        remaining -= len(chunk)  # Reduce the outstanding byte count

    return b"".join(chunks)  # Return the combined data


def subprocess_error_text(error_file) -> str:
    """
    Reads and decodes diagnostics captured in a temporary subprocess error file.

    :param error_file: Temporary binary file receiving subprocess stderr.
    :return: Decoded diagnostic text.
    """

    error_file.seek(0)  # Rewind the diagnostic file before reading
    return error_file.read().decode("utf-8", errors="replace").strip()  # Decode diagnostics safely


def extract_video_fingerprints(ffmpeg_executable: str, video_path: Path, duration_s: float) -> np.ndarray:
    """
    Extracts regularly spaced perceptual video fingerprints using FFmpeg decoding.

    :param ffmpeg_executable: Resolved FFmpeg executable path.
    :param video_path: Input video file.
    :param duration_s: Probed media duration in seconds.
    :return: Two-dimensional video fingerprint matrix.
    """

    frame_byte_count = VIDEO_FRAME_SIZE * VIDEO_FRAME_SIZE  # Calculate bytes per compact grayscale frame
    samples_per_second = 1.0 / SAMPLE_INTERVAL_S  # Convert the configured interval into FFmpeg fps
    expected_samples = max(1, math.ceil(duration_s / SAMPLE_INTERVAL_S))  # Estimate progress-bar sample count
    video_filter = f"fps={samples_per_second:.10f},scale={VIDEO_FRAME_SIZE}:{VIDEO_FRAME_SIZE}:flags=lanczos,format=gray"  # Build a compact scale-tolerant sampling filter
    command = [  # Build the streaming FFmpeg raw-frame extraction command
        ffmpeg_executable, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(video_path),
        "-map", "0:v:0", "-an", "-sn", "-dn", "-vf", video_filter,
        "-pix_fmt", "gray", "-f", "rawvideo", "pipe:1",
    ]
    fingerprints: list[np.ndarray] = []  # Store compact fingerprints rather than decoded full-resolution frames

    with tempfile.TemporaryFile() as error_file:  # Capture stderr outside a PIPE to avoid blocking on large diagnostics
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=error_file)  # Start FFmpeg and stream raw frames incrementally

        if process.stdout is None:  # Guard against an unexpected subprocess configuration
            process.kill()  # Stop the unusable FFmpeg process
            raise RuntimeError(f"Could not capture FFmpeg video output for: {video_path}")  # Report failed extraction setup

        progress_bar = tqdm(  # Render one inline video-fingerprint progress bar
            total=expected_samples,
            desc=f"{BackgroundColors.GREEN}Video fingerprints: {BackgroundColors.CYAN}{video_path.name}{BackgroundColors.GREEN}",
            unit="sample", dynamic_ncols=True, colour="green", file=sys.__stdout__, mininterval=0.2,
        )

        try:  # Ensure progress and process resources are finalized even when fingerprint calculation fails
            while True:  # Read fixed-size grayscale frames until FFmpeg reaches EOF
                frame_bytes = read_exact(process.stdout, frame_byte_count)  # Read one complete compact frame
                if not frame_bytes:  # Stop cleanly at EOF
                    break
                if len(frame_bytes) != frame_byte_count:  # Reject a truncated raw frame
                    raise RuntimeError(f"FFmpeg returned a truncated video fingerprint frame for: {video_path}")  # Prevent malformed arrays
                fingerprints.append(build_video_fingerprint(frame_bytes))  # Convert the frame into a robust perceptual descriptor
                progress_bar.update(1)  # Advance the inline fingerprint progress
        finally:
            progress_bar.close()  # Finalize the inline progress row
            process.stdout.close()  # Close the raw-frame pipe

        return_code = process.wait()  # Wait for FFmpeg to terminate after EOF
        diagnostic_output = subprocess_error_text(error_file)  # Read any captured FFmpeg diagnostics

    if return_code != 0:  # Reject incomplete FFmpeg video extraction
        diagnostic_suffix = f"\n\nFFmpeg output:\n{diagnostic_output}" if diagnostic_output else ""  # Include available FFmpeg details
        raise RuntimeError(f"FFmpeg video fingerprint extraction failed with exit code {return_code}.{diagnostic_suffix}")  # Surface the failure

    if not fingerprints:  # Require at least one decoded fingerprint
        raise RuntimeError(f"No video fingerprints could be extracted from: {video_path}")  # Reject unusable video input

    return normalize_rows(np.vstack(fingerprints))  # Return a consistently normalized video fingerprint matrix


def build_audio_band_slices(window_sample_count: int) -> list[tuple[int, int]]:
    """
    Builds logarithmic FFT-bin ranges used by every audio fingerprint window.

    :param window_sample_count: Number of PCM samples in one analysis window.
    :return: List of inclusive-exclusive FFT-bin slices.
    """

    frequencies = np.fft.rfftfreq(window_sample_count, d=1.0 / AUDIO_SAMPLE_RATE)  # Calculate one-sided FFT bin frequencies
    maximum_frequency = min(AUDIO_MAX_FREQUENCY_HZ, AUDIO_SAMPLE_RATE / 2.0 - 1.0)  # Respect the Nyquist limit
    frequency_edges = np.geomspace(AUDIO_MIN_FREQUENCY_HZ, maximum_frequency, AUDIO_FREQUENCY_BANDS + 1)  # Build logarithmic regions
    band_slices: list[tuple[int, int]] = []  # Store stable FFT-bin intervals

    for band_index in range(AUDIO_FREQUENCY_BANDS):  # Convert every frequency region into array indices
        start_index = int(np.searchsorted(frequencies, frequency_edges[band_index], side="left"))  # Locate the first bin
        end_index = int(np.searchsorted(frequencies, frequency_edges[band_index + 1], side="right"))  # Locate the final bin
        end_index = max(start_index + 1, min(end_index, len(frequencies)))  # Guarantee at least one valid FFT bin
        start_index = min(start_index, end_index - 1)  # Keep the start index inside the valid slice
        band_slices.append((start_index, end_index))  # Preserve the validated FFT-bin interval

    return band_slices  # Return all reusable frequency-band slices


def build_audio_fingerprint(samples: np.ndarray, hann_window: np.ndarray, band_slices: list[tuple[int, int]]) -> np.ndarray:
    """
    Builds one normalized spectral audio fingerprint.

    :param samples: Mono float32 PCM samples for one analysis window.
    :param hann_window: Precomputed Hann weighting window.
    :param band_slices: Precomputed logarithmic FFT-bin ranges.
    :return: Unit-normalized spectral fingerprint with a silence marker.
    """

    samples = np.asarray(samples, dtype=np.float32)  # Normalize the analysis buffer type
    rms = float(np.sqrt(np.mean(np.square(samples), dtype=np.float64)))  # Measure signal energy before spectral normalization

    if rms < 1e-4:  # Represent genuine silence deterministically
        silence_feature = np.zeros(AUDIO_FREQUENCY_BANDS + 1, dtype=np.float32)  # Initialize the silent fingerprint
        silence_feature[-1] = 1.0  # Mark this window as silence explicitly
        return silence_feature  # Return a stable silence fingerprint

    weighted_samples = samples * hann_window  # Reduce FFT edge discontinuities
    spectrum = np.abs(np.fft.rfft(weighted_samples)) ** 2  # Calculate one-sided spectral power
    band_energies = np.array(  # Aggregate power into logarithmic frequency bands
        [math.log1p(float(np.mean(spectrum[start_index:end_index]))) for start_index, end_index in band_slices],
        dtype=np.float32,
    )
    band_standard_deviation = float(band_energies.std())  # Measure spectral-shape variation

    if band_standard_deviation > 1e-6:  # Normalize meaningful spectral shape
        band_energies = (band_energies - band_energies.mean()) / band_standard_deviation  # Remove global level scaling
    else:  # Handle near-flat spectra defensively
        band_energies = band_energies - band_energies.mean()  # Preserve stable centered values

    fingerprint = np.concatenate((band_energies, np.array([0.0], dtype=np.float32)))  # Append a non-silence marker
    return normalize_vector(fingerprint)  # Return one unit-length audio fingerprint


def extract_audio_fingerprints(ffmpeg_executable: str, video_path: Path, duration_s: float) -> np.ndarray:
    """
    Extracts overlapping normalized audio fingerprints using FFmpeg mono PCM decoding.

    :param ffmpeg_executable: Resolved FFmpeg executable path.
    :param video_path: Input video file.
    :param duration_s: Probed media duration in seconds.
    :return: Two-dimensional audio fingerprint matrix.
    """

    window_sample_count = max(1, int(round(AUDIO_WINDOW_SIZE_S * AUDIO_SAMPLE_RATE)))  # Convert analysis-window duration into PCM samples
    hop_sample_count = max(1, int(round(SAMPLE_INTERVAL_S * AUDIO_SAMPLE_RATE)))  # Convert fingerprint spacing into PCM samples
    window_byte_count = window_sample_count * 2  # s16le uses two bytes per mono sample
    hop_byte_count = hop_sample_count * 2  # Calculate bytes discarded after each overlapping analysis window
    expected_samples = max(1, math.ceil(duration_s / SAMPLE_INTERVAL_S))  # Estimate progress-bar sample count
    hann_window = np.hanning(window_sample_count).astype(np.float32)  # Precompute the analysis weighting window
    band_slices = build_audio_band_slices(window_sample_count)  # Precompute logarithmic FFT-bin regions
    command = [  # Build the streaming mono PCM extraction command
        ffmpeg_executable, "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(video_path),
        "-map", "0:a:0", "-vn", "-sn", "-dn", "-ac", "1", "-ar", str(AUDIO_SAMPLE_RATE),
        "-acodec", "pcm_s16le", "-f", "s16le", "pipe:1",
    ]
    fingerprints: list[np.ndarray] = []  # Store compact audio fingerprints
    pcm_buffer = bytearray()  # Maintain an overlapping PCM window without loading the complete soundtrack into memory
    reached_eof = False  # Track whether FFmpeg stdout has been fully consumed

    with tempfile.TemporaryFile() as error_file:  # Capture stderr without risking a blocked stderr PIPE
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=error_file)  # Start FFmpeg and stream decoded PCM incrementally

        if process.stdout is None:  # Guard against an unexpected subprocess configuration
            process.kill()  # Stop the unusable process
            raise RuntimeError(f"Could not capture FFmpeg audio output for: {video_path}")  # Report failed audio extraction setup

        progress_bar = tqdm(  # Render one inline audio-fingerprint progress bar
            total=expected_samples,
            desc=f"{BackgroundColors.GREEN}Audio fingerprints: {BackgroundColors.CYAN}{video_path.name}{BackgroundColors.GREEN}",
            unit="sample", dynamic_ncols=True, colour="green", file=sys.__stdout__, mininterval=0.2,
        )

        try:  # Ensure progress and process resources are finalized safely
            while True:  # Produce one overlapping spectral fingerprint per SAMPLE_INTERVAL_S
                while len(pcm_buffer) < window_byte_count and not reached_eof:  # Fill the next complete analysis window
                    chunk = process.stdout.read(window_byte_count - len(pcm_buffer))  # Read only the missing PCM bytes
                    if not chunk:  # Detect FFmpeg EOF
                        reached_eof = True  # Stop future reads
                        break
                    pcm_buffer.extend(chunk)  # Append decoded PCM to the overlapping analysis buffer

                if not pcm_buffer:  # Stop when no PCM remains after EOF
                    break

                analysis_bytes = bytes(pcm_buffer[:window_byte_count])  # Copy the available bytes for one analysis window
                if len(analysis_bytes) < window_byte_count:  # Zero-pad the final partial analysis window deterministically
                    analysis_bytes += b"\x00" * (window_byte_count - len(analysis_bytes))  # Complete the last window

                samples = np.frombuffer(analysis_bytes, dtype="<i2").astype(np.float32) / 32768.0  # Convert signed 16-bit PCM into normalized floats
                fingerprints.append(build_audio_fingerprint(samples, hann_window, band_slices))  # Calculate one robust spectral fingerprint
                progress_bar.update(1)  # Advance the inline audio progress

                if len(pcm_buffer) <= hop_byte_count:  # Handle the final partial hop after EOF
                    pcm_buffer.clear()  # Remove all remaining bytes
                else:  # Preserve overlap between neighboring windows
                    del pcm_buffer[:hop_byte_count]  # Advance exactly SAMPLE_INTERVAL_S through the decoded soundtrack

                if reached_eof and not pcm_buffer:  # Stop after processing the final partial window
                    break
        finally:
            progress_bar.close()  # Finalize the inline audio progress row
            process.stdout.close()  # Close the PCM pipe

        return_code = process.wait()  # Wait for FFmpeg to terminate
        diagnostic_output = subprocess_error_text(error_file)  # Read captured FFmpeg diagnostics

    if return_code != 0:  # Reject incomplete FFmpeg audio extraction
        diagnostic_suffix = f"\n\nFFmpeg output:\n{diagnostic_output}" if diagnostic_output else ""  # Include available FFmpeg details
        raise RuntimeError(f"FFmpeg audio fingerprint extraction failed with exit code {return_code}.{diagnostic_suffix}")  # Surface the failure

    if not fingerprints:  # Require at least one decoded fingerprint
        raise RuntimeError(f"No audio fingerprints could be extracted from: {video_path}")  # Reject unusable audio input

    return normalize_rows(np.vstack(fingerprints))  # Return a consistently normalized audio fingerprint matrix


def resolve_effective_modalities(media_info: dict, video_path: Path) -> tuple[bool, bool]:
    """
    Resolves which requested modalities can actually be used for one input file.

    :param media_info: Probed media stream metadata.
    :param video_path: Input media path used in warnings and errors.
    :return: Tuple of effective video-enabled and audio-enabled flags.
    """

    effective_video = USE_VIDEO and bool(media_info.get("has_video"))  # Enable requested video analysis only when a video stream exists
    effective_audio = USE_AUDIO and bool(media_info.get("has_audio"))  # Enable requested audio analysis only when an audio stream exists

    if USE_VIDEO and not effective_video:  # Report a requested but unavailable video modality
        log_line(f"{BackgroundColors.YELLOW}Warning: no video stream available for video fingerprinting: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}")  # Keep other requested modalities available

    if USE_AUDIO and not effective_audio:  # Report a requested but unavailable audio modality
        log_line(f"{BackgroundColors.YELLOW}Warning: no audio stream available for audio fingerprinting: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}")  # Keep other requested modalities available

    if not effective_video and not effective_audio:  # Reject a file that cannot satisfy any enabled modality
        raise RuntimeError(f"No enabled comparison modality is available in: {video_path}")  # Prevent an empty fingerprint analysis

    return effective_video, effective_audio  # Return the usable modality configuration for this file


def align_fingerprint_matrices(video_features: np.ndarray | None, audio_features: np.ndarray | None) -> tuple[np.ndarray | None, np.ndarray | None, int]:
    """
    Aligns requested modality matrices to the same number of timeline samples.

    :param video_features: Video fingerprint matrix or None.
    :param audio_features: Audio fingerprint matrix or None.
    :return: Trimmed video matrix, trimmed audio matrix, and common sample count.
    """

    sample_counts = [matrix.shape[0] for matrix in (video_features, audio_features) if matrix is not None]  # Collect available modality lengths

    if not sample_counts:  # Guard against an impossible empty modality set
        raise RuntimeError("No fingerprint matrices were generated.")  # Reject analysis without fingerprints

    common_sample_count = min(sample_counts)  # Align modalities conservatively to their shared timeline length

    if video_features is not None:  # Trim video fingerprints to the shared sample count
        video_features = video_features[:common_sample_count]
    if audio_features is not None:  # Trim audio fingerprints to the shared sample count
        audio_features = audio_features[:common_sample_count]

    return video_features, audio_features, common_sample_count  # Return aligned modality matrices


def build_candidate_feature_matrix(video_features: np.ndarray | None, audio_features: np.ndarray | None) -> np.ndarray:
    """
    Builds a compact equal-modality-weight matrix for KD-tree candidate discovery.

    :param video_features: Aligned normalized video fingerprints or None.
    :param audio_features: Aligned normalized audio fingerprints or None.
    :return: Normalized compact candidate feature matrix.
    """

    modality_matrices: list[np.ndarray] = []  # Store compact enabled modality descriptors

    if video_features is not None:  # Include a compact visual descriptor when video analysis is enabled
        compact_video = video_features[:, :min(VIDEO_CANDIDATE_DIMENSIONS, video_features.shape[1])]  # Retain stable leading low-frequency visual dimensions
        modality_matrices.append(normalize_rows(compact_video))  # Normalize the compact visual descriptor independently

    if audio_features is not None:  # Include audio descriptors when audio analysis is enabled
        modality_matrices.append(normalize_rows(audio_features))  # Normalize audio independently so dimensions do not overwhelm video

    if not modality_matrices:  # Guard against a detector without features
        raise RuntimeError("No candidate feature modalities are available.")  # Reject impossible candidate discovery

    modality_scale = 1.0 / math.sqrt(len(modality_matrices))  # Give each enabled modality equal total influence
    weighted_matrices = [matrix * modality_scale for matrix in modality_matrices]  # Scale each modality before concatenation
    combined_matrix = np.concatenate(weighted_matrices, axis=1)  # Join enabled modality descriptors per timeline sample

    return normalize_rows(combined_matrix)  # Normalize the final KD-tree feature vectors


def sample_similarity(video_features: np.ndarray | None, audio_features: np.ndarray | None, first_index: int, second_index: int) -> float:
    """
    Calculates equal-modality-weight cosine similarity for two timeline samples.

    :param video_features: Normalized video fingerprints or None.
    :param audio_features: Normalized audio fingerprints or None.
    :param first_index: First timeline sample index.
    :param second_index: Second timeline sample index.
    :return: Similarity in the zero-to-one range.
    """

    similarities: list[float] = []  # Store enabled modality similarities

    if video_features is not None:  # Compare perceptual video structure
        video_similarity = float(np.dot(video_features[first_index], video_features[second_index]))  # Calculate cosine similarity
        similarities.append(min(1.0, max(0.0, video_similarity)))  # Clamp numerical noise

    if audio_features is not None:  # Compare normalized audio spectrum
        audio_similarity = float(np.dot(audio_features[first_index], audio_features[second_index]))  # Calculate cosine similarity
        similarities.append(min(1.0, max(0.0, audio_similarity)))  # Clamp numerical noise

    return sum(similarities) / len(similarities) if similarities else 0.0  # Return equal-modality average similarity


def discover_candidate_offsets(video_features: np.ndarray | None, audio_features: np.ndarray | None, minimum_samples: int) -> list[tuple[int, int]]:
    """
    Uses KD-tree nearest-neighbor voting to discover likely repeated temporal offsets.

    :param video_features: Normalized video fingerprints or None.
    :param audio_features: Normalized audio fingerprints or None.
    :param minimum_samples: Minimum duplicate length represented in timeline samples.
    :return: Candidate offsets paired with their vote counts, ordered strongest first.
    """

    candidate_matrix = build_candidate_feature_matrix(video_features, audio_features)  # Build compact equal-weight candidate descriptors
    sample_count = candidate_matrix.shape[0]  # Read the common timeline sample count

    if sample_count < minimum_samples * 2:  # Non-overlapping duplicate subsections cannot fit inside a shorter timeline
        return []  # Stop before unnecessary nearest-neighbor work

    neighbor_count = min(MAX_NEIGHBORS_PER_SAMPLE + 1, sample_count)  # Include self plus the configured number of neighbors
    tree = cKDTree(candidate_matrix)  # Build one efficient nearest-neighbor index
    _, neighbor_indices = tree.query(candidate_matrix, k=neighbor_count)  # Query nearest candidate samples for the complete timeline

    if neighbor_count == 1:  # Normalize cKDTree's one-neighbor shape defensively
        neighbor_indices = neighbor_indices.reshape(-1, 1)  # Convert one-dimensional results into rows

    candidate_threshold = max(0.0, (CONFIDENCE_PERCENTAGE - CANDIDATE_CONFIDENCE_MARGIN_PERCENTAGE) / 100.0)  # Use a looser candidate threshold than final validation
    offset_votes: Counter[int] = Counter()  # Count how many similar samples support each temporal offset
    progress_bar = tqdm(  # Render one inline candidate-discovery progress bar
        range(sample_count), total=sample_count,
        desc=f"{BackgroundColors.GREEN}Finding candidate offsets{BackgroundColors.GREEN}",
        unit="sample", dynamic_ncols=True, colour="green", file=sys.__stdout__, mininterval=0.2,
    )

    for first_index in progress_bar:  # Inspect nearest neighbors for every timeline sample
        for second_index_value in np.atleast_1d(neighbor_indices[first_index]):  # Inspect each nearby feature vector
            second_index = int(second_index_value)  # Normalize numpy integer types
            if second_index <= first_index:  # Ignore self and mirrored duplicate pairs
                continue
            offset = second_index - first_index  # Convert the pair into a stable temporal sample offset
            if offset < minimum_samples:  # Require enough separation for non-overlapping minimum-length duplicates
                continue
            similarity = sample_similarity(video_features, audio_features, first_index, second_index)  # Validate actual modalities
            if similarity < candidate_threshold:  # Ignore weak nearest-neighbor coincidences
                continue
            offset_votes[offset] += 1  # Add one vote for this likely repeated temporal alignment

    minimum_votes = max(4, math.ceil(minimum_samples / 3))  # Require repeated support across a meaningful fraction of the minimum subsection
    ranked_offsets = [(offset, votes) for offset, votes in offset_votes.most_common() if votes >= minimum_votes]  # Retain supported offsets

    return ranked_offsets[:MAX_CANDIDATE_OFFSETS]  # Limit expensive full-offset validation to the strongest candidates


def offset_similarity_arrays(video_features: np.ndarray | None, audio_features: np.ndarray | None, offset: int) -> tuple[np.ndarray, np.ndarray | None, np.ndarray | None]:
    """
    Calculates timeline-wide similarity arrays for one candidate temporal offset.

    :param video_features: Normalized video fingerprints or None.
    :param audio_features: Normalized audio fingerprints or None.
    :param offset: Positive sample offset between possible repeated subsections.
    :return: Combined, video-only, and audio-only similarity arrays.
    """

    modality_arrays: list[np.ndarray] = []  # Store enabled similarity vectors
    video_similarity: np.ndarray | None = None  # Initialize optional video similarity output
    audio_similarity: np.ndarray | None = None  # Initialize optional audio similarity output

    if video_features is not None:  # Calculate vectorized visual similarities
        video_similarity = np.sum(video_features[:-offset] * video_features[offset:], axis=1)  # Compute cosine similarity at this offset
        video_similarity = np.clip(video_similarity, 0.0, 1.0).astype(np.float32)  # Clamp numerical noise
        modality_arrays.append(video_similarity)  # Include video in the equal-weight combined score

    if audio_features is not None:  # Calculate vectorized audio similarities
        audio_similarity = np.sum(audio_features[:-offset] * audio_features[offset:], axis=1)  # Compute cosine similarity at this offset
        audio_similarity = np.clip(audio_similarity, 0.0, 1.0).astype(np.float32)  # Clamp numerical noise
        modality_arrays.append(audio_similarity)  # Include audio in the equal-weight combined score

    if not modality_arrays:  # Guard against an impossible empty modality set
        raise RuntimeError("No modality similarity arrays are available.")  # Reject invalid offset validation

    combined_similarity = np.mean(np.vstack(modality_arrays), axis=0).astype(np.float32)  # Average enabled modality confidence equally
    return combined_similarity, video_similarity, audio_similarity  # Return all requested confidence timelines


def contiguous_groups(indices: np.ndarray, maximum_gap_samples: int) -> list[tuple[int, int]]:
    """
    Groups sorted qualifying window starts while tolerating small gaps.

    :param indices: Sorted qualifying rolling-window start indices.
    :param maximum_gap_samples: Maximum missing starts tolerated inside one group.
    :return: Inclusive start-index groups.
    """

    if indices.size == 0:  # Handle no qualifying windows
        return []  # Return no groups

    groups: list[tuple[int, int]] = []  # Store grouped qualifying start ranges
    group_start = int(indices[0])  # Initialize the first group
    previous_index = int(indices[0])  # Track the previous qualifying start

    for current_value in indices[1:]:  # Inspect remaining qualifying starts
        current_index = int(current_value)  # Normalize numpy integer type
        missing_starts = current_index - previous_index - 1  # Count non-qualifying starts between matches
        if missing_starts > maximum_gap_samples:  # Close a group when the gap exceeds tolerance
            groups.append((group_start, previous_index))  # Preserve the completed inclusive range
            group_start = current_index  # Start a new group
        previous_index = current_index  # Advance the previous qualifying start

    groups.append((group_start, previous_index))  # Preserve the final group
    return groups  # Return all grouped qualifying rolling-window starts


def format_timestamp(seconds: float) -> str:
    """
    Formats seconds as HH:MM:SS.mmm.

    :param seconds: Non-negative timeline timestamp in seconds.
    :return: Human-readable timestamp.
    """

    safe_seconds = max(0.0, float(seconds))  # Clamp negative numerical drift
    hours = int(safe_seconds // 3600)  # Calculate full hours
    minutes = int((safe_seconds % 3600) // 60)  # Calculate remaining full minutes
    remaining_seconds = safe_seconds % 60  # Preserve fractional seconds

    return f"{hours:02d}:{minutes:02d}:{remaining_seconds:06.3f}"  # Return a fixed-width millisecond timestamp


def build_duplicate_record(start_sample: int, end_sample: int, offset: int, combined_similarity: np.ndarray, video_similarity: np.ndarray | None, audio_similarity: np.ndarray | None, duration_s: float) -> dict:
    """
    Builds one JSON-serializable duplicate subsection record.

    :param start_sample: First subsection start sample.
    :param end_sample: Exclusive first subsection end sample.
    :param offset: Positive sample offset to the second subsection.
    :param combined_similarity: Combined similarity timeline at this offset.
    :param video_similarity: Optional video similarity timeline.
    :param audio_similarity: Optional audio similarity timeline.
    :param duration_s: Complete input media duration.
    :return: Duplicate subsection result dictionary.
    """

    first_start_s = start_sample * SAMPLE_INTERVAL_S  # Convert first sample index into timeline seconds
    duplicate_duration_s = (end_sample - start_sample) * SAMPLE_INTERVAL_S  # Convert the validated sample span into seconds
    second_start_s = (start_sample + offset) * SAMPLE_INTERVAL_S  # Calculate the repeated occurrence start
    first_end_s = min(duration_s, first_start_s + duplicate_duration_s)  # Clamp the first range to media duration
    second_end_s = min(duration_s, second_start_s + duplicate_duration_s)  # Clamp the second range to media duration
    actual_duration_s = min(first_end_s - first_start_s, second_end_s - second_start_s)  # Preserve a common non-truncated duration
    slice_end = min(end_sample, combined_similarity.shape[0])  # Clamp confidence slicing to the available comparison timeline
    combined_confidence = float(np.mean(combined_similarity[start_sample:slice_end])) * 100.0  # Calculate average combined similarity
    video_confidence = float(np.mean(video_similarity[start_sample:slice_end])) * 100.0 if video_similarity is not None else None  # Optional visual confidence
    audio_confidence = float(np.mean(audio_similarity[start_sample:slice_end])) * 100.0 if audio_similarity is not None else None  # Optional audio confidence

    return {  # Build the complete duplicate subsection report record
        "first": {
            "start_s": round(first_start_s, 3), "end_s": round(first_start_s + actual_duration_s, 3),
            "start": format_timestamp(first_start_s), "end": format_timestamp(first_start_s + actual_duration_s),
        },
        "second": {
            "start_s": round(second_start_s, 3), "end_s": round(second_start_s + actual_duration_s, 3),
            "start": format_timestamp(second_start_s), "end": format_timestamp(second_start_s + actual_duration_s),
        },
        "duration_s": round(actual_duration_s, 3),
        "time_offset_s": round(offset * SAMPLE_INTERVAL_S, 3),
        "confidence_percent": round(combined_confidence, 3),
        "video_confidence_percent": round(video_confidence, 3) if video_confidence is not None else None,
        "audio_confidence_percent": round(audio_confidence, 3) if audio_confidence is not None else None,
    }


def validate_candidate_offset(video_features: np.ndarray | None, audio_features: np.ndarray | None, offset: int, minimum_samples: int, duration_s: float) -> list[dict]:
    """
    Fully validates one candidate temporal offset and returns qualifying repeated ranges.

    :param video_features: Normalized video fingerprints or None.
    :param audio_features: Normalized audio fingerprints or None.
    :param offset: Positive candidate sample offset.
    :param minimum_samples: Minimum duplicate duration represented in samples.
    :param duration_s: Complete input media duration.
    :return: Duplicate subsection records found at this offset.
    """

    combined_similarity, video_similarity, audio_similarity = offset_similarity_arrays(video_features, audio_features, offset)  # Calculate full temporal confidence
    if combined_similarity.shape[0] < minimum_samples:  # Require at least one complete minimum-sized comparison window
        return []  # Stop when this offset cannot fit a qualifying subsection

    threshold = CONFIDENCE_PERCENTAGE / 100.0  # Convert the final confidence threshold into a zero-to-one score
    cumulative = np.concatenate((np.array([0.0], dtype=np.float64), np.cumsum(combined_similarity, dtype=np.float64)))  # Build cumulative similarity
    rolling_means = (cumulative[minimum_samples:] - cumulative[:-minimum_samples]) / minimum_samples  # Calculate every minimum-length window average
    qualifying_starts = np.flatnonzero(rolling_means >= threshold)  # Locate windows that satisfy the requested average confidence
    if qualifying_starts.size == 0:  # Stop when no minimum-sized region reaches the threshold
        return []

    maximum_gap_samples = max(0, int(round(MAX_WINDOW_GAP_S / SAMPLE_INTERVAL_S)))  # Convert merge-gap tolerance into sample starts
    grouped_windows = contiguous_groups(qualifying_starts, maximum_gap_samples)  # Merge neighboring qualifying minimum windows
    duplicate_records: list[dict] = []  # Store validated ranges at this offset

    for group_start, group_last_start in grouped_windows:  # Convert each group into a maximal candidate subsection
        start_sample = group_start  # Start at the first qualifying minimum window
        end_sample = group_last_start + minimum_samples  # End after the final qualifying minimum window
        end_sample = min(end_sample, start_sample + offset)  # Prevent first and second reported occurrences from overlapping
        if end_sample - start_sample < minimum_samples:  # Reject a group shortened below the configured minimum
            continue

        boundary_threshold = max(0.70, threshold - 0.05)  # Use a slightly softer per-sample boundary rule while preserving the configured average threshold

        while end_sample - start_sample > minimum_samples and combined_similarity[start_sample] < boundary_threshold:  # Remove weak leading samples admitted only by rolling-window averaging
            start_sample += 1  # Tighten the first occurrence boundary by one fingerprint interval

        while end_sample - start_sample > minimum_samples and combined_similarity[end_sample - 1] < boundary_threshold:  # Remove weak trailing samples admitted only by rolling-window averaging
            end_sample -= 1  # Tighten the subsection end by one fingerprint interval

        subsection_average = float(np.mean(combined_similarity[start_sample:end_sample]))  # Validate the trimmed subsection's complete average confidence
        if subsection_average < threshold:  # Fall back to the strongest minimum window when the merged group becomes too weak
            local_start_candidates = qualifying_starts[(qualifying_starts >= group_start) & (qualifying_starts <= group_last_start)]  # Restrict valid starts
            if local_start_candidates.size == 0:  # Guard against an impossible empty grouped selection
                continue
            best_start = int(max(local_start_candidates, key=lambda index: float(rolling_means[int(index)])))  # Select the highest-confidence minimum window
            start_sample = best_start  # Use the strongest exact qualifying start
            end_sample = best_start + minimum_samples  # Preserve the configured minimum duration

        record = build_duplicate_record(start_sample, end_sample, offset, combined_similarity, video_similarity, audio_similarity, duration_s)  # Build one result
        if record["duration_s"] + 1e-9 < MINIMUM_SUBSECTION_SIZE_S:  # Guard against end-of-file truncation below the minimum
            continue
        if record["confidence_percent"] + 1e-9 < CONFIDENCE_PERCENTAGE:  # Enforce final configured confidence
            continue
        duplicate_records.append(record)  # Preserve the fully validated repeated subsection

    return duplicate_records  # Return all qualifying ranges at this temporal offset


def interval_overlap_ratio(first_start: float, first_end: float, second_start: float, second_end: float) -> float:
    """
    Calculates overlap relative to the shorter of two intervals.

    :param first_start: First interval start.
    :param first_end: First interval end.
    :param second_start: Second interval start.
    :param second_end: Second interval end.
    :return: Overlap ratio in the zero-to-one range.
    """

    overlap = max(0.0, min(first_end, second_end) - max(first_start, second_start))  # Calculate intersecting duration
    shorter_duration = max(0.0, min(first_end - first_start, second_end - second_start))  # Calculate the shorter interval duration
    return overlap / shorter_duration if shorter_duration > 0 else 0.0  # Avoid division by zero


def duplicate_records_are_equivalent(first_record: dict, second_record: dict) -> bool:
    """
    Determines whether two detections represent the same repeated subsection pair.

    :param first_record: Existing duplicate record.
    :param second_record: Candidate duplicate record.
    :return: True when both occurrence ranges substantially describe the same pair.
    """

    first_occurrence_overlap = interval_overlap_ratio(  # Compare the first reported occurrence ranges
        first_record["first"]["start_s"], first_record["first"]["end_s"],
        second_record["first"]["start_s"], second_record["first"]["end_s"],
    )
    second_occurrence_overlap = interval_overlap_ratio(  # Compare the second reported occurrence ranges
        first_record["second"]["start_s"], first_record["second"]["end_s"],
        second_record["second"]["start_s"], second_record["second"]["end_s"],
    )
    near_same_starts = (  # Treat sub-sample start jitter as equivalent
        abs(first_record["first"]["start_s"] - second_record["first"]["start_s"]) <= SAMPLE_INTERVAL_S * 1.5
        and abs(first_record["second"]["start_s"] - second_record["second"]["start_s"]) <= SAMPLE_INTERVAL_S * 1.5
    )
    return near_same_starts or (first_occurrence_overlap >= 0.80 and second_occurrence_overlap >= 0.80)  # Collapse redundant nearby-offset detections


def deduplicate_duplicate_records(records: list[dict]) -> list[dict]:
    """
    Removes redundant nearby-offset detections while preserving genuine multiple occurrences.

    :param records: Raw validated duplicate subsection records.
    :return: Deduplicated records ordered by timeline.
    """

    ranked_records = sorted(records, key=lambda record: (-record["duration_s"], -record["confidence_percent"]))  # Prefer longer, stronger detections
    selected_records: list[dict] = []  # Store non-redundant duplicate pairs

    for candidate in ranked_records:  # Inspect strongest detections first
        if any(duplicate_records_are_equivalent(existing, candidate) for existing in selected_records):  # Skip an already represented detection
            continue
        selected_records.append(candidate)  # Preserve the distinct duplicate pair
        if len(selected_records) >= MAX_REPORTED_DUPLICATES_PER_FILE:  # Enforce the pathological-output safety cap
            break

    return sorted(selected_records, key=lambda record: (record["first"]["start_s"], record["second"]["start_s"], -record["duration_s"]))  # Return chronological output


def find_duplicate_subsections(video_features: np.ndarray | None, audio_features: np.ndarray | None, duration_s: float) -> list[dict]:
    """
    Finds all validated repeated subsections from aligned video and/or audio fingerprints.

    :param video_features: Aligned normalized video fingerprints or None.
    :param audio_features: Aligned normalized audio fingerprints or None.
    :param duration_s: Complete input media duration.
    :return: Deduplicated repeated subsection records.
    """

    base_features = video_features if video_features is not None else audio_features  # Select one guaranteed available aligned modality
    if base_features is None:  # Guard against impossible empty input
        return []
    sample_count = base_features.shape[0]  # Read the shared aligned timeline length
    minimum_samples = max(1, math.ceil(MINIMUM_SUBSECTION_SIZE_S / SAMPLE_INTERVAL_S))  # Convert minimum duration into samples
    if sample_count < minimum_samples * 2:  # Require room for two non-overlapping minimum-sized subsections
        return []  # Report no duplicates without candidate discovery

    candidate_offsets = discover_candidate_offsets(video_features, audio_features, minimum_samples)  # Identify likely repeated alignments
    if not candidate_offsets:  # Stop when no temporal offset has enough matching evidence
        return []

    raw_records: list[dict] = []  # Collect validated records before nearby-offset deduplication
    progress_bar = tqdm(  # Render one inline full-validation progress bar
        candidate_offsets, total=len(candidate_offsets),
        desc=f"{BackgroundColors.GREEN}Validating candidate offsets{BackgroundColors.GREEN}",
        unit="offset", dynamic_ncols=True, colour="green", file=sys.__stdout__, mininterval=0.2,
    )

    for offset, _votes in progress_bar:  # Fully validate each strongest candidate temporal offset
        raw_records.extend(validate_candidate_offset(video_features, audio_features, offset, minimum_samples, duration_s))  # Preserve qualifying ranges

    return deduplicate_duplicate_records(raw_records)  # Collapse redundant detections and return chronological results


def sanitize_report_component(value: str) -> str:
    """
    Sanitizes one path-derived report filename component.

    :param value: Raw path-derived name.
    :return: Filesystem-safe report component.
    """

    sanitized = re.sub(r'[\\/:*?"<>|]+', "-", value)  # Replace Windows-invalid path and filename characters
    sanitized = re.sub(r"\s+", " ", sanitized).strip()  # Collapse repeated whitespace
    sanitized = re.sub(r"-+", "-", sanitized).strip("-")  # Collapse repeated separators
    return sanitized or "video"  # Return a deterministic fallback


def build_report_path(video_path: Path) -> Path:
    """
    Builds a collision-resistant report path for one input video.

    :param video_path: Input video file.
    :return: JSON report path beneath OUTPUT_DIR.
    """

    try:  # Prefer a relative path when processing files beneath INPUT_DIR
        relative_path = video_path.resolve().relative_to(Path(INPUT_DIR).expanduser().resolve())  # Derive input-root-relative path
        report_source = str(relative_path.with_suffix(""))  # Include subdirectories to avoid same-stem collisions
    except (ValueError, OSError):  # Handle explicit files outside INPUT_DIR
        report_source = video_path.stem  # Use the explicit input filename stem

    report_name = sanitize_report_component(report_source)  # Sanitize the path-derived report identity
    return OUTPUT_DIR / f"{report_name}-duplicates.json"  # Return the per-video JSON report destination


def write_json_report(report_path: Path, report_data: dict) -> None:
    """
    Atomically writes one UTF-8 JSON report.

    :param report_path: Final report destination.
    :param report_data: JSON-serializable report dictionary.
    :return: None
    """

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # Ensure the output directory exists
    temporary_path = report_path.with_suffix(f"{report_path.suffix}.tmp")  # Build a neighboring temporary path for atomic replacement
    with temporary_path.open("w", encoding="utf-8") as report_file:  # Write a complete temporary JSON document first
        json.dump(report_data, report_file, ensure_ascii=False, indent=4)  # Preserve Unicode filenames and readable indentation
        report_file.write("\n")  # Finish with a conventional trailing newline
    os.replace(temporary_path, report_path)  # Atomically replace any prior report only after successful serialization


def process_video(ffmpeg_executable: str, ffprobe_executable: str, video_path: Path) -> Path:
    """
    Extracts fingerprints, finds duplicate subsections, and writes one video report.

    :param ffmpeg_executable: Resolved FFmpeg executable path.
    :param ffprobe_executable: Resolved FFprobe executable path.
    :param video_path: Input video file.
    :return: Generated JSON report path.
    """

    started_at = datetime.datetime.now()  # Capture the per-video processing start time
    log_line(f"{BackgroundColors.GREEN}Processing: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}")  # Announce the current input video
    media_info = probe_media(ffprobe_executable, video_path)  # Read media duration and stream availability
    effective_video, effective_audio = resolve_effective_modalities(media_info, video_path)  # Resolve usable requested modalities
    duration_s = float(media_info["duration_s"])  # Normalize the probed duration
    video_features: np.ndarray | None = None  # Initialize optional video fingerprints
    audio_features: np.ndarray | None = None  # Initialize optional audio fingerprints

    if effective_video:  # Extract perceptual visual information when enabled and available
        video_features = extract_video_fingerprints(ffmpeg_executable, video_path, duration_s)  # Decode and fingerprint the video timeline
    if effective_audio:  # Extract normalized spectral information when enabled and available
        audio_features = extract_audio_fingerprints(ffmpeg_executable, video_path, duration_s)  # Decode and fingerprint the audio timeline

    video_features, audio_features, sample_count = align_fingerprint_matrices(video_features, audio_features)  # Align enabled modality timelines
    duplicates = find_duplicate_subsections(video_features, audio_features, duration_s)  # Find validated repeated subsection pairs
    finished_at = datetime.datetime.now()  # Capture the per-video processing finish time
    report_path = build_report_path(video_path)  # Resolve the collision-resistant report destination
    report_data = {  # Build a self-describing duplicate detection report
        "video_file": str(video_path),
        "duration_s": round(duration_s, 3),
        "duration": format_timestamp(duration_s),
        "configuration": {
            "use_video_requested": USE_VIDEO,
            "use_audio_requested": USE_AUDIO,
            "use_video_effective": effective_video,
            "use_audio_effective": effective_audio,
            "minimum_subsection_size_s": MINIMUM_SUBSECTION_SIZE_S,
            "confidence_percentage": CONFIDENCE_PERCENTAGE,
            "sample_interval_s": SAMPLE_INTERVAL_S,
            "audio_window_size_s": AUDIO_WINDOW_SIZE_S,
        },
        "sample_count": sample_count,
        "duplicate_count": len(duplicates),
        "duplicates": duplicates,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "execution_time": calculate_execution_time(started_at, finished_at),
    }
    write_json_report(report_path, report_data)  # Persist the completed result atomically

    log_line(  # Output one concise per-video summary
        f"{BackgroundColors.GREEN}Finished: {BackgroundColors.CYAN}{video_path.name}{BackgroundColors.GREEN} | "
        f"Duplicates: {BackgroundColors.CYAN}{len(duplicates)}{BackgroundColors.GREEN} | "
        f"Report: {BackgroundColors.CYAN}{report_path}{Style.RESET_ALL}"
    )

    for duplicate_index, duplicate in enumerate(duplicates, start=1):  # Display concise human-readable duplicate ranges
        log_line(
            f"{BackgroundColors.GREEN}Duplicate {duplicate_index}: "
            f"{BackgroundColors.CYAN}{duplicate['first']['start']} - {duplicate['first']['end']}"
            f"{BackgroundColors.GREEN} <-> "
            f"{BackgroundColors.CYAN}{duplicate['second']['start']} - {duplicate['second']['end']}"
            f"{BackgroundColors.GREEN} | Duration: {BackgroundColors.CYAN}{duplicate['duration_s']:.3f}s"
            f"{BackgroundColors.GREEN} | Confidence: {BackgroundColors.CYAN}{duplicate['confidence_percent']:.3f}%"
            f"{Style.RESET_ALL}"
        )

    return report_path  # Return the generated report path


def verify_filepath_exists(filepath):
    """
    Verify if a file or folder exists at the specified path.

    :param filepath: Path to the file or folder
    :return: True if the file or folder exists, False otherwise
    """

    try:  # Wrap existence verification safely
        return bool(filepath) and Path(filepath).expanduser().exists()  # Return whether the normalized path exists
    except (OSError, TypeError, ValueError):  # Handle malformed or inaccessible paths
        return False  # Report an unavailable path safely


def to_seconds(obj):
    """
    Converts various time-like objects to seconds.

    :param obj: The object to convert (can be int, float, timedelta, datetime, etc.)
    :return: The equivalent time in seconds as a float, or None if conversion fails
    """

    if obj is None:  # None can't be converted
        return None  # Signal failure to convert
    if isinstance(obj, (int, float)):  # Already numeric (seconds or timestamp)
        return float(obj)  # Return as float seconds
    if hasattr(obj, "total_seconds"):  # Timedelta-like objects
        try:
            return float(obj.total_seconds())  # Use the total_seconds() method
        except Exception:
            pass  # Fallthrough on error
    if hasattr(obj, "timestamp"):  # Datetime-like objects
        try:
            return float(obj.timestamp())  # Use timestamp() to get seconds since epoch
        except Exception:
            pass  # Fallthrough on error
    return None  # Couldn't convert


def calculate_execution_time(start_time, finish_time=None):
    """
    Calculates the execution time and returns a human-readable string.

    :param start_time: Start datetime, duration-like object, or numeric seconds.
    :param finish_time: Optional finish datetime or numeric seconds.
    :return: Human-readable elapsed time.
    """

    if finish_time is None:  # Single-argument mode
        total_seconds = to_seconds(start_time)  # Try to convert provided value to seconds
        if total_seconds is None:  # Conversion failed
            try:
                total_seconds = float(start_time)  # Attempt numeric coercion
            except Exception:
                total_seconds = 0.0  # Fallback to zero
    else:  # Two-argument mode
        st = to_seconds(start_time)  # Convert start to seconds if possible
        ft = to_seconds(finish_time)  # Convert finish to seconds if possible
        if st is not None and ft is not None:  # Both converted successfully
            total_seconds = ft - st  # Direct numeric subtraction
        else:
            try:
                delta = finish_time - start_time  # Try subtracting datetimes/timedeltas
                total_seconds = float(delta.total_seconds())  # Get seconds from resulting timedelta
            except Exception:
                try:
                    total_seconds = float(finish_time) - float(start_time)  # Final numeric coercion attempt
                except Exception:
                    total_seconds = 0.0  # Fallback to zero

    total_seconds = abs(float(total_seconds or 0.0))  # Normalize missing or negative durations
    days = int(total_seconds // 86400)  # Compute full days
    hours = int((total_seconds % 86400) // 3600)  # Compute remaining hours
    minutes = int((total_seconds % 3600) // 60)  # Compute remaining minutes
    seconds = int(total_seconds % 60)  # Compute remaining seconds

    if days > 0:
        return f"{days}d {hours}h {minutes}m {seconds}s"
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def play_sound():
    """
    Plays a sound when the program finishes and skips if the operating system is Windows.

    :param: None
    :return: None
    """

    current_os = platform.system()  # Get the operating system
    if current_os == "Windows":  # Preserve the repository template's Windows behavior
        return  # Do nothing on Windows

    if verify_filepath_exists(SOUND_FILE):  # If the sound file exists
        if current_os in SOUND_COMMANDS:  # If the operating system has a configured playback command
            os.system(f'{SOUND_COMMANDS[current_os]} "{SOUND_FILE}"')  # Play the sound
        else:  # If no playback command exists for this operating system
            log_line(f"{BackgroundColors.RED}The {BackgroundColors.CYAN}{current_os}{BackgroundColors.RED} is not in the SOUND_COMMANDS dictionary.{Style.RESET_ALL}")
    else:  # If the sound file does not exist
        verbose_output(true_string=f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found.{Style.RESET_ALL}")


def main():
    """
    Main function.

    :param: None
    :return: None
    """

    log_line(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the "
        f"{BackgroundColors.CYAN}Video Duplicate Segments Finder{BackgroundColors.GREEN} program!{Style.RESET_ALL}"
    )  # Output the welcome message
    log_line()  # Keep one intentional blank line after the welcome message

    start_time = datetime.datetime.now()  # Get the start time of the program
    validate_configuration()  # Validate detector constants before expensive media processing
    cli_video_file = parse_cli_video_file()  # Read an optional command-line single-video override
    input_videos = collect_input_videos(cli_video_file)  # Resolve the complete input workload

    if not input_videos:  # Reject an empty default input directory explicitly
        raise RuntimeError(f"No supported video files found under INPUT_DIR: {INPUT_DIR}")  # Prevent a silent no-op run

    ffmpeg_executable = resolve_executable(FFMPEG)  # Resolve FFmpeg once for all input files
    ffprobe_executable = resolve_executable(FFPROBE)  # Resolve FFprobe once for all input files
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)  # Ensure reports can be written
    generated_reports: list[Path] = []  # Store successfully generated report paths
    processing_errors: list[str] = []  # Aggregate per-video failures without abandoning remaining files

    log_line(
        f"{BackgroundColors.GREEN}Input videos: {BackgroundColors.CYAN}{len(input_videos)}{BackgroundColors.GREEN} | "
        f"USE_VIDEO: {BackgroundColors.CYAN}{USE_VIDEO}{BackgroundColors.GREEN} | "
        f"USE_AUDIO: {BackgroundColors.CYAN}{USE_AUDIO}{BackgroundColors.GREEN} | "
        f"Minimum subsection: {BackgroundColors.CYAN}{MINIMUM_SUBSECTION_SIZE_S:.3f}s{BackgroundColors.GREEN} | "
        f"Confidence: {BackgroundColors.CYAN}{CONFIDENCE_PERCENTAGE:.3f}%{Style.RESET_ALL}"
    )  # Display the configured workload
    log_line()  # Separate configuration from processing

    for video_index, video_path in enumerate(input_videos, start=1):  # Process every resolved input video independently
        log_line(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}[{video_index}/{len(input_videos)}] {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}")  # Display current file position
        try:
            generated_reports.append(process_video(ffmpeg_executable, ffprobe_executable, video_path))  # Analyze and report one complete input video
        except Exception as exception:  # Aggregate the failed video with diagnostic context
            processing_errors.append(f"{video_path}\n{type(exception).__name__}: {exception}")  # Preserve the affected file and error
            log_line(f"{BackgroundColors.RED}Failed: {BackgroundColors.CYAN}{video_path}{Style.RESET_ALL}")  # Report the failed video immediately
            log_line(f"{BackgroundColors.RED}{type(exception).__name__}: {BackgroundColors.CYAN}{exception}{Style.RESET_ALL}")  # Report the concrete failure
        finally:
            log_line()  # Separate input files with exactly one blank line

    finish_time = datetime.datetime.now()  # Get the finish time of the program
    log_line(f"{BackgroundColors.GREEN}Generated reports: {BackgroundColors.CYAN}{len(generated_reports)}{BackgroundColors.GREEN} | Failed videos: {BackgroundColors.CYAN}{len(processing_errors)}{Style.RESET_ALL}")  # Output final totals

    for report_path in generated_reports:  # Display every successfully generated report path
        log_line(f"{BackgroundColors.GREEN}Report: {BackgroundColors.CYAN}{report_path}{Style.RESET_ALL}")  # Output one report path

    if processing_errors:  # Print complete aggregated error details after every video has been attempted
        log_line()  # Separate successful report paths from the error summary
        log_line(f"{BackgroundColors.RED}Finished with errors:{Style.RESET_ALL}")  # Announce the aggregated failures
        for error in processing_errors:  # Output every complete video failure
            log_line(f"{BackgroundColors.RED}---{Style.RESET_ALL}")  # Separate error entries
            log_line(error)  # Preserve multiline diagnostic content

    log_line()  # Separate processing results from timing
    log_line(
        f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n"
        f"{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n"
        f"{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"
    )  # Output the start and finish times
    log_line(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}")  # Output the end of the program message

    (atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None)  # Register the play_sound function


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
