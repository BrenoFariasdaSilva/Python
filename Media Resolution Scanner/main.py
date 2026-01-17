"""
================================================================================
Media Resolution Scanner
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-01-17
Description :
	Scans configured media directories for resolution indicators (e.g. 1080p, 4k),
	normalizes resolutions (optionally converting k-formats to p-formats), and
	writes a JSON report summarizing found resolutions and directories without
	resolution indicators.

Usage:
	- Configure `SEARCH_DIRS` and `STANDARDIZE_RESOLUTION` at the top of the file.
	- Run with: `python main.py` or via the provided `Makefile`.

Outputs:
	- A JSON report saved to the path defined by `REPORT_OUTPUT`.

Notes:
	- Prints are routed through `Logger` so output is captured in Logs/.
	- Sound notifications are disabled on Windows by default.
"""

import atexit  # For playing a sound when the program finishes
import datetime  # For getting the current date and time
import json  # For handling JSON files
import os  # For running a command in the terminal
import platform  # For getting the operating system name
import re  # For regular expressions
import sys  # For system-specific parameters and functions
from colorama import Style  # For coloring the terminal
from Logger import Logger  # For logging output to both terminal and file
from pathlib import Path  # For handling file paths


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

SEARCH_DIRS = {
    "Movies": "F:\\Movies",
    "Series": "E:\\Series",
}  # Mapping of name -> directory path to be searched recursively

STANDARDIZE_RESOLUTION = True  # Convert k-format to p-format (e.g., 4k -> 2160p)

RESOLUTION_REGEX = re.compile(r"\b(?:[1-9]\d{2,4}p|[1-9]\d?k)\b", re.IGNORECASE)  # Regex to find resolutions in filenames

K_TO_P_MAP = {  # Mapping from k-format to p-format resolutions
    "2k": "1440p",
    "4k": "2160p",
    "8k": "4320p",
}

REPORT_OUTPUT = "./Reports/resolution_report.json"  # Path to save the resolution report (saved under Reports/)

# Logger Setup:
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

	if VERBOSE and true_string != "":  # If the VERBOSE constant is set to True and the true_string is set
		print(true_string)  # Output the true statement string
	elif false_string != "":  # If the false_string is set
		print(false_string)  # Output the false statement string


def normalize_resolution(resolution, standardize=None):
	"""
	Normalize a resolution token and optionally convert k-format to p-format.

	This function canonicalizes resolution strings found in filenames or
	directory names. It trims surrounding whitespace, lowercases the token so
	the trailing "p" is always lowercase (e.g. "1080p"), and when
	`standardize` is True will convert common `k`-style tokens (for example
	"4k") to their equivalent `p` value using `K_TO_P_MAP` (for example
	"4k" -> "2160p").

	:param resolution: The resolution string to normalize (e.g. "1080P", "4k").
	:type resolution: str
	:param standardize: Optional override for `STANDARDIZE_RESOLUTION`. If
	                    omitted (None), the module-level constant is used.
	:type standardize: bool | None
	:return: Normalized resolution string (lowercased). Examples: "1080p",
	         "2160p".
	:rtype: str
	"""

	verbose_output(
		f"{BackgroundColors.GREEN}Normalizing resolution:{BackgroundColors.CYAN} {resolution}{Style.RESET_ALL}"
	)  # Output verbose message for resolution normalization

	if standardize is None:  # Check if standardize parameter is not provided
		standardize = STANDARDIZE_RESOLUTION  # Use module-level constant as default

	raw = resolution.strip()  # Remove leading and trailing whitespace
	key = raw.lower()  # Convert to lowercase for case-insensitive comparison

	if standardize and key in K_TO_P_MAP:  # Check if k-format conversion is enabled and token exists in map
		return K_TO_P_MAP[key]  # Return the mapped p-format value

	return key  # Return the normalized lowercase token


