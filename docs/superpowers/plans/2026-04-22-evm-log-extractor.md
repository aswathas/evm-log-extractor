# EVM Log Extractor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `evm-log-extractor`, a forensics-grade CLI tool that extracts, normalises, and decodes EVM logs from Anvil/Foundry local nodes and any EVM JSON-RPC endpoint, producing deterministic NDJSON output suitable for smart-contract exploit investigation.

**Architecture:** Three independently-runnable Python CLIs (`extract`, `normalise`, `decode`) sharing a common `evm_log_extractor` package with explicit file-path contracts. Streaming NDJSON in/out at every stage. Zero global state, zero auto-discovery magic. ABI ingestion via Foundry-project globbing or single-bundle JSON. Per-run manifest with sha256 hashes for reproducibility.

**Tech Stack:** Python 3.11+, `web3.py` 6.x, `eth-abi` 4.x, `eth-utils` 2.x, `click` 8.x, `pytest` 7.x, `pytest-mock`, `requests-mock`. Package managed with `pyproject.toml` + `setuptools`. Target entities per `raw-log-schema.md` tier-1 list for v1 (blocks, transactions, receipts, event_logs, call_traces). Tier-2 (state_diffs, storage_diffs) deferred.

**Reference documents:**
- `raw-log-schema.md` — canonical field spec (source of truth for all entity shapes)
- `evm-forensics-meta-prompt.md` — original scope doc
- `DESIGN.md` — Apple design system for docs page

---

## File Structure

```
evm-log-extractor/
├── pyproject.toml
├── requirements.txt
├── .gitignore
├── README.md
├── DESIGN.md                         # (existing, kept)
├── raw-log-schema.md                 # (existing, kept as canonical schema)
├── evm-forensics-meta-prompt.md      # (existing, kept as scope doc)
├── docs/
│   ├── index.html                    # Apple-styled docs page
│   ├── styles.css                    # SF Pro, #000/#f5f5f7/#0071e3 palette
│   └── decode-flow.svg               # decoder pipeline diagram (inline SVG in index.html is fine — keep file optional)
├── src/
│   └── evm_log_extractor/
│       ├── __init__.py
│       ├── types.py                  # checksum, hex lowercase, wei str converters
│       ├── ndjson.py                 # read/write NDJSON streams
│       ├── rpc.py                    # web3.py wrapper + batch helpers
│       ├── manifest.py               # run manifest.json builder
│       ├── extractors/
│       │   ├── __init__.py
│       │   ├── blocks.py
│       │   ├── transactions.py
│       │   ├── receipts.py
│       │   ├── event_logs.py
│       │   └── call_traces.py
│       ├── normaliser.py             # single-file normaliser — small enough
│       ├── abi_loader.py             # Foundry/Hardhat/raw → topic0/selector index
│       ├── decoder.py                # event log decode via eth_abi
│       └── cli/
│           ├── __init__.py
│           ├── extract.py            # `evm-extract` entry
│           ├── normalise.py          # `evm-normalise` entry
│           └── decode.py             # `evm-decode` entry
└── tests/
    ├── __init__.py
    ├── conftest.py                   # fixtures: sample RPC responses
    ├── fixtures/
    │   ├── block_18500123.json
    │   ├── receipt_0xdea.json
    │   ├── logs_range.json
    │   ├── call_trace_nested.json
    │   └── erc20_abi.json
    ├── test_types.py
    ├── test_ndjson.py
    ├── test_rpc.py
    ├── test_manifest.py
    ├── test_extractor_blocks.py
    ├── test_extractor_transactions.py
    ├── test_extractor_receipts.py
    ├── test_extractor_event_logs.py
    ├── test_extractor_call_traces.py
    ├── test_normaliser.py
    ├── test_abi_loader.py
    ├── test_decoder.py
    └── test_cli_smoke.py
```

