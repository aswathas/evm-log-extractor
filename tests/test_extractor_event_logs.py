from unittest.mock import MagicMock

from evm_log_extractor.extractors.event_logs import extract_event_logs


def test_extract_event_logs_transfer():
    rpc = MagicMock()
    rpc.get_logs.return_value = [
        {
            "blockNumber": "0x11a0adb",
            "blockHash": "0xabc",
            "transactionHash": "0xdea" + "00" * 29 + "ff",
            "transactionIndex": "0x7",
            "logIndex": "0x17",
            "address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            "topics": [
                "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef",
                "0x000000000000000000000000abcd00000000000000000000000000000000dead",
                "0x000000000000000000000000beef020000000000000000000000000000000002",
            ],
            "data": "0x00000000000000000000000000000000000000000000000000000000000003e8",
            "removed": False,
        }
    ]
    records = list(extract_event_logs(rpc, from_block=0, to_block=18_500_123))
    assert len(records) == 1
    r = records[0]
    assert r["log_index"] == 23
    assert r["address"] == "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
    assert r["topic0"] == "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
    assert r["topic1"] == "0x000000000000000000000000abcd00000000000000000000000000000000dead"
    assert r["topic2"] == "0x000000000000000000000000beef020000000000000000000000000000000002"
    assert r["topic3"] is None
    assert r["topics_count"] == 3
    assert r["data"] == "0x00000000000000000000000000000000000000000000000000000000000003e8"
    assert r["removed"] is False


def test_extract_event_logs_anonymous_no_topic0():
    rpc = MagicMock()
    rpc.get_logs.return_value = [
        {
            "blockNumber": "0x1",
            "blockHash": "0xabc",
            "transactionHash": "0xdead" + "00" * 28,
            "transactionIndex": "0x0",
            "logIndex": "0x0",
            "address": "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
            "topics": [],
            "data": "0x1234",
            "removed": False,
        }
    ]
    r = next(extract_event_logs(rpc, 0, 1))
    assert r["topic0"] is None
    assert r["topics_count"] == 0


def test_extract_event_logs_passes_address_filter():
    rpc = MagicMock()
    rpc.get_logs.return_value = []
    list(extract_event_logs(rpc, 0, 100, address="0xABCD00000000000000000000000000000000DEAD"))
    rpc.get_logs.assert_called_once_with(
        from_block=0,
        to_block=100,
        address="0xABCD00000000000000000000000000000000DEAD",
        topics=None,
    )