def has_subdirectories(path):
	"""
	Return whether the given filesystem path contains any subdirectories.

	This checks only the immediate children of `path` and returns True as
	soon as a single subdirectory is encountered. Permission errors are
	handled gracefully and treated as "no subdirectories".

	:param path: Path to examine (string or pathlib.Path).
	:return: True if there is at least one subdirectory, False otherwise.
	:rtype: bool
	"""

	verbose_output(
		f"{BackgroundColors.GREEN}Checking for subdirectories in:{BackgroundColors.CYAN} {path}{Style.RESET_ALL}"
	)  # Output verbose message for subdirectory check

	try:  # Attempt to check for subdirectories
		return any(p.is_dir() for p in Path(path).iterdir())  # Return True if any child is a directory
	except PermissionError:  # Handle permission denied errors
		return False  # Return False if we cannot access the directory


def _get_dir_size_bytes(path):
	"""
	Return total size in bytes of files under a given path (recursive).

	:param path: The directory path to compute size for
	:return: Total size in bytes of all files under the path
	"""

	total = 0  # Initialize total size counter
	try:  # Attempt to walk through directory tree
		for dirpath, _, filenames in os.walk(path):  # Walk through directory tree
			for fname in filenames:  # Process each file
				fp = os.path.join(dirpath, fname)  # Build full file path
				try:  # Attempt to get file size
					if os.path.islink(fp):  # Skip symbolic links
						continue  # Skip to next file
					total += os.path.getsize(fp)  # Add file size to total
				except Exception:  # Handle any file access errors
					continue  # Skip files we can't stat
	except Exception:  # Handle directory walk errors
		return 0  # Return 0 if directory walk fails
	return total  # Return total size in bytes


def _prepare_report_args(search_dirs, report_output, standardize):
	"""
	Prepare and normalize arguments for scanning.

	:param search_dirs: Iterable of base directories to scan, or None to use default.
	:param report_output: Output file path for the report, or None to use default.
	:param standardize: Boolean override for standardization, or None to use default.
	:return: Tuple (search_dirs, report_output, standardize)
	"""

	if search_dirs is None:  # Check if search directories not provided
		search_dirs = SEARCH_DIRS  # Use default search directories
	if report_output is None:  # Check if report output path not provided
		report_output = REPORT_OUTPUT  # Use default report path
	if standardize is None:  # Check if standardization flag not provided
		standardize = STANDARDIZE_RESOLUTION  # Use default standardization flag
	return search_dirs, report_output, standardize  # Return normalized arguments tuple


def _resolution_sort_key(token):
	"""
	Return a numeric sort key for a resolution token.

	:param token: Resolution token string (e.g. '1080p', '4k')
	:return: Numeric sort key for ordering resolutions
	"""

	key = token.lower().strip()  # Normalize the token to lowercase

	if key in K_TO_P_MAP:  # Check if token exists in k-to-p mapping
		mapped = K_TO_P_MAP[key]  # Get mapped p-format value
		digits = re.findall(r"\d+", mapped)  # Extract numeric portion
		return int(digits[0]) if digits else float("inf")  # Return numeric value or infinity

	if key.endswith("p"):  # Check if token has p-suffix
		digits = re.findall(r"\d+", key)  # Extract numeric portion
		return int(digits[0]) if digits else float("inf")  # Return numeric value or infinity

	if key.endswith("k"):  # Check if token has k-suffix
		digits = re.findall(r"\d+", key)  # Extract numeric portion
		if digits:  # Check if digits were found
			try:  # Attempt to convert k to pixel count
				return int(float(digits[0]) * 1000)  # Convert k to approximate pixel count
			except Exception:  # Handle conversion errors
				return float("inf")  # Return infinity if conversion fails

	digits = re.findall(r"\d+", key)  # Extract numeric portion as fallback
	return int(digits[0]) if digits else float("inf")  # Return numeric value or infinity