**Responsibility boundaries:**
- `types.py` owns all primitive conversions — anywhere else a wei or addr is produced, it goes through this module.
- `ndjson.py` owns file I/O for NDJSON — no other module opens a `.ndjson` file.
- `rpc.py` owns JSON-RPC — no other module imports `web3` directly.
- Each extractor in `extractors/` owns exactly one entity type. Pure function: `(rpc, params) -> Iterator[dict]`.
- `normaliser.py` owns transformation + validation across all entities.
- `abi_loader.py` and `decoder.py` are the only ABI-aware modules.
- `cli/*` are thin wrappers — argument parsing and wiring only, no business logic.

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `src/evm_log_extractor/__init__.py`
- Create: `src/evm_log_extractor/extractors/__init__.py`
- Create: `src/evm_log_extractor/cli/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "evm-log-extractor"
version = "0.1.0"
description = "Forensics-grade EVM log extractor, normaliser, and decoder for Anvil/Foundry and any EVM JSON-RPC endpoint."
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "EVM Log Extractor Contributors" }]
dependencies = [
    "web3>=6.11,<7",
    "eth-abi>=4.2,<5",
    "eth-utils>=2.3,<3",
    "click>=8.1,<9",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4,<8",
    "pytest-mock>=3.12,<4",
    "requests-mock>=1.11,<2",
]

[project.scripts]
evm-extract = "evm_log_extractor.cli.extract:main"
evm-normalise = "evm_log_extractor.cli.normalise:main"
evm-decode = "evm_log_extractor.cli.decode:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] **Step 2: Write `requirements.txt`**

```
web3>=6.11,<7
eth-abi>=4.2,<5
eth-utils>=2.3,<3
click>=8.1,<9
pytest>=7.4,<8
pytest-mock>=3.12,<4
requests-mock>=1.11,<2
```

- [ ] **Step 3: Write `.gitignore`**

```
__pycache__/
*.pyc
*.pyo
*.egg-info/
build/
dist/
.pytest_cache/
.venv/
venv/
.env
.coverage
htmlcov/
output/
*.ndjson
*.ndjson.gz
!tests/fixtures/*.json
.DS_Store
```

- [ ] **Step 4: Write empty package init files**

Create `src/evm_log_extractor/__init__.py`:
```python
"""Forensics-grade EVM log extractor, normaliser, and decoder."""

__version__ = "0.1.0"
```

Create `src/evm_log_extractor/extractors/__init__.py` — empty file.

Create `src/evm_log_extractor/cli/__init__.py` — empty file.

Create `tests/__init__.py` — empty file.

- [ ] **Step 5: Write `tests/conftest.py`**

```python
import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES_DIR


@pytest.fixture
def load_fixture():
    def _load(name: str):
        with open(FIXTURES_DIR / name) as f:
            return json.load(f)
    return _load


@pytest.fixture
def tmp_run_dir(tmp_path):
    run_dir = tmp_path / "run"
    (run_dir / "raw").mkdir(parents=True)
    (run_dir / "norm").mkdir()
    (run_dir / "decoded").mkdir()
    return run_dir
```

- [ ] **Step 6: Create virtualenv and install**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Expected: `Successfully installed evm-log-extractor-0.1.0 web3-6.x ...`

- [ ] **Step 7: Verify imports work**

```bash
python -c "import evm_log_extractor; print(evm_log_extractor.__version__)"
```

Expected: `0.1.0`

- [ ] **Step 8: Commit**

```bash
git init
git add pyproject.toml requirements.txt .gitignore src/ tests/
git commit -m "chore: project scaffold with package layout and test harness"
```

---

## Task 2: Type converters (`types.py`)

**Files:**
- Create: `src/evm_log_extractor/types.py`
- Create: `tests/test_types.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_types.py`:

```python
import pytest

from evm_log_extractor.types import (
    checksum_address,
    hex_lower,
    wei_str,
    hex_to_int,
    signed_wei_delta,
)


class TestChecksumAddress:
    def test_lowercase_input_returns_eip55(self):
        assert checksum_address("0xc0ffee254729296a45a3885639ac7e10f9d54979") == "0xC0FfEE254729296a45a3885639AC7E10F9d54979"

    def test_uppercase_input_returns_eip55(self):
        assert checksum_address("0XC0FFEE254729296A45A3885639AC7E10F9D54979") == "0xC0FfEE254729296a45a3885639AC7E10F9d54979"

    def test_none_returns_none(self):
        assert checksum_address(None) is None

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            checksum_address("0xnothex")


class TestHexLower:
    def test_uppercase_returns_lowercase(self):
        assert hex_lower("0xABCDEF") == "0xabcdef"

    def test_already_lower_unchanged(self):
        assert hex_lower("0xabcdef") == "0xabcdef"

    def test_none_returns_none(self):
        assert hex_lower(None) is None

    def test_missing_prefix_raises(self):
        with pytest.raises(ValueError):
            hex_lower("abcdef")


class TestWeiStr:
    def test_int_returns_decimal_string(self):
        assert wei_str(1_000_000_000_000_000_000) == "1000000000000000000"

    def test_hex_string_returns_decimal_string(self):
        assert wei_str("0xde0b6b3a7640000") == "1000000000000000000"

    def test_decimal_string_unchanged(self):
        assert wei_str("42") == "42"

    def test_none_returns_none(self):
        assert wei_str(None) is None

    def test_negative_int_returns_negative_decimal(self):
        assert wei_str(-1) == "-1"


class TestHexToInt:
    def test_hex_prefix(self):
        assert hex_to_int("0x10") == 16

    def test_already_int(self):
        assert hex_to_int(42) == 42

    def test_none_returns_none(self):
        assert hex_to_int(None) is None


class TestSignedWeiDelta:
    def test_positive_delta(self):
        assert signed_wei_delta("1000", "500") == "500"

    def test_negative_delta(self):
        assert signed_wei_delta("500", "1000") == "-500"

    def test_zero_delta(self):
        assert signed_wei_delta("100", "100") == "0"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_types.py -v`
Expected: all 14 tests FAIL with `ModuleNotFoundError: No module named 'evm_log_extractor.types'`.

- [ ] **Step 3: Implement `types.py`**

Create `src/evm_log_extractor/types.py`:

```python
"""Primitive type converters for canonical NDJSON output.

All conversions follow rules in raw-log-schema.md §0.2:
- addresses: EIP-55 checksummed
- hex: lowercase `0x`-prefixed
- wei: decimal string (negative permitted for deltas)
"""

from __future__ import annotations

from typing import Optional, Union

from eth_utils import to_checksum_address as _to_checksum, is_hex

Numeric = Union[int, str]


def checksum_address(addr: Optional[str]) -> Optional[str]:
    if addr is None:
        return None
    return _to_checksum(addr)


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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_types.py -v`
Expected: all 14 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/evm_log_extractor/types.py tests/test_types.py
git commit -m "feat(types): EIP-55 checksum, lowercase hex, wei-as-string converters"
```

---

## Task 3: NDJSON stream I/O (`ndjson.py`)

**Files:**
- Create: `src/evm_log_extractor/ndjson.py`
- Create: `tests/test_ndjson.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_ndjson.py`:

```python
from pathlib import Path

import pytest

from evm_log_extractor.ndjson import NdjsonWriter, read_ndjson


def test_writer_writes_one_object_per_line(tmp_path: Path):
    out = tmp_path / "o.ndjson"
    with NdjsonWriter(out) as w:
        w.write({"a": 1})
        w.write({"b": 2})
    assert out.read_text() == '{"a": 1}\n{"b": 2}\n'


def test_writer_rejects_non_dict(tmp_path: Path):
    with NdjsonWriter(tmp_path / "o.ndjson") as w:
        with pytest.raises(TypeError):
            w.write([1, 2, 3])


def test_writer_tracks_count_and_sha256(tmp_path: Path):
    out = tmp_path / "o.ndjson"
    with NdjsonWriter(out) as w:
        w.write({"a": 1})
        w.write({"b": 2})
    assert w.count == 2
    # hash of the literal bytes written
    import hashlib
    expected = hashlib.sha256(b'{"a": 1}\n{"b": 2}\n').hexdigest()
    assert w.sha256 == expected


def test_read_ndjson_streams_records(tmp_path: Path):
    p = tmp_path / "i.ndjson"
    p.write_text('{"a": 1}\n{"b": 2}\n{"c": 3}\n')
    records = list(read_ndjson(p))
    assert records == [{"a": 1}, {"b": 2}, {"c": 3}]


def test_read_ndjson_skips_blank_lines(tmp_path: Path):
    p = tmp_path / "i.ndjson"
    p.write_text('{"a": 1}\n\n{"b": 2}\n')
    assert list(read_ndjson(p)) == [{"a": 1}, {"b": 2}]


def test_read_ndjson_raises_on_malformed(tmp_path: Path):
    p = tmp_path / "i.ndjson"
    p.write_text('{"a": 1}\nnot json\n')
    with pytest.raises(ValueError, match="line 2"):
        list(read_ndjson(p))


def test_writer_creates_parent_dirs(tmp_path: Path):
    out = tmp_path / "nested" / "deep" / "o.ndjson"
    with NdjsonWriter(out) as w:
        w.write({"a": 1})
    assert out.exists()
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_ndjson.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `ndjson.py`**

Create `src/evm_log_extractor/ndjson.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_ndjson.py -v`
Expected: all 7 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/evm_log_extractor/ndjson.py tests/test_ndjson.py
git commit -m "feat(ndjson): streaming writer with sha256 + line-error-aware reader"
```

---

## Task 4: RPC client (`rpc.py`)

**Files:**
- Create: `src/evm_log_extractor/rpc.py`
- Create: `tests/test_rpc.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_rpc.py`:

```python
from unittest.mock import MagicMock

import pytest

from evm_log_extractor.rpc import RpcClient


@pytest.fixture
def mock_w3():
    w3 = MagicMock()
    w3.eth.chain_id = 31337
    w3.eth.block_number = 250
    return w3


def test_client_chain_id(mock_w3):
    rpc = RpcClient.from_web3(mock_w3)
    assert rpc.chain_id() == 31337


def test_client_latest_block(mock_w3):
    rpc = RpcClient.from_web3(mock_w3)
    assert rpc.latest_block() == 250


def test_get_block_returns_dict(mock_w3):
    mock_w3.eth.get_block.return_value = {"number": 100, "hash": b"\x01" * 32}
    rpc = RpcClient.from_web3(mock_w3)
    b = rpc.get_block(100, full_tx=False)
    assert b["number"] == 100


def test_get_block_by_tag(mock_w3):
    mock_w3.eth.get_block.return_value = {"number": 250}
    rpc = RpcClient.from_web3(mock_w3)
    rpc.get_block("latest", full_tx=True)
    mock_w3.eth.get_block.assert_called_once_with("latest", full_transactions=True)


def test_get_receipt(mock_w3):
    mock_w3.eth.get_transaction_receipt.return_value = {"status": 1}
    rpc = RpcClient.from_web3(mock_w3)
    assert rpc.get_receipt("0xdea")["status"] == 1


def test_get_logs(mock_w3):
    mock_w3.eth.get_logs.return_value = [{"logIndex": 0}]
    rpc = RpcClient.from_web3(mock_w3)
    assert rpc.get_logs(from_block=0, to_block=100) == [{"logIndex": 0}]


def test_debug_trace_call_tracer(mock_w3):
    mock_w3.provider.make_request.return_value = {"result": {"type": "CALL"}}
    rpc = RpcClient.from_web3(mock_w3)
    result = rpc.debug_trace_transaction("0xdea", tracer="callTracer")
    mock_w3.provider.make_request.assert_called_once_with(
        "debug_traceTransaction", ["0xdea", {"tracer": "callTracer"}]
    )
    assert result == {"type": "CALL"}


def test_debug_trace_prestate_diff(mock_w3):
    mock_w3.provider.make_request.return_value = {"result": {}}
    rpc = RpcClient.from_web3(mock_w3)
    rpc.debug_trace_transaction(
        "0xdea",
        tracer="prestateTracer",
        tracer_config={"diffMode": True},
    )
    mock_w3.provider.make_request.assert_called_once_with(
        "debug_traceTransaction",
        ["0xdea", {"tracer": "prestateTracer", "tracerConfig": {"diffMode": True}}],
    )


def test_anvil_node_info_success(mock_w3):
    mock_w3.provider.make_request.return_value = {"result": {"currentBlockNumber": "0xfa"}}
    rpc = RpcClient.from_web3(mock_w3)
    info = rpc.anvil_node_info()
    assert info == {"currentBlockNumber": "0xfa"}


def test_anvil_node_info_unavailable(mock_w3):
    mock_w3.provider.make_request.return_value = {"error": {"code": -32601, "message": "not found"}}
    rpc = RpcClient.from_web3(mock_w3)
    assert rpc.anvil_node_info() is None
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_rpc.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `rpc.py`**

Create `src/evm_log_extractor/rpc.py`:

```python
"""Thin web3.py wrapper exposing only the RPC methods the extractor needs.

Every method returns raw dict/list payloads. Conversion happens in the
extractor layer, not here.
"""

from __future__ import annotations

from typing import Any, Optional, Union

from web3 import HTTPProvider, Web3

BlockTag = Union[int, str]


class RpcClient:
    def __init__(self, w3: Web3):
        self._w3 = w3

    @classmethod
    def from_url(cls, url: str, timeout: int = 30) -> "RpcClient":
        provider = HTTPProvider(url, request_kwargs={"timeout": timeout})
        return cls(Web3(provider))

    @classmethod
    def from_web3(cls, w3: Web3) -> "RpcClient":
        return cls(w3)

    def chain_id(self) -> int:
        return self._w3.eth.chain_id

    def latest_block(self) -> int:
        return self._w3.eth.block_number

    def get_block(self, block: BlockTag, full_tx: bool = False) -> dict:
        return self._w3.eth.get_block(block, full_transactions=full_tx)

    def get_receipt(self, tx_hash: str) -> dict:
        return self._w3.eth.get_transaction_receipt(tx_hash)

    def get_logs(
        self,
        from_block: BlockTag,
        to_block: BlockTag,
        address: Optional[str] = None,
        topics: Optional[list] = None,
    ) -> list[dict]:
        f: dict[str, Any] = {"fromBlock": from_block, "toBlock": to_block}
        if address is not None:
            f["address"] = address
        if topics is not None:
            f["topics"] = topics
        return self._w3.eth.get_logs(f)

    def debug_trace_transaction(
        self,
        tx_hash: str,
        tracer: str,
        tracer_config: Optional[dict] = None,
    ) -> Any:
        params: dict[str, Any] = {"tracer": tracer}
        if tracer_config is not None:
            params["tracerConfig"] = tracer_config
        resp = self._w3.provider.make_request(
            "debug_traceTransaction", [tx_hash, params]
        )
        if "error" in resp:
            raise RuntimeError(f"debug_traceTransaction failed: {resp['error']}")
        return resp["result"]

    def anvil_node_info(self) -> Optional[dict]:
        resp = self._w3.provider.make_request("anvil_nodeInfo", [])
        if "error" in resp:
            return None
        return resp.get("result")
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_rpc.py -v`
Expected: all 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/evm_log_extractor/rpc.py tests/test_rpc.py
git commit -m "feat(rpc): web3.py wrapper with debug_trace + anvil_nodeInfo support"
```

---

## Task 5: Manifest builder (`manifest.py`)

**Files:**
- Create: `src/evm_log_extractor/manifest.py`
- Create: `tests/test_manifest.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_manifest.py`:

```python
import json
from pathlib import Path

from evm_log_extractor.manifest import Manifest


def test_manifest_build_minimal(tmp_path: Path):
    m = Manifest(
        run_id="2026-04-22T14-33-07Z__test",
        tool_version="0.1.0",
        rpc_url="http://127.0.0.1:8545",
        chain_id=31337,
        cli_args={"from_block": 0, "to_block": 100, "entities": ["blocks"]},
    )
    m.set_node_info({"clientVersion": "anvil/0.2.0"})
    m.set_counts({"blocks": 101})
    m.set_hashes({"raw/blocks.ndjson": "sha256:abc"})

    out = tmp_path / "manifest.json"
    m.write(out)

    data = json.loads(out.read_text())
    assert data["run_id"] == "2026-04-22T14-33-07Z__test"
    assert data["rpc"]["chain_id"] == 31337
    assert data["rpc"]["fork_url"] is None
    assert data["cli_args"]["entities"] == ["blocks"]
    assert data["counts"]["blocks"] == 101
    assert data["hashes"]["raw/blocks.ndjson"] == "sha256:abc"


def test_manifest_fork_detection(tmp_path: Path):
    m = Manifest(
        run_id="r",
        tool_version="0.1.0",
        rpc_url="http://127.0.0.1:8545",
        chain_id=1,
        cli_args={},
    )
    m.set_node_info({
        "forkConfig": {"forkUrl": "https://eth.example", "forkBlockNumber": "0x1117b10"},
        "clientVersion": "anvil",
    })
    out = tmp_path / "manifest.json"
    m.write(out)
    data = json.loads(out.read_text())
    assert data["rpc"]["fork_url"] == "https://eth.example"
    assert data["rpc"]["fork_block_number"] == 17_923_856


def test_build_run_id_with_label():
    rid = Manifest.build_run_id(
        label="curve-reentrancy",
        from_block=100,
        to_block=200,
        now="2026-04-22T14:33:07Z",
    )
    assert rid == "2026-04-22T14-33-07Z__curve-reentrancy"


def test_build_run_id_fallback_to_block_range():
    rid = Manifest.build_run_id(
        label=None,
        from_block=100,
        to_block=200,
        now="2026-04-22T14:33:07Z",
    )
    assert rid == "2026-04-22T14-33-07Z__blk-100-200"
```

- [ ] **Step 2: Run tests to verify failure**

Run: `pytest tests/test_manifest.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `manifest.py`**

Create `src/evm_log_extractor/manifest.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify pass**

Run: `pytest tests/test_manifest.py -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/evm_log_extractor/manifest.py tests/test_manifest.py
git commit -m "feat(manifest): per-run manifest.json builder with fork detection"
```

---

## Task 6: Blocks extractor (`extractors/blocks.py`)

**Files:**
- Create: `src/evm_log_extractor/extractors/blocks.py`
- Create: `tests/fixtures/block_18500123.json`
- Create: `tests/test_extractor_blocks.py`

- [ ] **Step 1: Write fixture**

Create `tests/fixtures/block_18500123.json`:

```json
{
  "number": "0x11a0adb",
  "hash": "0xabcdef0000000000000000000000000000000000000000000000000000000001",
  "parentHash": "0x0000000000000000000000000000000000000000000000000000000000000002",
  "timestamp": "0x656533d0",
  "miner": "0xc0ffee254729296a45a3885639ac7e10f9d54979",
  "gasLimit": "0x1c9c380",
  "gasUsed": "0x18b6a5",
  "baseFeePerGas": "0x37e11d600",
  "size": "0x12ac0",
  "stateRoot": "0x7af0000000000000000000000000000000000000000000000000000000000000",
  "transactionsRoot": "0x9c10000000000000000000000000000000000000000000000000000000000000",
  "receiptsRoot": "0x2e00000000000000000000000000000000000000000000000000000000000000",
  "sha3Uncles": "0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347",
  "logsBloom": "0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000",
  "extraData": "0x",
  "nonce": "0x0000000000000000",
  "mixHash": "0x0000000000000000000000000000000000000000000000000000000000000000",
  "difficulty": "0x0",
  "totalDifficulty": "0x0",
  "withdrawalsRoot": null,
  "transactions": ["0xdea00000000000000000000000000000000000000000000000000000000000ff"]
}
```

- [ ] **Step 2: Write failing test**

Create `tests/test_extractor_blocks.py`:

```python
from unittest.mock import MagicMock

from evm_log_extractor.extractors.blocks import extract_block


def test_extract_block_shapes_record(load_fixture):
    raw = load_fixture("block_18500123.json")
    rpc = MagicMock()
    rpc.get_block.return_value = raw

    record = extract_block(rpc, 18_500_123)

    assert record["block_number"] == 18_500_123
    assert record["block_hash"] == "0xabcdef0000000000000000000000000000000000000000000000000000000001"
    assert record["timestamp"] == 1_701_123_024
    assert record["miner"] == "0xC0FfEE254729296a45a3885639AC7E10F9d54979"
    assert record["gas_limit"] == 30_000_000
    assert record["gas_used"] == 1_620_133
    assert record["base_fee_per_gas"] == "15000000000"
    assert record["transaction_count"] == 1
    assert record["withdrawals_root"] is None


def test_extract_block_handles_pre_london(load_fixture):
    raw = load_fixture("block_18500123.json")
    raw["baseFeePerGas"] = None
    rpc = MagicMock()
    rpc.get_block.return_value = raw
    record = extract_block(rpc, 18_500_123)
    assert record["base_fee_per_gas"] is None
```

- [ ] **Step 3: Run test to verify failure**

Run: `pytest tests/test_extractor_blocks.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement `extractors/blocks.py`**

Create `src/evm_log_extractor/extractors/blocks.py`:

```python
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
```

- [ ] **Step 5: Run test to verify pass**

Run: `pytest tests/test_extractor_blocks.py -v`
Expected: 2 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/evm_log_extractor/extractors/blocks.py tests/fixtures/block_18500123.json tests/test_extractor_blocks.py
git commit -m "feat(extractor): blocks entity shaping per schema §1"
```

---

## Task 7: Transactions extractor (`extractors/transactions.py`)

**Files:**
- Create: `src/evm_log_extractor/extractors/transactions.py`
- Create: `tests/test_extractor_transactions.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_extractor_transactions.py`:

```python
from unittest.mock import MagicMock

from evm_log_extractor.extractors.transactions import extract_transactions


def test_extract_transactions_type2_eip1559():
    block_full = {
        "number": "0x11a0adb",
        "hash": "0xabc",
        "transactions": [
            {
                "hash": "0xdea00000000000000000000000000000000000000000000000000000000000ff",
                "blockNumber": "0x11a0adb",
                "blockHash": "0xabc",
                "transactionIndex": "0x7",
                "type": "0x2",
                "chainId": "0x7a69",
                "from": "0xabcd00000000000000000000000000000000dead",
                "to": "0x1234000000000000000000000000000000005678",
                "value": "0xde0b6b3a7640000",
                "input": "0xa9059cbb000000000000000000000000c0ffee254729296a45a3885639ac7e10f9d549790000000000000000000000000000000000000000000000000000000000000064",
                "nonce": "0x2a",
                "gas": "0x1d4c0",
                "gasPrice": None,
                "maxFeePerGas": "0x9502f9000",
                "maxPriorityFeePerGas": "0x77359400",
                "accessList": [],
                "r": "0x0100000000000000000000000000000000000000000000000000000000000001",
                "s": "0x0200000000000000000000000000000000000000000000000000000000000002",
                "yParity": "0x1",
                "v": None,
            }
        ],
    }
    rpc = MagicMock()
    rpc.get_block.return_value = block_full

    records = list(extract_transactions(rpc, 18_500_123))
    assert len(records) == 1
    tx = records[0]
    assert tx["tx_hash"] == "0xdea00000000000000000000000000000000000000000000000000000000000ff"
    assert tx["tx_type"] == 2
    assert tx["chain_id"] == 31337
    assert tx["from_address"] == "0xabCd00000000000000000000000000000000dEaD"
    assert tx["value"] == "1000000000000000000"
    assert tx["function_selector"] == "0xa9059cbb"
    assert tx["gas_price"] is None
    assert tx["max_fee_per_gas"] == "40000000000"
    assert tx["y_parity"] == 1
    assert tx["v"] is None


def test_extract_transactions_contract_creation_null_to():
    block_full = {
        "number": "0x1",
        "hash": "0xabc",
        "transactions": [{
            "hash": "0xdeadc0de" + "00" * 28,
            "blockNumber": "0x1",
            "blockHash": "0xabc",
            "transactionIndex": "0x0",
            "type": "0x2",
            "chainId": "0x7a69",
            "from": "0xabcd00000000000000000000000000000000dead",
            "to": None,
            "value": "0x0",
            "input": "0x60806040",
            "nonce": "0x0",
            "gas": "0x100000",
            "gasPrice": None,
            "maxFeePerGas": "0x1",
            "maxPriorityFeePerGas": "0x1",
            "accessList": [],
            "r": "0x01" + "00" * 31,
            "s": "0x02" + "00" * 31,
            "yParity": "0x0",
            "v": None,
        }],
    }
    rpc = MagicMock()
    rpc.get_block.return_value = block_full
    tx = next(extract_transactions(rpc, 1))
    assert tx["to_address"] is None
    assert tx["function_selector"] == "0x60806040"


def test_extract_transactions_empty_input_selector_null():
    block_full = {
        "number": "0x1",
        "hash": "0xabc",
        "transactions": [{
            "hash": "0xdeadbeef" + "00" * 28,
            "blockNumber": "0x1",
            "blockHash": "0xabc",
            "transactionIndex": "0x0",
            "type": "0x0",
            "chainId": "0x7a69",
            "from": "0xabcd00000000000000000000000000000000dead",
            "to": "0x1234000000000000000000000000000000005678",
            "value": "0x0",
            "input": "0x",
            "nonce": "0x0",
            "gas": "0x5208",
            "gasPrice": "0x1",
            "maxFeePerGas": None,
            "maxPriorityFeePerGas": None,
            "accessList": None,
            "v": "0x1b",
            "r": "0x01" + "00" * 31,
            "s": "0x02" + "00" * 31,
            "yParity": None,
        }],
    }
    rpc = MagicMock()
    rpc.get_block.return_value = block_full
    tx = next(extract_transactions(rpc, 1))
    assert tx["function_selector"] is None
    assert tx["gas_price"] == "1"
    assert tx["max_fee_per_gas"] is None
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_extractor_transactions.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `extractors/transactions.py`**

Create `src/evm_log_extractor/extractors/transactions.py`:

```python
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
            "max_priority_fee_per_gas": wei_str(tx.get("maxPriorityFeePerGas")) if tx.get("maxPriorityFeePerGas") is not None else None,
            "access_list": tx.get("accessList"),
            "v": str(hex_to_int(tx["v"])) if tx.get("v") is not None else None,
            "r": hex_lower(_as_hex(tx["r"])),
            "s": hex_lower(_as_hex(tx["s"])),
            "y_parity": hex_to_int(tx.get("yParity")) if tx.get("yParity") is not None else None,
        }
```

- [ ] **Step 4: Run test to verify pass**

Run: `pytest tests/test_extractor_transactions.py -v`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/evm_log_extractor/extractors/transactions.py tests/test_extractor_transactions.py
git commit -m "feat(extractor): transactions entity with EIP-1559 + legacy + creation handling"
```

---

## Task 8: Receipts extractor (`extractors/receipts.py`)

**Files:**
- Create: `src/evm_log_extractor/extractors/receipts.py`
- Create: `tests/test_extractor_receipts.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_extractor_receipts.py`:

```python
from unittest.mock import MagicMock

from evm_log_extractor.extractors.receipts import extract_receipt


def test_extract_receipt_success():
    rpc = MagicMock()
    rpc.get_receipt.return_value = {
        "blockNumber": "0x11a0adb",
        "blockHash": "0xabc",
        "transactionHash": "0xdea" + "00" * 29 + "ff",
        "transactionIndex": "0x7",
        "type": "0x2",
        "from": "0xabcd00000000000000000000000000000000dead",
        "to": "0x1234000000000000000000000000000000005678",
        "status": "0x1",
        "gasUsed": "0x16c74",
        "cumulativeGasUsed": "0xb2f2d",
        "effectiveGasPrice": "0x77b80c900",
        "contractAddress": None,
        "logsBloom": "0x" + "00" * 256,
        "logs": [{"logIndex": "0x0"}, {"logIndex": "0x1"}, {"logIndex": "0x2"}, {"logIndex": "0x3"}],
    }
    r = extract_receipt(rpc, "0xdea" + "00" * 29 + "ff")
    assert r["status"] == 1
    assert r["gas_used"] == 93_300
    assert r["cumulative_gas_used"] == 733_485
    assert r["effective_gas_price"] == "32100000000"
    assert r["contract_address"] is None
    assert r["logs_count"] == 4


def test_extract_receipt_contract_creation_populates_address():
    rpc = MagicMock()
    rpc.get_receipt.return_value = {
        "blockNumber": "0x1",
        "blockHash": "0xabc",
        "transactionHash": "0xdeadc0de" + "00" * 28,
        "transactionIndex": "0x0",
        "type": "0x2",
        "from": "0xabcd00000000000000000000000000000000dead",
        "to": None,
        "status": "0x1",
        "gasUsed": "0x100000",
        "cumulativeGasUsed": "0x100000",
        "effectiveGasPrice": "0x1",
        "contractAddress": "0xbeef020000000000000000000000000000000002",
        "logsBloom": "0x" + "00" * 256,
        "logs": [],
    }
    r = extract_receipt(rpc, "0xdeadc0de" + "00" * 28)
    assert r["contract_address"] == "0xBEef020000000000000000000000000000000002"
    assert r["logs_count"] == 0
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_extractor_receipts.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `extractors/receipts.py`**

Create `src/evm_log_extractor/extractors/receipts.py`:

```python
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
```

- [ ] **Step 4: Run test to verify pass**

Run: `pytest tests/test_extractor_receipts.py -v`
Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/evm_log_extractor/extractors/receipts.py tests/test_extractor_receipts.py
git commit -m "feat(extractor): receipts entity with logs_count derivation"
```

---

## Task 9: Event logs extractor (`extractors/event_logs.py`)

**Files:**
- Create: `src/evm_log_extractor/extractors/event_logs.py`
- Create: `tests/test_extractor_event_logs.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_extractor_event_logs.py`:

```python
from unittest.mock import MagicMock

from evm_log_extractor.extractors.event_logs import extract_event_logs


def test_extract_event_logs_transfer():
    rpc = MagicMock()
    rpc.get_logs.return_value = [{
        "blockNumber": "0x11a0adb",
        "blockHash": "0xabc",
        "transactionHash": "0xdea" + "00" * 29 + "ff",
        "transactionIndex": "0x7",
        "logIndex": "0x17",
        "address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        "topics": [
            "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
            "0x000000000000000000000000abcd00000000000000000000000000000000dead",
            "0x000000000000000000000000beef020000000000000000000000000000000002",
        ],
        "data": "0x00000000000000000000000000000000000000000000000000000000000003e8",
        "removed": False,
    }]
    records = list(extract_event_logs(rpc, from_block=0, to_block=18_500_123))
    assert len(records) == 1
    r = records[0]
    assert r["log_index"] == 23
    assert r["address"] == "0xA0b86991c6218b36c1D19D4a2e9Eb0cE3606eB48"
    assert r["topic0"] == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    assert r["topic1"] == "0x000000000000000000000000abcd00000000000000000000000000000000dead"
    assert r["topic2"] == "0x000000000000000000000000beef020000000000000000000000000000000002"
    assert r["topic3"] is None
    assert r["topics_count"] == 3
    assert r["data"] == "0x00000000000000000000000000000000000000000000000000000000000003e8"
    assert r["removed"] is False


def test_extract_event_logs_anonymous_no_topic0():
    rpc = MagicMock()
    rpc.get_logs.return_value = [{
        "blockNumber": "0x1",
        "blockHash": "0xabc",
        "transactionHash": "0xdead" + "00" * 28,
        "transactionIndex": "0x0",
        "logIndex": "0x0",
        "address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        "topics": [],
        "data": "0x1234",
        "removed": False,
    }]
    r = next(extract_event_logs(rpc, 0, 1))
    assert r["topic0"] is None
    assert r["topics_count"] == 0


def test_extract_event_logs_passes_address_filter():
    rpc = MagicMock()
    rpc.get_logs.return_value = []
    list(extract_event_logs(rpc, 0, 100, address="0xABCD00000000000000000000000000000000DEAD"))
    rpc.get_logs.assert_called_once_with(
        from_block=0, to_block=100,
        address="0xABCD00000000000000000000000000000000DEAD",
        topics=None,
    )
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_extractor_event_logs.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `extractors/event_logs.py`**

Create `src/evm_log_extractor/extractors/event_logs.py`:

```python
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
```

- [ ] **Step 4: Run test to verify pass**

Run: `pytest tests/test_extractor_event_logs.py -v`
Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/evm_log_extractor/extractors/event_logs.py tests/test_extractor_event_logs.py
git commit -m "feat(extractor): event_logs entity with anonymous-event and filter support"
```

---

## Task 10: Call traces extractor with tree flatten (`extractors/call_traces.py`)

**Files:**
- Create: `src/evm_log_extractor/extractors/call_traces.py`
- Create: `tests/fixtures/call_trace_nested.json`
- Create: `tests/test_extractor_call_traces.py`

- [ ] **Step 1: Write fixture**

Create `tests/fixtures/call_trace_nested.json`:

```json
{
  "type": "CALL",
  "from": "0xabcd00000000000000000000000000000000dead",
  "to": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
  "value": "0x0",
  "gas": "0x1d4c0",
  "gasUsed": "0x7aa8",
  "input": "0xa9059cbb000000000000000000000000beef020000000000000000000000000000000002000000000000000000000000000000000000000000000000000000000000000064",
  "output": "0x0000000000000000000000000000000000000000000000000000000000000001",
  "calls": [
    {
      "type": "STATICCALL",
      "from": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
      "to": "0x1234000000000000000000000000000000005678",
      "gas": "0x1000",
      "gasUsed": "0x500",
      "input": "0x70a08231000000000000000000000000abcd00000000000000000000000000000000dead",
      "output": "0x00000000000000000000000000000000000000000000000000000000000003e8"
    },
    {
      "type": "DELEGATECALL",
      "from": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
      "to": "0x1234000000000000000000000000000000005678",
      "gas": "0x2000",
      "gasUsed": "0x1200",
      "input": "0x23b872dd",
      "output": "0x",
      "error": "execution reverted",
      "revertReason": "0x08c379a0"
    }
  ]
}
```

- [ ] **Step 2: Write failing test**

Create `tests/test_extractor_call_traces.py`:

```python
from unittest.mock import MagicMock

from evm_log_extractor.extractors.call_traces import extract_call_traces, flatten_tree


def test_flatten_tree_produces_correct_trace_addresses(load_fixture):
    tree = load_fixture("call_trace_nested.json")
    flat = list(flatten_tree(tree))
    addrs = [f["trace_address"] for f in flat]
    assert addrs == ["root", "0", "1"]

    depths = [f["depth"] for f in flat]
    assert depths == [0, 1, 1]


def test_flatten_tree_deeper(load_fixture):
    tree = load_fixture("call_trace_nested.json")
    # add a grandchild to the 2nd child
    tree["calls"][1]["calls"] = [{
        "type": "CALL",
        "from": "0x1234000000000000000000000000000000005678",
        "to": "0xbeef020000000000000000000000000000000002",
        "gas": "0x500",
        "gasUsed": "0x200",
        "input": "0x",
        "output": "0x"
    }]
    flat = list(flatten_tree(tree))
    addrs = [f["trace_address"] for f in flat]
    assert addrs == ["root", "0", "1", "1.0"]


def test_extract_call_traces_shapes_records(load_fixture):
    tree = load_fixture("call_trace_nested.json")
    rpc = MagicMock()
    rpc.debug_trace_transaction.return_value = tree

    tx_hash = "0xdea" + "00" * 29 + "ff"
    records = list(extract_call_traces(rpc, block_number=18_500_123, tx_hash=tx_hash))

    assert records[0]["call_type"] == "CALL"
    assert records[0]["from_address"] == "0xabCd00000000000000000000000000000000dEaD"
    assert records[0]["to_address"] == "0xA0b86991c6218b36c1D19D4a2e9Eb0cE3606eB48"
    assert records[0]["function_selector"] == "0xa9059cbb"
    assert records[0]["gas_used"] == 31_400
    assert records[0]["error"] is None

    assert records[1]["call_type"] == "STATICCALL"
    assert records[1]["value"] == "0"

    assert records[2]["call_type"] == "DELEGATECALL"
    assert records[2]["error"] == "execution reverted"
    assert records[2]["revert_reason"] == "0x08c379a0"


def test_flatten_create_null_to():
    tree = {
        "type": "CREATE",
        "from": "0xabcd00000000000000000000000000000000dead",
        "to": None,
        "value": "0x0",
        "gas": "0x100000",
        "gasUsed": "0x1000",
        "input": "0x60806040",
        "output": "0x60806040"
    }
    flat = list(flatten_tree(tree))
    assert flat[0]["to"] is None
    assert flat[0]["type"] == "CREATE"
```

- [ ] **Step 3: Run test to verify failure**

Run: `pytest tests/test_extractor_call_traces.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement `extractors/call_traces.py`**

Create `src/evm_log_extractor/extractors/call_traces.py`:

```python
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
```

- [ ] **Step 5: Run test to verify pass**

Run: `pytest tests/test_extractor_call_traces.py -v`
Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/evm_log_extractor/extractors/call_traces.py tests/fixtures/call_trace_nested.json tests/test_extractor_call_traces.py
git commit -m "feat(extractor): call_traces with nested tree flatten to trace_address paths"
```

---

## Task 11: Extractor CLI (`cli/extract.py`)

**Files:**
- Create: `src/evm_log_extractor/cli/extract.py`
- Create: `tests/test_cli_smoke.py`

- [ ] **Step 1: Write failing smoke test**

Create `tests/test_cli_smoke.py`:

```python
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from evm_log_extractor.cli.extract import main as extract_main


@patch("evm_log_extractor.cli.extract.RpcClient")
def test_extract_cli_runs_blocks_only(MockRpcCls, tmp_path: Path):
    rpc = MagicMock()
    MockRpcCls.from_url.return_value = rpc
    rpc.chain_id.return_value = 31337
    rpc.latest_block.return_value = 2
    rpc.anvil_node_info.return_value = {"clientVersion": "anvil/test"}
    rpc.get_block.side_effect = [
        {
            "number": hex(i), "hash": f"0x{i:064x}",
            "parentHash": "0x" + "00" * 32,
            "timestamp": "0x1", "miner": "0x0000000000000000000000000000000000000000",
            "gasLimit": "0x1", "gasUsed": "0x0", "baseFeePerGas": None,
            "size": "0x1", "stateRoot": "0x" + "00" * 32,
            "transactionsRoot": "0x" + "00" * 32, "receiptsRoot": "0x" + "00" * 32,
            "sha3Uncles": "0x" + "00" * 32, "logsBloom": "0x" + "00" * 256,
            "extraData": "0x", "nonce": "0x" + "00" * 8,
            "mixHash": "0x" + "00" * 32, "difficulty": "0x0",
            "totalDifficulty": "0x0", "withdrawalsRoot": None,
            "transactions": [],
        }
        for i in range(3)
    ]

    runner = CliRunner()
    result = runner.invoke(
        extract_main,
        [
            "--rpc", "http://127.0.0.1:8545",
            "--from-block", "0", "--to-block", "2",
            "--entities", "blocks",
            "--base-dir", str(tmp_path),
            "--label", "smoke",
        ],
    )
    assert result.exit_code == 0, result.output

    # find the run dir
    run_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    blocks = (run_dir / "raw" / "blocks.ndjson").read_text().strip().split("\n")
    assert len(blocks) == 3

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["counts"]["blocks"] == 3
    assert "raw/blocks.ndjson" in manifest["hashes"]
    assert manifest["rpc"]["chain_id"] == 31337
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_cli_smoke.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `cli/extract.py`**

Create `src/evm_log_extractor/cli/extract.py`:

```python
"""`evm-extract` CLI — pulls raw entities from JSON-RPC into NDJSON files."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from .. import __version__
from ..extractors.blocks import extract_block
from ..extractors.call_traces import extract_call_traces
from ..extractors.event_logs import extract_event_logs
from ..extractors.receipts import extract_receipt
from ..extractors.transactions import extract_transactions
from ..manifest import Manifest
from ..ndjson import NdjsonWriter
from ..rpc import RpcClient

TIER1 = ("blocks", "transactions", "receipts", "event_logs", "call_traces")


def _resolve_block(rpc: RpcClient, value: str) -> int:
    return rpc.latest_block() if value == "latest" else int(value)


@click.command(name="evm-extract")
@click.option("--rpc", "rpc_url", default="http://127.0.0.1:8545", show_default=True, help="JSON-RPC endpoint")
@click.option("--from-block", "from_block", required=True, help="Starting block number or 'latest'")
@click.option("--to-block", "to_block", required=True, help="Ending block number or 'latest'")
@click.option("--entities", default=",".join(TIER1), show_default=True, help="Comma-separated entity list")
@click.option("--address", default=None, help="Filter event_logs by emitter address")
@click.option("--base-dir", "base_dir", default="output", show_default=True, help="Parent directory for run folders")
@click.option("--label", default=None, help="Human-friendly run label (appears in run-id)")
def main(
    rpc_url: str,
    from_block: str,
    to_block: str,
    entities: str,
    address: Optional[str],
    base_dir: str,
    label: Optional[str],
) -> None:
    selected = [e.strip() for e in entities.split(",") if e.strip()]
    for e in selected:
        if e not in TIER1:
            click.echo(f"unknown entity: {e}. Tier-1 supported: {TIER1}", err=True)
            sys.exit(2)

    rpc = RpcClient.from_url(rpc_url)
    chain_id = rpc.chain_id()
    from_n = _resolve_block(rpc, from_block)
    to_n = _resolve_block(rpc, to_block)
    if from_n > to_n:
        click.echo(f"from-block {from_n} > to-block {to_n}", err=True)
        sys.exit(2)

    run_id = Manifest.build_run_id(label, from_n, to_n)
    run_dir = Path(base_dir) / run_id
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    manifest = Manifest(
        run_id=run_id,
        tool_version=__version__,
        rpc_url=rpc_url,
        chain_id=chain_id,
        cli_args={
            "from_block": from_n,
            "to_block": to_n,
            "entities": selected,
            "address_filter": address,
        },
    )
    manifest.set_node_info(rpc.anvil_node_info())

    counts: dict[str, int] = {}
    hashes: dict[str, str] = {}

    def _write(entity: str, iterator):
        path = raw_dir / f"{entity}.ndjson"
        with NdjsonWriter(path) as w:
            for rec in iterator:
                w.write(rec)
        counts[entity] = w.count
        hashes[f"raw/{entity}.ndjson"] = f"sha256:{w.sha256}"
        click.echo(f"  {entity}: {w.count} records")

    click.echo(f"[extract] run_id={run_id} blocks={from_n}..{to_n}")

    if "blocks" in selected:
        _write("blocks", (extract_block(rpc, n) for n in range(from_n, to_n + 1)))

    if "transactions" in selected:
        def _tx_iter():
            for n in range(from_n, to_n + 1):
                yield from extract_transactions(rpc, n)
        _write("transactions", _tx_iter())

    if "receipts" in selected:
        # iterate over tx hashes from the transactions file or re-pull per block
        def _rc_iter():
            for n in range(from_n, to_n + 1):
                blk = rpc.get_block(n, full_tx=False)
                for tx_hash in blk.get("transactions") or []:
                    h = tx_hash if isinstance(tx_hash, str) else "0x" + tx_hash.hex()
                    yield extract_receipt(rpc, h)
        _write("receipts", _rc_iter())

    if "event_logs" in selected:
        _write("event_logs", extract_event_logs(rpc, from_n, to_n, address=address))

    if "call_traces" in selected:
        def _ct_iter():
            for n in range(from_n, to_n + 1):
                blk = rpc.get_block(n, full_tx=False)
                for tx_hash in blk.get("transactions") or []:
                    h = tx_hash if isinstance(tx_hash, str) else "0x" + tx_hash.hex()
                    yield from extract_call_traces(rpc, block_number=n, tx_hash=h)
        _write("call_traces", _ct_iter())

    manifest.set_counts(counts)
    manifest.set_hashes(hashes)
    manifest.write(run_dir / "manifest.json")

    click.echo(f"[extract] done. output: {run_dir}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify pass**

Run: `pytest tests/test_cli_smoke.py -v`
Expected: 1 test PASSES.

- [ ] **Step 5: Run full test suite to check no regressions**

Run: `pytest -v`
Expected: all tests PASS so far.

- [ ] **Step 6: Commit**

```bash
git add src/evm_log_extractor/cli/extract.py tests/test_cli_smoke.py
git commit -m "feat(cli): evm-extract tier-1 entity CLI with manifest writing"
```

---

## Task 12: Normaliser (`normaliser.py` + CLI)

**Files:**
- Create: `src/evm_log_extractor/normaliser.py`
- Create: `src/evm_log_extractor/cli/normalise.py`
- Create: `tests/test_normaliser.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_normaliser.py`:

```python
import json
from pathlib import Path

import pytest

from evm_log_extractor.normaliser import normalise_run, ValidationError


def _write_raw(run_dir: Path, entity: str, records: list[dict]) -> None:
    raw = run_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    with open(raw / f"{entity}.ndjson", "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def test_normaliser_copies_and_validates(tmp_run_dir):
    _write_raw(tmp_run_dir, "blocks", [{"block_number": 1, "block_hash": "0x" + "ab" * 32}])
    _write_raw(tmp_run_dir, "transactions", [
        {"tx_hash": "0x" + "de" * 32, "block_number": 1, "block_hash": "0x" + "ab" * 32}
    ])
    _write_raw(tmp_run_dir, "receipts", [
        {"tx_hash": "0x" + "de" * 32, "block_number": 1, "block_hash": "0x" + "ab" * 32, "logs_count": 1}
    ])
    _write_raw(tmp_run_dir, "event_logs", [
        {"tx_hash": "0x" + "de" * 32, "log_index": 0, "block_number": 1, "block_hash": "0x" + "ab" * 32,
         "address": "0xA0b86991c6218b36c1D19D4a2e9Eb0cE3606eB48"}
    ])

    counts = normalise_run(tmp_run_dir)
    assert counts == {"blocks": 1, "transactions": 1, "receipts": 1, "event_logs": 1}
    assert (tmp_run_dir / "norm" / "blocks.ndjson").exists()


def test_normaliser_rejects_duplicate_pk(tmp_run_dir):
    _write_raw(tmp_run_dir, "blocks", [
        {"block_number": 1, "block_hash": "0x" + "ab" * 32},
        {"block_number": 1, "block_hash": "0x" + "cd" * 32},
    ])
    with pytest.raises(ValidationError, match="duplicate"):
        normalise_run(tmp_run_dir)


def test_normaliser_rejects_logs_count_mismatch(tmp_run_dir):
    _write_raw(tmp_run_dir, "blocks", [{"block_number": 1, "block_hash": "0x" + "ab" * 32}])
    _write_raw(tmp_run_dir, "transactions", [
        {"tx_hash": "0x" + "de" * 32, "block_number": 1, "block_hash": "0x" + "ab" * 32}
    ])
    _write_raw(tmp_run_dir, "receipts", [
        {"tx_hash": "0x" + "de" * 32, "block_number": 1, "block_hash": "0x" + "ab" * 32, "logs_count": 3}
    ])
    _write_raw(tmp_run_dir, "event_logs", [
        {"tx_hash": "0x" + "de" * 32, "log_index": 0, "block_number": 1, "block_hash": "0x" + "ab" * 32,
         "address": "0xA0b86991c6218b36c1D19D4a2e9Eb0cE3606eB48"}
    ])
    with pytest.raises(ValidationError, match="logs_count"):
        normalise_run(tmp_run_dir)
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_normaliser.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `normaliser.py`**

Create `src/evm_log_extractor/normaliser.py`:

```python
"""Normalisation pass + validation. See raw-log-schema.md §10.

Extraction already performs type-canonicalisation (addresses checksummed,
hex lowercased, wei → decimal string). The normaliser's job is therefore:

1. stream raw → norm with identity transform (placeholder for future
   re-canonicalisation if raw is imported from another tool)
2. enforce validation rules: duplicate PKs, cross-file consistency,
   receipts.logs_count match.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .ndjson import NdjsonWriter, read_ndjson

ENTITIES = ("blocks", "transactions", "receipts", "event_logs", "call_traces")
PK_BY_ENTITY = {
    "blocks": ("block_number",),
    "transactions": ("tx_hash",),
    "receipts": ("tx_hash",),
    "event_logs": ("tx_hash", "log_index"),
    "call_traces": ("tx_hash", "trace_address"),
}


class ValidationError(RuntimeError):
    pass


def _copy_with_dedup_check(src: Path, dst: Path, pk_fields: tuple[str, ...]) -> int:
    seen: set = set()
    with NdjsonWriter(dst) as w:
        for rec in read_ndjson(src):
            key = tuple(rec.get(k) for k in pk_fields)
            if key in seen:
                raise ValidationError(
                    f"{src.name}: duplicate primary key {key}"
                )
            seen.add(key)
            w.write(rec)
    return w.count


def normalise_run(run_dir: Path | str) -> dict[str, int]:
    run = Path(run_dir)
    raw = run / "raw"
    norm = run / "norm"
    norm.mkdir(parents=True, exist_ok=True)

    counts: dict[str, int] = {}
    for entity in ENTITIES:
        src = raw / f"{entity}.ndjson"
        if not src.exists():
            continue
        pk = PK_BY_ENTITY[entity]
        counts[entity] = _copy_with_dedup_check(src, norm / f"{entity}.ndjson", pk)

    # cross-file validation: receipts.logs_count == count(event_logs per tx)
    if {"receipts", "event_logs"} <= counts.keys():
        log_counts: dict[str, int] = defaultdict(int)
        for log in read_ndjson(norm / "event_logs.ndjson"):
            log_counts[log["tx_hash"]] += 1
        for r in read_ndjson(norm / "receipts.ndjson"):
            expected = r.get("logs_count", 0)
            actual = log_counts.get(r["tx_hash"], 0)
            if expected != actual:
                raise ValidationError(
                    f"receipts.logs_count mismatch for tx {r['tx_hash']}: "
                    f"receipt says {expected}, event_logs has {actual}"
                )

    # cross-file: every transactions.block_number present in blocks
    if {"blocks", "transactions"} <= counts.keys():
        block_numbers = {b["block_number"] for b in read_ndjson(norm / "blocks.ndjson")}
        for tx in read_ndjson(norm / "transactions.ndjson"):
            if tx["block_number"] not in block_numbers:
                raise ValidationError(
                    f"transactions.tx_hash={tx['tx_hash']} references missing block {tx['block_number']}"
                )

    return counts
```

- [ ] **Step 4: Implement `cli/normalise.py`**

Create `src/evm_log_extractor/cli/normalise.py`:

```python
"""`evm-normalise` CLI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import click

from ..normaliser import ValidationError, normalise_run


@click.command(name="evm-normalise")
@click.option("--run", "run_id", default=None, help="Run id (combined with --base-dir)")
@click.option("--base-dir", default="output", show_default=True)
@click.option("--in-dir", "in_dir", default=None, help="Explicit run directory (overrides --run/--base-dir)")
def main(run_id: Optional[str], base_dir: str, in_dir: Optional[str]) -> None:
    if in_dir:
        run_dir = Path(in_dir)
    elif run_id:
        run_dir = Path(base_dir) / run_id
    else:
        click.echo("provide --in-dir or --run", err=True)
        sys.exit(2)
    if not run_dir.exists():
        click.echo(f"not found: {run_dir}", err=True)
        sys.exit(1)

    try:
        counts = normalise_run(run_dir)
    except ValidationError as e:
        click.echo(f"[normalise] validation error: {e}", err=True)
        sys.exit(1)

    click.echo(f"[normalise] run_dir={run_dir}")
    for entity, n in counts.items():
        click.echo(f"  {entity}: {n} records")
    click.echo("[normalise] done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify pass**

Run: `pytest tests/test_normaliser.py -v`
Expected: 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/evm_log_extractor/normaliser.py src/evm_log_extractor/cli/normalise.py tests/test_normaliser.py
git commit -m "feat(normaliser): dedup PK check + cross-file validation + CLI"
```

---

## Task 13: ABI loader (`abi_loader.py`)

**Files:**
- Create: `src/evm_log_extractor/abi_loader.py`
- Create: `tests/fixtures/erc20_abi.json`
- Create: `tests/test_abi_loader.py`

- [ ] **Step 1: Write fixture**

Create `tests/fixtures/erc20_abi.json`:

```json
{
  "abi": [
    {
      "anonymous": false,
      "inputs": [
        {"indexed": true, "internalType": "address", "name": "from", "type": "address"},
        {"indexed": true, "internalType": "address", "name": "to", "type": "address"},
        {"indexed": false, "internalType": "uint256", "name": "value", "type": "uint256"}
      ],
      "name": "Transfer",
      "type": "event"
    },
    {
      "inputs": [
        {"internalType": "address", "name": "to", "type": "address"},
        {"internalType": "uint256", "name": "amount", "type": "uint256"}
      ],
      "name": "transfer",
      "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
      "stateMutability": "nonpayable",
      "type": "function"
    }
  ]
}
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_abi_loader.py`:

```python
import json
from pathlib import Path

import pytest

from evm_log_extractor.abi_loader import AbiIndex, load_abi_sources


def test_load_foundry_artifact(fixtures_dir, tmp_path):
    idx = load_abi_sources(abi_files=[fixtures_dir / "erc20_abi.json"])
    transfer_topic0 = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    assert idx.lookup_event(transfer_topic0) is not None
    assert idx.lookup_event(transfer_topic0)["name"] == "Transfer"


def test_load_raw_abi_array(tmp_path):
    raw = [
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "a", "type": "address"},
                {"indexed": False, "name": "v", "type": "uint256"},
            ],
            "name": "Ping",
            "type": "event",
        }
    ]
    f = tmp_path / "raw.json"
    f.write_text(json.dumps(raw))
    idx = load_abi_sources(abi_files=[f])
    import eth_utils
    topic0 = "0x" + eth_utils.keccak(text="Ping(address,uint256)").hex()
    assert idx.lookup_event(topic0)["name"] == "Ping"


def test_load_dir_recursive(fixtures_dir, tmp_path):
    # copy fixture into a nested dir and load via --abi-dir
    nested = tmp_path / "out" / "ERC20.sol"
    nested.mkdir(parents=True)
    (nested / "ERC20.json").write_text((fixtures_dir / "erc20_abi.json").read_text())
    idx = load_abi_sources(abi_dirs=[tmp_path / "out"])
    assert idx.lookup_function("0xa9059cbb")["name"] == "transfer"


def test_missing_source_raises():
    with pytest.raises(ValueError, match="no ABI"):
        load_abi_sources()
```

- [ ] **Step 3: Run test to verify failure**

Run: `pytest tests/test_abi_loader.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 4: Implement `abi_loader.py`**

Create `src/evm_log_extractor/abi_loader.py`:

```python
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
```

- [ ] **Step 5: Run test to verify pass**

Run: `pytest tests/test_abi_loader.py -v`
Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/evm_log_extractor/abi_loader.py tests/fixtures/erc20_abi.json tests/test_abi_loader.py
git commit -m "feat(abi): Foundry/Hardhat/raw ABI loader with topic0 + selector index"
```

---

## Task 14: Decoder (`decoder.py` + CLI)

**Files:**
- Create: `src/evm_log_extractor/decoder.py`
- Create: `src/evm_log_extractor/cli/decode.py`
- Create: `tests/test_decoder.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_decoder.py`:

```python
import json
from pathlib import Path

from evm_log_extractor.abi_loader import load_abi_sources
from evm_log_extractor.decoder import decode_event_logs


def _sample_transfer_log() -> dict:
    return {
        "block_number": 1, "block_hash": "0x" + "ab" * 32,
        "tx_hash": "0x" + "de" * 32, "tx_index": 0, "log_index": 0,
        "address": "0xA0b86991c6218b36c1D19D4a2e9Eb0cE3606eB48",
        "topic0": "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
        "topic1": "0x000000000000000000000000abcd00000000000000000000000000000000dead",
        "topic2": "0x000000000000000000000000beef020000000000000000000000000000000002",
        "topic3": None,
        "topics_count": 3,
        "data": "0x00000000000000000000000000000000000000000000000000000000000003e8",
        "removed": False,
    }


def test_decode_event_logs_transfer(fixtures_dir, tmp_path):
    idx = load_abi_sources(abi_files=[fixtures_dir / "erc20_abi.json"])
    logs_file = tmp_path / "event_logs.ndjson"
    with open(logs_file, "w") as f:
        f.write(json.dumps(_sample_transfer_log()) + "\n")

    out = tmp_path / "decoded.ndjson"
    unmatched = tmp_path / "unmatched.ndjson"
    stats = decode_event_logs(logs_file, idx, out_path=out, unmatched_path=unmatched)

    assert stats["matched"] == 1
    assert stats["unmatched"] == 0
    rec = json.loads(out.read_text().strip())
    assert rec["event_name"] == "Transfer"
    assert rec["event_signature"] == "Transfer(address,address,uint256)"
    assert rec["decoded"]["value"] == "1000"
    assert rec["decoded"]["from"] == "0xabCd00000000000000000000000000000000dEaD"
    assert rec["decoded"]["to"] == "0xBEef020000000000000000000000000000000002"


def test_decode_event_logs_unmatched(fixtures_dir, tmp_path):
    idx = load_abi_sources(abi_files=[fixtures_dir / "erc20_abi.json"])
    log = _sample_transfer_log()
    log["topic0"] = "0x" + "ff" * 32
    logs_file = tmp_path / "event_logs.ndjson"
    with open(logs_file, "w") as f:
        f.write(json.dumps(log) + "\n")

    out = tmp_path / "decoded.ndjson"
    unmatched = tmp_path / "unmatched.ndjson"
    stats = decode_event_logs(logs_file, idx, out_path=out, unmatched_path=unmatched)

    assert stats["matched"] == 0
    assert stats["unmatched"] == 1
    u = json.loads(unmatched.read_text().strip())
    assert u["topic0"] == "0x" + "ff" * 32
    # decoded ndjson should still contain a row with decoded:null
    passthrough = json.loads(out.read_text().strip())
    assert passthrough["decoded"] is None
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/test_decoder.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `decoder.py`**

Create `src/evm_log_extractor/decoder.py`:

```python
"""Event-log decoder. See raw-log-schema.md §Decode Pass."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from eth_abi import decode as abi_decode
from eth_utils import to_checksum_address

from .abi_loader import AbiIndex
from .ndjson import NdjsonWriter, read_ndjson


def _event_signature(abi_entry: dict) -> str:
    return f"{abi_entry['name']}({','.join(i['type'] for i in abi_entry.get('inputs', []))})"


def _decode_topic_word(word_hex: str, sol_type: str) -> Any:
    b = bytes.fromhex(word_hex[2:])
    if sol_type == "address":
        return to_checksum_address("0x" + b[-20:].hex())
    if sol_type.startswith("uint") or sol_type.startswith("int"):
        return str(int.from_bytes(b, "big", signed=sol_type.startswith("int")))
    if sol_type == "bool":
        return bool(int.from_bytes(b, "big"))
    # dynamic types (string/bytes/arrays) are hashed when indexed — return raw hash
    return word_hex


def _decode_data(data_hex: str, types: list[str]) -> list[Any]:
    raw = bytes.fromhex(data_hex[2:]) if data_hex and data_hex != "0x" else b""
    if not types:
        return []
    vals = abi_decode(types, raw)
    out: list[Any] = []
    for t, v in zip(types, vals):
        if t == "address":
            out.append(to_checksum_address(v))
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
        # topics[0] is topic0 (signature); indexed params start at topics[1]
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
```

- [ ] **Step 4: Implement `cli/decode.py`**

Create `src/evm_log_extractor/cli/decode.py`:

```python
"""`evm-decode` CLI."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple

import click

from ..abi_loader import load_abi_sources
from ..decoder import decode_event_logs


@click.command(name="evm-decode")
@click.option("--input", "input_path", required=True, type=click.Path(exists=True, path_type=Path))
@click.option("--out", "out_path", required=True, type=click.Path(path_type=Path))
@click.option("--unmatched", "unmatched_path", default=None, type=click.Path(path_type=Path))
@click.option("--manifest", "manifest_path", default=None, type=click.Path(path_type=Path))
@click.option("--abi", "abi_files", multiple=True, type=click.Path(exists=True, path_type=Path))
@click.option("--abi-dir", "abi_dirs", multiple=True, type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--foundry-project", "foundry_project", default=None, type=click.Path(exists=True, file_okay=False, path_type=Path))
def main(
    input_path: Path,
    out_path: Path,
    unmatched_path: Optional[Path],
    manifest_path: Optional[Path],
    abi_files: Tuple[Path, ...],
    abi_dirs: Tuple[Path, ...],
    foundry_project: Optional[Path],
) -> None:
    try:
        idx = load_abi_sources(
            abi_files=list(abi_files),
            abi_dirs=list(abi_dirs),
            foundry_project=foundry_project,
        )
    except ValueError as e:
        click.echo(str(e), err=True)
        sys.exit(2)

    unmatched = unmatched_path or out_path.with_name("unmatched.ndjson")
    manifest = manifest_path or out_path.with_name("abi_manifest.json")

    stats = decode_event_logs(
        input_path=input_path,
        index=idx,
        out_path=out_path,
        unmatched_path=unmatched,
        manifest_path=manifest,
    )
    click.echo(f"[decode] matched={stats['matched']} unmatched={stats['unmatched']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify pass**

Run: `pytest tests/test_decoder.py -v`
Expected: 2 tests PASS.

- [ ] **Step 6: Run full test suite**

Run: `pytest -v`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/evm_log_extractor/decoder.py src/evm_log_extractor/cli/decode.py tests/test_decoder.py
git commit -m "feat(decoder): event-log decode + abi_manifest + unmatched passthrough + CLI"
```

---

## Task 15: README.md (with decode flow explanation)

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

Create `README.md`:

````markdown
# evm-log-extractor

Forensics-grade EVM log extractor, normaliser, and decoder for Anvil / Foundry local nodes and any EVM JSON-RPC endpoint. Produces deterministic NDJSON output suitable for smart-contract exploit investigation, protocol auditing, and on-chain analytics.

**Key properties**
- Three independent stages (extract, normalise, decode) — run separately or as a pipeline.
- NDJSON output — streaming-friendly, diffable, grep-able, no DB dependency.
- EIP-55 checksummed addresses, lowercase hex, decimal-string wei — canonical and stable.
- Per-run `manifest.json` with sha256 hashes for reproducibility.
- ABI decode from Foundry project, Hardhat artifacts, or raw ABI JSON.
- Anvil-aware: captures `anvil_nodeInfo`, handles fork metadata, instant-mine friendly.

---

## Installation

```bash
git clone https://github.com/<you>/evm-log-extractor.git
cd evm-log-extractor
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Three CLI entry points are installed: `evm-extract`, `evm-normalise`, `evm-decode`.

---

## Quickstart (three stages)

### 1. Extract

Pull raw data for a block range from a running Anvil node:

```bash
anvil &                                # start local node in background

evm-extract \
  --rpc http://127.0.0.1:8545 \
  --from-block 0 --to-block 200 \
  --entities blocks,transactions,receipts,event_logs,call_traces \
  --base-dir ./output \
  --label curve-reentrancy
```

Produces:

```
output/2026-04-22T14-33-07Z__curve-reentrancy/
├── manifest.json
└── raw/
    ├── blocks.ndjson
    ├── transactions.ndjson
    ├── receipts.ndjson
    ├── event_logs.ndjson
    └── call_traces.ndjson
```

### 2. Normalise

Validates PK uniqueness, cross-file consistency, `receipts.logs_count` parity. Produces the canonical `norm/` directory:

```bash
evm-normalise --in-dir output/2026-04-22T14-33-07Z__curve-reentrancy/
```

Produces:

```
output/2026-04-22T14-33-07Z__curve-reentrancy/
└── norm/
    ├── blocks.ndjson
    ├── transactions.ndjson
    ├── receipts.ndjson
    ├── event_logs.ndjson
    └── call_traces.ndjson
```

### 3. Decode

Attach event names and decoded parameters using ABIs from the client's Foundry project:

```bash
evm-decode \
  --input  output/2026-04-22T14-33-07Z__curve-reentrancy/norm/event_logs.ndjson \
  --out    output/2026-04-22T14-33-07Z__curve-reentrancy/decoded/event_logs.ndjson \
  --foundry-project ../client-forge-repo
```

Produces:

```
output/2026-04-22T14-33-07Z__curve-reentrancy/
└── decoded/
    ├── event_logs.ndjson       # original fields + event_name, event_signature, decoded
    ├── unmatched.ndjson        # logs with no ABI match, for audit
    └── abi_manifest.json       # loaded ABIs, topic0 indexes, match/unmatched counts
```

---

## How decoding works

The decoder is ABI-dependent by design — extraction and normalisation are ABI-free so they can run the moment exploit data hits the node, and decode is replayable whenever the client ships a new or corrected ABI.

```
 ┌────────────────────────────┐
 │  norm/event_logs.ndjson    │   canonical logs (topic0, topic1..3, data)
 └────────────┬───────────────┘
              │
              ▼
 ┌────────────────────────────┐   ABI sources (any combination):
 │      abi_loader            │   • --abi <file>          (raw ABI JSON)
 │                            │◄──• --abi-dir <dir>       (globs *.json recursively)
 │  builds:                   │   • --foundry-project <d> (reads <d>/out/**/*.json)
 │   topic0  → event_abi      │
 │   selector → fn_abi        │
 └────────────┬───────────────┘
              │
              ▼
 ┌────────────────────────────┐
 │         decoder            │
 │                            │
 │  for each log:             │
 │   topic0 = log.topic0      │
 │   event  = topic0_index[.] │
 │   if event:                │
 │     decode indexed topics  │──► decoded[name] = value (per Solidity type)
 │     decode data via eth_abi│
 │     emit decoded row       │
 │   else:                    │
 │     passthrough decoded:null
 │     append to unmatched    │
 └────────────┬───────────────┘
              │
              ├──► decoded/event_logs.ndjson
              ├──► decoded/unmatched.ndjson
              └──► decoded/abi_manifest.json
