"""
Test cases for the MockFactory and MockBuilder classes.
"""

import pytest

from squish.command_executor import ICommandExecutor
from squish.mock_factory import MockFactory
from squish.observer import (
    IProgressObserver,
    OperationType,
    ProgressInfo,
    ProgressState,
)
from squish.tool_adapters import IMksquashfsAdapter, ISha256sumAdapter


class TestMockFactory:
    """Test cases for MockFactory class."""

    def test_create_basic_mock(self, mocker):
        """Test creating a basic mock instance."""
        factory = MockFactory()
        mock = factory.create_mock(ICommandExecutor)

        assert isinstance(mock, mocker.MagicMock)
        assert hasattr(mock, "execute")

    def test_create_mock_with_behavior(self, mocker):
        """Test creating a mock with predefined behavior."""
        factory = MockFactory()
        behavior = {"execute": mocker.MagicMock(return_value="test_result")}
        mock = factory.create_mock_with_behavior(ICommandExecutor, behavior)

        assert mock.execute() == "test_result"

    def test_create_progress_mock(self):
        """Test creating a progress mock."""
        factory = MockFactory()
        progress_values = []
        mock = factory.create_progress_mock(progress_values)

        # Test progress update
        test_progress = ProgressInfo(
            operation_type=OperationType.BUILD,
            state=ProgressState.IN_PROGRESS,
            percentage=50,
            current=50,
            total=100,
            message="Test progress",
        )
        mock.on_progress_update(test_progress)

        # Verify the mock was called and the side effect worked
        assert mock.on_progress_update.called
        assert len(progress_values) == 1
        assert progress_values[0] == 50

    def test_create_command_executor_mock(self):
        """Test creating a command executor mock."""
        factory = MockFactory()
        return_values = {"mksquashfs": "build_result"}
        mock = factory.create_command_executor_mock(return_values=return_values)

        result = mock.execute(["mksquashfs", "source", "output.sqsh"])
        assert result == "build_result"

    def test_create_tool_adapter_mock(self, mocker):
        """Test creating a tool adapter mock."""
        factory = MockFactory()
        behavior = {"build": mocker.MagicMock(return_value="build_success")}
        mock = factory.create_tool_adapter_mock(IMksquashfsAdapter, behavior)

        assert mock.build() == "build_success"

    def test_create_mksquashfs_mock(self):
        """Test creating a mksquashfs mock."""
        factory = MockFactory()
        mock = factory.create_mksquashfs_mock(build_return="success")

        assert mock.build() == "success"

    def test_create_unsquashfs_mock(self):
        """Test creating an unsquashfs mock."""
        factory = MockFactory()
        mock = factory.create_unsquashfs_mock(extract_return="success")

        assert mock.extract() == "success"

    def test_create_zenity_mock(self):
        """Test creating a Zenity mock."""
        factory = MockFactory()
        progress_values = []
        mock = factory.create_zenity_mock(
            progress_values=progress_values, cancelled=False
        )

        mock.update_progress(75, "Processing...")
        assert 75 in progress_values
        assert not mock.check_cancelled()

    def test_track_mocks(self):
        """Test that mocks are properly tracked."""
        factory = MockFactory()
        mock1 = factory.create_mock(ICommandExecutor)
        mock2 = factory.create_mock(IProgressObserver)

        command_mocks = factory.get_created_mocks(ICommandExecutor)
        progress_mocks = factory.get_created_mocks(IProgressObserver)

        assert len(command_mocks) == 1
        assert len(progress_mocks) == 1
        assert command_mocks[0] == mock1
        assert progress_mocks[0] == mock2

    def test_verify_mock_calls(self):
        """Test mock call verification."""
        factory = MockFactory()
        mock = factory.create_mock(ICommandExecutor)

        # Call the method
        mock.execute(["test", "command"])

        # Verify it was called once
        assert factory.verify_mock_calls(mock, "execute", expected_calls=1)
        assert not factory.verify_mock_calls(mock, "execute", expected_calls=2)

    def test_reset_factory(self):
        """Test factory reset functionality."""
        factory = MockFactory()
        factory.create_mock(ICommandExecutor)

        assert len(factory.get_all_created_mocks()) == 1

        factory.reset()

        assert len(factory.get_all_created_mocks()) == 0


class TestMockBuilder:
    """Test cases for MockBuilder class."""

    def test_builder_basic_functionality(self):
        """Test basic builder functionality."""
        factory = MockFactory()
        builder = factory.create_mock_builder()

        scenario = (
            builder.with_name("test_scenario")
            .with_mock(ICommandExecutor)
            .with_progress_mock()
            .build()
        )

        assert scenario["name"] == "test_scenario"
        assert scenario["count"] == 2
        assert len(scenario["mocks"]) == 2

    def test_builder_with_behavior(self, mocker):
        """Test builder with behavior configuration."""
        factory = MockFactory()
        builder = factory.create_mock_builder()

        behavior = {"execute": mocker.MagicMock(return_value="test_result")}

        scenario = builder.with_mock(ICommandExecutor, behavior).build()

        mock = scenario["mocks"][0]
        assert mock.execute() == "test_result"

    def test_builder_complex_scenario(self):
        """Test building a complex scenario with multiple components."""
        factory = MockFactory()
        builder = factory.create_mock_builder()

        scenario = (
            builder.with_name("complex_scenario")
            .with_command_executor(return_values={"mksquashfs": "build_success"})
            .with_mksquashfs_mock(build_return="success")
            .with_unsquashfs_mock(extract_return="success")
            .with_zenity_mock(cancelled=False)
            .build()
        )

        assert scenario["name"] == "complex_scenario"
        assert scenario["count"] == 4
        assert len(scenario["mocks"]) == 4

    def test_builder_verify_all(self):
        """Test builder verification functionality."""
        factory = MockFactory()
        builder = factory.create_mock_builder()

        # Create mocks and call their methods
        mock1 = factory.create_mock(ICommandExecutor)
        mock2 = factory.create_mock(ICommandExecutor)

        mock1.execute(["test"])
        mock2.execute(["test"])

        # Add mocks to builder
        builder._mocks = [mock1, mock2]

        # Verify all were called
        assert builder.verify_all("execute", expected_calls=1)

    def test_builder_reset(self):
        """Test builder reset functionality."""
        factory = MockFactory()
        builder = factory.create_mock_builder()

        # Build a scenario
        builder.with_mock(ICommandExecutor).build()

        # Builder should be reset after build
        assert builder.get_mocks() == []
        assert builder._scenario_name is None


