"""
================================================================================
Audio Track Muxer
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-07-12
Description :
    Muxes video, English audio, attachments, chapters, and non-forced subtitles
    from higher-quality target media files with PT-BR audio from matching lower-
    quality original media files. Matching target external SRT files are copied
    beside each generated output.

    Key features include:
        - Direct movie pairing and season/episode matching across configured roots.
        - Season matching for names such as "Season 02" and "S02".
        - Episode matching for names such as "01.mp4" and "S02E01 - Title.mkv".
        - Higher-quality target English audio preservation with PT-BR audio injection.
        - Non-forced target subtitle preservation with normalized metadata.
        - External target SRT discovery, collision-safe naming, and metadata copying.
        - Dedicated output root to avoid consuming target-drive free space.
        - Optional post-success deletion of processed target and/or original source media files.
        - Dry-run support, overwrite control, erasure-aware storage preflight, and partial-output cleanup.

Usage:
    1. Configure ORIGINAL_ROOT, TARGET_ROOT, OUTPUT_ROOT, DRY_RUN, OVERWRITE,
       ERASE_TARGET_FILES, ERASE_ORIGINAL_FILES, and the optional
       FALLBACK_ORIGINAL_AUDIO_ORDER value.
    2. Ensure FFmpeg and FFprobe are available through FFMPEG and FFPROBE.
    3. Execute the script with: python main.py

Outputs:
    - One <media>-updated.mkv file under OUTPUT_ROOT for each matched target media file.
    - Series outputs preserve the target season directory name under OUTPUT_ROOT.
    - Matching target external SRT files are copied beside each generated MKV output.

Dependencies:
    - Python >= 3.10.
    - FFmpeg.
    - FFprobe.

Assumptions & Notes:
    - Movie roots may contain one supported media file directly in each configured
      root; those files are paired even when their filenames and extensions differ.
    - Series season directory names may use forms such as "Season 02" or "S02".
    - Series episode filenames may use numeric forms such as "01.mp4" or explicit
      forms such as "Breaking Bad - S02E01 - Seven Thirty-Seven.mkv".
    - Only seasons and episodes present in both roots are processed.
    - The higher-quality target provides video and English audio; the original source
      provides PT-BR audio. Existing target English audio is never replaced by the
      lower-quality original English audio.
    - FALLBACK_ORIGINAL_AUDIO_ORDER is used only when PT-BR cannot be identified
      from original-source audio metadata.
    - Generated media always uses MKV so copied video, audio, subtitle, attachment,
      and chapter streams are not constrained by the target input container format.
    - Generated media is written under OUTPUT_ROOT, which may be located on the same
      filesystem as either source root or on a different filesystem entirely.
    - ERASE_TARGET_FILES and ERASE_ORIGINAL_FILES delete only the matched source media
      files after FFmpeg succeeds, the generated output is validated, and target SRT
      copying completes successfully. Sidecar files and source directories are preserved.
    - Source-file deletion is disabled during DRY_RUN and never occurs when an existing
      output is skipped because OVERWRITE is disabled.
    - Storage preflight simulates sequential processing and credits ERASE_TARGET_FILES or
      ERASE_ORIGINAL_FILES only when that source occupies the same filesystem as OUTPUT_ROOT.
      A source on another drive does not reduce the free-space requirement of the output drive.
    - Source erasure is credited only after the current output has been fully generated and
      validated, so the output filesystem must always be able to hold the next complete output.
"""

import json  # Parse FFprobe JSON output.
import re  # Match season numbers and normalized language tokens.
import shutil  # Copy external subtitle files with metadata preservation.
import subprocess  # Execute FFmpeg and FFprobe commands.
import unicodedata  # Remove diacritics from language and track metadata.
from pathlib import Path  # Represent configured directories and media paths.
from typing import Any, Literal, cast  # Define precise JSON and language types.


# Macros:

LanguageClass = Literal["english", "ptbr"]  # Restrict supported audio language classes.
FallbackAudioOrder = tuple[LanguageClass, LanguageClass] | None  # Define the optional source audio order.
Stream = dict[str, Any]  # Represent one FFprobe stream dictionary.
MediaInfo = dict[str, Any]  # Represent parsed FFprobe media information.
MatchedMediaPair = tuple[Path, Path, Path]  # Represent target media, matching original media, and the generated output path.

ORIGINAL_ROOT = Path(r"G:\\Series\\Breaking Bad")  # Preserve the configured lower-quality Dual source root providing PT-BR audio.
ERASE_ORIGINAL_FILES = False  # Set to True to delete each processed lower-quality original media file only after its new output is safely generated.
TARGET_ROOT = Path(r"D:\\Sem Backup\\Download\\Torrent\\Completed\\Breaking Bad 1080p")  # Preserve the configured higher-quality target root providing video and English audio.
ERASE_TARGET_FILES = False  # Set to True to delete each processed higher-quality target media file only after its new output is safely generated.
OUTPUT_ROOT = Path(r"G:\\Series\\Breaking Bad 1080p Dual")  # Store generated high-quality Dual outputs on G: instead of consuming limited D: free space.
FFMPEG = "ffmpeg"  # Select the configured FFmpeg executable.
FFPROBE = "ffprobe"  # Select the configured FFprobe executable.
UPDATED_SUFFIX = "-updated"  # Append the configured suffix to generated MKV files.
DRY_RUN = False  # Execute commands instead of only printing planned operations.
OVERWRITE = False  # Preserve existing generated outputs when disabled.
FALLBACK_ORIGINAL_AUDIO_ORDER: FallbackAudioOrder = None  # Preserve automatic PT-BR source-audio detection by default.
MIN_FREE_SPACE_RESERVE_GB = 10  # Preserve at least this many GiB after the estimated output allocation.
OUTPUT_SIZE_SAFETY_FACTOR = 1.10  # Reserve ten percent above matched target sizes for the injected PT-BR audio and container overhead.


SUPPORTED_MEDIA_EXTENSIONS = frozenset(  # Define input video container extensions accepted for source and target media files.
    {
        ".3g2",  # Support 3GPP2 video containers.
        ".3gp",  # Support 3GPP video containers.
        ".avi",  # Support Audio Video Interleave containers.
        ".flv",  # Support Flash Video containers.
        ".m2ts",  # Support Blu-ray MPEG-2 transport stream containers.
        ".m4v",  # Support MPEG-4 video containers.
        ".mkv",  # Support Matroska video containers.
        ".mk3d",  # Support Matroska 3D video containers.
        ".mov",  # Support QuickTime movie containers.
        ".mp4",  # Support MPEG-4 Part 14 containers.
        ".mpeg",  # Support MPEG program stream containers.
        ".mpg",  # Support MPEG program stream containers.
        ".mts",  # Support AVCHD MPEG transport stream containers.
        ".ogv",  # Support Ogg video containers.
        ".ts",  # Support MPEG transport stream containers.
        ".vob",  # Support DVD Video Object containers.
        ".webm",  # Support WebM video containers.
        ".wmv",  # Support Windows Media Video containers.
    }
)

# Functions Definitions:

def normalize_text(value: str) -> str:
    """
    Normalize text for accent-insensitive metadata comparisons.

    :param value: Text value to normalize.
    :return: Lowercase text without diacritics or surrounding whitespace.
    """

    normalized_value = unicodedata.normalize("NFKD", value or "")  # Decompose accented characters.
    normalized_value = "".join(character for character in normalized_value if not unicodedata.combining(character))  # Remove decomposed diacritics.

    return normalized_value.lower().strip()  # Return normalized lowercase text.


def normalized_token_text(value: str) -> str:
    """
    Convert normalized text into a space-delimited token sequence.

    :param value: Text value to tokenize.
    :return: Normalized text with punctuation replaced by single spaces.
    """

    normalized_value = normalize_text(value)  # Normalize accents, case, and surrounding whitespace.
    token_text = re.sub(r"[^a-z0-9]+", " ", normalized_value)  # Replace punctuation and separators with spaces.

    return " ".join(token_text.split())  # Collapse repeated whitespace between tokens.


def contains_token(value: str, token: str) -> bool:
    """
    Determine whether normalized text contains a complete token phrase.

    :param value: Normalized or raw text to inspect.
    :param token: Token or token phrase to locate.
    :return: True when the complete normalized token phrase is present.
    """

    normalized_value = f" {normalized_token_text(value)} "  # Add boundaries around the normalized text.
    normalized_token = f" {normalized_token_text(token)} "  # Add boundaries around the normalized token.

    return normalized_token in normalized_value  # Match only complete tokens or token phrases.


def stream_tags(stream: Stream) -> Stream:
    """
    Return a stream metadata tag dictionary.

    :param stream: FFprobe stream dictionary.
    :return: Stream tag dictionary or an empty dictionary when unavailable.
    """

    tags = stream.get("tags")  # Read the raw stream tags value.

    return cast(Stream, tags) if isinstance(tags, dict) else {}  # Return only dictionary-shaped tags.


def stream_disposition(stream: Stream) -> Stream:
    """
    Return a stream disposition dictionary.

    :param stream: FFprobe stream dictionary.
    :return: Stream disposition dictionary or an empty dictionary when unavailable.
    """

    disposition = stream.get("disposition")  # Read the raw stream disposition value.

    return cast(Stream, disposition) if isinstance(disposition, dict) else {}  # Return only dictionary-shaped dispositions.


