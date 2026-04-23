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
    m.set_node_info(
        {
            "forkConfig": {"forkUrl": "https://eth.example", "forkBlockNumber": "0x1117f10"},
            "clientVersion": "anvil",
        }
    )
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
