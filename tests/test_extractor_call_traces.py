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
    tree["calls"][1]["calls"] = [
        {
            "type": "CALL",
            "from": "0x1234000000000000000000000000000000005678",
            "to": "0xbeef020000000000000000000000000000000002",
            "gas": "0x500",
            "gasUsed": "0x200",
            "input": "0x",
            "output": "0x",
        }
    ]
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
    assert records[0]["from_address"] == "0xabcd00000000000000000000000000000000DEAD"
    assert records[0]["to_address"] == "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
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
        "output": "0x60806040",
    }
    flat = list(flatten_tree(tree))
    assert flat[0]["to"] is None
    assert flat[0]["type"] == "CREATE"
