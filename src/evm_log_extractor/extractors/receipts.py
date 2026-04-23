"""Receipts entity extractor. See raw-log-schema.md §3."""

from __future__ import annotations

from typing import Any

from ..rpc import RpcClient
from ..types import checksum_address, hex_lower, hex_to_int, wei_str


def _as_hex(v: Any) -> str:
    if isinstance(v, bytes):
        return "0x" + v.hex()
    return str(v)


def extract_receipt(rpc: RpcClient, tx_hash: str) -> dict[str, Any]:
    raw = rpc.get_receipt(tx_hash)
    logs = raw.get("logs") or []
    return {
        "block_number": hex_to_int(raw["blockNumber"]),
        "block_hash": hex_lower(_as_hex(raw["blockHash"])),
        "tx_hash": hex_lower(_as_hex(raw["transactionHash"])),
        "tx_index": hex_to_int(raw["transactionIndex"]),
        "tx_type": hex_to_int(raw.get("type", 0)),
        "from_address": checksum_address(raw["from"]),
        "to_address": checksum_address(raw.get("to")) if raw.get("to") else None,
        "status": hex_to_int(raw["status"]),
        "gas_used": hex_to_int(raw["gasUsed"]),
        "cumulative_gas_used": hex_to_int(raw["cumulativeGasUsed"]),
        "effective_gas_price": wei_str(raw["effectiveGasPrice"]),
        "contract_address": checksum_address(raw.get("contractAddress")) if raw.get("contractAddress") else None,
        "logs_bloom": hex_lower(_as_hex(raw["logsBloom"])),
        "logs_count": len(logs),
    }