class TestMockFactoryIntegration:
    """Integration tests for MockFactory with other components."""

    def test_factory_with_di_container(self):
        """Test MockFactory integration with DI container."""
        from squish.dependency_injection import TestDIContainer

        factory = MockFactory()
        di_container = TestDIContainer()

        # Create a mock and register it with DI container
        mock_executor = factory.create_mock(ICommandExecutor)
        di_container.register_mock(ICommandExecutor, mock_executor)

        # Verify the mock can be resolved
        resolved = di_container.resolve(ICommandExecutor)
        assert resolved == mock_executor

    def test_factory_with_progress_observer(self):
        """Test MockFactory with progress observer integration."""
        factory = MockFactory()

        # Create a progress mock
        progress_values = []
        mock_observer = factory.create_progress_mock(progress_values)

        # Test progress updates
        progress1 = ProgressInfo(
            operation_type=OperationType.BUILD,
            state=ProgressState.IN_PROGRESS,
            percentage=25,
            current=25,
            total=100,
            message="First update",
        )

        progress2 = ProgressInfo(
            operation_type=OperationType.BUILD,
            state=ProgressState.IN_PROGRESS,
            percentage=75,
            current=75,
            total=100,
            message="Second update",
        )

        mock_observer.on_progress_update(progress1)
        mock_observer.on_progress_update(progress2)

        assert len(progress_values) == 2
        assert progress_values[0] == 25
        assert progress_values[1] == 75

    def test_factory_with_tool_adapters(self, mocker):
        """Test MockFactory with tool adapter integration."""
        factory = MockFactory()

        # Create various tool adapter mocks
        mksquashfs_mock = factory.create_mksquashfs_mock(build_return="build_success")
        unsquashfs_mock = factory.create_unsquashfs_mock(
            extract_return="extract_success"
        )
        sha256sum_mock = factory.create_tool_adapter_mock(
            ISha256sumAdapter,
            {"generate_checksum": mocker.MagicMock(return_value="abc123")},
        )
        zenity_mock = factory.create_zenity_mock(cancelled=False)

        # Test the mocks
        assert mksquashfs_mock.build() == "build_success"
        assert unsquashfs_mock.extract() == "extract_success"
        assert sha256sum_mock.generate_checksum() == "abc123"
        assert not zenity_mock.check_cancelled()


class TestMockFactoryEdgeCases:
    """Edge case tests for MockFactory."""

    def test_unsupported_adapter_type(self):
        """Test error handling for unsupported adapter types."""
        factory = MockFactory()

        # Create a fake interface that's not supported
        class FakeAdapter:
            pass

        with pytest.raises(ValueError, match="Unsupported adapter type"):
            factory.create_tool_adapter_mock(FakeAdapter)

    def test_mock_with_exception_behavior(self):
        """Test mock with exception behavior."""
        factory = MockFactory()

        test_exception = Exception("Test exception")
        mock = factory.create_mock_with_behavior(
            ICommandExecutor, {"execute": test_exception}
        )

        with pytest.raises(Exception, match="Test exception"):
            mock.execute()

    def test_verify_mock_calls_with_args(self):
        """Test mock call verification with arguments."""
        factory = MockFactory()
        mock = factory.create_mock(ICommandExecutor)

        # Call with specific arguments
        mock.execute(["mksquashfs", "source", "output.sqsh"], check=True)

        # Verify with arguments
        assert factory.verify_mock_calls(
            mock,
            "execute",
            expected_calls=1,
            args=(["mksquashfs", "source", "output.sqsh"],),
            kwargs={"check": True},
        )

    def test_empty_factory(self):
        """Test factory behavior when no mocks are created."""
        factory = MockFactory()

        assert len(factory.get_all_created_mocks()) == 0
        assert factory.get_created_mocks(ICommandExecutor) == []
        assert factory.verify_all_mock_calls(
            ICommandExecutor, "execute"
        )  # Vacously true


class TestMockFactoryPerformance:
    """Performance tests for MockFactory."""

    def test_bulk_mock_creation(self):
        """Test creating many mocks efficiently."""
        factory = MockFactory()

        # Create 100 mocks
        for i in range(100):
            factory.create_mock(ICommandExecutor)

        # Verify all were tracked
        assert len(factory.get_created_mocks(ICommandExecutor)) == 100

    def test_builder_reuse(self):
        """Test reusing builder for multiple scenarios."""
        factory = MockFactory()
        builder = factory.create_mock_builder()

        # Build multiple scenarios
        scenario1 = builder.with_name("scenario1").with_mock(ICommandExecutor).build()
        scenario2 = builder.with_name("scenario2").with_mock(IProgressObserver).build()

        assert scenario1["name"] == "scenario1"
        assert scenario2["name"] == "scenario2"
        assert len(scenario1["mocks"]) == 1
        assert len(scenario2["mocks"]) == 1
