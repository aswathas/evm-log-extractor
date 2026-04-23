"""Event logs entity extractor. See raw-log-schema.md §4."""

from __future__ import annotations

from typing import Any, Iterator, Optional

from ..rpc import RpcClient
from ..types import checksum_address, hex_lower, hex_to_int


def _as_hex(v: Any) -> str:
    if isinstance(v, bytes):
        return "0x" + v.hex()
    return str(v)


def extract_event_logs(
    rpc: RpcClient,
    from_block: int,
    to_block: int,
    address: Optional[str] = None,
    topics: Optional[list] = None,
) -> Iterator[dict[str, Any]]:
    raw_logs = rpc.get_logs(
        from_block=from_block,
        to_block=to_block,
        address=address,
        topics=topics,
    )
    for log in raw_logs:
        topics_list = [hex_lower(_as_hex(t)) for t in (log.get("topics") or [])]
        padded = topics_list + [None] * (4 - len(topics_list))
        yield {
            "block_number": hex_to_int(log["blockNumber"]),
            "block_hash": hex_lower(_as_hex(log["blockHash"])),
            "tx_hash": hex_lower(_as_hex(log["transactionHash"])),
            "tx_index": hex_to_int(log["transactionIndex"]),
            "log_index": hex_to_int(log["logIndex"]),
            "address": checksum_address(log["address"]),
            "topic0": padded[0],
            "topic1": padded[1],
            "topic2": padded[2],
            "topic3": padded[3],
            "topics_count": len(topics_list),
            "data": hex_lower(_as_hex(log.get("data") or "0x")),
            "removed": bool(log.get("removed", False)),
        }

