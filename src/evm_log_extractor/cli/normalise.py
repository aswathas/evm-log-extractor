"""`evm-normalise` CLI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from ..normaliser import ValidationError, normalise_run


@click.command(name="evm-normalise")
@click.option("--run", "run_id", default=None, help="Run id (combined with --base-dir)")
@click.option("--base-dir", default="output", show_default=True)
@click.option("--in-dir", "in_dir", default=None, help="Explicit run directory (overrides --run/--base-dir)")
def main(run_id: Optional[str], base_dir: str, in_dir: Optional[str]) -> None:
    if in_dir:
        run_dir = Path(in_dir)
    elif run_id:
        run_dir = Path(base_dir) / run_id
    else:
        click.echo("provide --in-dir or --run", err=True)
        sys.exit(2)
    if not run_dir.exists():
        click.echo(f"not found: {run_dir}", err=True)
        sys.exit(1)

    try:
        counts = normalise_run(run_dir)
    except ValidationError as e:
        click.echo(f"[normalise] validation error: {e}", err=True)
        sys.exit(1)

    click.echo(f"[normalise] run_dir={run_dir}")
    for entity, n in counts.items():
        click.echo(f"  {entity}: {n} records")
    click.echo("[normalise] done.")


if __name__ == "__main__":
    main()

