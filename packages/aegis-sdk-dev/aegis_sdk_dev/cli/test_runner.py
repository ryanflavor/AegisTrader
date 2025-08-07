"""Test runner CLI for SDK testing."""

import click


class TestRunner:
    """Test runner for SDK services."""

    pass


@click.command()
def main():
    """Run tests for AegisSDK services."""
    click.echo("Test runner - use pytest for testing")


if __name__ == "__main__":
    main()
