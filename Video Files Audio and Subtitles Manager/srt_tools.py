"""
SRT parsing, cleanup, and atomic writing utilities.
"""

import re  # Parse subtitle structure and text cues.
from pathlib import Path  # Write subtitle files.


SUBTITLE_FORMATTING_TAG_PATTERN = re.compile(r"</?(?:i|b|u|font)(?:\s+[^<>]*)?>", re.IGNORECASE)  # Store supported SRT tag pattern.


def read_text_file_lines(file_path: Path) -> list[str]:
    """
    Reads a text file using tolerant UTF-8 decoding.

    :param file_path: Text file path.
    :return: Decoded file lines.
    """

    try:  # Attempt file read.
        return file_path.read_text(encoding="utf-8", errors="replace").splitlines()  # Return decoded lines.
    except OSError:  # Handle unreadable file.
        return []  # Return empty lines.


def strip_html_tags(text: str) -> str:
    """
    Removes supported subtitle formatting tags.

    :param text: Text that may contain formatting tags.
    :return: Text without supported tags.
    """

    return SUBTITLE_FORMATTING_TAG_PATTERN.sub("", text)  # Remove supported tags.


def parse_srt_blocks(lines: list[str]) -> list[tuple[str, str, list[str]]]:
    """
    Parses SRT lines into index, timing, and text-line blocks.

    :param lines: SRT lines to parse.
    :return: Parsed SRT blocks.
    """

    blocks: list[tuple[str, str, list[str]]] = []  # Store parsed blocks.
    block: list[str] = []  # Store current block lines.
    pending_empty_block: tuple[str, str] | None = None  # Store empty timed cue pending recovery.

    for line in lines + [""]:  # Add sentinel line to flush final block.
        stripped = line.strip().lstrip("\ufeff")  # Normalize line and remove BOM.
        if stripped:  # Verify current line has content.
            block.append(stripped)  # Add line to current block.
            continue  # Continue collecting block.

        if not block:  # Verify current block has content.
            continue  # Skip repeated blank lines.

        if len(block) < 2 or not block[0].isdigit() or "-->" not in block[1]:  # Verify block has SRT structure.
            if pending_empty_block:  # Verify recoverable empty cue exists.
                index, timing = pending_empty_block  # Restore pending cue fields.
                blocks.append((index, timing, [text_line.strip() for text_line in block if text_line.strip()]))  # Store recovered block.
                pending_empty_block = None  # Clear pending cue.
                block = []  # Reset current block.
                continue  # Continue parsing.
            if blocks:  # Verify prior block exists for orphan text recovery.
                blocks[-1][2].extend(text_line.strip() for text_line in block if text_line.strip())  # Attach orphan text to prior block.
                block = []  # Reset current block.
                continue  # Continue parsing.
            return []  # Return invalid parse result.

        text_lines = [text_line.strip() for text_line in block[2:] if text_line.strip()]  # Extract dialogue lines.
        if pending_empty_block:  # Verify earlier empty cue needs preservation.
            index, timing = pending_empty_block  # Restore pending cue fields.
            blocks.append((index, timing, []))  # Preserve empty timed cue.
            pending_empty_block = None  # Clear pending cue.
        if not text_lines:  # Verify block has no dialogue.
            pending_empty_block = (block[0], block[1])  # Defer possible empty cue.
            block = []  # Reset current block.
            continue  # Continue parsing.
        blocks.append((block[0], block[1], text_lines))  # Store parsed block.
        block = []  # Reset current block.

    if pending_empty_block:  # Verify trailing empty cue exists.
        index, timing = pending_empty_block  # Restore pending cue fields.
        blocks.append((index, timing, []))  # Preserve trailing empty cue.

    return blocks  # Return parsed blocks.


def serialize_srt_blocks(blocks: list[tuple[str, str, list[str]]]) -> list[str]:
    """
    Serializes parsed SRT blocks back into SRT lines.

    :param blocks: Parsed SRT blocks.
    :return: Serialized SRT lines.
    """

    lines: list[str] = []  # Store serialized lines.
    for new_index, (_index, timing, text_lines) in enumerate(blocks, start=1):  # Iterate parsed blocks.
        lines.extend([str(new_index), timing])  # Add sequence and timing lines.
        lines.extend(text_lines)  # Add subtitle text lines.
        lines.append("")  # Add block separator.
    return lines  # Return serialized lines.


def count_letters(text: str) -> int:
    """
    Counts alphabetic characters in text.

    :param text: Text to inspect.
    :return: Number of alphabetic characters.
    """

    return sum(1 for character in text if character.isalpha())  # Count letters only.


def build_language_detection_sample(lines: list[str], maximum_chars: int) -> str:
    """
    Builds a dialogue-only subtitle language detection sample.

    :param lines: Subtitle lines.
    :param maximum_chars: Maximum sample characters.
    :return: Text sample for language detection.
    """

    sample_lines: list[str] = []  # Store sample dialogue lines.
    seen_lines: dict[str, int] = {}  # Track repeated sample lines.
    sample_length = 0  # Track current sample length.

    for _index, _timing, text_lines in parse_srt_blocks(lines):  # Iterate parsed dialogue blocks.
        for text_line in text_lines:  # Iterate text lines inside block.
            dialogue_line = strip_html_tags(text_line).strip()  # Remove formatting tags.
            dialogue_line = re.sub(r"^[A-Z][A-Z0-9 .'-]{1,30}:\s*", "", dialogue_line).strip()  # Remove speaker prefixes.
            if count_letters(dialogue_line) < 3:  # Verify line has enough letters.
                continue  # Skip tiny or numeric-only line.
            line_key = dialogue_line.lower()  # Normalize repeated-line key.
            if seen_lines.get(line_key, 0) >= 3:  # Avoid repeated dialogue dominating sample.
                continue  # Skip repeated line.
            seen_lines[line_key] = seen_lines.get(line_key, 0) + 1  # Count accepted line.
            sample_lines.append(dialogue_line)  # Add dialogue line.
            sample_length += len(dialogue_line) + 1  # Update sample length.
            if sample_length >= maximum_chars:  # Verify sample reached limit.
                return "\n".join(sample_lines)[:maximum_chars]  # Return bounded sample.

    return "\n".join(sample_lines)  # Return collected sample.


