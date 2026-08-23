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
        - Precision-first evidence-gated credit/promotional-content detection
        - Generic translation/revision labels require validated creator-identity payloads, including multiline role/payload forms
        - Plain Translation-name credits require cross-title repetition instead of edge position alone
        - Names-only neighboring blocks are never inferred as removable from adjacency alone
        - Strict URL/domain validation that rejects numeric thousands, dotted initials,
          sentence typos, and other text that only resembles a domain syntactically
        - Context-aware handling of websites, emails, social handles, and creator identities
        - Endpoint-only creator hints require edge or cross-content corroboration
        - Standalone social-platform names/follow-me dialogue never qualify by themselves
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
    - Extend only high-precision creator/distributor signatures when new verified real-world patterns are found.
    - Keep reviewed-report editing as the final manual allow/deny control before removal.

Dependencies:
    - Python >= 3.10
    - colorama
    - tqdm
    - Local Logger.py from the repository template

Assumptions & Notes:
    - Detection is precision-first: ambiguous dialogue is deliberately excluded even when
      that means genuine but uncorroborated creator credits may be omitted from the report.
    - Adjacency alone never creates a removal target; every reported block needs its own evidence.
    - The detector never edits SRT files.
    - The remover consumes only the exact occurrences still present in reviewed detector
      reports instead of re-detecting, inferring, or expanding targets.
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
from collections import defaultdict  # For directory-level evidence/repetition grouping
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
INPUT_DIRS = [f"E:/Movies/", f"F:/Documentaries/", f"F:/Movies/", f"F:/Series/", f"G:/Animes/", f"G:/Series/"]  # Directories searched recursively for source SRT files
OUTPUT_DIR = Path("./Outputs")  # Directory used for one grouped JSON report per input directory
EDGE_BLOCK_WINDOW = 20  # Number of first/last blocks eligible for conservative edge-context rules
CROSS_CONTENT_REPETITION_MIN = 2  # Minimum distinct titles required before an ambiguous endpoint can be trusted as repeated injected content
REPORT_SCHEMA_VERSION = 4  # Detector report schema version consumed by the exact report-driven remover
DETECTION_POLICY = "high_precision_context_v4"  # Precision-first policy with multiline credit parsing and no adjacency-only inference
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
)  # Known subtitle-distribution sites that are direct creator/distributor evidence

PUBLIC_WEB_TLDS = frozenset(
    (
        "app", "au", "biz", "blog", "br", "ca", "cc", "club", "co", "com", "de",
        "dev", "digital", "email", "es", "film", "films", "fm", "fr", "gg", "info",
        "io", "it", "link", "live", "ly", "me", "media", "movie", "movies", "net",
        "news", "nl", "online", "one", "org", "page", "pro", "pt", "ru", "show",
        "site", "social", "store", "stream", "tech", "to", "torrent", "tv", "uk",
        "us", "video", "watch", "website", "world", "wtf", "xyz",
    )
)  # Conservative TLD allow-list used only for bare domains without http(s):// or www.

GENERIC_SERVICE_DOMAINS = frozenset(
    (
        "facebook.com", "fb.com", "gmail.com", "hotmail.com", "instagram.com",
        "outlook.com", "t.me", "telegram.me", "tiktok.com", "twitter.com",
        "x.com", "youtube.com", "youtu.be",
    )
)  # Common services that may legitimately appear in movie/series dialogue and therefore need creator context

CONTENT_CATEGORY_DIR_NAMES = frozenset(
    ("dual", "dublado", "legendado", "nacional", "english", "portugues", "português")
)  # Movie-library grouping directories ignored when deriving a distinct title/content scope

CREATOR_IDENTITY_HINT_PATTERN = re.compile(
    r"(?:subtitles?|legendas?|legendei|legseries|opensub|addic7ed|insubs?|"
    r"wtfsubs?|creepysubs?|powersubs?|acesubs?|piratebay|"
    r"[a-z0-9]{3,}subs(?:$|[._/@-]))",
    re.IGNORECASE,
)  # Narrow creator/distributor identity tokens; avoids generic words such as "legend" or "substitute"

CREDIT_PAYLOAD_CREATOR_TOKEN_PATTERN = re.compile(
    r"(?:legendei|legseries|opensub|addic7ed|insubs?|wtfsubs?|creepysubs?|powersubs?|acesubs?|piratebay|"
    r"[a-z0-9]{3,}subs(?:$|[._/@-]))",
    re.IGNORECASE,
)  # Creator-like payload token without generic prose words such as legenda/legendas/subtitles

EXPLICIT_URL_PATTERN = re.compile(
    r"(?<![\w@])(?:https?://|www\.)"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?)+"
    r"(?:/[^\s<>]*)?",
    re.IGNORECASE,
)  # Explicit URL marker; unlike the old regex this can never match 27.000, D.C, R.G, etc.

EMAIL_ADDRESS_PATTERN = re.compile(
    r"(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b",
    re.IGNORECASE,
)  # Full email address pattern; domains inside an email are not separately counted as websites