def stream_text(stream: Stream) -> str:
    """
    Combine relevant stream metadata into normalized searchable text.

    :param stream: FFprobe stream dictionary.
    :return: Normalized text composed from language, title, and handler metadata.
    """

    tags = stream_tags(stream)  # Resolve the stream tag dictionary.
    values = [  # Collect metadata fields used for language and role detection.
        tags.get("language", ""),  # Include the lowercase language tag.
        tags.get("LANGUAGE", ""),  # Include the uppercase language tag variant.
        tags.get("title", ""),  # Include the lowercase title tag.
        tags.get("TITLE", ""),  # Include the uppercase title tag variant.
        tags.get("handler_name", ""),  # Include the stream handler name.
    ]
    combined_text = " ".join(str(value) for value in values if value)  # Join populated metadata fields.

    return normalize_text(combined_text)  # Return normalized searchable metadata.


def stream_language(stream: Stream) -> str:
    """
    Return the normalized language tag from a stream.

    :param stream: FFprobe stream dictionary.
    :return: Normalized language tag or an empty string when unavailable.
    """

    tags = stream_tags(stream)  # Resolve the stream tag dictionary.
    language = tags.get("language") or tags.get("LANGUAGE") or ""  # Select the available language tag variant.

    return normalize_text(str(language))  # Return the normalized language value.


def classify_language(stream_or_text: Stream | str | Path) -> LanguageClass | None:
    """
    Classify stream metadata or text as English or Brazilian Portuguese.

    :param stream_or_text: FFprobe stream dictionary, filename, or text value.
    :return: Detected language class or None when no supported language is found.
    """

    if isinstance(stream_or_text, dict):  # Handle structured FFprobe stream metadata.
        text = stream_text(stream_or_text)  # Combine searchable stream metadata.
        language = stream_language(stream_or_text)  # Read the normalized stream language tag.
    else:  # Handle filenames and plain text values.
        text = normalize_text(str(stream_or_text))  # Normalize the supplied text value.
        language = text  # Reuse the normalized text for exact language comparisons.

    english_tokens = {"eng", "en", "english", "ingles"}  # Define recognized English language tokens.
    ptbr_tokens = {"por", "pt", "pt-br", "ptbr", "pt br", "pob", "portuguese", "portugues", "brazilian", "brasil", "brazil", "br"}  # Define recognized Brazilian Portuguese language tokens.

    if language in english_tokens:  # Prefer exact English language metadata.
        return "english"  # Return the English classification.

    if language in ptbr_tokens:  # Prefer exact Brazilian Portuguese language metadata.
        return "ptbr"  # Return the Brazilian Portuguese classification.

    if any(contains_token(text, token) for token in english_tokens):  # Inspect complete English tokens in combined metadata.
        return "english"  # Return the English classification.

    if any(contains_token(text, token) for token in ptbr_tokens):  # Inspect complete Brazilian Portuguese tokens in combined metadata.
        return "ptbr"  # Return the Brazilian Portuguese classification.

    return None  # Report unsupported or absent language metadata.


def is_forced(stream_or_path: Stream | str | Path) -> bool:
    """
    Determine whether a subtitle stream or external path is marked as forced.

    :param stream_or_path: FFprobe stream dictionary, subtitle path, or filename.
    :return: True when forced disposition or forced naming metadata is present.
    """

    if isinstance(stream_or_path, dict):  # Handle structured FFprobe stream metadata.
        disposition = stream_disposition(stream_or_path)  # Resolve the stream disposition dictionary.

        if disposition.get("forced") == 1:  # Honor the explicit FFprobe forced disposition.
            return True  # Report the stream as forced.

        text = stream_text(stream_or_path)  # Combine searchable stream metadata.
    else:  # Handle external subtitle paths and filenames.
        text = normalize_text(str(stream_or_path))  # Normalize the supplied path text.

    forced_tokens = {"forced", "forcado"}  # Define normalized forced-subtitle markers.

    return any(contains_token(text, token) for token in forced_tokens)  # Match complete forced-subtitle markers.


def is_commentary_audio(stream: Stream) -> bool:
    """
    Determine whether an audio stream contains commentary metadata.

    :param stream: FFprobe audio stream dictionary.
    :return: True when commentary metadata is present.
    """

    text = stream_text(stream)  # Combine searchable audio stream metadata.
    commentary_tokens = {"commentary", "comentario", "comentarios"}  # Define normalized commentary markers.

    return any(contains_token(text, token) for token in commentary_tokens)  # Match complete commentary markers.


def output_language_metadata(language_class: LanguageClass) -> tuple[str, str]:
    """
    Return FFmpeg language metadata for a supported language class.

    :param language_class: Supported internal language classification.
    :return: FFmpeg language code and normalized track title.
    """

    if language_class == "english":  # Handle the English language class.
        return "eng", "English"  # Return normalized English metadata.

    return "por", "PT-BR"  # Return normalized Brazilian Portuguese metadata.


def subtitle_metadata(stream: Stream, fallback_number: int) -> tuple[str, str]:
    """
    Resolve language metadata and a clean title for an internal subtitle stream.

    :param stream: FFprobe subtitle stream dictionary.
    :param fallback_number: Sequential subtitle number used for unknown metadata.
    :return: FFmpeg language code and normalized subtitle title.
    """

    language_class = classify_language(stream)  # Classify supported subtitle languages.

    if language_class is not None:  # Handle supported subtitle languages.
        return output_language_metadata(language_class)  # Return standardized supported metadata.

    language = stream_language(stream)  # Read the normalized raw subtitle language.
    known_languages = {  # Map additional known subtitle language tags.
        "eng": ("eng", "English"),  # Normalize the English ISO tag.
        "en": ("eng", "English"),  # Normalize the short English tag.
        "por": ("por", "PT-BR"),  # Normalize the Portuguese ISO tag.
        "pt": ("por", "PT-BR"),  # Normalize the short Portuguese tag.
        "pt-br": ("por", "PT-BR"),  # Normalize the regional Portuguese tag.
        "pob": ("por", "PT-BR"),  # Normalize the Brazilian Portuguese legacy tag.
        "spa": ("spa", "Spanish"),  # Preserve the Spanish ISO tag.
        "es": ("spa", "Spanish"),  # Normalize the short Spanish tag.
        "fre": ("fre", "French"),  # Preserve the legacy French ISO tag.
        "fra": ("fre", "French"),  # Normalize the modern French ISO tag.
        "fr": ("fre", "French"),  # Normalize the short French tag.
    }

    if language in known_languages:  # Handle known secondary subtitle languages.
        return known_languages[language]  # Return mapped language metadata.

    return "und", f"Subtitle {fallback_number}"  # Return deterministic fallback subtitle metadata.


def stream_index(stream: Stream, media_path: Path) -> int:
    """
    Return a validated global FFprobe stream index.

    :param stream: FFprobe stream dictionary.
    :param media_path: Media path used in validation errors.
    :return: Non-negative global stream index.
    """

    index = stream.get("index")  # Read the raw FFprobe stream index.

    if isinstance(index, bool) or not isinstance(index, int) or index < 0:  # Validate the global stream index shape and range.
        raise RuntimeError(f"Invalid stream index in media file: {media_path}")  # Reject unusable FFmpeg stream mappings.

    return index  # Return the validated global stream index.


def probe_media(path: Path) -> MediaInfo:
    """
    Read FFprobe stream metadata for a media file.

    :param path: Media file path to inspect.
    :return: Parsed FFprobe JSON information.
    """

    command = [  # Build the FFprobe stream inspection command.
        FFPROBE,  # Select the configured FFprobe executable.
        "-v",  # Configure FFprobe logging verbosity.
        "error",  # Emit only FFprobe errors.
        "-print_format",  # Select the metadata serialization format.
        "json",  # Request JSON metadata output.
        "-show_streams",  # Include all media stream records.
        str(path),  # Supply the media file path.
    ]
    result = subprocess.run(  # Execute FFprobe and capture its JSON output.
        command,  # Supply the prepared FFprobe command.
        check=True,  # Raise an exception when FFprobe exits unsuccessfully.
        capture_output=True,  # Capture standard output and standard error.
        text=True,  # Decode captured output as text.
        encoding="utf-8",  # Decode FFprobe output with UTF-8.
        errors="replace",  # Replace invalid byte sequences deterministically.
    )
    parsed_output = json.loads(result.stdout)  # Parse the captured FFprobe JSON document.

    if not isinstance(parsed_output, dict):  # Validate the FFprobe root JSON structure.
        raise RuntimeError(f"Unexpected FFprobe output structure for: {path}")  # Reject non-object FFprobe output.

    return cast(MediaInfo, parsed_output)  # Return the validated media information dictionary.


def extract_streams(media_info: MediaInfo, media_path: Path) -> list[Stream]:
    """
    Extract validated stream dictionaries from FFprobe media information.

    :param media_info: Parsed FFprobe media information.
    :param media_path: Media path used in validation errors.
    :return: List of validated FFprobe stream dictionaries.
    """

    raw_streams = media_info.get("streams")  # Read the raw FFprobe streams collection.

    if not isinstance(raw_streams, list):  # Validate the FFprobe streams collection type.
        raise RuntimeError(f"FFprobe returned no stream list for: {media_path}")  # Reject missing or malformed stream collections.

    streams = [cast(Stream, stream) for stream in raw_streams if isinstance(stream, dict)]  # Retain dictionary-shaped stream records.

    if len(streams) != len(raw_streams):  # Validate every FFprobe stream record shape.
        raise RuntimeError(f"FFprobe returned malformed stream data for: {media_path}")  # Reject partially malformed stream collections.

    return streams  # Return validated FFprobe stream dictionaries.


