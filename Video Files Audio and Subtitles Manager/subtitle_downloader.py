"""
Subtitle downloading through subliminal.
"""

from pathlib import Path  # Represent video and subtitle paths.
from command_runner import CommandRunner  # Execute subliminal.
from config import AppConfig  # Read downloader settings.
from console import BackgroundColors, STYLE_RESET, log_debug, log_warning  # Report downloader results.
from models import ExternalSubtitle  # Compare subtitle inventory records.
from subtitle_inventory import SubtitleInventory  # Refresh subtitle inventory.


class SubtitleDownloader:
    """
    Owns subtitle downloads through the existing subliminal workflow.
    """

    def __init__(self, config: AppConfig, runner: CommandRunner, inventory: SubtitleInventory) -> None:
        """
        Initializes subtitle downloading.

        :param config: Application configuration.
        :param runner: External command runner.
        :param inventory: Subtitle inventory service.
        :return: None.
        """

        self.config = config  # Store application configuration.
        self.runner = runner  # Store command runner.
        self.inventory = inventory  # Store subtitle inventory service.

    def download_language(self, video_path: Path, language_name: str) -> list[Path]:
        """
        Downloads one missing subtitle language for one video.

        :param video_path: Video path.
        :param language_name: Canonical language name.
        :return: Newly available subtitle paths.
        """

        subliminal_cmd = self.runner.find_executable("subliminal")  # Locate subliminal executable.
        if subliminal_cmd is None:  # Verify subliminal is available.
            log_warning("subliminal executable not found; subtitle download skipped.")  # Report missing downloader.
            return []  # Return no downloads.

        before_paths = {subtitle.path for subtitle in self.inventory.discover_external_subtitles(video_path)}  # Snapshot current associated subtitles.
        downloaded_paths: list[Path] = []  # Store downloaded subtitle paths.

        for variant in self.config.subtitle_download_languages.get(language_name, ()):  # Iterate language variants.
            command = [subliminal_cmd, "download", "-l", variant, "-m", "50", str(video_path)]  # Build subliminal command.
            result = self.runner.run(command)  # Run subtitle download.
            after_subtitles = self.inventory.discover_external_subtitles(video_path)  # Refresh associated subtitles.
            matching_paths = self.get_new_matching_paths(after_subtitles, before_paths, language_name)  # Detect matching new files.
            if matching_paths:  # Verify matching subtitles were downloaded.
                downloaded_paths.extend(matching_paths)  # Add downloaded paths.
                print(f"{BackgroundColors.GREEN}Downloaded {BackgroundColors.CYAN}{language_name}{BackgroundColors.GREEN} subtitles for {BackgroundColors.CYAN}{video_path.name}{STYLE_RESET}")  # Report download success.
                break  # Stop variants after success.
            if result.returncode != 0:  # Verify command failed.
                log_debug(f"subliminal failed for {variant}: {result.stderr.strip()}", self.config.verbose)  # Report variant failure when verbose.

        if not downloaded_paths:  # Verify no download succeeded.
            log_warning(f"No {language_name} subtitles found for {video_path.name}.")  # Report missing subtitles.

        return downloaded_paths  # Return downloaded paths.

    def get_new_matching_paths(self, subtitles: list[ExternalSubtitle], before_paths: set[Path], language_name: str) -> list[Path]:
        """
        Selects newly created subtitle paths for the requested language.

        :param subtitles: Current external subtitle inventory.
        :param before_paths: Subtitle paths present before download.
        :param language_name: Requested canonical language name.
        :return: Newly created matching subtitle paths.
        """

        return [subtitle.path for subtitle in subtitles if subtitle.path not in before_paths and subtitle.normalized_language == language_name]  # Return matching new paths.
