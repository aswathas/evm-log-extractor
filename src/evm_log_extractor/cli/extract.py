"""`evm-extract` CLI — pulls raw entities from JSON-RPC into NDJSON files."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from .. import __version__
from ..extractors.blocks import extract_block
from ..extractors.call_traces import extract_call_traces
from ..extractors.event_logs import extract_event_logs
from ..extractors.receipts import extract_receipt
from ..extractors.state_diffs import extract_state_diffs
from ..extractors.storage_diffs import extract_storage_diffs
from ..extractors.transactions import extract_transactions
from ..manifest import Manifest
from ..ndjson import NdjsonWriter
from ..rpc import RpcClient

TIER1 = ("blocks", "transactions", "receipts", "event_logs", "call_traces")
TIER2 = ("state_diffs", "storage_diffs")
ALL_ENTITIES = TIER1 + TIER2


def _resolve_block(rpc: RpcClient, value: str) -> int:
    return rpc.latest_block() if value == "latest" else int(value)


@click.command(name="evm-extract")
@click.option("--rpc", "rpc_url", default="http://127.0.0.1:8545", show_default=True, help="JSON-RPC endpoint")
@click.option("--tx", "tx_hash", default=None, help="Extract for a single transaction hash (required for tier-2 diffs)")
@click.option("--from-block", "from_block", required=False, help="Starting block number or 'latest'")
@click.option("--to-block", "to_block", required=False, help="Ending block number or 'latest'")
@click.option("--entities", default=",".join(TIER1), show_default=True, help="Comma-separated entity list")
@click.option("--address", default=None, help="Filter event_logs by emitter address")
@click.option("--base-dir", "base_dir", default="output", show_default=True, help="Parent directory for run folders")
@click.option("--label", default=None, help="Human-friendly run label (appears in run-id)")
def main(
    rpc_url: str,
    tx_hash: Optional[str],
    from_block: str,
    to_block: str,
    entities: str,
    address: Optional[str],
    base_dir: str,
    label: Optional[str],
) -> None:
    selected = [e.strip() for e in entities.split(",") if e.strip()]
    for e in selected:
        if e not in ALL_ENTITIES:
            click.echo(f"unknown entity: {e}. Supported: {ALL_ENTITIES}", err=True)
            sys.exit(2)

    rpc = RpcClient.from_url(rpc_url)
    chain_id = rpc.chain_id()
    want_tier2 = any(e in TIER2 for e in selected)
    if want_tier2 and not tx_hash:
        click.echo("tier-2 entities (state_diffs/storage_diffs) require --tx <hash>", err=True)
        sys.exit(2)

    if tx_hash:
        from_n = None
        to_n = None
    else:
        if from_block is None or to_block is None:
            click.echo("provide either --tx or both --from-block/--to-block", err=True)
            sys.exit(2)
        from_n = _resolve_block(rpc, from_block)
        to_n = _resolve_block(rpc, to_block)
        if from_n > to_n:
            click.echo(f"from-block {from_n} > to-block {to_n}", err=True)
            sys.exit(2)

    rid_label = label or (f"tx-{tx_hash[:10]}" if tx_hash else None)
    run_id = Manifest.build_run_id(rid_label, from_n if from_n is not None else "tx", to_n if to_n is not None else "tx")
    run_dir = Path(base_dir) / run_id
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    manifest = Manifest(
        run_id=run_id,
        tool_version=__version__,
        rpc_url=rpc_url,
        chain_id=chain_id,
        cli_args={
            "tx_hash": tx_hash,
            "from_block": from_n,
            "to_block": to_n,
            "entities": selected,
            "address_filter": address,
        },
    )
    manifest.set_node_info(rpc.anvil_node_info())

    counts: dict[str, int] = {}
    hashes: dict[str, str] = {}

    def _write(entity: str, iterator):
        path = raw_dir / f"{entity}.ndjson"
        with NdjsonWriter(path) as w:
            for rec in iterator:
                w.write(rec)
        counts[entity] = w.count
        hashes[f"raw/{entity}.ndjson"] = f"sha256:{w.sha256}"
        click.echo(f"  {entity}: {w.count} records")

    if tx_hash:
        click.echo(f"[extract] run_id={run_id} tx={tx_hash}")
    else:
        click.echo(f"[extract] run_id={run_id} blocks={from_n}..{to_n}")

    if "blocks" in selected:
        assert from_n is not None and to_n is not None
        _write("blocks", (extract_block(rpc, n) for n in range(from_n, to_n + 1)))

    if "transactions" in selected:
        assert from_n is not None and to_n is not None
        def _tx_iter():
            for n in range(from_n, to_n + 1):
                yield from extract_transactions(rpc, n)

        _write("transactions", _tx_iter())

    if "receipts" in selected:
        assert from_n is not None and to_n is not None
        def _rc_iter():
            for n in range(from_n, to_n + 1):
                blk = rpc.get_block(n, full_tx=False)
                for tx_hash in blk.get("transactions") or []:
                    h = tx_hash if isinstance(tx_hash, str) else "0x" + tx_hash.hex()
                    yield extract_receipt(rpc, h)

        _write("receipts", _rc_iter())

    if "event_logs" in selected:
        if tx_hash:
            # debug_traceTransaction does not provide logs; use range mode for logs.
            click.echo("event_logs requires --from-block/--to-block (not supported with --tx-only mode)", err=True)
            sys.exit(2)
        assert from_n is not None and to_n is not None
        _write("event_logs", extract_event_logs(rpc, from_n, to_n, address=address))

    if "call_traces" in selected:
        if tx_hash:
            # Use receipt for block_number in tx-only mode.
            receipt = rpc.get_receipt(tx_hash)
            bn = int(receipt["blockNumber"], 16) if isinstance(receipt.get("blockNumber"), str) else int(receipt["blockNumber"])
            _write("call_traces", extract_call_traces(rpc, block_number=bn, tx_hash=tx_hash))
        else:
            assert from_n is not None and to_n is not None
            def _ct_iter():
                for n in range(from_n, to_n + 1):
                    blk = rpc.get_block(n, full_tx=False)
                    for tx_hash in blk.get("transactions") or []:
                        h = tx_hash if isinstance(tx_hash, str) else "0x" + tx_hash.hex()
                        yield from extract_call_traces(rpc, block_number=n, tx_hash=h)

            _write("call_traces", _ct_iter())

    if "state_diffs" in selected:
        assert tx_hash is not None
        _write("state_diffs", extract_state_diffs(rpc, tx_hash))

    if "storage_diffs" in selected:
        assert tx_hash is not None
        _write("storage_diffs", extract_storage_diffs(rpc, tx_hash))

    manifest.set_counts(counts)
    manifest.set_hashes(hashes)
    manifest.write(run_dir / "manifest.json")

    click.echo(f"[extract] done. output: {run_dir}")


if __name__ == "__main__":
    main()