```

### Decode specifics

1. **Topic hashing.** For every event in the loaded ABI, the decoder computes `keccak256("EventName(type1,type2,...)")`. That 32-byte hash is the canonical `topic0`. The index maps `topic0 → event_abi`.

2. **Indexed vs non-indexed params.** Solidity events have up to 3 indexed params that live in `topic1`, `topic2`, `topic3`, while non-indexed params sit ABI-encoded in `data`. The decoder:
   - decodes indexed params one-by-one from their topic word (address = last 20 bytes, uint/int = big-endian integer, bool = 0/1, dynamic types = hash).
   - passes non-indexed params through `eth_abi.decode(types, bytes.fromhex(data[2:]))`.

3. **Canonical output.** Numbers become decimal strings (uint256 exceeds JS `Number`), addresses are EIP-55 checksummed, bytes are `0x…` lowercase. Matches the rest of the pipeline.

4. **Unmatched logs are preserved.** A log with no matching topic0 is still written to `decoded/event_logs.ndjson` with `decoded: null`, and *also* to `decoded/unmatched.ndjson` with its original fields — the forensic audit trail lives there. `abi_manifest.json` carries per-topic0 match and unmatched counts.

5. **Anonymous events** (`anonymous: true` in ABI, no `topic0`) are skipped by v1 — they pass through as unmatched.

6. **Proxies.** If the same `topic0` appears in multiple loaded ABIs, the first-loaded wins and a collision note goes into `abi_manifest.json`. For proxy patterns where logs fire from the proxy but the ABI lives on the implementation, just load both ABIs — the topic0 will match the implementation's event.

### When decode cannot match

You will see `unmatched` > 0 if any of:

- The client's Foundry project was not compiled (`out/` missing) — run `forge build` before passing `--foundry-project`.
- Logs originate from contracts the client did not ship ABIs for (external protocols, dependencies). Load the upstream ABIs separately with `--abi`.
- The event in the ABI does not have `anonymous: false` with a non-empty signature — anonymous events are skipped.

Every unmatched log is still captured in `unmatched.ndjson`. You can load more ABIs and re-run `evm-decode` against the same `norm/event_logs.ndjson` — decode never re-hits the RPC.

---

## CLI reference

### `evm-extract`

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--rpc` | | `http://127.0.0.1:8545` | JSON-RPC endpoint |
| `--from-block` | ✓ | | Start block (int or `latest`) |
| `--to-block` | ✓ | | End block (int or `latest`) |
| `--entities` | | `blocks,transactions,receipts,event_logs,call_traces` | Comma list |
| `--address` | | | Filter `event_logs` by emitter |
| `--base-dir` | | `output` | Parent dir for run folders |
| `--label` | | | Human label; joined into `run_id` |

