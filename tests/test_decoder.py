import json
from pathlib import Path

from evm_log_extractor.abi_loader import load_abi_sources
from evm_log_extractor.decoder import decode_event_logs


def _sample_transfer_log() -> dict:
    return {
        "block_number": 1,
        "block_hash": "0x" + "ab" * 32,
        "tx_hash": "0x" + "de" * 32,
        "tx_index": 0,
        "log_index": 0,
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
    assert rec["decoded"]["from"] == "0xabcd00000000000000000000000000000000DEAD"
    assert rec["decoded"]["to"] == "0xBeEF020000000000000000000000000000000002"


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
    passthrough = json.loads(out.read_text().strip())
    assert passthrough["decoded"] is None
