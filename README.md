# evm-log-extractor

Forensics-grade EVM log extractor, normaliser, and decoder for Anvil/Foundry and any EVM JSON-RPC endpoint.

Output is flat NDJSON files (one JSON object per line) with:
- checksummed addresses (EIP-55)
- lowercase `0x` hex
- wei values as **decimal strings** (never JSON numbers — they lose precision past 2^53)

No database, no streaming, no indexing. Every run is a folder of NDJSON plus a manifest.

## Pipeline (3 stages)

| Stage | Command | Reads | Writes | Properties |
|---|---|---|---|---|
| 1. Extract | `evm-extract` | JSON-RPC | `raw/*.ndjson` + `manifest.json` | RPC-bound, ABI-free, run once |
| 2. Normalise | `evm-normalise` | `raw/` | `norm/*.ndjson` | deterministic, ABI-free, safe to rerun |
| 3. Decode | `evm-decode` | `norm/event_logs.ndjson` + ABIs | `decoded/event_logs.ndjson` | ABI-dependent, replayable without RPC |

The split is deliberate: clients deliver ABIs late, wrong, or partial, so decoding must be re-runnable against the normalised logs without re-hitting RPC.

Entities — tier 1 (block-range mode):
`blocks`, `transactions`, `receipts`, `event_logs`, `call_traces`

Entities — tier 2 (single-tx mode only):
`state_diffs`, `storage_diffs`

Join keys: `block_number` joins to `blocks`; `tx_hash` joins to `receipts`, `event_logs`, `call_traces`, `state_diffs`, `storage_diffs`.

## Requirements

- Python >= 3.11
- A JSON-RPC endpoint. Defaults to `http://127.0.0.1:8545` (Anvil).

The endpoint must serve these methods:

| Method | Needed for |
|---|---|
| `eth_chainId`, `eth_blockNumber` | every run (manifest, `latest` resolution) |
| `eth_getBlockByNumber` | `blocks`, `transactions`, `receipts`, `call_traces` |
| `eth_getTransactionReceipt` | `receipts`, `call_traces` |
| `eth_getLogs` | `event_logs` |
| `debug_traceTransaction` with `tracer: "callTracer"` | `call_traces` |
| `debug_traceTransaction` with `tracer: "prestateTracer"`, `tracerConfig: {diffMode: true}` | `state_diffs`, `storage_diffs` |
| `anvil_nodeInfo` | optional — fills in `rpc.client` / fork info in the manifest; ignored if unsupported |

The two `debug_traceTransaction` tracers are non-standard debug RPC. Public endpoints usually disable them; tier-1 `event_logs` extraction works on a plain endpoint, `call_traces` and the tier-2 diffs generally do not. Anvil supports all of them.

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

That installs four runtime deps (`web3`, `eth-abi`, `eth-utils`, `click`) and puts three commands on your PATH:
`evm-extract`, `evm-normalise`, `evm-decode`.

For tests only:

```bash
pytest
```

## Quickstart: local Anvil demo

With Foundry installed (`anvil`, `forge`, `cast`):

```bash
./scripts/anvil_demo.sh
```

The script starts Anvil on `127.0.0.1:9545`, deploys `examples/foundry-demo/src/Counter.sol`, calls `inc()`, then runs the full pipeline over the resulting block range and for the `inc()` transaction hash. Output goes to `./output/<run_id>`.

Environment overrides: `RPC_HOST`, `RPC_PORT`, `OUT_BASE`, `DEMO_PRIVATE_KEY`, and `EVM_EXTRACT_BIN` / `EVM_NORMALISE_BIN` / `EVM_DECODE_BIN` (defaults to `.venv/bin/*` if present, otherwise `PATH`). See `docs/anvil-demo.md` for a manual walkthrough.

## Manual usage

### Extract — block range (tier 1)

```bash
evm-extract \
  --rpc http://127.0.0.1:8545 \
  --from-block 0 --to-block latest \
  --entities blocks,transactions,receipts,event_logs,call_traces \
  --base-dir output \
  --label anvil-range
```

`--from-block` / `--to-block` each take an integer or `latest`. Either both, or `--tx`, must be given.

### Extract — single transaction (tier 2 diffs)

```bash
evm-extract \
  --rpc http://127.0.0.1:8545 \
  --tx 0xYOUR_TX_HASH \
  --entities call_traces,state_diffs,storage_diffs \
  --base-dir output \
  --label anvil-diffs
```

`state_diffs` and `storage_diffs` require `--tx` — they have no block-range mode.

`event_logs` is the reverse: it requires `--from-block`/`--to-block` and is rejected in `--tx` mode, because `eth_getLogs` is range-based. To get the logs of one transaction, extract its block range and filter on `tx_hash` afterwards.

Other `evm-extract` flags: `--address <addr>` filters `event_logs` by emitter.

### Normalise

