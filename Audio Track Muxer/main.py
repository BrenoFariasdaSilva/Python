"""
================================================================================
Audio Track Muxer
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-07-12
Description :
    Muxes video and attachments from higher-resolution target MKV episodes with
    English and PT-BR audio plus non-forced subtitles from matching original
    MKV episodes. Matching external SRT files are copied beside each output.

    Key features include:
        - Season and episode matching across configured source directories.
        - English and PT-BR audio detection with configurable order fallback.
        - Non-forced internal subtitle preservation with normalized metadata.
        - External SRT discovery, collision-safe naming, and metadata copying.
        - Dry-run support, overwrite control, and partial-output cleanup.

Usage:
    1. Configure ORIGINAL_ROOT, TARGET_ROOT, DRY_RUN, OVERWRITE, and the optional
       FALLBACK_ORIGINAL_AUDIO_ORDER value.
    2. Ensure FFmpeg and FFprobe are available through FFMPEG and FFPROBE.
    3. Execute the script with: python main.py

Outputs:
    - One <episode>-updated.mkv file beside each processed target episode.
    - Matching external SRT files renamed beside the generated MKV output.

Dependencies:
    - Python >= 3.10.
    - FFmpeg.
    - FFprobe.

Assumptions & Notes:
    - Target season directory names contain a value such as "Season 01".
    - Matching original and target episodes use equal filenames, ignoring case.
    - The original MKV contains identifiable English and PT-BR audio tracks or
      FALLBACK_ORIGINAL_AUDIO_ORDER is configured.
"""

import json  # Parse FFprobe JSON output.
import re  # Match season numbers and normalized language tokens.
import shutil  # Copy external subtitle files with metadata preservation.
import subprocess  # Execute FFmpeg and FFprobe commands.
import unicodedata  # Remove diacritics from language and track metadata.
from pathlib import Path  # Represent configured directories and media paths.
from typing import Any, Literal, cast  # Define precise JSON and language types.


LanguageClass = Literal["english", "ptbr"]  # Restrict supported audio language classes.
FallbackAudioOrder = tuple[LanguageClass, LanguageClass] | None  # Define the optional source audio order.
Stream = dict[str, Any]  # Represent one FFprobe stream dictionary.
MediaInfo = dict[str, Any]  # Represent parsed FFprobe media information.

ORIGINAL_ROOT = Path(r"F:\Series\The Punisher")  # Preserve the configured original media root.
TARGET_ROOT = Path(r"D:\Sem Backup\Download\Torrent\Completed\Marvels.The.Punisher")  # Preserve the configured target media root.
FFMPEG = "ffmpeg"  # Select the configured FFmpeg executable.
FFPROBE = "ffprobe"  # Select the configured FFprobe executable.
UPDATED_SUFFIX = "-updated"  # Append the configured suffix to generated MKV files.
DRY_RUN = False  # Execute commands instead of only printing planned operations.
OVERWRITE = False  # Preserve existing generated outputs when disabled.
FALLBACK_ORIGINAL_AUDIO_ORDER: FallbackAudioOrder = None  # Preserve automatic audio language detection by default.



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

    match = re.search(r"season\s*0*(\d+)", path.name, re.IGNORECASE)  # Locate a season number in the directory name.

    if match is None:  # Handle directories without a recognizable season number.
        return None  # Report that no season key was found.

    return int(match.group(1))  # Return the parsed numeric season key.



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



def iter_mkv_files(directory: Path, include_updated: bool = False) -> list[Path]:
    """
    Return sorted MKV files from a directory with case-insensitive extensions.

    :param directory: Directory containing candidate media files.
    :param include_updated: Whether generated files with UPDATED_SUFFIX are included.
    :return: Sorted list of matching MKV file paths.
    """

    media_files = [entry for entry in directory.iterdir() if entry.is_file() and entry.suffix.lower() == ".mkv"]  # Retain MKV files regardless of extension case.

    if not include_updated:  # Exclude previously generated outputs by default.
        media_files = [entry for entry in media_files if not entry.stem.lower().endswith(UPDATED_SUFFIX.lower())]  # Remove files carrying the configured output suffix.

    return sorted(media_files, key=lambda entry: entry.name.casefold())  # Return deterministic case-insensitive filename ordering.



