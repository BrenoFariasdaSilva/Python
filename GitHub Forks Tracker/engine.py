"""
================================================================================
GitHub Forks Tracker - engine.py
================================================================================
Author      : Breno Farias da Silva
Created     : 2026-02-27
Description :
    Core engine that interacts with the GitHub REST API to list forks,
    stream commits, compute divergent commits and export results to CSV.

    Key features include:
        - Paginated REST API requests with `per_page=100` and Link handling
        - Robust retry and backoff for network errors and 5xx responses
        - Rate-limit awareness using `X-RateLimit-Remaining` and `X-RateLimit-Reset`
        - Efficient SHA set comparisons for O(1) lookup
        - CSV streaming writer with proper escaping and newline preservation

Usage:
    Import and call `process_repository(original_owner, repo, token, outputs_dir)`
    or run this module as a script for quick testing.

Outputs:
    CSV files written to `./Outputs/` following the naming convention:
    "{ForkName}-{ForkOwner}-{CommitsRecord}.csv"

Dependencies:
    - requests
    - python-dotenv

Assumptions & Notes:
    - Uses GitHub REST API only and expects a valid token with repo access.
"""

import csv  # For CSV writing
import os  # For filesystem operations
import requests  # For HTTP requests
import sys  # For system functions
import time  # For sleeping between retries
import typing  # For type hints
from colorama import Style  # For colored output compatibility
from Logger import Logger  # For logging
from pathlib import Path  # For path handling


# Macros:
class BackgroundColors:  # Colors for the terminal
    CYAN = "\033[96m"  # Cyan
    GREEN = "\033[92m"  # Green
    YELLOW = "\033[93m"  # Yellow
    RED = "\033[91m"  # Red
    BOLD = "\033[1m"  # Bold
    UNDERLINE = "\033[4m"  # Underline
    CLEAR_TERMINAL = "\033[H\033[J"  # Clear the terminal


# Logger Setup:
logger = Logger(f"./Logs/{Path(__file__).stem}.log", clean=True)  # Create logger
sys.stdout = logger  # Redirect stdout to logger
sys.stderr = logger  # Redirect stderr to logger


# Classes Definitions:


