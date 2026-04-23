"""ABI loader: Foundry artifact, Hardhat artifact, or raw ABI array.

Builds topic0 → event and selector → function indexes for the decoder.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Optional

from eth_utils import keccak


def _event_signature(abi_entry: dict) -> str:
    inputs = abi_entry.get("inputs", [])
    return f"{abi_entry['name']}({','.join(i['type'] for i in inputs)})"


def _function_signature(abi_entry: dict) -> str:
    inputs = abi_entry.get("inputs", [])
    return f"{abi_entry['name']}({','.join(i['type'] for i in inputs)})"


def _topic0(event_abi: dict) -> str:
    return "0x" + keccak(text=_event_signature(event_abi)).hex()


def _selector(fn_abi: dict) -> str:
    return "0x" + keccak(text=_function_signature(fn_abi)).hex()[:8]


class AbiIndex:
    def __init__(self):
        self._events: dict[str, list[dict]] = {}
        self._functions: dict[str, list[dict]] = {}

    def add_abi(self, abi: list[dict]) -> None:
        for entry in abi:
            t = entry.get("type")
            if t == "event" and not entry.get("anonymous", False):
                self._events.setdefault(_topic0(entry), []).append(entry)
            elif t == "function":
                self._functions.setdefault(_selector(entry), []).append(entry)

    def lookup_event(self, topic0: str) -> Optional[dict]:
        lst = self._events.get(topic0.lower())
        return lst[0] if lst else None

    def lookup_function(self, selector: str) -> Optional[dict]:
        lst = self._functions.get(selector.lower())
        return lst[0] if lst else None

    @property
    def known_topic0s(self) -> list[str]:
        return list(self._events)

    @property
    def known_selectors(self) -> list[str]:
        return list(self._functions)


def _extract_abi_list(obj: Any) -> list[dict]:
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict) and isinstance(obj.get("abi"), list):
        return obj["abi"]
    return []


def load_abi_sources(
    abi_files: Optional[Iterable[Path]] = None,
    abi_dirs: Optional[Iterable[Path]] = None,
    foundry_project: Optional[Path] = None,
) -> AbiIndex:
    idx = AbiIndex()
    any_loaded = False

    for f in abi_files or []:
        with open(f) as fp:
            data = json.load(fp)
        abi = _extract_abi_list(data)
        if abi:
            idx.add_abi(abi)
            any_loaded = True

    for d in abi_dirs or []:
        for path in Path(d).rglob("*.json"):
            try:
                with open(path) as fp:
                    data = json.load(fp)
            except (json.JSONDecodeError, OSError):
                continue
            abi = _extract_abi_list(data)
            if abi:
                idx.add_abi(abi)
                any_loaded = True

    if foundry_project:
        out = Path(foundry_project) / "out"
        if out.is_dir():
            for path in out.rglob("*.json"):
                try:
                    with open(path) as fp:
                        data = json.load(fp)
                except (json.JSONDecodeError, OSError):
                    continue
                abi = _extract_abi_list(data)
                if abi:
                    idx.add_abi(abi)
                    any_loaded = True

    if not any_loaded:
        raise ValueError("no ABI sources provided or discovered")

    return idx

