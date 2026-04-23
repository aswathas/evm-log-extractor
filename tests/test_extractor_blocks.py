from unittest.mock import MagicMock

from evm_log_extractor.extractors.blocks import extract_block


def test_extract_block_shapes_record(load_fixture):
    raw = load_fixture("block_18500123.json")
    rpc = MagicMock()
    rpc.get_block.return_value = raw

    record = extract_block(rpc, 18_500_123)

    assert record["block_number"] == 18_500_123
    assert record["block_hash"] == "0xabcdef0000000000000000000000000000000000000000000000000000000001"
    assert record["timestamp"] == 1_701_123_024
    assert record["miner"] == "0xc0ffee254729296a45a3885639AC7E10F9d54979"
    assert record["gas_limit"] == 30_000_000
    assert record["gas_used"] == 1_620_133
    assert record["base_fee_per_gas"] == "15000000000"
    assert record["transaction_count"] == 1
    assert record["withdrawals_root"] is None


def test_extract_block_handles_pre_london(load_fixture):
    raw = load_fixture("block_18500123.json")
    raw["baseFeePerGas"] = None
    rpc = MagicMock()
    rpc.get_block.return_value = raw
    record = extract_block(rpc, 18_500_123)
    assert record["base_fee_per_gas"] is None