def format_command(command: list[str]) -> str:
    """
    Format a subprocess argument list for readable terminal output.

    :param command: Subprocess command and argument list.
    :return: Readable command string with whitespace-containing arguments quoted.
    """

    formatted_parts = [f'"{part}"' if any(character.isspace() for character in part) else part for part in command]  # Quote arguments containing whitespace.

    return " ".join(formatted_parts)  # Join command arguments for display.


def run_command(command: list[str]) -> None:
    """
    Print and optionally execute a subprocess command.

    :param command: Subprocess command and argument list.
    :return: None.
    """

    print("\nRunning:")  # Announce the next external command.
    print(format_command(command))  # Display the complete command before execution.

    if DRY_RUN:  # Honor non-destructive command preview mode.
        print("DRY_RUN=True, command not executed.")  # Report that execution was intentionally skipped.

        return  # Stop before invoking the external process.

    subprocess.run(command, check=True)  # Execute the command and propagate unsuccessful exit status.


def season_key(path: Path) -> int | None:
    """
    Extract a numeric season identifier from a directory name.

    :param path: Season directory path.
    :return: Parsed season number or None when the name has no season identifier.
    """

    season_match = re.search(r"season\s*0*(\d+)", path.name, re.IGNORECASE)  # Locate verbose season names such as "Breaking Bad - Season 02 2009 720p Dual".

    if season_match is not None:  # Prefer an explicit "Season XX" identifier when available.
        return int(season_match.group(1))  # Return the parsed verbose season number.

    short_match = re.search(r"(?:^|[^a-z0-9])s\s*0*(\d+)(?:[^0-9]|$)", path.name, re.IGNORECASE)  # Locate compact season names such as "S02".

    if short_match is not None:  # Handle target directories using compact season notation.
        return int(short_match.group(1))  # Return the parsed compact season number.

    return None  # Report that no supported season identifier was found.


def episode_key(path: Path, expected_season: int | None = None) -> int | None:
    """
    Extract a numeric episode identifier from a media filename.

    :param path: Media file path whose filename identifies an episode.
    :param expected_season: Optional season number used to reject an SxxExx identifier from another season.
    :return: Parsed episode number or None when the filename has no supported episode identifier.
    """

    explicit_match = re.search(r"s\s*0*(\d+)\s*e\s*0*(\d+)", path.stem, re.IGNORECASE)  # Locate explicit identifiers such as "S02E01" inside descriptive target filenames.

    if explicit_match is not None:  # Prefer season-aware episode identifiers when available.
        detected_season = int(explicit_match.group(1))  # Parse the season number embedded in the media filename.
        detected_episode = int(explicit_match.group(2))  # Parse the episode number embedded in the media filename.

        if expected_season is not None and detected_season != expected_season:  # Reject a filename whose explicit season conflicts with its containing matched season.
            return None  # Prevent cross-season episode pairing.

        return detected_episode  # Return the explicit episode number.

    episode_match = re.search(r"(?:^|[^a-z0-9])e\s*0*(\d+)(?:[^0-9]|$)", path.stem, re.IGNORECASE)  # Locate standalone episode identifiers such as "E01".

    if episode_match is not None:  # Handle filenames that identify only the episode number.
        return int(episode_match.group(1))  # Return the standalone episode number.

    numeric_stem = path.stem.strip()  # Normalize numeric-only source filenames such as "01.mp4".

    if numeric_stem.isdigit():  # Accept source episodes represented only by their sequential number.
        return int(numeric_stem)  # Return the numeric source episode number.

    return None  # Report that no supported episode identifier was found.


def build_original_season_map() -> dict[int, Path]:
    """
    Map original season numbers to their configured directories.

    :return: Dictionary mapping season numbers to original season directories.
    """

    seasons: dict[int, Path] = {}  # Initialize the original season mapping.

    for folder in ORIGINAL_ROOT.iterdir():  # Inspect each entry under the original media root.
        if not folder.is_dir():  # Ignore files and other non-directory entries.
            continue  # Continue with the next original root entry.

        key = season_key(folder)  # Extract the season number from the directory name.

        if key is not None:  # Retain directories with recognized season numbers.
            seasons[key] = folder  # Map the season number to its original directory.

    return seasons  # Return the complete original season mapping.


def iter_media_files(directory: Path, include_updated: bool = False) -> list[Path]:
    """
    Return sorted supported media files from a directory.

    :param directory: Directory containing candidate media files.
    :param include_updated: Whether generated files with UPDATED_SUFFIX are included.
    :return: Sorted list of supported media file paths.
    """

    media_files = [entry for entry in directory.iterdir() if entry.is_file() and entry.suffix.lower() in SUPPORTED_MEDIA_EXTENSIONS]  # Retain supported media files with case-insensitive extensions.

    if not include_updated:  # Exclude previously generated outputs by default.
        media_files = [entry for entry in media_files if not entry.stem.lower().endswith(UPDATED_SUFFIX.lower())]  # Remove files carrying the configured output suffix.

    return sorted(media_files, key=lambda entry: entry.name.casefold())  # Return deterministic case-insensitive filename ordering.


def resolve_original_media(original_directory: Path, target_media: Path, season_number: int | None = None) -> Path | None:
    """
    Resolve the original media file matching a target filename, stem, or episode number.

    :param original_directory: Original media directory containing source media files.
    :param target_media: Target media file whose source counterpart is required.
    :param season_number: Optional matched season number used for episode-number resolution.
    :return: Matching original media path or None when no unambiguous match exists.
    """

    exact_match = original_directory / target_media.name  # Build the original path using the exact target filename and extension.

    if exact_match.is_file() and exact_match.suffix.lower() in SUPPORTED_MEDIA_EXTENSIONS:  # Prefer an exact supported filesystem filename match.
        return exact_match  # Return the exact matching original media file.

    casefolded_name = target_media.name.casefold()  # Normalize the complete target filename for case-insensitive matching.
    original_files = iter_media_files(original_directory, include_updated=True)  # Collect supported original media candidates from the requested directory.
    matching_names = [candidate for candidate in original_files if candidate.name.casefold() == casefolded_name]  # Locate case-insensitive complete filename matches.

    if len(matching_names) > 1:  # Reject ambiguous complete filenames on case-sensitive filesystems.
        raise RuntimeError(f"Multiple original files match target media filename: {target_media}")  # Prevent selecting an arbitrary original media file.

    if matching_names:  # Prefer a unique complete filename match before comparing filename stems.
        return matching_names[0]  # Return the unique case-insensitive complete filename match.

    casefolded_stem = target_media.stem.casefold()  # Normalize the target filename without its container extension.
    matching_stems = [candidate for candidate in original_files if candidate.stem.casefold() == casefolded_stem]  # Match equivalent media names even when container extensions differ.

    if len(matching_stems) > 1:  # Reject ambiguous same-stem files across multiple source container formats.
        raise RuntimeError(f"Multiple original files match target media stem: {target_media}")  # Prevent guessing between duplicate source representations.

    if matching_stems:  # Prefer a unique same-stem match before attempting series-specific episode matching.
        return matching_stems[0]  # Return the unique same-stem source media file.

    target_episode = episode_key(target_media, season_number)  # Extract the target episode number from names such as "Breaking Bad - S02E01 - Title.mkv".

    if target_episode is None:  # Stop when the target filename provides no safe episode identifier.
        return None  # Report that no supported source match could be resolved.

    matching_episodes = [candidate for candidate in original_files if episode_key(candidate, season_number) == target_episode]  # Match numeric source filenames such as "01.mp4" to descriptive SxxExx target filenames.

    if len(matching_episodes) > 1:  # Reject duplicate source candidates for the same season episode number.
        raise RuntimeError(f"Multiple original files match target episode S{season_number:02d}E{target_episode:02d}: {target_media}" if season_number is not None else f"Multiple original files match target episode {target_episode}: {target_media}")  # Prevent selecting an arbitrary source episode.

    return matching_episodes[0] if matching_episodes else None  # Return the unique episode-number match when available.


def select_target_english_audio_track(target_media: Path, streams: list[Stream]) -> Stream:
    """
    Select the higher-quality English non-commentary audio stream from the target media.

    :param target_media: Higher-quality target media path used in validation errors.
    :param streams: FFprobe stream dictionaries from the target media file.
    :return: Selected target English audio stream.
    """

    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio" and not is_commentary_audio(stream)]  # Retain non-commentary target audio streams.
    english_streams = [stream for stream in audio_streams if classify_language(stream) == "english"]  # Collect target audio streams explicitly identified as English.

    if english_streams:  # Prefer the first explicitly identified English target audio stream.
        return english_streams[0]  # Preserve the highest-priority target English stream in source order.

    if len(audio_streams) == 1:  # Handle common English-only target files whose single audio stream lacks useful language metadata.
        return audio_streams[0]  # Safely treat the only available target audio stream as the English track.

    debug_lines: list[str] = []  # Initialize diagnostic descriptions for ambiguous target audio layouts.

    for stream in audio_streams:  # Describe every eligible target audio stream for the error report.
        tags = stream_tags(stream)  # Resolve the stream tag dictionary.
        debug_lines.append(  # Add one diagnostic line for the current target audio stream.
            f"index={stream.get('index')} "  # Include the global stream index.
            f"codec={stream.get('codec_name')} "  # Include the audio codec name.
            f"language={tags.get('language') or tags.get('LANGUAGE')} "  # Include the available language tag.
            f"title={tags.get('title') or tags.get('TITLE')}"  # Include the available track title.
        )

    detected_streams = "\n".join(debug_lines) if debug_lines else "No eligible audio streams were detected."  # Serialize target audio diagnostics.
    raise RuntimeError(  # Reject targets where preserving the correct high-quality English track would require guessing.
        f"Could not identify the target English audio track in:\n"  # Describe the target-language detection failure.
        f"{target_media}\n\n"  # Include the affected higher-quality target path.
        f"Detected target audio streams:\n{detected_streams}"  # Include stream metadata diagnostics.
    )


