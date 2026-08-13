"""
Application configuration and CLI parsing.
"""

import argparse  # Parse command-line arguments.
from dataclasses import dataclass, field  # Define typed configuration objects.
from pathlib import Path  # Resolve input paths.


DESIRED_LANGUAGES = {  # Store desired language aliases.
    "English": ["english", "eng", "en", "Inglês"],  # Store English aliases.
    "Brazilian Portuguese": ["PT-BR FULL", "brazilian", "portuguese", "COMPLETA PT-BR", "PT-BR COMPLETA", "Português (Brasil)", "pt-br", "pt"],  # Store PT-BR aliases.
}  # Finish desired language mapping.


@dataclass(frozen=True)
class AppConfig:
    """
    Owns application settings shared by workflow components.
    """

    script_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent)  # Store project directory.
    input_directory: Path = Path("./Input")  # Store resolved input directory.
    video_extensions: tuple[str, ...] = (".mkv", ".mp4", ".avi", ".mov")  # Store supported video extensions.
    subtitle_extensions: tuple[str, ...] = (".srt", ".ass", ".ssa", ".vtt", ".sub")  # Store supported external subtitle extensions.
    ignore_dirs: tuple[str, ...] = ("Backup", ".assets", "venv", ".venv")  # Store ignored directory fragments.
    ignore_file_patterns: tuple[str, ...] = (".tmp", ".part", ".partial", ".!ut", ".temp")  # Store ignored file fragments.
    desired_languages: dict[str, list[str]] = field(default_factory=lambda: {key: list(values) for key, values in DESIRED_LANGUAGES.items()})  # Store language aliases.
    audio_priority_order: tuple[str, ...] = ("English", "Brazilian Portuguese")  # Store default audio priority.
    required_subtitle_languages: tuple[str, ...] = ("Brazilian Portuguese",)  # Store obligatory subtitle languages.
    translation_source_languages: tuple[str, ...] = ("English",)  # Store source languages for PT-BR fallback.
    subtitle_download_languages: dict[str, tuple[str, ...]] = field(default_factory=lambda: {"Brazilian Portuguese": ("pt-BR", "pt", "pt-PT"), "English": ("eng", "en", "en-US")})  # Store downloader language variants.
    text_subtitle_codecs: tuple[str, ...] = ("subrip", "text", "ass", "ssa", "webvtt", "mov_text")  # Store extractable subtitle codecs.
    bitmap_subtitle_codecs: tuple[str, ...] = ("hdmv_pgs_subtitle", "dvd_subtitle")  # Store bitmap subtitle codecs.
    target_language: str = "PT-BR"  # Store DeepL target language.
    remove_descriptive_subtitles: bool = True  # Enable SDH cleanup before translation.
    enable_subtitle_downloads: bool = True  # Enable subtitle downloads.
    sync_downloaded_subtitles: bool = True  # Enable synchronization for downloaded SRTs.
    enable_deepl_translation: bool = True  # Enable DeepL fallback translation.
    language_detection_min_letters: int = 80  # Store minimum letters for subtitle content detection.
    language_detection_max_sample_chars: int = 4000  # Store maximum language detection sample size.
    sound_file: str = "./.assets/Sounds/NotificationSound.wav"  # Store notification sound path.
    play_sound: bool = True  # Enable notification sound.
    verbose: bool = False  # Enable verbose output.

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "AppConfig":
        """
        Builds configuration from parsed CLI arguments.

        :param args: Parsed CLI arguments.
        :return: Application configuration.
        """

        script_dir = Path(__file__).resolve().parent  # Resolve project directory.
        input_directory = Path(args.input_directory).expanduser()  # Expand configured input path.
        if not input_directory.is_absolute():  # Verify input path is relative.
            input_directory = script_dir / input_directory  # Resolve relative input path from project directory.
        required_languages = tuple(dict.fromkeys(args.required_subtitle_language)) if args.required_subtitle_language else ("Brazilian Portuguese",)  # Resolve required subtitle languages.
        return cls(script_dir=script_dir, input_directory=input_directory.resolve(), required_subtitle_languages=required_languages, enable_subtitle_downloads=not args.skip_subtitle_download, sync_downloaded_subtitles=not args.skip_subtitle_sync, enable_deepl_translation=not args.skip_deepl_translation, verbose=bool(args.verbose))  # Return configured settings.


def parse_arguments() -> argparse.Namespace:
    """
    Parses CLI arguments.

    :return: Parsed arguments.
    """

    parser = argparse.ArgumentParser(description="Manage video audio defaults and subtitles.")  # Create CLI parser.
    parser.add_argument("--input-directory", default="./Input", help="Directory containing video files")  # Add input directory option.
    parser.add_argument("--required-subtitle-language", action="append", choices=list(DESIRED_LANGUAGES.keys()), help="Required subtitle language; may be passed multiple times")  # Add required language option.
    parser.add_argument("--skip-subtitle-download", action="store_true", help="Skip subliminal subtitle downloads")  # Add download skip option.
    parser.add_argument("--skip-subtitle-sync", action="store_true", help="Skip ffsubsync for downloaded subtitles")  # Add sync skip option.
    parser.add_argument("--skip-deepl-translation", action="store_true", help="Skip DeepL PT-BR translation fallback")  # Add translation skip option.
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")  # Add verbose option.
    return parser.parse_args()  # Return parsed arguments.