def _scan_for_resolutions(search_dirs, standardize):
	"""
	Walk directories in `search_dirs` and collect resolution data.

	:param search_dirs: Iterable of base directories to scan.
	:param standardize: Whether to convert k-format to p-format.
	:return: Tuple (resolution_groups, no_resolution_found)
	"""

	resolution_groups = {}  # Mapping: normalized_resolution -> [ {name,size_gb,created} ]
	no_resolution_found = []  # List of dirs with no resolution token

	for base_dir in search_dirs:  # Iterate through each base directory to scan
		base_path = Path(base_dir)  # Convert base directory to Path object

		if not base_path.exists():  # Check if base directory exists
			continue  # Skip missing base directories

		for root, dirs, _ in os.walk(base_path):  # Walk through directory tree
			current_dir = Path(root)  # Convert current directory to Path object
			dir_name = current_dir.name  # Current directory name to inspect

			matches = RESOLUTION_REGEX.findall(dir_name)  # Find resolution tokens in directory name

			if matches:  # Check if resolution tokens were found
				try:  # Attempt to compute directory size
					size_bytes = _get_dir_size_bytes(current_dir)  # Get total size in bytes
					size_gb = round(size_bytes / (1024 ** 3), 2)  # Convert bytes to gigabytes
				except Exception:  # Handle size computation errors
					size_gb = 0.0  # Default to 0 GB on error

				try:  # Attempt to get directory creation time
					st = current_dir.stat()  # Get directory stats
					if hasattr(st, "st_birthtime"):  # Check if birth time is available
						created_ts = st.st_birthtime  # Use birth time when available
					else:  # Birth time not available
						created_ts = st.st_ctime  # Fall back to ctime
					created = datetime.datetime.fromtimestamp(created_ts).strftime("%d-%m-%Y")  # Format creation date
				except Exception:  # Handle stat errors
					created = ""  # Default to empty string on error

				for match in matches:  # Iterate through each resolution token found
					normalized = normalize_resolution(match, standardize)  # Normalize token
					entry = {"name": dir_name, "size_gb": size_gb, "created": created}  # Create entry dictionary
					resolution_groups.setdefault(normalized, []).append(entry)  # Add entry to resolution group
			else:  # No resolution tokens found in directory name
				if not dirs:  # Check if this is a leaf directory
					try:  # Attempt to compute directory size
						size_bytes = _get_dir_size_bytes(current_dir)  # Get total size in bytes
						size_gb = round(size_bytes / (1024 ** 3), 2)  # Convert bytes to gigabytes
					except Exception:  # Handle size computation errors
						size_bytes = 0  # Default to 0 bytes
						size_gb = 0.0  # Default to 0 GB

					if size_bytes == 0:  # Check if directory is empty
						continue  # Skip empty directories entirely

					try:  # Attempt to get directory creation time
						st = current_dir.stat()  # Get directory stats
						if hasattr(st, "st_birthtime"):  # Check if birth time is available
							created_ts = st.st_birthtime  # Use birth time when available
						else:  # Birth time not available
							created_ts = st.st_ctime  # Fall back to ctime
						created = datetime.datetime.fromtimestamp(created_ts).strftime("%d-%m-%Y")  # Format creation date
					except Exception:  # Handle stat errors
						created = ""  # Default to empty string on error

					try:  # Attempt to compute relative path
						rel = str(current_dir.relative_to(base_path))  # Compute relative path to base
					except Exception:  # Handle relative path computation errors
						rel = str(current_dir)  # Use full path as fallback
					if rel in (".", ""):  # Check if relative path is current directory or empty
						rel = dir_name  # Use directory name instead

					no_resolution_found.append({"rel": rel, "size_gb": size_gb, "created": created})  # Store structured entry

	return resolution_groups, no_resolution_found  # Return tuple of resolution groups and no-resolution list