BARE_DOMAIN_PATTERN = re.compile(
    r"(?<![@\w.-])"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,62}[A-Za-z0-9])?)+"
    r"(?:/[^\s<>]*)?",
    re.IGNORECASE,
)  # Bare-domain candidate; accepted only after strict TLD and contextual validation

SOCIAL_HANDLE_PATTERN = re.compile(r"(?<![\w@])@[A-Za-z0-9_][A-Za-z0-9_.-]{1,31}\b")  # Social-network handle pattern

CREDIT_ROLE_LINE_PATTERN = re.compile(
    r"^[\t =:.©*#|_-]*(?P<label>"
    r"(?:equipe[\t ]+de[\t ]+)?(?:legendas?|legendad[oa]s?|tradu(?:ç|c)[aã]o|traduzid[oa]s?|"
    r"revis(?:ã|a)o|revisad[oa]s?|sincroniza(?:ç|c)[aã]o|sincronizad[oa]s?|"
    r"sincronia|adapta(?:ç|c)[aã]o|subrip|re-?syncs?|ressync|resyncs?|sync|"
    r"bluray[\t ]+sync|dvdrip[\t ]+sync)"
    r"(?:[\t ]+(?:inicial|final|portugu[eê]s(?:[\t ]+brasil)?|ingl[eê]s))?"
    r")"
    r"(?:(?P<colon_separator>[\t ]*:[\t ]*)(?:\n[\t ]*)?|"
    r"(?P<word_separator>[\t ]+(?:por|by|de)[\t ]+))"
    r"(?P<payload>[^\n]{1,180})$",
    re.IGNORECASE | re.MULTILINE,
)  # Consumes an optional line break after ':' so multiline role/payload credits are validated correctly.


REVIEW_STUDIO_LINE_PATTERN = re.compile(
    r"^[\s\-=:.©*#|_]*(?P<label>revis(?:ã|a)o\s+de\s+legendas?)\s+(?P<payload>[^\n]{2,120})$",
    re.IGNORECASE | re.MULTILINE,
)  # Common studio-credit form without colon, e.g. "Revisão de Legendas BRAVO STUDIOS"

MULTI_ROLE_CREDIT_PATTERN = re.compile(
    r"^[\s\-=:.©*#|_]*(?:"
    r"(?:adapta(?:ç|c)[aã]o|revis(?:ã|a)o|sincronia|sincroniza(?:ç|c)[aã]o|"
    r"tradu(?:ç|c)[aã]o|legendas?)\s*[|/&+\-]\s*"
    r"){1,4}"
    r"(?:adapta(?:ç|c)[aã]o|revis(?:ã|a)o|sincronia|sincroniza(?:ç|c)[aã]o|"
    r"tradu(?:ç|c)[aã]o|legendas?)\s*:(?=\s*\S)",
    re.IGNORECASE | re.MULTILINE,
)  # Explicit multi-role production header such as "ADAPTAÇÃO | REVISÃO | SINCRONIA:"

UNAMBIGUOUS_CREDIT_PATTERNS = (
    re.compile(r"\b(?:sync|resync|timing|translation|translated)\s+(?:and\s+corrected\s+)?by(?=\s+\S)", re.IGNORECASE),
    re.compile(r"\bsincronizad[oa]\s+e\s+corrigid[oa]\s+por(?=\s+\S)", re.IGNORECASE),
    re.compile(r"\bripad[oa]s?\s+e\s+sincronizad[oa]s?\s+por\s*:(?=\s*\S)", re.IGNORECASE),
    re.compile(r"\btraduzid[oa]\s+do\s+subpack\s+por(?=\s+\S)", re.IGNORECASE),
    re.compile(r"\btraduzid[oa]\s+e\s+revisad[oa]\s+por(?=\s+\S)", re.IGNORECASE),
    re.compile(r"\bre-?sync\b.{0,30}\brevis(?:ã|a)o\b\s*:(?=\s*\S)", re.IGNORECASE),
    re.compile(r"\bressync\b.{0,30}\brevis(?:ã|a)o\b\s*:(?=\s*\S)", re.IGNORECASE),
)  # Syntax that is intrinsically subtitle-production-specific and does not depend on a generic label payload

CREDIT_PAYLOAD_CONNECTORS = frozenset(("a", "as", "da", "das", "de", "do", "dos", "e", "o", "os"))
CREDIT_PAYLOAD_SUFFIXES = frozenset(("dds", "deluxe", "studios", "studio", "team"))
CREDIT_PAYLOAD_DIALOGUE_STARTERS = frozenset((
    "adeus", "agora", "ainda", "amanhã", "assim", "como", "diga", "doida", "ela", "ele",
    "eu", "há", "isso", "isto", "minha", "meu", "não", "nos", "nós", "pênis", "por",
    "porque", "quando", "que", "se", "sim", "sua", "seu", "todo", "tudo", "você", "vocês",
))  # High-value dialogue/content starters observed in real subtitles; these make a generic role payload unsafe

