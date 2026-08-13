"""
ffprobe media inspection and embedded track inventory.
"""

import json  # Parse ffprobe JSON output.
from pathlib import Path  # Represent video paths.
from command_runner import CommandRunner  # Execute ffprobe.
from config import AppConfig  # Read inspection settings.
from console import log_warning  # Report inspection failures.
from language_identifier import LanguageIdentifier  # Detect stream language.
from models import JsonValue, TrackInfo  # Return typed stream metadata.
from subtitle_extractor import SubtitleExtractor  # Extract subtitle text for content detection.


class MediaInspector:
    """
    Owns ffprobe inspection and embedded track mapping.
    """

    def __init__(self, config: AppConfig, runner: CommandRunner, language_identifier: LanguageIdentifier, extractor: SubtitleExtractor) -> None:
        """
        Initializes media inspection.

        :param config: Application configuration.
        :param runner: External command runner.
        :param language_identifier: Language identifier.
        :param extractor: Subtitle extractor for text fallback detection.
        :return: None.
        """

        self.config = config  # Store application configuration.
        self.runner = runner  # Store command runner.
        self.language_identifier = language_identifier  # Store language identifier.
        self.extractor = extractor  # Store subtitle extractor.

    def probe_media(self, video_path: Path) -> dict[str, JsonValue]:
        """
        Reads ffprobe stream metadata for a video.

        :param video_path: Video path.
        :return: ffprobe JSON data.
        """

        command = ["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(video_path)]  # Build ffprobe command.
        result = self.runner.run(command)  # Run ffprobe.
        if result.returncode != 0:  # Verify ffprobe succeeded.
            log_warning(f"ffprobe failed for {video_path}: {result.stderr.strip()}")  # Report ffprobe failure.
            return {"streams": []}  # Return empty media data.
        try:  # Parse JSON output.
            parsed = json.loads(result.stdout) if result.stdout else {"streams": []}  # Parse ffprobe output.
        except json.JSONDecodeError as error:  # Handle invalid JSON.
            log_warning(f"ffprobe returned invalid JSON for {video_path}: {error}")  # Report parse failure.
            return {"streams": []}  # Return empty media data.
        return parsed if isinstance(parsed, dict) else {"streams": []}  # Return object-shaped media data.

    def detect_stream_language(self, stream: dict[str, JsonValue]) -> str | None:
        """
        Detects desired language from stream metadata.

        :param stream: ffprobe stream data.
        :return: Canonical language name or None.
        """

        tags = self.read_string_tags(stream)  # Resolve string tags.
        values: list[object] = [tags.get("language"), tags.get("LANGUAGE"), tags.get("lang"), tags.get("title"), tags.get("handler_name"), tags.get("track"), tags.get("TRACK")]  # Collect known metadata fields.
        values.extend(tags.values())  # Add every tag value as fallback metadata.
        return self.language_identifier.match_from_values(values)  # Return detected language from metadata.

    def read_string_tags(self, stream: dict[str, JsonValue]) -> dict[str, str]:
        """
        Reads string tags from a stream.

        :param stream: ffprobe stream data.
        :return: String tag mapping.
        """

        raw_tags = stream.get("tags")  # Read raw tags value.
        if not isinstance(raw_tags, dict):  # Verify tags are object-shaped.
            return {}  # Return empty tag mapping.
        return {str(key): str(value) for key, value in raw_tags.items() if value is not None}  # Return stringified tag mapping.

    def read_disposition(self, stream: dict[str, JsonValue]) -> dict[str, int | str | bool | None]:
        """
        Reads disposition values from a stream.

        :param stream: ffprobe stream data.
        :return: Disposition mapping.
        """

        raw_disposition = stream.get("disposition")  # Read raw disposition value.
        if not isinstance(raw_disposition, dict):  # Verify disposition is object-shaped.
            return {}  # Return empty disposition mapping.
        return {str(key): value for key, value in raw_disposition.items() if isinstance(value, (int, str, bool)) or value is None}  # Return supported disposition values.

    def inspect(self, video_path: Path) -> tuple[list[TrackInfo], list[TrackInfo]]:
        """
        Builds audio and embedded subtitle inventories for a video.

        :param video_path: Video path.
        :return: Audio track list and subtitle track list.
        """

        media_data = self.probe_media(video_path)  # Read stream metadata.
        raw_streams = media_data.get("streams", [])  # Read stream list.
        streams = raw_streams if isinstance(raw_streams, list) else []  # Normalize stream list.
        audio_tracks: list[TrackInfo] = []  # Store audio track inventory.
        subtitle_tracks: list[TrackInfo] = []  # Store embedded subtitle inventory.
        audio_position = 0  # Track audio stream position.
        subtitle_position = 0  # Track subtitle stream position.

        for raw_stream in streams:  # Iterate ffprobe streams.
            if not isinstance(raw_stream, dict):  # Verify stream is object-shaped.
                continue  # Skip invalid stream entry.
            stream = raw_stream  # Store typed stream mapping.
            stream_type_value = stream.get("codec_type")  # Read stream type.
            stream_type = str(stream_type_value) if stream_type_value is not None else ""  # Normalize stream type.
            if stream_type not in {"audio", "subtitle"}:  # Verify stream is relevant.
                continue  # Skip unrelated stream.
            tags = self.read_string_tags(stream)  # Resolve stream tags.
            disposition = self.read_disposition(stream)  # Resolve stream disposition.
            normalized_language = self.detect_stream_language(stream)  # Detect desired language from metadata.
            position = audio_position if stream_type == "audio" else subtitle_position  # Resolve type-relative position.
            track = TrackInfo(index=int(stream["index"]) if isinstance(stream.get("index"), int) else None, track_type=stream_type, track_position=position, title=tags.get("title", ""), track_name=tags.get("track") or tags.get("TRACK") or tags.get("handler_name", ""), declared_language=tags.get("language") or tags.get("LANGUAGE") or tags.get("lang") or "", normalized_language=normalized_language, default=str(disposition.get("default", 0)).lower() in {"1", "true", "yes"}, forced=str(disposition.get("forced", 0)).lower() in {"1", "true", "yes"}, codec=str(stream.get("codec_name") or ""), tags=tags, disposition=disposition)  # Build track record.
            if stream_type == "audio":  # Verify audio stream.
                audio_tracks.append(track)  # Add audio track.
                audio_position += 1  # Increment audio position.
            else:  # Handle subtitle stream.
                if track.normalized_language is None:  # Verify metadata language is unknown.
                    extracted_lines = self.extractor.extract_for_detection(video_path, subtitle_position, track.codec)  # Extract text for fallback detection.
                    track.normalized_language = self.language_identifier.detect_subtitle_content_language(extracted_lines) if extracted_lines else None  # Store content-detected language when reliable.
                subtitle_tracks.append(track)  # Add subtitle track.
                subtitle_position += 1  # Increment subtitle position.

        return audio_tracks, subtitle_tracks  # Return inventories.
