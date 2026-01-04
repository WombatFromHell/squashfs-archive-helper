# Mount SquashFS package
# This will be the main package for the mount-squashfs functionality

__version__ = "0.1.0"

# Import key components for easy access
from .command_executor import (
    CommandExecutor,
    ICommandExecutor,
    MockCommandExecutor,
)
from .config import SquishFSConfig, get_default_config
from .core import SquashFSManager
from .dependency_injection import (
    DependencyRegistrationError,
    DependencyResolutionError,
    DIContainer,
    InterfaceRegistry,
    IServiceProvider,
    ScopedDIContainer,
)
from .errors import (
    CommandExecutionError,
    ConfigError,
    DependencyError,
    MountCommandExecutionError,
    MountError,
    MountPointError,
    SquashFSError,
    UnmountCommandExecutionError,
    UnmountError,
)
from .mock_factory import MockBuilder, MockFactory
from .observer import (
    CompositeProgressObserver,
    EventDispatcher,
    FilteringProgressObserver,
    IProgressObserver,
    NullProgressObserver,
    ObserverError,
    ObserverNotificationError,
    ObserverRegistrationError,
    OperationEvent,
    OperationType,
    ProgressInfo,
    ProgressObserverAdapter,
    ProgressState,
    ProgressSubject,
)
from .path_utils import (
    ensure_directory_exists,
    get_file_extension,
    get_filename_without_extension,
    get_parent_directory,
    get_relative_path,
    normalize_path,
    path_contains,
    resolve_path,
)
from .progress import (
    BuildCancelledError,
    ExtractCancelledError,
    ExtractProgressTracker,
    MksquashfsProgress,
    ProgressParseError,
    ProgressTracker,
    UnifiedProgressParser,
    UnsquashfsProgress,
    ZenityProgressService,
    parse_mksquashfs_progress,
    parse_unsquashfs_progress,
)
from .tool_adapters import (
    IMksquashfsAdapter,
    ISha256sumAdapter,
    IToolAdapter,
    IUnsquashfsAdapter,
    IZenityAdapter,
    MksquashfsAdapter,
    MockMksquashfsAdapter,
    MockSha256sumAdapter,
    MockUnsquashfsAdapter,
    MockZenityAdapter,
    Sha256sumAdapter,
    UnsquashfsAdapter,
    ZenityAdapter,
)
from .tracking import MountTracker

__all__ = [
    "SquishFSConfig",
    "get_default_config",
    "SquashFSManager",
    "SquashFSError",
    "DependencyError",
    "MountError",
    "UnmountError",
    "ConfigError",
    "MountPointError",
    "CommandExecutionError",
    "MountCommandExecutionError",
    "UnmountCommandExecutionError",
    "MountTracker",
    # Command Executor components
    "ICommandExecutor",
    "CommandExecutor",
    "MockCommandExecutor",
    # Tool Adapter components
    "IToolAdapter",
    "IMksquashfsAdapter",
    "IUnsquashfsAdapter",
    "ISha256sumAdapter",
    "IZenityAdapter",
    "MksquashfsAdapter",
    "UnsquashfsAdapter",
    "Sha256sumAdapter",
    "ZenityAdapter",
    "MockMksquashfsAdapter",
    "MockUnsquashfsAdapter",
    "MockSha256sumAdapter",
    "MockZenityAdapter",
    # Progress Tracking components
    "BuildCancelledError",
    "ExtractCancelledError",
    "MksquashfsProgress",
    "UnsquashfsProgress",
    "ProgressParseError",
    "ProgressTracker",
    "ExtractProgressTracker",
    "UnifiedProgressParser",
    "ZenityProgressService",
    "parse_mksquashfs_progress",
    "parse_unsquashfs_progress",
    # Dependency Injection components
    "DIContainer",
    "ScopedDIContainer",
    "IServiceProvider",
    "InterfaceRegistry",
    "DependencyResolutionError",
    "DependencyRegistrationError",
    # Path Utility components
    "resolve_path",
    "normalize_path",
    "get_parent_directory",
    "ensure_directory_exists",
    "get_filename_without_extension",
    "get_file_extension",
    "path_contains",
    "get_relative_path",
    # Observer Pattern components
    "IProgressObserver",
    "ProgressSubject",
    "ProgressInfo",
    "ProgressState",
    "OperationType",
    "OperationEvent",
    "ObserverError",
    "ObserverRegistrationError",
    "ObserverNotificationError",
    "CompositeProgressObserver",
    "FilteringProgressObserver",
    "NullProgressObserver",
    "ProgressObserverAdapter",
    "EventDispatcher",
    # Mock Factory components
    "MockFactory",
    "MockBuilder",
]
