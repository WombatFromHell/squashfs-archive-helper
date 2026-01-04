"""
Dependency Injection Container for SquishFS.

This module provides a comprehensive dependency injection container that supports:
- Service registration and resolution
- Factory pattern support
- Singleton lifecycle management
- Interface-based dependency injection
- Error handling for dependency resolution
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional, Type, TypeVar

T = TypeVar("T")


class DependencyResolutionError(Exception):
    """Exception raised when dependency resolution fails."""

    def __init__(self, interface: Type[T], message: str):
        self.interface = interface
        self.message = message
        interface_name = getattr(interface, "__name__", str(interface))
        super().__init__(f"Failed to resolve dependency {interface_name}: {message}")


class DependencyRegistrationError(Exception):
    """Exception raised when dependency registration fails."""

    def __init__(self, interface: Type[T], message: str):
        self.interface = interface
        self.message = message
        super().__init__(
            f"Failed to register dependency {interface.__name__}: {message}"
        )


class IServiceProvider(ABC):
    """Interface for service providers that can be used with the DI container."""

    @abstractmethod
    def get_service(self, interface: Type[T]) -> T:
        """Get a service by its interface type."""
        pass


class DIContainer(IServiceProvider):
    """
    Dependency Injection Container.

    Provides a flexible way to manage dependencies and their lifecycles.
    Supports service registration, factory patterns, and singleton management.
    """

    def __init__(self):
        """Initialize the DI container with empty service registrations."""
        self._services: Dict[Type[Any], Type[Any]] = {}
        self._factories: Dict[Type[Any], Callable[[IServiceProvider], Any]] = {}
        self._singletons: Dict[Type[Any], Any] = {}
        self._service_providers: Dict[str, IServiceProvider] = {}

    def register(
        self, interface: Type[T], implementation: Type[T], singleton: bool = False
    ) -> None:
        """
        Register a service implementation for an interface.

        Args:
            interface: The interface type to register
            implementation: The concrete implementation class
            singleton: Whether to treat this as a singleton

        Raises:
            DependencyRegistrationError: If registration fails
        """
        try:
            if singleton:
                # Create singleton instance immediately
                instance = implementation()
                self._singletons[interface] = instance
            else:
                # Register for instantiation on demand
                self._services[interface] = implementation
        except Exception as e:
            raise DependencyRegistrationError(interface, str(e)) from e

    def register_factory(
        self, interface: Type[T], factory: Callable[[IServiceProvider], T]
    ) -> None:
        """
        Register a factory function for an interface.

        Args:
            interface: The interface type to register
            factory: A factory function that takes a service provider and returns an instance

        Raises:
            DependencyRegistrationError: If registration fails
        """
        try:
            self._factories[interface] = factory
        except Exception as e:
            raise DependencyRegistrationError(interface, str(e)) from e

    def register_singleton(self, interface: Type[T], instance: T) -> None:
        """
        Register an existing instance as a singleton.

        Args:
            interface: The interface type to register
            instance: The instance to register as a singleton

        Raises:
            DependencyRegistrationError: If registration fails
        """
        try:
            self._singletons[interface] = instance
        except Exception as e:
            raise DependencyRegistrationError(interface, str(e)) from e

    def add_service_provider(self, name: str, provider: IServiceProvider) -> None:
        """
        Add an external service provider to the container.

        Args:
            name: Name to identify the provider
            provider: The service provider instance
        """
        self._service_providers[name] = provider

    def get_service_provider(self, name: str) -> Optional[IServiceProvider]:
        """
        Get a registered service provider by name.

        Args:
            name: Name of the service provider

        Returns:
            The service provider if found, None otherwise
        """
        return self._service_providers.get(name)

    def get_service(self, interface: Type[T]) -> T:
        """
        Get a service by its interface type (implements IServiceProvider).

        Args:
            interface: The interface type to resolve

        Returns:
            An instance of the requested interface

        Raises:
            DependencyResolutionError: If resolution fails
        """
        return self.resolve(interface)

    def resolve(self, interface: Type[T]) -> T:
        """
        Resolve a dependency by its interface type.

        Args:
            interface: The interface type to resolve

        Returns:
            An instance of the requested interface

        Raises:
            DependencyResolutionError: If resolution fails
        """
        # Check singletons first
        if interface in self._singletons:
            return self._singletons[interface]

        # Check factories
        if interface in self._factories:
            try:
                return self._factories[interface](self)
            except Exception as e:
                raise DependencyResolutionError(
                    interface, f"Factory failed: {str(e)}"
                ) from e

        # Check services
        if interface in self._services:
            try:
                implementation = self._services[interface]
                return implementation()
            except Exception as e:
                raise DependencyResolutionError(
                    interface, f"Instantiation failed: {str(e)}"
                ) from e

        # Check if any service provider can provide this interface
        for provider in self._service_providers.values():
            try:
                return provider.get_service(interface)
            except (DependencyResolutionError, AttributeError):
                # Try next provider if this one can't provide the service
                continue

        # If we get here, no implementation was found
        raise DependencyResolutionError(interface, "No implementation registered")

    def can_resolve(self, interface: Type[T]) -> bool:
        """
        Check if an interface can be resolved.

        Args:
            interface: The interface type to check

        Returns:
            True if the interface can be resolved, False otherwise
        """
        return (
            interface in self._singletons
            or interface in self._factories
            or interface in self._services
            or any(
                hasattr(provider, "get_service")
                and provider.get_service(interface) is not None
                for provider in self._service_providers.values()
            )
        )

    def get_all_instances(self, interface: Type[T]) -> list[T]:
        """
        Get all registered instances of a given interface.

        Args:
            interface: The interface type to search for

        Returns:
            List of all instances implementing the interface
        """
        instances = []

        # Add singleton if exists
        if interface in self._singletons:
            instances.append(self._singletons[interface])

        # Add instances from service providers
        for provider in self._service_providers.values():
            if hasattr(provider, "get_service"):
                service = provider.get_service(interface)
                if service is not None:
                    instances.append(service)

        return instances

    def clear(self) -> None:
        """Clear all registrations from the container."""
        self._services.clear()
        self._factories.clear()
        self._singletons.clear()
        self._service_providers.clear()

    def get_registration_info(self) -> Dict[str, Any]:
        """
        Get information about current registrations.

        Returns:
            Dictionary containing registration information
        """
        return {
            "services": list(self._services.keys()),
            "factories": list(self._factories.keys()),
            "singletons": list(self._singletons.keys()),
            "service_providers": list(self._service_providers.keys()),
        }


class ScopedDIContainer(DIContainer):
    """
    Scoped Dependency Injection Container.

    Extends DIContainer to support scoped lifecycles for dependencies.
    """

    def __init__(self, parent: Optional[DIContainer] = None):
        """Initialize a scoped container with optional parent container."""
        super().__init__()
        self._parent = parent

    def resolve(self, interface: Type[T]) -> T:
        """
        Resolve a dependency, falling back to parent container if not found.

        Args:
            interface: The interface type to resolve

        Returns:
            An instance of the requested interface

        Raises:
            DependencyResolutionError: If resolution fails in both current and parent containers
        """
        try:
            return super().resolve(interface)
        except DependencyResolutionError:
            if self._parent is not None:
                return self._parent.resolve(interface)
            raise

    def can_resolve(self, interface: Type[T]) -> bool:
        """
        Check if an interface can be resolved in current or parent container.

        Args:
            interface: The interface type to check

        Returns:
            True if the interface can be resolved, False otherwise
        """
        return super().can_resolve(interface) or (
            self._parent is not None and self._parent.can_resolve(interface)
        )


class InterfaceRegistry:
    """
    Registry for managing interface to implementation mappings.

    Provides a way to define and manage interface contracts.
    """

    def __init__(self):
        self._interfaces: Dict[Type[Any], Type[Any]] = {}
        self._implementations: Dict[Type[Any], list[Type[Any]]] = {}

    def register_interface(self, interface: Type[T], implementation: Type[T]) -> None:
        """
        Register an implementation for an interface.

        Args:
            interface: The interface type
            implementation: The implementation class
        """
        self._interfaces[interface] = implementation
        if implementation not in self._implementations:
            self._implementations[implementation] = []
        self._implementations[implementation].append(interface)

    def get_implementation(self, interface: Type[T]) -> Optional[Type[T]]:
        """
        Get the implementation for an interface.

        Args:
            interface: The interface type

        Returns:
            The implementation class if found, None otherwise
        """
        return self._interfaces.get(interface)

    def get_interfaces(self, implementation: Type[T]) -> list[Type[T]]:
        """
        Get all interfaces implemented by a class.

        Args:
            implementation: The implementation class

        Returns:
            List of interfaces implemented by the class
        """
        return self._implementations.get(implementation, [])

    def get_all_interfaces(self) -> list[Type[Any]]:
        """
        Get all registered interfaces.

        Returns:
            List of all registered interface types
        """
        return list(self._interfaces.keys())

    def get_all_implementations(self) -> list[Type[Any]]:
        """
        Get all registered implementation types.

        Returns:
            List of all registered implementation types
        """
        return list(self._implementations.keys())


class TestDIContainer(DIContainer):
    """
    Test-specific Dependency Injection Container.

    Extends DIContainer with testing-specific features including:
    - Mock service registration
    - Test-specific factory methods
    - Convenience methods for common test scenarios
    - Mock verification utilities
    """

    # Prevent pytest from trying to collect this as a test class
    __test__ = False

    def __init__(self):
        """Initialize the test DI container with test-specific setup."""
        super().__init__()
        self._mock_services: Dict[Type[Any], Any] = {}
        self._mock_behaviors: Dict[Type[Any], Dict[str, Any]] = {}
        self._setup_test_dependencies()

    def _setup_test_dependencies(self) -> None:
        """Set up default test dependencies and mock services."""
        # This will be implemented with actual mock services
        pass

    def register_mock(
        self, interface: Type[T], mock_instance: T, singleton: bool = True
    ) -> None:
        """
        Register a mock instance for an interface.

        Args:
            interface: The interface type to mock
            mock_instance: The mock instance to register
            singleton: Whether to treat this as a singleton (default: True)
        """
        if singleton:
            self._singletons[interface] = mock_instance
        else:
            # For non-singleton mocks, we store them separately
            self._mock_services[interface] = mock_instance

    def register_mock_with_behavior(
        self, interface: Type[T], mock_instance: T, behavior: Dict[str, Any]
    ) -> None:
        """
        Register a mock instance with predefined behavior.

        Args:
            interface: The interface type to mock
            mock_instance: The mock instance to register
            behavior: Dictionary defining method behaviors
        """
        self._mock_services[interface] = mock_instance
        self._mock_behaviors[interface] = behavior

        # Apply behavior to mock methods
        for method_name, return_value in behavior.items():
            if hasattr(mock_instance, method_name):
                # Create a mock method that returns the predefined value
                def make_mock_method(value):
                    def mock_method(*args, **kwargs):
                        return value

                    return mock_method

                mock_method = make_mock_method(return_value)
                setattr(mock_instance, method_name, mock_method)

    def get_mock(self, interface: Type[T]) -> Optional[T]:
        """
        Get a registered mock instance.

        Args:
            interface: The interface type

        Returns:
            The mock instance if found, None otherwise
        """
        return self._mock_services.get(interface)

    def clear_mocks(self) -> None:
        """Clear all registered mock services."""
        self._mock_services.clear()
        self._mock_behaviors.clear()

    def verify_mock_calls(self, interface: Type[T], expected_calls: int) -> bool:
        """
        Verify that a mock was called the expected number of times.

        Args:
            interface: The interface type to verify
            expected_calls: Expected number of calls

        Returns:
            True if call count matches, False otherwise
        """
        mock = self._mock_services.get(interface)
        if mock and hasattr(mock, "call_count"):
            return getattr(mock, "call_count") == expected_calls
        return False

    def create_test_manager(self, config: Optional[Any] = None) -> Any:
        """
        Create a test manager with all test dependencies.

        Args:
            config: Optional configuration for the manager

        Returns:
            Configured test manager instance
        """
        # This will be implemented to return a properly configured test manager
        from .core import SquashFSManager  # type: ignore

        if config is None:
            from .config import SquishFSConfig  # type: ignore

            config = SquishFSConfig()
        return SquashFSManager(config)

    def setup_common_test_scenarios(self) -> None:
        """Set up common test scenarios with appropriate mocks."""
        # This will be implemented with common test scenarios
        pass

    def get_test_registration_info(self) -> Dict[str, Any]:
        """
        Get information about test-specific registrations.

        Returns:
            Dictionary containing test registration information
        """
        return {
            "mock_services": list(self._mock_services.keys()),
            "mock_behaviors": list(self._mock_behaviors.keys()),
            **super().get_registration_info(),
        }
