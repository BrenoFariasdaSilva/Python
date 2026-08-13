"""
Shared workflow data models.
"""

from dataclasses import dataclass, field  # Define typed immutable-like records.
from pathlib import Path  # Represent filesystem paths.


JsonValue = str | int | float | bool | None | dict[str, "JsonValue"] | list["JsonValue"]  # Describe JSON-like ffprobe values.


@dataclass(frozen=True)
class CommandResult:
    """
    Stores an external command result.
    """

    returncode: int  # Store process return code.
    stdout: str  # Store captured standard output.
    stderr: str  # Store captured standard error.


@dataclass
class TrackInfo:
    """
    Stores audio or embedded subtitle track metadata.
    """

    index: int | None  # Store global stream index.
    track_type: str  # Store track type.
    track_position: int  # Store type-relative stream position.
    title: str = ""  # Store stream title.
    track_name: str = ""  # Store name-like metadata.
    declared_language: str = ""  # Store declared metadata language.
    normalized_language: str | None = None  # Store canonical language when known.
    default: bool = False  # Store default disposition.
    forced: bool = False  # Store forced disposition.
    codec: str = ""  # Store codec name.
    tags: dict[str, str] = field(default_factory=dict)  # Store stream tags.
    disposition: dict[str, int | str | bool | None] = field(default_factory=dict)  # Store stream dispositions.


@dataclass(frozen=True)
class ExternalSubtitle:
    """
    Stores associated external subtitle metadata.
    """

    path: Path  # Store subtitle file path.
    normalized_language: str | None  # Store canonical language when known.
    title: str  # Store display title.
    codec: str  # Store subtitle extension.


@dataclass(frozen=True)
class VideoStatus:
    """
    Stores final per-video workflow status.
    """

    video: Path  # Store video path.
    audio_modified: bool  # Store audio modification result.
    ptbr_available: bool  # Store final PT-BR availability.
    english_available: bool  # Store final English availability.
