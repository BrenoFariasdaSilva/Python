"""
Video discovery.
"""

import os  # Walk filesystem trees.
from pathlib import Path  # Traverse filesystem paths.
from config import AppConfig  # Read discovery settings.
from language_identifier import LanguageIdentifier  # Reuse path normalization.


class MediaDiscovery:
    """
    Finds supported video files under the input directory.
    """

    def __init__(self, config: AppConfig, language_identifier: LanguageIdentifier) -> None:
        """
        Initializes media discovery.

        :param config: Application configuration.
        :param language_identifier: Language identifier for normalized path matching.
        :return: None.
        """

        self.config = config  # Store application configuration.
        self.language_identifier = language_identifier  # Store language identifier.

    def should_ignore_directory(self, dirpath: str) -> bool:
        """
        Determines whether a directory should be ignored.

        :param dirpath: Directory path.
        :return: True when directory should be ignored.
        """

        normalized_dirpath = self.language_identifier.normalize_text(dirpath)  # Normalize directory path.
        return any(self.language_identifier.normalize_text(ignore_dir) in normalized_dirpath for ignore_dir in self.config.ignore_dirs)  # Return ignored directory decision.

    def should_ignore_file(self, filename: str) -> bool:
        """
        Determines whether a file should be ignored.

        :param filename: File name.
        :return: True when file should be ignored.
        """

        normalized_filename = self.language_identifier.normalize_text(filename)  # Normalize file name.
        return any(self.language_identifier.normalize_text(pattern) in normalized_filename for pattern in self.config.ignore_file_patterns)  # Return ignored file decision.

    def find_videos(self) -> list[Path]:
        """
        Recursively finds supported video files.

        :return: Sorted video paths.
        """

        videos: list[Path] = []  # Store discovered videos.
        for root_text, dirnames, filenames in os.walk(self.config.input_directory):  # Walk input tree.
            root = Path(root_text)  # Convert root to Path.
            dirnames[:] = sorted(directory for directory in dirnames if not self.should_ignore_directory(str(root / directory)))  # Prune ignored directories.
            for filename in sorted(filenames):  # Iterate sorted filenames.
                if self.should_ignore_file(filename):  # Verify file should be skipped.
                    continue  # Skip ignored file.
                file_path = root / filename  # Build full file path.
                if file_path.suffix.lower() in self.config.video_extensions:  # Verify supported video extension.
                    videos.append(file_path)  # Add video file.
        return sorted(videos)  # Return sorted video list.
