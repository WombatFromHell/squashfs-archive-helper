"""
Command execution abstraction for the SquashFS Archive Helper.

This module provides an abstraction layer for executing external commands,
making the code more testable and maintainable.
"""

import subprocess
from abc import ABC, abstractmethod

from .config import SquishFSConfig
from .errors import CommandExecutionError
from .logging import get_logger


class ICommandExecutor(ABC):
    """Interface for command execution."""

    @abstractmethod
    def execute(
        self,
        command: list[str],
        check: bool = True,
        capture_output: bool = False,
        text: bool = False,
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """Execute a command and return the result."""
        pass

    @abstractmethod
    def run_command(
        self,
        command: list[str],
        check: bool = True,
        capture_output: bool = False,
        text: bool = False,
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """Run a command with error handling."""
        pass

    @abstractmethod
    def check_command_available(self, command: str) -> bool:
        """Check if a command is available in the system."""
        pass


class CommandExecutor(ICommandExecutor):
    """Concrete implementation of command executor."""

    def __init__(self, config: SquishFSConfig):
        self.config = config
        self.logger = get_logger(config.verbose)

    def execute(
        self,
        command: list[str],
        check: bool = True,
        capture_output: bool = False,
        text: bool = False,
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """Execute a command and return the result."""
        if self.config.verbose:
            self.logger.log_command_execution(" ".join(command))

        try:
            result = subprocess.run(
                command, check=check, capture_output=capture_output, text=text, **kwargs
            )
            if self.config.verbose:
                self.logger.log_command_execution(" ".join(command), success=True)
            return result
        except subprocess.CalledProcessError as e:
            if self.config.verbose:
                self.logger.log_command_execution(
                    " ".join(command), e.returncode, success=False
                )
            raise CommandExecutionError(command[0], e.returncode, e.stderr)

    def run_command(
        self,
        command: list[str],
        check: bool = True,
        capture_output: bool = False,
        text: bool = False,
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """Run a command with error handling."""
        return self.execute(command, check, capture_output, text, **kwargs)

    def check_command_available(self, command: str) -> bool:
        """Check if a command is available in the system."""
        try:
            self.execute(["which", command], check=True, capture_output=True)
            return True
        except CommandExecutionError:
            return False


class MockCommandExecutor(ICommandExecutor):
    """Mock implementation of command executor for testing."""

    def __init__(self):
        self.executed_commands = []
        self.command_results = {}
        self.available_commands = set()

    def execute(
        self,
        command: list[str],
        check: bool = True,
        capture_output: bool = False,
        text: bool = False,
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """Mock command execution."""
        self.executed_commands.append(command)

        # Check if we have a predefined result for this command
        command_key = " ".join(command)
        if command_key in self.command_results:
            return self.command_results[command_key]

        # Check if the command is in the "which" format and the target command is not available
        if (
            len(command) == 2
            and command[0] == "which"
            and command[1] not in self.available_commands
        ):
            # Simulate command not found
            if check:
                raise subprocess.CalledProcessError(
                    returncode=1,
                    cmd=command,
                    output="",
                    stderr=f"{command[1]}: command not found",
                )
            else:
                return subprocess.CompletedProcess(
                    args=command,
                    returncode=1,
                    stdout="",
                    stderr=f"{command[1]}: command not found",
                )

        # Default mock behavior: return successful result
        return subprocess.CompletedProcess(
            args=command, returncode=0, stdout="", stderr=""
        )

    def run_command(
        self,
        command: list[str],
        check: bool = True,
        capture_output: bool = False,
        text: bool = False,
        **kwargs,
    ) -> subprocess.CompletedProcess:
        """Mock command execution with error handling."""
        return self.execute(command, check, capture_output, text, **kwargs)

    def check_command_available(self, command: str) -> bool:
        """Mock command availability check."""
        return command in self.available_commands

    def set_command_result(self, command: str, result: subprocess.CompletedProcess):
        """Set a predefined result for a command."""
        self.command_results[command] = result

    def set_available_commands(self, commands: list[str]):
        """Set which commands should be available."""
        self.available_commands.update(commands)

    def clear(self):
        """Clear all recorded commands and results."""
        self.executed_commands.clear()
        self.command_results.clear()
        self.available_commands.clear()
