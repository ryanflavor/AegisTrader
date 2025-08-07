"""File system adapter implementation."""

from __future__ import annotations

import shutil
from pathlib import Path


class FileSystemAdapter:
    """Adapter for file system operations."""

    def read_file(self, path: str) -> str:
        """Read contents of a file."""
        try:
            return Path(path).read_text()
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File not found: {path}") from e
        except Exception as e:
            raise OSError(f"Unable to read file {path}: {e}") from e

    def write_file(self, path: str, content: str) -> None:
        """Write content to a file."""
        try:
            Path(path).write_text(content)
        except Exception as e:
            raise OSError(f"Unable to write file {path}: {e}") from e

    def create_directory(self, path: str, exist_ok: bool = True) -> None:
        """Create a directory."""
        try:
            Path(path).mkdir(parents=True, exist_ok=exist_ok)
        except Exception as e:
            raise OSError(f"Unable to create directory {path}: {e}") from e

    def path_exists(self, path: str) -> bool:
        """Check if a path exists."""
        return Path(path).exists()

    def is_directory(self, path: str) -> bool:
        """Check if path is a directory."""
        return Path(path).is_dir()

    def is_file(self, path: str) -> bool:
        """Check if path is a file."""
        return Path(path).is_file()

    def list_directory(self, path: str) -> list[str]:
        """List contents of a directory."""
        try:
            return [p.name for p in Path(path).iterdir()]
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Directory not found: {path}") from e

    def delete_file(self, path: str) -> None:
        """Delete a file."""
        try:
            Path(path).unlink()
        except FileNotFoundError as e:
            raise FileNotFoundError(f"File not found: {path}") from e
        except Exception as e:
            raise OSError(f"Unable to delete file {path}: {e}") from e

    def copy_file(self, source: str, destination: str) -> None:
        """Copy a file."""
        try:
            shutil.copy2(source, destination)
        except FileNotFoundError as e:
            raise FileNotFoundError(f"Source file not found: {source}") from e
        except Exception as e:
            raise OSError(f"Unable to copy file from {source} to {destination}: {e}") from e
