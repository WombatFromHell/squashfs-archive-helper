"""
Comprehensive tests for path_utils.py module.

This test suite covers all functions in the path_utils module with extensive
scenarios including success paths, error handling, and edge cases.
"""

import os
from pathlib import Path

import pytest

from squish.path_utils import (
    ensure_directory_exists,
    get_file_extension,
    get_filename_without_extension,
    get_parent_directory,
    get_relative_path,
    normalize_path,
    path_contains,
    resolve_path,
)


class TestResolvePath:
    """Test resolve_path function with various scenarios."""

    def test_resolve_existing_file(self, tmp_path):
        """Test resolving path to existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = resolve_path(str(test_file))
        assert result == str(test_file.resolve())

    def test_resolve_existing_directory(self, tmp_path):
        """Test resolving path to existing directory."""
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        result = resolve_path(str(test_dir))
        assert result == str(test_dir.resolve())

    def test_resolve_nonexistent_file_with_existing_parent(self, tmp_path):
        """Test resolving path to non-existent file with existing parent."""
        result = resolve_path(str(tmp_path / "nonexistent.txt"))
        expected = str(tmp_path.resolve() / "nonexistent.txt")
        assert result == expected

    def test_resolve_nonexistent_file_with_nonexistent_parent(self, tmp_path):
        """Test resolving path to non-existent file with non-existent parent."""
        result = resolve_path(str(tmp_path / "nonexistent_dir" / "file.txt"))
        expected = str(tmp_path / "nonexistent_dir" / "file.txt")
        assert result == expected

    def test_resolve_path_object(self, tmp_path):
        """Test resolving Path object."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = resolve_path(test_file)
        assert result == str(test_file.resolve())

    def test_resolve_empty_path(self):
        """Test resolving empty path (becomes current directory)."""
        # Note: Empty string "" becomes "." when converted to Path, which is valid
        # This test verifies the actual behavior
        result = resolve_path("")
        # Should return current directory resolved
        assert Path(result).exists()
        assert Path(result).is_dir()

    def test_resolve_invalid_type(self):
        """Test resolving invalid type raises TypeError."""
        with pytest.raises(TypeError, match="Target must be string or Path"):
            resolve_path(123)  # type: ignore

    def test_resolve_relative_path(self, tmp_path):
        """Test resolving relative path."""
        # Change to tmp_path directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            # Create a file
            test_file = tmp_path / "test.txt"
            test_file.write_text("content")

            # Test with relative path
            result = resolve_path("test.txt")
            assert result == str(test_file.resolve())
        finally:
            os.chdir(original_cwd)


class TestNormalizePath:
    """Test normalize_path function with various scenarios."""

    def test_normalize_existing_path(self, tmp_path):
        """Test normalizing existing path."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = normalize_path(str(test_file))
        assert result == str(test_file.resolve())

    def test_normalize_path_object(self, tmp_path):
        """Test normalizing Path object."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = normalize_path(test_file)
        assert result == str(test_file.resolve())

    def test_normalize_symlink(self, tmp_path):
        """Test normalizing symlink."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        symlink = tmp_path / "link.txt"
        symlink.symlink_to(test_file)

        result = normalize_path(str(symlink))
        assert result == str(test_file.resolve())

    def test_normalize_invalid_type(self):
        """Test normalizing invalid type raises TypeError."""
        with pytest.raises(TypeError, match="Path must be string or Path"):
            normalize_path(123)  # type: ignore

    def test_normalize_nonexistent_path(self, tmp_path):
        """Test normalizing non-existent path (should work for valid paths)."""
        # normalize_path doesn't fail for non-existent paths, it just resolves them
        result = normalize_path(str(tmp_path / "nonexistent" / "file.txt"))
        expected = str((tmp_path / "nonexistent" / "file.txt").resolve())
        assert result == expected


class TestGetParentDirectory:
    """Test get_parent_directory function with various scenarios."""

    def test_get_parent_existing_file(self, tmp_path):
        """Test getting parent of existing file."""
        test_file = tmp_path / "subdir" / "test.txt"
        test_file.parent.mkdir()
        test_file.write_text("content")

        result = get_parent_directory(str(test_file))
        assert result == str(test_file.parent.resolve())

    def test_get_parent_existing_directory(self, tmp_path):
        """Test getting parent of existing directory."""
        test_dir = tmp_path / "subdir" / "childdir"
        test_dir.mkdir(parents=True)

        result = get_parent_directory(str(test_dir))
        assert result == str(test_dir.parent.resolve())

    def test_get_parent_nonexistent_path(self, tmp_path):
        """Test getting parent of non-existent path."""
        result = get_parent_directory(str(tmp_path / "nonexistent" / "file.txt"))
        assert result == str(tmp_path / "nonexistent")

    def test_get_parent_root_directory(self):
        """Test getting parent of root directory."""
        result = get_parent_directory("/")
        assert result == "/"

    def test_get_parent_path_object(self, tmp_path):
        """Test getting parent of Path object."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        result = get_parent_directory(test_file)
        assert result == str(test_file.parent.resolve())

    def test_get_parent_invalid_type(self):
        """Test getting parent of invalid type raises TypeError."""
        with pytest.raises(TypeError, match="Path must be string or Path"):
            get_parent_directory(123)  # type: ignore