def is_descriptive_cue(text: str) -> bool:
    """
    Determines whether text is only an SDH or descriptive cue.

    :param text: Subtitle text to classify.
    :return: True when text is descriptive-only.
    """

    normalized = strip_html_tags(text).strip()  # Remove supported tags.
    normalized = normalized.strip("[](){}").strip()  # Remove cue wrappers.
    normalized = normalized.strip("?!.- ").strip()  # Remove cue punctuation.
    cue_words = re.findall(r"[a-z]+", normalized.lower())  # Extract cue words.
    descriptive_words = {"applause", "audience", "beeping", "bell", "breathing", "cheering", "chuckles", "coughing", "crying", "door", "footsteps", "gasps", "groaning", "indistinctly", "instrumental", "laugh", "laughing", "laughs", "music", "phone", "playing", "ringing", "sighs", "singing", "speaking", "thunder", "whispering", "whispers"}  # Store conservative cue vocabulary.
    if not cue_words:  # Verify words exist.
        return True  # Treat symbol-only cue as descriptive.
    return all(word in descriptive_words for word in cue_words)  # Return descriptive-only decision.


def clean_subtitle_text_line(text_line: str) -> tuple[str, bool]:
    """
    Removes isolated SDH cues from one subtitle text line.

    :param text_line: Subtitle text line.
    :return: Cleaned text and change flag.
    """

    stripped = text_line.strip()  # Normalize current line.
    tagless = strip_html_tags(stripped).strip()  # Remove supported formatting tags.
    formatting_changed = tagless != stripped  # Track tag removal.
    if ((tagless.startswith("[") and tagless.endswith("]")) or (tagless.startswith("(") and tagless.endswith(")"))) and is_descriptive_cue(tagless):  # Verify whole-line descriptive cue.
        return "", True  # Drop descriptive-only cue.
    cleaned = re.sub(r"(\[[^\]]+\]|\([^)]+\))", lambda match: "" if is_descriptive_cue(match.group(0)) else match.group(0), tagless)  # Remove inline descriptive spans.
    cleaned = " ".join(cleaned.split())  # Normalize spacing.
    return cleaned, formatting_changed or cleaned != stripped  # Return cleaned line and change flag.


def clean_descriptive_subtitle_lines(lines: list[str]) -> tuple[list[str], int, int]:
    """
    Removes descriptive cues from SRT lines without writing files.

    :param lines: Source SRT lines.
    :return: Cleaned lines, removed entry count, and mixed cleaned entry count.
    """

    blocks = parse_srt_blocks(lines)  # Parse source lines.
    if not blocks:  # Verify source can be parsed.
        return lines, 0, 0  # Preserve malformed input.

    cleaned_blocks: list[tuple[str, str, list[str]]] = []  # Store cleaned blocks.
    removed_entry_count = 0  # Count removed entries.
    mixed_cleaned_entry_count = 0  # Count changed retained entries.

    for index, timing, text_lines in blocks:  # Iterate subtitle blocks.
        cleaned_line_results = [clean_subtitle_text_line(text_line) for text_line in text_lines]  # Clean each dialogue line.
        cleaned_text_lines = [text_line for text_line, _changed in cleaned_line_results if text_line]  # Keep non-empty cleaned lines.
        if cleaned_text_lines:  # Verify block still has dialogue.
            cleaned_blocks.append((index, timing, cleaned_text_lines))  # Keep cleaned block.
            if any(changed for _text_line, changed in cleaned_line_results):  # Verify retained block changed.
                mixed_cleaned_entry_count += 1  # Count mixed cleanup.
        else:  # Handle fully removed block.
            removed_entry_count += 1  # Count removed block.

    return serialize_srt_blocks(cleaned_blocks), removed_entry_count, mixed_cleaned_entry_count  # Return cleaned subtitle data.


def count_translatable_characters(lines: list[str]) -> int:
    """
    Counts characters that will be sent to DeepL.

    :param lines: Cleaned SRT lines.
    :return: Total translatable characters.
    """

    return sum(len("\n".join(text_lines)) for _index, _timing, text_lines in parse_srt_blocks(lines))  # Count translated text blocks.


def write_srt_lines_atomic(file_path: Path, lines: list[str]) -> None:
    """
    Writes SRT lines through a same-folder temporary file.

    :param file_path: Destination SRT file.
    :param lines: SRT lines to write.
    :return: None.
    """

    temp_file = file_path.with_suffix(file_path.suffix + ".tmp")  # Build same-directory temporary path.
    temp_file.write_text("\n".join(lines), encoding="utf-8")  # Write complete subtitle content.
    temp_file.replace(file_path)  # Replace destination atomically.