def select_original_ptbr_audio_track(original_media: Path, streams: list[Stream]) -> Stream:
    """
    Select the PT-BR non-commentary audio stream from the lower-quality original media.

    :param original_media: Original media path used in validation errors.
    :param streams: FFprobe stream dictionaries from the original media file.
    :return: Selected original PT-BR audio stream.
    """

    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio" and not is_commentary_audio(stream)]  # Retain non-commentary source audio streams.
    ptbr_streams = [stream for stream in audio_streams if classify_language(stream) == "ptbr"]  # Collect source streams explicitly identified as Brazilian Portuguese.

    if ptbr_streams:  # Prefer metadata-based PT-BR detection whenever available.
        return ptbr_streams[0]  # Return the first detected PT-BR source stream.

    if FALLBACK_ORIGINAL_AUDIO_ORDER is not None:  # Apply the configured deterministic source order only when metadata cannot identify PT-BR.
        if FALLBACK_ORIGINAL_AUDIO_ORDER not in {("english", "ptbr"), ("ptbr", "english")}:  # Validate the supported fallback configurations.
            raise RuntimeError("Invalid FALLBACK_ORIGINAL_AUDIO_ORDER. Use None, ('english', 'ptbr'), or ('ptbr', 'english').")  # Reject unsupported fallback values.

        if len(audio_streams) < 2:  # Require both expected fallback positions before selecting PT-BR by position.
            raise RuntimeError(f"Not enough audio tracks in original file: {original_media}")  # Reject incomplete source audio layouts.

        ptbr_position = FALLBACK_ORIGINAL_AUDIO_ORDER.index("ptbr")  # Resolve whether PT-BR is the first or second eligible source audio track.

        return audio_streams[ptbr_position]  # Return the PT-BR source stream selected from the configured deterministic order.

    debug_lines: list[str] = []  # Initialize diagnostic descriptions for unresolved source audio layouts.

    for stream in audio_streams:  # Describe every eligible source audio stream for the error report.
        tags = stream_tags(stream)  # Resolve the stream tag dictionary.
        debug_lines.append(  # Add one diagnostic line for the current source audio stream.
            f"index={stream.get('index')} "  # Include the global stream index.
            f"codec={stream.get('codec_name')} "  # Include the audio codec name.
            f"language={tags.get('language') or tags.get('LANGUAGE')} "  # Include the available language tag.
            f"title={tags.get('title') or tags.get('TITLE')}"  # Include the available track title.
        )

    detected_streams = "\n".join(debug_lines) if debug_lines else "No eligible audio streams were detected."  # Serialize source audio diagnostics.
    raise RuntimeError(  # Reject unresolved PT-BR source layouts rather than copying the wrong language.
        f"Could not identify the PT-BR audio track in:\n"  # Describe the source-language detection failure.
        f"{original_media}\n\n"  # Include the affected original source path.
        f"Detected original audio streams:\n{detected_streams}"  # Include stream metadata diagnostics.
    )


def select_subtitle_tracks(streams: list[Stream]) -> list[Stream]:
    """
    Select every non-forced internal subtitle stream.

    :param streams: FFprobe stream dictionaries from the original media file.
    :return: Non-forced subtitle streams in source order.
    """

    subtitle_streams = [stream for stream in streams if stream.get("codec_type") == "subtitle" and not is_forced(stream)]  # Retain non-forced subtitle streams.

    return subtitle_streams  # Return subtitles in their original stream order.


def matching_external_srts(original_media: Path) -> list[Path]:
    """
    Find non-forced external SRT files associated with an original media file.

    :param original_media: Original media path used as the media filename prefix.
    :return: Sorted matching external SRT paths.
    """

    media_stem = original_media.stem.casefold()  # Normalize the media stem for case-insensitive matching.
    candidates: list[Path] = []  # Initialize matching external subtitle paths.

    for subtitle_path in original_media.parent.iterdir():  # Inspect files beside the original media file.
        if not subtitle_path.is_file() or subtitle_path.suffix.lower() != ".srt":  # Ignore directories and non-SRT files.
            continue  # Continue with the next neighboring entry.

        subtitle_stem = subtitle_path.stem.casefold()  # Normalize the external subtitle stem.
        same_media = (  # Evaluate supported media filename relationships.
            subtitle_stem == media_stem  # Match an equal media stem.
            or subtitle_stem.startswith(f"{media_stem}.")  # Match a period-delimited suffix.
            or subtitle_stem.startswith(f"{media_stem} ")  # Match a space-delimited suffix.
            or subtitle_stem.startswith(f"{media_stem}-")  # Match a hyphen-delimited suffix.
            or subtitle_stem.startswith(f"{media_stem}_")  # Match an underscore-delimited suffix.
        )

        if same_media and not is_forced(subtitle_path.name):  # Retain associated subtitles without forced markers.
            candidates.append(subtitle_path)  # Add the external subtitle candidate.

    return sorted(candidates, key=lambda entry: entry.name.casefold())  # Return deterministic case-insensitive filename ordering.


def external_subtitle_destination(media_path: Path, output_mkv: Path, subtitle_path: Path, subtitle_number: int, subtitle_count: int) -> Path:
    """
    Build the preferred destination path for an external subtitle file.

    :param media_path: Target media path whose filename prefix identifies the subtitle suffix.
    :param output_mkv: Generated MKV path that determines the destination stem.
    :param subtitle_path: Source external subtitle path used for destination naming.
    :param subtitle_number: One-based subtitle position used for fallback naming.
    :param subtitle_count: Total number of matching external subtitles.
    :return: Preferred destination SRT path.
    """

    media_stem = media_path.stem  # Preserve the target media filename stem used to identify an external subtitle suffix.
    subtitle_stem = subtitle_path.stem  # Read the external subtitle filename without its .srt extension.

    if subtitle_stem.casefold().startswith(media_stem.casefold()):  # Preserve target subtitle suffixes such as ".pt-BR" when present.
        source_suffix = subtitle_stem[len(media_stem):]  # Extract the exact suffix following the target media stem.
    else:  # Handle an unexpected associated subtitle naming shape defensively.
        source_suffix = ""  # Fall back to deterministic generated naming.

    if source_suffix:  # Preserve meaningful target-language and role suffixes when available.
        destination_name = f"{output_mkv.stem}{source_suffix}.srt"  # Rebuild the subtitle filename around the generated MKV stem.
    elif subtitle_count == 1:  # Preserve the simple output stem for a single external subtitle without a source suffix.
        destination_name = f"{output_mkv.stem}.srt"  # Build the single-subtitle destination filename.
    else:  # Add positional metadata when multiple subtitle files provide no reusable suffix.
        destination_name = f"{output_mkv.stem}.Subtitle-{subtitle_number}.srt"  # Build a deterministic multi-subtitle destination filename.

    return output_mkv.parent / destination_name  # Return the preferred destination path.


def copy_external_srts(target_media: Path, output_mkv: Path) -> None:
    """
    Copy matching target external SRT files beside a generated MKV output.

    :param target_media: Higher-quality target media path used to discover synchronized external SRT files.
    :param output_mkv: Generated MKV path used for destination naming.
    :return: None.
    """

    subtitle_paths = matching_external_srts(target_media)  # Discover associated non-forced target SRT files already synchronized to the higher-quality release.

    if not subtitle_paths:  # Stop when the target media file has no matching external subtitles.
        return  # Complete without creating subtitle files.

    print("\nExternal target SRT files to copy:")  # Announce external target subtitle copy operations.
    used_destinations: set[Path] = set()  # Track destinations selected during the current media file.

    for subtitle_number, subtitle_path in enumerate(subtitle_paths, start=1):  # Process external target subtitles in deterministic order.
        destination = external_subtitle_destination(target_media, output_mkv, subtitle_path, subtitle_number, len(subtitle_paths))  # Build the preferred destination path preserving target subtitle suffixes.
        collision_number = 2  # Initialize the alternate filename counter.

        while destination in used_destinations or (destination.exists() and not OVERWRITE):  # Avoid in-memory and filesystem destination collisions.
            destination = output_mkv.parent / f"{output_mkv.stem}.Subtitle-{subtitle_number}-{collision_number}.srt"  # Build the next collision-safe destination.
            collision_number += 1  # Advance the collision suffix for another attempt.

        used_destinations.add(destination)  # Reserve the selected destination for this media file.
        print(f"  {subtitle_path} -> {destination}")  # Display the planned external subtitle copy.

        if not DRY_RUN:  # Perform filesystem changes only outside preview mode.
            shutil.copy2(subtitle_path, destination)  # Copy target subtitle contents and filesystem metadata.


