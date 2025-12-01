#!/usr/bin/env python3
"""
CLI wrapper for converting Markdown quizzes to Moodle XML.

Usage:
    uv run cli.py convert --md examples/sample-questions.md --output out/quiz.xml
"""

from __future__ import annotations

from pathlib import Path

import click

from md2moodle import parse_markdown


@click.group(help="Learning Mall Markdown utilities.")
def cli() -> None:
    """Base CLI group."""


@cli.command()
@click.option(
    "--md",
    "md_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, readable=True, path_type=Path),
    help="Markdown source file.",
)
@click.option(
    "--output",
    "output_path",
    default=Path("examples/generated-from-md.xml"),
    show_default=True,
    type=click.Path(dir_okay=False, writable=True, path_type=Path),
    help="Destination Moodle XML file.",
)
@click.option(
    "--pretty/--no-pretty",
    default=True,
    show_default=True,
    help="Whether to pretty-print the generated XML.",
)
def convert(md_path: Path, output_path: Path, pretty: bool) -> None:
    """Convert a Markdown quiz file into Moodle XML."""
    try:
        md_text = md_path.read_text()
    except OSError as exc:
        click.echo(f"Failed to read markdown file: {exc}", err=True)
        raise click.Abort() from exc

    try:
        quiz = parse_markdown(md_text)
    except Exception as exc:  # noqa: BLE001 - surface parse errors to the user
        click.echo(f"Failed to parse markdown: {exc}", err=True)
        raise click.Abort() from exc

    if output_path.parent and not output_path.parent.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        out_path = quiz.save(output_path, pretty_print=pretty)
    except Exception as exc:  # noqa: BLE001 - surface save errors to the user
        click.echo(f"Failed to write XML: {exc}", err=True)
        raise click.Abort() from exc

    click.echo(f"Wrote {out_path}")


if __name__ == "__main__":
    cli()