### `evm-normalise`

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--in-dir` | one of | | Explicit run directory |
| `--run` | one of | | Run id (with `--base-dir`) |
| `--base-dir` | | `output` | Parent dir when using `--run` |

### `evm-decode`

| Flag | Required | Default | Meaning |
|---|---|---|---|
| `--input` | ✓ | | Path to normalised `event_logs.ndjson` |
| `--out` | ✓ | | Path to decoded output NDJSON |
| `--unmatched` | | `<out>/../unmatched.ndjson` | Unmatched logs |
| `--manifest` | | `<out>/../abi_manifest.json` | ABI manifest |
| `--abi` | | (repeatable) | Single ABI JSON file |
| `--abi-dir` | | (repeatable) | Directory globbed recursively |
| `--foundry-project` | | | Foundry project dir (uses `out/`) |

---

## Canonical schema

All entity field definitions, types, edge cases, join keys, and derivation rules live in [`raw-log-schema.md`](./raw-log-schema.md). That document is the source of truth — if the code and the schema disagree, the schema wins.

---

## Development

```bash
source .venv/bin/activate
pytest -v                                    # run full test suite
pytest tests/test_decoder.py -v              # single file
pytest tests/test_decoder.py::test_decode_event_logs_transfer -v   # single test
```

---

## License

MIT.
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: README with quickstart, decode flow explainer, CLI reference"
```

