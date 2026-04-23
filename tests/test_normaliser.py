import json
from pathlib import Path

import pytest

from evm_log_extractor.normaliser import ValidationError, normalise_run


def _write_raw(run_dir: Path, entity: str, records: list[dict]) -> None:
    raw = run_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    with open(raw / f"{entity}.ndjson", "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def test_normaliser_copies_and_validates(tmp_run_dir):
    _write_raw(tmp_run_dir, "blocks", [{"block_number": 1, "block_hash": "0x" + "ab" * 32}])
    _write_raw(
        tmp_run_dir,
        "transactions",
        [{"tx_hash": "0x" + "de" * 32, "block_number": 1, "block_hash": "0x" + "ab" * 32}],
    )
    _write_raw(
        tmp_run_dir,
        "receipts",
        [{"tx_hash": "0x" + "de" * 32, "block_number": 1, "block_hash": "0x" + "ab" * 32, "logs_count": 1}],
    )
    _write_raw(
        tmp_run_dir,
        "event_logs",
        [
            {
                "tx_hash": "0x" + "de" * 32,
                "log_index": 0,
                "block_number": 1,
                "block_hash": "0x" + "ab" * 32,
                "address": "0xA0b86991c6218b36c1D19D4a2e9Eb0cE3606eB48",
            }
        ],
    )

    counts = normalise_run(tmp_run_dir)
    assert counts == {"blocks": 1, "transactions": 1, "receipts": 1, "event_logs": 1}
    assert (tmp_run_dir / "norm" / "blocks.ndjson").exists()


def test_normaliser_rejects_duplicate_pk(tmp_run_dir):
    _write_raw(
        tmp_run_dir,
        "blocks",
        [
            {"block_number": 1, "block_hash": "0x" + "ab" * 32},
            {"block_number": 1, "block_hash": "0x" + "cd" * 32},
        ],
    )
    with pytest.raises(ValidationError, match="duplicate"):
        normalise_run(tmp_run_dir)


def test_normaliser_rejects_logs_count_mismatch(tmp_run_dir):
    _write_raw(tmp_run_dir, "blocks", [{"block_number": 1, "block_hash": "0x" + "ab" * 32}])
    _write_raw(
        tmp_run_dir,
        "transactions",
        [{"tx_hash": "0x" + "de" * 32, "block_number": 1, "block_hash": "0x" + "ab" * 32}],
    )
    _write_raw(
        tmp_run_dir,
        "receipts",
        [{"tx_hash": "0x" + "de" * 32, "block_number": 1, "block_hash": "0x" + "ab" * 32, "logs_count": 3}],
    )
    _write_raw(
        tmp_run_dir,
        "event_logs",
        [
            {
                "tx_hash": "0x" + "de" * 32,
                "log_index": 0,
                "block_number": 1,
                "block_hash": "0x" + "ab" * 32,
                "address": "0xA0b86991c6218b36c1D19D4a2e9Eb0cE3606eB48",
            }
        ],
    )
    with pytest.raises(ValidationError, match="logs_count"):
        normalise_run(tmp_run_dir)