class GitHubAPI:
    """
    Minimal GitHub REST API client with pagination and retry logic.

    :param token: Personal access token for GitHub API authentication.
    """

    def __init__(self, token: str) -> None:  # Initialize the client
        self.session = requests.Session()  # Create a requests session
        
        if token:  # If token provided
            self.session.headers.update({"Authorization": f"Bearer {token}"})  # Set auth header
        
        self.session.headers.update({"Accept": "application/vnd.github.v3+json"})  # Use REST v3


    def execute_single_request(self, method: str, url: str, params: typing.Optional[dict] = None) -> requests.Response:
        """
        Execute a single HTTP request and return the response.

        :param method: HTTP method
        :param url: Full URL
        :param params: Query parameters
        :return: requests.Response
        """
        
        return self.session.request(method, url, params=params, timeout=20)  # Perform request


    def is_rate_limited(self, resp: requests.Response) -> bool:
        """
        Determine if response indicates a rate limit has been reached.

        :param resp: Response object
        :return: True if rate limited
        """
        
        remaining = resp.headers.get("X-RateLimit-Remaining")  # Remaining calls
        reset = resp.headers.get("X-RateLimit-Reset")  # Reset epoch
        return resp.status_code == 403 and remaining == "0" and bool(reset)  # Rate limited check


    def compute_rate_limit_wait(self, resp: requests.Response, fallback: float) -> int:
        """
        Compute seconds to wait until rate limit reset, fallback on error.

        :param resp: Response object
        :param fallback: Fallback seconds
        :return: Seconds to wait
        """
        
        reset = resp.headers.get("X-RateLimit-Reset")  # Reset epoch
        if reset is None:  # Missing header
            return int(fallback)  # Fallback to backoff
        try:
            reset_int = int(reset)  # Convert reset to int
        except Exception:
            return int(fallback)  # Fallback to backoff on parse error
        return max(1, reset_int - int(time.time()))  # Compute wait seconds


    def is_server_error(self, resp: requests.Response) -> bool:
        """
        Verify if response is a server-side error (5xx).

        :param resp: Response object
        :return: True if server error
        """
        
        return resp.status_code >= 500  # Server error verify


    def is_client_error(self, resp: requests.Response) -> bool:
        """
        Verify if response is a client-side error (4xx).

        :param resp: Response object
        :return: True if client error
        """
        
        return resp.status_code >= 400  # Client error verify


    def extract_link_header(self, resp: requests.Response) -> typing.Optional[str]:
        """
        Extract the Link header from a response if present.

        :param resp: Response object
        :return: Link header string or None
        """
        
        return resp.headers.get("Link")  # Return Link header


    def parse_next_url(self, link_header: str) -> typing.Optional[str]:
        """
        Parse a Link header and return the URL for rel="next" if available.

        :param link_header: The Link header string
        :return: Next page URL or None
        """
        
        parts = link_header.split(",")  # Split link parts
        
        for part in parts:  # Iterate parts
            if 'rel="next"' in part:  # Next link found
                return part.split(";")[0].strip()[1:-1]  # Extract and return URL
        
        return None  # No next link


    def yield_items_from_data(self, data: typing.Any) -> typing.Iterator[dict]:
        """
        Yield items from parsed JSON data (list or single object).

        :param data: Parsed JSON payload
        :return: Iterator of items
        """
        
        if isinstance(data, list):  # If list of items
            for item in data:  # Iterate list
                yield item  # Yield each
            return  # End generator
        yield data  # Yield single object


    def request(self, method: str, url: str, params: typing.Optional[dict] = None) -> requests.Response:
        """
        Perform HTTP request with retries, backoff and rate-limit handling.

        :param method: HTTP method (GET, POST, etc.)
        :param url: Full URL to request
        :param params: Query parameters
        :return: requests.Response on success
        """

        backoff = 1.0  # Initial backoff seconds
        
        for attempt in range(8):  # Retry loop
            try:  # Attempt request
                resp = self.execute_single_request(method, url, params=params)  # Perform single request
            except requests.RequestException:  # Network error
                time.sleep(backoff)  # Sleep before retry
                backoff *= 2  # Exponential backoff
                continue  # Retry

            if self.is_rate_limited(resp):  # Rate limited
                wait_seconds = self.compute_rate_limit_wait(resp, backoff)  # Compute wait
                time.sleep(wait_seconds + 1)  # Sleep until reset
                continue  # Retry after wait

            if self.is_server_error(resp):  # Server error
                time.sleep(backoff)  # Sleep then retry
                backoff *= 2  # Increase backoff
                continue  # Retry

            if self.is_client_error(resp):  # Client error
                raise RuntimeError(f"HTTP {resp.status_code} for {url}")  # Raise for 4xx

            return resp  # Return successful response

        raise RuntimeError("Max retries exceeded for URL: " + url)  # Give up after retries


    def get_all_pages(self, url: typing.Optional[str], params: typing.Optional[dict] = None) -> typing.Iterator[dict]:
        """
        Yield items from paginated GitHub endpoints using `per_page=100` and Link headers.

        :param url: Endpoint URL
        :param params: Query parameters
        :yield: Parsed JSON items one by one
        """

        params = dict(params or {})  # Copy params
        params["per_page"] = 100  # Force 100 per page

        while url:  # Walk pages
            resp = self.request("GET", url, params=params)  # Perform request with retries
            if resp.status_code == 404:  # Not found
                return  # Stop iteration on 404

            data = resp.json()  # Parse JSON body
            for item in self.yield_items_from_data(data):  # Yield parsed items
                yield item  # Yield each item

            link = self.extract_link_header(resp)  # Extract Link header
            next_url = self.parse_next_url(link) if link else None  # Determine next page
            url = next_url  # Advance to next page


    def list_forks(self, owner: str, repo: str) -> typing.List[dict]:
        """
        List forks for a repository using GET /repos/{owner}/{repo}/forks.

        :param owner: Original repository owner
        :param repo: Repository name
        :return: List of fork repository dicts
        """

        url = f"https://api.github.com/repos/{owner}/{repo}/forks"  # Forks endpoint
        items = []  # Collect forks
        
        for item in self.get_all_pages(url):  # Iterate pages
            items.append(item)  # Append fork
        
        return items  # Return forks


    def list_commits(self, owner: str, repo: str) -> typing.List[dict]:
        """
        Retrieve all commits for a repository using GET /repos/{owner}/{repo}/commits.

        :param owner: Repository owner
        :param repo: Repository name
        :return: List of commits (newest first as returned by GitHub)
        """

        url = f"https://api.github.com/repos/{owner}/{repo}/commits"  # Commits endpoint
        commits = []  # Collection
        
        for item in self.get_all_pages(url):  # Iterate items
            commits.append(item)  # Append commit
        
        return commits  # Return list


