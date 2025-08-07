"""Process executor adapter implementation."""

from __future__ import annotations

import asyncio
import shutil


class ProcessExecutorAdapter:
    """Adapter for executing external processes."""

    async def execute_command(
        self,
        command: list[str],
        cwd: str | None = None,
        timeout: float | None = None,
    ) -> tuple[int, str, str]:
        """Execute an external command."""
        try:
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                raise TimeoutError(f"Command timed out after {timeout} seconds")

            return (
                process.returncode or 0,
                stdout.decode("utf-8") if stdout else "",
                stderr.decode("utf-8") if stderr else "",
            )

        except FileNotFoundError as e:
            raise OSError(f"Command not found: {command[0]}") from e
        except Exception as e:
            raise OSError(f"Failed to execute command: {e}") from e

    async def run_pytest(
        self,
        args: list[str],
        cwd: str | None = None,
        timeout: float = 300.0,
    ) -> tuple[int, str]:
        """Run pytest with specified arguments."""
        # Construct pytest command
        command = ["python", "-m", "pytest"] + args

        exit_code, stdout, stderr = await self.execute_command(command, cwd=cwd, timeout=timeout)

        # Combine stdout and stderr for pytest output
        output = stdout
        if stderr:
            output += "\n" + stderr

        return exit_code, output

    def check_command_exists(self, command: str) -> bool:
        """Check if a command exists in the system."""
        return shutil.which(command) is not None