---

## Task 16: Apple-styled docs page (`docs/index.html`)

**Files:**
- Create: `docs/index.html`
- Create: `docs/styles.css`

- [ ] **Step 1: Write `docs/styles.css`**

Create `docs/styles.css`:

```css
:root {
  --bg-dark: #000000;
  --bg-light: #f5f5f7;
  --text-dark: #1d1d1f;
  --text-light: #ffffff;
  --accent: #0071e3;
  --link-light: #0066cc;
  --link-dark: #2997ff;
  --surface-card: #272729;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

html { scroll-behavior: smooth; }

body {
  font-family: "SF Pro Text", "SF Pro Icons", "Helvetica Neue", Helvetica, Arial, sans-serif;
  font-size: 17px;
  line-height: 1.47;
  letter-spacing: -0.374px;
  color: var(--text-dark);
  background: var(--bg-light);
  -webkit-font-smoothing: antialiased;
}

.nav {
  position: sticky;
  top: 0;
  z-index: 10;
  height: 48px;
  background: rgba(0, 0, 0, 0.8);
  backdrop-filter: saturate(180%) blur(20px);
  -webkit-backdrop-filter: saturate(180%) blur(20px);
  display: flex;
  align-items: center;
  padding: 0 22px;
}
.nav__brand {
  color: var(--text-light);
  font-family: "SF Pro Display", "Helvetica Neue", sans-serif;
  font-size: 21px;
  font-weight: 600;
  letter-spacing: 0.231px;
  text-decoration: none;
}
.nav__links { margin-left: auto; display: flex; gap: 32px; }
.nav__link {
  color: rgba(255, 255, 255, 0.8);
  font-size: 14px;
  text-decoration: none;
  letter-spacing: -0.224px;
}
.nav__link:hover { color: var(--text-light); }

.hero {
  background: var(--bg-dark);
  color: var(--text-light);
  padding: 120px 22px 140px;
  text-align: center;
}
.hero__title {
  font-family: "SF Pro Display", sans-serif;
  font-size: 56px;
  font-weight: 600;
  line-height: 1.07;
  letter-spacing: -0.28px;
  margin-bottom: 16px;
}
.hero__tag {
  font-family: "SF Pro Display", sans-serif;
  font-size: 28px;
  font-weight: 400;
  line-height: 1.14;
  letter-spacing: 0.196px;
  color: rgba(255, 255, 255, 0.86);
  max-width: 720px;
  margin: 0 auto 40px;
}
.hero__cta {
  display: inline-block;
  padding: 12px 22px;
  background: var(--accent);
  color: var(--text-light);
  font-size: 17px;
  font-weight: 400;
  text-decoration: none;
  border-radius: 980px;
  transition: background-color 0.15s ease;
}
.hero__cta:hover { background: #0077ed; }
.hero__cta--ghost {
  background: transparent;
  border: 1px solid var(--link-dark);
  color: var(--link-dark);
  margin-left: 12px;
}
.hero__cta--ghost:hover { background: rgba(41, 151, 255, 0.08); }

.section {
  padding: 96px 22px;
  max-width: 980px;
  margin: 0 auto;
}
.section--dark {
  background: var(--bg-dark);
  color: var(--text-light);
  max-width: none;
  margin: 0;
}
.section--dark .section__inner { max-width: 980px; margin: 0 auto; padding: 0 22px; }

.section__eyebrow {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: -0.224px;
  color: var(--accent);
  text-transform: uppercase;
  margin-bottom: 12px;
}
.section__title {
  font-family: "SF Pro Display", sans-serif;
  font-size: 40px;
  font-weight: 600;
  line-height: 1.10;
  margin-bottom: 24px;
}
.section__body {
  font-size: 17px;
  line-height: 1.47;
  letter-spacing: -0.374px;
  max-width: 700px;
  margin-bottom: 24px;
}
.section__body a { color: var(--link-light); text-decoration: none; }
.section--dark .section__body a { color: var(--link-dark); }
.section__body a:hover { text-decoration: underline; }

.grid {
  display: grid;
  gap: 20px;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  margin-top: 32px;
}
.card {
  background: var(--bg-light);
  border-radius: 18px;
  padding: 32px 28px;
  box-shadow: rgba(0, 0, 0, 0.22) 3px 5px 30px 0px;
}
.section--dark .card { background: var(--surface-card); }
.card__title {
  font-family: "SF Pro Display", sans-serif;
  font-size: 21px;
  font-weight: 700;
  line-height: 1.19;
  letter-spacing: 0.231px;
  margin-bottom: 8px;
}
.card__body {
  font-size: 17px;
  line-height: 1.47;
  letter-spacing: -0.374px;
  color: rgba(0, 0, 0, 0.8);
}
.section--dark .card__body { color: rgba(255, 255, 255, 0.78); }

pre {
  background: #1d1d1f;
  color: #f5f5f7;
  padding: 24px;
  border-radius: 12px;
  overflow-x: auto;
  font-family: "SF Mono", ui-monospace, Menlo, Monaco, Consolas, monospace;
  font-size: 13.5px;
  line-height: 1.6;
  margin-top: 16px;
}
.section--dark pre { background: #0a0a0a; }

.pipe-row {
  display: flex;
  align-items: stretch;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 32px;
}
.pipe-step {
  flex: 1 1 220px;
  background: var(--surface-card);
  color: var(--text-light);
  border-radius: 14px;
  padding: 20px;
}
.pipe-step__num {
  font-size: 12px;
  font-weight: 600;
  color: var(--link-dark);
  letter-spacing: -0.12px;
  margin-bottom: 6px;
}
.pipe-step__title {
  font-family: "SF Pro Display", sans-serif;
  font-size: 21px;
  font-weight: 700;
  letter-spacing: 0.231px;
  margin-bottom: 8px;
}
.pipe-step__body { font-size: 14px; line-height: 1.43; color: rgba(255, 255, 255, 0.78); }

footer {
  background: var(--bg-light);
  padding: 40px 22px;
  text-align: center;
  color: rgba(0, 0, 0, 0.48);
  font-size: 12px;
  letter-spacing: -0.12px;
}
```