SUBTITLE_PROMOTIONAL_PATTERNS = (
    re.compile(r"\blegende\s+conosco\b", re.IGNORECASE),
    re.compile(r"\b(?:quer(?:e|em)?|venha)\s+legendar\s+(?:conosco|com\s+a\s+gente)\b", re.IGNORECASE),
    re.compile(r"\bsugest(?:ão|ao|ões|oes)\b.{0,100}\b(?:legendar|legendad[oa]s?|legendas?)\b", re.IGNORECASE),
    re.compile(r"\b(?:download|baixe)\b.{0,100}\b(?:legenda|legendas|subtitle|subtitles)\b", re.IGNORECASE),
    re.compile(r"\blegendas?\s+(?:liberad[oa]s?|dispon[ií]veis?)\b", re.IGNORECASE),
    re.compile(
        r"(?:\bfilmes?\b.{0,100}\bs[eé]ries?\b|\bs[eé]ries?\b.{0,100}\bfilmes?\b)"
        r".{0,100}\b(?:torrent|download)\b",
        re.IGNORECASE,
    ),
)  # Subtitle/distributor-specific promotional language; generic platform mentions are intentionally absent

FOLLOW_CONTACT_PATTERN = re.compile(
    r"\b(?:sigam?-me|siga-nos|sigam-nos|follow\s+me|follow\s+us|curta-nos|"
    r"curta\s+nossa\s+p[aá]gina|acesse\s+nossa\s+p[aá]gina|visite\s+nosso\s+site|"
    r"fale\s+conosco)\b",
    re.IGNORECASE,
)  # Weak call-to-action that requires an independently trusted creator endpoint

SOCIAL_PLATFORM_PATTERN = re.compile(
    r"\b(?:twitter|instagram|facebook|tiktok|telegram|youtube)\b",
    re.IGNORECASE,
)  # Weak platform reference; never sufficient on its own

SUBTITLE_CONTEXT_PATTERN = re.compile(
    r"\b(?:legenda|legendas|legendad[oa]s?|subtitle|subtitles|subs|traduzid[oa]s?|"
    r"tradu(?:ç|c)[aã]o|sincroniza(?:ç|c)[aã]o|sincronia|resync|subrip)\b",
    re.IGNORECASE,
)  # Weak creator-context metadata retained for report transparency but never sufficient alone

HTML_TAG_PATTERN = re.compile(r"<[^>]+>")  # Generic HTML-like formatting tags ignored for detection analysis
ASS_OVERRIDE_TAG_PATTERN = re.compile(r"\{\\[^{}\r\n]+\}")  # ASS/SSA positioning/style tags ignored for detection analysis


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

    return ASS_OVERRIDE_TAG_PATTERN.sub("", HTML_TAG_PATTERN.sub("", value))  # Ignore formatting/positioning tags without altering stored source text


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


def normalize_endpoint_identity(value: str) -> str:
    """
    Normalize a URL/domain/email-like endpoint for exact contextual comparison.

    :param value: Endpoint text from one signal.
    :return: Lowercase endpoint without scheme/www/trailing punctuation.
    """

    normalized = value.strip().strip(".,!?;:()[]{}<>\"'")
    normalized = re.sub(r"^https?://", "", normalized, flags=re.IGNORECASE)

    if normalized.casefold().startswith("www."):
        normalized = normalized[4:]

    return normalized.casefold().rstrip(".")


def endpoint_host(value: str) -> str:
    """
    Extract a normalized host from a URL, bare domain, or email address.

    :param value: Endpoint text.
    :return: Lowercase host without scheme/www/path.
    """

    normalized = normalize_endpoint_identity(value)

    if "@" in normalized:
        normalized = normalized.rsplit("@", 1)[1]

    return normalized.split("/", 1)[0].rstrip(".")


def is_valid_web_host(host: str, require_known_tld: bool) -> bool:
    """
    Validate a host while preventing numeric/abbreviation false domains.

    :param host: Normalized host.
    :param require_known_tld: Require final suffix to be in PUBLIC_WEB_TLDS.
    :return: True only for a syntactically credible hostname.
    """

    labels = host.split(".")

    if len(labels) < 2:
        return False

    if any(
        not label
        or len(label) > 63
        or label.startswith("-")
        or label.endswith("-")
        or re.fullmatch(r"[A-Za-z0-9-]+", label) is None
        for label in labels
    ):
        return False

    final_label = labels[-1].casefold()

    if not final_label.isalpha() or len(final_label) < 2 or len(final_label) > 24:
        return False  # Reject 27.000, 1.600km-style pseudo-domains and D.C/R.G initials

    if require_known_tld and final_label not in PUBLIC_WEB_TLDS:
        return False  # Reject sentence typos such as "for.te" and "Espere.Segure"

    return True


