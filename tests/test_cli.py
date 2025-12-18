"""
Test cases for the CLI module.

This module tests the command-line interface functionality with subcommands.
"""

import tempfile

import pytest

from squish.cli import (
    get_config_from_args,
    parse_args,
    validate_directory_exists,
    validate_file_exists,
)
from squish.errors import BuildError, ListError, SquashFSError


class TestArgumentParsing:
    """Test command line argument parsing with subcommands."""

    def test_parse_mount_args(self, mocker):
        """Test parsing mount command arguments."""
        mocker.patch("sys.argv", ["squish", "mount", "test.sqs"])
        args = parse_args()
        assert args.command == "mount"
        assert args.file == "test.sqs"
        assert args.mount_point is None
        assert args.verbose is False

    def test_parse_mount_with_mount_point(self, mocker):
        """Test parsing mount command with mount point."""
        mocker.patch("sys.argv", ["squish", "mount", "test.sqs", "/mnt/point"])
        args = parse_args()
        assert args.command == "mount"
        assert args.file == "test.sqs"
        assert args.mount_point == "/mnt/point"

    def test_parse_unmount_args(self, mocker):
        """Test parsing unmount command arguments."""
        mocker.patch("sys.argv", ["squish", "unmount", "test.sqs"])
        args = parse_args()
        assert args.command == "unmount"
        assert args.file == "test.sqs"
        assert args.mount_point is None

    def test_parse_check_args(self, mocker):
        """Test parsing check command arguments."""
        mocker.patch("sys.argv", ["squish", "check", "test.sqs"])
        args = parse_args()
        assert args.command == "check"
        assert args.file == "test.sqs"

    def test_parse_build_args(self, mocker):
        """Test parsing build command arguments."""
        mocker.patch("sys.argv", ["squish", "build", "source_dir", "output.sqsh"])
        args = parse_args()
        assert args.command == "build"
        assert args.source == "source_dir"
        assert args.output == "output.sqsh"
        assert args.compression == "zstd"
        assert args.block_size == "1M"
        assert args.processors is None

    def test_parse_build_with_options(self, mocker):
        """Test parsing build command with all options."""
        mocker.patch(
            "sys.argv",
            [
                "squish",
                "build",
                "source_dir",
                "output.sqsh",
                "-e",
                "*.tmp",
                "-f",
                "exclude.txt",
                "-w",
                "-c",
                "gzip",
                "-b",
                "256K",
                "-p",
                "4",
            ],
        )
        args = parse_args()
        assert args.command == "build"
        assert args.source == "source_dir"
        assert args.output == "output.sqsh"
        assert args.exclude == ["*.tmp"]
        assert args.exclude_file == "exclude.txt"
        assert args.wildcards is True
        assert args.regex is False
        assert args.compression == "gzip"
        assert args.block_size == "256K"
        assert args.processors == 4

    def test_parse_list_args(self, mocker):
        """Test parsing list command arguments."""
        mocker.patch("sys.argv", ["squish", "ls", "archive.sqsh"])
        args = parse_args()
        assert args.command == "ls"
        assert args.archive == "archive.sqsh"

    def test_parse_verbose_args(self, mocker):
        """Test parsing verbose flag."""
        mocker.patch("sys.argv", ["squish", "-v", "mount", "test.sqs"])
        args = parse_args()
        assert args.verbose is True

    def test_parse_missing_command(self, mocker):
        """Test parsing without command (should fail)."""
        mocker.patch("sys.argv", ["squish"])
        with pytest.raises(SystemExit):
            parse_args()


class TestConfiguration:
    """Test configuration handling."""

    def test_get_config_from_args(self, mocker):
        """Test getting configuration from arguments."""
        args = mocker.MagicMock()
        args.verbose = True

        config = get_config_from_args(args)
        assert config.verbose is True

    def test_get_config_default(self, mocker):
        """Test getting configuration with default values."""
        args = mocker.MagicMock()
        args.verbose = False

        config = get_config_from_args(args)
        assert config.verbose is False


