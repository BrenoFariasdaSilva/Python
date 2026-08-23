"""
================================================================================
Subtitle Credits-Promotional Content Detector
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-08-23
Description :
    Recursively scans SRT subtitle files and detects blocks that appear to contain
    subtitle-author credits, subtitle-group credits, websites, social-network
    promotion, handles, download/promotion messages, and other text added by the
    subtitle creator/distributor rather than belonging to the actual subtitle.

    The detector does not modify subtitle files. It creates one grouped JSON
    report per configured input directory. Identical normalized unwanted strings
    are grouped together with a counter, while every occurrence retains exact
    file/block metadata and cryptographic hashes for safe later removal.

    Key features include:
        - Recursive SRT discovery across multiple configured input directories
        - Conservative score-based credit/promotional-content detection
        - Exact detection of websites, social handles, credit phrases, and promo text
        - Grouped report strings with occurrence counters
        - Exact file/block metadata for report-driven removal
        - SHA-256 file and block fingerprints for safe removal verification
        - PT-BR-friendly subtitle decoding with UTF-8/Windows-1252 fallbacks
        - Logger integration and one colored progress bar per input directory

Usage:
    1. Configure INPUT_DIRS if necessary.
    2. Copy the repository's existing Logger.py beside this script.
    3. Execute:
        $ python detect.py
    4. Review the generated JSON reports before running remove.py.

Outputs:
    - ./Outputs/<input-directory-prefix>-report.json
    - ./Logs/detect.log

TODOs:
    - Extend CREDIT_PATTERNS/PROMOTIONAL_PATTERNS when new real-world signatures are found.
    - Add optional user-managed allow/deny lists if manual overrides become necessary.

Dependencies:
    - Python >= 3.10
    - colorama
    - tqdm
    - Local Logger.py from the repository template

Assumptions & Notes:
    - Detection is intentionally conservative to reduce removal of real dialogue.
    - The detector never edits SRT files.
    - The remover consumes reviewed detector reports instead of re-detecting content.
    - Paths stored in JSON use forward slashes.
"""

import atexit  # For playing a sound when the program finishes
import datetime  # For getting the current date and time
import hashlib  # For generating exact file/block fingerprints
import json  # For writing grouped detection reports
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For matching SRT structures and unwanted-content signals
import sys  # For system-specific parameters and functions
from colorama import Style  # For coloring the terminal
from Logger import Logger  # For logging output to both terminal and file
from pathlib import Path  # For handling file paths
from tqdm import tqdm  # For displaying per-directory progress bars


# Macros:
class BackgroundColors:  # Colors for the terminal
    CYAN = "\033[96m"  # Cyan
    GREEN = "\033[92m"  # Green
    YELLOW = "\033[93m"  # Yellow
    RED = "\033[91m"  # Red
    BOLD = "\033[1m"  # Bold
    UNDERLINE = "\033[4m"  # Underline
    CLEAR_TERMINAL = "\033[H\033[J"  # Clear the terminal


# Execution Constants:
VERBOSE = False  # Set to True to output verbose messages
INPUT_DIRS = [f"E:/Movies/", f"F:/Movies/", f"F:/Series/", f"G:/Series/", f"G:/Animes/"]  # Directories searched recursively for source SRT files
OUTPUT_DIR = Path("./Outputs")  # Directory used for one grouped JSON report per input directory
DETECTION_SCORE_THRESHOLD = 7  # Minimum conservative score required for a block to be reported
EDGE_BLOCK_WINDOW = 20  # Number of first/last blocks considered likely credit/promo positions
SHORT_BLOCK_CHARACTER_LIMIT = 220  # Maximum plain-text size rewarded as typical credit/promo text
SRT_TEXT_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")  # Common subtitle encodings

KNOWN_SUBTITLE_SITES = (
    "opensubtitles.org",
    "opensubtitles.com",
    "addic7ed.com",
    "tvsubtitles.net",
    "subscene.com",
    "podnapisi.net",
    "yifysubtitles.org",
    "legendastv.com",
    "legendas.tv",
    "legendas-zone.org",
    "subdivx.com",
)  # Known subtitle-distribution sites that are strong non-dialogue indicators

