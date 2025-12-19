# Mount SquashFS package
# This will be the main package for the mount-squashfs functionality

__version__ = "0.1.0"

# Import key components for easy access
from .config import SquishFSConfig, get_default_config
from .core import SquashFSManager
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
from .progress import (
    CommandRunner,
    DefaultCommandRunner,
    KdialogProgressHandler,
    MockCommandRunner,
    NoopProgressHandler,
    ProgressHandler,
    ProgressParser,
    ProgressService,
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
    "KdialogProgressHandler",
    "NoopProgressHandler",
    "ProgressHandler",
    "ProgressParser",
    "ProgressService",
    "CommandRunner",
    "DefaultCommandRunner",
    "MockCommandRunner",
]
