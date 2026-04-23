"""Blocks entity extractor. See raw-log-schema.md §1."""

from __future__ import annotations

from typing import Any

from ..rpc import RpcClient
from ..types import checksum_address, hex_lower, hex_to_int, wei_str


def _as_hex(v: Any) -> str:
    if isinstance(v, bytes):
        return "0x" + v.hex()
    return str(v)


def extract_block(rpc: RpcClient, block_number: int) -> dict[str, Any]:
    raw = rpc.get_block(block_number, full_tx=False)

    txs = raw.get("transactions") or []
    return {
        "block_number": hex_to_int(raw["number"]),
        "block_hash": hex_lower(_as_hex(raw["hash"])),
        "parent_hash": hex_lower(_as_hex(raw["parentHash"])),
        "timestamp": hex_to_int(raw["timestamp"]),
        "miner": checksum_address(raw["miner"]),
        "gas_limit": hex_to_int(raw["gasLimit"]),
        "gas_used": hex_to_int(raw["gasUsed"]),
        "base_fee_per_gas": wei_str(raw.get("baseFeePerGas")),
        "transaction_count": len(txs),
        "size": hex_to_int(raw["size"]),
        "state_root": hex_lower(_as_hex(raw["stateRoot"])),
        "transactions_root": hex_lower(_as_hex(raw["transactionsRoot"])),
        "receipts_root": hex_lower(_as_hex(raw["receiptsRoot"])),
        "sha3_uncles": hex_lower(_as_hex(raw["sha3Uncles"])),
        "logs_bloom": hex_lower(_as_hex(raw["logsBloom"])),
        "extra_data": hex_lower(_as_hex(raw["extraData"])),
        "nonce": hex_lower(_as_hex(raw["nonce"])),
        "mix_hash": hex_lower(_as_hex(raw["mixHash"])),
        "difficulty": wei_str(raw["difficulty"]),
        "total_difficulty": wei_str(raw.get("totalDifficulty")),
        "withdrawals_root": hex_lower(_as_hex(raw["withdrawalsRoot"])) if raw.get("withdrawalsRoot") else None,
    }