CREDIT_PATTERNS = (
    re.compile(r"\blegendas?\b\s*(?:por|by|de|:)", re.IGNORECASE),
    re.compile(r"\blegendad[oa]s?\b\s*(?:por|by|de|:)", re.IGNORECASE),
    re.compile(r"\bsincroniza(?:ç|c)[aã]o\b\s*(?:por|by|de|:)", re.IGNORECASE),
    re.compile(r"\bsincronizad[oa]s?\b\s*(?:por|by|de|:)", re.IGNORECASE),
    re.compile(r"\btradu(?:ç|c)[aã]o\b\s*(?:por|by|de|:)", re.IGNORECASE),
    re.compile(r"\btraduzid[oa]s?\b\s*(?:por|by|de|:)", re.IGNORECASE),
    re.compile(r"\brevis(?:ã|a)o\b\s*(?:por|by|de|:)", re.IGNORECASE),
    re.compile(r"\brevisad[oa]s?\b\s*(?:por|by|de|:)", re.IGNORECASE),
    re.compile(r"\b(?:subtitle|subtitles|caption|captions)\s+by\b", re.IGNORECASE),
    re.compile(r"\b(?:sync|resync|timing|translation|translated)\s+by\b", re.IGNORECASE),
    re.compile(r"\b(?:rip|ripped)\s+by\b", re.IGNORECASE),
)  # Strong creator/contributor credit phrases

PROMOTIONAL_PATTERNS = (
    re.compile(r"\bsigam[- ]?me\b", re.IGNORECASE),
    re.compile(r"\bsiga[- ]?me\b", re.IGNORECASE),
    re.compile(r"\bfollow\s+me\b", re.IGNORECASE),
    re.compile(r"\b(?:visite|acesse|confira)\b.*\b(?:site|p[aá]gina|canal)\b", re.IGNORECASE),
    re.compile(r"\b(?:download|baixe)\b.*\b(?:legenda|legendas|subtitle|subtitles)\b", re.IGNORECASE),
    re.compile(r"\bsugest(?:ão|ao|ões|oes)\b.*\blegend", re.IGNORECASE),
    re.compile(r"\b(?:assista|assistam)\b.*\b(?:frente|antes)\b", re.IGNORECASE),
    re.compile(r"\b(?:twitter|instagram|facebook|tiktok|telegram|youtube)\b", re.IGNORECASE),
)  # Promotional/social-network language

SUBTITLE_CONTEXT_PATTERN = re.compile(
    r"\b(?:legenda|legendas|legendad[oa]s?|subtitle|subtitles|subs|traduzid[oa]s?|tradu(?:ç|c)[aã]o|sincroniza(?:ç|c)[aã]o)\b",
    re.IGNORECASE,
)  # Weak subtitle-creation context signal

WEBSITE_PATTERN = re.compile(
    r"(?:(?:https?://)|(?:www\.))?[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?)+(?:/[^\s<>]*)?",
    re.IGNORECASE,
)  # Generic website/domain pattern

SOCIAL_HANDLE_PATTERN = re.compile(r"(?<![\w@])@[A-Za-z0-9_][A-Za-z0-9_.-]{1,31}\b")  # Social-network handle pattern
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")  # Generic formatting tag pattern used only for detection normalization


# Logger Setup:
PROGRESS_OUTPUT = sys.stdout  # Preserve original terminal stream so tqdm can update one line in place
logger = Logger(f"./Logs/{Path(__file__).stem}.log", clean=True)  # Create a Logger instance
sys.stdout = logger  # Redirect stdout to the logger
sys.stderr = logger  # Redirect stderr to the logger


# Sound Constants:
SOUND_COMMANDS = {
    "Darwin": "afplay",
    "Linux": "aplay",
    "Windows": "start",
}  # The commands to play a sound for each operating system
SOUND_FILE = "./.assets/Sounds/NotificationSound.wav"  # The path to the sound file


# RUN_FUNCTIONS:
RUN_FUNCTIONS = {
    "Play Sound": True,  # Set to True to play a sound when the program finishes
}


# Functions Definitions:


def verbose_output(true_string="", false_string=""):
    """
    Outputs a message if the VERBOSE constant is set to True.

    :param true_string: The string to be outputted if the VERBOSE constant is set to True.
    :param false_string: The string to be outputted if the VERBOSE constant is set to False.
    :return: None
    """

    if VERBOSE and true_string != "":
        print(true_string)
    elif false_string != "":
        print(false_string)