def _build_report_dict(resolution_groups, no_resolution_found, standardize):
	"""
	Construct the final report dictionary from scan results.

	:param resolution_groups: Mapping of normalized resolution -> list of dirs.
	:param no_resolution_found: List of directory names without resolution tokens.
	:param standardize: Whether resolutions were standardized.
	:return: Report dictionary ready for JSON serialization.
	"""

	sorted_items = sorted(resolution_groups.items(), key=lambda kv: _resolution_sort_key(kv[0]))  # Sort resolutions numerically

	ordered_resolutions = {}  # Initialize ordered resolutions dictionary
	for res_key, entries in sorted_items:  # Iterate through sorted resolution groups
		entries_sorted = sorted(entries, key=lambda e: e.get("name", ""))  # Sort entries by name alphabetically
		items = [
			{"Name": e["name"], "Size": f"{e.get("size_gb", 0.0)} GB", "Created": e.get("created", "")}
			for e in entries_sorted
		]  # Format items as JSON objects per item
		total = round(sum(e.get("size_gb", 0.0) for e in entries_sorted), 2)  # Calculate total size for this resolution
		ordered_resolutions[res_key] = {"count": len(items), "total_gb": total, "items": items}  # Create resolution entry with count, total and items

	no_items = []  # Initialize no-resolution items list
	no_total = 0.0  # Initialize no-resolution total size
	if no_resolution_found:  # Check if there are any no-resolution entries
		no_sorted = sorted(no_resolution_found, key=lambda e: e.get("rel", ""))  # Sort by relative path
		for e in no_sorted:  # Iterate through sorted no-resolution entries
			rel_raw = e.get("rel", "")  # Raw relative path (OS-specific separators)
			rel = rel_raw.replace("\\", "/")  # Normalize separators to Linux-style forward slash
			no_items.append({"Name": rel, "Size": f"{e.get("size_gb", 0.0)} GB", "Created": e.get("created", "")})  # Format item as JSON object
			try:  # Attempt to add size to total
				no_total += float(e.get("size_gb", 0.0))  # Add entry size to total
			except Exception:  # Handle conversion errors
				pass  # Skip entries with invalid size values
		no_total = round(no_total, 2)  # Round total to 2 decimal places

	return {
		"no_resolution_found": {"count": len(no_items), "total_gb": no_total, "items": no_items},  # No-resolution section
		"resolutions": ordered_resolutions,  # Numeric-ascending mapping with totals
	}  # Return complete report dictionary


def _ensure_output_dir(report_output):
	"""
	Ensure the parent directory for `report_output` exists.

	:param report_output: Path to the report file.
	:return: None
	"""

	try:  # Attempt to create parent directories
		Path(report_output).parent.mkdir(parents=True, exist_ok=True)  # Create parent directories if needed
	except Exception:  # Handle directory creation errors
		pass  # Best-effort; any write error will surface later


def _write_report(report_output, report):
	"""
	Write the `report` dict as JSON to `report_output`.

	:param report_output: Path to the JSON file to write.
	:param report: Report dictionary to serialize.
	:return: None
	"""

	with open(report_output, "w", encoding="utf-8") as f:  # Open file for writing with UTF-8 encoding
		json.dump(report, f, indent=4, ensure_ascii=False)  # Write JSON to disk preserving unicode


def generate_resolution_report(search_dirs=None, report_output=None, standardize=None):
	"""
	High-level wrapper that builds and writes the resolution report.

	:param search_dirs: Iterable of base directories to scan, or None to use default.
	:param report_output: Path to write the JSON report, or None to use default.
	:param standardize: Optional override for standardization flag.
	:return: Tuple (report_output_path, report_dict)
	"""

	verbose_output(
		f"{BackgroundColors.GREEN}Generating resolution report (standardize={standardize}) for: {BackgroundColors.CYAN}{search_dirs or SEARCH_DIRS}{Style.RESET_ALL}"
	)  # Output verbose message for report generation

	search_dirs, report_output, standardize = _prepare_report_args(
		search_dirs, report_output, standardize
	)  # Prepare arguments with defaults

	if hasattr(search_dirs, "items"):  # Check if search_dirs is a mapping
		outputs = {}  # Initialize outputs dictionary
		for name, path in search_dirs.items():  # Iterate through each named search directory
			resolution_groups, no_resolution_found = _scan_for_resolutions([path], standardize)  # Scan directory for resolutions
			report = _build_report_dict(resolution_groups, no_resolution_found, standardize)  # Build report dictionary

			base_output = Path(report_output)  # Convert report output to Path object
			per_name_output = base_output.with_name(f"{base_output.stem}_{name}{base_output.suffix}")  # Build per-name output path
			_ensure_output_dir(per_name_output)  # Ensure parent directory exists
			verbose_output(
				f"{BackgroundColors.GREEN}Writing resolution report to:{BackgroundColors.CYAN} {per_name_output}{Style.RESET_ALL}"
			)  # Output verbose message for file write
			_write_report(per_name_output, report)  # Write report to file
			outputs[name] = (str(per_name_output), report)  # Store output path and report in dictionary

		return outputs  # Return mapping of name to output path and report

	resolution_groups, no_resolution_found = _scan_for_resolutions(search_dirs, standardize)  # Scan directories for resolutions
	report = _build_report_dict(resolution_groups, no_resolution_found, standardize)  # Build report dictionary
	_ensure_output_dir(report_output)  # Ensure parent directory exists
	verbose_output(
		f"{BackgroundColors.GREEN}Writing resolution report to:{BackgroundColors.CYAN} {report_output}{Style.RESET_ALL}"
	)  # Output verbose message for file write
	_write_report(report_output, report)  # Write report to file
	return report_output, report  # Return output path and report tuple


