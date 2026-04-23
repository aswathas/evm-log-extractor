import json
from pathlib import Path

import pytest

from evm_log_extractor.abi_loader import load_abi_sources


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
    nested = tmp_path / "out" / "ERC20.sol"
    nested.mkdir(parents=True)
    (nested / "ERC20.json").write_text((fixtures_dir / "erc20_abi.json").read_text())
    idx = load_abi_sources(abi_dirs=[tmp_path / "out"])
    assert idx.lookup_function("0xa9059cbb")["name"] == "transfer"


def test_missing_source_raises():
    with pytest.raises(ValueError, match="no ABI"):
        load_abi_sources()

