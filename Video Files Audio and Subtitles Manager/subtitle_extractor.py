"""
Embedded subtitle extraction.
"""

from pathlib import Path  # Build subtitle output paths.
from command_runner import CommandRunner  # Execute ffmpeg.
from config import AppConfig  # Read subtitle codec settings.
from console import log_debug, log_warning  # Report extraction status.
from models import TrackInfo  # Consume subtitle track metadata.
from srt_tools import read_text_file_lines  # Read extracted subtitle text.


class SubtitleExtractor:
    """
    Owns embedded subtitle extraction through ffmpeg.
    """

    def __init__(self, config: AppConfig, runner: CommandRunner) -> None:
        """
        Initializes subtitle extraction.

        :param config: Application configuration.
        :param runner: External command runner.
        :return: None.
        """

        self.config = config  # Store application configuration.
        self.runner = runner  # Store command runner.

    def can_extract_text(self, codec: str) -> bool:
        """
        Determines whether a subtitle codec can be extracted as text.

        :param codec: Subtitle codec name.
        :return: True when codec can be converted to SRT.
        """

        return codec in self.config.text_subtitle_codecs and codec not in self.config.bitmap_subtitle_codecs  # Return text extraction capability.

    def extract_for_detection(self, video_path: Path, track_position: int, codec: str) -> list[str]:
        """
        Extracts a text subtitle stream to temporary SRT lines for detection.

        :param video_path: Video path.
        :param track_position: Subtitle position among subtitle streams.
        :param codec: Subtitle codec name.
        :return: Extracted subtitle lines or an empty list.
        """

        if not self.can_extract_text(codec):  # Verify stream can be converted without OCR.
            return []  # Return no text for unsupported codecs.
        temp_file = video_path.with_name(f"{video_path.stem}.subtitle-detect-{track_position}.tmp.srt")  # Build temporary extraction path.
        command = ["ffmpeg", "-y", "-i", str(video_path), "-map", f"0:s:{track_position}", str(temp_file)]  # Build extraction command.
        result = self.runner.run(command)  # Run ffmpeg extraction.
        if result.returncode != 0 or not temp_file.exists():  # Verify extraction succeeded.
            log_debug(f"Embedded subtitle detection extraction failed for {video_path} stream {track_position}: {result.stderr.strip()}", self.config.verbose)  # Log extraction failure.
            return []  # Return no extracted lines.
        lines = read_text_file_lines(temp_file)  # Read extracted lines.
        temp_file.unlink(missing_ok=True)  # Remove temporary subtitle file.
        return lines  # Return extracted lines.

    def extract_to_srt(self, video_path: Path, subtitle_track: TrackInfo, output_file: Path) -> Path | None:
        """
        Extracts one embedded text subtitle track to SRT.

        :param video_path: Video path.
        :param subtitle_track: Embedded subtitle track inventory record.
        :param output_file: Desired output SRT path.
        :return: Output SRT path or None.
        """

        if not self.can_extract_text(subtitle_track.codec):  # Verify subtitle can be extracted as text.
            log_warning(f"Embedded subtitle stream {subtitle_track.track_position} uses codec {subtitle_track.codec}; OCR is not integrated.")  # Report unsupported extraction.
            return None  # Return no extraction.
        command = ["ffmpeg", "-y", "-i", str(video_path), "-map", f"0:s:{subtitle_track.track_position}", str(output_file)]  # Build ffmpeg extraction command.
        result = self.runner.run(command)  # Run extraction.
        if result.returncode != 0 or not output_file.exists() or output_file.stat().st_size == 0:  # Verify extraction output exists.
            log_warning(f"Failed to extract embedded subtitle from {video_path.name}: {result.stderr.strip()}")  # Report extraction failure.
            output_file.unlink(missing_ok=True)  # Remove partial extraction.
            return None  # Return no extraction.
        return output_file  # Return extracted subtitle path.
