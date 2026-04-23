"""Thin web3.py wrapper exposing only the RPC methods the extractor needs.

Every method returns raw dict/list payloads. Conversion happens in the
extractor layer, not here.
"""

from __future__ import annotations

from typing import Any, Optional, Union

from web3 import HTTPProvider, Web3

BlockTag = Union[int, str]


class RpcClient:
    def __init__(self, w3: Web3):
        self._w3 = w3

    @classmethod
    def from_url(cls, url: str, timeout: int = 30) -> "RpcClient":
        provider = HTTPProvider(url, request_kwargs={"timeout": timeout})
        return cls(Web3(provider))

    @classmethod
    def from_web3(cls, w3: Web3) -> "RpcClient":
        return cls(w3)

    def chain_id(self) -> int:
        return self._w3.eth.chain_id

    def latest_block(self) -> int:
        return self._w3.eth.block_number

    def get_block(self, block: BlockTag, full_tx: bool = False) -> dict:
        return self._w3.eth.get_block(block, full_transactions=full_tx)

    def get_receipt(self, tx_hash: str) -> dict:
        return self._w3.eth.get_transaction_receipt(tx_hash)

    def get_logs(
        self,
        from_block: BlockTag,
        to_block: BlockTag,
        address: Optional[str] = None,
        topics: Optional[list] = None,
    ) -> list[dict]:
        f: dict[str, Any] = {"fromBlock": from_block, "toBlock": to_block}
        if address is not None:
            f["address"] = address
        if topics is not None:
            f["topics"] = topics
        return self._w3.eth.get_logs(f)

    def debug_trace_transaction(
        self,
        tx_hash: str,
        tracer: str,
        tracer_config: Optional[dict] = None,
    ) -> Any:
        params: dict[str, Any] = {"tracer": tracer}
        if tracer_config is not None:
            params["tracerConfig"] = tracer_config
        resp = self._w3.provider.make_request("debug_traceTransaction", [tx_hash, params])
        if "error" in resp:
            raise RuntimeError(f"debug_traceTransaction failed: {resp['error']}")
        return resp["result"]

    def anvil_node_info(self) -> Optional[dict]:
        resp = self._w3.provider.make_request("anvil_nodeInfo", [])
        if "error" in resp:
            return None
        return resp.get("result")

