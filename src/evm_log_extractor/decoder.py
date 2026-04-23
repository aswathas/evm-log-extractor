"""Event-log decoder. See raw-log-schema.md §Decode Pass."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eth_abi import decode as abi_decode
from .types import checksum_address

from .abi_loader import AbiIndex
from .ndjson import NdjsonWriter, read_ndjson


def _event_signature(abi_entry: dict) -> str:
    return f"{abi_entry['name']}({','.join(i['type'] for i in abi_entry.get('inputs', []))})"


def _decode_topic_word(word_hex: str, sol_type: str) -> Any:
    b = bytes.fromhex(word_hex[2:])
    if sol_type == "address":
        return checksum_address("0x" + b[-20:].hex())
    if sol_type.startswith("uint") or sol_type.startswith("int"):
        return str(int.from_bytes(b, "big", signed=sol_type.startswith("int")))
    if sol_type == "bool":
        return bool(int.from_bytes(b, "big"))
    return word_hex


def _decode_data(data_hex: str, types: list[str]) -> list[Any]:
    raw = bytes.fromhex(data_hex[2:]) if data_hex and data_hex != "0x" else b""
    if not types:
        return []
    vals = abi_decode(types, raw)
    out: list[Any] = []
    for t, v in zip(types, vals):
        if t == "address":
            out.append(checksum_address(v))
        elif t.startswith("uint") or t.startswith("int"):
            out.append(str(v))
        elif isinstance(v, (bytes, bytearray)):
            out.append("0x" + bytes(v).hex())
        else:
            out.append(v)
    return out


def _decode_one(log: dict, event_abi: dict) -> dict[str, Any]:
    topics = [log.get("topic0"), log.get("topic1"), log.get("topic2"), log.get("topic3")]
    topics = [t for t in topics if t is not None]
    indexed_inputs = [i for i in event_abi.get("inputs", []) if i.get("indexed")]
    non_indexed = [i for i in event_abi.get("inputs", []) if not i.get("indexed")]

    decoded: dict[str, Any] = {}
    for i, inp in enumerate(indexed_inputs):
        decoded[inp["name"]] = _decode_topic_word(topics[i + 1], inp["type"])

    values = _decode_data(log.get("data") or "0x", [i["type"] for i in non_indexed])
    for inp, v in zip(non_indexed, values):
        decoded[inp["name"]] = v

    return decoded


def decode_event_logs(
    input_path: Path | str,
    index: AbiIndex,
    out_path: Path | str,
    unmatched_path: Path | str,
    manifest_path: Path | str | None = None,
) -> dict[str, int]:
    matched = 0
    unmatched = 0
    match_counts: dict[str, int] = {}
    unmatched_counts: dict[str, int] = {}

    with NdjsonWriter(out_path) as w_out, NdjsonWriter(unmatched_path) as w_u:
        for log in read_ndjson(input_path):
            topic0 = log.get("topic0")
            event = index.lookup_event(topic0) if topic0 else None

            if event is None:
                out = dict(log)
                out["event_name"] = None
                out["event_signature"] = None
                out["decoded"] = None
                w_out.write(out)
                w_u.write(log)
                unmatched += 1
                if topic0:
                    unmatched_counts[topic0] = unmatched_counts.get(topic0, 0) + 1
                continue

            try:
                decoded = _decode_one(log, event)
            except Exception as exc:  # noqa: BLE001
                out = dict(log)
                out["event_name"] = event.get("name")
                out["event_signature"] = _event_signature(event)
                out["decoded"] = None
                out["decode_error"] = str(exc)
                w_out.write(out)
                unmatched += 1
                continue

            out = dict(log)
            out["event_name"] = event["name"]
            out["event_signature"] = _event_signature(event)
            out["decoded"] = decoded
            w_out.write(out)
            matched += 1
            match_counts[topic0] = match_counts.get(topic0, 0) + 1

    if manifest_path:
        manifest = {
            "known_events": index.known_topic0s,
            "known_functions": index.known_selectors,
            "match_counts": match_counts,
            "unmatched_counts": unmatched_counts,
        }
        Path(manifest_path).write_text(json.dumps(manifest, indent=2) + "\n")

    return {"matched": matched, "unmatched": unmatched}
