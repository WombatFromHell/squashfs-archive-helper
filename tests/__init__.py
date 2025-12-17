"""
Test package for mount-squashfs-helper.

This package contains all the test cases for the mount-squashfs functionality.
"""

# Import test fixtures and utilities that should be available to all tests
import os

# Add the src directory to the path so we can import the package during testing
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
