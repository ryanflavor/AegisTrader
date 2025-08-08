"""Unit tests for FileSystemAdapter following TDD principles."""

from unittest.mock import MagicMock, patch

import pytest

from aegis_sdk_dev.infrastructure.file_system_adapter import FileSystemAdapter
from aegis_sdk_dev.ports.file_system import FileSystemPort


class TestFileSystemAdapter:
    """Test FileSystemAdapter implementation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = FileSystemAdapter()

    def test_implements_file_system_port(self):
        """Test that FileSystemAdapter implements FileSystemPort interface."""
        # Assert
        assert isinstance(self.adapter, FileSystemPort)

    @patch("pathlib.Path.read_text")
    def test_read_file_success(self, mock_read_text):
        """Test reading a file successfully."""
        # Arrange
        file_path = "/test/file.txt"
        expected_content = "File content"
        mock_read_text.return_value = expected_content

        # Act
        result = self.adapter.read_file(file_path)

        # Assert
        assert result == expected_content
        mock_read_text.assert_called_once()

    @patch("pathlib.Path.read_text")
    def test_read_file_not_found(self, mock_read_text):
        """Test reading a non-existent file."""
        # Arrange
        file_path = "/test/nonexistent.txt"
        mock_read_text.side_effect = FileNotFoundError("File not found")

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            self.adapter.read_file(file_path)

    @patch("pathlib.Path.read_text")
    def test_read_file_io_error(self, mock_read_text):
        """Test reading a file with IO error."""
        # Arrange
        file_path = "/test/file.txt"
        mock_read_text.side_effect = OSError("Permission denied")

        # Act & Assert
        with pytest.raises(IOError):
            self.adapter.read_file(file_path)

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.parent", new_callable=lambda: MagicMock())
    def test_write_file_success(self, mock_parent, mock_write_text):
        """Test writing to a file successfully."""
        # Arrange
        file_path = "/test/file.txt"
        content = "New content"
        mock_parent.mkdir = MagicMock()

        # Act
        self.adapter.write_file(file_path, content)

        # Assert
        mock_parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_write_text.assert_called_once_with(content)

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.parent", new_callable=lambda: MagicMock())
    def test_write_file_io_error(self, mock_parent, mock_write_text):
        """Test writing to a file with IO error."""
        # Arrange
        file_path = "/test/file.txt"
        content = "New content"
        mock_parent.mkdir = MagicMock()
        mock_write_text.side_effect = OSError("Disk full")

        # Act & Assert
        with pytest.raises(IOError):
            self.adapter.write_file(file_path, content)

    @patch("pathlib.Path.mkdir")
    def test_create_directory_success(self, mock_mkdir):
        """Test creating a directory successfully."""
        # Arrange
        dir_path = "/test/new_dir"

        # Act
        self.adapter.create_directory(dir_path)

        # Assert
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("pathlib.Path.mkdir")
    def test_create_directory_exist_ok_false(self, mock_mkdir):
        """Test creating a directory with exist_ok=False."""
        # Arrange
        dir_path = "/test/new_dir"

        # Act
        self.adapter.create_directory(dir_path, exist_ok=False)

        # Assert
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=False)

    @patch("pathlib.Path.mkdir")
    def test_create_directory_io_error(self, mock_mkdir):
        """Test creating a directory with IO error."""
        # Arrange
        dir_path = "/test/new_dir"
        mock_mkdir.side_effect = OSError("Permission denied")

        # Act & Assert
        with pytest.raises(IOError):
            self.adapter.create_directory(dir_path)

    @patch("pathlib.Path.exists")
    def test_path_exists_true(self, mock_exists):
        """Test checking if a path exists (true case)."""
        # Arrange
        path = "/test/exists.txt"
        mock_exists.return_value = True

        # Act
        result = self.adapter.path_exists(path)

        # Assert
        assert result is True
        mock_exists.assert_called_once()

    @patch("pathlib.Path.exists")
    def test_path_exists_false(self, mock_exists):
        """Test checking if a path exists (false case)."""
        # Arrange
        path = "/test/nonexistent.txt"
        mock_exists.return_value = False

        # Act
        result = self.adapter.path_exists(path)

        # Assert
        assert result is False
        mock_exists.assert_called_once()

    @patch("pathlib.Path.is_dir")
    def test_is_directory_true(self, mock_is_dir):
        """Test checking if path is a directory (true case)."""
        # Arrange
        path = "/test/directory"
        mock_is_dir.return_value = True

        # Act
        result = self.adapter.is_directory(path)

        # Assert
        assert result is True
        mock_is_dir.assert_called_once()

    @patch("pathlib.Path.is_dir")
    def test_is_directory_false(self, mock_is_dir):
        """Test checking if path is a directory (false case)."""
        # Arrange
        path = "/test/file.txt"
        mock_is_dir.return_value = False

        # Act
        result = self.adapter.is_directory(path)

        # Assert
        assert result is False
        mock_is_dir.assert_called_once()

    @patch("pathlib.Path.is_file")
    def test_is_file_true(self, mock_is_file):
        """Test checking if path is a file (true case)."""
        # Arrange
        path = "/test/file.txt"
        mock_is_file.return_value = True

        # Act
        result = self.adapter.is_file(path)

        # Assert
        assert result is True
        mock_is_file.assert_called_once()

    @patch("pathlib.Path.is_file")
    def test_is_file_false(self, mock_is_file):
        """Test checking if path is a file (false case)."""
        # Arrange
        path = "/test/directory"
        mock_is_file.return_value = False

        # Act
        result = self.adapter.is_file(path)

        # Assert
        assert result is False
        mock_is_file.assert_called_once()

    @patch("pathlib.Path.iterdir")
    def test_list_directory_success(self, mock_iterdir):
        """Test listing directory contents successfully."""
        # Arrange
        dir_path = "/test/directory"
        mock_items = [
            MagicMock(name="file1.txt"),
            MagicMock(name="file2.txt"),
            MagicMock(name="subdir"),
        ]
        for item, name in zip(mock_items, ["file1.txt", "file2.txt", "subdir"], strict=False):
            item.name = name
        mock_iterdir.return_value = mock_items

        # Act
        result = self.adapter.list_directory(dir_path)

        # Assert
        assert result == ["file1.txt", "file2.txt", "subdir"]
        mock_iterdir.assert_called_once()

    @patch("pathlib.Path.iterdir")
    def test_list_directory_not_found(self, mock_iterdir):
        """Test listing non-existent directory."""
        # Arrange
        dir_path = "/test/nonexistent"
        mock_iterdir.side_effect = FileNotFoundError("Directory not found")

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            self.adapter.list_directory(dir_path)

    @patch("pathlib.Path.unlink")
    def test_delete_file_success(self, mock_unlink):
        """Test deleting a file successfully."""
        # Arrange
        file_path = "/test/file.txt"

        # Act
        self.adapter.delete_file(file_path)

        # Assert
        mock_unlink.assert_called_once()

    @patch("pathlib.Path.unlink")
    def test_delete_file_not_found(self, mock_unlink):
        """Test deleting a non-existent file."""
        # Arrange
        file_path = "/test/nonexistent.txt"
        mock_unlink.side_effect = FileNotFoundError("File not found")

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            self.adapter.delete_file(file_path)

    @patch("pathlib.Path.unlink")
    def test_delete_file_io_error(self, mock_unlink):
        """Test deleting a file with IO error."""
        # Arrange
        file_path = "/test/file.txt"
        mock_unlink.side_effect = OSError("Permission denied")

        # Act & Assert
        with pytest.raises(IOError):
            self.adapter.delete_file(file_path)

    @patch("shutil.copy2")
    def test_copy_file_success(self, mock_copy2):
        """Test copying a file successfully."""
        # Arrange
        source = "/test/source.txt"
        destination = "/test/destination.txt"

        # Act
        self.adapter.copy_file(source, destination)

        # Assert
        mock_copy2.assert_called_once_with(source, destination)

    @patch("shutil.copy2")
    def test_copy_file_not_found(self, mock_copy2):
        """Test copying a non-existent file."""
        # Arrange
        source = "/test/nonexistent.txt"
        destination = "/test/destination.txt"
        mock_copy2.side_effect = FileNotFoundError("Source file not found")

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            self.adapter.copy_file(source, destination)

    @patch("shutil.copy2")
    def test_copy_file_io_error(self, mock_copy2):
        """Test copying a file with IO error."""
        # Arrange
        source = "/test/source.txt"
        destination = "/test/destination.txt"
        mock_copy2.side_effect = OSError("Disk full")

        # Act & Assert
        with pytest.raises(IOError):
            self.adapter.copy_file(source, destination)

    def test_file_system_adapter_stateless(self):
        """Test that FileSystemAdapter is stateless."""
        # Arrange
        adapter1 = FileSystemAdapter()
        adapter2 = FileSystemAdapter()

        # Assert
        assert adapter1 is not adapter2

    @patch("pathlib.Path.write_text")
    @patch("pathlib.Path.parent", new_callable=lambda: MagicMock())
    def test_write_file_creates_parent_directories(self, mock_parent, mock_write_text):
        """Test that write_file creates parent directories if they don't exist."""
        # Arrange
        file_path = "/test/nested/deep/file.txt"
        content = "Content"
        mock_parent.mkdir = MagicMock()

        # Act
        self.adapter.write_file(file_path, content)

        # Assert
        mock_parent.mkdir.assert_called_once_with(parents=True, exist_ok=True)

    @patch("pathlib.Path.iterdir")
    def test_list_directory_empty(self, mock_iterdir):
        """Test listing an empty directory."""
        # Arrange
        dir_path = "/test/empty"
        mock_iterdir.return_value = []

        # Act
        result = self.adapter.list_directory(dir_path)

        # Assert
        assert result == []

    @patch("pathlib.Path.exists")
    @patch("pathlib.Path.is_dir")
    @patch("pathlib.Path.is_file")
    def test_path_type_checks_consistency(self, mock_is_file, mock_is_dir, mock_exists):
        """Test consistency between path type checking methods."""
        # Test: path exists and is a file
        mock_exists.return_value = True
        mock_is_file.return_value = True
        mock_is_dir.return_value = False

        path = "/test/file.txt"
        assert self.adapter.path_exists(path) is True
        assert self.adapter.is_file(path) is True
        assert self.adapter.is_directory(path) is False

        # Test: path exists and is a directory
        mock_is_file.return_value = False
        mock_is_dir.return_value = True

        assert self.adapter.is_file(path) is False
        assert self.adapter.is_directory(path) is True
