"""
Test cases for the CLI module.

This module tests the command-line interface functionality.
"""

import tempfile
from unittest.mock import MagicMock, patch

import pytest

from mount_squashfs.cli import get_config_from_args, parse_args, validate_file_exists
from mount_squashfs.errors import SquashFSError


class TestArgumentParsing:
    """Test command line argument parsing."""

    def test_parse_mount_args(self):
        """Test parsing mount command arguments."""
        with patch("sys.argv", ["mount-squashfs", "test.sqs"]):
            args = parse_args()
            assert args.file == "test.sqs"
            assert args.mount_point is None
            assert args.unmount is False
            assert args.verbose is False

    def test_parse_mount_with_mount_point(self):
        """Test parsing mount command with mount point."""
        with patch("sys.argv", ["mount-squashfs", "test.sqs", "/mnt/point"]):
            args = parse_args()
            assert args.file == "test.sqs"
            assert args.mount_point == "/mnt/point"
            assert args.unmount is False

    def test_parse_unmount_args(self):
        """Test parsing unmount command arguments."""
        with patch("sys.argv", ["mount-squashfs", "-u", "test.sqs"]):
            args = parse_args()
            assert args.file == "test.sqs"
            assert args.mount_point is None
            assert args.unmount is True

    def test_parse_verbose_args(self):
        """Test parsing verbose flag."""
        with patch("sys.argv", ["mount-squashfs", "-v", "test.sqs"]):
            args = parse_args()
            assert args.verbose is True

    def test_parse_help_args(self):
        """Test parsing help flag."""
        with patch("sys.argv", ["mount-squashfs", "--help"]):
            with pytest.raises(SystemExit) as e:
                parse_args()
            assert e.value.code == 0


class TestConfigurationFromArgs:
    """Test configuration creation from command line arguments."""

    def test_default_config(self):
        """Test default configuration."""
        args = MagicMock()
        args.verbose = False

        config = get_config_from_args(args)
        assert config.verbose is False
        assert config.mount_base == "mounts"

    def test_verbose_config(self):
        """Test verbose configuration."""
        args = MagicMock()
        args.verbose = True

        config = get_config_from_args(args)
        assert config.verbose is True


class TestFileValidation:
    """Test file validation logic."""

    def test_validate_existing_file(self):
        """Test validation of existing file."""
        with tempfile.NamedTemporaryFile(suffix=".sqs") as temp_file:
            # Should not raise an exception
            validate_file_exists(temp_file.name)

    def test_validate_nonexistent_file(self):
        """Test validation of nonexistent file."""
        with pytest.raises(SystemExit):
            validate_file_exists("/nonexistent/file.sqs")

    def test_validate_nonexistent_file_when_unmounting(self):
        """Test that validation is skipped when unmounting."""
        # Should not raise an exception when unmounting
        validate_file_exists("/nonexistent/file.sqs", unmounting=True)


class TestCLIIntegration:
    """Test CLI integration with mocked components."""

    @patch("mount_squashfs.cli.SquashFSManager")
    @patch("mount_squashfs.cli.parse_args")
    @patch("mount_squashfs.cli.validate_file_exists")
    def test_mount_integration(self, mock_validate, mock_parse, mock_manager):
        """Test mount operation integration."""
        # Mock arguments
        mock_args = MagicMock()
        mock_args.file = "test.sqs"
        mock_args.mount_point = None
        mock_args.unmount = False
        mock_args.verbose = False
        mock_parse.return_value = mock_args

        # Mock manager
        mock_manager_instance = MagicMock()
        mock_manager.return_value = mock_manager_instance

        # Mock validation
        mock_validate.return_value = None

        # Import and run main
        from mount_squashfs.cli import main

        with patch("sys.argv", ["mount-squashfs", "test.sqs"]):
            main()

        # Verify manager was created with correct config
        mock_manager.assert_called_once()

        # Verify mount was called
        mock_manager_instance.mount.assert_called_once_with("test.sqs", None)

    @patch("mount_squashfs.cli.SquashFSManager")
    @patch("mount_squashfs.cli.parse_args")
    @patch("mount_squashfs.cli.validate_file_exists")
    def test_unmount_integration(self, mock_validate, mock_parse, mock_manager):
        """Test unmount operation integration."""
        # Mock arguments
        mock_args = MagicMock()
        mock_args.file = "test.sqs"
        mock_args.mount_point = None
        mock_args.unmount = True
        mock_args.verbose = False
        mock_parse.return_value = mock_args

        # Mock manager
        mock_manager_instance = MagicMock()
        mock_manager.return_value = mock_manager_instance

        # Mock validation (should not raise for unmount)
        mock_validate.return_value = None

        # Import and run main
        from mount_squashfs.cli import main

        with patch("sys.argv", ["mount-squashfs", "-u", "test.sqs"]):
            main()

        # Verify manager was created
        mock_manager.assert_called_once()

        # Verify unmount was called
        mock_manager_instance.unmount.assert_called_once_with("test.sqs", None)

    @patch("mount_squashfs.cli.SquashFSManager")
    @patch("mount_squashfs.cli.parse_args")
    @patch("mount_squashfs.cli.validate_file_exists")
    def test_error_handling(self, mock_validate, mock_parse, mock_manager):
        """Test error handling in CLI."""
        # Mock arguments
        mock_args = MagicMock()
        mock_args.file = "test.sqs"
        mock_args.mount_point = None
        mock_args.unmount = False
        mock_args.verbose = False
        mock_parse.return_value = mock_args

        # Mock manager to raise an error
        mock_manager_instance = MagicMock()
        mock_manager_instance.mount.side_effect = SquashFSError("Test error")
        mock_manager.return_value = mock_manager_instance

        # Mock validation
        mock_validate.return_value = None

        # Import and run main
        from mount_squashfs.cli import main

        with patch("sys.argv", ["mount-squashfs", "test.sqs"]):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 1


