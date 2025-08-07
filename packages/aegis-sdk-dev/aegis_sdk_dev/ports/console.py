"""Console port for user interface operations."""

from __future__ import annotations

from typing import Protocol


class ConsolePort(Protocol):
    """Port for console/terminal operations."""

    def print(self, message: str, style: str | None = None) -> None:
        """Print a message to the console.

        Args:
            message: Message to print
            style: Optional style/color formatting
        """
        ...

    def print_error(self, message: str) -> None:
        """Print an error message to the console.

        Args:
            message: Error message to print
        """
        ...

    def print_warning(self, message: str) -> None:
        """Print a warning message to the console.

        Args:
            message: Warning message to print
        """
        ...

    def print_success(self, message: str) -> None:
        """Print a success message to the console.

        Args:
            message: Success message to print
        """
        ...

    def print_table(
        self, headers: list[str], rows: list[list[str]], title: str | None = None
    ) -> None:
        """Print a formatted table to the console.

        Args:
            headers: Table column headers
            rows: Table data rows
            title: Optional table title
        """
        ...

    def print_panel(self, content: str, title: str | None = None, style: str | None = None) -> None:
        """Print a formatted panel to the console.

        Args:
            content: Panel content
            title: Optional panel title
            style: Optional panel style
        """
        ...

    def prompt(self, message: str, default: str | None = None) -> str:
        """Prompt the user for input.

        Args:
            message: Prompt message
            default: Default value if no input provided

        Returns:
            User input string
        """
        ...

    def confirm(self, message: str, default: bool = False) -> bool:
        """Ask the user for confirmation.

        Args:
            message: Confirmation message
            default: Default response if no input

        Returns:
            True if confirmed, False otherwise
        """
        ...
