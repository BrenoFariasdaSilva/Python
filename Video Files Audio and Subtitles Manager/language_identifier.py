"""
Language normalization and subtitle content identification.
"""

import re  # Normalize text fragments.
import unicodedata  # Remove accent marks.
from config import AppConfig  # Read language aliases and detection limits.
from srt_tools import build_language_detection_sample, count_letters  # Build subtitle content samples.


class LanguageIdentifier:
    """
    Owns desired-language alias and subtitle content identification.
    """

    def __init__(self, config: AppConfig) -> None:
        """
        Initializes language identification.

        :param config: Application configuration.
        :return: None.
        """

        self.config = config  # Store application configuration.
        self.normalized_aliases = self.build_normalized_aliases()  # Precompute normalized aliases.

    def normalize_text(self, value: object) -> str:
        """
        Normalizes metadata text for language matching.

        :param value: Raw metadata value.
        :return: Normalized comparable text.
        """

        text = "" if value is None else str(value)  # Convert missing values to empty text.
        text = text.lower()  # Convert text to lowercase.
        text = unicodedata.normalize("NFKD", text)  # Split accents from base characters.
        text = "".join(character for character in text if not unicodedata.combining(character))  # Remove accent marks.
        text = re.sub(r"\b\d+(\.\d+)?\b", " ", text)  # Remove isolated numeric quality markers.
        text = re.sub(r"[\(\)\[\]\{\}_\-\.]+", " ", text)  # Replace separators with spaces.
        text = re.sub(r"\s+", " ", text).strip()  # Collapse whitespace.
        return text  # Return normalized text.

    def build_normalized_aliases(self) -> dict[str, list[str]]:
        """
        Builds normalized aliases for every desired language.

        :return: Mapping from canonical language to normalized aliases.
        """

        normalized_aliases: dict[str, list[str]] = {}  # Initialize normalized alias mapping.
        for language_name, aliases in self.config.desired_languages.items():  # Iterate configured languages.
            ordered_aliases: list[str] = []  # Store ordered aliases for current language.
            seen_aliases: set[str] = set()  # Store aliases already added.
            for alias in [language_name, *aliases]:  # Iterate canonical name and aliases.
                normalized_alias = self.normalize_text(alias)  # Normalize current alias.
                if normalized_alias and normalized_alias not in seen_aliases:  # Verify alias is useful and unique.
                    ordered_aliases.append(normalized_alias)  # Add normalized alias.
                    seen_aliases.add(normalized_alias)  # Record normalized alias.
            normalized_aliases[language_name] = ordered_aliases  # Store aliases for current language.
        return normalized_aliases  # Return alias mapping.

    def match_from_values(self, values: list[object]) -> str | None:
        """
        Matches a canonical desired language from metadata values.

        :param values: Metadata values to match.
        :return: Canonical language name or None.
        """

        normalized_values = [normalized for value in values if (normalized := self.normalize_text(value))]  # Normalize non-empty metadata values.
        for language_name, aliases in self.normalized_aliases.items():  # Prefer exact alias matches.
            for alias in aliases:  # Iterate language aliases.
                if alias in normalized_values:  # Verify exact metadata match.
                    return language_name  # Return canonical language.
        priority_order = list(self.config.audio_priority_order) + [language for language in self.config.desired_languages if language not in self.config.audio_priority_order]  # Build deterministic scan order.
        for language_name in priority_order:  # Iterate configured language order.
            for alias in self.normalized_aliases.get(language_name, []):  # Iterate aliases.
                for value in normalized_values:  # Iterate metadata values.
                    if alias in value.split():  # Verify alias appears as a full token.
                        return language_name  # Return canonical language.
        for language_name in priority_order:  # Iterate configured language order for fuzzy matches.
            for alias in self.normalized_aliases.get(language_name, []):  # Iterate aliases.
                if len(alias) < 3:  # Avoid unsafe fuzzy matches for tiny aliases.
                    continue  # Skip tiny alias.
                for value in normalized_values:  # Iterate metadata values.
                    if alias in value:  # Verify alias appears in metadata.
                        return language_name  # Return canonical language.
        return None  # Return unknown when no reliable match exists.

    def detect_subtitle_content_language(self, lines: list[str]) -> str | None:
        """
        Detects English or Brazilian Portuguese from subtitle content.

        :param lines: Subtitle lines.
        :return: Canonical language name or None.
        """

        sample = build_language_detection_sample(lines, self.config.language_detection_max_sample_chars)  # Build dialogue sample.
        if count_letters(sample) < self.config.language_detection_min_letters:  # Verify sample is large enough.
            return None  # Return unknown for small samples.

        try:  # Import optional detector lazily.
            from lingua import LanguageDetectorBuilder  # Import lingua detector builder.
        except ImportError:  # Handle missing detector dependency.
            return None  # Return unknown when package is unavailable.

        detector = LanguageDetectorBuilder.from_all_languages().build()  # Build offline detector.
        confidence_values = detector.compute_language_confidence_values(sample)  # Compute language scores.
        if not confidence_values:  # Verify scores exist.
            return None  # Return unknown when detector cannot classify.
        top_confidence = confidence_values[0]  # Store strongest language score.
        second_confidence = confidence_values[1].value if len(confidence_values) > 1 else 0.0  # Store second score.
        detected_code = top_confidence.language.iso_code_639_1.name  # Store ISO language code.
        if top_confidence.value < 0.55 or top_confidence.value - second_confidence < 0.15:  # Require a reliable winner.
            return None  # Return unknown when confidence is weak.
        if detected_code == "EN":  # Verify English content.
            return "English"  # Return English canonical language.
        if detected_code == "PT":  # Verify Portuguese content.
            return "Brazilian Portuguese"  # Return Portuguese canonical language.
        return None  # Return unknown for unneeded languages.
