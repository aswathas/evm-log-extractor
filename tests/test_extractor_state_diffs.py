from unittest.mock import MagicMock

from evm_log_extractor.extractors.state_diffs import extract_state_diffs


def test_extract_state_diffs_shapes_records(load_fixture):
    rpc = MagicMock()
    rpc.get_receipt.return_value = {"blockNumber": "0x1"}
    rpc.debug_trace_transaction.return_value = load_fixture("prestate_diff.json")

    tx_hash = "0xdea" + "00" * 29 + "ff"
    recs = list(extract_state_diffs(rpc, tx_hash))
    assert len(recs) == 2

    eoa = next(r for r in recs if r["address"] == "0xabcd00000000000000000000000000000000DEAD")
    assert eoa["block_number"] == 1
    assert eoa["tx_hash"] == tx_hash
    assert eoa["balance_before"] == "1000000000000000000"
    assert eoa["balance_after"] == "0"
    assert eoa["balance_delta"] == "-1000000000000000000"
    assert eoa["nonce_before"] == 42
    assert eoa["nonce_after"] == 43
    assert eoa["code_changed"] is False


def test_extract_state_diffs_code_changed(load_fixture):
    rpc = MagicMock()
    rpc.get_receipt.return_value = {"blockNumber": "0x1"}
    rpc.debug_trace_transaction.return_value = load_fixture("prestate_diff.json")

    tx_hash = "0xdea" + "00" * 29 + "ff"
    recs = list(extract_state_diffs(rpc, tx_hash))
    contract = next(r for r in recs if r["address"] == "0xBeEF020000000000000000000000000000000002")
    assert contract["code_changed"] is True

