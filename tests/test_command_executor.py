"""
Test cases for the CommandExecutor module.
"""

import subprocess

import pytest

from squish.command_executor import (
    CommandExecutionError,
    CommandExecutor,
    ICommandExecutor,
    MockCommandExecutor,
)
from squish.config import SquishFSConfig


class TestCommandExecutorInterface:
    """Test cases for ICommandExecutor interface."""

    def test_interface_has_required_methods(self):
        """Test that ICommandExecutor interface has all required methods."""
        required_methods = ["execute", "run_command", "check_command_available"]

        for method in required_methods:
            assert hasattr(ICommandExecutor, method)
            assert callable(getattr(ICommandExecutor, method))


class TestCommandExecutorInitialization:
    """Test cases for CommandExecutor initialization."""

    def test_init_with_default_config(self):
        """Test initialization with default configuration."""
        config = SquishFSConfig()
        executor = CommandExecutor(config)

        assert executor.config == config
        assert executor.logger is not None

    def test_init_with_custom_config(self):
        """Test initialization with custom configuration."""
        config = SquishFSConfig(verbose=True)
        executor = CommandExecutor(config)

        assert executor.config == config
        assert executor.logger is not None


class TestCommandExecutorExecute:
    """Test cases for CommandExecutor.execute method."""

    def test_execute_successful_command(self, mocker):
        """Test successful command execution."""
        config = SquishFSConfig()
        executor = CommandExecutor(config)

        # Mock subprocess.run to return successful result
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "success"
        mock_result.stderr = ""

        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        result = executor.execute(["echo", "test"])

        assert result == mock_result
        mock_subprocess.assert_called_once_with(
            ["echo", "test"], check=True, capture_output=False, text=False
        )

    def test_execute_failed_command(self, mocker):
        """Test failed command execution."""
        config = SquishFSConfig()
        executor = CommandExecutor(config)

        # Mock subprocess.run to raise CalledProcessError
        error = subprocess.CalledProcessError(
            returncode=1, cmd=["false"], output="", stderr="command failed"
        )

        mock_subprocess = mocker.patch("subprocess.run", side_effect=error)

        with pytest.raises(CommandExecutionError) as exc_info:
            executor.execute(["false"])

        assert (
            str(exc_info.value)
            == "Command 'false' failed with return code 1: command failed"
        )
        mock_subprocess.assert_called_once()

    def test_execute_with_capture_output(self, mocker):
        """Test command execution with output capture."""
        config = SquishFSConfig()
        executor = CommandExecutor(config)

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "captured output"
        mock_result.stderr = "captured error"

        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        result = executor.execute(["echo", "test"], capture_output=True, text=True)

        mock_subprocess.assert_called_once_with(
            ["echo", "test"], check=True, capture_output=True, text=True
        )
        assert result == mock_result

    def test_execute_with_additional_kwargs(self, mocker):
        """Test command execution with additional kwargs."""
        config = SquishFSConfig()
        executor = CommandExecutor(config)

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0

        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        result = executor.execute(["echo", "test"], cwd="/tmp", env={"TEST": "value"})

        mock_subprocess.assert_called_once_with(
            ["echo", "test"],
            check=True,
            capture_output=False,
            text=False,
            cwd="/tmp",
            env={"TEST": "value"},
        )
        assert result == mock_result


class TestCommandExecutorRunCommand:
    """Test cases for CommandExecutor.run_command method."""

    def test_run_command_success(self, mocker):
        """Test successful command execution via run_command."""
        config = SquishFSConfig()
        executor = CommandExecutor(config)

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0

        mock_execute = mocker.patch.object(
            executor, "execute", return_value=mock_result
        )

        result = executor.run_command(["echo", "test"])

        mock_execute.assert_called_once_with(["echo", "test"], True, False, False)
        assert result == mock_result

    def test_run_command_with_error_handling(self, mocker):
        """Test command execution with error handling via run_command."""
        config = SquishFSConfig()
        executor = CommandExecutor(config)

        error = CommandExecutionError("test", 1, "error")
        mocker.patch.object(executor, "execute", side_effect=error)

        with pytest.raises(CommandExecutionError):
            executor.run_command(["false"])


