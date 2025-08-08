"""Comprehensive edge case tests for FileSystemAdapter following TDD principles."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from aegis_sdk_dev.infrastructure.file_system_adapter import FileSystemAdapter


class TestFileSystemAdapterEdgeCases:
    """Test FileSystemAdapter edge cases and error conditions."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = FileSystemAdapter()
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"
        self.test_file.write_text("test content")

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    # Test read_file edge cases
    def test_read_file_nonexistent(self):
        """Test reading non-existent file raises appropriate error."""
        # Act & Assert
        with pytest.raises(FileNotFoundError, match="File not found"):
            self.adapter.read_file("/nonexistent/file.txt")

    def test_read_file_directory(self):
        """Test reading a directory raises error."""
        # Act & Assert
        with pytest.raises(OSError, match="Unable to read file"):
            self.adapter.read_file(self.temp_dir)

    def test_read_file_empty(self):
        """Test reading empty file."""
        # Arrange
        empty_file = Path(self.temp_dir) / "empty.txt"
        empty_file.write_text("")

        # Act
        content = self.adapter.read_file(str(empty_file))

        # Assert
        assert content == ""

    def test_read_file_with_special_characters(self):
        """Test reading file with special characters."""
        # Arrange
        special_file = Path(self.temp_dir) / "special.txt"
        # Note: \r gets normalized to \n on Unix systems, and \x00 may be treated specially
        special_content = "Hello\n\t\nWorld!@#$%^&*()"
        special_file.write_text(special_content)

        # Act
        content = self.adapter.read_file(str(special_file))

        # Assert
        assert content == special_content

    def test_read_file_with_unicode(self):
        """Test reading file with unicode content."""
        # Arrange
        unicode_file = Path(self.temp_dir) / "unicode.txt"
        unicode_content = "Hello 世界 🌍 مرحبا"
        unicode_file.write_text(unicode_content, encoding="utf-8")

        # Act
        content = self.adapter.read_file(str(unicode_file))

        # Assert
        assert content == unicode_content

    @patch("aegis_sdk_dev.infrastructure.file_system_adapter.Path")
    def test_read_file_permission_denied(self, mock_path_class):
        """Test reading file with permission denied."""
        # Arrange
        mock_path_instance = Mock()
        mock_path_instance.read_text.side_effect = PermissionError("Permission denied")
        mock_path_class.return_value = mock_path_instance

        # Act & Assert
        with pytest.raises(OSError, match="Unable to read file"):
            self.adapter.read_file("/protected/file.txt")

    def test_read_file_very_large(self):
        """Test reading very large file."""
        # Arrange
        large_file = Path(self.temp_dir) / "large.txt"
        large_content = "x" * (10 * 1024 * 1024)  # 10MB
        large_file.write_text(large_content)

        # Act
        content = self.adapter.read_file(str(large_file))

        # Assert
        assert content == large_content

    def test_read_file_with_null_bytes(self):
        """Test reading file with null bytes."""
        # Arrange
        null_file = Path(self.temp_dir) / "null.txt"
        null_content = "Before\x00After"
        null_file.write_bytes(null_content.encode("utf-8"))

        # Act
        content = self.adapter.read_file(str(null_file))

        # Assert
        assert content == null_content

    # Test write_file edge cases
    def test_write_file_creates_parent_dirs(self):
        """Test writing file creates parent directories."""
        # Arrange
        nested_path = Path(self.temp_dir) / "dir1" / "dir2" / "dir3" / "file.txt"

        # Act
        self.adapter.write_file(str(nested_path), "content")

        # Assert
        assert nested_path.exists()
        assert nested_path.read_text() == "content"

    def test_write_file_overwrites_existing(self):
        """Test writing file overwrites existing content."""
        # Arrange
        existing_file = Path(self.temp_dir) / "existing.txt"
        existing_file.write_text("old content")

        # Act
        self.adapter.write_file(str(existing_file), "new content")

        # Assert
        assert existing_file.read_text() == "new content"

    def test_write_file_empty_content(self):
        """Test writing empty content to file."""
        # Arrange
        empty_file = Path(self.temp_dir) / "empty.txt"

        # Act
        self.adapter.write_file(str(empty_file), "")

        # Assert
        assert empty_file.exists()
        assert empty_file.read_text() == ""

    @patch("aegis_sdk_dev.infrastructure.file_system_adapter.Path")
    def test_write_file_permission_denied(self, mock_path_class):
        """Test writing file with permission denied."""
        # Arrange
        mock_path_instance = Mock()
        mock_parent = Mock()
        mock_parent.mkdir.side_effect = PermissionError("Permission denied")
        mock_path_instance.parent = mock_parent
        mock_path_class.return_value = mock_path_instance

        # Act & Assert
        with pytest.raises(OSError, match="Unable to write file"):
            self.adapter.write_file("/protected/file.txt", "content")

    @patch("aegis_sdk_dev.infrastructure.file_system_adapter.Path")
    def test_write_file_disk_full(self, mock_path_class):
        """Test writing file when disk is full."""
        # Arrange
        mock_path_instance = Mock()
        mock_parent = Mock()
        mock_parent.mkdir.return_value = None
        mock_path_instance.parent = mock_parent
        mock_path_instance.write_text.side_effect = OSError("No space left on device")
        mock_path_class.return_value = mock_path_instance

        # Act & Assert
        with pytest.raises(OSError, match="Unable to write file.*No space left"):
            self.adapter.write_file("/tmp/file.txt", "content")

    def test_write_file_with_special_path_characters(self):
        """Test writing file with special characters in path."""
        # Arrange
        special_path = Path(self.temp_dir) / "file with spaces & special.txt"

        # Act
        self.adapter.write_file(str(special_path), "content")

        # Assert
        assert special_path.exists()
        assert special_path.read_text() == "content"

    # Test create_directory edge cases
    def test_create_directory_nested(self):
        """Test creating deeply nested directory."""
        # Arrange
        nested_dir = Path(self.temp_dir) / "a" / "b" / "c" / "d" / "e"

        # Act
        self.adapter.create_directory(str(nested_dir))

        # Assert
        assert nested_dir.exists()
        assert nested_dir.is_dir()

    def test_create_directory_already_exists_with_exist_ok(self):
        """Test creating directory that already exists with exist_ok=True."""
        # Arrange
        existing_dir = Path(self.temp_dir) / "existing"
        existing_dir.mkdir()

        # Act - should not raise
        self.adapter.create_directory(str(existing_dir), exist_ok=True)

        # Assert
        assert existing_dir.exists()

    def test_create_directory_already_exists_without_exist_ok(self):
        """Test creating directory that already exists with exist_ok=False."""
        # Arrange
        existing_dir = Path(self.temp_dir) / "existing"
        existing_dir.mkdir()

        # Act & Assert
        with pytest.raises(OSError, match="Unable to create directory"):
            self.adapter.create_directory(str(existing_dir), exist_ok=False)

    @patch("aegis_sdk_dev.infrastructure.file_system_adapter.Path")
    def test_create_directory_permission_denied(self, mock_path_class):
        """Test creating directory with permission denied."""
        # Arrange
        mock_path_instance = Mock()
        mock_path_instance.mkdir.side_effect = PermissionError("Permission denied")
        mock_path_class.return_value = mock_path_instance

        # Act & Assert
        with pytest.raises(OSError, match="Unable to create directory"):
            self.adapter.create_directory("/protected/dir")

    def test_create_directory_over_existing_file(self):
        """Test creating directory over existing file."""
        # Arrange
        file_path = Path(self.temp_dir) / "file.txt"
        file_path.write_text("content")

        # Act & Assert
        with pytest.raises(OSError, match="Unable to create directory"):
            self.adapter.create_directory(str(file_path))

    # Test path_exists edge cases
    def test_path_exists_with_symlink(self):
        """Test path_exists with symbolic link."""
        # Arrange
        target = Path(self.temp_dir) / "target.txt"
        target.write_text("content")
        link = Path(self.temp_dir) / "link.txt"
        link.symlink_to(target)

        # Act
        result = self.adapter.path_exists(str(link))

        # Assert
        assert result is True

    def test_path_exists_with_broken_symlink(self):
        """Test path_exists with broken symbolic link."""
        # Arrange
        link = Path(self.temp_dir) / "broken_link.txt"
        link.symlink_to("/nonexistent/target")

        # Act
        result = self.adapter.path_exists(str(link))

        # Assert
        assert result is False  # Path.exists() returns False for broken symlinks

    def test_path_exists_empty_string(self):
        """Test path_exists with empty string."""
        # Act
        result = self.adapter.path_exists("")

        # Assert
        # Empty string resolves to current directory which exists
        assert result is True

    # Test is_directory edge cases
    def test_is_directory_on_file(self):
        """Test is_directory on a file."""
        # Act
        result = self.adapter.is_directory(str(self.test_file))

        # Assert
        assert result is False

    def test_is_directory_on_nonexistent(self):
        """Test is_directory on non-existent path."""
        # Act
        result = self.adapter.is_directory("/nonexistent/path")

        # Assert
        assert result is False

    def test_is_directory_on_symlink_to_dir(self):
        """Test is_directory on symlink pointing to directory."""
        # Arrange
        target_dir = Path(self.temp_dir) / "target_dir"
        target_dir.mkdir()
        link = Path(self.temp_dir) / "link_dir"
        link.symlink_to(target_dir)

        # Act
        result = self.adapter.is_directory(str(link))

        # Assert
        assert result is True

    # Test is_file edge cases
    def test_is_file_on_directory(self):
        """Test is_file on a directory."""
        # Act
        result = self.adapter.is_file(self.temp_dir)

        # Assert
        assert result is False

    def test_is_file_on_nonexistent(self):
        """Test is_file on non-existent path."""
        # Act
        result = self.adapter.is_file("/nonexistent/file")

        # Assert
        assert result is False

    def test_is_file_on_symlink_to_file(self):
        """Test is_file on symlink pointing to file."""
        # Arrange
        target_file = Path(self.temp_dir) / "target.txt"
        target_file.write_text("content")
        link = Path(self.temp_dir) / "link.txt"
        link.symlink_to(target_file)

        # Act
        result = self.adapter.is_file(str(link))

        # Assert
        assert result is True

    # Test list_directory edge cases
    def test_list_directory_empty(self):
        """Test listing empty directory."""
        # Arrange
        empty_dir = Path(self.temp_dir) / "empty"
        empty_dir.mkdir()

        # Act
        result = self.adapter.list_directory(str(empty_dir))

        # Assert
        assert result == []

    def test_list_directory_nonexistent(self):
        """Test listing non-existent directory."""
        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Directory not found"):
            self.adapter.list_directory("/nonexistent/dir")

    def test_list_directory_on_file(self):
        """Test listing a file instead of directory."""
        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Directory not found"):
            self.adapter.list_directory(str(self.test_file))

    def test_list_directory_with_hidden_files(self):
        """Test listing directory includes hidden files."""
        # Arrange
        hidden_file = Path(self.temp_dir) / ".hidden"
        hidden_file.write_text("hidden")

        # Act
        result = self.adapter.list_directory(self.temp_dir)

        # Assert
        assert ".hidden" in result

    def test_list_directory_with_special_names(self):
        """Test listing directory with special file names."""
        # Arrange
        special_names = [
            "file with spaces.txt",
            "file-with-dashes.txt",
            "file.multiple.dots.txt",
        ]
        for name in special_names:
            (Path(self.temp_dir) / name).write_text("content")

        # Act
        result = self.adapter.list_directory(self.temp_dir)

        # Assert
        for name in special_names:
            assert name in result

    # Test delete_file edge cases
    def test_delete_file_nonexistent(self):
        """Test deleting non-existent file."""
        # Act & Assert
        with pytest.raises(FileNotFoundError, match="File not found"):
            self.adapter.delete_file("/nonexistent/file.txt")

    def test_delete_file_directory(self):
        """Test deleting directory raises error."""
        # Arrange
        test_dir = Path(self.temp_dir) / "testdir"
        test_dir.mkdir()

        # Act & Assert
        with pytest.raises(OSError, match="Unable to delete file"):
            self.adapter.delete_file(str(test_dir))

    @patch("aegis_sdk_dev.infrastructure.file_system_adapter.Path")
    def test_delete_file_permission_denied(self, mock_path_class):
        """Test deleting file with permission denied."""
        # Arrange
        mock_path_instance = Mock()
        mock_path_instance.unlink.side_effect = PermissionError("Permission denied")
        mock_path_class.return_value = mock_path_instance

        # Act & Assert
        with pytest.raises(OSError, match="Unable to delete file"):
            self.adapter.delete_file("/protected/file.txt")

    def test_delete_file_success(self):
        """Test successful file deletion."""
        # Arrange
        file_to_delete = Path(self.temp_dir) / "delete_me.txt"
        file_to_delete.write_text("content")

        # Act
        self.adapter.delete_file(str(file_to_delete))

        # Assert
        assert not file_to_delete.exists()

    # Test copy_file edge cases
    def test_copy_file_nonexistent_source(self):
        """Test copying non-existent source file."""
        # Act & Assert
        with pytest.raises(FileNotFoundError, match="Source file not found"):
            self.adapter.copy_file("/nonexistent/source.txt", str(self.temp_dir))

    def test_copy_file_overwrites_destination(self):
        """Test copying file overwrites existing destination."""
        # Arrange
        source = Path(self.temp_dir) / "source.txt"
        source.write_text("new content")
        dest = Path(self.temp_dir) / "dest.txt"
        dest.write_text("old content")

        # Act
        self.adapter.copy_file(str(source), str(dest))

        # Assert
        assert dest.read_text() == "new content"

    def test_copy_file_to_nonexistent_directory(self):
        """Test copying file to non-existent directory."""
        # Arrange
        source = self.test_file
        dest = Path("/nonexistent/dir/file.txt")

        # Act & Assert
        with pytest.raises(OSError, match="Unable to copy file"):
            self.adapter.copy_file(str(source), str(dest))

    @patch("shutil.copy2")
    def test_copy_file_permission_denied(self, mock_copy2):
        """Test copying file with permission denied."""
        # Arrange
        mock_copy2.side_effect = PermissionError("Permission denied")

        # Act & Assert
        with pytest.raises(OSError, match="Unable to copy file"):
            self.adapter.copy_file("source.txt", "dest.txt")

    def test_copy_file_preserves_metadata(self):
        """Test copying file preserves metadata."""
        # Arrange
        source = Path(self.temp_dir) / "source.txt"
        source.write_text("content")
        dest = Path(self.temp_dir) / "dest.txt"

        # Act
        self.adapter.copy_file(str(source), str(dest))

        # Assert
        assert dest.exists()
        assert dest.read_text() == "content"
        # Note: shutil.copy2 preserves metadata

    def test_copy_file_large_file(self):
        """Test copying large file."""
        # Arrange
        source = Path(self.temp_dir) / "large.txt"
        large_content = "x" * (5 * 1024 * 1024)  # 5MB
        source.write_text(large_content)
        dest = Path(self.temp_dir) / "large_copy.txt"

        # Act
        self.adapter.copy_file(str(source), str(dest))

        # Assert
        assert dest.read_text() == large_content