def ranges_overlap(first: tuple[int, int], second: tuple[int, int]) -> bool:
    """
    Return whether two half-open string spans overlap.

    :param first: First start/end span.
    :param second: Second start/end span.
    :return: True when spans overlap.
    """

    return first[0] < second[1] and second[0] < first[1]


def build_content_scope_key(filepath: Path, input_dir: Path) -> str:
    """
    Build a stable title/series scope used to distinguish cross-title injected text.

    Movie roots may contain language folders such as Dual/Legendado, which are
    skipped so two different movies count as different scopes. Series roots use
    their top-level series directory.

    :param filepath: Current subtitle file.
    :param input_dir: Active configured input root.
    :return: Casefolded content-title scope key.
    """

    try:
        relative_parts = filepath.resolve().relative_to(input_dir.resolve()).parts[:-1]
    except ValueError:
        relative_parts = filepath.parts[:-1]

    if not relative_parts:
        return filepath.parent.as_posix().casefold()

    first_part = relative_parts[0]

    if first_part.casefold() in CONTENT_CATEGORY_DIR_NAMES and len(relative_parts) >= 2:
        return relative_parts[1].casefold()

    return first_part.casefold()


def normalize_credit_payload(value: str) -> str:
    """Normalize a role-label payload for conservative creator-identity checks.

    :param value: Text following a subtitle-production role label.
    :return: Compact payload with surrounding decorative punctuation removed.
    """

    compact = normalize_display_text(strip_formatting_tags(value)).strip()
    return compact.strip(" \t-=:;|_*#©[]{}()<>.")


def credit_payload_identity_tokens(value: str) -> list[str]:
    """Return whitespace-delimited identity-like payload tokens.

    :param value: Normalized credit payload.
    :return: Tokens after harmless list punctuation is removed.
    """

    cleaned = re.sub(r"[|,&+/]+", " ", value)
    cleaned = re.sub(r"[\[\]{}()=*:;]", " ", cleaned)
    return [token.strip(".\"'!?-") for token in cleaned.split() if token.strip(".\"'!?-")]


def is_identity_like_credit_token(token: str) -> bool:
    """Return whether one token plausibly identifies a contributor rather than prose.

    :param token: Candidate contributor token.
    :return: True only for conservative name/alias shapes.
    """

    stripped = token.strip(".\"'!?-")

    if not stripped:
        return False

    folded = stripped.casefold()

    if folded in CREDIT_PAYLOAD_CONNECTORS or folded in CREDIT_PAYLOAD_SUFFIXES:
        return True

    if "@" in stripped or "_" in stripped or any(character.isdigit() for character in stripped):
        return True

    letters = "".join(character for character in stripped if character.isalpha())

    if not letters:
        return False

    if letters.isupper() and len(letters) >= 2:
        return True

    if stripped[0].isupper():
        return True

    # Mixed-case aliases such as guiLOG/brunoivens are accepted only when their
    # casing itself carries identity evidence. Plain lowercase words remain prose.
    return any(character.isupper() for character in stripped[1:])


def classify_credit_payload(payload: str) -> str | None:
    """Classify a generic workflow-label payload without guessing from prose.

    Returns ``structured`` for independently creator-specific payloads, ``name``
    for plausible contributor names that still require edge/repetition context,
    or ``None`` for ambiguous/ordinary subtitle content.

    :param payload: Text following a generic translation/revision/etc. label.
    :return: structured, name, or None.
    """

    compact = normalize_credit_payload(payload)

    if not compact or len(compact) > 140:
        return None

    if compact[0] in '"“”‘’' or "?" in compact or "!" in compact:
        return None

    first_word_match = re.match(r"[A-Za-zÀ-ÖØ-öø-ÿ]+", compact)
    first_word = first_word_match.group(0).casefold() if first_word_match else ""

    if first_word in CREDIT_PAYLOAD_DIALOGUE_STARTERS:
        return None

    lowered = compact.casefold()

    if any(site.casefold() in lowered for site in KNOWN_SUBTITLE_SITES):
        return "structured"

    if CREDIT_PAYLOAD_CREATOR_TOKEN_PATTERN.search(compact):
        return "structured"

    if EMAIL_ADDRESS_PATTERN.search(compact) or EXPLICIT_URL_PATTERN.search(compact):
        return "structured"

    if SOCIAL_HANDLE_PATTERN.search(compact) or re.search(r"\b[^\s@]+@[^\s@]+\b", compact):
        return "structured"

    if re.search(r"(?:==|::)", payload):
        tokens = credit_payload_identity_tokens(compact)
        if tokens and all(is_identity_like_credit_token(token) for token in tokens):
            return "structured"

    if re.search(
        r"\b(?:revis(?:ã|a)o|sincronia|sincroniza(?:ç|c)[aã]o|resync|sync|adapta(?:ç|c)[aã]o)\s*:",
        compact,
        re.IGNORECASE,
    ):
        return "structured"

    tokens = credit_payload_identity_tokens(compact)

    if not tokens:
        return None

    significant_tokens = [
        token for token in tokens
        if token.casefold() not in CREDIT_PAYLOAD_CONNECTORS and token.casefold() not in CREDIT_PAYLOAD_SUFFIXES
    ]

    if len(significant_tokens) < 2 or len(significant_tokens) > 8:
        return None  # One-word payloads are too ambiguous: "Tradução: NAMORADOS", "Tradução: não", etc.

    if not all(is_identity_like_credit_token(token) for token in tokens):
        return None

    # Contributor lists are still names-only evidence. Even conspicuous separators
    # do not make them removable without edge/repetition corroboration because
    # translated on-screen content can itself contain lists.
    return "name"