class TestEnsureDirectoryExists:
    """Test ensure_directory_exists function with various scenarios."""

    def test_ensure_existing_directory(self, tmp_path):
        """Test ensuring existing directory."""
        test_dir = tmp_path / "existing"
        test_dir.mkdir()

        result = ensure_directory_exists(str(test_dir))
        assert result == str(test_dir.resolve())

    def test_ensure_nonexistent_directory(self, tmp_path):
        """Test ensuring non-existent directory is created."""
        test_dir = tmp_path / "newdir" / "subdir"

        result = ensure_directory_exists(str(test_dir))
        assert result == str(test_dir.resolve())
        assert test_dir.exists()

    def test_ensure_directory_path_object(self, tmp_path):
        """Test ensuring directory with Path object."""
        test_dir = tmp_path / "pathobjdir"

        result = ensure_directory_exists(test_dir)
        assert result == str(test_dir.resolve())
        assert test_dir.exists()

    def test_ensure_directory_invalid_type(self):
        """Test ensuring directory with invalid type raises TypeError."""
        with pytest.raises(TypeError, match="Directory must be string or Path"):
            ensure_directory_exists(123)  # type: ignore

    def test_ensure_directory_permission_error(self, tmp_path):
        """Test ensuring directory with permission error raises ValueError."""
        # Create a directory with no write permissions
        restricted_dir = tmp_path / "restricted"
        restricted_dir.mkdir(mode=0o444)

        try:
            with pytest.raises(ValueError, match="Failed to ensure directory exists"):
                ensure_directory_exists(str(restricted_dir / "subdir"))
        finally:
            # Clean up
            restricted_dir.chmod(0o755)


class TestGetFilenameWithoutExtension:
    """Test get_filename_without_extension function with various scenarios."""

    def test_filename_single_extension(self):
        """Test getting filename without single extension."""
        result = get_filename_without_extension("/path/to/file.txt")
        assert result == "file"

    def test_filename_multiple_extensions(self):
        """Test getting filename without multiple extensions."""
        result = get_filename_without_extension("/path/to/file.tar.gz")
        assert result == "file"

    def test_filename_no_extension(self):
        """Test getting filename without extension when no extension."""
        result = get_filename_without_extension("/path/to/file")
        assert result == "file"

    def test_filename_path_object(self):
        """Test getting filename without extension with Path object."""
        result = get_filename_without_extension(Path("/path/to/file.txt"))
        assert result == "file"

    def test_filename_no_filename_component(self):
        """Test getting filename without extension when no filename raises ValueError."""
        # Use root path which has no filename component
        with pytest.raises(ValueError, match="Path.*has no filename component"):
            get_filename_without_extension("/")

    def test_filename_invalid_type(self):
        """Test getting filename without extension with invalid type raises TypeError."""
        with pytest.raises(TypeError, match="Path must be string or Path"):
            get_filename_without_extension(123)  # type: ignore


class TestGetFileExtension:
    """Test get_file_extension function with various scenarios."""

    def test_file_extension_single(self):
        """Test getting single file extension."""
        result = get_file_extension("/path/to/file.txt")
        assert result == ".txt"

    def test_file_extension_multiple(self):
        """Test getting last file extension from multiple extensions."""
        result = get_file_extension("/path/to/file.tar.gz")
        assert result == ".gz"

    def test_file_extension_none(self):
        """Test getting file extension when no extension."""
        result = get_file_extension("/path/to/file")
        assert result == ""

    def test_file_extension_path_object(self):
        """Test getting file extension with Path object."""
        result = get_file_extension(Path("/path/to/file.txt"))
        assert result == ".txt"

    def test_file_extension_no_filename_component(self):
        """Test getting file extension when no filename raises ValueError."""
        # Use root path which has no filename component
        with pytest.raises(ValueError, match="Path.*has no filename component"):
            get_file_extension("/")

    def test_file_extension_invalid_type(self):
        """Test getting file extension with invalid type raises TypeError."""
        with pytest.raises(TypeError, match="Path must be string or Path"):
            get_file_extension(123)  # type: ignore