def resolve_original_mkv(original_season: Path, target_mkv: Path) -> Path | None:
    """
    Resolve the original episode matching a target MKV filename.

    :param original_season: Original season directory containing source episodes.
    :param target_mkv: Target episode whose source counterpart is required.
    :return: Matching original MKV path or None when no match exists.
    """

    exact_match = original_season / target_mkv.name  # Build the original path using the exact target filename.

    if exact_match.is_file():  # Prefer the exact filesystem filename match.
        return exact_match  # Return the exact matching original episode.

    casefolded_name = target_mkv.name.casefold()  # Normalize the target filename for case-insensitive matching.
    matching_files = [candidate for candidate in iter_mkv_files(original_season, include_updated=True) if candidate.name.casefold() == casefolded_name]  # Locate case-insensitive original filename matches.

    if len(matching_files) > 1:  # Reject ambiguous filenames on case-sensitive filesystems.
        raise RuntimeError(f"Multiple original files match target episode: {target_mkv}")  # Prevent selecting an arbitrary original episode.

    return matching_files[0] if matching_files else None  # Return the unique match when available.



def select_audio_tracks(original_mkv: Path, streams: list[Stream]) -> list[Stream]:
    """
    Select English and PT-BR non-commentary audio streams in output order.

    :param original_mkv: Original MKV path used in validation errors.
    :param streams: FFprobe stream dictionaries from the original MKV.
    :return: English and PT-BR audio streams in the required output order.
    """

    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio" and not is_commentary_audio(stream)]  # Retain non-commentary audio streams.
    english_stream: Stream | None = None  # Initialize the detected English audio stream.
    ptbr_stream: Stream | None = None  # Initialize the detected Brazilian Portuguese audio stream.

    for stream in audio_streams:  # Inspect each eligible audio stream in source order.
        language_class = classify_language(stream)  # Classify the stream language metadata.

        if language_class == "english" and english_stream is None:  # Retain the first detected English stream.
            english_stream = stream  # Store the English stream selection.
        elif language_class == "ptbr" and ptbr_stream is None:  # Retain the first detected Brazilian Portuguese stream.
            ptbr_stream = stream  # Store the Brazilian Portuguese stream selection.

    if english_stream is None or ptbr_stream is None:  # Handle incomplete automatic language detection.
        if FALLBACK_ORIGINAL_AUDIO_ORDER is not None:  # Apply the configured deterministic source order.
            if FALLBACK_ORIGINAL_AUDIO_ORDER not in {("english", "ptbr"), ("ptbr", "english")}:  # Validate the supported fallback configurations.
                raise RuntimeError("Invalid FALLBACK_ORIGINAL_AUDIO_ORDER. Use None, ('english', 'ptbr'), or ('ptbr', 'english').")  # Reject unsupported fallback values.

            if len(audio_streams) < 2:  # Validate that both fallback positions exist.
                raise RuntimeError(f"Not enough audio tracks in original file: {original_mkv}")  # Reject incomplete source audio layouts.

            first_stream, second_stream = audio_streams[0], audio_streams[1]  # Select the first two eligible source audio streams.

            if FALLBACK_ORIGINAL_AUDIO_ORDER == ("english", "ptbr"):  # Apply English-first fallback ordering.
                english_stream, ptbr_stream = first_stream, second_stream  # Assign both streams from the configured order.
            else:  # Apply Brazilian Portuguese-first fallback ordering.
                ptbr_stream, english_stream = first_stream, second_stream  # Assign both streams from the configured order.

    if english_stream is None or ptbr_stream is None:  # Handle unresolved required audio languages.
        debug_lines: list[str] = []  # Initialize diagnostic stream descriptions.

        for stream in audio_streams:  # Describe every eligible audio stream for the error report.
            tags = stream_tags(stream)  # Resolve the stream tag dictionary.
            debug_lines.append(  # Add one diagnostic line for the current stream.
                f"index={stream.get('index')} "  # Include the global stream index.
                f"codec={stream.get('codec_name')} "  # Include the audio codec name.
                f"language={tags.get('language') or tags.get('LANGUAGE')} "  # Include the available language tag.
                f"title={tags.get('title') or tags.get('TITLE')}"  # Include the available track title.
            )

        detected_streams = "\n".join(debug_lines) if debug_lines else "No eligible audio streams were detected."  # Serialize detected stream diagnostics.
        raise RuntimeError(  # Report missing required language tracks.
            f"Could not detect both English and PT-BR audio tracks in:\n"  # Describe the language detection failure.
            f"{original_mkv}\n\n"  # Include the affected original media path.
            f"Detected audio streams:\n{detected_streams}"  # Include stream metadata diagnostics.
        )

    english_index = stream_index(english_stream, original_mkv)  # Validate the selected English global stream index.
    ptbr_index = stream_index(ptbr_stream, original_mkv)  # Validate the selected Brazilian Portuguese global stream index.

    if english_index == ptbr_index:  # Prevent duplicate mappings of one source audio stream.
        raise RuntimeError(f"English and PT-BR resolved to the same stream in: {original_mkv}")  # Reject an invalid duplicate selection.

    return [english_stream, ptbr_stream]  # Return English first and Brazilian Portuguese second.