```bash
evm-normalise --in-dir output/<run_id>
```

or `evm-normalise --base-dir output --run <run_id>`. It copies each `raw/*.ndjson` to `norm/`, rejects duplicate primary keys, and runs two cross-entity checks — receipt `logs_count` must match the number of `event_logs` for that tx, and every `transactions` row must reference a `blocks` row that exists. A failure exits non-zero with the offending tx hash.

### Decode

```bash
evm-decode \
  --input output/<run_id>/norm/event_logs.ndjson \
  --out output/<run_id>/decoded/event_logs.ndjson \
  --foundry-project /path/to/foundry/project
```

ABI sources, any combination of:

- `--abi FILE` (repeatable) — a Foundry/Hardhat artifact with an `.abi` key, or a raw JSON array
- `--abi-dir DIR` (repeatable) — a directory of the above
- `--foundry-project DIR` — a Foundry project; walks `out/` for artifacts

Optional: `--unmatched PATH` and `--manifest PATH` (default: `unmatched.ndjson` and `abi_manifest.json` beside `--out`).

Decoding is a pure replay — it never calls RPC.

## Output layout

```
output/<run_id>/
  manifest.json
  raw/
    blocks.ndjson
    transactions.ndjson
    receipts.ndjson
    event_logs.ndjson
    call_traces.ndjson
    state_diffs.ndjson          # tier 2, only with --tx
    storage_diffs.ndjson        # tier 2, only with --tx
  norm/
    ...same set...
  decoded/
    event_logs.ndjson
    unmatched.ndjson
    abi_manifest.json
```

`<run_id>` is `<ISO-timestamp>__<label>` (or `__blk-<from>-<to>` with no label). `manifest.json` records `run_id`, `tool_version`, `created_at`, the `rpc` block (`url`, `chain_id`, `client`, fork info where available), the `cli_args` used, per-entity `counts`, and a `sha256:` of every raw NDJSON file.

## Record formats

One JSON object per line. Fields below are exactly what the extractors emit.

**`blocks.ndjson`** — `block_number`, `block_hash`, `parent_hash`, `timestamp`, `miner`, `gas_limit`, `gas_used`, `base_fee_per_gas` (string), `transaction_count`, `size`, `state_root`, `transactions_root`, `receipts_root`, `sha3_uncles`, `logs_bloom`, `extra_data`, `nonce`, `mix_hash`, `difficulty` (string), `total_difficulty` (string), `withdrawals_root`.

**`transactions.ndjson`** — `block_number`, `block_hash`, `tx_hash`, `tx_index`, `tx_type`, `chain_id`, `from_address`, `to_address`, `value` (string), `input`, `function_selector`, `nonce`, `gas_limit`, `gas_price`, `max_fee_per_gas`, `max_priority_fee_per_gas` (all strings), `access_list`, `v`, `r`, `s`, `y_parity`.

**`receipts.ndjson`** — `block_number`, `block_hash`, `tx_hash`, `tx_index`, `tx_type`, `from_address`, `to_address`, `status`, `gas_used`, `cumulative_gas_used`, `effective_gas_price` (string), `contract_address`, `logs_bloom`, `logs_count`.

**`event_logs.ndjson`** — `block_number`, `block_hash`, `tx_hash`, `tx_index`, `log_index`, `address`, `topic0`–`topic3` (padded with `null`), `topics_count`, `data`, `removed`.

**`call_traces.ndjson`** — one row per call frame, flattened from the nested `callTracer` tree. `trace_address` is `"root"` for the top frame, then `"0"`, `"0.1"`, `"0.1.2"`…; `depth` is the dot count + 1 (root = 0). Also `block_number`, `tx_hash`, `call_type`, `from_address`, `to_address`, `value` (string), `input`, `function_selector`, `output`, `gas_provided`, `gas_used`, `error`, `revert_reason`.

**`state_diffs.ndjson`** — per address touched by the tx. `block_number`, `tx_hash`, `address`, `balance_before`, `balance_after`, `balance_delta` (signed decimal strings), `nonce_before`, `nonce_after`, `code_changed`.

**`storage_diffs.ndjson`** — one row per (address, slot) touched by the tx. `block_number`, `tx_hash`, `address`, `slot`, `value_before`, `value_after` (both 32-byte-padded lowercase hex).

**`decoded/event_logs.ndjson`** — every input row plus `event_name`, `event_signature` (`Name(type,...)`), and `decoded` (object of parameter name → value). Decoded addresses are checksummed; uints/ints become decimal strings; bytes become `0x` hex. Unmatched rows are passed through with `event_name`, `event_signature`, and `decoded` all `null` — nothing is dropped — and are copied to `unmatched.ndjson`.

## Schemas

Canonical per-entity field schemas and invariants: `raw-log-schema.md`.
Design rationale: `DESIGN.md`.
Test suite: `tests/` (`pytest`).

## License

MIT.