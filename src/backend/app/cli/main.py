import asyncio

import click

from app.cli.create_admin import create_admin


@click.group()
def cli():
    """SAKN administration CLI."""


cli.add_command(create_admin)


def main():
    cli()
