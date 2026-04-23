from unittest.mock import MagicMock

import pytest

from evm_log_extractor.rpc import RpcClient


@pytest.fixture
def mock_w3():
    w3 = MagicMock()
    w3.eth.chain_id = 31337
    w3.eth.block_number = 250
    return w3


def test_client_chain_id(mock_w3):
    rpc = RpcClient.from_web3(mock_w3)
    assert rpc.chain_id() == 31337


def test_client_latest_block(mock_w3):
    rpc = RpcClient.from_web3(mock_w3)
    assert rpc.latest_block() == 250


def test_get_block_returns_dict(mock_w3):
    mock_w3.eth.get_block.return_value = {"number": 100, "hash": b"\x01" * 32}
    rpc = RpcClient.from_web3(mock_w3)
    b = rpc.get_block(100, full_tx=False)
    assert b["number"] == 100


def test_get_block_by_tag(mock_w3):
    mock_w3.eth.get_block.return_value = {"number": 250}
    rpc = RpcClient.from_web3(mock_w3)
    rpc.get_block("latest", full_tx=True)
    mock_w3.eth.get_block.assert_called_once_with("latest", full_transactions=True)


def test_get_receipt(mock_w3):
    mock_w3.eth.get_transaction_receipt.return_value = {"status": 1}
    rpc = RpcClient.from_web3(mock_w3)
    assert rpc.get_receipt("0xdea")["status"] == 1


def test_get_logs(mock_w3):
    mock_w3.eth.get_logs.return_value = [{"logIndex": 0}]
    rpc = RpcClient.from_web3(mock_w3)
    assert rpc.get_logs(from_block=0, to_block=100) == [{"logIndex": 0}]


def test_debug_trace_call_tracer(mock_w3):
    mock_w3.provider.make_request.return_value = {"result": {"type": "CALL"}}
    rpc = RpcClient.from_web3(mock_w3)
    result = rpc.debug_trace_transaction("0xdea", tracer="callTracer")
    mock_w3.provider.make_request.assert_called_once_with(
        "debug_traceTransaction", ["0xdea", {"tracer": "callTracer"}]
    )
    assert result == {"type": "CALL"}


def test_debug_trace_prestate_diff(mock_w3):
    mock_w3.provider.make_request.return_value = {"result": {}}
    rpc = RpcClient.from_web3(mock_w3)
    rpc.debug_trace_transaction("0xdea", tracer="prestateTracer", tracer_config={"diffMode": True})
    mock_w3.provider.make_request.assert_called_once_with(
        "debug_traceTransaction",
        ["0xdea", {"tracer": "prestateTracer", "tracerConfig": {"diffMode": True}}],
    )


def test_anvil_node_info_success(mock_w3):
    mock_w3.provider.make_request.return_value = {"result": {"currentBlockNumber": "0xfa"}}
    rpc = RpcClient.from_web3(mock_w3)
    info = rpc.anvil_node_info()
    assert info == {"currentBlockNumber": "0xfa"}


def test_anvil_node_info_unavailable(mock_w3):
    mock_w3.provider.make_request.return_value = {"error": {"code": -32601, "message": "not found"}}
    rpc = RpcClient.from_web3(mock_w3)
    assert rpc.anvil_node_info() is None