def select_subtitle_tracks(streams: list[Stream]) -> list[Stream]:
    """
    Select every non-forced internal subtitle stream.

    :param streams: FFprobe stream dictionaries from the original MKV.
    :return: Non-forced subtitle streams in source order.
    """

    subtitle_streams = [stream for stream in streams if stream.get("codec_type") == "subtitle" and not is_forced(stream)]  # Retain non-forced subtitle streams.

    return subtitle_streams  # Return subtitles in their original stream order.



def matching_external_srts(original_mkv: Path) -> list[Path]:
    """
    Find non-forced external SRT files associated with an original episode.

    :param original_mkv: Original MKV path used as the episode filename prefix.
    :return: Sorted matching external SRT paths.
    """

    episode_stem = original_mkv.stem.casefold()  # Normalize the episode stem for case-insensitive matching.
    candidates: list[Path] = []  # Initialize matching external subtitle paths.

    for subtitle_path in original_mkv.parent.iterdir():  # Inspect files beside the original episode.
        if not subtitle_path.is_file() or subtitle_path.suffix.lower() != ".srt":  # Ignore directories and non-SRT files.
            continue  # Continue with the next neighboring entry.

        subtitle_stem = subtitle_path.stem.casefold()  # Normalize the external subtitle stem.
        same_episode = (  # Evaluate supported episode filename relationships.
            subtitle_stem == episode_stem  # Match an equal episode stem.
            or subtitle_stem.startswith(f"{episode_stem}.")  # Match a period-delimited suffix.
            or subtitle_stem.startswith(f"{episode_stem} ")  # Match a space-delimited suffix.
            or subtitle_stem.startswith(f"{episode_stem}-")  # Match a hyphen-delimited suffix.
            or subtitle_stem.startswith(f"{episode_stem}_")  # Match an underscore-delimited suffix.
        )

        if same_episode and not is_forced(subtitle_path.name):  # Retain associated subtitles without forced markers.
            candidates.append(subtitle_path)  # Add the external subtitle candidate.

    return sorted(candidates, key=lambda entry: entry.name.casefold())  # Return deterministic case-insensitive filename ordering.