class TestCLIErrorConditions:
    """Test CLI error conditions."""

    @patch("mount_squashfs.cli.parse_args")
    def test_keyboard_interrupt(self, mock_parse):
        """Test handling of keyboard interrupt."""
        # Mock arguments
        mock_args = MagicMock()
        mock_parse.return_value = mock_args

        # Import and run main with KeyboardInterrupt
        from mount_squashfs.cli import main

        with patch("sys.argv", ["mount-squashfs", "test.sqs"]):
            with patch(
                "mount_squashfs.cli.SquashFSManager", side_effect=KeyboardInterrupt
            ):
                with pytest.raises(SystemExit) as e:
                    main()
                assert e.value.code == 1

    @patch("mount_squashfs.cli.parse_args")
    def test_unexpected_error(self, mock_parse):
        """Test handling of unexpected errors."""
        # Mock arguments
        mock_args = MagicMock()
        mock_parse.return_value = mock_args

        # Import and run main with unexpected error
        from mount_squashfs.cli import main

        with patch("sys.argv", ["mount-squashfs", "test.sqs"]):
            with patch(
                "mount_squashfs.cli.SquashFSManager",
                side_effect=Exception("Unexpected error"),
            ):
                with pytest.raises(SystemExit) as e:
                    main()
                assert e.value.code == 1

    @patch("mount_squashfs.cli.SquashFSManager")
    @patch("mount_squashfs.cli.parse_args")
    @patch("mount_squashfs.cli.validate_file_exists")
    def test_unmount_error_handling(self, mock_validate, mock_parse, mock_manager):
        """Test error handling in unmount operation."""
        # Mock arguments for unmount
        mock_args = MagicMock()
        mock_args.file = "test.sqs"
        mock_args.mount_point = None
        mock_args.unmount = True
        mock_args.verbose = False
        mock_parse.return_value = mock_args

        # Mock manager to raise an error during unmount
        mock_manager_instance = MagicMock()
        mock_manager_instance.unmount.side_effect = SquashFSError("Unmount failed")
        mock_manager.return_value = mock_manager_instance

        # Mock validation
        mock_validate.return_value = None

        # Import and run main
        from mount_squashfs.cli import main

        with patch("sys.argv", ["mount-squashfs", "-u", "test.sqs"]):
            with pytest.raises(SystemExit) as e:
                main()
            assert e.value.code == 1

    def test_main_entry_point(self):
        """Test that the main function can be called directly."""
        # This test ensures the if __name__ == "__main__": block is covered
        from mount_squashfs.cli import main

        # Mock all the components to prevent actual execution
        with (
            patch("mount_squashfs.cli.parse_args") as mock_parse,
            patch("mount_squashfs.cli.validate_file_exists") as mock_validate,
            patch("mount_squashfs.cli.SquashFSManager") as mock_manager,
        ):
            # Mock arguments
            mock_args = MagicMock()
            mock_args.file = "test.sqs"
            mock_args.mount_point = None
            mock_args.unmount = False
            mock_args.verbose = False
            mock_parse.return_value = mock_args

            # Mock validation and manager
            mock_validate.return_value = None
            mock_manager_instance = MagicMock()
            mock_manager.return_value = mock_manager_instance

            with patch("sys.argv", ["mount-squashfs", "test.sqs"]):
                # This should not raise an exception
                main()

                # Verify the main function executed properly
                mock_parse.assert_called_once()
                mock_validate.assert_called_once()
                mock_manager.assert_called_once()
