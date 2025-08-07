"""Console adapter implementation using Rich library."""

from __future__ import annotations

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table


class ConsoleAdapter:
    """Adapter for console operations using Rich library."""

    def __init__(self, console: Console | None = None):
        """Initialize console adapter.

        Args:
            console: Optional Rich console instance
        """
        self._console = console or Console()

    def print(self, message: str, style: str | None = None) -> None:
        """Print a message to the console."""
        if style:
            self._console.print(f"[{style}]{message}[/{style}]")
        else:
            self._console.print(message)

    def print_error(self, message: str) -> None:
        """Print an error message to the console."""
        self._console.print(f"[red bold]Error:[/red bold] {message}")

    def print_warning(self, message: str) -> None:
        """Print a warning message to the console."""
        self._console.print(f"[yellow]Warning:[/yellow] {message}")

    def print_success(self, message: str) -> None:
        """Print a success message to the console."""
        self._console.print(f"[green]✓[/green] {message}")

    def print_table(
        self, headers: list[str], rows: list[list[str]], title: str | None = None
    ) -> None:
        """Print a formatted table to the console."""
        table = Table(title=title, box=box.SIMPLE)

        for header in headers:
            table.add_column(header)

        for row in rows:
            table.add_row(*row)

        self._console.print(table)

    def print_panel(self, content: str, title: str | None = None, style: str | None = None) -> None:
        """Print a formatted panel to the console."""
        panel = Panel(content, title=title, box=box.ROUNDED)
        if style:
            self._console.print(panel, style=style)
        else:
            self._console.print(panel)

    def prompt(self, message: str, default: str | None = None) -> str:
        """Prompt the user for input."""
        return Prompt.ask(message, default=default)

    def confirm(self, message: str, default: bool = False) -> bool:
        """Ask the user for confirmation."""
        return Confirm.ask(message, default=default)
