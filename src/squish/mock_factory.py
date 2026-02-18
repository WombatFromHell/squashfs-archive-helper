"""
Mock Factory for the SquashFS Archive Helper.

This module provides a comprehensive mock factory system for creating and managing
mock implementations of interfaces during testing. It includes:

- MockFactory class for creating mock instances
- Behavior configuration support
- Mock builders for complex scenarios
- Mock verification utilities
- Integration with the DI container system
"""

from typing import Any, Dict, List, Optional, Type, TypeVar
from unittest.mock import MagicMock, patch

from .command_executor import ICommandExecutor
from .observer import IProgressObserver
from .tool_adapters import (
    IMksquashfsAdapter,
    ISha256sumAdapter,
    IUnsquashfsAdapter,
    IZenityAdapter,
)

T = TypeVar("T")


class MockFactory:
    """
    Comprehensive mock factory for creating and managing mock implementations.

    This factory provides methods for creating mocks with predefined behaviors,
    complex scenario builders, and verification utilities.
    """

    def __init__(self):
        """Initialize the mock factory."""
        self._created_mocks: Dict[Type[Any], List[Any]] = {}
        self._behavior_configs: Dict[Type[Any], Dict[str, Any]] = {}

    def create_mock(self, interface: Type[T], **kwargs) -> MagicMock:
        """
        Create a basic mock instance for the given interface.

        Args:
            interface: The interface type to mock
            **kwargs: Additional arguments to pass to MagicMock

        Returns:
            MagicMock instance configured for the interface
        """
        mock = MagicMock(spec=interface, **kwargs)
        self._track_mock(interface, mock)
        return mock

    def create_mock_with_behavior(
        self, interface: Type[T], behavior: Dict[str, Any], **kwargs
    ) -> MagicMock:
        """
        Create a mock instance with predefined behavior.

        Args:
            interface: The interface type to mock
            behavior: Dictionary mapping method names to return values or side effects
            **kwargs: Additional arguments to pass to MagicMock

        Returns:
            MagicMock instance with configured behavior
        """
        mock = self.create_mock(interface, **kwargs)

        for method_name, config in behavior.items():
            if hasattr(mock, method_name):
                method = getattr(mock, method_name)

                if isinstance(config, Exception):
                    method.side_effect = config
                elif callable(config):
                    method.side_effect = config
                else:
                    method.return_value = config

        self._behavior_configs[interface] = behavior
        return mock

    def create_progress_mock(
        self, progress_values: Optional[List[int]] = None, **kwargs
    ) -> MagicMock:
        """
        Create a mock progress observer with predefined progress values.

        Args:
            progress_values: List of progress percentages to return
            **kwargs: Additional arguments to pass to MagicMock

        Returns:
            MagicMock instance configured as IProgressObserver
        """
        mock = self.create_mock(IProgressObserver, **kwargs)

        if progress_values is not None:
            mock.on_progress_update.side_effect = lambda progress: (
                progress_values.append(progress.percentage)
            )

        return mock

    def create_command_executor_mock(
        self,
        return_values: Optional[Dict[str, Any]] = None,
        side_effects: Optional[Dict[str, Exception]] = None,
        **kwargs,
    ) -> MagicMock:
        """
        Create a mock command executor with configurable behavior.

        Args:
            return_values: Dictionary mapping command patterns to return values
            side_effects: Dictionary mapping command patterns to exceptions
            **kwargs: Additional arguments to pass to MagicMock

        Returns:
            MagicMock instance configured as ICommandExecutor
        """
        mock = self.create_mock(ICommandExecutor, **kwargs)

        def execute_side_effect(command: list[str], **exec_kwargs):
            command_str = " ".join(command)

            # Check for side effects first
            if side_effects:
                for pattern, exception in side_effects.items():
                    if pattern in command_str:
                        raise exception

            # Check for return values
            if return_values:
                for pattern, return_value in return_values.items():
                    if pattern in command_str:
                        return return_value

            # Default behavior
            return MagicMock()

        mock.execute.side_effect = execute_side_effect
        return mock

    def create_tool_adapter_mock(
        self,
        adapter_type: Type[T],
        method_behaviors: Optional[Dict[str, Any]] = None,
        **kwargs,
    ) -> MagicMock:
        """
        Create a mock tool adapter with configurable method behaviors.

        Args:
            adapter_type: The tool adapter interface type
            method_behaviors: Dictionary mapping method names to behaviors
            **kwargs: Additional arguments to pass to MagicMock

        Returns:
            MagicMock instance configured as the specified tool adapter
        """
        if adapter_type not in [
            IMksquashfsAdapter,
            IUnsquashfsAdapter,
            ISha256sumAdapter,
            IZenityAdapter,
        ]:
            raise ValueError(f"Unsupported adapter type: {adapter_type}")

        mock = self.create_mock(adapter_type, **kwargs)

        if method_behaviors:
            for method_name, behavior in method_behaviors.items():
                if hasattr(mock, method_name):
                    method = getattr(mock, method_name)

                    if isinstance(behavior, Exception):
                        method.side_effect = behavior
                    elif callable(behavior):
                        method.side_effect = behavior
                    else:
                        method.return_value = behavior

        return mock

    def create_mksquashfs_mock(
        self,
        build_return: Any = None,
        build_side_effect: Optional[Exception] = None,
        **kwargs,
    ) -> MagicMock:
        """
        Create a mock mksquashfs adapter.

        Args:
            build_return: Return value for build method
            build_side_effect: Exception to raise for build method
            **kwargs: Additional arguments to pass to MagicMock

        Returns:
            MagicMock instance configured as IMksquashfsAdapter
        """
        mock = self.create_mock(IMksquashfsAdapter, **kwargs)

        if build_side_effect:
            mock.build.side_effect = build_side_effect
        else:
            mock.build.return_value = build_return

        return mock

    def create_unsquashfs_mock(
        self,
        extract_return: Any = None,
        extract_side_effect: Optional[Exception] = None,
        **kwargs,
    ) -> MagicMock:
        """
        Create a mock unsquashfs adapter.

        Args:
            extract_return: Return value for extract method
            extract_side_effect: Exception to raise for extract method
            **kwargs: Additional arguments to pass to MagicMock

        Returns:
            MagicMock instance configured as IUnsquashfsAdapter
        """
        mock = self.create_mock(IUnsquashfsAdapter, **kwargs)

        if extract_side_effect:
            mock.extract.side_effect = extract_side_effect
        else:
            mock.extract.return_value = extract_return

        return mock

    def create_zenity_mock(
        self,
        progress_values: Optional[List[int]] = None,
        cancelled: bool = False,
        **kwargs,
    ) -> MagicMock:
        """
        Create a mock Zenity adapter.

        Args:
            progress_values: List of progress values to return
            cancelled: Whether to simulate user cancellation
            **kwargs: Additional arguments to pass to MagicMock

        Returns:
            MagicMock instance configured as IZenityAdapter
        """
        mock = self.create_mock(IZenityAdapter, **kwargs)

        if progress_values is not None:
            mock.update_progress.side_effect = lambda percentage, status: (
                progress_values.append(percentage)
            )

        mock.check_cancelled.return_value = cancelled

        return mock

    def _track_mock(self, interface: Type[T], mock: Any) -> None:
        """Track created mocks for verification and cleanup."""
        if interface not in self._created_mocks:
            self._created_mocks[interface] = []
        self._created_mocks[interface].append(mock)

    def get_created_mocks(self, interface: Type[T]) -> List[Any]:
        """
        Get all created mocks for a specific interface.

        Args:
            interface: The interface type

        Returns:
            List of mock instances for the interface
        """
        return self._created_mocks.get(interface, [])

    def get_all_created_mocks(self) -> Dict[Type[Any], List[Any]]:
        """
        Get all created mocks across all interfaces.

        Returns:
            Dictionary mapping interface types to lists of mock instances
        """
        return self._created_mocks

    def verify_mock_calls(
        self, mock: Any, method_name: str, expected_calls: int = 1, **call_args
    ) -> bool:
        """
        Verify that a mock method was called the expected number of times.

        Args:
            mock: The mock instance to verify
            method_name: Name of the method to verify
            expected_calls: Expected number of calls
            **call_args: Expected call arguments for verification

        Returns:
            True if verification passes, False otherwise
        """
        if not hasattr(mock, method_name):
            return False

        method = getattr(mock, method_name)

        if method.call_count != expected_calls:
            return False

        if call_args:
            # Verify call arguments
            if expected_calls > 0:
                last_call_args = method.call_args

                # Check positional arguments
                if "args" in call_args:
                    if last_call_args.args != call_args["args"]:
                        return False

                # Check keyword arguments
                if "kwargs" in call_args:
                    if last_call_args.kwargs != call_args["kwargs"]:
                        return False

        return True

    def verify_all_mock_calls(
        self, interface: Type[T], method_name: str, expected_calls: int = 1, **call_args
    ) -> bool:
        """
        Verify that all mocks of a specific interface had their method called.

        Args:
            interface: The interface type
            method_name: Name of the method to verify
            expected_calls: Expected number of calls per mock
            **call_args: Expected call arguments for verification

        Returns:
            True if all verifications pass, False otherwise
        """
        mocks = self.get_created_mocks(interface)
        return all(
            self.verify_mock_calls(mock, method_name, expected_calls, **call_args)
            for mock in mocks
        )

    def reset(self) -> None:
        """Reset the mock factory, clearing all tracked mocks and configurations."""
        self._created_mocks.clear()
        self._behavior_configs.clear()

    def create_context_manager(self, mock_target: str, **kwargs) -> Any:
        """
        Create a context manager for patching objects during testing.

        Args:
            mock_target: Target to patch (e.g., "module.Class.method")
            **kwargs: Arguments to pass to patch()

        Returns:
            Context manager for use with 'with' statement
        """
        return patch(mock_target, **kwargs)

    def create_mock_builder(self) -> "MockBuilder":
        """
        Create a mock builder for complex scenario construction.

        Returns:
            MockBuilder instance
        """
        return MockBuilder(self)


