from unittest.mock import MagicMock

from evm_log_extractor.extractors.storage_diffs import extract_storage_diffs


def test_extract_storage_diffs_shapes_records(load_fixture):
    rpc = MagicMock()
    rpc.get_receipt.return_value = {"blockNumber": "0x1"}
    rpc.debug_trace_transaction.return_value = load_fixture("prestate_diff.json")

    tx_hash = "0xdea" + "00" * 29 + "ff"
    recs = list(extract_storage_diffs(rpc, tx_hash))
    assert len(recs) == 1
    r = recs[0]
    assert r["block_number"] == 1
    assert r["tx_hash"] == tx_hash
    assert r["address"] == "0xBeEF020000000000000000000000000000000002"
    assert r["slot"] == "0x" + "00" * 31 + "02"
    assert r["value_before"] == "0x" + "00" * 31 + "01"
    assert r["value_after"] == "0x" + "00" * 31 + "02"

