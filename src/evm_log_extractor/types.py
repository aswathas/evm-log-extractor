"""Primitive type converters for canonical NDJSON output.

All conversions follow rules in raw-log-schema.md §0.2:
- addresses: EIP-55 checksummed
- hex: lowercase `0x`-prefixed
- wei: decimal string (negative permitted for deltas)
"""

from __future__ import annotations

from typing import Optional, Union

import re

from eth_utils import keccak

Numeric = Union[int, str]


def checksum_address(addr: Optional[str]) -> Optional[str]:
    if addr is None:
        return None
    if not isinstance(addr, str):
        raise ValueError(f"address must be a string, got {type(addr).__name__}")
    raw = addr[2:] if addr.startswith(("0x", "0X")) else addr
    raw = raw.lower()
    if not re.fullmatch(r"[0-9a-f]{40}", raw):
        raise ValueError(f"invalid address hex: {addr!r}")
    digest = keccak(text=raw).hex()
    out = []
    for i, c in enumerate(raw):
        if c in "abcdef" and int(digest[i], 16) >= 8:
            out.append(c.upper())
        else:
            out.append(c)
    return "0x" + "".join(out)


def hex_lower(h: Optional[str]) -> Optional[str]:
    if h is None:
        return None
    if not isinstance(h, str) or not h.startswith(("0x", "0X")):
        raise ValueError(f"not a 0x-prefixed hex string: {h!r}")
    return "0x" + h[2:].lower()


def wei_str(v: Optional[Numeric]) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, int):
        return str(v)
    if isinstance(v, str):
        if v.startswith(("0x", "0X")):
            return str(int(v, 16))
        return str(int(v))
    raise ValueError(f"unsupported wei source type: {type(v).__name__}")


def hex_to_int(v: Optional[Numeric]) -> Optional[int]:
    if v is None:
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        return int(v, 16) if v.startswith(("0x", "0X")) else int(v)
    raise ValueError(f"unsupported int source type: {type(v).__name__}")


def signed_wei_delta(after: str, before: str) -> str:
    return str(int(after) - int(before))