- [ ] **Step 2: Write `docs/index.html`**

Create `docs/index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>evm-log-extractor — forensic EVM data extraction</title>
<link rel="stylesheet" href="styles.css">
</head>
<body>

<nav class="nav">
  <a class="nav__brand" href="#">evm-log-extractor</a>
  <div class="nav__links">
    <a class="nav__link" href="#overview">Overview</a>
    <a class="nav__link" href="#pipeline">Pipeline</a>
    <a class="nav__link" href="#decode">Decode</a>
    <a class="nav__link" href="#install">Install</a>
    <a class="nav__link" href="https://github.com/">GitHub</a>
  </div>
</nav>

<section class="hero">
  <h1 class="hero__title">Forensic EVM data. Deterministic. Replayable.</h1>
  <p class="hero__tag">Extract, normalise, and decode smart-contract activity from Anvil, Foundry, or any EVM JSON-RPC endpoint — one NDJSON file per entity, one sha256 per file, one command per stage.</p>
  <a class="hero__cta" href="#install">Get started</a>
  <a class="hero__cta hero__cta--ghost" href="#decode">Decoding</a>
</section>

<section class="section" id="overview">
  <div class="section__eyebrow">Overview</div>
  <h2 class="section__title">Three stages. Zero surprises.</h2>
  <p class="section__body">Extraction is slow — it hits the RPC. Normalisation is deterministic — it is safe to rerun. Decoding depends on ABIs — it is replayable without touching the chain. The pipeline separates these cleanly so a single expensive extract can be re-normalised and re-decoded as many times as the investigation needs.</p>

  <div class="grid">
    <div class="card">
      <h3 class="card__title">Canonical types</h3>
      <p class="card__body">EIP-55 addresses, lowercase hex, decimal-string wei. The output is stable across runs and diffable across tools.</p>
    </div>
    <div class="card">
      <h3 class="card__title">Per-run manifest</h3>
      <p class="card__body">Every run writes <code>manifest.json</code> with chain id, node info, CLI args, record counts, and sha256 per file. Reproducibility is a first-class output.</p>
    </div>
    <div class="card">
      <h3 class="card__title">Anvil-native</h3>
      <p class="card__body">Uses <code>debug_traceTransaction</code> (callTracer, prestateTracer) out of the box. Captures <code>anvil_nodeInfo</code> including fork URL and fork block.</p>
    </div>
  </div>
</section>

<section class="section section--dark" id="pipeline">
  <div class="section__inner">
    <div class="section__eyebrow">Pipeline</div>
    <h2 class="section__title">Extract. Normalise. Decode.</h2>
    <p class="section__body">Each stage is a separate CLI, writing NDJSON to the filesystem. Pipe them or run them independently — both are first-class.</p>

    <div class="pipe-row">
      <div class="pipe-step">
        <div class="pipe-step__num">01 — extract</div>
        <div class="pipe-step__title">Raw from RPC</div>
        <div class="pipe-step__body">Pulls blocks, transactions, receipts, event logs, call traces. Hits the RPC once; never again for the same range.</div>
      </div>
      <div class="pipe-step">
        <div class="pipe-step__num">02 — normalise</div>
        <div class="pipe-step__title">Canonical + validated</div>
        <div class="pipe-step__body">Dedupes primary keys, enforces cross-file consistency, verifies <code>receipts.logs_count</code> matches actual log counts.</div>
      </div>
      <div class="pipe-step">
        <div class="pipe-step__num">03 — decode</div>
        <div class="pipe-step__title">ABI-aware, replayable</div>
        <div class="pipe-step__body">Attaches <code>event_name</code>, <code>event_signature</code>, and decoded parameters. Unmatched logs are preserved for audit.</div>
      </div>
    </div>

    <pre>anvil &amp;

evm-extract   --rpc http://127.0.0.1:8545 \
              --from-block 0 --to-block 200 \
              --label curve-reentrancy

evm-normalise --in-dir output/&lt;run-id&gt;

evm-decode    --input  output/&lt;run-id&gt;/norm/event_logs.ndjson \
              --out    output/&lt;run-id&gt;/decoded/event_logs.ndjson \
              --foundry-project ../client-forge-repo</pre>
  </div>
</section>

<section class="section" id="decode">
  <div class="section__eyebrow">Decoding</div>
  <h2 class="section__title">From topic0 to typed parameters.</h2>
  <p class="section__body">The decoder hashes every event in the loaded ABIs — <code>keccak256("EventName(type1,type2,...)")</code> — and indexes the result as <code>topic0 → event_abi</code>. For each log in the normalised stream it looks up <code>topic0</code>, decodes the indexed parameters directly from <code>topic1..3</code>, and passes the non-indexed parameters through <code>eth_abi.decode</code>. Unmatched logs are preserved verbatim in <code>unmatched.ndjson</code> so nothing is ever silently dropped.</p>

  <div class="grid">
    <div class="card">
      <h3 class="card__title">ABI sources</h3>
      <p class="card__body">Foundry <code>out/</code> directory, Hardhat <code>artifacts/</code> tree, or a single raw ABI JSON. Mix and match any combination on the command line.</p>
    </div>
    <div class="card">
      <h3 class="card__title">Indexed vs non-indexed</h3>
      <p class="card__body">Indexed parameters are decoded per-type from their topic word. Non-indexed parameters come out of <code>data</code> via the standard ABI decoder. Addresses end up checksummed; integers end up as decimal strings.</p>
    </div>
    <div class="card">
      <h3 class="card__title">Audit trail</h3>
      <p class="card__body"><code>abi_manifest.json</code> records every loaded ABI, every known topic0, and match/unmatched counts per event — so every decode decision is defensible in a report.</p>
    </div>
  </div>

  <pre>decoder resolves each log:

  topic0 = log.topic0
  event  = index[topic0]
  if event:
    for i in indexed_inputs:
      decoded[i.name] = decode_word(topics[i+1], i.type)
    for v, t in zip(decode_data(log.data, non_indexed_types), non_indexed):
      decoded[t.name] = v
    emit { ...log, event_name, event_signature, decoded }
  else:
    emit { ...log, decoded: null }
    append to unmatched.ndjson</pre>
</section>

<section class="section section--dark" id="install">
  <div class="section__inner">
    <div class="section__eyebrow">Get started</div>
    <h2 class="section__title">Install in a minute.</h2>
    <p class="section__body">Python 3.11+. Install in a virtualenv. Three console scripts appear in your shell: <code>evm-extract</code>, <code>evm-normalise</code>, <code>evm-decode</code>.</p>

    <pre>git clone https://github.com/&lt;you&gt;/evm-log-extractor.git
cd evm-log-extractor
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

evm-extract --help</pre>
  </div>
</section>

<footer>
  Built for on-chain forensics. <a href="https://github.com/" style="color:inherit;text-decoration:underline;">Source on GitHub</a>.
</footer>

</body>
</html>
```