class MockBuilder:
    """
    Builder class for constructing complex mock scenarios.

    This builder allows for fluent construction of mock scenarios with
    multiple components and behaviors.
    """

    def __init__(self, factory: MockFactory):
        """Initialize the mock builder with a factory."""
        self._factory = factory
        self._mocks: List[Any] = []
        self._scenario_name: Optional[str] = None

    def with_name(self, name: str) -> "MockBuilder":
        """Set a name for this mock scenario."""
        self._scenario_name = name
        return self

    def with_mock(
        self, interface: Type[T], behavior: Optional[Dict[str, Any]] = None
    ) -> "MockBuilder":
        """Add a mock with optional behavior to the scenario."""
        if behavior:
            mock = self._factory.create_mock_with_behavior(interface, behavior)
        else:
            mock = self._factory.create_mock(interface)

        self._mocks.append(mock)
        return self

    def with_progress_mock(
        self, progress_values: Optional[List[int]] = None
    ) -> "MockBuilder":
        """Add a progress mock to the scenario."""
        mock = self._factory.create_progress_mock(progress_values)
        self._mocks.append(mock)
        return self

    def with_command_executor(
        self,
        return_values: Optional[Dict[str, Any]] = None,
        side_effects: Optional[Dict[str, Exception]] = None,
    ) -> "MockBuilder":
        """Add a command executor mock to the scenario."""
        mock = self._factory.create_command_executor_mock(return_values, side_effects)
        self._mocks.append(mock)
        return self

    def with_mksquashfs_mock(
        self, build_return: Any = None, build_side_effect: Optional[Exception] = None
    ) -> "MockBuilder":
        """Add a mksquashfs adapter mock to the scenario."""
        mock = self._factory.create_mksquashfs_mock(build_return, build_side_effect)
        self._mocks.append(mock)
        return self

    def with_unsquashfs_mock(
        self,
        extract_return: Any = None,
        extract_side_effect: Optional[Exception] = None,
    ) -> "MockBuilder":
        """Add an unsquashfs adapter mock to the scenario."""
        mock = self._factory.create_unsquashfs_mock(extract_return, extract_side_effect)
        self._mocks.append(mock)
        return self

    def with_zenity_mock(
        self, progress_values: Optional[List[int]] = None, cancelled: bool = False
    ) -> "MockBuilder":
        """Add a Zenity adapter mock to the scenario."""
        mock = self._factory.create_zenity_mock(progress_values, cancelled)
        self._mocks.append(mock)
        return self

    def build(self) -> Dict[str, Any]:
        """
        Build the mock scenario and return the created mocks.

        Returns:
            Dictionary containing scenario information and mocks
        """
        scenario = {
            "name": self._scenario_name,
            "mocks": self._mocks,
            "count": len(self._mocks),
        }

        # Reset for next scenario
        self._mocks = []
        self._scenario_name = None

        return scenario

    def get_mocks(self) -> List[Any]:
        """Get the list of mocks in this scenario."""
        return self._mocks

    def verify_all(self, method_name: str, expected_calls: int = 1) -> bool:
        """
        Verify that all mocks in this scenario had their method called.

        Args:
            method_name: Name of the method to verify
            expected_calls: Expected number of calls per mock

        Returns:
            True if all verifications pass, False otherwise
        """
        return all(
            self._factory.verify_mock_calls(mock, method_name, expected_calls)
            for mock in self._mocks
        )
