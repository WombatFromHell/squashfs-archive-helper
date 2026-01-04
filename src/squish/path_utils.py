"""
Path utility functions for SquishFS.

This module provides comprehensive path resolution and manipulation utilities
that match the behavior of squish.sh reference implementation.
"""

from pathlib import Path
from typing import Union


def resolve_path(target: Union[str, Path]) -> str:
    """
    Resolve path to absolute, handling potential non-existence for parent dirs.

    This function implements the path resolution logic from squish.sh to handle:
    - Existing files and directories
    - Non-existing paths with parent resolution
    - Comprehensive error handling

    Args:
        target: Path to resolve (string or Path object)

    Returns:
        Resolved absolute path as string

    Raises:
        ValueError: If path resolution fails
        TypeError: If target is not a string or Path object
    """
    # Convert to Path object if it's a string
    if isinstance(target, str):
        target_path = Path(target)
    elif isinstance(target, Path):
        target_path = target
    else:
        raise TypeError(f"Target must be string or Path, got {type(target)}")

    # Handle empty path
    if not str(target_path):
        raise ValueError("Path cannot be empty")

    # If the target exists, return its absolute resolved path
    if target_path.exists():
        if target_path.is_dir():
            return str(target_path.resolve())
        else:
            return str(target_path.resolve())
    else:
        # File/Dir doesn't exist yet, try to resolve the parent
        parent = target_path.parent
        if parent.exists():
            return str(parent.resolve() / target_path.name)
        else:
            # If parent doesn't exist, return the original path
            # This maintains squish.sh behavior for non-existent paths
            return str(target_path)


def normalize_path(path: Union[str, Path]) -> str:
    """
    Normalize a path by resolving symlinks and converting to absolute path.

    Args:
        path: Path to normalize (string or Path object)

    Returns:
        Normalized absolute path as string

    Raises:
        ValueError: If path normalization fails
        TypeError: If path is not a string or Path object
    """
    try:
        if isinstance(path, str):
            return str(Path(path).resolve())
        elif isinstance(path, Path):
            return str(path.resolve())
        else:
            raise TypeError(f"Path must be string or Path, got {type(path)}")
    except (OSError, RuntimeError) as e:
        raise ValueError(f"Failed to normalize path '{path}': {e}")


def get_parent_directory(path: Union[str, Path]) -> str:
    """
    Get the parent directory of a path, resolving it if possible.

    Args:
        path: Path to get parent of (string or Path object)

    Returns:
        Parent directory path as string

    Raises:
        ValueError: If path has no parent or resolution fails
        TypeError: If path is not a string or Path object
    """
    if isinstance(path, str):
        path_obj = Path(path)
    elif isinstance(path, Path):
        path_obj = path
    else:
        raise TypeError(f"Path must be string or Path, got {type(path)}")

    parent = path_obj.parent
    if parent == path_obj:  # No parent (root directory)
        return str(parent)

    # Try to resolve the parent if it exists
    if parent.exists():
        return str(parent.resolve())
    else:
        return str(parent)


def ensure_directory_exists(directory: Union[str, Path]) -> str:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        directory: Directory path to ensure exists (string or Path object)

    Returns:
        Path to the existing directory as string

    Raises:
        ValueError: If directory creation fails
        TypeError: If directory is not a string or Path object
    """
    if isinstance(directory, str):
        dir_path = Path(directory)
    elif isinstance(directory, Path):
        dir_path = directory
    else:
        raise TypeError(f"Directory must be string or Path, got {type(directory)}")

    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        return str(dir_path.resolve())
    except OSError as e:
        raise ValueError(f"Failed to ensure directory exists '{directory}': {e}")


def get_filename_without_extension(path: Union[str, Path]) -> str:
    """
    Get the filename without extension from a path.

    Args:
        path: Path to extract filename from (string or Path object)

    Returns:
        Filename without extension

    Raises:
        ValueError: If path has no filename component
        TypeError: If path is not a string or Path object
    """
    if isinstance(path, str):
        path_obj = Path(path)
    elif isinstance(path, Path):
        path_obj = path
    else:
        raise TypeError(f"Path must be string or Path, got {type(path)}")

    filename = path_obj.name
    if not filename:
        raise ValueError(f"Path '{path}' has no filename component")

    # Remove all extensions (handles multiple extensions like .tar.gz)
    stem = path_obj.stem
    while stem != path_obj.name and Path(stem).suffix:
        stem = Path(stem).stem

    return stem


def get_file_extension(path: Union[str, Path]) -> str:
    """
    Get the file extension from a path.

    Args:
        path: Path to extract extension from (string or Path object)

    Returns:
        File extension (including dot) or empty string if no extension

    Raises:
        ValueError: If path has no filename component
        TypeError: If path is not a string or Path object
    """
    if isinstance(path, str):
        path_obj = Path(path)
    elif isinstance(path, Path):
        path_obj = path
    else:
        raise TypeError(f"Path must be string or Path, got {type(path)}")

    filename = path_obj.name
    if not filename:
        raise ValueError(f"Path '{path}' has no filename component")

    # Get the last extension (handles multiple extensions)
    suffix = path_obj.suffix
    return suffix if suffix else ""


def path_contains(path: Union[str, Path], target: Union[str, Path]) -> bool:
    """
    Check if a path contains another path as a subpath.

    Args:
        path: Parent path to check (string or Path object)
        target: Target path to check for (string or Path object)

    Returns:
        True if target is contained within path, False otherwise

    Raises:
        TypeError: If either path is not a string or Path object
    """
    if isinstance(path, str):
        path_obj = Path(path)
    elif isinstance(path, Path):
        path_obj = path
    else:
        raise TypeError(f"Path must be string or Path, got {type(path)}")

    if isinstance(target, str):
        target_obj = Path(target)
    elif isinstance(target, Path):
        target_obj = target
    else:
        raise TypeError(f"Target must be string or Path, got {type(target)}")

    try:
        # Use resolve() to handle relative paths and symlinks
        path_resolved = path_obj.resolve()
        target_resolved = target_obj.resolve()

        # Check if target is within path
        return path_resolved in target_resolved.parents
    except (OSError, RuntimeError):
        # If resolution fails, fall back to string comparison
        return str(path_obj) in str(target_obj)


def get_relative_path(base: Union[str, Path], target: Union[str, Path]) -> str:
    """
    Get the relative path from base to target.

    Args:
        base: Base path (string or Path object)
        target: Target path (string or Path object)

    Returns:
        Relative path from base to target as string

    Raises:
        ValueError: If paths are on different drives or relative path cannot be computed
        TypeError: If either path is not a string or Path object
    """
    if isinstance(base, str):
        base_obj = Path(base)
    elif isinstance(base, Path):
        base_obj = base
    else:
        raise TypeError(f"Base must be string or Path, got {type(base)}")

    if isinstance(target, str):
        target_obj = Path(target)
    elif isinstance(target, Path):
        target_obj = target
    else:
        raise TypeError(f"Target must be string or Path, got {type(target)}")

    try:
        relative = target_obj.relative_to(base_obj)
        return str(relative)
    except ValueError as e:
        raise ValueError(
            f"Cannot compute relative path from '{base}' to '{target}': {e}"
        )