def resolve_full_trailing_space_path(filepath: str) -> str:
    """
    Resolve a configured path conservatively.

    :param filepath: Path to resolve.
    :return: Existing normalized path when possible, otherwise original path.
    """

    try:
        verbose_output(true_string=f"{BackgroundColors.GREEN}Resolving path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}")

        if not isinstance(filepath, str) or not filepath:
            return filepath

        filepath = os.path.expanduser(filepath)

        if os.path.exists(filepath):
            return filepath

        candidate = os.path.normpath(filepath)
        return candidate if os.path.exists(candidate) else filepath
    except Exception:
        return filepath


def verify_filepath_exists(filepath):
    """
    Verify if a file or folder exists at the specified path.

    :param filepath: Path to the file or folder.
    :return: True if it exists, False otherwise.
    """

    try:
        return isinstance(filepath, str) and bool(filepath.strip()) and os.path.exists(filepath)
    except Exception as exc:
        print(str(exc))
        raise


def to_seconds(obj):
    """
    Convert a time-like object to seconds.

    :param obj: Numeric/timedelta/datetime-like object.
    :return: Float seconds or None.
    """

    if obj is None:
        return None
    if isinstance(obj, (int, float)):
        return float(obj)
    if hasattr(obj, "total_seconds"):
        try:
            return float(obj.total_seconds())
        except Exception:
            pass
    if hasattr(obj, "timestamp"):
        try:
            return float(obj.timestamp())
        except Exception:
            pass
    return None


