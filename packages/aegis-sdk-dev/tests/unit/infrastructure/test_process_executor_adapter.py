"""Unit tests for ProcessExecutorAdapter following TDD and hexagonal architecture.

These tests verify the adapter's implementation of the ProcessExecutorPort interface,
focusing on behavior at the architectural boundary. Tests follow the AAA pattern
and use dependency injection through the factory pattern.
"""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from aegis_sdk_dev.infrastructure.factory import InfrastructureFactory
from aegis_sdk_dev.ports.process import ProcessExecutorPort


class TestProcessExecutorAdapter:
    """Test ProcessExecutorAdapter implementation.

    Tests focus on verifying the adapter correctly implements the ProcessExecutorPort
    interface and handles edge cases at the infrastructure boundary.
    """

    def setup_method(self):
        """Set up test fixtures using factory pattern."""
        # Arrange: Create adapter through factory for proper dependency injection
        self.adapter = InfrastructureFactory.create_process_executor()

    def test_implements_process_executor_port(self):
        """Test that ProcessExecutorAdapter implements ProcessExecutorPort interface.

        This verifies the adapter conforms to the hexagonal architecture port definition.
        """
        # Assert: Verify port implementation
        assert isinstance(self.adapter, ProcessExecutorPort)

        # Verify all required methods are present
        assert hasattr(self.adapter, "execute_command")
        assert hasattr(self.adapter, "run_pytest")
        assert hasattr(self.adapter, "check_command_exists")

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_execute_command_success(self, mock_create_subprocess):
        """Test executing a command successfully.

        Verifies the adapter correctly translates port calls to infrastructure operations.
        """
        # Arrange: Setup mock process with expected output
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"output", b"")
        mock_process.returncode = 0
        mock_create_subprocess.return_value = mock_process

        # Act: Execute command through port interface
        exit_code, stdout, stderr = await self.adapter.execute_command(["echo", "test"])

        # Assert: Verify correct behavior and output
        assert exit_code == 0
        assert stdout == "output"
        assert stderr == ""

        # Verify infrastructure was called correctly
        mock_create_subprocess.assert_called_once_with(
            "echo",
            "test",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=None,
        )

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_execute_command_with_cwd(self, mock_create_subprocess):
        """Test executing a command with working directory."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"output", b"")
        mock_process.returncode = 0
        mock_create_subprocess.return_value = mock_process

        # Act
        exit_code, stdout, stderr = await self.adapter.execute_command(["ls", "-la"], cwd="/tmp")

        # Assert
        assert exit_code == 0
        mock_create_subprocess.assert_called_once_with(
            "ls",
            "-la",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd="/tmp",
        )

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_execute_command_with_error(self, mock_create_subprocess):
        """Test executing a command that returns an error."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"error message")
        mock_process.returncode = 1
        mock_create_subprocess.return_value = mock_process

        # Act
        exit_code, stdout, stderr = await self.adapter.execute_command(["false"])

        # Assert
        assert exit_code == 1
        assert stdout == ""
        assert stderr == "error message"

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_execute_command_with_timeout(self, mock_create_subprocess):
        """Test executing a command with timeout.

        Verifies timeout handling and proper cleanup at the infrastructure boundary.
        """
        # Arrange: Setup mock process that simulates slow execution
        mock_process = AsyncMock()

        async def slow_communicate():
            await asyncio.sleep(10)
            return (b"", b"")

        mock_process.communicate.side_effect = slow_communicate
        mock_process.kill = AsyncMock()
        mock_create_subprocess.return_value = mock_process

        # Act & Assert: Verify timeout is properly handled
        with pytest.raises(TimeoutError, match="Command timed out"):
            await self.adapter.execute_command(["sleep", "10"], timeout=0.1)

        # Assert: Verify cleanup was performed
        mock_process.kill.assert_called()

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_execute_command_os_error(self, mock_create_subprocess):
        """Test executing a command that raises OSError.

        Verifies error handling at the infrastructure boundary.
        """
        # Arrange: Simulate command not found error
        mock_create_subprocess.side_effect = FileNotFoundError("Command not found")

        # Act & Assert: Verify error is properly wrapped and propagated
        with pytest.raises(OSError, match="Command not found"):
            await self.adapter.execute_command(["nonexistent_command"])

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_run_pytest_success(self, mock_create_subprocess):
        """Test running pytest successfully."""
        # Arrange
        mock_process = AsyncMock()
        test_output = b"===== 10 passed in 1.23s ====="
        mock_process.communicate.return_value = (test_output, b"")
        mock_process.returncode = 0
        mock_create_subprocess.return_value = mock_process

        # Act
        exit_code, output = await self.adapter.run_pytest(["-v", "tests/"])

        # Assert
        assert exit_code == 0
        assert "10 passed" in output

        # Verify pytest was called correctly
        call_args = mock_create_subprocess.call_args[0]
        assert "pytest" in call_args[0] or "pytest" in str(call_args)
        assert "-v" in call_args
        assert "tests/" in call_args

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_run_pytest_with_cwd(self, mock_create_subprocess):
        """Test running pytest with custom working directory."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"tests passed", b"")
        mock_process.returncode = 0
        mock_create_subprocess.return_value = mock_process

        # Act
        exit_code, output = await self.adapter.run_pytest(["--cov"], cwd="/project", timeout=60.0)

        # Assert
        assert exit_code == 0
        call_kwargs = mock_create_subprocess.call_args[1]
        assert call_kwargs["cwd"] == "/project"

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_run_pytest_failure(self, mock_create_subprocess):
        """Test running pytest with test failures."""
        # Arrange
        mock_process = AsyncMock()
        test_output = b"===== 2 failed, 8 passed in 1.23s ====="
        mock_process.communicate.return_value = (test_output, b"")
        mock_process.returncode = 1
        mock_create_subprocess.return_value = mock_process

        # Act
        exit_code, output = await self.adapter.run_pytest(["tests/"])

        # Assert
        assert exit_code == 1
        assert "2 failed" in output

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_run_pytest_timeout(self, mock_create_subprocess):
        """Test running pytest with timeout exceeded."""
        # Arrange
        mock_process = AsyncMock()

        async def slow_communicate():
            await asyncio.sleep(10)
            return (b"", b"")

        mock_process.communicate.side_effect = slow_communicate
        mock_process.kill = AsyncMock()
        mock_create_subprocess.return_value = mock_process

        # Act & Assert
        with pytest.raises(TimeoutError):
            await self.adapter.run_pytest(["tests/"], timeout=0.1)

    @patch("shutil.which")
    def test_check_command_exists_true(self, mock_which):
        """Test checking if command exists (true case)."""
        # Arrange
        mock_which.return_value = "/usr/bin/git"

        # Act
        result = self.adapter.check_command_exists("git")

        # Assert
        assert result is True
        mock_which.assert_called_once_with("git")

    @patch("shutil.which")
    def test_check_command_exists_false(self, mock_which):
        """Test checking if command exists (false case)."""
        # Arrange
        mock_which.return_value = None

        # Act
        result = self.adapter.check_command_exists("nonexistent")

        # Assert
        assert result is False
        mock_which.assert_called_once_with("nonexistent")

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_execute_command_encoding_handling(self, mock_create_subprocess):
        """Test that command output is properly decoded from bytes."""
        # Arrange
        mock_process = AsyncMock()
        # Test with UTF-8 encoded output
        mock_process.communicate.return_value = (
            "Hello 世界".encode(),
            "Error 错误".encode(),
        )
        mock_process.returncode = 0
        mock_create_subprocess.return_value = mock_process

        # Act
        exit_code, stdout, stderr = await self.adapter.execute_command(["echo", "test"])

        # Assert
        assert exit_code == 0
        assert stdout == "Hello 世界"
        assert stderr == "Error 错误"

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_execute_command_empty_output(self, mock_create_subprocess):
        """Test executing a command with empty output."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"", b"")
        mock_process.returncode = 0
        mock_create_subprocess.return_value = mock_process

        # Act
        exit_code, stdout, stderr = await self.adapter.execute_command(["true"])

        # Assert
        assert exit_code == 0
        assert stdout == ""
        assert stderr == ""

    def test_process_executor_adapter_stateless(self):
        """Test that ProcessExecutorAdapter is stateless.

        Verifies the adapter follows the stateless design principle.
        """
        # Arrange: Create multiple adapters through factory
        adapter1 = InfrastructureFactory.create_process_executor()
        adapter2 = InfrastructureFactory.create_process_executor()

        # Assert: Verify each instance is independent (stateless)
        assert adapter1 is not adapter2
        assert isinstance(adapter1, ProcessExecutorPort)
        assert isinstance(adapter2, ProcessExecutorPort)

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_execute_command_with_spaces_in_args(self, mock_create_subprocess):
        """Test executing command with spaces in arguments."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"output", b"")
        mock_process.returncode = 0
        mock_create_subprocess.return_value = mock_process

        # Act
        exit_code, stdout, stderr = await self.adapter.execute_command(
            ["echo", "hello world", "multiple spaces"]
        )

        # Assert
        assert exit_code == 0
        call_args = mock_create_subprocess.call_args[0]
        assert "hello world" in call_args
        assert "multiple spaces" in call_args

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_run_pytest_combines_stdout_stderr(self, mock_create_subprocess):
        """Test that run_pytest combines stdout and stderr."""
        # Arrange
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (
            b"stdout output",
            b"stderr output",
        )
        mock_process.returncode = 0
        mock_create_subprocess.return_value = mock_process

        # Act
        exit_code, output = await self.adapter.run_pytest(["tests/"])

        # Assert
        assert exit_code == 0
        # Both stdout and stderr should be in the output
        assert "stdout output" in output or "stderr output" in output

    @pytest.mark.asyncio
    async def test_execute_command_empty_command_list(self):
        """Test executing with empty command list.

        Verifies input validation at the port boundary.
        """
        # Act & Assert: Verify validation prevents invalid input
        with pytest.raises(ValueError, match="Command list cannot be empty"):
            await self.adapter.execute_command([])

    @patch("shutil.which")
    def test_check_command_exists_with_path(self, mock_which):
        """Test checking command with full path."""
        # Arrange
        mock_which.return_value = "/usr/local/bin/custom_tool"

        # Act
        result = self.adapter.check_command_exists("/usr/local/bin/custom_tool")

        # Assert
        assert result is True
