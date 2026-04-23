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
    assert tx["from_address"] == "0xabcd00000000000000000000000000000000DEAD"
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
        "transactions": [
            {
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
            }
        ],
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
        "transactions": [
            {
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
            }
        ],
    }
    rpc = MagicMock()
    rpc.get_block.return_value = block_full
    tx = next(extract_transactions(rpc, 1))
    assert tx["function_selector"] is None
    assert tx["gas_price"] == "1"
    assert tx["max_fee_per_gas"] is None
