"""
Default audio track management.
"""

from pathlib import Path  # Represent video paths.
from command_runner import CommandRunner  # Execute ffmpeg.
from config import AppConfig  # Read audio priority.
from console import BackgroundColors, STYLE_RESET, log_debug, log_warning  # Report audio workflow results.
from models import TrackInfo  # Consume audio track metadata.


class AudioTrackManager:
    """
    Owns preferred audio selection and default disposition updates.
    """

    def __init__(self, config: AppConfig, runner: CommandRunner) -> None:
        """
        Initializes audio track management.

        :param config: Application configuration.
        :param runner: External command runner.
        :return: None.
        """

        self.config = config  # Store application configuration.
        self.runner = runner  # Store command runner.

    def select_preferred_audio_track(self, audio_tracks: list[TrackInfo]) -> TrackInfo | None:
        """
        Selects the preferred audio track by configured priority.

        :param audio_tracks: Audio track inventory.
        :return: Selected audio track or None.
        """

        for language_name in self.config.audio_priority_order:  # Iterate preferred language order.
            for track in audio_tracks:  # Iterate audio tracks in file order.
                if track.normalized_language == language_name:  # Verify language priority match.
                    return track  # Return selected track.
        return None  # Return no selection when desired audio is absent.

    def set_preferred_default_audio(self, video_path: Path, audio_tracks: list[TrackInfo]) -> bool:
        """
        Sets preferred audio track as default when needed.

        :param video_path: Video path.
        :param audio_tracks: Audio track inventory.
        :return: True when video was modified.
        """

        selected_track = self.select_preferred_audio_track(audio_tracks)  # Select desired audio track.
        if selected_track is None:  # Verify desired audio exists.
            log_warning(f"No desired audio track found for {video_path}; source audio left untouched.")  # Report missing desired audio.
            return False  # Return no modification.
        if selected_track.default:  # Verify preferred track already default.
            log_debug(f"Preferred audio already default for {video_path}.", self.config.verbose)  # Report no-op when verbose.
            return False  # Return no modification.

        temp_file = video_path.with_name(video_path.stem + ".tmp" + video_path.suffix.lower())  # Build temporary media path.
        command = ["ffmpeg", "-y", "-i", str(video_path), "-map", "0", "-c", "copy"]  # Build remux command preserving every stream.
        for audio_index, track in enumerate(audio_tracks):  # Iterate output audio stream order.
            disposition_value = "default" if track is selected_track else "0"  # Select disposition value.
            command.extend([f"-disposition:a:{audio_index}", disposition_value])  # Add audio disposition argument.
        command.append(str(temp_file))  # Add temporary output path.

        result = self.runner.run(command)  # Run ffmpeg remux.
        if result.returncode != 0 or not temp_file.exists() or temp_file.stat().st_size == 0:  # Verify remux produced valid temporary file.
            log_warning(f"Failed to set default audio for {video_path}: {result.stderr.strip()}")  # Report remux failure.
            temp_file.unlink(missing_ok=True)  # Remove partial temporary file.
            return False  # Return no successful modification.

        temp_file.replace(video_path)  # Replace original video after successful remux.
        print(f"{BackgroundColors.GREEN}Default audio set to {BackgroundColors.CYAN}{selected_track.normalized_language}{BackgroundColors.GREEN} for {BackgroundColors.CYAN}{video_path.name}{STYLE_RESET}")  # Report audio default update.
        return True  # Return modification flag.
