"""Storage diffs entity extractor. See raw-log-schema.md §7."""

from __future__ import annotations

from typing import Any, Iterator

from ..rpc import RpcClient
from ..types import checksum_address, hex_lower, hex_to_int


def _as_hex(v: Any) -> str:
    if isinstance(v, bytes):
        return "0x" + v.hex()
    return str(v)


def _pad_32(h: str) -> str:
    low = hex_lower(h)
    return "0x" + low[2:].rjust(64, "0")


def extract_storage_diffs(rpc: RpcClient, tx_hash: str) -> Iterator[dict[str, Any]]:
    """Yield per-(address,slot) storage diffs for a single transaction hash."""
    txh = hex_lower(_as_hex(tx_hash))
    receipt = rpc.get_receipt(txh)
    block_number = hex_to_int(receipt["blockNumber"])

    trace = rpc.debug_trace_transaction(txh, tracer="prestateTracer", tracer_config={"diffMode": True})
    pre = trace.get("pre") or {}
    post = trace.get("post") or {}

    all_addrs = set(pre) | set(post)
    for addr in sorted(all_addrs):
        pre_a = pre.get(addr) or {}
        post_a = post.get(addr) or {}
        pre_s = pre_a.get("storage") or {}
        post_s = post_a.get("storage") or {}

        all_slots = set(pre_s) | set(post_s)
        for slot in sorted(all_slots):
            before = pre_s.get(slot) or "0x0"
            after = post_s.get(slot) or "0x0"
            yield {
                "block_number": block_number,
                "tx_hash": txh,
                "address": checksum_address(addr),
                "slot": _pad_32(_as_hex(slot)),
                "value_before": _pad_32(_as_hex(before)),
                "value_after": _pad_32(_as_hex(after)),
            }