def extract_verified_credit_signals(text: str) -> list[tuple[str, str, int]]:
    """Extract role-label credits only after validating their right-hand payload.

    Multiline role/payload forms are handled explicitly. A generic workflow word
    never becomes a credit merely because it is followed by ':' or 'de'; the
    payload itself must look like a contributor identity. Two independently
    validated role lines inside one block are treated as a structured credit
    cluster.

    :param text: Plain subtitle block text.
    :return: (category, matched string, weight) tuples.
    """

    verified = []
    verified_role_matches: list[tuple[re.Match[str], str]] = []

    for match in CREDIT_ROLE_LINE_PATTERN.finditer(text):
        payload_kind = classify_credit_payload(match.group("payload"))

        if payload_kind is None:
            continue

        verified_role_matches.append((match, payload_kind))

        if payload_kind == "structured":
            category = "subtitle_credit_structured"
            weight = 95
        else:
            label = match.group("label").casefold()
            is_translation_label = re.search(r"tradu(?:ç|c)[aã]o|traduzid[oa]", label, re.IGNORECASE) is not None
            category = "subtitle_translation_credit_name" if is_translation_label else "subtitle_credit_name"
            weight = 65 if is_translation_label else 70

        verified.append((category, match.group(0), weight))

    if len(verified_role_matches) >= 2:
        # Multiple validated production-role lines in the same subtitle block are
        # independently strong credit structure. Invalid/ordinary payloads never
        # contribute to this count, so e.g. 'TRADUÇÃO: NAMORADOS' remains excluded.
        verified.append(("subtitle_credit_structured", normalize_display_text(text), 95))

    for match in REVIEW_STUDIO_LINE_PATTERN.finditer(text):
        payload = normalize_credit_payload(match.group("payload"))
        payload_tokens = credit_payload_identity_tokens(payload)

        if len(payload_tokens) >= 2 and all(is_identity_like_credit_token(token) for token in payload_tokens):
            verified.append(("subtitle_credit_structured", match.group(0), 95))

    for match in MULTI_ROLE_CREDIT_PATTERN.finditer(text):
        verified.append(("subtitle_credit_structured", match.group(0), 95))

    for pattern in UNAMBIGUOUS_CREDIT_PATTERNS:
        for match in pattern.finditer(text):
            verified.append(("subtitle_credit_structured", match.group(0), 95))

    return verified