# Functions Definitions:


def build_original_sha_set(original_commits: typing.List[dict]) -> typing.Set[str]:
    """
    Build a set of SHA hashes from original commits.

    :param original_commits: List of commit dictionaries from original repository
    :return: Set of commit SHA strings
    """

    original_shas: typing.Set[str] = set()  # Set for O(1) lookups
    for c in original_commits:  # Iterate original commits
        sha = c.get("sha")  # Extract SHA
        if isinstance(sha, str):  # Ensure it's a string
            original_shas.add(sha)  # Add to set

    return original_shas  # Return SHA set


def find_divergent_commits(original_shas: typing.Set[str], fork_commits: typing.List[dict]) -> typing.List[dict]:
    """
    Return commits present in `fork_commits` but not in `original_shas` preserving chronological order.

    :param original_shas: Set of original commit SHAs
    :param fork_commits: List of commits from fork (newest first)
    :return: List of divergent commits ordered oldest -> newest
    """

    divergent = [c for c in fork_commits if c.get("sha") not in original_shas]  # Filter by SHA membership
    divergent.reverse()  # Oldest -> newest
    return divergent  # Return filtered list


def build_commit_csv_row(commit: dict, commit_number: int) -> typing.List[typing.Any]:
    """
    Build a CSV row from a commit dictionary.

    :param commit: Commit dictionary returned from GitHub API
    :param commit_number: Sequential commit number (oldest->newest)
    :return: List representing a CSV row
    """

    sha = commit.get("sha", "")  # Commit SHA
    commit_obj = commit.get("commit", {})  # Commit object
    author_obj = commit_obj.get("author") or {}  # Author object
    date = author_obj.get("date", "")  # ISO date
    owner_name = author_obj.get("name") or "Unknown"  # Owner fallback
    message = commit_obj.get("message", "")  # Full message

    return [commit_number, sha, date, owner_name, message]  # Return formatted row


def export_commits_csv(fork_name: str, fork_owner: str, commits: typing.List[dict], outputs_dir: str) -> str:
    """
    Export commits to CSV and return the output path.

    :param fork_name: Repository name of the fork
    :param fork_owner: Owner login of the fork
    :param commits: List of commit dicts ordered oldest->newest
    :param outputs_dir: Directory to write CSV into
    :return: Path to the written CSV file
    """

    if not commits:  # No commits, nothing to write
        return ""  # Return empty

    Path(outputs_dir).mkdir(parents=True, exist_ok=True)  # Ensure outputs dir exists
    count = len(commits)  # Number of divergent commits
    safe_name = f"{fork_name}-{fork_owner}-{count}.csv"  # File name
    output_path = os.path.join(outputs_dir, safe_name)  # Full path

    header = ["Commit Number", "Commit Hash", "Commit Date", "Commit Owner", "Commit Message"]  # CSV header

    with open(output_path, "w", newline="", encoding="utf-8") as fh:  # Open file for writing
        writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL)  # CSV writer
        writer.writerow(header)  # Write header
        
        for idx, commit in enumerate(commits, start=1):  # Iterate commits
            row = build_commit_csv_row(commit, idx)  # Build row
            writer.writerow(row)  # Write CSV row

    return output_path  # Return path


