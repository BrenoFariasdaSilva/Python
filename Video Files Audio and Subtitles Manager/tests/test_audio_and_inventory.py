import tempfile  # Create isolated filesystem fixtures.
import unittest  # Run focused component tests.
from pathlib import Path  # Build fixture paths.
from config import AppConfig  # Build application configuration.
from command_runner import CommandRunner  # Create command runner dependency.
from audio_track_manager import AudioTrackManager  # Test audio selection logic.
from language_identifier import LanguageIdentifier  # Test language matching and content fallback path.
from models import ExternalSubtitle, TrackInfo  # Build production data models.
from subtitle_inventory import SubtitleInventory  # Test subtitle availability and discovery.


class AudioTrackManagerTests(unittest.TestCase):  # Group audio manager tests.
    def test_preferred_audio_already_default(self) -> None:
        config = AppConfig()  # Build default configuration.
        manager = AudioTrackManager(config, CommandRunner())  # Build audio manager.
        audio_tracks = [TrackInfo(index=1, track_type="audio", track_position=0, normalized_language="English", default=True), TrackInfo(index=2, track_type="audio", track_position=1, normalized_language=None, default=False)]  # Build audio inventory with English default.
        selected_track = manager.select_preferred_audio_track(audio_tracks)  # Select preferred audio track.
        self.assertIs(selected_track, audio_tracks[0])  # Verify English track wins and unknown track stays untouched.

    def test_preferred_audio_exists_but_not_default(self) -> None:
        config = AppConfig()  # Build default configuration.
        manager = AudioTrackManager(config, CommandRunner())  # Build audio manager.
        audio_tracks = [TrackInfo(index=1, track_type="audio", track_position=0, normalized_language=None, default=True), TrackInfo(index=2, track_type="audio", track_position=1, normalized_language="English", default=False)]  # Build preferred audio not default.
        selected_track = manager.select_preferred_audio_track(audio_tracks)  # Select preferred audio track.
        self.assertIs(selected_track, audio_tracks[1])  # Verify preferred non-default track is selected.

    def test_unknown_audio_language_returns_no_selection(self) -> None:
        config = AppConfig()  # Build default configuration.
        manager = AudioTrackManager(config, CommandRunner())  # Build audio manager.
        audio_tracks = [TrackInfo(index=1, track_type="audio", track_position=0, normalized_language=None, default=True)]  # Build unknown-only audio inventory.
        selected_track = manager.select_preferred_audio_track(audio_tracks)  # Select preferred audio track.
        self.assertIsNone(selected_track)  # Verify unknown audio is not treated as desired.


class SubtitleInventoryTests(unittest.TestCase):  # Group subtitle inventory tests.
    def test_ptbr_already_embedded(self) -> None:
        config = AppConfig()  # Build default configuration.
        inventory = SubtitleInventory(config, LanguageIdentifier(config))  # Build subtitle inventory.
        subtitle_tracks = [TrackInfo(index=3, track_type="subtitle", track_position=0, normalized_language="Brazilian Portuguese")]  # Build embedded PT-BR inventory.
        self.assertTrue(inventory.subtitle_language_exists("Brazilian Portuguese", subtitle_tracks, []))  # Verify embedded PT-BR availability.

    def test_ptbr_already_external(self) -> None:
        config = AppConfig()  # Build default configuration.
        inventory = SubtitleInventory(config, LanguageIdentifier(config))  # Build subtitle inventory.
        external_subtitles = [ExternalSubtitle(Path("Movie.pt-BR.srt"), "Brazilian Portuguese", "Movie.pt-BR.srt", "srt")]  # Build external PT-BR inventory.
        self.assertTrue(inventory.subtitle_language_exists("Brazilian Portuguese", [], external_subtitles))  # Verify external PT-BR availability.

    def test_external_english_and_ptbr_already_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:  # Create temporary fixture directory.
            config = AppConfig(input_directory=Path(temp_dir))  # Build fixture configuration.
            inventory = SubtitleInventory(config, LanguageIdentifier(config))  # Build subtitle inventory.
            video_path = Path(temp_dir) / "Movie.mkv"  # Build fake video path.
            video_path.write_text("", encoding="utf-8")  # Create fake video file.
            (Path(temp_dir) / "Movie.en.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nHello there.\n", encoding="utf-8")  # Create English subtitle file.
            (Path(temp_dir) / "Movie.pt-BR.srt").write_text("1\n00:00:01,000 --> 00:00:02,000\nOla.\n", encoding="utf-8")  # Create PT-BR subtitle file.
            external_subtitles = inventory.discover_external_subtitles(video_path)  # Discover associated subtitles.
        self.assertTrue(any(item.normalized_language == "English" for item in external_subtitles))  # Verify English filename detection.
        self.assertTrue(any(item.normalized_language == "Brazilian Portuguese" for item in external_subtitles))  # Verify PT-BR filename detection.

    def test_subtitle_metadata_without_language_uses_content_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:  # Create temporary fixture directory.
            config = AppConfig(input_directory=Path(temp_dir))  # Build fixture configuration.
            identifier = LanguageIdentifier(config)  # Build language identifier.
            inventory = SubtitleInventory(config, identifier)  # Build subtitle inventory.
            video_path = Path(temp_dir) / "Movie.mkv"  # Build fake video path.
            video_path.write_text("", encoding="utf-8")  # Create fake video file.
            subtitle_path = Path(temp_dir) / "Movie.subtitle.srt"  # Build subtitle path without language marker.
            subtitle_path.write_text("1\n00:00:01,000 --> 00:00:02,000\nHello there.\n", encoding="utf-8")  # Create subtitle content.
            identifier.detect_subtitle_content_language = lambda lines: "English"  # Replace content detector boundary.
            external_subtitles = inventory.discover_external_subtitles(video_path)  # Discover associated subtitles.
        self.assertEqual(external_subtitles[0].normalized_language, "English")  # Verify content language is recorded.

    def test_unknown_subtitle_language_stays_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:  # Create temporary fixture directory.
            config = AppConfig(input_directory=Path(temp_dir))  # Build fixture configuration.
            identifier = LanguageIdentifier(config)  # Build language identifier.
            inventory = SubtitleInventory(config, identifier)  # Build subtitle inventory.
            video_path = Path(temp_dir) / "Movie.mkv"  # Build fake video path.
            video_path.write_text("", encoding="utf-8")  # Create fake video file.
            subtitle_path = Path(temp_dir) / "Movie.zzz.srt"  # Build unknown subtitle path.
            subtitle_path.write_text("1\n00:00:01,000 --> 00:00:02,000\n???\n", encoding="utf-8")  # Create unknown content.
            identifier.detect_subtitle_content_language = lambda lines: None  # Replace content detector boundary.
            external_subtitles = inventory.discover_external_subtitles(video_path)  # Discover associated subtitles.
        self.assertIsNone(external_subtitles[0].normalized_language)  # Verify unknown language remains unknown.


if __name__ == "__main__":  # Detect direct test execution.
    unittest.main()  # Run tests.
