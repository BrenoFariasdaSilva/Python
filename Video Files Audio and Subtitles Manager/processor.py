"""
Overall video workflow orchestration.
"""

from pathlib import Path  # Represent video paths.
from audio_track_manager import AudioTrackManager  # Manage audio defaults.
from command_runner import CommandRunner  # Share external command runner.
from config import AppConfig  # Read workflow settings.
from console import BackgroundColors, STYLE_RESET, log_warning  # Report processing status.
from language_identifier import LanguageIdentifier  # Detect languages.
from media_discovery import MediaDiscovery  # Discover videos.
from media_inspector import MediaInspector  # Inspect embedded tracks.
from models import ExternalSubtitle, TrackInfo, VideoStatus  # Share workflow models.
from subtitle_downloader import SubtitleDownloader  # Download missing subtitles.
from subtitle_extractor import SubtitleExtractor  # Extract embedded English subtitles.
from subtitle_inventory import SubtitleInventory  # Query subtitle availability.
from subtitle_synchronizer import SubtitleSynchronizer  # Synchronize downloaded SRTs.
from subtitle_translator import SubtitleTranslator  # Translate English SRT to PT-BR.


class VideoProcessor:
    """
    Coordinates per-video audio and subtitle workflow components.
    """

    def __init__(self, config: AppConfig, runner: CommandRunner) -> None:
        """
        Initializes the video processor.

        :param config: Application configuration.
        :param runner: External command runner.
        :return: None.
        """

        self.config = config  # Store application configuration.
        self.runner = runner  # Store shared command runner.
        self.language_identifier = LanguageIdentifier(config)  # Create language identifier.
        self.extractor = SubtitleExtractor(config, runner)  # Create subtitle extractor.
        self.inspector = MediaInspector(config, runner, self.language_identifier, self.extractor)  # Create media inspector.
        self.discovery = MediaDiscovery(config, self.language_identifier)  # Create media discovery.
        self.inventory = SubtitleInventory(config, self.language_identifier)  # Create subtitle inventory service.
        self.audio_manager = AudioTrackManager(config, runner)  # Create audio manager.
        self.downloader = SubtitleDownloader(config, runner, self.inventory)  # Create subtitle downloader.
        self.synchronizer = SubtitleSynchronizer(config, runner)  # Create subtitle synchronizer.
        self.translator = SubtitleTranslator(config)  # Create subtitle translator.

    def process_all(self) -> list[VideoStatus]:
        """
        Processes every discovered video.

        :return: Per-video status list.
        """

        videos = self.discovery.find_videos()  # Discover videos.
        if not videos:  # Verify videos were found.
            return []  # Return empty result.
        statuses: list[VideoStatus] = []  # Store per-video statuses.
        for video_path in videos:  # Iterate discovered videos.
            try:  # Process each video independently.
                statuses.append(self.process_video(video_path))  # Process current video.
            except KeyboardInterrupt:  # Preserve user interruption.
                raise  # Re-raise interruption.
            except Exception as error:  # Handle per-video failure.
                log_warning(f"Failed to process {video_path}: {error}")  # Report failure and continue.
        return statuses  # Return processed statuses.

    def log_inventory(self, video_path: Path, audio_tracks: list[TrackInfo], subtitle_tracks: list[TrackInfo], external_subtitles: list[ExternalSubtitle]) -> None:
        """
        Logs media track inventory.

        :param video_path: Video path.
        :param audio_tracks: Audio track inventory.
        :param subtitle_tracks: Embedded subtitle inventory.
        :param external_subtitles: External subtitle inventory.
        :return: None.
        """

        print(f"{BackgroundColors.GREEN}Inventory:{STYLE_RESET} {BackgroundColors.CYAN}{video_path}{STYLE_RESET}")  # Print inventory header.
        for track in audio_tracks + subtitle_tracks:  # Iterate embedded tracks.
            language = track.normalized_language or "unknown"  # Resolve display language.
            print(f"  {track.track_type} #{track.track_position} stream={track.index} lang={language} declared={track.declared_language or 'und'} default={track.default} title={track.title or ''} codec={track.codec or ''}")  # Print embedded track line.
        for subtitle in external_subtitles:  # Iterate external subtitles.
            language = subtitle.normalized_language or "unknown"  # Resolve display language.
            print(f"  external subtitle lang={language} file={subtitle.path.name}")  # Print external subtitle line.

    def process_video(self, video_path: Path) -> VideoStatus:
        """
        Processes one video through the unified workflow.

        :param video_path: Video path.
        :return: Final status.
        """

        audio_tracks, subtitle_tracks = self.inspector.inspect(video_path)  # Build initial embedded inventory.
        external_subtitles = self.inventory.discover_external_subtitles(video_path)  # Build initial external inventory.
        self.log_inventory(video_path, audio_tracks, subtitle_tracks, external_subtitles)  # Log initial inventory.

        audio_modified = self.audio_manager.set_preferred_default_audio(video_path, audio_tracks)  # Set preferred default audio if needed.
        if audio_modified:  # Verify remux changed embedded metadata.
            audio_tracks, subtitle_tracks = self.inspector.inspect(video_path)  # Refresh embedded inventory after remux.

        subtitle_tracks, external_subtitles = self.ensure_required_subtitles(video_path, subtitle_tracks, external_subtitles)  # Download missing subtitles.
        external_subtitles = self.ensure_ptbr_translation_fallback(video_path, subtitle_tracks, external_subtitles)  # Translate PT-BR fallback when needed.

        ptbr_available = self.inventory.subtitle_language_exists("Brazilian Portuguese", subtitle_tracks, external_subtitles)  # Determine final PT-BR availability.
        english_available = self.inventory.subtitle_language_exists("English", subtitle_tracks, external_subtitles)  # Determine final English availability.
        print(f"{BackgroundColors.GREEN}Final subtitle status for {BackgroundColors.CYAN}{video_path.name}{BackgroundColors.GREEN}: PT-BR={BackgroundColors.CYAN}{ptbr_available}{BackgroundColors.GREEN}, English={BackgroundColors.CYAN}{english_available}{STYLE_RESET}")  # Report final status.
        return VideoStatus(video=video_path, audio_modified=audio_modified, ptbr_available=ptbr_available, english_available=english_available)  # Return final status.

    def ensure_required_subtitles(self, video_path: Path, subtitle_tracks: list[TrackInfo], external_subtitles: list[ExternalSubtitle]) -> tuple[list[TrackInfo], list[ExternalSubtitle]]:
        """
        Ensures required subtitles are available by download when possible.

        :param video_path: Video path.
        :param subtitle_tracks: Embedded subtitle inventory.
        :param external_subtitles: External subtitle inventory.
        :return: Refreshed embedded and external subtitle inventories.
        """

        if not self.config.enable_subtitle_downloads:  # Verify subtitle downloads are enabled.
            return subtitle_tracks, external_subtitles  # Return unchanged inventories.

        needed_languages = list(self.config.required_subtitle_languages)  # Start with obligatory languages.
        if not self.inventory.subtitle_language_exists("Brazilian Portuguese", subtitle_tracks, external_subtitles):  # Verify PT-BR is missing.
            needed_languages.extend(language for language in self.config.translation_source_languages if language not in needed_languages)  # Add English source need.

        for language_name in needed_languages:  # Iterate needed languages.
            if self.inventory.subtitle_language_exists(language_name, subtitle_tracks, external_subtitles):  # Verify language already exists.
                continue  # Avoid duplicate download.
            downloaded_paths = self.downloader.download_language(video_path, language_name)  # Download missing language.
            for downloaded_path in downloaded_paths:  # Iterate downloaded subtitles.
                self.synchronizer.synchronize(video_path, downloaded_path)  # Synchronize downloaded subtitle when possible.
            external_subtitles = self.inventory.discover_external_subtitles(video_path)  # Refresh external subtitle inventory.

        return subtitle_tracks, external_subtitles  # Return refreshed inventories.

    def ensure_ptbr_translation_fallback(self, video_path: Path, subtitle_tracks: list[TrackInfo], external_subtitles: list[ExternalSubtitle]) -> list[ExternalSubtitle]:
        """
        Creates PT-BR subtitle by translating English when PT-BR is still missing.

        :param video_path: Video path.
        :param subtitle_tracks: Embedded subtitle inventory.
        :param external_subtitles: External subtitle inventory.
        :return: Refreshed external subtitle inventory.
        """

        if not self.config.enable_deepl_translation:  # Verify translation is enabled.
            return external_subtitles  # Return unchanged inventory.
        if self.inventory.subtitle_language_exists("Brazilian Portuguese", subtitle_tracks, external_subtitles):  # Verify PT-BR already exists.
            return external_subtitles  # Avoid duplicate translation.

        english_source_srt = self.inventory.get_external_srt_for_language("English", external_subtitles)  # Prefer external English SRT.
        if english_source_srt is None:  # Verify external English source is absent.
            embedded_english = self.inventory.find_embedded_subtitle_for_language("English", subtitle_tracks)  # Find embedded English source.
            if embedded_english is not None:  # Verify embedded English exists.
                extracted_srt = video_path.with_name(f"{video_path.stem}.eng.extracted.srt")  # Build extracted source filename.
                english_source_srt = self.extractor.extract_to_srt(video_path, embedded_english, extracted_srt)  # Extract embedded source.

        if english_source_srt is None:  # Verify no English source exists.
            log_warning(f"PT-BR subtitle missing and no usable English subtitle source exists for {video_path.name}.")  # Report translation skip reason.
            return external_subtitles  # Return unchanged inventory.

        output_srt = video_path.with_name(f"{video_path.stem}.pt-BR.srt")  # Build PT-BR output path.
        self.translator.translate_english_srt_to_ptbr(english_source_srt, output_srt)  # Translate English source to PT-BR.
        return self.inventory.discover_external_subtitles(video_path)  # Return refreshed external inventory.