def build_ffmpeg_command(target_media: Path, original_media: Path, output_mkv: Path) -> list[str]:
    """
    Build the FFmpeg mux command for one higher-quality target and original PT-BR source pair.

    :param target_media: Higher-quality target media file providing video, English audio, subtitles, attachments, and chapters.
    :param original_media: Lower-quality original media file providing the PT-BR audio stream.
    :param output_mkv: Destination MKV path.
    :return: Complete FFmpeg command and argument list.
    """

    target_info = probe_media(target_media)  # Read stream metadata from the higher-quality target media file.
    target_streams = extract_streams(target_info, target_media)  # Validate and extract higher-quality target stream dictionaries.
    original_info = probe_media(original_media)  # Read stream metadata from the lower-quality original source media file.
    original_streams = extract_streams(original_info, original_media)  # Validate and extract original source stream dictionaries.
    english_audio_track = select_target_english_audio_track(target_media, target_streams)  # Preserve the higher-quality target English audio instead of downgrading it from the source.
    ptbr_audio_track = select_original_ptbr_audio_track(original_media, original_streams)  # Select only the PT-BR audio required from the lower-quality original source.
    subtitle_tracks = select_subtitle_tracks(target_streams)  # Preserve every non-forced internal subtitle stream from the higher-quality target release.
    command = [  # Initialize the FFmpeg mux command.
        FFMPEG,  # Select the configured FFmpeg executable.
        "-hide_banner",  # Suppress the FFmpeg startup banner.
        "-y" if OVERWRITE else "-n",  # Apply the configured output overwrite policy.
        "-i",  # Declare the higher-quality target media input.
        str(target_media),  # Supply the target media path as input zero.
        "-i",  # Declare the lower-quality PT-BR source media input.
        str(original_media),  # Supply the original source media path as input one.
        "-map",  # Add a stream mapping directive.
        "0:v?",  # Preserve every video stream from the higher-quality target media file when present.
        "-map",  # Add another stream mapping directive.
        "0:t?",  # Preserve every attachment stream from the higher-quality target media file when present.
        "-map",  # Add the selected higher-quality target English audio stream.
        f"0:{stream_index(english_audio_track, target_media)}",  # Map the validated English audio stream from input zero.
        "-map",  # Add the selected original PT-BR audio stream.
        f"1:{stream_index(ptbr_audio_track, original_media)}",  # Map the validated PT-BR audio stream from input one.
    ]

    for subtitle_track in subtitle_tracks:  # Map non-forced higher-quality target subtitle streams in source order.
        command.extend(["-map", f"0:{stream_index(subtitle_track, target_media)}"])  # Map one validated global subtitle stream index from input zero.

    command.extend(  # Add container-level mapping and codec behavior.
        [  # Define metadata, chapter, and codec arguments.
            "-map_metadata",  # Configure global metadata mapping.
            "-1",  # Remove source global metadata from the output container.
            "-map_chapters",  # Configure chapter mapping.
            "0",  # Preserve chapters from the higher-quality target media file.
            "-c",  # Configure a codec policy for every mapped stream.
            "copy",  # Copy all mapped streams without re-encoding.
        ]
    )
    command.extend(  # Add normalized audio metadata and dispositions.
        [  # Define output audio stream metadata arguments.
            "-metadata:s:a:0",  # Select metadata for the first output audio stream.
            "language=eng",  # Tag the preserved target audio stream as English.
            "-metadata:s:a:0",  # Select another metadata field for the first output audio stream.
            "title=English",  # Title the preserved target audio stream as English.
            "-disposition:a:0",  # Configure the first output audio stream disposition.
            "default",  # Keep higher-quality English as the default audio stream.
            "-metadata:s:a:1",  # Select metadata for the second output audio stream.
            "language=por",  # Tag the injected source audio stream as Portuguese.
            "-metadata:s:a:1",  # Select another metadata field for the second output audio stream.
            "title=PT-BR",  # Title the injected source audio stream as Brazilian Portuguese.
            "-disposition:a:1",  # Configure the second output audio stream disposition.
            "0",  # Keep PT-BR available without making it the default audio stream.
        ]
    )

    for subtitle_number, subtitle_track in enumerate(subtitle_tracks):  # Configure each preserved target subtitle stream in mapped order.
        language_code, clean_title = subtitle_metadata(subtitle_track, subtitle_number + 1)  # Resolve normalized target subtitle metadata.
        command.extend(  # Add metadata and disposition arguments for one subtitle stream.
            [  # Define output subtitle stream metadata arguments.
                f"-metadata:s:s:{subtitle_number}",  # Select the subtitle language metadata field.
                f"language={language_code}",  # Apply the resolved subtitle language code.
                f"-metadata:s:s:{subtitle_number}",  # Select the subtitle title metadata field.
                f"title={clean_title}",  # Apply the resolved subtitle title.
                f"-disposition:s:{subtitle_number}",  # Configure the subtitle stream disposition.
                "default" if subtitle_number == 0 else "0",  # Mark only the first preserved target subtitle as default.
            ]
        )

    command.append(str(output_mkv))  # Append the destination MKV path stored under OUTPUT_ROOT.

    return command  # Return the complete FFmpeg mux command.


def remove_partial_output(output_mkv: Path) -> None:
    """
    Remove a partial generated MKV after unsuccessful FFmpeg processing.

    :param output_mkv: Generated MKV path that may contain partial data.
    :return: None.
    """

    if output_mkv.is_file():  # Limit cleanup to an existing regular output file.
        output_mkv.unlink()  # Remove the incomplete generated media file.


def validate_generated_output(output_mkv: Path) -> None:
    """
    Validate that FFmpeg created a non-empty output MKV file.

    :param output_mkv: Generated MKV path to validate.
    :return: None.
    """

    if not output_mkv.is_file():  # Require FFmpeg to create the configured output path.
        raise RuntimeError(f"FFmpeg completed without creating output: {output_mkv}")  # Report a missing generated file.

    if output_mkv.stat().st_size <= 0:  # Reject an empty generated media file.
        raise RuntimeError(f"FFmpeg created an empty output file: {output_mkv}")  # Report unusable zero-byte output.


def validate_generated_output_for_source_erasure(output_mkv: Path) -> None:
    """
    Validate the generated output contains the required streams before deleting any source media.

    :param output_mkv: Generated MKV path that must safely replace information from source media files.
    :return: None.
    """

    output_info = probe_media(output_mkv)  # Re-open the completed output with FFprobe before permitting destructive source cleanup.
    output_streams = extract_streams(output_info, output_mkv)  # Validate and extract the generated output stream dictionaries.
    video_streams = [stream for stream in output_streams if stream.get("codec_type") == "video" and stream_disposition(stream).get("attached_pic") != 1]  # Retain actual output video streams while excluding attached artwork.
    audio_streams = [stream for stream in output_streams if stream.get("codec_type") == "audio" and not is_commentary_audio(stream)]  # Retain non-commentary output audio streams used for language validation.
    english_streams = [stream for stream in audio_streams if classify_language(stream) == "english"]  # Confirm the generated output contains the preserved English audio track.
    ptbr_streams = [stream for stream in audio_streams if classify_language(stream) == "ptbr"]  # Confirm the generated output contains the injected PT-BR audio track.

    if not video_streams:  # Reject source deletion when the completed output has no actual video stream.
        raise RuntimeError(f"Generated output has no video stream; source files will not be erased: {output_mkv}")  # Preserve both sources when the replacement media is structurally incomplete.

    if not english_streams:  # Reject source deletion when the required English audio cannot be confirmed in the completed output.
        raise RuntimeError(f"Generated output has no identifiable English audio stream; source files will not be erased: {output_mkv}")  # Preserve both sources rather than deleting the only known English source.

    if not ptbr_streams:  # Reject source deletion when the required PT-BR audio cannot be confirmed in the completed output.
        raise RuntimeError(f"Generated output has no identifiable PT-BR audio stream; source files will not be erased: {output_mkv}")  # Preserve both sources rather than deleting the only known PT-BR source.


def erase_processed_source_files(target_media: Path, original_media: Path, output_mkv: Path) -> None:
    """
    Delete configured source media files only after a generated replacement has been validated.

    :param target_media: Higher-quality target media file eligible for deletion when ERASE_TARGET_FILES is enabled.
    :param original_media: Lower-quality original media file eligible for deletion when ERASE_ORIGINAL_FILES is enabled.
    :param output_mkv: Successfully generated output that must exist before source deletion is permitted.
    :return: None.
    """

    if not ERASE_TARGET_FILES and not ERASE_ORIGINAL_FILES:  # Stop immediately when destructive source cleanup is disabled for both inputs.
        return  # Preserve both source media files without unnecessary validation work.

    if DRY_RUN:  # Prevent all destructive filesystem changes while command preview mode is enabled.
        if ERASE_TARGET_FILES:  # Report the target deletion that would occur during a real successful run.
            print(f"\nDRY_RUN=True, target media not erased: {target_media}")  # Preserve the target while making the configured action visible.

        if ERASE_ORIGINAL_FILES:  # Report the original-source deletion that would occur during a real successful run.
            print(f"\nDRY_RUN=True, original media not erased: {original_media}")  # Preserve the original while making the configured action visible.

        return  # Complete preview-mode cleanup without touching either source file.

    validate_generated_output(output_mkv)  # Reconfirm that the generated replacement still exists and is non-empty immediately before destructive cleanup.
    validate_generated_output_for_source_erasure(output_mkv)  # Re-open and inspect the replacement to confirm required video, English, and PT-BR streams before deletion.
    output_resolved = output_mkv.resolve()  # Resolve the generated output path for exact-path source-protection comparisons.
    deletion_candidates: list[tuple[str, Path]] = []  # Initialize configured source files that may be safely erased after validation.

    if ERASE_TARGET_FILES:  # Include the higher-quality target media when target cleanup is enabled.
        deletion_candidates.append(("target", target_media))  # Queue the processed target media file for deletion.

    if ERASE_ORIGINAL_FILES:  # Include the lower-quality original media when original cleanup is enabled.
        deletion_candidates.append(("original", original_media))  # Queue the processed original source media file for deletion.

    unique_candidates: list[tuple[str, Path]] = []  # Initialize path-deduplicated source deletion candidates.
    seen_paths: set[Path] = set()  # Track resolved source paths to avoid deleting the same physical path twice.

    for source_label, source_path in deletion_candidates:  # Validate every configured source path before deleting any of them.
        source_resolved = source_path.resolve()  # Resolve the source path for output-protection and duplicate checks.

        if source_resolved == output_resolved:  # Reject any configuration that could erase the newly generated replacement itself.
            raise RuntimeError(f"Refusing to erase {source_label} media because it resolves to the generated output: {source_path}")  # Preserve the output and all sources on an unsafe path collision.

        if source_resolved in seen_paths:  # Ignore a duplicate source path when both logical inputs resolve to the same physical file.
            continue  # Avoid a second unlink attempt against an already queued physical source file.

        if not source_path.is_file():  # Require every configured source file to still exist before beginning any destructive cleanup.
            raise FileNotFoundError(f"Cannot erase processed {source_label} media because the source file no longer exists: {source_path}")  # Abort before deleting any remaining source candidate.

        seen_paths.add(source_resolved)  # Reserve the validated physical source path against duplicate deletion.
        unique_candidates.append((source_label, source_path))  # Retain the validated source candidate for the actual deletion phase.

    for source_label, source_path in unique_candidates:  # Delete validated source files only after every configured candidate passes pre-deletion checks.
        print(f"\nErasing processed {source_label} media: {source_path}")  # Announce the destructive post-success cleanup operation.
        source_path.unlink()  # Delete only the matched processed media file while preserving sidecars and parent directories.

        if source_path.exists():  # Verify the filesystem no longer exposes the deleted source path.
            raise RuntimeError(f"Processed {source_label} media still exists after deletion attempt: {source_path}")  # Report an unexpected cleanup failure immediately.

        print(f"Erased processed {source_label} media successfully.")  # Confirm successful deletion of the processed source media file.


