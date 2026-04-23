"""Call traces entity extractor + tree flattener. See raw-log-schema.md §5."""

from __future__ import annotations

from typing import Any, Iterator

from ..rpc import RpcClient
from ..types import checksum_address, hex_lower, hex_to_int, wei_str


def _as_hex(v: Any) -> str:
    if isinstance(v, bytes):
        return "0x" + v.hex()
    return str(v)


def _derive_selector(input_hex: str | None) -> str | None:
    if not input_hex:
        return None
    low = input_hex.lower()
    if not low.startswith("0x") or len(low) < 10:
        return None
    return low[:10]


def flatten_tree(tree: dict[str, Any], prefix: str = "root") -> Iterator[dict[str, Any]]:
    """Walk the nested callTracer tree and yield flattened frames.

    Each yielded dict carries `trace_address`, `depth`, and the raw frame
    fields for downstream shaping.
    """

    depth = 0 if prefix == "root" else prefix.count(".") + 1
    frame = {
        "trace_address": prefix,
        "depth": depth,
        "type": tree.get("type"),
        "from": tree.get("from"),
        "to": tree.get("to"),
        "value": tree.get("value"),
        "input": tree.get("input"),
        "output": tree.get("output"),
        "gas": tree.get("gas"),
        "gasUsed": tree.get("gasUsed"),
        "error": tree.get("error"),
        "revertReason": tree.get("revertReason"),
    }
    yield frame
    for idx, child in enumerate(tree.get("calls") or []):
        child_prefix = str(idx) if prefix == "root" else f"{prefix}.{idx}"
        yield from flatten_tree(child, prefix=child_prefix)


def extract_call_traces(
    rpc: RpcClient,
    block_number: int,
    tx_hash: str,
) -> Iterator[dict[str, Any]]:
    tree = rpc.debug_trace_transaction(tx_hash, tracer="callTracer")
    for frame in flatten_tree(tree):
        input_lower = hex_lower(_as_hex(frame["input"])) if frame.get("input") else None
        yield {
            "block_number": block_number,
            "tx_hash": hex_lower(_as_hex(tx_hash)),
            "trace_address": frame["trace_address"],
            "depth": frame["depth"],
            "call_type": frame["type"],
            "from_address": checksum_address(frame["from"]) if frame.get("from") else None,
            "to_address": checksum_address(frame["to"]) if frame.get("to") else None,
            "value": wei_str(frame.get("value") or 0),
            "input": input_lower,
            "function_selector": _derive_selector(input_lower),
            "output": hex_lower(_as_hex(frame["output"])) if frame.get("output") else None,
            "gas_provided": hex_to_int(frame["gas"]) if frame.get("gas") is not None else None,
            "gas_used": hex_to_int(frame["gasUsed"]) if frame.get("gasUsed") is not None else None,
            "error": frame.get("error"),
            "revert_reason": hex_lower(_as_hex(frame["revertReason"])) if frame.get("revertReason") else None,
        }

