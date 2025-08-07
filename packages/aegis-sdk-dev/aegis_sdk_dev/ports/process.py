"""Process execution port for running external commands."""

from __future__ import annotations

from typing import Protocol


class ProcessExecutorPort(Protocol):
    """Port for executing external processes."""

    async def execute_command(
        self,
        command: list[str],
        cwd: str | None = None,
        timeout: float | None = None,
    ) -> tuple[int, str, str]:
        """Execute an external command.

        Args:
            command: Command and arguments as list
            cwd: Working directory for command execution
            timeout: Execution timeout in seconds

        Returns:
            Tuple of (exit_code, stdout, stderr)

        Raises:
            TimeoutError: If command exceeds timeout
            OSError: If command cannot be executed
        """
        ...

    async def run_pytest(
        self,
        args: list[str],
        cwd: str | None = None,
        timeout: float = 300.0,
    ) -> tuple[int, str]:
        """Run pytest with specified arguments.

        Args:
            args: Pytest arguments
            cwd: Working directory
            timeout: Test execution timeout

        Returns:
            Tuple of (exit_code, output)

        Raises:
            TimeoutError: If tests exceed timeout
        """
        ...

    def check_command_exists(self, command: str) -> bool:
        """Check if a command exists in the system.

        Args:
            command: Command name to check

        Returns:
            True if command exists, False otherwise
        """
        ...