def process_single_fork(api: "GitHubAPI", fork: dict, original_shas: typing.Set[str], outputs_dir: str) -> None:
    """
    Process a single fork: fetch commits, compute divergence and export CSV.

    :param api: GitHubAPI client instance
    :param fork: Fork metadata dictionary
    :param original_shas: Set of original repository SHAs
    :param outputs_dir: Directory to write CSV outputs
    :return: None
    """

    fork_owner = (fork.get("owner") or {}).get("login") or ""  # Fork owner
    fork_name = fork.get("name") or ""  # Fork repo name
    if not fork_owner or not fork_name:  # Skip malformed entries
        return  # Abort fork processing

    print(f"{BackgroundColors.GREEN}Processing fork {BackgroundColors.CYAN}{fork_owner}{BackgroundColors.GREEN}/{BackgroundColors.CYAN}{fork_name}{Style.RESET_ALL}")  # Log
    try:  # Fetch fork commits
        fork_commits = api.list_commits(fork_owner, fork_name)  # All commits newest->oldest
    except Exception as exc:  # Handle inaccessible or deleted fork
        print(f"{BackgroundColors.YELLOW}Skipping fork {BackgroundColors.CYAN}{fork_owner}{BackgroundColors.YELLOW}/{BackgroundColors.CYAN}{fork_name}{BackgroundColors.YELLOW}, error: {exc}{Style.RESET_ALL}")  # Log
        return  # Skip fork

    divergent = find_divergent_commits(original_shas, fork_commits)  # Compute divergent commits
    if not divergent:  # No divergent commits
        print(f"{BackgroundColors.YELLOW}No divergent commits for {BackgroundColors.CYAN}{fork_owner}{BackgroundColors.GREEN}/{BackgroundColors.CYAN}{fork_name}{Style.RESET_ALL}")  # Log
        return  # Skip CSV creation

    outpath = export_commits_csv(fork_name, fork_owner, divergent, outputs_dir)  # Write CSV
    print(f"{BackgroundColors.GREEN}Exported {BackgroundColors.CYAN}{len(divergent)}{BackgroundColors.GREEN} divergent commits to {BackgroundColors.CYAN}{outpath}{Style.RESET_ALL}")  # Log


def process_repository(original_owner: str, repo: str, token: str, outputs_dir: str = "./Outputs/") -> None:
    """
    High-level process: list forks, collect original SHAs, compute divergent commits and export CSVs.

    :param original_owner: Owner of the original repository
    :param repo: Repository name
    :param token: GitHub auth token
    :param outputs_dir: Directory to write CSV outputs
    :return: None
    """

    api = GitHubAPI(token)  # Create API client
    
    print(f"{BackgroundColors.GREEN}Listing forks for {BackgroundColors.CYAN}{original_owner}{BackgroundColors.GREEN}/{BackgroundColors.CYAN}{repo}{Style.RESET_ALL}")  # Log action
    forks = []  # Initialize forks list
    
    try:  # Attempt to list forks
        forks = api.list_forks(original_owner, repo)  # Get forks
    except Exception as exc:  # Handle errors
        print(f"{BackgroundColors.RED}Failed to list forks: {BackgroundColors.YELLOW}{exc}{Style.RESET_ALL}")  # Print error
        return  # Abort

    if not forks:  # No forks to process
        print(f"{BackgroundColors.YELLOW}No forks found for {BackgroundColors.CYAN}{original_owner}{BackgroundColors.GREEN}/{BackgroundColors.CYAN}{repo}{Style.RESET_ALL}")  # Inform user
        return  # Nothing to do

    print(f"{BackgroundColors.GREEN}Collecting commits from original repository...{Style.RESET_ALL}")  # Log
    try:  # Attempt to fetch commits
        original_commits = api.list_commits(original_owner, repo)  # All commits newest->oldest
    except Exception as exc:  # On failure
        print(f"{BackgroundColors.RED}Failed to fetch original commits: {BackgroundColors.YELLOW}{exc}{Style.RESET_ALL}")  # Log
        return  # Abort

    original_shas = build_original_sha_set(original_commits)  # Build SHA lookup set

    for fork in forks:  # Iterate forks
        process_single_fork(api, fork, original_shas, outputs_dir)  # Process fork


def main():
    """
    Main function.

    :param: None
    :return: None
    """

    print(
        f"{BackgroundColors.CLEAR_TERMINAL}{BackgroundColors.BOLD}{BackgroundColors.GREEN}Welcome to the {BackgroundColors.CYAN}GitHub Forks Tracker - engine.py{BackgroundColors.GREEN}!{Style.RESET_ALL}",
        end="\n\n",
    )  # Output the welcome message


if __name__ == "__main__":
    """
    This is the standard boilerplate that calls the main() function.

    :return: None
    """

    main()  # Call the main function