- [ ] **Step 3: Verify page renders (local preview)**

Run: `python -m http.server --directory docs 8080`
Open in a browser: `http://localhost:8080/`
Expected: black hero, light sections, pill CTA, pipeline cards, dark code blocks. Kill the server with Ctrl-C.

- [ ] **Step 4: Commit**

```bash
git add docs/index.html docs/styles.css
git commit -m "docs: Apple-styled static docs page with pipeline and decode explainer"
```

---

## Task 17: Initial GitHub push

**Files:** (repo metadata only)

- [ ] **Step 1: Verify git identity is set**

Run:
```bash
git config user.name
git config user.email
```
Expected: both non-empty. If either is missing, set them:
```bash
git config user.name "Your Name"
git config user.email "you@example.com"
```

- [ ] **Step 2: Verify `gh` CLI is authenticated**

Run: `gh auth status`
Expected: `Logged in to github.com as <user>`. If not, run `gh auth login` interactively outside Claude Code.

- [ ] **Step 3: Run full test suite one last time**

Run: `pytest -v`
Expected: all tests PASS. No open work remaining.

- [ ] **Step 4: Create remote repo and push**

Run:
```bash
gh repo create evm-log-extractor \
  --public \
  --source . \
  --description "Forensics-grade EVM log extractor, normaliser, and decoder for Anvil/Foundry and any EVM JSON-RPC endpoint." \
  --push
```
Expected: `✓ Created repository <user>/evm-log-extractor on GitHub` and push output.