def external_subtitle_destination(output_mkv: Path, subtitle_path: Path, subtitle_number: int, subtitle_count: int) -> Path:
    """
    Build the preferred destination path for an external subtitle file.

    :param output_mkv: Generated MKV path that determines the destination stem.
    :param subtitle_path: Source external subtitle path used for language classification.
    :param subtitle_number: One-based subtitle position used for fallback naming.
    :param subtitle_count: Total number of matching external subtitles.
    :return: Preferred destination SRT path.
    """

    if subtitle_count == 1:  # Preserve the simple output stem for a single external subtitle.
        destination_name = f"{output_mkv.stem}.srt"  # Build the single-subtitle destination filename.
    else:  # Add language or positional metadata when multiple subtitles exist.
        language_class = classify_language(subtitle_path.name)  # Classify language tokens from the source filename.

        if language_class == "english":  # Handle an English external subtitle filename.
            clean_name = "English"  # Select the normalized English title.
        elif language_class == "ptbr":  # Handle a Brazilian Portuguese external subtitle filename.
            clean_name = "PT-BR"  # Select the normalized Brazilian Portuguese title.
        else:  # Handle unknown external subtitle languages.
            clean_name = f"Subtitle-{subtitle_number}"  # Build a deterministic positional title.

        destination_name = f"{output_mkv.stem}.{clean_name}.srt"  # Build the multi-subtitle destination filename.

    return output_mkv.parent / destination_name  # Return the preferred destination path.



def copy_external_srts(original_mkv: Path, output_mkv: Path) -> None:
    """
    Copy matching external SRT files beside a generated MKV output.

    :param original_mkv: Original MKV path used to discover source SRT files.
    :param output_mkv: Generated MKV path used for destination naming.
    :return: None.
    """

    subtitle_paths = matching_external_srts(original_mkv)  # Discover associated non-forced external SRT files.

    if not subtitle_paths:  # Stop when the episode has no matching external subtitles.
        return  # Complete without creating subtitle files.

    print("\nExternal SRT files to copy:")  # Announce external subtitle copy operations.
    used_destinations: set[Path] = set()  # Track destinations selected during the current episode.

    for subtitle_number, subtitle_path in enumerate(subtitle_paths, start=1):  # Process external subtitles in deterministic order.
        destination = external_subtitle_destination(output_mkv, subtitle_path, subtitle_number, len(subtitle_paths))  # Build the preferred destination path.
        collision_number = 2  # Initialize the alternate filename counter.

        while destination in used_destinations or (destination.exists() and not OVERWRITE):  # Avoid in-memory and filesystem destination collisions.
            destination = output_mkv.parent / f"{output_mkv.stem}.Subtitle-{subtitle_number}-{collision_number}.srt"  # Build the next collision-safe destination.
            collision_number += 1  # Advance the collision suffix for another attempt.

        used_destinations.add(destination)  # Reserve the selected destination for this episode.
        print(f"  {subtitle_path} -> {destination}")  # Display the planned external subtitle copy.

        if not DRY_RUN:  # Perform filesystem changes only outside preview mode.
            shutil.copy2(subtitle_path, destination)  # Copy subtitle contents and filesystem metadata.



