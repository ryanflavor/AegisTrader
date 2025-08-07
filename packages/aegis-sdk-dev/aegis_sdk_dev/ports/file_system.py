"""File system port for file operations."""

from __future__ import annotations

from typing import Protocol


class FileSystemPort(Protocol):
    """Port for file system operations."""

    def read_file(self, path: str) -> str:
        """Read contents of a file.

        Args:
            path: File path

        Returns:
            File contents

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If unable to read file
        """
        ...

    def write_file(self, path: str, content: str) -> None:
        """Write content to a file.

        Args:
            path: File path
            content: Content to write

        Raises:
            IOError: If unable to write file
        """
        ...

    def create_directory(self, path: str, exist_ok: bool = True) -> None:
        """Create a directory.

        Args:
            path: Directory path
            exist_ok: If True, don't raise error if directory exists

        Raises:
            IOError: If unable to create directory
        """
        ...

    def path_exists(self, path: str) -> bool:
        """Check if a path exists.

        Args:
            path: Path to check

        Returns:
            True if path exists, False otherwise
        """
        ...

    def is_directory(self, path: str) -> bool:
        """Check if path is a directory.

        Args:
            path: Path to check

        Returns:
            True if directory, False otherwise
        """
        ...

    def is_file(self, path: str) -> bool:
        """Check if path is a file.

        Args:
            path: Path to check

        Returns:
            True if file, False otherwise
        """
        ...

    def list_directory(self, path: str) -> list[str]:
        """List contents of a directory.

        Args:
            path: Directory path

        Returns:
            List of file/directory names

        Raises:
            FileNotFoundError: If directory doesn't exist
        """
        ...

    def delete_file(self, path: str) -> None:
        """Delete a file.

        Args:
            path: File path to delete

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If unable to delete file
        """
        ...

    def copy_file(self, source: str, destination: str) -> None:
        """Copy a file.

        Args:
            source: Source file path
            destination: Destination file path

        Raises:
            FileNotFoundError: If source doesn't exist
            IOError: If unable to copy file
        """
        ...