def build_output_media_path(target_media: Path, output_directory: Path | None = None) -> Path:
    """
    Build the generated Matroska output path for one target media file.

    :param target_media: Higher-quality target media file whose filename provides the output stem.
    :param output_directory: Optional destination directory under OUTPUT_ROOT for the generated media file.
    :return: Generated MKV path.
    """

    destination_directory = output_directory if output_directory is not None else OUTPUT_ROOT  # Select the dedicated output root or a season-specific subdirectory.

    return destination_directory / f"{target_media.stem}{UPDATED_SUFFIX}.mkv"  # Build a Matroska output path on the configured output drive.


def existing_filesystem_path(path: Path) -> Path:
    """
    Return the nearest existing path that belongs to the filesystem containing a configured path.

    :param path: File or directory path whose backing filesystem must be identified.
    :return: Nearest existing path on the same filesystem.
    """

    storage_probe = path  # Start with the exact configured path so existing outputs and roots resolve directly.

    while not storage_probe.exists() and storage_probe.parent != storage_probe:  # Walk upward until an existing path on the configured filesystem is available.
        storage_probe = storage_probe.parent  # Move to the nearest existing parent without creating directories or files.

    if not storage_probe.exists():  # Reject a path whose backing filesystem cannot be resolved safely.
        raise FileNotFoundError(f"Could not resolve filesystem for: {path}")  # Prevent storage calculations against an unknown destination or source filesystem.

    return storage_probe  # Return an existing path whose device identifier and free-space information are reliable.


def paths_share_filesystem(first_path: Path, second_path: Path) -> bool:
    """
    Determine whether two paths occupy the same backing filesystem.

    :param first_path: First file or directory path to compare.
    :param second_path: Second file or directory path to compare.
    :return: True when both paths resolve to the same filesystem device.
    """

    first_probe = existing_filesystem_path(first_path)  # Resolve an existing path on the first configured filesystem.
    second_probe = existing_filesystem_path(second_path)  # Resolve an existing path on the second configured filesystem.

    return first_probe.stat().st_dev == second_probe.stat().st_dev  # Compare filesystem device identifiers instead of assuming equal or different drives from path text.


def estimated_generated_output_size(target_media: Path) -> int:
    """
    Estimate generated output size from the higher-quality target file.

    :param target_media: Higher-quality target media file providing the output video and English audio.
    :return: Conservative estimated generated MKV size in bytes.
    """

    return int(target_media.stat().st_size * OUTPUT_SIZE_SAFETY_FACTOR)  # Add the configured safety margin for injected PT-BR audio and Matroska overhead.


def validate_media_pair_output_storage(target_media: Path, output_mkv: Path) -> None:
    """
    Recheck output-drive capacity immediately before generating one media file.

    :param target_media: Higher-quality target media file used to estimate the next generated output size.
    :param output_mkv: Generated output path whose filesystem free space must be checked.
    :return: None.
    """

    if DRY_RUN:  # Skip runtime capacity enforcement because preview mode does not create any media output.
        return  # Complete without requiring disk space that DRY_RUN will never consume.

    estimated_output_bytes = estimated_generated_output_size(target_media)  # Estimate the complete temporary space needed before any source can be erased.
    existing_output_bytes = output_mkv.stat().st_size if output_mkv.is_file() and OVERWRITE else 0  # Credit an existing output only when FFmpeg is configured to replace it.
    additional_output_bytes = max(0, estimated_output_bytes - existing_output_bytes)  # Estimate new bytes that must be allocated beyond a replaceable existing output.
    reserve_bytes = MIN_FREE_SPACE_RESERVE_GB * 1024 ** 3  # Convert the configured post-processing free-space reserve from GiB to bytes.
    storage_probe = existing_filesystem_path(output_mkv)  # Resolve the actual filesystem that will receive the generated output.
    disk_usage = shutil.disk_usage(storage_probe)  # Read current free space immediately before processing this media pair.
    required_free_bytes = additional_output_bytes + reserve_bytes  # Require enough temporary space for this output while still preserving the configured reserve.

    if disk_usage.free < required_free_bytes:  # Stop before FFmpeg when actual current capacity cannot safely hold this single generated output.
        gib = 1024 ** 3  # Define the binary gigabyte divisor used for readable runtime diagnostics.
        raise RuntimeError(  # Report a pair-specific capacity shortage without relying on earlier deletion assumptions.
            f"Insufficient current free space for the next generated output under {OUTPUT_ROOT}. "
            f"Need approximately {required_free_bytes / gib:.2f} GiB including reserve for {output_mkv.name}, "
            f"but only {disk_usage.free / gib:.2f} GiB is currently free."
        )


def process_media_pair(target_media: Path, original_media: Path, output_directory: Path | None = None) -> None:
    """
    Mux one higher-quality target media file with PT-BR audio from its matching original source and optionally erase processed inputs.

    :param target_media: Higher-quality target media file providing video, English audio, subtitles, attachments, and chapters.
    :param original_media: Lower-quality original media file providing PT-BR audio.
    :param output_directory: Optional destination directory under OUTPUT_ROOT for the generated media file.
    :return: None.
    """

    destination_directory = output_directory if output_directory is not None else OUTPUT_ROOT  # Select the dedicated output root or a season-specific subdirectory.
    output_mkv = build_output_media_path(target_media, destination_directory)  # Build the generated Matroska path using the shared output-path convention.

    if output_mkv.exists() and not OVERWRITE:  # Preserve an existing generated output when overwrite is disabled.
        print(f"\nSkipping existing output: {output_mkv}")  # Report the skipped generated media file.

        return  # Stop processing the current media pair.

    validate_media_pair_output_storage(target_media, output_mkv)  # Recheck real free space immediately before this output so prior cleanup failures cannot invalidate the global estimate.
    print("\n" + "=" * 100)  # Separate the current media pair from previous terminal output.
    print(f"Target  : {target_media}")  # Display the higher-quality target media path.
    print(f"Original: {original_media}")  # Display the lower-quality PT-BR source media path.
    print(f"Output  : {output_mkv}")  # Display the generated output path on the configured output drive.
    command = build_ffmpeg_command(target_media, original_media, output_mkv)  # Build the complete FFmpeg mux command.

    if not DRY_RUN:  # Create destination folders only during real execution.
        destination_directory.mkdir(parents=True, exist_ok=True)  # Ensure the dedicated output directory exists before FFmpeg creates the MKV.

    try:  # Isolate FFmpeg execution for partial-output cleanup.
        run_command(command)  # Execute or preview the FFmpeg mux operation.

        if not DRY_RUN:  # Validate generated media only after real execution.
            validate_generated_output(output_mkv)  # Require a non-empty generated MKV file.
    except Exception:  # Handle FFmpeg execution and output validation failures.
        if not DRY_RUN:  # Avoid filesystem cleanup during command preview mode.
            remove_partial_output(output_mkv)  # Remove any incomplete generated MKV file.

        raise  # Preserve the original processing failure for aggregation.

    copy_external_srts(target_media, output_mkv)  # Copy target external SRT files already synchronized to the higher-quality release.
    erase_processed_source_files(target_media, original_media, output_mkv)  # Optionally erase processed source media only after output validation and subtitle copying succeed.


