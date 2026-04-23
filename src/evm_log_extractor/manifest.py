"""Per-run manifest.json builder. See raw-log-schema.md §Appendix B."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


class Manifest:
    def __init__(
        self,
        run_id: str,
        tool_version: str,
        rpc_url: str,
        chain_id: int,
        cli_args: dict[str, Any],
    ):
        self._data: dict[str, Any] = {
            "run_id": run_id,
            "tool_version": tool_version,
            "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "rpc": {
                "url": rpc_url,
                "chain_id": chain_id,
                "client": None,
                "fork_url": None,
                "fork_block_number": None,
            },
            "cli_args": cli_args,
            "counts": {},
            "hashes": {},
        }

    def set_node_info(self, info: Optional[dict]) -> None:
        if not info:
            return
        if "clientVersion" in info:
            self._data["rpc"]["client"] = info["clientVersion"]
        fork = info.get("forkConfig") or {}
        fork_url = fork.get("forkUrl")
        fork_bn = fork.get("forkBlockNumber")
        if fork_url:
            self._data["rpc"]["fork_url"] = fork_url
        if fork_bn is not None:
            if isinstance(fork_bn, str) and fork_bn.startswith("0x"):
                fork_bn = int(fork_bn, 16)
            self._data["rpc"]["fork_block_number"] = int(fork_bn)

    def set_counts(self, counts: dict[str, int]) -> None:
        self._data["counts"] = dict(counts)

    def set_hashes(self, hashes: dict[str, str]) -> None:
        self._data["hashes"] = dict(hashes)

    def write(self, path: Path | str) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
            f.write("\n")

    @staticmethod
    def build_run_id(
        label: Optional[str],
        from_block: int | str,
        to_block: int | str,
        now: Optional[str] = None,
    ) -> str:
        ts = now or datetime.now(timezone.utc).isoformat(timespec="seconds")
        ts_id = ts.replace(":", "-").replace("+00-00", "Z").rstrip("Z") + "Z"
        if label:
            safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in label)
            return f"{ts_id}__{safe}"
        return f"{ts_id}__blk-{from_block}-{to_block}"

