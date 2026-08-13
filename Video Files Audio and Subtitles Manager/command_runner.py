"""
External command execution.
"""

import os  # Detect platform executable extension.
import shutil  # Locate executables on PATH.
import subprocess  # Run external commands.
import sys  # Locate active virtual environment scripts.
from pathlib import Path  # Build executable paths.
from console import log_debug, log_error  # Report command diagnostics.
from models import CommandResult  # Return typed command results.


class CommandRunner:
    """
    Owns external command lookup and execution.
    """

    def __init__(self, verbose: bool = False) -> None:
        """
        Initializes the command runner.

        :param verbose: Verbose output flag.
        :return: None.
        """

        self.verbose = verbose  # Store verbose output flag.

    def find_executable(self, command_name: str) -> str | None:
        """
        Finds an executable in the active environment or PATH.

        :param command_name: Executable name.
        :return: Executable path or None.
        """

        venv_bin = Path(sys.prefix) / ("Scripts" if os.name == "nt" else "bin")  # Build active environment binary directory.
        executable_name = f"{command_name}.exe" if os.name == "nt" else command_name  # Resolve platform executable name.
        venv_candidate = venv_bin / executable_name  # Build virtual environment executable path.
        if venv_candidate.exists():  # Verify executable exists in virtual environment.
            return str(venv_candidate)  # Return virtual environment executable.
        return shutil.which(command_name)  # Return PATH lookup result.

    def has_required_commands(self, command_names: tuple[str, ...]) -> bool:
        """
        Verifies required commands are available.

        :param command_names: Command names to verify.
        :return: True when every command is available.
        """

        missing = [name for name in command_names if self.find_executable(name) is None]  # Gather missing commands.
        if missing:  # Verify any command is missing.
            log_error(f"Missing required command(s): {', '.join(missing)}")  # Report missing commands.
            return False  # Return unavailable result.
        return True  # Return available result.

    def run(self, command: list[str], quiet: bool = True) -> CommandResult:
        """
        Runs an external command.

        :param command: Command argument list.
        :param quiet: Whether output should be captured.
        :return: Command result.
        """

        log_debug(f"Command: {' '.join(command)}", self.verbose)  # Log command when verbose.
        stdout_target = subprocess.PIPE if quiet else None  # Select stdout target.
        stderr_target = subprocess.PIPE if quiet else None  # Select stderr target.
        result = subprocess.run(command, stdout=stdout_target, stderr=stderr_target, text=True, encoding="utf-8", errors="replace")  # Execute command.
        stdout_text = result.stdout if isinstance(result.stdout, str) else ""  # Normalize stdout.
        stderr_text = result.stderr if isinstance(result.stderr, str) else ""  # Normalize stderr.
        return CommandResult(result.returncode, stdout_text, stderr_text)  # Return typed result.