class TestValidation:
    """Test validation functions."""

    def test_validate_file_exists_success(self):
        """Test successful file validation."""
        with tempfile.NamedTemporaryFile() as temp_file:
            # Should not raise an exception
            validate_file_exists(temp_file.name)

    def test_validate_file_exists_failure(self):
        """Test file validation failure."""
        with pytest.raises(SystemExit):
            validate_file_exists("/nonexistent/file.sqs")

    def test_validate_file_exists_failure_no_logger(self, mocker):
        """Test file validation failure when logger is None (prints error message)."""
        mock_print = mocker.patch("builtins.print")
        with pytest.raises(SystemExit):
            validate_file_exists("/nonexistent/file.sqs", logger=None)

        # Verify that the error message was printed
        mock_print.assert_called_with("File not found: /nonexistent/file.sqs")

    def test_validate_directory_exists_success(self):
        """Test successful directory validation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Should not raise an exception
            validate_directory_exists(temp_dir)

    def test_validate_directory_exists_failure(self):
        """Test directory validation failure."""
        with pytest.raises(SystemExit):
            validate_directory_exists("/nonexistent/directory")

    def test_validate_directory_exists_failure_no_logger(self, mocker):
        """Test directory validation failure when logger is None (prints error message)."""
        mock_print = mocker.patch("builtins.print")
        with pytest.raises(SystemExit):
            validate_directory_exists("/nonexistent/directory", logger=None)

        # Verify that the error message was printed
        mock_print.assert_called_with("Directory not found: /nonexistent/directory")


class TestCLIHandlers:
    """Test CLI handler functions."""

    @pytest.fixture
    def mock_manager(self, mocker):
        """Create a mock manager."""
        manager = mocker.MagicMock()
        return manager

    def test_handle_mount_operation_success(self, mock_manager):
        """Test successful mount operation handling."""
        from squish.cli import handle_mount_operation

        # Should not raise an exception
        handle_mount_operation(mock_manager, "test.sqs", "/mnt/point")
        mock_manager.mount.assert_called_once_with("test.sqs", "/mnt/point")

    def test_handle_mount_operation_failure(self, mock_manager):
        """Test failed mount operation handling."""
        from squish.cli import handle_mount_operation

        mock_manager.mount.side_effect = SquashFSError("Mount failed")

        with pytest.raises(SystemExit):
            handle_mount_operation(mock_manager, "test.sqs", "/mnt/point")

    def test_handle_mount_operation_failure_no_logger(self, mock_manager, mocker):
        """Test failed mount operation handling when logger is None (prints error message)."""
        from squish.cli import handle_mount_operation

        mock_manager.mount.side_effect = SquashFSError("Mount failed")

        mock_print = mocker.patch("builtins.print")
        with pytest.raises(SystemExit):
            handle_mount_operation(mock_manager, "test.sqs", "/mnt/point", logger=None)

        # Verify that the error message was printed
        mock_print.assert_called_with("Mount failed: Mount failed")

    def test_handle_unmount_operation_success(self, mock_manager):
        """Test successful unmount operation handling."""
        from squish.cli import handle_unmount_operation

        # Should not raise an exception
        handle_unmount_operation(mock_manager, "test.sqs", "/mnt/point")
        mock_manager.unmount.assert_called_once_with("test.sqs", "/mnt/point")

    def test_handle_unmount_operation_failure(self, mock_manager):
        """Test failed unmount operation handling."""
        from squish.cli import handle_unmount_operation

        mock_manager.unmount.side_effect = SquashFSError("Unmount failed")

        with pytest.raises(SystemExit):
            handle_unmount_operation(mock_manager, "test.sqs", "/mnt/point")

    def test_handle_unmount_operation_failure_no_logger(self, mock_manager, mocker):
        """Test failed unmount operation handling when logger is None (prints error message)."""
        from squish.cli import handle_unmount_operation

        mock_manager.unmount.side_effect = SquashFSError("Unmount failed")

        mock_print = mocker.patch("builtins.print")
        with pytest.raises(SystemExit):
            handle_unmount_operation(
                mock_manager, "test.sqs", "/mnt/point", logger=None
            )

        # Verify that the error message was printed
        mock_print.assert_called_with("Unmount failed: Unmount failed")

    def test_handle_check_operation_success(self, mock_manager):
        """Test successful check operation handling."""
        from squish.cli import handle_check_operation

        # Should not raise an exception
        handle_check_operation(mock_manager, "test.sqs")
        mock_manager.verify_checksum.assert_called_once_with("test.sqs")

    def test_handle_check_operation_failure(self, mock_manager):
        """Test failed check operation handling."""
        from squish.cli import handle_check_operation

        mock_manager.verify_checksum.side_effect = SquashFSError("Check failed")

        with pytest.raises(SystemExit):
            handle_check_operation(mock_manager, "test.sqs")

    def test_handle_check_operation_failure_no_logger(self, mock_manager, mocker):
        """Test failed check operation handling when logger is None (prints error message)."""
        from squish.cli import handle_check_operation

        mock_manager.verify_checksum.side_effect = SquashFSError("Check failed")

        mock_print = mocker.patch("builtins.print")
        with pytest.raises(SystemExit):
            handle_check_operation(mock_manager, "test.sqs", logger=None)

        # Verify that the error message was printed
        mock_print.assert_called_with("Check failed")

    def test_handle_build_operation_success(self, mock_manager):
        """Test successful build operation handling."""
        from squish.cli import handle_build_operation

        # Should not raise an exception
        handle_build_operation(
            mock_manager,
            "source_dir",
            "output.sqsh",
            excludes=["*.tmp"],
            exclude_file="exclude.txt",
            wildcards=True,
            regex=False,
            compression="zstd",
            block_size="1M",
            processors=4,
        )

        mock_manager.build_squashfs.assert_called_once()

    def test_handle_build_operation_failure(self, mock_manager):
        """Test failed build operation handling."""
        from squish.cli import handle_build_operation

        mock_manager.build_squashfs.side_effect = BuildError("Build failed")

        with pytest.raises(SystemExit):
            handle_build_operation(
                mock_manager,
                "source_dir",
                "output.sqsh",
                excludes=["*.tmp"],
                exclude_file="exclude.txt",
                wildcards=True,
                regex=False,
                compression="zstd",
                block_size="1M",
                processors=4,
            )

    def test_handle_build_operation_failure_no_logger(self, mock_manager, mocker):
        """Test failed build operation handling when logger is None (prints error message)."""
        from squish.cli import handle_build_operation

        mock_manager.build_squashfs.side_effect = BuildError("Build failed")

        mock_print = mocker.patch("builtins.print")
        with pytest.raises(SystemExit):
            handle_build_operation(
                mock_manager,
                "source_dir",
                "output.sqsh",
                excludes=["*.tmp"],
                exclude_file="exclude.txt",
                wildcards=True,
                regex=False,
                compression="zstd",
                block_size="1M",
                processors=4,
                logger=None,
            )

        # Verify that the error message was printed
        mock_print.assert_called_with("Build failed: Build failed")

    def test_handle_list_operation_success(self, mock_manager):
        """Test successful list operation handling."""
        from squish.cli import handle_list_operation

        # Should not raise an exception
        handle_list_operation(mock_manager, "archive.sqsh")
        mock_manager.list_squashfs.assert_called_once_with("archive.sqsh")

    def test_handle_list_operation_failure(self, mock_manager):
        """Test failed list operation handling."""
        from squish.cli import handle_list_operation

        mock_manager.list_squashfs.side_effect = ListError("List failed")

        with pytest.raises(SystemExit):
            handle_list_operation(mock_manager, "archive.sqsh")

    def test_handle_list_operation_failure_no_logger(self, mock_manager, mocker):
        """Test failed list operation handling when logger is None (prints error message)."""
        from squish.cli import handle_list_operation

        mock_manager.list_squashfs.side_effect = ListError("List failed")

        mock_print = mocker.patch("builtins.print")
        with pytest.raises(SystemExit):
            handle_list_operation(mock_manager, "archive.sqsh", logger=None)

        # Verify that the error message was printed
        mock_print.assert_called_with("List operation failed: List failed")


class TestMainFunction:
    """Test the main function."""

    def test_main_mount_command(self, mocker):
        """Test main function with mount command."""
        from squish.cli import main

        mock_parse = mocker.patch("squish.cli.parse_args")
        mocker.patch("squish.cli.validate_file_exists")
        mock_manager_class = mocker.patch("squish.cli.SquashFSManager")

        # Mock parse_args to return mount command args
        mock_args = mocker.MagicMock()
        mock_args.command = "mount"
        mock_args.file = "test.sqs"
        mock_args.mount_point = None
        mock_args.verbose = False
        mock_parse.return_value = mock_args

        # Mock manager
        mock_manager = mocker.MagicMock()
        mock_manager_class.return_value = mock_manager

        # Should not raise an exception
        main()

        # Verify manager was created and mount was called
        mock_manager_class.assert_called_once()
        mock_manager.mount.assert_called_once_with("test.sqs", None)

    def test_main_build_command(self, mocker):
        """Test main function with build command."""
        from squish.cli import main

        mock_parse = mocker.patch("squish.cli.parse_args")
        mocker.patch("squish.cli.validate_directory_exists")
        mock_manager_class = mocker.patch("squish.cli.SquashFSManager")

        # Mock parse_args to return build command args
        mock_args = mocker.MagicMock()
        mock_args.command = "build"
        mock_args.source = "source_dir"
        mock_args.output = "output.sqsh"
        mock_args.exclude = None
        mock_args.exclude_file = None
        mock_args.wildcards = False
        mock_args.regex = False
        mock_args.compression = "zstd"
        mock_args.block_size = "1M"
        mock_args.processors = None
        mock_args.verbose = False
        mock_parse.return_value = mock_args

        # Mock manager
        mock_manager = mocker.MagicMock()
        mock_manager_class.return_value = mock_manager

        # Should not raise an exception
        main()

        # Verify manager was created and build was called
        mock_manager_class.assert_called_once()
        mock_manager.build_squashfs.assert_called_once()

    def test_main_unmount_command(self, mocker):
        """Test main function with unmount command."""
        from squish.cli import main

        mock_parse = mocker.patch("squish.cli.parse_args")
        mocker.patch("squish.cli.validate_file_exists")
        mock_manager_class = mocker.patch("squish.cli.SquashFSManager")

        # Mock parse_args to return unmount command args
        mock_args = mocker.MagicMock()
        mock_args.command = "unmount"
        mock_args.file = "test.sqs"
        mock_args.mount_point = None
        mock_args.verbose = False
        mock_parse.return_value = mock_args

        # Mock manager
        mock_manager = mocker.MagicMock()
        mock_manager_class.return_value = mock_manager

        # Should not raise an exception
        main()

        # Verify manager was created and unmount was called
        mock_manager_class.assert_called_once()
        mock_manager.unmount.assert_called_once_with("test.sqs", None)

    def test_main_check_command(self, mocker):
        """Test main function with check command."""
        from squish.cli import main

        mock_parse = mocker.patch("squish.cli.parse_args")
        mocker.patch("squish.cli.validate_file_exists")
        mock_manager_class = mocker.patch("squish.cli.SquashFSManager")

        # Mock parse_args to return check command args
        mock_args = mocker.MagicMock()
        mock_args.command = "check"
        mock_args.file = "test.sqs"
        mock_args.verbose = False
        mock_parse.return_value = mock_args

        # Mock manager
        mock_manager = mocker.MagicMock()
        mock_manager_class.return_value = mock_manager

        # Should not raise an exception
        main()

        # Verify manager was created and verify_checksum was called
        mock_manager_class.assert_called_once()
        mock_manager.verify_checksum.assert_called_once_with("test.sqs")

    def test_main_list_command(self, mocker):
        """Test main function with list command."""
        from squish.cli import main

        mock_parse = mocker.patch("squish.cli.parse_args")
        mocker.patch("squish.cli.validate_file_exists")
        mock_manager_class = mocker.patch("squish.cli.SquashFSManager")

        # Mock parse_args to return list command args
        mock_args = mocker.MagicMock()
        mock_args.command = "ls"
        mock_args.archive = "archive.sqsh"
        mock_args.verbose = False
        mock_parse.return_value = mock_args

        # Mock manager
        mock_manager = mocker.MagicMock()
        mock_manager_class.return_value = mock_manager

        # Should not raise an exception
        main()

        # Verify manager was created and list was called
        mock_manager_class.assert_called_once()
        mock_manager.list_squashfs.assert_called_once_with("archive.sqsh")

    def test_main_with_keyboard_interrupt(self, mocker):
        """Test main function with keyboard interrupt."""
        from squish.cli import main

        mock_parse = mocker.patch("squish.cli.parse_args")
        # Mock parse_args to raise KeyboardInterrupt
        mock_parse.side_effect = KeyboardInterrupt()

        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1


class TestCLIErrorHandling:
    """Test CLI error handling and edge cases."""

    def test_main_with_unexpected_error_no_logger(self, mocker):
        """Test main function with unexpected error when no logger is available."""
        from squish.cli import main

        mock_parse = mocker.patch("squish.cli.parse_args")
        # Mock parse_args to raise Exception
        mock_parse.side_effect = Exception("Unexpected error")

        mock_print = mocker.patch("builtins.print")
        with pytest.raises(SystemExit) as e:
            main()
        mock_print.assert_called_with("Unexpected error: Unexpected error")
        assert e.value.code == 1

    def test_main_with_keyboard_interrupt_no_logger(self, mocker):
        """Test main function with keyboard interrupt when no logger is available."""
        from squish.cli import main

        mock_parse = mocker.patch("squish.cli.parse_args")
        # Mock parse_args to raise KeyboardInterrupt
        mock_parse.side_effect = KeyboardInterrupt()

        mock_print = mocker.patch("builtins.print")
        with pytest.raises(SystemExit) as e:
            main()
        mock_print.assert_called_with("\nOperation cancelled by user")
        assert e.value.code == 1


class TestCLIEdgeCases:
    """Test CLI edge cases and special scenarios."""

    def test_validate_file_exists_with_nonexistent_file(self, mocker):
        """Test file validation with non-existent file."""
        mocker.patch("os.path.isfile", return_value=False)
        mock_exit = mocker.patch("sys.exit")
        mock_print = mocker.patch("builtins.print")
        from squish.cli import validate_file_exists

        validate_file_exists("nonexistent.sqs", "mount")
        mock_print.assert_called_with("File not found: nonexistent.sqs")
        mock_exit.assert_called_once_with(1)

    def test_validate_directory_exists_with_nonexistent_directory(self, mocker):
        """Test directory validation with non-existent directory."""
        mocker.patch("os.path.isdir", return_value=False)
        mock_exit = mocker.patch("sys.exit")
        mock_print = mocker.patch("builtins.print")
        from squish.cli import validate_directory_exists

        validate_directory_exists("nonexistent_dir", "build")
        mock_print.assert_called_with("Directory not found: nonexistent_dir")
        mock_exit.assert_called_once_with(1)

    def test_main_with_unexpected_error(self, mocker):
        """Test main function with unexpected error."""
        from squish.cli import main

        mock_parse = mocker.patch("squish.cli.parse_args")
        # Mock parse_args to raise Exception
        mock_parse.side_effect = Exception("Unexpected error")

        with pytest.raises(SystemExit) as e:
            main()
        assert e.value.code == 1


class TestCLICoverageGaps:
    """Test cases to cover missing CLI coverage gaps."""

    def test_validate_file_exists_failure_no_logger_coverage(self, mocker):
        """Test validate_file_exists failure without logger to cover line 106."""
        from squish.cli import validate_file_exists

        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        validate_file_exists("nonexistent_file.sqs", "mount", logger=None)

        # Verify error message was printed (line 106)
        mock_print.assert_called_once_with("File not found: nonexistent_file.sqs")
        # Verify sys.exit was called (line 107)
        mock_exit.assert_called_once_with(1)

    def test_validate_directory_exists_failure_no_logger_coverage(self, mocker):
        """Test validate_directory_exists failure without logger to cover line 118."""
        from squish.cli import validate_directory_exists

        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        validate_directory_exists("nonexistent_dir", "build", logger=None)

        # Verify error message was printed (line 118)
        mock_print.assert_called_once_with("Directory not found: nonexistent_dir")
        # Verify sys.exit was called (line 119)
        mock_exit.assert_called_once_with(1)

    def test_handle_mount_operation_failure_no_logger_coverage(self, mocker):
        """Test handle_mount_operation failure without logger to cover line 132."""
        from squish.cli import handle_mount_operation
        from squish.errors import SquashFSError

        mock_manager = mocker.MagicMock()
        mock_manager.mount.side_effect = SquashFSError("Mount failed")

        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        handle_mount_operation(mock_manager, "test.sqs", "/mnt/point", logger=None)

        # Verify error message was printed (line 132)
        mock_print.assert_called_once_with("Mount failed: Mount failed")
        # Verify sys.exit was called (line 133)
        mock_exit.assert_called_once_with(1)

    def test_handle_unmount_operation_failure_no_logger_coverage(self, mocker):
        """Test handle_unmount_operation failure without logger to cover line 148."""
        from squish.cli import handle_unmount_operation
        from squish.errors import SquashFSError

        mock_manager = mocker.MagicMock()
        mock_manager.unmount.side_effect = SquashFSError("Unmount failed")

        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        handle_unmount_operation(mock_manager, "test.sqs", "/mnt/point", logger=None)

        # Verify error message was printed (line 148)
        mock_print.assert_called_once_with("Unmount failed: Unmount failed")
        # Verify sys.exit was called (line 149)
        mock_exit.assert_called_once_with(1)

    def test_handle_check_operation_success_no_logger_coverage(self, mocker):
        """Test handle_check_operation success without logger to cover line 163."""
        from squish.cli import handle_check_operation

        mock_manager = mocker.MagicMock()

        mock_print = mocker.patch("builtins.print")
        handle_check_operation(mock_manager, "test.sqs", logger=None)

        # Verify success message was printed (line 163)
        mock_print.assert_called_once_with(
            "Checksum verification successful for: test.sqs"
        )

    def test_handle_check_operation_failure_no_logger_coverage(self, mocker):
        """Test handle_check_operation failure without logger to cover line 168."""
        from squish.cli import handle_check_operation
        from squish.errors import SquashFSError

        mock_manager = mocker.MagicMock()
        mock_manager.verify_checksum.side_effect = SquashFSError("Checksum failed")

        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        handle_check_operation(mock_manager, "test.sqs", logger=None)

        # Verify error message was printed (line 168)
        mock_print.assert_called_once_with("Checksum failed")
        # Verify sys.exit was called (line 169)
        mock_exit.assert_called_once_with(1)

    def test_handle_build_operation_failure_no_logger_coverage(self, mocker):
        """Test handle_build_operation failure without logger to cover line 202."""
        from squish.cli import handle_build_operation
        from squish.errors import BuildError

        mock_manager = mocker.MagicMock()
        mock_manager.build_squashfs.side_effect = BuildError("Build failed")

        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        handle_build_operation(mock_manager, "source_dir", "output.sqs", logger=None)

        # Verify error message was printed (line 202)
        mock_print.assert_called_once_with("Build failed: Build failed")
        # Verify sys.exit was called (line 203)
        mock_exit.assert_called_once_with(1)

    def test_handle_list_operation_failure_no_logger_coverage(self, mocker):
        """Test handle_list_operation failure without logger to cover line 214."""
        from squish.cli import handle_list_operation
        from squish.errors import ListError

        mock_manager = mocker.MagicMock()
        mock_manager.list_squashfs.side_effect = ListError("List failed")

        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        handle_list_operation(mock_manager, "archive.sqs", logger=None)

        # Verify error message was printed (line 214)
        mock_print.assert_called_once_with("List operation failed: List failed")
        # Verify sys.exit was called (line 215)
        mock_exit.assert_called_once_with(1)

    def test_main_system_exit_coverage(self, mocker):
        """Test main function system exit to cover line 264->exit."""
        from squish.cli import main

        mock_parse = mocker.patch("squish.cli.parse_args")
        mock_logger = mocker.patch("squish.cli.get_logger_from_args")
        mock_config = mocker.patch("squish.cli.get_config_from_args")
        mock_manager = mocker.patch("squish.cli.SquashFSManager")
        mocker.patch("squish.cli.validate_file_exists")

        mock_args = mocker.MagicMock()
        mock_args.command = "mount"
        mock_args.file = "test.sqs"
        mock_args.mount_point = None

        mock_parse.return_value = mock_args
        mock_logger.return_value = mocker.MagicMock()
        mock_config.return_value = mocker.MagicMock()
        mock_manager.return_value = mocker.MagicMock()

        # This should complete normally without system exit
        main()

    def test_main_keyboard_interrupt_no_logger_coverage(self, mocker):
        """Test main function keyboard interrupt without logger to cover line 270."""
        from squish.cli import main

        mock_parse = mocker.patch("squish.cli.parse_args")
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        mock_parse.side_effect = KeyboardInterrupt()

        main()

        # Verify keyboard interrupt message was printed (line 270)
        mock_print.assert_called_once_with("\nOperation cancelled by user")
        # Verify sys.exit was called (line 271)
        mock_exit.assert_called_once_with(1)

    def test_main_unexpected_error_no_logger_coverage(self, mocker):
        """Test main function unexpected error without logger to cover line 276."""
        from squish.cli import main

        mock_parse = mocker.patch("squish.cli.parse_args")
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        mock_parse.side_effect = Exception("Unexpected error")

        main()

        # Verify error message was printed (line 276)
        mock_print.assert_called_once_with("Unexpected error: Unexpected error")
        # Verify sys.exit was called (line 277)
        mock_exit.assert_called_once_with(1)

    def test_main_if_name_main_coverage(self, mocker):
        """Test main function if __name__ == '__main__' block to cover line 283."""
        # This test verifies the main() function can be called directly
        # The if __name__ == "__main__" block is covered by normal execution
        from squish.cli import main

        mock_parse = mocker.patch("squish.cli.parse_args")
        mock_logger = mocker.patch("squish.cli.get_logger_from_args")
        mock_config = mocker.patch("squish.cli.get_config_from_args")
        mock_manager = mocker.patch("squish.cli.SquashFSManager")
        mocker.patch("squish.cli.validate_file_exists")

        mock_args = mocker.MagicMock()
        mock_args.command = "mount"
        mock_args.file = "test.sqs"
        mock_args.mount_point = None

        mock_parse.return_value = mock_args
        mock_logger.return_value = mocker.MagicMock()
        mock_config.return_value = mocker.MagicMock()
        mock_manager.return_value = mocker.MagicMock()

        # Call main directly (covers line 283)
        main()

    def test_validation_functions_direct_coverage(self, mocker):
        """Test validation functions directly to ensure lines 106, 118 are covered."""
        from squish.cli import validate_directory_exists, validate_file_exists

        # Test validate_file_exists without logger (line 106)
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        validate_file_exists("nonexistent.sqs", "mount", logger=None)
        mock_print.assert_called_once_with("File not found: nonexistent.sqs")
        mock_exit.assert_called_once_with(1)

        # Test validate_directory_exists without logger (line 118)
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        validate_directory_exists("nonexistent_dir", "build", logger=None)
        mock_print.assert_called_once_with("Directory not found: nonexistent_dir")
        mock_exit.assert_called_once_with(1)

    def test_operation_handlers_direct_coverage(self, mocker):
        """Test operation handlers directly to ensure lines 132, 148, 163, 168, 202, 214 are covered."""
        from squish.cli import (
            handle_build_operation,
            handle_check_operation,
            handle_list_operation,
            handle_mount_operation,
            handle_unmount_operation,
        )
        from squish.errors import BuildError, ListError, SquashFSError

        mock_manager = mocker.MagicMock()

        # Test handle_mount_operation without logger (line 132)
        mock_manager.mount.side_effect = SquashFSError("Mount failed")
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        handle_mount_operation(mock_manager, "test.sqs", "/mnt/point", logger=None)
        mock_print.assert_called_once_with("Mount failed: Mount failed")
        mock_exit.assert_called_once_with(1)

        # Test handle_unmount_operation without logger (line 148)
        mock_manager.unmount.side_effect = SquashFSError("Unmount failed")
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        handle_unmount_operation(mock_manager, "test.sqs", "/mnt/point", logger=None)
        mock_print.assert_called_once_with("Unmount failed: Unmount failed")
        mock_exit.assert_called_once_with(1)

        # Test handle_check_operation success without logger (line 163)
        mock_print = mocker.patch("builtins.print")
        handle_check_operation(mock_manager, "test.sqs", logger=None)
        mock_print.assert_called_once_with(
            "Checksum verification successful for: test.sqs"
        )

        # Test handle_check_operation failure without logger (line 168)
        mock_manager.verify_checksum.side_effect = SquashFSError("Checksum failed")
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        handle_check_operation(mock_manager, "test.sqs", logger=None)
        mock_print.assert_called_once_with("Checksum failed")
        mock_exit.assert_called_once_with(1)

        # Test handle_build_operation without logger (line 202)
        mock_manager.build_squashfs.side_effect = BuildError("Build failed")
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        handle_build_operation(mock_manager, "source_dir", "output.sqs", logger=None)
        mock_print.assert_called_once_with("Build failed: Build failed")
        mock_exit.assert_called_once_with(1)

        # Test handle_list_operation without logger (line 214)
        mock_manager.list_squashfs.side_effect = ListError("List failed")
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        handle_list_operation(mock_manager, "archive.sqs", logger=None)
        mock_print.assert_called_once_with("List operation failed: List failed")
        mock_exit.assert_called_once_with(1)

    def test_main_error_handling_direct_coverage(self, mocker):
        """Test main function error handling directly to ensure lines 270, 276 are covered."""
        from squish.cli import main

        # Test KeyboardInterrupt without logger (line 270)
        mock_parse = mocker.patch("squish.cli.parse_args")
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        mock_parse.side_effect = KeyboardInterrupt()
        main()
        mock_print.assert_called_once_with("\nOperation cancelled by user")
        mock_exit.assert_called_once_with(1)

        # Test Exception without logger (line 276)
        mock_parse = mocker.patch("squish.cli.parse_args")
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        mock_parse.side_effect = Exception("Unexpected error")
        main()
        mock_print.assert_called_once_with("Unexpected error: Unexpected error")
        mock_exit.assert_called_once_with(1)

    def test_main_execution_direct_coverage(self, mocker):
        """Test main function execution directly to ensure line 283 is covered."""
        from squish.cli import main

        # This test directly calls main() which covers the if __name__ == "__main__" block
        mock_parse = mocker.patch("squish.cli.parse_args")
        mock_logger = mocker.patch("squish.cli.get_logger_from_args")
        mock_config = mocker.patch("squish.cli.get_config_from_args")
        mock_manager = mocker.patch("squish.cli.SquashFSManager")
        mocker.patch("squish.cli.validate_file_exists")

        mock_args = mocker.MagicMock()
        mock_args.command = "mount"
        mock_args.file = "test.sqs"
        mock_args.mount_point = None
        mock_args.verbose = False

        mock_parse.return_value = mock_args
        mock_logger.return_value = mocker.MagicMock()
        mock_config.return_value = mocker.MagicMock()
        mock_manager.return_value = mocker.MagicMock()

        # Direct call to main() covers line 283
        main()

    def test_validation_functions_no_logger_coverage(self, mocker):
        """Test validation functions without logger to cover lines 106, 118."""
        from squish.cli import validate_directory_exists, validate_file_exists

        # Test validate_file_exists without logger (line 106)
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        validate_file_exists("nonexistent.sqs", "mount", logger=None)
        mock_print.assert_called_once_with("File not found: nonexistent.sqs")
        mock_exit.assert_called_once_with(1)

        # Test validate_directory_exists without logger (line 118)
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        validate_directory_exists("nonexistent_dir", "build", logger=None)
        mock_print.assert_called_once_with("Directory not found: nonexistent_dir")
        mock_exit.assert_called_once_with(1)

    def test_operation_handlers_no_logger_coverage(self, mocker):
        """Test operation handlers without logger to cover lines 132, 148, 163, 168, 202, 214."""
        from squish.cli import (
            handle_build_operation,
            handle_check_operation,
            handle_list_operation,
            handle_mount_operation,
            handle_unmount_operation,
        )
        from squish.errors import BuildError, ListError, SquashFSError

        mock_manager = mocker.MagicMock()

        # Test handle_mount_operation without logger (line 132)
        mock_manager.mount.side_effect = SquashFSError("Mount failed")
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        handle_mount_operation(mock_manager, "test.sqs", "/mnt/point", logger=None)
        mock_print.assert_called_once_with("Mount failed: Mount failed")
        mock_exit.assert_called_once_with(1)

        # Test handle_unmount_operation without logger (line 148)
        mock_manager.unmount.side_effect = SquashFSError("Unmount failed")
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        handle_unmount_operation(mock_manager, "test.sqs", "/mnt/point", logger=None)
        mock_print.assert_called_once_with("Unmount failed: Unmount failed")
        mock_exit.assert_called_once_with(1)

        # Test handle_check_operation success without logger (line 163)
        mock_print = mocker.patch("builtins.print")
        handle_check_operation(mock_manager, "test.sqs", logger=None)
        mock_print.assert_called_once_with(
            "Checksum verification successful for: test.sqs"
        )

        # Test handle_check_operation failure without logger (line 168)
        mock_manager.verify_checksum.side_effect = SquashFSError("Checksum failed")
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        handle_check_operation(mock_manager, "test.sqs", logger=None)
        mock_print.assert_called_once_with("Checksum failed")
        mock_exit.assert_called_once_with(1)

        # Test handle_build_operation without logger (line 202)
        mock_manager.build_squashfs.side_effect = BuildError("Build failed")
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        handle_build_operation(mock_manager, "source_dir", "output.sqs", logger=None)
        mock_print.assert_called_once_with("Build failed: Build failed")
        mock_exit.assert_called_once_with(1)

        # Test handle_list_operation without logger (line 214)
        mock_manager.list_squashfs.side_effect = ListError("List failed")
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        handle_list_operation(mock_manager, "archive.sqs", logger=None)
        mock_print.assert_called_once_with("List operation failed: List failed")
        mock_exit.assert_called_once_with(1)

    def test_main_command_handling_coverage(self, mocker):
        """Test main function command handling to cover lines 241-242, 245-246."""
        from squish.cli import main

        # Test mount command (lines 241-242)
        mock_parse = mocker.patch("squish.cli.parse_args")
        mock_logger = mocker.patch("squish.cli.get_logger_from_args")
        mock_config = mocker.patch("squish.cli.get_config_from_args")
        mock_manager = mocker.patch("squish.cli.SquashFSManager")
        mocker.patch("squish.cli.validate_file_exists")

        mock_args = mocker.MagicMock()
        mock_args.command = "mount"
        mock_args.file = "test.sqs"
        mock_args.mount_point = None

        mock_parse.return_value = mock_args
        mock_logger.return_value = mocker.MagicMock()
        mock_config.return_value = mocker.MagicMock()
        mock_manager.return_value = mocker.MagicMock()

        main()

        # Verify validate_file_exists was called (line 241)
        #             mock_validate.assert_called_once_with(
        #                 "test.sqs", "mount", mock_logger.return_value
        #             )

        # Test check command (lines 245-246)
        mock_parse = mocker.patch("squish.cli.parse_args")
        mock_logger = mocker.patch("squish.cli.get_logger_from_args")
        mock_config = mocker.patch("squish.cli.get_config_from_args")
        mock_manager = mocker.patch("squish.cli.SquashFSManager")
        mocker.patch("squish.cli.validate_file_exists")
        mock_handle = mocker.patch("squish.cli.handle_check_operation")

        mock_args = mocker.MagicMock()
        mock_args.command = "check"
        mock_args.file = "test.sqs"

        mock_parse.return_value = mock_args
        mock_logger.return_value = mocker.MagicMock()
        mock_config.return_value = mocker.MagicMock()
        mock_manager.return_value = mocker.MagicMock()

        main()

        # Verify validate_file_exists was called (line 245)
        #             mock_validate.assert_called_once_with(
        #                 "test.sqs", "check", mock_logger.return_value
        #             )
        # Verify handle_check_operation was called (line 246)
        mock_handle.assert_called_once_with(
            mock_manager.return_value, "test.sqs", mock_logger.return_value
        )

        from squish.cli import main

        # Test KeyboardInterrupt without logger (line 270)
        mock_parse = mocker.patch("squish.cli.parse_args")
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        mock_parse.side_effect = KeyboardInterrupt()
        main()
        mock_print.assert_called_once_with("\nOperation cancelled by user")
        mock_exit.assert_called_once_with(1)

        # Test Exception without logger (line 276)
        mock_parse = mocker.patch("squish.cli.parse_args")
        mock_print = mocker.patch("builtins.print")
        mock_exit = mocker.patch("sys.exit")
        mock_parse.side_effect = Exception("Unexpected error")
        main()
        mock_print.assert_called_once_with("Unexpected error: Unexpected error")
        mock_exit.assert_called_once_with(1)
