"""State diffs entity extractor. See raw-log-schema.md §6."""

from __future__ import annotations

from typing import Any, Iterator

from ..rpc import RpcClient
from ..types import checksum_address, hex_lower, hex_to_int, signed_wei_delta, wei_str


def _as_hex(v: Any) -> str:
    if isinstance(v, bytes):
        return "0x" + v.hex()
    return str(v)


def extract_state_diffs(rpc: RpcClient, tx_hash: str) -> Iterator[dict[str, Any]]:
    """Yield per-address state diffs for a single transaction hash."""
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
        bal_before = wei_str(pre_a.get("balance") or 0) or "0"
        bal_after = wei_str(post_a.get("balance") or 0) or "0"
        nonce_before = hex_to_int(pre_a.get("nonce") or 0) or 0
        nonce_after = hex_to_int(post_a.get("nonce") or 0) or 0
        code_before = hex_lower(_as_hex(pre_a.get("code") or "0x"))
        code_after = hex_lower(_as_hex(post_a.get("code") or "0x"))

        yield {
            "block_number": block_number,
            "tx_hash": txh,
            "address": checksum_address(addr),
            "balance_before": bal_before,
            "balance_after": bal_after,
            "balance_delta": signed_wei_delta(bal_after, bal_before),
            "nonce_before": nonce_before,
            "nonce_after": nonce_after,
            "code_changed": code_before != code_after,
        }