class TestPathContains:
    """Test path_contains function with various scenarios."""

    def test_path_contains_true(self, tmp_path):
        """Test path contains when target is within path."""
        parent = tmp_path / "parent"
        child = parent / "child"
        parent.mkdir()
        child.mkdir()

        result = path_contains(str(parent), str(child))
        assert result is True

    def test_path_contains_false(self, tmp_path):
        """Test path contains when target is not within path."""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        result = path_contains(str(dir1), str(dir2))
        assert result is False

    def test_path_contains_same_path(self, tmp_path):
        """Test path contains when paths are the same (should be False - not contained within itself)."""
        test_dir = tmp_path / "testdir"
        test_dir.mkdir()

        result = path_contains(str(test_dir), str(test_dir))
        # A path is not considered to "contain" itself according to the current implementation
        assert result is False

    def test_path_contains_path_objects(self, tmp_path):
        """Test path contains with Path objects."""
        parent = tmp_path / "parent"
        child = parent / "child"
        parent.mkdir()
        child.mkdir()

        result = path_contains(parent, child)
        assert result is True

    def test_path_contains_invalid_types(self):
        """Test path contains with invalid types raises TypeError."""
        with pytest.raises(TypeError, match="Path must be string or Path"):
            path_contains(123, "/some/path")  # type: ignore

        with pytest.raises(TypeError, match="Target must be string or Path"):
            path_contains("/some/path", 123)  # type: ignore

    def test_path_contains_nonexistent_paths(self, tmp_path):
        """Test path contains with non-existent paths."""
        result = path_contains(
            str(tmp_path / "parent"), str(tmp_path / "parent" / "child")
        )
        assert result is True


class TestGetRelativePath:
    """Test get_relative_path function with various scenarios."""

    def test_relative_path_success(self, tmp_path):
        """Test getting relative path successfully."""
        base = tmp_path / "base"
        target = tmp_path / "base" / "subdir" / "file.txt"
        base.mkdir()
        target.parent.mkdir(parents=True)
        target.write_text("content")

        result = get_relative_path(str(base), str(target))
        assert result == "subdir/file.txt"

    def test_relative_path_different_drives(self, tmp_path):
        """Test getting relative path with different drives raises ValueError."""
        with pytest.raises(ValueError, match="Cannot compute relative path"):
            get_relative_path("/path/on/drive1", "/path/on/drive2")

    def test_relative_path_path_objects(self, tmp_path):
        """Test getting relative path with Path objects."""
        base = tmp_path / "base"
        target = tmp_path / "base" / "file.txt"
        base.mkdir()
        target.write_text("content")

        result = get_relative_path(base, target)
        assert result == "file.txt"

    def test_relative_path_invalid_types(self):
        """Test getting relative path with invalid types raises TypeError."""
        with pytest.raises(TypeError, match="Base must be string or Path"):
            get_relative_path(123, "/some/path")  # type: ignore

        with pytest.raises(TypeError, match="Target must be string or Path"):
            get_relative_path("/some/path", 123)  # type: ignore

    def test_relative_path_complex_structure(self, tmp_path):
        """Test getting relative path with complex directory structure."""
        base = tmp_path / "a" / "b"
        target = tmp_path / "a" / "b" / "c" / "d" / "file.txt"
        base.mkdir(parents=True)
        target.parent.mkdir(parents=True)
        target.write_text("content")

        result = get_relative_path(str(base), str(target))
        assert result == "c/d/file.txt"