def calculate_execution_time(start_time, finish_time):
	"""
	Calculates the execution time between start and finish times and formats it as hh:mm:ss.

	:param start_time: The start datetime object
	:param finish_time: The finish datetime object
	:return: String formatted as hh:mm:ss representing the execution time
	"""

	delta = finish_time - start_time  # Calculate the time difference
	hours, remainder = divmod(delta.seconds, 3600)  # Calculate the hours, minutes and seconds
	minutes, seconds = divmod(remainder, 60)  # Calculate the minutes and seconds
	return f"{hours:02d}:{minutes:02d}:{seconds:02d}"  # Format the execution time


def verify_filepath_exists(filepath):
	"""
	Verify if a file or folder exists at the specified path.

	:param filepath: Path to the file or folder
	:return: True if the file or folder exists, False otherwise
	"""

	verbose_output(
		f"{BackgroundColors.GREEN}Verifying if the file or folder exists at the path: {BackgroundColors.CYAN}{filepath}{Style.RESET_ALL}"
	)  # Output the verbose message

	return os.path.exists(filepath)  # Return True if the file or folder exists, False otherwise


def play_sound():
	"""
	Plays a sound when the program finishes and skips if the operating system is Windows.

	:param: None
	:return: None
	"""

	current_os = platform.system()  # Get the current operating system
	if current_os == "Windows":  # If the current operating system is Windows
		return  # Do nothing

	if verify_filepath_exists(SOUND_FILE):  # If the sound file exists
		if current_os in SOUND_COMMANDS:  # If the platform.system() is in the SOUND_COMMANDS dictionary
			os.system(f"{SOUND_COMMANDS[current_os]} {SOUND_FILE}")  # Play the sound
		else:  # If the platform.system() is not in the SOUND_COMMANDS dictionary
			print(
				f"{BackgroundColors.RED}The {BackgroundColors.CYAN}{current_os}{BackgroundColors.RED} is not in the {BackgroundColors.CYAN}SOUND_COMMANDS dictionary{BackgroundColors.RED}. Please add it!{Style.RESET_ALL}"
			)  # Output error message for missing OS
	else:  # If the sound file does not exist
		print(
			f"{BackgroundColors.RED}Sound file {BackgroundColors.CYAN}{SOUND_FILE}{BackgroundColors.RED} not found. Make sure the file exists.{Style.RESET_ALL}"
		)  # Output error message for missing sound file


def main():
	"""
	Main function.

	:param: None
	:return: None
	"""

	print(
		f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Media Resolution Scanner{BackgroundColors.GREEN}!{Style.RESET_ALL}",
		end="\n\n",
	)  # Output the welcome message
	start_time = datetime.datetime.now()  # Get the start time of the program

	result = generate_resolution_report()  # Generate resolution report using module-level helper
	if isinstance(result, tuple):  # Check if result is a tuple (single report)
		report_path, report = result  # Unpack report path and report data
		print(
			f"{BackgroundColors.GREEN}Resolution report generated at:{BackgroundColors.CYAN} {report_path}{Style.RESET_ALL}"
		)  # Output report path message
	else:  # Result is a mapping (multiple reports)
		for name, (report_path, report) in result.items():  # Iterate through each named report
			print(
				f"{BackgroundColors.GREEN}Resolution report for {BackgroundColors.CYAN}{name}{BackgroundColors.GREEN} generated at:{BackgroundColors.CYAN} {report_path}{Style.RESET_ALL}"
			)  # Output report path message for each named report

	finish_time = datetime.datetime.now()  # Get the finish time of the program
	print(
		f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"
	)  # Output the start and finish times
	print(
		f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
	)  # Output the end of the program message

	(
		atexit.register(play_sound) if RUN_FUNCTIONS["Play Sound"] else None
	)  # Register the play_sound function to be called when the program finishes


if __name__ == "__main__":
	"""
	This is the standard boilerplate that calls the main() function.

	:return: None
	"""

	main()  # Call the main function
