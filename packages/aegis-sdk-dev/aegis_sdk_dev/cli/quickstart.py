"""Quickstart CLI for rapid service development."""

import click
from rich.console import Console


class QuickstartCLI:
    """CLI for quickstart operations."""

    def __init__(self):
        self.console = Console()


@click.command()
def main():
    """Launch quickstart wizard for creating new services."""
    console = Console()
    console.print("[bold cyan]AegisSDK Quickstart[/bold cyan]")
    console.print("Use aegis-sdk-examples package for comprehensive examples.")


if __name__ == "__main__":
    main()
