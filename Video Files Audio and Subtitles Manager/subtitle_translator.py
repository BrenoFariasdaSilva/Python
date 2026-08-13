"""
DeepL SRT translation.
"""

import json  # Parse DeepL key configuration.
import os  # Read environment variables.
from pathlib import Path  # Represent subtitle paths.
import deepl  # Use DeepL API client.
from dotenv import load_dotenv  # Load .env file.
from config import AppConfig  # Read translation settings.
from console import BackgroundColors, STYLE_RESET, log_debug, log_warning  # Report translation events.
from srt_tools import clean_descriptive_subtitle_lines, parse_srt_blocks, read_text_file_lines, write_srt_lines_atomic  # Reuse SRT behavior.


class SubtitleTranslator:
    """
    Owns DeepL credentials, clients, and SRT translation.
    """

    def __init__(self, config: AppConfig) -> None:
        """
        Initializes subtitle translation.

        :param config: Application configuration.
        :return: None.
        """

        self.config = config  # Store application configuration.
        self.api_keys: dict[str, str] = {}  # Store loaded DeepL account keys.
        self.translators: dict[str, deepl.DeepLClient] = {}  # Store DeepL clients by account name.

    def parse_deepl_api_keys(self, raw_value: str) -> dict[str, str]:
        """
        Parses named DeepL API keys from a JSON object string.

        :param raw_value: Environment variable value containing account names and keys.
        :return: Ordered mapping of DeepL account names to API keys.
        """

        try:  # Parse JSON mapping.
            api_keys = json.loads(raw_value)  # Parse account key mapping.
        except json.JSONDecodeError as error:  # Handle invalid JSON.
            raise ValueError(f"DEEPL_API_KEYS must be valid JSON: {error.msg}") from None  # Raise configuration error.
        if not isinstance(api_keys, dict):  # Verify JSON object shape.
            raise ValueError("DEEPL_API_KEYS must be a JSON object mapping account names to API keys")  # Raise shape error.
        parsed_keys: dict[str, str] = {}  # Store validated key mapping.
        for account_name, api_key in api_keys.items():  # Validate configured accounts.
            if not isinstance(account_name, str) or not account_name.strip():  # Verify account name text.
                raise ValueError("DEEPL_API_KEYS account names must be non-empty strings")  # Raise account name error.
            if not isinstance(api_key, str) or not api_key.strip():  # Verify account key text.
                raise ValueError(f"DEEPL_API_KEYS account '{account_name}' must have a non-empty string API key")  # Raise account key error.
            parsed_keys[account_name] = api_key  # Store validated account key.
        if not parsed_keys:  # Verify at least one account exists.
            raise ValueError("DEEPL_API_KEYS must contain at least one account")  # Raise empty mapping error.
        return parsed_keys  # Return validated mapping.

    def load_deepl_api_keys(self) -> bool:
        """
        Loads DeepL API keys from environment and optional .env.

        :return: True when keys were loaded.
        """

        load_dotenv(self.config.script_dir / ".env")  # Load project .env file.
        raw_api_keys = os.getenv("DEEPL_API_KEYS")  # Read DeepL API keys.
        if not raw_api_keys:  # Verify keys exist.
            log_warning("DEEPL_API_KEYS not configured; PT-BR DeepL translation skipped.")  # Report missing keys.
            return False  # Return no keys.
        try:  # Validate configured keys.
            self.api_keys = self.parse_deepl_api_keys(raw_api_keys)  # Store validated keys.
        except ValueError as error:  # Handle configuration error.
            log_warning(f"DeepL configuration error: {error}")  # Report configuration error.
            return False  # Return no keys.
        return True  # Return keys loaded.

    def get_remaining_characters(self, translator: deepl.DeepLClient) -> int | None:
        """
        Reads remaining DeepL account characters.

        :param translator: DeepL translator client.
        :return: Remaining characters or None.
        """

        usage = translator.get_usage()  # Read DeepL usage.
        if usage.character.valid:  # Verify character usage data is available.
            return usage.character.limit - usage.character.count  # Return remaining characters.
        return None  # Return unknown quota.

    def create_deepl_client(self, account_name: str, api_key: str) -> deepl.DeepLClient:
        """
        Creates a DeepL client for a named account.

        :param account_name: DeepL account name for logging.
        :param api_key: DeepL API key.
        :return: DeepL client instance.
        """

        log_debug(f"Using DeepL account: {account_name}", self.config.verbose)  # Log account name only.
        return deepl.DeepLClient(auth_key=api_key)  # Create DeepL client without exposing key.

    def translate_text_block(self, text_block: str, account_items: list[tuple[str, str]], active_account_index: int) -> tuple[list[str], int]:
        """
        Translates a text block with circular DeepL account fallback.

        :param text_block: Text block to translate.
        :param account_items: Ordered account/key pairs.
        :param active_account_index: Current account index.
        :return: Translated lines and active account index.
        """

        total_quota_attempts = 0  # Count quota attempts.
        maximum_quota_attempts = len(account_items) * 2  # Limit circular retries.
        while total_quota_attempts < maximum_quota_attempts:  # Retry until quota attempts are exhausted.
            account_name, api_key = account_items[active_account_index]  # Select active account.
            if account_name not in self.translators:  # Verify client must be created.
                self.translators[account_name] = self.create_deepl_client(account_name, api_key)  # Create cached client.
            translator = self.translators[account_name]  # Resolve translator client.
            try:  # Read usage before translation.
                remaining_chars = self.get_remaining_characters(translator)  # Read available quota.
            except deepl.QuotaExceededException:  # Handle quota exception during usage read.
                remaining_chars = 0  # Store exhausted quota.
            if remaining_chars is not None and len(text_block) > remaining_chars:  # Verify block fits current account.
                total_quota_attempts += 1  # Count quota attempt.
                active_account_index = (active_account_index + 1) % len(account_items)  # Advance account index.
                continue  # Retry same block with next account.
            try:  # Perform translation.
                result = translator.translate_text(text_block, target_lang=self.config.target_language)  # Translate with DeepL source auto-detection.
                return result.text.split("\n"), active_account_index  # Return translated lines.
            except deepl.QuotaExceededException:  # Handle quota exhaustion during translation.
                total_quota_attempts += 1  # Count quota attempt.
                active_account_index = (active_account_index + 1) % len(account_items)  # Advance account index.
                continue  # Retry same block with next account.
            except Exception as error:  # Handle non-quota translation failure.
                log_warning(f"Translation failed: {error}. Original lines kept for this block.")  # Report translation failure.
                return text_block.split("\n"), active_account_index  # Return original lines.
        attempted_accounts = ", ".join(account_name for account_name, _api_key in account_items)  # Build account summary.
        raise RuntimeError(f"All configured DeepL accounts were attempted twice without enough quota. Accounts attempted: {attempted_accounts}")  # Raise quota failure.

    def translate_srt_lines(self, source_srt: Path, lines: list[str], account_items: list[tuple[str, str]]) -> list[str]:
        """
        Translates SRT lines while keeping timing and indexes.

        :param source_srt: Source SRT file.
        :param lines: Source SRT lines.
        :param account_items: Ordered DeepL account/key pairs.
        :return: Translated SRT lines.
        """

        translated_lines: list[str] = []  # Store translated output lines.
        buffer: list[str] = []  # Store pending dialogue lines.
        active_account_index = 0  # Store current DeepL account index.
        for line in lines:  # Iterate source SRT lines.
            stripped = line.strip()  # Normalize current line.
            is_structure_line = stripped == "" or stripped.replace(":", "").replace(",", "").isdigit() or "-->" in line  # Determine structural SRT line.
            if is_structure_line:  # Verify line should not be translated.
                if buffer:  # Verify pending dialogue exists.
                    translated, active_account_index = self.translate_text_block("\n".join(buffer), account_items, active_account_index)  # Translate pending block.
                    translated_lines.extend(translated)  # Append translated dialogue.
                    buffer = []  # Reset dialogue buffer.
                translated_lines.append(line.rstrip("\n"))  # Preserve structural line.
            else:  # Handle dialogue line.
                buffer.append(stripped)  # Add dialogue line to buffer.
        if buffer:  # Verify trailing dialogue exists.
            translated, active_account_index = self.translate_text_block("\n".join(buffer), account_items, active_account_index)  # Translate trailing block.
            translated_lines.extend(translated)  # Append trailing translated dialogue.
        log_debug(f"Translated SRT candidate {source_srt.name}.", self.config.verbose)  # Report translated candidate when verbose.
        return translated_lines  # Return translation result.

    def translate_english_srt_to_ptbr(self, source_srt: Path, output_srt: Path) -> bool:
        """
        Translates one English SRT to Brazilian Portuguese using DeepL.

        :param source_srt: English source SRT path.
        :param output_srt: PT-BR output SRT path.
        :return: True when a valid translated output was saved.
        """

        if output_srt.exists() and output_srt.stat().st_size > 0:  # Verify output already exists.
            print(f"{BackgroundColors.GREEN}PT-BR translation already exists:{STYLE_RESET} {BackgroundColors.CYAN}{output_srt.name}{STYLE_RESET}")  # Report existing output.
            return False  # Return no new translation.
        if not self.load_deepl_api_keys():  # Verify DeepL keys are available.
            return False  # Return no translation.

        source_lines = read_text_file_lines(source_srt)  # Read source subtitle.
        if not parse_srt_blocks(source_lines):  # Verify source is valid SRT.
            log_warning(f"English source SRT is invalid or empty: {source_srt}")  # Report invalid source.
            return False  # Return no translation.
        if self.config.remove_descriptive_subtitles:  # Verify cleanup is enabled.
            cleaned_lines, removed_entries, mixed_entries = clean_descriptive_subtitle_lines(source_lines)  # Clean source cues.
            if parse_srt_blocks(cleaned_lines):  # Verify cleaned result is valid.
                source_lines = cleaned_lines  # Use cleaned subtitle lines.
                if removed_entries or mixed_entries:  # Verify cleanup changed content.
                    print(f"{BackgroundColors.YELLOW}SDH cleanup: {BackgroundColors.CYAN}{source_srt.name}{BackgroundColors.YELLOW} removed {BackgroundColors.CYAN}{removed_entries}{BackgroundColors.YELLOW} entries, cleaned {BackgroundColors.CYAN}{mixed_entries}{BackgroundColors.YELLOW} mixed entries.{STYLE_RESET}")  # Report cleanup summary.

        account_items = list(self.api_keys.items())  # Preserve configured account order.
        try:  # Translate source lines.
            translated_lines = self.translate_srt_lines(source_srt, source_lines, account_items)  # Translate SRT lines.
        except RuntimeError as error:  # Handle fatal translation failure.
            log_warning(f"DeepL translation failed for {source_srt.name}: {error}")  # Report translation failure.
            return False  # Return no translation.
        if not parse_srt_blocks(translated_lines):  # Verify translated structure.
            log_warning(f"Translated SRT structure is invalid and was not saved: {output_srt}")  # Report invalid translation.
            return False  # Return no translation.

        output_srt.parent.mkdir(parents=True, exist_ok=True)  # Ensure output directory exists.
        write_srt_lines_atomic(output_srt, translated_lines)  # Save translated subtitle atomically.
        print(f"{BackgroundColors.GREEN}Translated SRT saved as:{STYLE_RESET}\n{BackgroundColors.CYAN}{output_srt}{STYLE_RESET}")  # Report saved translation.
        return True  # Return translation success.