def extract_detection_signals(text: str) -> list[dict[str, object]]:
    """
    Extract exact high-precision creator/distributor evidence from subtitle text.

    Numeric values, initials/abbreviations, ordinary sentence dots, platform-name
    mentions, and generic "follow me" dialogue are intentionally not strong
    creator evidence.

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
            add_signal("known_subtitle_site", site, 100)

    occupied_endpoint_spans = []

    for match in EMAIL_ADDRESS_PATTERN.finditer(text):
        email_value = match.group(0)
        host = endpoint_host(email_value)

        if is_valid_web_host(host, require_known_tld=False):
            occupied_endpoint_spans.append(match.span())
            add_signal("email_address", email_value, 30)

    for match in EXPLICIT_URL_PATTERN.finditer(text):
        url_value = match.group(0)
        host = endpoint_host(url_value)

        if is_valid_web_host(host, require_known_tld=False):
            occupied_endpoint_spans.append(match.span())
            add_signal("explicit_url", url_value, 35)

    for match in BARE_DOMAIN_PATTERN.finditer(text):
        if any(ranges_overlap(match.span(), occupied_span) for occupied_span in occupied_endpoint_spans):
            continue  # Do not misreport the domain inside an already captured email/explicit URL

        domain_value = match.group(0)
        host = endpoint_host(domain_value)

        if is_valid_web_host(host, require_known_tld=True):
            add_signal("bare_domain", domain_value, 20)

    for match in SOCIAL_HANDLE_PATTERN.finditer(text):
        add_signal("social_handle", match.group(0), 20)

    for category, matched_string, weight in extract_verified_credit_signals(text):
        add_signal(category, matched_string, weight)


    for pattern in SUBTITLE_PROMOTIONAL_PATTERNS:
        for match in pattern.finditer(text):
            add_signal("subtitle_promotion_phrase", match.group(0), 90)

    for match in FOLLOW_CONTACT_PATTERN.finditer(text):
        add_signal("follow_contact_call", match.group(0), 10)

    for match in SOCIAL_PLATFORM_PATTERN.finditer(text):
        add_signal("social_platform_reference", match.group(0), 5)

    for match in SUBTITLE_CONTEXT_PATTERN.finditer(text):
        add_signal("subtitle_creation_context", match.group(0), 5)

    return signals


def signal_categories(signals: list[dict[str, object]]) -> set[str]:
    """
    Return unique signal category names.

    :param signals: Candidate signal dictionaries.
    :return: Category-name set.
    """

    return {str(signal["category"]) for signal in signals}


def candidate_has_intrinsic_strong_evidence(candidate: dict[str, object]) -> bool:
    """
    Identify candidates that are independently creator/distributor-specific.

    :param candidate: Internal detection candidate.
    :return: True when no recurrence/identity inference is needed.
    """

    categories = signal_categories(candidate["matched_strings"])

    if categories & {"subtitle_credit_structured", "subtitle_promotion_phrase"}:
        return True

    if "known_subtitle_site" in categories and bool(candidate.get("_edge_block")):
        return True  # A known subtitle-distribution domain is direct only at an SRT edge

    return False


def creator_identity_hint(value: str) -> bool:
    """
    Identify an endpoint/handle whose own text strongly suggests subtitle distribution.

    :param value: URL/domain/email/handle identity.
    :return: True when it contains a creator/distributor-specific token.
    """

    return CREATOR_IDENTITY_HINT_PATTERN.search(value) is not None


def signal_identity_keys(signals: list[dict[str, object]]) -> set[tuple[str, str]]:
    """
    Extract exact reusable endpoint/contact identities from signals.

    :param signals: Candidate signal dictionaries.
    :return: Identity tuples used by directory-level contextual validation.
    """

    identities = set()

    for signal in signals:
        category = str(signal["category"])
        value = str(signal["string"])

        if category == "email_address":
            normalized_email = normalize_endpoint_identity(value)
            identities.add(("email", normalized_email))

            host = endpoint_host(value)
            if host and host not in GENERIC_SERVICE_DOMAINS:
                identities.add(("domain", host))

            local_part = normalized_email.split("@", 1)[0]
            if len(local_part) >= 4:
                identities.add(("contact_token", local_part))

        elif category in {"explicit_url", "bare_domain"}:
            normalized_endpoint = normalize_endpoint_identity(value)
            host = endpoint_host(value)

            identities.add(("endpoint", normalized_endpoint))

            if host:
                identities.add(("domain", host))

            if "/" in normalized_endpoint:
                for token in re.split(r"[^A-Za-z0-9_.-]+", normalized_endpoint.split("/", 1)[1]):
                    normalized_token = token.casefold().strip("._-")
                    if len(normalized_token) >= 4:
                        identities.add(("contact_token", normalized_token))

        elif category == "social_handle":
            normalized_handle = value.casefold()
            identities.add(("handle", normalized_handle))
            identities.add(("contact_token", normalized_handle.lstrip("@")))

    return identities


def candidate_endpoint_categories(candidate: dict[str, object]) -> set[str]:
    """
    Return endpoint/contact categories present in a candidate.

    :param candidate: Internal detection candidate.
    :return: Endpoint category set.
    """

    return signal_categories(candidate["matched_strings"]) & {
        "explicit_url",
        "bare_domain",
        "email_address",
        "social_handle",
    }


def candidate_has_creator_identity_hint(candidate: dict[str, object]) -> bool:
    """
    Determine whether any endpoint/contact identity is inherently creator-specific.

    :param candidate: Internal detection candidate.
    :return: True when creator-specific identity text is present.
    """

    for identity_type, identity_value in signal_identity_keys(candidate["matched_strings"]):
        if identity_type in {"email", "endpoint", "domain", "handle", "contact_token"} and creator_identity_hint(identity_value):
            return True

    return False


def calculate_candidate_score(candidate: dict[str, object], decision_reasons: list[str]) -> int:
    """
    Calculate an audit score after the candidate has passed precision gates.

    :param candidate: Accepted candidate.
    :param decision_reasons: High-precision reasons that authorized reporting.
    :return: Integer evidence score capped at 100.
    """

    base_score = sum(int(signal["weight"]) for signal in candidate["matched_strings"])

    if bool(candidate.get("_edge_block")):
        base_score += 5
    if "trusted_creator_identity" in decision_reasons:
        base_score += 20
    if "cross_content_repetition" in decision_reasons:
        base_score += 15
    if "edge_credit_identity" in decision_reasons:
        base_score += 15
    if "repeated_credit_identity" in decision_reasons:
        base_score += 20

    return min(100, base_score)


def classify_confidence(decision_reasons: list[str]) -> str:
    """
    Convert accepted decision reasons into report confidence.

    :param decision_reasons: High-precision acceptance reasons.
    :return: high or medium.
    """

    high_reasons = {
        "direct_creator_evidence",
        "creator_identity_hint",
        "trusted_creator_identity",
        "edge_credit_identity",
        "repeated_credit_identity",
    }

    return "high" if high_reasons.intersection(decision_reasons) else "medium"


def build_detection_candidate(
    filepath: Path,
    input_dir: Path,
    current_file_sha256: str,
    block: dict[str, object],
    total_blocks: int,
) -> dict[str, object] | None:
    """
    Build an internal candidate containing raw evidence but make no removal decision yet.

    :param filepath: Source SRT path.
    :param input_dir: Active configured root.
    :param current_file_sha256: SHA-256 of source file.
    :param block: Parsed block.
    :param total_blocks: Number of parsed blocks.
    :return: Internal candidate or None when no relevant evidence exists.
    """

    text = str(block["text"])
    plain_text = strip_formatting_tags(text)
    display_string = normalize_display_text(plain_text)

    if not display_string:
        return None

    signals = extract_detection_signals(plain_text)

    if not signals:
        return None

    block_number = int(block["block_number"])
    edge_block = (
        block_number <= EDGE_BLOCK_WINDOW
        or block_number > max(0, total_blocks - EDGE_BLOCK_WINDOW)
    )

    return {
        "file_path": filepath.resolve().as_posix(),
        "file_sha256": current_file_sha256,
        "block_sha256": block_sha256(int(block["original_index"]), str(block["timestamp"]), text),
        "block_number": block_number,
        "original_index": int(block["original_index"]),
        "timestamp": str(block["timestamp"]),
        "text": text,
        "plain_text": display_string,
        "matched_strings": signals,
        "_edge_block": edge_block,
        "_content_scope": build_content_scope_key(filepath, input_dir),
    }


def detect_file_candidates(filepath: Path, input_dir: Path) -> list[dict[str, object]]:
    """
    Extract high-precision evidence candidates from one SRT without finalizing weak endpoints.

    :param filepath: Source SRT path.
    :param input_dir: Active configured root.
    :return: Candidate occurrence dictionaries.
    """

    content = read_srt_file(filepath)
    blocks = parse_srt_blocks(content)
    current_file_sha256 = file_sha256(filepath)
    total_blocks = len(blocks)
    candidates = []

    for block in blocks:
        candidate = build_detection_candidate(
            filepath,
            input_dir,
            current_file_sha256,
            block,
            total_blocks,
        )

        if candidate is not None:
            candidates.append(candidate)

    # No adjacency-only inference is permitted. A neighboring block must carry
    # its own independently extracted evidence to ever become a report target.

    return candidates


def build_directory_detection_context(
    candidates: list[dict[str, object]],
) -> dict[str, object]:
    """
    Build directory-level identity/repetition context before weak endpoints are accepted.

    :param candidates: Preliminary candidates from every SRT in one configured root.
    :return: Context dictionaries/sets used by final classification.
    """

    display_scopes: dict[str, set[str]] = defaultdict(set)
    identity_scopes: dict[tuple[str, str], set[str]] = defaultdict(set)
    trusted_identities = set()

    for candidate in candidates:
        content_scope = str(candidate["_content_scope"])
        display_key = normalize_group_key(str(candidate["plain_text"]))
        display_scopes[display_key].add(content_scope)
        identities = signal_identity_keys(candidate["matched_strings"])

        for identity in identities:
            identity_scopes[identity].add(content_scope)

        if candidate_has_intrinsic_strong_evidence(candidate):
            for identity_type, identity_value in identities:
                if identity_type == "domain" and identity_value in GENERIC_SERVICE_DOMAINS:
                    continue  # Never globally trust gmail/facebook/twitter merely because one strong block used them
                trusted_identities.add((identity_type, identity_value))

    return {
        "display_scopes": display_scopes,
        "identity_scopes": identity_scopes,
        "trusted_identities": trusted_identities,
    }


def classify_detection_candidate(
    candidate: dict[str, object],
    context: dict[str, object],
) -> tuple[bool, list[str]]:
    """
    Apply precision gates to one candidate.

    :param candidate: Preliminary candidate.
    :param context: Directory-level trust/repetition context.
    :return: Acceptance boolean and exact decision reasons.
    """

    reasons = []

    if candidate_has_intrinsic_strong_evidence(candidate):
        reasons.append("direct_creator_evidence")
        return True, reasons

    categories = signal_categories(candidate["matched_strings"])

    name_credit_categories = {"subtitle_credit_name", "subtitle_translation_credit_name"}

    if categories.intersection(name_credit_categories):
        # Plain "Tradução: <name>" is not accepted from edge position alone because
        # subtitles also use Tradução: to label legitimate translated on-screen text.
        if "subtitle_credit_name" in categories and bool(candidate["_edge_block"]):
            return True, ["edge_credit_identity"]

        display_key = normalize_group_key(str(candidate["plain_text"]))
        display_scopes = context["display_scopes"]

        if len(display_scopes.get(display_key, set())) >= CROSS_CONTENT_REPETITION_MIN:
            return True, ["repeated_credit_identity"]

    endpoint_categories = candidate_endpoint_categories(candidate)

    if not endpoint_categories:
        return False, []  # Weak platform/context/follow-call evidence can never qualify alone

    identities = signal_identity_keys(candidate["matched_strings"])

    if candidate_has_creator_identity_hint(candidate):
        if bool(candidate["_edge_block"]):
            return True, ["creator_identity_hint"]

        identity_scopes = context["identity_scopes"]
        if any(
            len(identity_scopes.get(identity, set())) >= CROSS_CONTENT_REPETITION_MIN
            for identity in identities
            if identity[0] in {"endpoint", "email", "handle", "domain"}
        ):
            return True, ["creator_identity_hint"]

    trusted_identities = context["trusted_identities"]

    if any(identity in trusted_identities for identity in identities):
        return True, ["trusted_creator_identity"]

    # Also allow a URL path/contact token to inherit trust from a creator handle/email
    # observed in a direct creator block elsewhere in the same input root.
    candidate_contact_tokens = {
        identity
        for identity in identities
        if identity[0] == "contact_token"
    }

    if candidate_contact_tokens.intersection(trusted_identities):
        return True, ["trusted_creator_identity"]

    handle_count = sum(
        1 for signal in candidate["matched_strings"] if signal["category"] == "social_handle"
    )

    if bool(candidate["_edge_block"]) and handle_count >= 2:
        return True, ["edge_multiple_creator_handles"]

    display_key = normalize_group_key(str(candidate["plain_text"]))
    display_scopes = context["display_scopes"]

    if len(display_scopes.get(display_key, set())) >= CROSS_CONTENT_REPETITION_MIN:
        non_generic_endpoint = False

        for identity_type, identity_value in identities:
            if identity_type == "domain" and identity_value in GENERIC_SERVICE_DOMAINS:
                continue
            if identity_type in {"endpoint", "email", "handle", "domain"}:
                non_generic_endpoint = True
                break

        if non_generic_endpoint:
            return True, ["cross_content_repetition"]

    identity_scopes = context["identity_scopes"]

    if bool(candidate["_edge_block"]):
        for identity_type, identity_value in identities:
            if identity_type == "domain" and identity_value in GENERIC_SERVICE_DOMAINS:
                continue
            if identity_type not in {"endpoint", "email", "handle", "domain"}:
                continue
            if len(identity_scopes.get((identity_type, identity_value), set())) >= CROSS_CONTENT_REPETITION_MIN:
                return True, ["cross_content_repetition"]

    # A generic follow/contact call is intentionally rejected here unless the
    # endpoint itself was creator-specific/trusted above. "Siga-me" dialogue,
    # "follow me on Instagram", etc. remain untouched.
    if "follow_contact_call" in categories:
        return False, []

    return False, []


def finalize_detection_candidates(
    candidates: list[dict[str, object]],
) -> list[dict[str, object]]:
    """
    Convert preliminary candidates into reportable high-precision occurrences.

    :param candidates: Candidates collected across one configured input directory.
    :return: Accepted occurrence dictionaries with internal context removed.
    """

    context = build_directory_detection_context(candidates)
    accepted_occurrences = []

    for candidate in candidates:
        accepted, decision_reasons = classify_detection_candidate(candidate, context)

        if not accepted:
            continue

        occurrence = {
            key: value
            for key, value in candidate.items()
            if not key.startswith("_")
        }
        occurrence["score"] = calculate_candidate_score(candidate, decision_reasons)
        occurrence["confidence"] = classify_confidence(decision_reasons)
        occurrence["decision_reasons"] = decision_reasons
        accepted_occurrences.append(occurrence)

    return accepted_occurrences


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
        "schema_version": REPORT_SCHEMA_VERSION,
        "detection_policy": DETECTION_POLICY,
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
        directory_candidates = []
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
                    file_candidates = detect_file_candidates(srt_file, input_dir)
                    directory_candidates.extend(file_candidates)
                except Exception as exc:
                    tqdm.write(
                        f"{BackgroundColors.RED}Failed: {BackgroundColors.CYAN}{srt_file.resolve().as_posix()}{BackgroundColors.RED} - {str(exc).replace(chr(92), '/')}{Style.RESET_ALL}",
                        file=PROGRESS_OUTPUT,
                    )

        directory_occurrences = finalize_detection_candidates(directory_candidates)  # Apply directory-wide trust/repetition gates only after scanning every file
        affected_files = {occurrence["file_path"] for occurrence in directory_occurrences}  # Count only accepted report findings
        print(
            f"{BackgroundColors.GREEN}Candidates extracted: {BackgroundColors.CYAN}{len(directory_candidates)}"
            f"{BackgroundColors.GREEN} | Accepted findings: {BackgroundColors.CYAN}{len(directory_occurrences)}{Style.RESET_ALL}"
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
