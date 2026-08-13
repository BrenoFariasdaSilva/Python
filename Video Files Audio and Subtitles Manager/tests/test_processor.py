import tempfile  # Create isolated filesystem fixtures.
import unittest  # Run orchestration tests.
from pathlib import Path  # Build fixture paths.
from unittest.mock import Mock  # Mock component boundaries.
from command_runner import CommandRunner  # Build command runner dependency.
from config import AppConfig  # Build application configuration.
from models import ExternalSubtitle, TrackInfo  # Build production models.
from processor import VideoProcessor  # Test orchestration behavior.


class ProcessorTests(unittest.TestCase):  # Group processor orchestration tests.
    def test_missing_ptbr_external_english_is_preferred_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:  # Create temporary fixture directory.
            config = AppConfig(input_directory=Path(temp_dir))  # Build fixture configuration.
            processor = VideoProcessor(config, CommandRunner())  # Build processor.
            video_path = Path(temp_dir) / "Movie.mkv"  # Build fake video path.
            english_path = Path(temp_dir) / "Movie.en.srt"  # Build English subtitle path.
            external_subtitles = [ExternalSubtitle(english_path, "English", english_path.name, "srt")]  # Build external English inventory.
            processor.translator.translate_english_srt_to_ptbr = Mock(return_value=True)  # Mock DeepL boundary.
            processor.ensure_ptbr_translation_fallback(video_path, [], external_subtitles)  # Run translation fallback.
        processor.translator.translate_english_srt_to_ptbr.assert_called_once()  # Verify translation was called once.
        self.assertEqual(processor.translator.translate_english_srt_to_ptbr.call_args.args[0], english_path)  # Verify external English source was used.

    def test_missing_ptbr_embedded_english_is_extracted_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:  # Create temporary fixture directory.
            config = AppConfig(input_directory=Path(temp_dir))  # Build fixture configuration.
            processor = VideoProcessor(config, CommandRunner())  # Build processor.
            video_path = Path(temp_dir) / "Movie.mkv"  # Build fake video path.
            extracted_path = Path(temp_dir) / "Movie.eng.extracted.srt"  # Build extracted subtitle path.
            subtitle_tracks = [TrackInfo(index=3, track_type="subtitle", track_position=0, normalized_language="English", codec="subrip")]  # Build embedded English inventory.
            processor.extractor.extract_to_srt = Mock(return_value=extracted_path)  # Mock extraction boundary.
            processor.translator.translate_english_srt_to_ptbr = Mock(return_value=True)  # Mock DeepL boundary.
            processor.ensure_ptbr_translation_fallback(video_path, subtitle_tracks, [])  # Run translation fallback.
        processor.extractor.extract_to_srt.assert_called_once()  # Verify embedded English extraction was attempted.
        processor.translator.translate_english_srt_to_ptbr.assert_called_once()  # Verify translation was attempted.
        self.assertEqual(processor.translator.translate_english_srt_to_ptbr.call_args.args[0], extracted_path)  # Verify extracted SRT was used.

    def test_missing_ptbr_and_no_english_skips_translation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:  # Create temporary fixture directory.
            config = AppConfig(input_directory=Path(temp_dir))  # Build fixture configuration.
            processor = VideoProcessor(config, CommandRunner())  # Build processor.
            video_path = Path(temp_dir) / "Movie.mkv"  # Build fake video path.
            processor.translator.translate_english_srt_to_ptbr = Mock(return_value=True)  # Mock DeepL boundary.
            processor.ensure_ptbr_translation_fallback(video_path, [], [])  # Run fallback with no English.
        processor.translator.translate_english_srt_to_ptbr.assert_not_called()  # Verify translation was skipped.

    def test_ptbr_present_skips_translation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:  # Create temporary fixture directory.
            config = AppConfig(input_directory=Path(temp_dir))  # Build fixture configuration.
            processor = VideoProcessor(config, CommandRunner())  # Build processor.
            video_path = Path(temp_dir) / "Movie.mkv"  # Build fake video path.
            ptbr_path = Path(temp_dir) / "Movie.pt-BR.srt"  # Build PT-BR subtitle path.
            external_subtitles = [ExternalSubtitle(ptbr_path, "Brazilian Portuguese", ptbr_path.name, "srt")]  # Build PT-BR inventory.
            processor.translator.translate_english_srt_to_ptbr = Mock(return_value=True)  # Mock DeepL boundary.
            processor.ensure_ptbr_translation_fallback(video_path, [], external_subtitles)  # Run fallback workflow.
        processor.translator.translate_english_srt_to_ptbr.assert_not_called()  # Verify existing PT-BR prevents duplicate translation.

    def test_orchestration_order_between_components(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:  # Create temporary fixture directory.
            config = AppConfig(input_directory=Path(temp_dir), enable_deepl_translation=False)  # Build fixture configuration.
            processor = VideoProcessor(config, CommandRunner())  # Build processor.
            video_path = Path(temp_dir) / "Movie.mkv"  # Build fake video path.
            calls: list[str] = []  # Store observed call order.
            processor.inspector.inspect = Mock(side_effect=lambda path: calls.append("inspect") or ([TrackInfo(index=1, track_type="audio", track_position=0, normalized_language="English", default=True)], []))  # Mock inspection boundary.
            processor.inventory.discover_external_subtitles = Mock(side_effect=lambda path: calls.append("external") or [])  # Mock external inventory boundary.
            processor.audio_manager.set_preferred_default_audio = Mock(side_effect=lambda path, tracks: calls.append("audio") or False)  # Mock audio manager boundary.
            processor.ensure_required_subtitles = Mock(side_effect=lambda path, tracks, external: calls.append("required") or (tracks, external))  # Mock required subtitle step.
            processor.ensure_ptbr_translation_fallback = Mock(side_effect=lambda path, tracks, external: calls.append("translate") or external)  # Mock translation fallback step.
            processor.process_video(video_path)  # Process fake video.
        self.assertEqual(calls, ["inspect", "external", "audio", "required", "translate"])  # Verify deterministic orchestration order.


if __name__ == "__main__":  # Detect direct test execution.
    unittest.main()  # Run tests.
