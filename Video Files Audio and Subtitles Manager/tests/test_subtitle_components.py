import tempfile  # Create isolated filesystem fixtures.
import unittest  # Run focused component tests.
from pathlib import Path  # Build fixture paths.
from unittest.mock import Mock  # Mock external boundaries.
from command_runner import CommandRunner  # Use command boundary type.
from config import AppConfig  # Build application configuration.
from language_identifier import LanguageIdentifier  # Build language identifier.
from models import CommandResult, ExternalSubtitle, TrackInfo  # Build production models.
from subtitle_downloader import SubtitleDownloader  # Test downloader behavior.
from subtitle_extractor import SubtitleExtractor  # Test extractor failure behavior.
from subtitle_inventory import SubtitleInventory  # Build inventory dependency.
from subtitle_synchronizer import SubtitleSynchronizer  # Test synchronization behavior.
from subtitle_translator import SubtitleTranslator  # Test translation failure behavior.


class SubtitleDownloaderTests(unittest.TestCase):  # Group downloader tests.
    def test_download_failure_is_safe(self) -> None:
        config = AppConfig()  # Build default configuration.
        runner = Mock(spec=CommandRunner)  # Mock command runner boundary.
        inventory = Mock(spec=SubtitleInventory)  # Mock inventory dependency.
        runner.find_executable.return_value = "subliminal"  # Provide downloader executable.
        runner.run.return_value = CommandResult(1, "", "failed")  # Simulate failed download.
        inventory.discover_external_subtitles.return_value = []  # Simulate no subtitles created.
        downloader = SubtitleDownloader(config, runner, inventory)  # Build downloader.
        downloaded_paths = downloader.download_language(Path("Movie.mkv"), "Brazilian Portuguese")  # Attempt download.
        self.assertEqual(downloaded_paths, [])  # Verify failed download returns no files.

    def test_no_duplicate_download_when_ptbr_exists(self) -> None:
        config = AppConfig()  # Build default configuration.
        identifier = LanguageIdentifier(config)  # Build language identifier.
        inventory = SubtitleInventory(config, identifier)  # Build inventory.
        existing = [ExternalSubtitle(Path("Movie.pt-BR.srt"), "Brazilian Portuguese", "Movie.pt-BR.srt", "srt")]  # Build existing PT-BR subtitle.
        self.assertTrue(inventory.subtitle_language_exists("Brazilian Portuguese", [], existing))  # Verify existing PT-BR prevents downloader need.


class SubtitleSynchronizerTests(unittest.TestCase):  # Group synchronizer tests.
    def test_synchronization_failure_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:  # Create temporary fixture directory.
            config = AppConfig(input_directory=Path(temp_dir))  # Build fixture configuration.
            runner = Mock(spec=CommandRunner)  # Mock command runner boundary.
            runner.find_executable.return_value = "ffsubsync"  # Provide synchronizer executable.
            runner.run.return_value = CommandResult(1, "", "failed")  # Simulate synchronization failure.
            video_path = Path(temp_dir) / "Movie.mkv"  # Build fake video path.
            srt_path = Path(temp_dir) / "Movie.en.srt"  # Build fake subtitle path.
            srt_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello.\n", encoding="utf-8")  # Create source subtitle.
            synchronizer = SubtitleSynchronizer(config, runner)  # Build synchronizer.
            result = synchronizer.synchronize(video_path, srt_path)  # Attempt synchronization.
        self.assertFalse(result)  # Verify failed synchronization returns false.


class SubtitleExtractorTests(unittest.TestCase):  # Group extractor tests.
    def test_extraction_failure_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:  # Create temporary fixture directory.
            config = AppConfig(input_directory=Path(temp_dir))  # Build fixture configuration.
            runner = Mock(spec=CommandRunner)  # Mock command runner boundary.
            runner.run.return_value = CommandResult(1, "", "failed")  # Simulate ffmpeg failure.
            extractor = SubtitleExtractor(config, runner)  # Build extractor.
            track = TrackInfo(index=3, track_type="subtitle", track_position=0, normalized_language="English", codec="subrip")  # Build embedded English track.
            result = extractor.extract_to_srt(Path(temp_dir) / "Movie.mkv", track, Path(temp_dir) / "Movie.eng.extracted.srt")  # Attempt extraction.
        self.assertIsNone(result)  # Verify failed extraction returns None.


class SubtitleTranslatorTests(unittest.TestCase):  # Group translator tests.
    def test_deepl_failure_keeps_original_block(self) -> None:
        config = AppConfig()  # Build default configuration.
        translator = SubtitleTranslator(config)  # Build translator.
        translator.translators["acct"] = Mock()  # Inject mocked DeepL client.
        translator.translators["acct"].get_usage.return_value.character.valid = False  # Simulate unknown quota.
        translator.translators["acct"].translate_text.side_effect = RuntimeError("boom")  # Simulate DeepL translation failure.
        result = translator.translate_text_block("Hello", [("acct", "key")], 0)  # Translate text block.
        self.assertEqual(result[0], ["Hello"])  # Verify failed block returns original text.


if __name__ == "__main__":  # Detect direct test execution.
    unittest.main()  # Run tests.
