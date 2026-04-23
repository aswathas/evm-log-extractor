"""Normalisation pass + validation. See raw-log-schema.md §10.

Extraction already performs type-canonicalisation (addresses checksummed,
hex lowercased, wei → decimal string). The normaliser's job is therefore:

1. stream raw → norm with identity transform (placeholder for future
   re-canonicalisation if raw is imported from another tool)
2. enforce validation rules: duplicate PKs, cross-file consistency,
   receipts.logs_count match.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .ndjson import NdjsonWriter, read_ndjson

ENTITIES = ("blocks", "transactions", "receipts", "event_logs", "call_traces", "state_diffs", "storage_diffs")
PK_BY_ENTITY = {
    "blocks": ("block_number",),
    "transactions": ("tx_hash",),
    "receipts": ("tx_hash",),
    "event_logs": ("tx_hash", "log_index"),
    "call_traces": ("tx_hash", "trace_address"),
    "state_diffs": ("tx_hash", "address"),
    "storage_diffs": ("tx_hash", "address", "slot"),
}


class ValidationError(RuntimeError):
    pass


def _copy_with_dedup_check(src: Path, dst: Path, pk_fields: tuple[str, ...]) -> int:
    seen: set = set()
    with NdjsonWriter(dst) as w:
        for rec in read_ndjson(src):
            key = tuple(rec.get(k) for k in pk_fields)
            if key in seen:
                raise ValidationError(f"{src.name}: duplicate primary key {key}")
            seen.add(key)
            w.write(rec)
    return w.count


def normalise_run(run_dir: Path | str) -> dict[str, int]:
    run = Path(run_dir)
    raw = run / "raw"
    norm = run / "norm"
    norm.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    for entity in ENTITIES:
        src = raw / f"{entity}.ndjson"
        if not src.exists():
            continue
        pk = PK_BY_ENTITY[entity]
        counts[entity] = _copy_with_dedup_check(src, norm / f"{entity}.ndjson", pk)

    if {"receipts", "event_logs"} <= counts.keys():
        log_counts: dict[str, int] = defaultdict(int)
        for log in read_ndjson(norm / "event_logs.ndjson"):
            log_counts[log["tx_hash"]] += 1
        for r in read_ndjson(norm / "receipts.ndjson"):
            expected = r.get("logs_count", 0)
            actual = log_counts.get(r["tx_hash"], 0)
            if expected != actual:
                raise ValidationError(
                    f"receipts.logs_count mismatch for tx {r['tx_hash']}: "
                    f"receipt says {expected}, event_logs has {actual}"
                )

    if {"blocks", "transactions"} <= counts.keys():
        block_numbers = {b["block_number"] for b in read_ndjson(norm / "blocks.ndjson")}
        for tx in read_ndjson(norm / "transactions.ndjson"):
            if tx["block_number"] not in block_numbers:
                raise ValidationError(
                    f"transactions.tx_hash={tx['tx_hash']} references missing block {tx['block_number']}"
                )

    return counts