def build_ffmpeg_command(target_mkv: Path, original_mkv: Path, output_mkv: Path) -> list[str]:
    """
    Build the FFmpeg mux command for one target and original episode pair.

    :param target_mkv: Higher-resolution target MKV providing video and attachments.
    :param original_mkv: Original MKV providing English, PT-BR, and subtitle streams.
    :param output_mkv: Destination MKV path.
    :return: Complete FFmpeg command and argument list.
    """

    original_info = probe_media(original_mkv)  # Read stream metadata from the original episode.
    streams = extract_streams(original_info, original_mkv)  # Validate and extract original stream dictionaries.
    audio_tracks = select_audio_tracks(original_mkv, streams)  # Select English and Brazilian Portuguese audio streams.
    subtitle_tracks = select_subtitle_tracks(streams)  # Select every non-forced internal subtitle stream.
    command = [  # Initialize the FFmpeg mux command.
        FFMPEG,  # Select the configured FFmpeg executable.
        "-hide_banner",  # Suppress the FFmpeg startup banner.
        "-y" if OVERWRITE else "-n",  # Apply the configured output overwrite policy.
        "-i",  # Declare the target episode input.
        str(target_mkv),  # Supply the target episode path as input zero.
        "-i",  # Declare the original episode input.
        str(original_mkv),  # Supply the original episode path as input one.
        "-map",  # Add a stream mapping directive.
        "0:v?",  # Preserve every video stream from the target episode when present.
        "-map",  # Add another stream mapping directive.
        "0:t?",  # Preserve every attachment stream from the target episode when present.
    ]

    for audio_track in audio_tracks:  # Map required original audio streams in output order.
        command.extend(["-map", f"1:{stream_index(audio_track, original_mkv)}"])  # Map one validated global audio stream index from input one.

    for subtitle_track in subtitle_tracks:  # Map non-forced original subtitle streams in source order.
        command.extend(["-map", f"1:{stream_index(subtitle_track, original_mkv)}"])  # Map one validated global subtitle stream index from input one.

    command.extend(  # Add container-level mapping and codec behavior.
        [  # Define metadata, chapter, and codec arguments.
            "-map_metadata",  # Configure global metadata mapping.
            "-1",  # Remove source global metadata from the output container.
            "-map_chapters",  # Configure chapter mapping.
            "0",  # Preserve chapters from the target episode.
            "-c",  # Configure a codec policy for every mapped stream.
            "copy",  # Copy all mapped streams without re-encoding.
        ]
    )
    command.extend(  # Add normalized audio metadata and dispositions.
        [  # Define output audio stream metadata arguments.
            "-metadata:s:a:0",  # Select metadata for the first output audio stream.
            "language=eng",  # Tag the first output audio stream as English.
            "-metadata:s:a:0",  # Select another metadata field for the first output audio stream.
            "title=English",  # Title the first output audio stream as English.
            "-disposition:a:0",  # Configure the first output audio stream disposition.
            "default",  # Mark English as the default audio stream.
            "-metadata:s:a:1",  # Select metadata for the second output audio stream.
            "language=por",  # Tag the second output audio stream as Portuguese.
            "-metadata:s:a:1",  # Select another metadata field for the second output audio stream.
            "title=PT-BR",  # Title the second output audio stream as Brazilian Portuguese.
            "-disposition:a:1",  # Configure the second output audio stream disposition.
            "0",  # Clear default and special dispositions from the second audio stream.
        ]
    )

    for subtitle_number, subtitle_track in enumerate(subtitle_tracks):  # Configure each output subtitle stream in mapped order.
        language_code, clean_title = subtitle_metadata(subtitle_track, subtitle_number + 1)  # Resolve normalized subtitle metadata.
        command.extend(  # Add metadata and disposition arguments for one subtitle stream.
            [  # Define output subtitle stream metadata arguments.
                f"-metadata:s:s:{subtitle_number}",  # Select the subtitle language metadata field.
                f"language={language_code}",  # Apply the resolved subtitle language code.
                f"-metadata:s:s:{subtitle_number}",  # Select the subtitle title metadata field.
                f"title={clean_title}",  # Apply the resolved subtitle title.
                f"-disposition:s:{subtitle_number}",  # Configure the subtitle stream disposition.
                "default" if subtitle_number == 0 else "0",  # Mark only the first copied subtitle as default.
            ]
        )

    command.append(str(output_mkv))  # Append the destination MKV path.

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



def process_episode(target_mkv: Path, original_mkv: Path) -> None:
    """
    Mux one target episode with audio and subtitles from its original episode.

    :param target_mkv: Higher-resolution target MKV providing video and attachments.
    :param original_mkv: Original MKV providing audio and subtitles.
    :return: None.
    """

    output_mkv = target_mkv.with_name(f"{target_mkv.stem}{UPDATED_SUFFIX}{target_mkv.suffix}")  # Build the generated episode path.

    if output_mkv.exists() and not OVERWRITE:  # Preserve an existing generated output when overwrite is disabled.
        print(f"\nSkipping existing output: {output_mkv}")  # Report the skipped generated episode.

        return  # Stop processing the current episode.

    print("\n" + "=" * 100)  # Separate the current episode from previous terminal output.
    print(f"Target  : {target_mkv}")  # Display the target episode path.
    print(f"Original: {original_mkv}")  # Display the original episode path.
    print(f"Output  : {output_mkv}")  # Display the generated episode path.
    command = build_ffmpeg_command(target_mkv, original_mkv, output_mkv)  # Build the complete FFmpeg mux command.

    try:  # Isolate FFmpeg execution for partial-output cleanup.
        run_command(command)  # Execute or preview the FFmpeg mux operation.

        if not DRY_RUN:  # Validate generated media only after real execution.
            validate_generated_output(output_mkv)  # Require a non-empty generated MKV file.
    except Exception:  # Handle FFmpeg execution and output validation failures.
        if not DRY_RUN:  # Avoid filesystem cleanup during command preview mode.
            remove_partial_output(output_mkv)  # Remove any incomplete generated MKV file.

        raise  # Preserve the original processing failure for aggregation.

    copy_external_srts(original_mkv, output_mkv)  # Copy associated non-forced external SRT files.



