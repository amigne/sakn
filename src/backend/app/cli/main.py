
import click

from app.cli.create_admin import create_admin
from app.cli.sync_oui import sync_oui


@click.group()
def cli():
    """SAKN administration CLI."""


cli.add_command(create_admin)
cli.add_command(sync_oui)


def main():
    cli()