- [ ] **Step 5: Verify default branch and remote**

Run: `git remote -v && git log --oneline -10`
Expected: `origin` points at the new repo; last ~15 commits present.

- [ ] **Step 6: Open the repo in a browser (optional)**

Run: `gh repo view --web`

---

## Self-Review

Checklist run against the spec (`raw-log-schema.md`) and user requirements:

**Spec coverage (tier-1 v1):**
- ✅ blocks entity — Task 6
- ✅ transactions entity — Task 7
- ✅ receipts entity — Task 8
- ✅ event_logs entity — Task 9
- ✅ call_traces entity with tree flatten — Task 10
- ✅ Manifest with fork detection — Task 5
- ✅ EIP-55 + lowercase hex + wei str — Task 2
- ✅ NDJSON with sha256 — Task 3
- ✅ Extract / normalise / decode CLIs — Tasks 11, 12, 14
- ✅ ABI loader (Foundry / Hardhat / raw) — Task 13
- ✅ Decode with unmatched passthrough + manifest — Task 14
- ✅ Cross-file validation (logs_count, block references) — Task 12

**Explicitly deferred (v2):**
- state_diffs and storage_diffs entities — mentioned in schema, not in v1 scope. Adding them in v2 is a copy of Task 10's pattern (new extractor + test + CLI wiring).
- `contracts.ndjson` optional tier-2 entity.
- 4byte.directory / Etherscan fallback decode modes.
- Call-trace decode (decode function selectors in frames).

**User requirements:**
- ✅ Tool-only, no simulation harness — sim lives in separate repo.
- ✅ Anvil-specific awareness (`anvil_nodeInfo`, fork fields).
- ✅ Modular: three CLIs that can run independently or in sequence.
- ✅ Per-run output folder layout.
- ✅ README explains decoding.
- ✅ Apple-styled docs page.
- ✅ Push to GitHub as `evm-log-extractor`.

**Placeholder scan:** no TBDs, no "TODO" in the plan, no "similar to Task N" — each task repeats its code. Pass.

**Type consistency:** `NdjsonWriter` API (`.write`, `.count`, `.sha256`) is identical across tasks. `RpcClient` method names match between rpc tests and extractor usage. `AbiIndex.lookup_event` / `.lookup_function` consistent across abi_loader and decoder tasks. `Manifest.build_run_id` signature identical between manifest tests and CLI usage.

Plan passes self-review.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-22-evm-log-extractor.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
