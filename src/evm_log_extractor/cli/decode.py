"""`evm-decode` CLI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple

import click

from ..abi_loader import load_abi_sources
from ..decoder import decode_event_logs


@click.command(name="evm-decode")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--out", "out_path", required=True, type=click.Path(path_type=Path))
@click.option("--unmatched", "unmatched_path", default=None, type=click.Path(path_type=Path))
@click.option("--manifest", "manifest_path", default=None, type=click.Path(path_type=Path))
@click.option("--abi", "abi_files", multiple=True, type=click.Path(exists=True, path_type=Path))
@click.option("--abi-dir", "abi_dirs", multiple=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--foundry-project", "foundry_project", default=None, type=click.Path(exists=True, file_okay=False, path_type=Path))
def main(
    input_path: Path,
    out_path: Path,
    unmatched_path: Optional[Path],
    manifest_path: Optional[Path],
    abi_files: Tuple[Path, ...],
    abi_dirs: Tuple[Path, ...],
    foundry_project: Optional[Path],
) -> None:
    try:
        idx = load_abi_sources(
            abi_files=list(abi_files),
            abi_dirs=list(abi_dirs),
            foundry_project=foundry_project,
        )
    except ValueError as e:
        click.echo(str(e), err=True)
        sys.exit(2)

    unmatched = unmatched_path or out_path.with_name("unmatched.ndjson")
    manifest = manifest_path or out_path.with_name("abi_manifest.json")

    stats = decode_event_logs(
        input_path=input_path,
        index=idx,
        out_path=out_path,
        unmatched_path=unmatched,
        manifest_path=manifest,
    )
    click.echo(f\"[decode] matched={stats['matched']} unmatched={stats['unmatched']}\")


if __name__ == "__main__":
    main()