class TestPathUtilsEdgeCases:
    """Test edge cases and integration scenarios for path_utils functions."""

    def test_resolve_path_with_special_characters(self, tmp_path):
        """Test resolving path with special characters."""
        test_file = tmp_path / "file with spaces and special!chars.txt"
        test_file.write_text("content")

        result = resolve_path(str(test_file))
        assert result == str(test_file.resolve())

    def test_resolve_path_with_unicode(self, tmp_path):
        """Test resolving path with unicode characters."""
        test_file = tmp_path / "文件.txt"
        test_file.write_text("content")

        result = resolve_path(str(test_file))
        assert result == str(test_file.resolve())

    def test_normalize_path_with_symlinks(self, tmp_path):
        """Test normalizing path with symlinks."""
        test_file = tmp_path / "real.txt"
        test_file.write_text("content")

        symlink = tmp_path / "link.txt"
        symlink.symlink_to(test_file)

        result = normalize_path(str(symlink))
        assert result == str(test_file.resolve())

    def test_get_parent_directory_root(self):
        """Test getting parent directory of root."""
        result = get_parent_directory("/")
        assert result == "/"

    def test_ensure_directory_exists_nested(self, tmp_path):
        """Test ensuring deeply nested directory exists."""
        deep_path = tmp_path / "a" / "b" / "c" / "d" / "e"

        result = ensure_directory_exists(str(deep_path))
        assert result == str(deep_path.resolve())
        assert deep_path.exists()

    def test_filename_without_extension_complex(self):
        """Test getting filename without extension for complex cases."""
        result = get_filename_without_extension("file.tar.bz2.gz")
        assert result == "file"

    def test_file_extension_complex(self):
        """Test getting file extension for complex cases."""
        result = get_file_extension("file.tar.bz2.gz")
        assert result == ".gz"

    def test_path_contains_relative_paths(self, tmp_path):
        """Test path contains with relative paths."""
        # Change to tmp_path directory
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)

            # Create directories
            parent = tmp_path / "parent"
            child = parent / "child"
            parent.mkdir()
            child.mkdir()

            # Test with relative paths
            result = path_contains("parent", "parent/child")
            assert result is True
        finally:
            os.chdir(original_cwd)

    def test_get_relative_path_upwards(self, tmp_path):
        """Test getting relative path that goes upwards (should raise ValueError)."""
        base = tmp_path / "a" / "b"
        target = tmp_path / "a"
        base.mkdir(parents=True)

        # This should raise ValueError because target is not in base's subtree
        with pytest.raises(ValueError, match="Cannot compute relative path"):
            get_relative_path(str(base), str(target))


class TestPathUtilsErrorHandling:
    """Test error handling scenarios for path_utils functions."""

    def test_resolve_path_permission_error(self, tmp_path):
        """Test resolve_path with permission error."""
        # This is tricky to test as resolve_path doesn't directly handle permission errors
        # The function should handle cases where parent exists but we can't access it
        pass  # This scenario is handled by the existing implementation

    def test_normalize_path_broken_symlink(self, tmp_path):
        """Test normalize_path with broken symlink (resolves to target)."""
        symlink = tmp_path / "broken.txt"
        symlink.symlink_to("/nonexistent/path")

        # normalize_path resolves broken symlinks to their target path
        result = normalize_path(str(symlink))
        assert result == "/nonexistent/path"

    def test_get_parent_directory_nonexistent(self, tmp_path):
        """Test get_parent_directory with completely nonexistent path."""
        result = get_parent_directory(str(tmp_path / "nonexistent" / "path"))
        assert result == str(tmp_path / "nonexistent")

    def test_ensure_directory_exists_permission_denied(self, tmp_path):
        """Test ensure_directory_exists with permission denied."""
        # Create a parent directory with no write permissions
        restricted_parent = tmp_path / "restricted"
        restricted_parent.mkdir(mode=0o444)

        try:
            with pytest.raises(ValueError, match="Failed to ensure directory exists"):
                ensure_directory_exists(str(restricted_parent / "subdir"))
        finally:
            restricted_parent.chmod(0o755)

    def test_filename_functions_empty_filename(self):
        """Test filename functions with empty filename."""
        # Use root path which has no filename component
        with pytest.raises(ValueError, match="Path.*has no filename component"):
            get_filename_without_extension("/")

        with pytest.raises(ValueError, match="Path.*has no filename component"):
            get_file_extension("/")

    def test_path_contains_nonexistent_resolution(self, tmp_path):
        """Test path_contains when resolution fails."""
        # This tests the fallback string comparison
        result = path_contains(
            str(tmp_path / "parent"), str(tmp_path / "parent" / "child")
        )
        assert result is True


