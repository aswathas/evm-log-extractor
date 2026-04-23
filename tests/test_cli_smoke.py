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
            "number": hex(i),
            "hash": f"0x{i:064x}",
            "parentHash": "0x" + "00" * 32,
            "timestamp": "0x1",
            "miner": "0x0000000000000000000000000000000000000000",
            "gasLimit": "0x1",
            "gasUsed": "0x0",
            "baseFeePerGas": None,
            "size": "0x1",
            "stateRoot": "0x" + "00" * 32,
            "transactionsRoot": "0x" + "00" * 32,
            "receiptsRoot": "0x" + "00" * 32,
            "sha3Uncles": "0x" + "00" * 32,
            "logsBloom": "0x" + "00" * 256,
            "extraData": "0x",
            "nonce": "0x" + "00" * 8,
            "mixHash": "0x" + "00" * 32,
            "difficulty": "0x0",
            "totalDifficulty": "0x0",
            "withdrawalsRoot": None,
            "transactions": [],
        }
        for i in range(3)
    ]

    runner = CliRunner()
    result = runner.invoke(
        extract_main,
        [
            "--rpc",
            "http://127.0.0.1:8545",
            "--from-block",
            "0",
            "--to-block",
            "2",
            "--entities",
            "blocks",
            "--base-dir",
            str(tmp_path),
            "--label",
            "smoke",
        ],
    )
    assert result.exit_code == 0, result.output

    run_dirs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    blocks = (run_dir / "raw" / "blocks.ndjson").read_text().strip().split("\n")
    assert len(blocks) == 3

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["counts"]["blocks"] == 3
    assert "raw/blocks.ndjson" in manifest["hashes"]
    assert manifest["rpc"]["chain_id"] == 31337

