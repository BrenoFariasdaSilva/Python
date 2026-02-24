"""
================================================================================
<PROJECT OR SCRIPT TITLE>
================================================================================
Author      : Breno Farias da Silva
Created     : <YYYY-MM-DD>
Description :
   <Provide a concise and complete overview of what this script does.>
   <Mention its purpose, scope, and relevance to the larger project.>

   Key features include:
      - <Feature 1 — e.g., automatic data loading and preprocessing>
      - <Feature 2 — e.g., model training and evaluation>
      - <Feature 3 — e.g., visualization or report generation>
      - <Feature 4 — e.g., logging or notification system>
      - <Feature 5 — e.g., integration with other modules or datasets>

Usage:
   1. <Explain any configuration steps before running, such as editing variables or paths.>
   2. <Describe how to execute the script — typically via Makefile or Python.>
         $ make <target>   or   $ python <script_name>.py
   3. <List what outputs are expected or where results are saved.>

Outputs:
   - <Output file or directory 1 — e.g., results.csv>
   - <Output file or directory 2 — e.g., Feature_Analysis/plots/>
   - <Output file or directory 3 — e.g., logs/output.txt>

TODOs:
   - <Add a task or improvement — e.g., implement CLI argument parsing.>
   - <Add another improvement — e.g., extend support to Parquet files.>
   - <Add optimization — e.g., parallelize evaluation loop.>
   - <Add robustness — e.g., error handling or data validation.>

Dependencies:
   - Python >= <version>
   - <Library 1 — e.g., pandas>
   - <Library 2 — e.g., numpy>
   - <Library 3 — e.g., scikit-learn>
   - <Library 4 — e.g., matplotlib, seaborn, tqdm, colorama>

Assumptions & Notes:
   - <List any key assumptions — e.g., last column is the target variable.>
   - <Mention data format — e.g., CSV files only.>
   - <Mention platform or OS-specific notes — e.g., sound disabled on Windows.>
   - <Note on output structure or reusability.>
"""

import datetime  # For getting the current date and time
import os  # For running a command in the terminal and filesystem ops
import sys  # For system-specific parameters and functions
import re  # For year matching in filenames
import json  # For writing the report
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

# Input/Output Constants:
INPUT_DIR = r"E:\Movies"  # Root input folder that contains movie-type subfolders
LOGS_DIR = "./Logs"  # Directory where logs and reports are stored
REPORT_FILE = f"{LOGS_DIR}/{Path(__file__).stem}_movie_year_report.json"

# Logger Setup:
logger = Logger(f"./Logs/{Path(__file__).stem}.log", clean=True)  # Create a Logger instance
sys.stdout = logger  # Redirect stdout to the logger
sys.stderr = logger  # Redirect stderr to the logger

# Functions Definitions:


def find_year_in_text(text: str) -> bool:
    """
    Returns True if a 4-digit year in the range 1900-2099 is present in `text`.
    
    :param text: The text to search for a year
    :return: True if a year is found, False otherwise
    """

    return re.search(r"(?<!\d)(19|20)\d{2}(?!\d)", text) is not None  # Regular expression to find a 4-digit year between 1900 and 2099


def scan_movies_for_missing_years(input_dir: str, report_path: str) -> dict:
    """
    Scan subdirectories of `input_dir` and verify movie files for a year (YYYY) in the filename.

    :param input_dir: Root folder that contains movie-type subfolders
    :param report_path: Path where the JSON report will be saved
    :return: A dictionary with report information
    """

    report = {"missing_years": [], "summary": {"scanned": 0, "missing": 0}}  # Initialize the report structure

    root = Path(input_dir)  # Create a Path object for the input directory
    if not root.exists() or not root.is_dir():  # Verifies if the input directory exists and is a directory
        print(f"{BackgroundColors.RED}Input directory not found: {BackgroundColors.CYAN}{input_dir}{Style.RESET_ALL}")
        return report  # Return an empty report if the input directory is invalid

    movie_type_dirs = [p for p in root.iterdir() if p.is_dir()]  # Discover movie-type subdirectories (only immediate children)

    for movie_dir in movie_type_dirs:  # Iterate through each movie-type subdirectory
        movie_type = movie_dir.name  # Get the name of the movie type (subdirectory name)
        for path in movie_dir.iterdir():  # Iterate through each file in the movie-type subdirectory
            if path.is_file():  # Verifies if the path is a file (not a directory)
                report["summary"]["scanned"] += 1  # Increment the count of scanned files
                if not find_year_in_text(path.name):  # Verifies if the filename does not contain a year
                    report_entry = {
                        "movie_type": movie_type,
                        "file_name": path.name,
                        "relative_path": str(path.as_posix()),
                    }  # Create a report entry for the file missing a year
                    report["missing_years"].append(report_entry)  # Add the report entry to the list of missing years
                    report["summary"]["missing"] += 1  # Increment the count of files missing a year

    Path(report_path).parent.mkdir(parents=True, exist_ok=True)  # Ensure the directory for the report exists
    
    with open(report_path, "w", encoding="utf-8") as fh:  # Open the report file for writing
        json.dump(report, fh, indent=2, ensure_ascii=False)  # Write the report as a JSON file with indentation for readability

    return report  # Return the report dictionary


def calculate_execution_time(start_time, finish_time):
    """
    Calculates the execution time between start and finish times and formats it as hh:mm:ss.

    :param start_time: The start datetime object
    :param finish_time: The finish datetime object
    :return: String formatted as hh:mm:ss representing the execution time
    """

    delta = finish_time - start_time  # Calculate the time difference
    hours, remainder = divmod(int(delta.total_seconds()), 3600)  # Calculate the hours, minutes and seconds
    minutes, seconds = divmod(remainder, 60)  # Calculate the minutes and seconds
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"  # Format the execution time


def main():
    """
    Main function.

    :param: None
    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}Main Template Python{BackgroundColors.GREEN} program!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the welcome message
    start_time = datetime.datetime.now()  # Get the start time of the program

    Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)  # Ensure logs directory exists

    report = scan_movies_for_missing_years(INPUT_DIR, REPORT_FILE)  # Scan movies and create report for files missing a 4-digit year (YYYY)

    scanned = report.get("summary", {}).get("scanned", 0)  # Get the total number of scanned files from the report summary
    missing = report.get("summary", {}).get("missing", 0)  # Get the total number of files missing a year from the report summary
    print(f"\nScanned files: {scanned} — Missing year: {missing}")  # Output the summary of scanned files and missing years

    finish_time = datetime.datetime.now()  # Get the finish time of the program
    print(
        f"{BackgroundColors.GREEN}Start time: {BackgroundColors.CYAN}{start_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Finish time: {BackgroundColors.CYAN}{finish_time.strftime('%d/%m/%Y - %H:%M:%S')}\n{BackgroundColors.GREEN}Execution time: {BackgroundColors.CYAN}{calculate_execution_time(start_time, finish_time)}{Style.RESET_ALL}"
    )  # Output the start and finish times
    print(
        f"\n{BackgroundColors.BOLD}{BackgroundColors.GREEN}Program finished.{Style.RESET_ALL}"
    )  # Output the end of the program message


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
