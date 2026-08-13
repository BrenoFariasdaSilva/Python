"""
Subtitle synchronization through ffsubsync.
"""

from pathlib import Path  # Represent video and subtitle paths.
from command_runner import CommandRunner  # Execute ffsubsync.
from config import AppConfig  # Read synchronization settings.
from console import BackgroundColors, STYLE_RESET, log_warning  # Report synchronization results.


class SubtitleSynchronizer:
    """
    Owns downloaded SRT synchronization.
    """

    def __init__(self, config: AppConfig, runner: CommandRunner) -> None:
        """
        Initializes subtitle synchronization.

        :param config: Application configuration.
        :param runner: External command runner.
        :return: None.
        """

        self.config = config  # Store application configuration.
        self.runner = runner  # Store command runner.

    def synchronize(self, video_path: Path, srt_file: Path) -> bool:
        """
        Synchronizes one SRT subtitle with ffsubsync.

        :param video_path: Video path.
        :param srt_file: SRT subtitle path.
        :return: True when synchronized output replaced the source.
        """

        if not self.config.sync_downloaded_subtitles:  # Verify synchronization is enabled.
            return False  # Return no synchronization.
        if srt_file.suffix.lower() != ".srt":  # Verify subtitle is SRT.
            return False  # Return no synchronization for non-SRT.

        ffsubsync_cmd = self.runner.find_executable("ffsubsync")  # Locate ffsubsync executable.
        if ffsubsync_cmd is None:  # Verify ffsubsync is available.
            log_warning("ffsubsync executable not found; downloaded subtitle left unsynchronized.")  # Report missing synchronization tool.
            return False  # Return no synchronization.

        synced_srt_file = srt_file.with_name(srt_file.stem + "-synced.srt")  # Build synchronized output path.
        command = [ffsubsync_cmd, str(video_path), "-i", str(srt_file), "-o", str(synced_srt_file)]  # Build ffsubsync command.
        result = self.runner.run(command)  # Run synchronization.
        if result.returncode != 0 or not synced_srt_file.exists() or synced_srt_file.stat().st_size == 0:  # Verify synchronized output exists.
            log_warning(f"Subtitle synchronization failed for {srt_file.name}: {result.stderr.strip()}")  # Report synchronization failure.
            synced_srt_file.unlink(missing_ok=True)  # Remove partial synced output.
            return False  # Return no replacement.

        synced_srt_file.replace(srt_file)  # Replace original subtitle with synchronized subtitle.
        print(f"{BackgroundColors.GREEN}Synchronized subtitle:{STYLE_RESET} {BackgroundColors.CYAN}{srt_file.name}{STYLE_RESET}")  # Report synchronization success.
        return True  # Return synchronization success.
