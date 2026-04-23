"""Transactions entity extractor. See raw-log-schema.md §2."""

from __future__ import annotations

from typing import Any, Iterator

from ..rpc import RpcClient
from ..types import checksum_address, hex_lower, hex_to_int, wei_str


def _as_hex(v: Any) -> str:
    if isinstance(v, bytes):
        return "0x" + v.hex()
    return str(v)


def _derive_selector(input_hex: str) -> str | None:
    low = input_hex.lower()
    if not low.startswith("0x") or len(low) < 10:
        return None
    return low[:10]


def extract_transactions(rpc: RpcClient, block_number: int) -> Iterator[dict[str, Any]]:
    raw = rpc.get_block(block_number, full_tx=True)
    for tx in raw.get("transactions") or []:
        input_lower = hex_lower(_as_hex(tx.get("input") or "0x"))
        yield {
            "block_number": hex_to_int(tx["blockNumber"]),
            "block_hash": hex_lower(_as_hex(tx["blockHash"])),
            "tx_hash": hex_lower(_as_hex(tx["hash"])),
            "tx_index": hex_to_int(tx["transactionIndex"]),
            "tx_type": hex_to_int(tx.get("type", 0)),
            "chain_id": hex_to_int(tx.get("chainId")) if tx.get("chainId") is not None else None,
            "from_address": checksum_address(tx["from"]),
            "to_address": checksum_address(tx.get("to")) if tx.get("to") else None,
            "value": wei_str(tx.get("value", 0)),
            "input": input_lower,
            "function_selector": _derive_selector(input_lower),
            "nonce": hex_to_int(tx["nonce"]),
            "gas_limit": hex_to_int(tx["gas"]),
            "gas_price": wei_str(tx.get("gasPrice")) if tx.get("gasPrice") is not None else None,
            "max_fee_per_gas": wei_str(tx.get("maxFeePerGas")) if tx.get("maxFeePerGas") is not None else None,
            "max_priority_fee_per_gas": wei_str(tx.get("maxPriorityFeePerGas"))
            if tx.get("maxPriorityFeePerGas") is not None
            else None,
            "access_list": tx.get("accessList"),
            "v": str(hex_to_int(tx["v"])) if tx.get("v") is not None else None,
            "r": hex_lower(_as_hex(tx["r"])),
            "s": hex_lower(_as_hex(tx["s"])),
            "y_parity": hex_to_int(tx.get("yParity")) if tx.get("yParity") is not None else None,
        }