def process_target_season(target_season: Path, original_season: Path, errors: list[str]) -> None:
    """
    Process every eligible target MKV in one matched season directory.

    :param target_season: Target season directory containing higher-resolution episodes.
    :param original_season: Matching original season directory containing source tracks.
    :param errors: Shared error list receiving episode processing failures.
    :return: None.
    """

    for target_mkv in iter_mkv_files(target_season):  # Process target MKV files in deterministic order.
        try:  # Isolate filename resolution and episode processing failures.
            original_mkv = resolve_original_mkv(original_season, target_mkv)  # Resolve the matching original episode path.

            if original_mkv is None:  # Handle missing original episode files.
                errors.append(  # Add a detailed missing-file report.
                    f"Missing matching original file:\n"  # Describe the matching failure.
                    f"Target  : {target_mkv}\n"  # Include the target episode path.
                    f"Expected: {original_season / target_mkv.name}"  # Include the expected original path.
                )

                continue  # Continue with the next target episode.

            process_episode(target_mkv, original_mkv)  # Mux the resolved episode pair.
        except Exception as exception:  # Aggregate one episode failure without stopping the batch.
            errors.append(f"{target_mkv}\n{type(exception).__name__}: {exception}")  # Store the episode path and exception details.



def print_processing_errors(errors: list[str]) -> None:
    """
    Print aggregated season and episode processing errors.

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
    Process every configured season and episode pair.

    :return: None.
    """

    if not ORIGINAL_ROOT.exists():  # Validate the configured original media root.
        raise FileNotFoundError(f"Original root does not exist: {ORIGINAL_ROOT}")  # Stop before processing an unavailable source root.

    if not TARGET_ROOT.exists():  # Validate the configured target media root.
        raise FileNotFoundError(f"Target root does not exist: {TARGET_ROOT}")  # Stop before processing an unavailable target root.

    original_seasons = build_original_season_map()  # Build the original season lookup by season number.

    if not original_seasons:  # Require at least one recognized original season directory.
        raise RuntimeError(f"No original season folders found in: {ORIGINAL_ROOT}")  # Stop when source season matching cannot operate.

    errors: list[str] = []  # Initialize aggregated batch processing errors.

    for target_season in sorted(TARGET_ROOT.iterdir(), key=lambda entry: entry.name.casefold()):  # Inspect target root entries in deterministic order.
        if not target_season.is_dir():  # Ignore files and other non-directory entries.
            continue  # Continue with the next target root entry.

        key = season_key(target_season)  # Extract the target season number.

        if key is None:  # Handle directories without recognizable season numbers.
            print(f"\nSkipping folder without season number: {target_season}")  # Report the skipped target directory.

            continue  # Continue with the next target season directory.

        original_season = original_seasons.get(key)  # Resolve the matching original season directory.

        if original_season is None:  # Handle target seasons without a source counterpart.
            errors.append(f"No matching original season for: {target_season}")  # Add a season-level matching error.

            continue  # Continue with the next target season directory.

        process_target_season(target_season, original_season, errors)  # Process every eligible episode in the matched season.

    if errors:  # Report all collected failures after processing every season.
        print_processing_errors(errors)  # Print the aggregated error summary.
    else:  # Handle complete batch success.
        print("\nFinished successfully.")  # Report successful completion.


if __name__ == "__main__":  # Execute the program only when invoked as a script.
    main()  # Start the configured audio track muxing workflow.
