"""NDJSON reader/writer with sha256 integrity tracking."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterator


class NdjsonWriter:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.count = 0
        self._hasher = hashlib.sha256()
        self._fp = None

    def __enter__(self) -> "NdjsonWriter":
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fp = open(self.path, "w", encoding="utf-8", newline="\n")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._fp is not None:
            self._fp.close()

    def write(self, record: dict[str, Any]) -> None:
        if not isinstance(record, dict):
            raise TypeError(f"NDJSON records must be dicts, got {type(record).__name__}")
        line = json.dumps(record, separators=(", ", ": "), ensure_ascii=False) + "\n"
        assert self._fp is not None, "writer not opened; use as context manager"
        self._fp.write(line)
        self._hasher.update(line.encode("utf-8"))
        self.count += 1

    @property
    def sha256(self) -> str:
        return self._hasher.hexdigest()


def read_ndjson(path: Path | str) -> Iterator[dict[str, Any]]:
    p = Path(path)
    with open(p, "r", encoding="utf-8") as f:
        for idx, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{p}: line {idx}: invalid JSON: {exc}") from exc

