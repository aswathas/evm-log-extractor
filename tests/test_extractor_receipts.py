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
        "cumulativeGasUsed": "0xb312d",
        "effectiveGasPrice": "0x7794f2100",
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
    assert r["contract_address"] == "0xBeEF020000000000000000000000000000000002"
    assert r["logs_count"] == 0