def process_root_movies(errors: list[str]) -> bool:
    """
    Process eligible movie media files located directly inside the configured roots.

    :param errors: Shared error list receiving movie processing failures.
    :return: True when at least one direct target media file is available for processing.
    """

    target_movies = iter_media_files(TARGET_ROOT)  # Collect direct higher-quality target media files while excluding generated outputs.

    if not target_movies:  # Report that the configured roots do not use the direct movie layout.
        return False  # Allow the caller to continue with season-based series processing.

    original_movies = iter_media_files(ORIGINAL_ROOT)  # Collect direct original PT-BR source media files while excluding generated outputs.

    if not original_movies:  # Handle a target movie layout without any direct original media file.
        errors.append(f"No original movie media files found directly in: {ORIGINAL_ROOT}")  # Record the missing source movie files.

        return True  # Report that a direct target movie layout was detected even though it could not be processed.

    if len(target_movies) == 1 and len(original_movies) == 1:  # Handle the unambiguous one-movie-per-root layout.
        target_media = target_movies[0]  # Select the only direct higher-quality target movie file.
        original_media = original_movies[0]  # Select the only direct original PT-BR source movie regardless of filename differences.

        try:  # Isolate the single movie processing failure for aggregated reporting.
            process_media_pair(target_media, original_media, OUTPUT_ROOT)  # Mux the unambiguous movie pair into the dedicated output root.
        except Exception as exception:  # Aggregate the movie failure without bypassing the common error summary.
            errors.append(f"{target_media}\n{type(exception).__name__}: {exception}")  # Store the movie path and exception details.

        return True  # Complete direct movie processing after the unique pair is handled.

    for target_media in target_movies:  # Process multiple direct target movies deterministically by filename.
        try:  # Isolate filename resolution and movie processing failures.
            original_media = resolve_original_media(ORIGINAL_ROOT, target_media)  # Resolve a same-named original movie without guessing among multiple files.

            if original_media is None:  # Handle a direct target movie without an unambiguous original filename or stem match.
                print(f"\nSkipping target movie without a common original counterpart: {target_media}")  # Report the intentionally skipped non-common movie.

                continue  # Continue with the next direct target movie.

            process_media_pair(target_media, original_media, OUTPUT_ROOT)  # Mux the resolved direct movie pair into the dedicated output root.
        except Exception as exception:  # Aggregate one direct movie failure without stopping the remaining files.
            errors.append(f"{target_media}\n{type(exception).__name__}: {exception}")  # Store the movie path and exception details.

    return True  # Report that the direct movie layout was found and processed.


def process_target_season(target_season: Path, original_season: Path, season_number: int, errors: list[str]) -> None:
    """
    Process every common target/source episode in one matched season directory.

    :param target_season: Higher-quality target season directory containing descriptive episode filenames.
    :param original_season: Lower-quality original season directory containing PT-BR source episodes.
    :param season_number: Matched numeric season identifier used for safe episode-number matching.
    :param errors: Shared error list receiving episode processing failures.
    :return: None.
    """

    output_season = OUTPUT_ROOT / target_season.name  # Preserve the target season folder name beneath the dedicated G: output root.

    for target_media in iter_media_files(target_season):  # Process target media files in deterministic order.
        try:  # Isolate episode resolution and processing failures.
            original_media = resolve_original_media(original_season, target_media, season_number)  # Match descriptive SxxExx targets to numeric source filenames such as "01.mp4".

            if original_media is None:  # Handle target episodes that do not exist in the matched original season.
                print(f"\nSkipping target episode without a common original counterpart: {target_media}")  # Report the intentionally skipped non-common episode.

                continue  # Continue with the next target episode because only common episodes should be processed.

            process_media_pair(target_media, original_media, output_season)  # Mux the common episode pair into the dedicated season output directory.
        except Exception as exception:  # Aggregate one episode failure without stopping the remaining season.
            errors.append(f"{target_media}\n{type(exception).__name__}: {exception}")  # Store the episode path and exception details.


def matched_media_pairs() -> list[MatchedMediaPair]:
    """
    Return unambiguous target/original media pairs with their generated output paths in processing order.

    :return: Ordered list of target media, matching original media, and generated output path tuples.
    """

    matched_pairs: list[MatchedMediaPair] = []  # Initialize matched media pairs used for storage simulation and diagnostics.
    target_movies = iter_media_files(TARGET_ROOT)  # Collect direct higher-quality target movie files when the configured roots use movie layout.
    original_movies = iter_media_files(ORIGINAL_ROOT)  # Collect direct lower-quality original movie files when the configured roots use movie layout.

    if len(target_movies) == 1 and len(original_movies) == 1:  # Handle the unambiguous direct one-movie layout.
        target_media = target_movies[0]  # Select the only direct higher-quality target movie.
        original_media = original_movies[0]  # Select the only direct original PT-BR source movie.
        output_mkv = build_output_media_path(target_media, OUTPUT_ROOT)  # Build the direct movie output path beneath the configured output root.
        matched_pairs.append((target_media, original_media, output_mkv))  # Retain the complete direct movie pair for ordered storage simulation.
    elif target_movies and original_movies:  # Handle multiple direct movies using only safe filename/stem matches.
        for target_media in target_movies:  # Inspect each direct target movie candidate in the same order used by processing.
            try:  # Ignore ambiguous candidates here because processing will report them with full context.
                original_media = resolve_original_media(ORIGINAL_ROOT, target_media)  # Resolve a safe matching original direct movie.

                if original_media is not None:  # Include only direct movies with an unambiguous original counterpart.
                    output_mkv = build_output_media_path(target_media, OUTPUT_ROOT)  # Build the direct movie output path beneath the configured output root.
                    matched_pairs.append((target_media, original_media, output_mkv))  # Add the complete direct movie pair to the ordered storage simulation.
            except RuntimeError:  # Defer ambiguous direct movie reporting to the processing phase.
                continue  # Exclude the unresolved candidate from storage simulation.

    original_seasons = build_original_season_map()  # Build original season lookup using verbose or compact supported season naming.

    for target_season in sorted(TARGET_ROOT.iterdir(), key=lambda entry: entry.name.casefold()):  # Inspect higher-quality target season directories in the same deterministic order used by processing.
        if not target_season.is_dir():  # Ignore files and other non-directory target-root entries.
            continue  # Continue with the next target-root entry.

        season_number = season_key(target_season)  # Resolve a target season identifier such as S02.

        if season_number is None:  # Ignore target folders that are not recognized as seasons.
            continue  # Continue with the next target folder.

        original_season = original_seasons.get(season_number)  # Resolve the original season folder such as "Breaking Bad - Season 02 ...".

        if original_season is None:  # Skip seasons that are not common to both configured roots.
            continue  # Continue with the next target season.

        output_season = OUTPUT_ROOT / target_season.name  # Preserve the target season folder name beneath the configured output root.

        for target_media in iter_media_files(target_season):  # Inspect target episodes in the same deterministic order used by processing.
            try:  # Ignore ambiguous candidates here because processing will report them with full context.
                original_media = resolve_original_media(original_season, target_media, season_number)  # Resolve the matching numeric or descriptive original episode.

                if original_media is not None:  # Include only episodes with a safe common season/episode source match.
                    output_mkv = build_output_media_path(target_media, output_season)  # Build the generated episode path beneath the matching output season directory.
                    matched_pairs.append((target_media, original_media, output_mkv))  # Add the complete episode pair to the ordered storage simulation.
            except RuntimeError:  # Defer ambiguous episode reporting to the processing phase.
                continue  # Exclude the unresolved candidate from storage simulation.

    return matched_pairs  # Preserve processing order so peak-space simulation matches the real sequential workflow.


def matched_target_media_files() -> list[Path]:
    """
    Return higher-quality target media files that have an unambiguous original counterpart.

    :return: Ordered list of target media files expected to generate or match outputs.
    """

    return [target_media for target_media, _, _ in matched_media_pairs()]  # Preserve the compatibility helper while deriving its result from complete matched pairs.