class TestCommandExecutorCheckCommandAvailable:
    """Test cases for CommandExecutor.check_command_available method."""

    def test_check_command_available_success(self, mocker):
        """Test checking for available command."""
        config = SquishFSConfig()
        executor = CommandExecutor(config)

        # Mock execute to return successful result for 'which' command
        mock_result = mocker.MagicMock()
        mock_result.returncode = 0

        mock_execute = mocker.patch.object(
            executor, "execute", return_value=mock_result
        )

        result = executor.check_command_available("mksquashfs")

        mock_execute.assert_called_once_with(
            ["which", "mksquashfs"], check=True, capture_output=True
        )
        assert result is True

    def test_check_command_available_failure(self, mocker):
        """Test checking for unavailable command."""
        config = SquishFSConfig()
        executor = CommandExecutor(config)

        # Mock execute to raise CommandExecutionError
        mock_execute = mocker.patch.object(
            executor,
            "execute",
            side_effect=CommandExecutionError("which", 1, "not found"),
        )

        result = executor.check_command_available("nonexistent")

        mock_execute.assert_called_once_with(
            ["which", "nonexistent"], check=True, capture_output=True
        )
        assert result is False


class TestMockCommandExecutor:
    """Test cases for MockCommandExecutor."""

    def test_mock_executor_init(self):
        """Test MockCommandExecutor initialization."""
        executor = MockCommandExecutor()

        assert executor.executed_commands == []
        assert executor.command_results == {}
        assert executor.available_commands == set()

    def test_mock_execute_success(self):
        """Test successful mock command execution."""
        executor = MockCommandExecutor()

        result = executor.execute(["echo", "test"])

        assert result.returncode == 0
        assert result.stdout == ""
        assert result.stderr == ""
        assert executor.executed_commands == [["echo", "test"]]

    def test_mock_execute_with_predefined_result(self):
        """Test mock execution with predefined result."""
        executor = MockCommandExecutor()

        # Set a predefined result
        predefined_result = subprocess.CompletedProcess(
            args=["test", "command"],
            returncode=0,
            stdout="predefined output",
            stderr="predefined error",
        )

        executor.set_command_result("test command", predefined_result)

        result = executor.execute(["test", "command"])

        assert result == predefined_result
        assert executor.executed_commands == [["test", "command"]]

    def test_mock_execute_unavailable_command(self):
        """Test mock execution of unavailable command."""
        executor = MockCommandExecutor()

        with pytest.raises(subprocess.CalledProcessError) as exc_info:
            executor.execute(["which", "nonexistent"])

        assert exc_info.value.returncode == 1
        assert "nonexistent: command not found" in exc_info.value.stderr

    def test_mock_execute_available_command(self):
        """Test mock execution of available command."""
        executor = MockCommandExecutor()
        executor.set_available_commands(["mksquashfs"])

        result = executor.execute(["which", "mksquashfs"])

        assert result.returncode == 0
        assert executor.executed_commands == [["which", "mksquashfs"]]

    def test_mock_check_command_available(self):
        """Test mock command availability check."""
        executor = MockCommandExecutor()
        executor.set_available_commands(["mksquashfs", "unsquashfs"])

        assert executor.check_command_available("mksquashfs") is True
        assert executor.check_command_available("unsquashfs") is True
        assert executor.check_command_available("nonexistent") is False

    def test_mock_run_command(self):
        """Test mock run_command method."""
        executor = MockCommandExecutor()

        result = executor.run_command(["echo", "test"])

        assert result.returncode == 0
        assert executor.executed_commands == [["echo", "test"]]

    def test_mock_clear(self):
        """Test clearing mock executor state."""
        executor = MockCommandExecutor()

        # Add some state
        executor.execute(["echo", "test"])
        executor.set_available_commands(["mksquashfs"])

        assert len(executor.executed_commands) == 1
        assert len(executor.available_commands) == 1

        # Clear state
        executor.clear()

        assert executor.executed_commands == []
        assert executor.command_results == {}
        assert executor.available_commands == set()


