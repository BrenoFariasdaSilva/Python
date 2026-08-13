"""
External subtitle discovery and subtitle availability queries.
"""

from pathlib import Path  # Represent subtitle paths.
from config import AppConfig  # Read subtitle settings.
from language_identifier import LanguageIdentifier  # Detect subtitle languages.
from models import ExternalSubtitle, TrackInfo  # Return subtitle inventory models.
from srt_tools import read_text_file_lines  # Read SRT files for content detection.


class SubtitleInventory:
    """
    Owns external subtitle discovery and subtitle availability decisions.
    """

    def __init__(self, config: AppConfig, language_identifier: LanguageIdentifier) -> None:
        """
        Initializes subtitle inventory.

        :param config: Application configuration.
        :param language_identifier: Language identifier.
        :return: None.
        """

        self.config = config  # Store application configuration.
        self.language_identifier = language_identifier  # Store language identifier.

    def discover_external_subtitles(self, video_path: Path) -> list[ExternalSubtitle]:
        """
        Discovers external subtitle files associated with a video.

        :param video_path: Video path.
        :return: External subtitle inventory.
        """

        external_subtitles: list[ExternalSubtitle] = []  # Store external subtitle records.
        video_stem_normalized = self.language_identifier.normalize_text(video_path.stem)  # Normalize video stem for matching.

        for candidate in sorted(video_path.parent.iterdir()):  # Iterate sibling files.
            if not candidate.is_file():  # Verify candidate is a file.
                continue  # Skip non-files.
            if candidate.suffix.lower() not in self.config.subtitle_extensions:  # Verify subtitle extension.
                continue  # Skip non-subtitle file.
            if not self.language_identifier.normalize_text(candidate.stem).startswith(video_stem_normalized):  # Verify subtitle belongs to video.
                continue  # Skip unrelated subtitle file.
            filename_language = self.language_identifier.match_from_values([candidate.stem, candidate.name])  # Detect language from filename.
            content_language = None  # Initialize content-detected language.
            if candidate.suffix.lower() == ".srt" and filename_language is None:  # Verify content fallback is useful.
                content_language = self.language_identifier.detect_subtitle_content_language(read_text_file_lines(candidate))  # Detect language from SRT content.
            external_subtitles.append(ExternalSubtitle(path=candidate, normalized_language=filename_language or content_language, title=candidate.name, codec=candidate.suffix.lower().lstrip(".")))  # Add subtitle record.

        return external_subtitles  # Return external subtitle inventory.

    def subtitle_language_exists(self, language_name: str, subtitle_tracks: list[TrackInfo], external_subtitles: list[ExternalSubtitle]) -> bool:
        """
        Determines whether a subtitle language exists internally or externally.

        :param language_name: Canonical language name.
        :param subtitle_tracks: Embedded subtitle inventory.
        :param external_subtitles: External subtitle inventory.
        :return: True when language is available.
        """

        embedded_exists = any(track.normalized_language == language_name for track in subtitle_tracks)  # Determine embedded availability.
        external_exists = any(subtitle.normalized_language == language_name for subtitle in external_subtitles)  # Determine external availability.
        return embedded_exists or external_exists  # Return combined availability.

    def get_external_srt_for_language(self, language_name: str, external_subtitles: list[ExternalSubtitle]) -> Path | None:
        """
        Finds an external SRT for a language.

        :param language_name: Canonical language name.
        :param external_subtitles: External subtitle inventory.
        :return: Matching SRT path or None.
        """

        for subtitle in external_subtitles:  # Iterate external subtitles.
            if subtitle.normalized_language == language_name and subtitle.path.suffix.lower() == ".srt":  # Verify language and SRT extension.
                return subtitle.path  # Return matching SRT path.
        return None  # Return no matching SRT.

    def find_embedded_subtitle_for_language(self, language_name: str, subtitle_tracks: list[TrackInfo]) -> TrackInfo | None:
        """
        Finds an embedded subtitle track for a language.

        :param language_name: Canonical language name.
        :param subtitle_tracks: Embedded subtitle inventory.
        :return: Matching subtitle track or None.
        """

        for track in subtitle_tracks:  # Iterate embedded subtitle tracks.
            if track.normalized_language == language_name:  # Verify language match.
                return track  # Return matching track.
        return None  # Return no matching embedded subtitle.