def validate_output_storage() -> None:
    """
    Validate peak output-drive capacity while accounting for configured sequential source-file erasure.

    :return: None.
    """

    matched_pairs = matched_media_pairs()  # Resolve complete target/original/output relationships in the same order used by real processing.

    if not matched_pairs:  # Stop when there are no common movie or episode pairs to process.
        raise RuntimeError("No common target/original media pairs were found for the configured roots.")  # Prevent an apparently successful run that produces nothing.

    reserve_bytes = MIN_FREE_SPACE_RESERVE_GB * 1024 ** 3  # Convert the configured post-processing free-space reserve from GiB to bytes.
    storage_probe = existing_filesystem_path(OUTPUT_ROOT)  # Resolve an existing path on the actual output filesystem without creating anything.
    disk_usage = shutil.disk_usage(storage_probe)  # Read total, used, and free bytes from the output filesystem before processing starts.
    running_additional_bytes = 0  # Track net output-filesystem growth relative to the current pre-run filesystem state.
    peak_additional_bytes = 0  # Track the maximum temporary growth reached before configured source deletion occurs for each pair.
    target_bytes = 0  # Accumulate target sizes for media pairs that will actually create or overwrite outputs.
    estimated_output_bytes = 0  # Accumulate conservative generated-output sizes for diagnostic reporting.
    reclaimable_target_bytes = 0  # Accumulate target bytes that configured deletion will return to the output filesystem.
    reclaimable_original_bytes = 0  # Accumulate original bytes that configured deletion will return to the output filesystem.
    replaceable_output_bytes = 0  # Accumulate existing output bytes that OVERWRITE can reclaim before writing replacement contents.
    pairs_requiring_output = 0  # Count matched pairs that will not be skipped by the existing-output policy.

    for target_media, original_media, output_mkv in matched_pairs:  # Simulate each pair in the same sequential order used by the real mux workflow.
        if output_mkv.exists() and not OVERWRITE:  # Mirror process_media_pair behavior for existing outputs that are intentionally preserved.
            continue  # Skipped outputs allocate no new space and never trigger source-file deletion.

        pairs_requiring_output += 1  # Count this pair because FFmpeg is expected to generate or replace its output.
        current_target_bytes = target_media.stat().st_size  # Read the target size that forms the baseline generated-output estimate.
        current_estimated_output_bytes = estimated_generated_output_size(target_media)  # Estimate the complete generated output before any post-success deletion.
        target_bytes += current_target_bytes  # Add this target to the diagnostic baseline total.
        estimated_output_bytes += current_estimated_output_bytes  # Add this output to the diagnostic conservative total.

        if output_mkv.is_file() and OVERWRITE:  # Account for an existing output that FFmpeg will replace rather than coexist with indefinitely.
            existing_output_bytes = output_mkv.stat().st_size  # Read currently allocated bytes that can be reclaimed when replacement starts.
            replaceable_output_bytes += existing_output_bytes  # Track replaceable output capacity for diagnostic reporting.
            running_additional_bytes -= existing_output_bytes  # Model FFmpeg replacing/truncating the prior output before allocating the new output contents.

        running_additional_bytes += current_estimated_output_bytes  # Model the complete new output existing before either source file is allowed to be erased.
        peak_additional_bytes = max(peak_additional_bytes, running_additional_bytes)  # Preserve the maximum temporary output-filesystem growth reached so far.
        reclaimed_source_paths: set[Path] = set()  # Prevent double-crediting when target and original resolve to the same physical source file.

        if ERASE_TARGET_FILES and paths_share_filesystem(target_media, output_mkv):  # Credit target deletion only when it actually frees the filesystem receiving outputs.
            target_resolved = target_media.resolve()  # Resolve the target source path for duplicate-source accounting.

            if target_resolved != output_mkv.resolve() and target_resolved not in reclaimed_source_paths:  # Exclude unsafe output collisions and duplicate physical source paths.
                running_additional_bytes -= current_target_bytes  # Model target deletion immediately after this generated output passes validation and subtitle copying.
                reclaimable_target_bytes += current_target_bytes  # Track target bytes genuinely returned to the output filesystem.
                reclaimed_source_paths.add(target_resolved)  # Prevent another logical source from crediting the same physical file.

        if ERASE_ORIGINAL_FILES and paths_share_filesystem(original_media, output_mkv):  # Credit original deletion only when it actually frees the filesystem receiving outputs.
            original_resolved = original_media.resolve()  # Resolve the original source path for duplicate-source accounting.

            if original_resolved != output_mkv.resolve() and original_resolved not in reclaimed_source_paths:  # Exclude unsafe output collisions and duplicate physical source paths.
                current_original_bytes = original_media.stat().st_size  # Read the lower-quality source size that will be reclaimed after successful processing.
                running_additional_bytes -= current_original_bytes  # Model original-source deletion after the generated replacement has passed all safety checks.
                reclaimable_original_bytes += current_original_bytes  # Track original bytes genuinely returned to the output filesystem.
                reclaimed_source_paths.add(original_resolved)  # Prevent double-crediting the same physical source file.

    required_with_reserve = max(0, peak_additional_bytes) + reserve_bytes  # Require only the simulated peak additional allocation plus the configured free-space reserve.
    gib = 1024 ** 3  # Define the binary gigabyte divisor used for readable storage diagnostics.

    print("\nStorage preflight:")  # Announce the destination-drive capacity simulation.
    print(f"  Output root             : {OUTPUT_ROOT}")  # Display the configured generated-output location.
    print(f"  Matched media pairs     : {len(matched_pairs)}")  # Display all unambiguous common pairs regardless of existing-output skipping.
    print(f"  Pairs requiring output  : {pairs_requiring_output}")  # Display how many pairs actually require allocation under the overwrite policy.
    print(f"  Matched target size     : {target_bytes / gib:.2f} GiB")  # Display target sizes for outputs that will actually be generated or replaced.
    print(f"  Estimated output total  : {estimated_output_bytes / gib:.2f} GiB")  # Display total output bytes without incorrectly requiring all of them as additional free space.
    print(f"  ERASE_TARGET_FILES      : {ERASE_TARGET_FILES}")  # Display whether successful target files are configured for deletion.
    print(f"  ERASE_ORIGINAL_FILES    : {ERASE_ORIGINAL_FILES}")  # Display whether successful original files are configured for deletion.
    print(f"  Target reclaim on output: {reclaimable_target_bytes / gib:.2f} GiB")  # Display target deletion capacity that genuinely helps the output filesystem.
    print(f"  Original reclaim output : {reclaimable_original_bytes / gib:.2f} GiB")  # Display original deletion capacity that genuinely helps the output filesystem.
    print(f"  Replaceable outputs     : {replaceable_output_bytes / gib:.2f} GiB")  # Display existing output capacity reusable when OVERWRITE is enabled.
    print(f"  Peak additional storage : {max(0, peak_additional_bytes) / gib:.2f} GiB")  # Display the maximum simulated extra allocation before per-pair cleanup.
    print(f"  Current output free     : {disk_usage.free / gib:.2f} GiB")  # Display currently available destination-filesystem capacity.
    print(f"  Required free reserve   : {MIN_FREE_SPACE_RESERVE_GB:.2f} GiB")  # Display the free-space reserve preserved throughout processing.
    print(f"  Required peak free      : {required_with_reserve / gib:.2f} GiB")  # Display the actual peak free-space requirement after erasure-aware simulation.

    if DRY_RUN:  # Preview mode creates no outputs and deletes no sources, so capacity must not block command inspection.
        print("  Storage enforcement     : skipped because DRY_RUN=True")  # Explain why the calculated real-run estimate is informational only.

        return  # Complete preview-mode preflight without rejecting insufficient real-run capacity.

    if disk_usage.free < required_with_reserve:  # Reject processing only when the erasure-aware peak cannot fit while preserving the configured reserve.
        raise RuntimeError(  # Report the simulated peak capacity shortfall before FFmpeg creates any large output.
            f"Insufficient peak free space under output root {OUTPUT_ROOT}. "
            f"Need approximately {required_with_reserve / gib:.2f} GiB including reserve after accounting for configured source erasure, "
            f"but only {disk_usage.free / gib:.2f} GiB is currently free."
        )


def print_processing_errors(errors: list[str]) -> None:
    """
    Print aggregated movie, season, and episode processing errors.

    :param errors: Processing error descriptions collected during execution.
    :return: None.
    """

    print("\n" + "=" * 100)  # Separate the error summary from episode output.
    print("Finished with errors:")  # Announce unsuccessful batch completion.

    for error in errors:  # Print every collected processing error.
        print("\n---")  # Separate the current error from the previous entry.
        print(error)  # Display the complete error description.


def main() -> None:
    """
    Process every configured common movie pair and common season/episode pair.

    :return: None.
    """

    if not ORIGINAL_ROOT.exists():  # Validate the configured lower-quality original PT-BR source root.
        raise FileNotFoundError(f"Original root does not exist: {ORIGINAL_ROOT}")  # Stop before processing an unavailable source root.

    if not TARGET_ROOT.exists():  # Validate the configured higher-quality target root.
        raise FileNotFoundError(f"Target root does not exist: {TARGET_ROOT}")  # Stop before processing an unavailable target root.

    validate_output_storage()  # Verify that the dedicated output drive can hold the expected matched outputs before starting FFmpeg.
    errors: list[str] = []  # Initialize aggregated movie, season, and episode processing errors.
    processed_root_movies = process_root_movies(errors)  # Process supported media files located directly inside configured movie roots when present.
    original_seasons = build_original_season_map()  # Build the original season lookup by season number using supported season naming forms.
    processed_target_seasons = False  # Track whether the target root contains at least one recognized season directory.

    for target_season in sorted(TARGET_ROOT.iterdir(), key=lambda entry: entry.name.casefold()):  # Inspect target root entries in deterministic order.
        if not target_season.is_dir():  # Ignore files and other non-directory entries.
            continue  # Continue with the next target root entry.

        season_number = season_key(target_season)  # Extract a target season number from forms such as "S02" or "Season 02".

        if season_number is None:  # Handle directories without a recognizable season number.
            print(f"\nSkipping folder without season number: {target_season}")  # Report the skipped target directory.

            continue  # Continue with the next target season directory.

        original_season = original_seasons.get(season_number)  # Resolve the matching lower-quality original season directory.

        if original_season is None:  # Handle target seasons without a common original counterpart.
            print(f"\nSkipping target season without a common original counterpart: {target_season}")  # Report the intentionally skipped non-common season.

            continue  # Continue with the next target season directory.

        processed_target_seasons = True  # Record that at least one common season-based series layout was found.
        process_target_season(target_season, original_season, season_number, errors)  # Process only common episodes in the matched season.

    if not processed_root_movies and not processed_target_seasons:  # Reject roots that contain neither common direct movies nor common season directories.
        raise RuntimeError(  # Report the supported common-media layouts required for processing.
            f"No common direct movie files or matching target/original season folders found between:\n"
            f"Target  : {TARGET_ROOT}\n"
            f"Original: {ORIGINAL_ROOT}"
        )

    if errors:  # Report all collected failures after processing every common media layout.
        print_processing_errors(errors)  # Print the aggregated error summary.
    else:  # Handle complete batch success.
        print("\nFinished successfully.")  # Report successful completion.


if __name__ == "__main__":  # Execute the program only when invoked as a script.
    main()  # Start the configured audio track muxing workflow.