class TestCommandExecutorEdgeCases:
    """Edge case tests for CommandExecutor."""

    def test_execute_empty_command(self, mocker):
        """Test execution of empty command."""
        config = SquishFSConfig()
        executor = CommandExecutor(config)

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0

        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        # Empty command should still execute (subprocess.run allows it)
        result = executor.execute([])

        mock_subprocess.assert_called_once_with(
            [], check=True, capture_output=False, text=False
        )
        assert result == mock_result

    def test_execute_with_check_false(self, mocker):
        """Test command execution with check=False."""
        config = SquishFSConfig()
        executor = CommandExecutor(config)

        # Mock subprocess.run to return non-zero returncode
        mock_result = mocker.MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error"

        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        result = executor.execute(["false"], check=False)

        assert result.returncode == 1
        mock_subprocess.assert_called_once_with(
            ["false"], check=False, capture_output=False, text=False
        )

    def test_execute_with_complex_command(self, mocker):
        """Test execution of complex command with many arguments."""
        config = SquishFSConfig()
        executor = CommandExecutor(config)

        complex_command = [
            "mksquashfs",
            "source",
            "output.sqsh",
            "-comp",
            "zstd",
            "-b",
            "1M",
            "-processors",
            "4",
            "-info",
            "-keep-as-directory",
        ]

        mock_result = mocker.MagicMock()
        mock_result.returncode = 0

        mock_subprocess = mocker.patch("subprocess.run", return_value=mock_result)

        result = executor.execute(complex_command)

        mock_subprocess.assert_called_once_with(
            complex_command, check=True, capture_output=False, text=False
        )
        assert result == mock_result


class TestCommandExecutorIntegration:
    """Integration tests for CommandExecutor."""

    def test_complete_workflow(self, mocker):
        """Test complete command execution workflow."""
        config = SquishFSConfig(verbose=True)
        executor = CommandExecutor(config)

        # Mock subprocess.run to return different results
        mock_results = [
            mocker.MagicMock(returncode=0, stdout="step1", stderr=""),
            mocker.MagicMock(returncode=0, stdout="step2", stderr=""),
        ]

        # For the third call, raise CalledProcessError
        def mock_subprocess_side_effect(*args, **kwargs):
            if len(mock_results) > 0:
                return mock_results.pop(0)
            else:
                raise subprocess.CalledProcessError(
                    returncode=1, cmd=["false"], output="", stderr="error"
                )

        mocker.patch("subprocess.run", side_effect=mock_subprocess_side_effect)
        mock_logger = mocker.patch.object(executor.logger, "log_command_execution")

        # Execute successful commands
        result1 = executor.execute(["echo", "step1"])
        result2 = executor.execute(["echo", "step2"])

        assert result1.returncode == 0
        assert result2.returncode == 0

        # Execute failing command
        with pytest.raises(CommandExecutionError):
            executor.execute(["false"])

        # Verify logging calls
        assert mock_logger.call_count == 6  # 2 successful + 1 failed (pre and post)

    def test_command_availability_workflow(self, mocker):
        """Test command availability checking workflow."""
        config = SquishFSConfig()
        executor = CommandExecutor(config)

        # Mock execute to simulate different command availability
        def mock_execute_side_effect(command, **kwargs):
            if command[1] in ["mksquashfs", "unsquashfs"]:
                return mocker.MagicMock(returncode=0)
            else:
                raise CommandExecutionError(command[0], 1, "not found")

        mock_execute = mocker.patch.object(
            executor, "execute", side_effect=mock_execute_side_effect
        )

        # Test available commands
        assert executor.check_command_available("mksquashfs") is True
        assert executor.check_command_available("unsquashfs") is True

        # Test unavailable commands
        assert executor.check_command_available("nonexistent") is False
        assert executor.check_command_available("fakecommand") is False

        # Verify execute was called with correct parameters
        assert mock_execute.call_count == 4