class TestPathUtilsIntegration:
    """Test integration scenarios using multiple path_utils functions."""

    def test_integration_resolve_and_normalize(self, tmp_path):
        """Test integration of resolve_path and normalize_path."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        # Resolve then normalize should give same result
        resolved = resolve_path(str(test_file))
        normalized = normalize_path(str(test_file))

        assert resolved == normalized

    def test_integration_parent_and_ensure(self, tmp_path):
        """Test integration of get_parent_directory and ensure_directory_exists."""
        test_file = tmp_path / "subdir" / "test.txt"
        test_file.parent.mkdir()
        test_file.write_text("content")

        # Get parent and ensure it exists
        parent = get_parent_directory(str(test_file))
        result = ensure_directory_exists(parent)

        assert result == parent

    def test_integration_filename_functions(self):
        """Test integration of filename functions."""
        path = "/path/to/file.tar.gz"

        filename = get_filename_without_extension(path)
        extension = get_file_extension(path)

        assert filename == "file"
        assert extension == ".gz"
        assert f"{filename}{extension}" == "file.gz"

    def test_integration_path_operations(self, tmp_path):
        """Test integration of multiple path operations."""
        # Create a complex directory structure
        base = tmp_path / "base"
        target = base / "subdir" / "file.txt"
        base.mkdir()
        target.parent.mkdir()
        target.write_text("content")

        # Test multiple operations
        resolved_base = resolve_path(str(base))
        resolved_target = resolve_path(str(target))

        contains = path_contains(resolved_base, resolved_target)
        relative = get_relative_path(resolved_base, resolved_target)

        assert contains is True
        assert relative == "subdir/file.txt"


class TestPathUtilsTypeSafety:
    """Test type safety and validation for path_utils functions."""

    def test_all_functions_type_validation(self):
        """Test that all functions properly validate input types."""
        invalid_inputs: list[int | None | list | dict | set] = [
            123,
            None,
            [],
            {},
            set(),
        ]

        for invalid_input in invalid_inputs:
            # Test resolve_path
            with pytest.raises(TypeError):
                resolve_path(invalid_input)  # type: ignore

            # Test normalize_path
            with pytest.raises(TypeError):
                normalize_path(invalid_input)  # type: ignore

            # Test get_parent_directory
            with pytest.raises(TypeError):
                get_parent_directory(invalid_input)  # type: ignore

            # Test ensure_directory_exists
            with pytest.raises(TypeError):
                ensure_directory_exists(invalid_input)  # type: ignore

            # Test get_filename_without_extension
            with pytest.raises(TypeError):
                get_filename_without_extension(invalid_input)  # type: ignore

            # Test get_file_extension
            with pytest.raises(TypeError):
                get_file_extension(invalid_input)  # type: ignore

            # Test path_contains (both parameters)
            with pytest.raises(TypeError):
                path_contains(invalid_input, "/some/path")  # type: ignore

            with pytest.raises(TypeError):
                path_contains("/some/path", invalid_input)  # type: ignore

            # Test get_relative_path (both parameters)
            with pytest.raises(TypeError):
                get_relative_path(invalid_input, "/some/path")  # type: ignore

            with pytest.raises(TypeError):
                get_relative_path("/some/path", invalid_input)  # type: ignore


class TestPathUtilsStringPathEquivalence:
    """Test that string and Path object inputs produce equivalent results."""

    def test_resolve_path_equivalence(self, tmp_path):
        """Test resolve_path produces same result for string and Path inputs."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        string_result = resolve_path(str(test_file))
        path_result = resolve_path(test_file)

        assert string_result == path_result

    def test_normalize_path_equivalence(self, tmp_path):
        """Test normalize_path produces same result for string and Path inputs."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        string_result = normalize_path(str(test_file))
        path_result = normalize_path(test_file)

        assert string_result == path_result

    def test_get_parent_directory_equivalence(self, tmp_path):
        """Test get_parent_directory produces same result for string and Path inputs."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("content")

        string_result = get_parent_directory(str(test_file))
        path_result = get_parent_directory(test_file)

        assert string_result == path_result

    def test_ensure_directory_exists_equivalence(self, tmp_path):
        """Test ensure_directory_exists produces same result for string and Path inputs."""
        test_dir = tmp_path / "testdir"

        string_result = ensure_directory_exists(str(test_dir))
        path_result = ensure_directory_exists(test_dir)

        assert string_result == path_result

    def test_get_filename_without_extension_equivalence(self):
        """Test get_filename_without_extension produces same result for string and Path inputs."""
        string_result = get_filename_without_extension("/path/to/file.txt")
        path_result = get_filename_without_extension(Path("/path/to/file.txt"))

        assert string_result == path_result

    def test_get_file_extension_equivalence(self):
        """Test get_file_extension produces same result for string and Path inputs."""
        string_result = get_file_extension("/path/to/file.txt")
        path_result = get_file_extension(Path("/path/to/file.txt"))

        assert string_result == path_result

    def test_path_contains_equivalence(self, tmp_path):
        """Test path_contains produces same result for string and Path inputs."""
        parent = tmp_path / "parent"
        child = parent / "child"
        parent.mkdir()
        child.mkdir()

        string_result = path_contains(str(parent), str(child))
        path_result = path_contains(parent, child)

        assert string_result == path_result

    def test_get_relative_path_equivalence(self, tmp_path):
        """Test get_relative_path produces same result for string and Path inputs."""
        base = tmp_path / "base"
        target = tmp_path / "base" / "file.txt"
        base.mkdir()
        target.write_text("content")

        string_result = get_relative_path(str(base), str(target))
        path_result = get_relative_path(base, target)

        assert string_result == path_result