def calculate_execution_time(start_time, finish_time=None):
    """
    Calculate execution time and return a human-readable string.

    :param start_time: Start object or complete duration.
    :param finish_time: Optional finish object.
    :return: Human-readable duration.
    """

    if finish_time is None:
        total_seconds = to_seconds(start_time)
        total_seconds = total_seconds if total_seconds is not None else 0.0
    else:
        start_seconds = to_seconds(start_time)
        finish_seconds = to_seconds(finish_time)
        total_seconds = (finish_seconds - start_seconds) if start_seconds is not None and finish_seconds is not None else 0.0

    total_seconds = abs(total_seconds or 0.0)
    days = int(total_seconds // 86400)
    hours = int((total_seconds % 86400) // 3600)
    minutes = int((total_seconds % 3600) // 60)
    seconds = int(total_seconds % 60)

    if days > 0:
        return f"{days}d {hours}h {minutes}m {seconds}s"
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def play_sound():
    """
    Play completion sound and skip on Windows.

    :return: None
    """

    current_os = platform.system()

    if current_os == "Windows":
        return

    if verify_filepath_exists(SOUND_FILE) and current_os in SOUND_COMMANDS:
        os.system(f"{SOUND_COMMANDS[current_os]} {SOUND_FILE}")


def atomic_write_text(filepath: Path, content: str) -> None:
    """
    Write text through a sibling temporary file and atomic replacement.

    :param filepath: Destination path.
    :param content: UTF-8 text content.
    :return: None
    """

    filepath.parent.mkdir(parents=True, exist_ok=True)
    temporary_filepath = filepath.with_name(f".{filepath.name}.{os.getpid()}.tmp")

    try:
        with open(temporary_filepath, "w", encoding="utf-8", newline="\n") as temporary_file:
            temporary_file.write(content)
        os.replace(temporary_filepath, filepath)
    finally:
        if temporary_filepath.exists():
            temporary_filepath.unlink()


def read_srt_file(filepath: Path) -> str:
    """
    Read an SRT file using common UTF-8/Western subtitle encodings.

    :param filepath: Source SRT path.
    :return: Decoded subtitle text.
    """

    data = filepath.read_bytes()

    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16")

    for encoding in SRT_TEXT_ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue

    raise UnicodeDecodeError("utf-8", data, 0, 1, "Unable to decode subtitle file")


def discover_srt_files(input_dir: Path) -> list[Path]:
    """
    Discover source SRT files recursively.

    :param input_dir: Directory to search.
    :return: Sorted source SRT paths.
    """

    return sorted(path for path in input_dir.rglob("*.srt") if not path.name.lower().endswith(".cleaned.srt"))


def file_sha256(filepath: Path) -> str:
    """
    Calculate SHA-256 for one file.

    :param filepath: File path to hash.
    :return: Lowercase hexadecimal SHA-256 digest.
    """

    digest = hashlib.sha256()

    with filepath.open("rb") as source_file:
        for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def block_sha256(index: int, timestamp: str, text: str) -> str:
    """
    Calculate deterministic SHA-256 identity for one SRT block.

    :param index: Original SRT index.
    :param timestamp: Original timestamp line.
    :param text: Original subtitle text.
    :return: Hexadecimal SHA-256 digest.
    """

    return hashlib.sha256(f"{index}\n{timestamp}\n{text}".encode("utf-8")).hexdigest()


def parse_srt_blocks(content: str) -> list[dict[str, object]]:
    """
    Parse SRT blocks by detecting index+timestamp headers instead of blank-line splitting.

    :param content: Decoded SRT content.
    :return: Ordered block dictionaries.
    """

    normalized_content = content.replace("\r\n", "\n").replace("\r", "\n").strip("\ufeff")
    lines = normalized_content.split("\n")
    blocks = []
    line_index = 0

    while line_index < len(lines):
        current = lines[line_index].strip()

        if current.isdigit() and line_index + 1 < len(lines) and "-->" in lines[line_index + 1]:
            original_index = int(current)
            timestamp = lines[line_index + 1].strip()
            text_start = line_index + 2
            next_index = text_start

            while next_index < len(lines):
                next_line = lines[next_index].strip()
                if next_line.isdigit() and next_index + 1 < len(lines) and "-->" in lines[next_index + 1]:
                    break
                next_index += 1

            text_lines = lines[text_start:next_index]

            while text_lines and not text_lines[0].strip():
                text_lines.pop(0)
            while text_lines and not text_lines[-1].strip():
                text_lines.pop()

            blocks.append(
                {
                    "block_number": len(blocks) + 1,
                    "original_index": original_index,
                    "timestamp": timestamp,
                    "text": "\n".join(text_lines),
                }
            )
            line_index = next_index
            continue

        line_index += 1

    return blocks


def strip_formatting_tags(value: str) -> str:
    """
    Remove formatting tags only for detection analysis.

    :param value: Subtitle text.
    :return: Tag-free text.
    """

    return HTML_TAG_PATTERN.sub("", value)


def normalize_display_text(value: str) -> str:
    """
    Normalize one detected block into a grouping string.

    :param value: Plain subtitle text.
    :return: Compact human-readable string used for grouping.
    """

    return re.sub(r"\s+", " ", value).strip()


def normalize_group_key(value: str) -> str:
    """
    Normalize one finding string for case-insensitive grouping.

    :param value: Display finding string.
    :return: Stable grouping key.
    """

    return normalize_display_text(value).casefold()


def extract_detection_signals(text: str) -> list[dict[str, object]]:
    """
    Extract exact evidence strings indicating creator/distributor-added content.

    :param text: Plain subtitle block text without formatting tags.
    :return: Structured signal dictionaries.
    """

    signals = []
    seen = set()

    def add_signal(category: str, string: str, weight: int) -> None:
        cleaned_string = normalize_display_text(string)
        key = (category, cleaned_string.casefold())
        if cleaned_string and key not in seen:
            seen.add(key)
            signals.append({"category": category, "string": cleaned_string, "weight": weight})

    lowered_text = text.casefold()

    for site in KNOWN_SUBTITLE_SITES:
        if site.casefold() in lowered_text:
            add_signal("known_subtitle_site", site, 10)

    for match in WEBSITE_PATTERN.finditer(text):
        add_signal("website", match.group(0), 6)

    for match in SOCIAL_HANDLE_PATTERN.finditer(text):
        add_signal("social_handle", match.group(0), 4)

    for pattern in CREDIT_PATTERNS:
        for match in pattern.finditer(text):
            add_signal("subtitle_credit_phrase", match.group(0), 8)

    for pattern in PROMOTIONAL_PATTERNS:
        for match in pattern.finditer(text):
            add_signal("promotional_phrase", match.group(0), 5)

    for match in SUBTITLE_CONTEXT_PATTERN.finditer(text):
        add_signal("subtitle_creation_context", match.group(0), 2)

    return signals


def score_unwanted_block(block: dict[str, object], total_blocks: int) -> tuple[int, list[dict[str, object]]]:
    """
    Score one SRT block for likely subtitle-author/distributor-added content.

    :param block: Parsed SRT block.
    :param total_blocks: Number of blocks in current file.
    :return: Detection score and evidence signals.
    """

    plain_text = strip_formatting_tags(str(block["text"]))
    signals = extract_detection_signals(plain_text)
    score = sum(int(signal["weight"]) for signal in signals)
    block_number = int(block["block_number"])
    original_index = int(block["original_index"])
    compact_text = normalize_display_text(plain_text)

    if compact_text and len(compact_text) <= SHORT_BLOCK_CHARACTER_LIMIT:
        score += 1

    if block_number <= EDGE_BLOCK_WINDOW or block_number > max(0, total_blocks - EDGE_BLOCK_WINDOW):
        score += 1

    if original_index > max(total_blocks + 100, 2000):
        score += 2

    return score, signals


def classify_confidence(score: int) -> str:
    """
    Convert numeric score into report confidence.

    :param score: Detection score.
    :return: high or medium.
    """

    return "high" if score >= 10 else "medium"


def build_detection_occurrence(
    filepath: Path,
    current_file_sha256: str,
    block: dict[str, object],
    total_blocks: int,
) -> dict[str, object] | None:
    """
    Build one exact report occurrence when a block passes detection threshold.

    :param filepath: Source SRT path.
    :param current_file_sha256: SHA-256 of source file.
    :param block: Parsed block.
    :param total_blocks: Number of parsed blocks.
    :return: Occurrence dictionary or None.
    """

    score, signals = score_unwanted_block(block, total_blocks)

    if score < DETECTION_SCORE_THRESHOLD or not signals:
        return None

    text = str(block["text"])
    plain_text = strip_formatting_tags(text)
    display_string = normalize_display_text(plain_text)

    if not display_string:
        return None

    return {
        "file_path": filepath.resolve().as_posix(),
        "file_sha256": current_file_sha256,
        "block_sha256": block_sha256(int(block["original_index"]), str(block["timestamp"]), text),
        "block_number": int(block["block_number"]),
        "original_index": int(block["original_index"]),
        "timestamp": str(block["timestamp"]),
        "text": text,
        "plain_text": display_string,
        "matched_strings": signals,
        "score": score,
        "confidence": classify_confidence(score),
    }


def detect_file_findings(filepath: Path) -> list[dict[str, object]]:
    """
    Detect unwanted creator/distributor-added blocks in one SRT file.

    :param filepath: Source SRT path.
    :return: Detected occurrence dictionaries.
    """

    content = read_srt_file(filepath)
    blocks = parse_srt_blocks(content)
    current_file_sha256 = file_sha256(filepath)
    occurrences = []

    for block in blocks:
        occurrence = build_detection_occurrence(filepath, current_file_sha256, block, len(blocks))
        if occurrence is not None:
            occurrences.append(occurrence)

    return occurrences


def group_findings(occurrences: list[dict[str, object]]) -> list[dict[str, object]]:
    """
    Group identical normalized unwanted strings and count their occurrences.

    :param occurrences: Detected occurrences for one input directory.
    :return: Sorted grouped findings.
    """

    grouped = {}

    for occurrence in occurrences:
        display_string = str(occurrence["plain_text"])
        group_key = normalize_group_key(display_string)

        if group_key not in grouped:
            grouped[group_key] = {
                "string": display_string,
                "count": 0,
                "categories": set(),
                "occurrences": [],
            }

        grouped_entry = grouped[group_key]
        grouped_entry["count"] += 1
        grouped_entry["occurrences"].append(occurrence)

        for signal in occurrence["matched_strings"]:
            grouped_entry["categories"].add(signal["category"])

    findings = []

    for grouped_entry in grouped.values():
        findings.append(
            {
                "string": grouped_entry["string"],
                "count": grouped_entry["count"],
                "categories": sorted(grouped_entry["categories"]),
                "occurrences": sorted(
                    grouped_entry["occurrences"],
                    key=lambda item: (item["file_path"].casefold(), item["block_number"]),
                ),
            }
        )

    return sorted(findings, key=lambda item: (-item["count"], item["string"].casefold()))


def build_report_filename_prefix(configured_input_dir: str) -> str:
    """
    Build Windows-safe report filename prefix from configured input directory.

    :param configured_input_dir: Original configured input directory string.
    :return: Safe prefix with slash types replaced by hyphens.
    """

    normalized = re.sub(r"[\\/]+", "-", str(configured_input_dir).strip())
    normalized = re.sub(r'[<>:"|?*]+', "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-. ")
    return normalized or "input"


def build_report_path(configured_input_dir: str) -> Path:
    """
    Build per-input-directory report path.

    :param configured_input_dir: Original configured input directory.
    :return: ./Outputs/<prefix>-report.json path.
    """

    return OUTPUT_DIR / f"{build_report_filename_prefix(configured_input_dir)}-report.json"


def write_detection_report(
    configured_input_dir: str,
    input_dir: Path,
    scanned_files: int,
    occurrences: list[dict[str, object]],
) -> Path:
    """
    Write one grouped detection report for an input directory.

    :param configured_input_dir: Original configured root.
    :param input_dir: Resolved processed root.
    :param scanned_files: Number of scanned SRT files.
    :param occurrences: Detected block occurrences.
    :return: Written report path.
    """

    findings = group_findings(occurrences)
    affected_files = {occurrence["file_path"] for occurrence in occurrences}
    report_payload = {
        "input_dir": input_dir.as_posix().rstrip("/") + "/",
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "summary": {
            "srt_files_scanned": scanned_files,
            "srt_files_with_findings": len(affected_files),
            "detected_blocks": len(occurrences),
            "grouped_strings": len(findings),
        },
        "findings": findings,
    }
    report_path = build_report_path(configured_input_dir)
    atomic_write_text(report_path, json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n")
    return report_path


def display_input_directory(input_dir: Path) -> str:
    """
    Format input directory for progress output.

    :param input_dir: Input root.
    :return: Forward-slash path with trailing slash.
    """

    return input_dir.as_posix().rstrip("/") + "/"


def display_relative_path(filepath: Path, input_dir: Path) -> str:
    """
    Format file relative to input directory when possible.

    :param filepath: Current file.
    :param input_dir: Current root.
    :return: Display path.
    """

    try:
        return filepath.relative_to(input_dir).as_posix()
    except ValueError:
        return filepath.as_posix()


def main():
    """
    Main function.

    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Subtitle Credits-Promotional Content Detector{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
    )

    start_time = datetime.datetime.now()
    total_scanned = 0
    total_detected_blocks = 0
    total_affected_files = 0

    for configured_input_dir in INPUT_DIRS:
        input_dir = Path(resolve_full_trailing_space_path(str(configured_input_dir))).resolve()

        if not verify_filepath_exists(str(input_dir)) or not input_dir.is_dir():
            print(f"{BackgroundColors.RED}Input directory not found: {BackgroundColors.CYAN}{input_dir}{Style.RESET_ALL}")
            continue

        srt_files = discover_srt_files(input_dir)
        directory_occurrences = []
        affected_files = set()
        directory_display = display_input_directory(input_dir)

        with tqdm(
            srt_files,
            total=len(srt_files),
            file=PROGRESS_OUTPUT,
            desc=f"{BackgroundColors.GREEN}Detecting {BackgroundColors.CYAN}{directory_display}{Style.RESET_ALL}",
            unit="file",
            dynamic_ncols=True,
            leave=True,
            colour="green",
            bar_format="{desc}: {percentage:3.0f}%|{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}] {postfix}",
        ) as progress_bar:
            for srt_file in progress_bar:
                relative_path = display_relative_path(srt_file, input_dir)
                progress_bar.set_postfix_str(
                    f"{BackgroundColors.GREEN}File: {BackgroundColors.CYAN}{relative_path}{Style.RESET_ALL}",
                    refresh=True,
                )

                try:
                    file_occurrences = detect_file_findings(srt_file)
                    directory_occurrences.extend(file_occurrences)

                    if file_occurrences:
                        affected_files.add(srt_file.resolve().as_posix())
                except Exception as exc:
                    tqdm.write(
                        f"{BackgroundColors.RED}Failed: {BackgroundColors.CYAN}{relative_path}{BackgroundColors.RED} - {exc}{Style.RESET_ALL}",
                        file=PROGRESS_OUTPUT,
                    )

        report_path = write_detection_report(
            str(configured_input_dir),
            input_dir,
            len(srt_files),
            directory_occurrences,
        )
        print(f"{BackgroundColors.GREEN}Report: {BackgroundColors.CYAN}{report_path.as_posix()}{Style.RESET_ALL}")

        total_scanned += len(srt_files)
        total_detected_blocks += len(directory_occurrences)
        total_affected_files += len(affected_files)

    finish_time = datetime.datetime.now()

    print(
        f"{BackgroundColors.GREEN}Summary:{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}SRT files scanned: {BackgroundColors.CYAN}{total_scanned}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Files with findings: {BackgroundColors.CYAN}{total_affected_files}{Style.RESET_ALL}\n"
        f"{BackgroundColors.GREEN}Detected unwanted blocks: {BackgroundColors.CYAN}{total_detected_blocks}{Style.RESET_ALL}"
    )

    print(
        f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n"
        f"{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n"
        f"{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"
    )

    print(f"{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}")

    (
        atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None
    )


if __name__ == "__main__":
    """
    Standard boilerplate that calls main().

    :return: None
    """

    main()
