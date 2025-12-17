#!/usr/bin/env python3
"""
Entry point for the mount-squashfs zipapp bundle.

This module serves as the main entry point when the application is bundled
using zipapp. It imports and runs the main functionality from the refactored
mount-squashfs package.
"""

import os
import sys

# Add the current directory to sys.path to ensure we can import the package
sys.path.insert(0, os.path.dirname(__file__))


def main():
    """
    Main entry point for the bundled application.

    This function will be called when the zipapp bundle is executed.
    It imports and runs the main CLI from the refactored mount_squashfs package.
    """
    try:
        # Import the CLI from our refactored package
        from mount_squashfs.cli import main as cli_main

        # Run the CLI
        return cli_main()

    except ImportError as e:
        print(f"Error: Could not import mount_squashfs package: {e}")
        print(
            "This might indicate a problem with the package structure or installation."
        )
        return 1
    except Exception as e:
        print(f"Unexpected error in entry point: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
