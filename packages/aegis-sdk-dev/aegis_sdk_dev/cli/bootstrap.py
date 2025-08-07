"""Bootstrap CLI for service initialization."""

import click


class BootstrapCLI:
    """Bootstrap CLI for service setup."""

    pass


@click.command()
def main():
    """Bootstrap a new AegisSDK service."""
    click.echo("Bootstrap service - see aegis-sdk-examples for templates")


if __name__ == "__main__":
    main()
