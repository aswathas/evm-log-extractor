# evm-log-extractor

Forensics-grade EVM log extractor, normaliser, and decoder for Anvil/Foundry and any EVM JSON-RPC endpoint.

This tool produces flat NDJSON files (one JSON object per line) with:
- checksummed addresses (EIP-55)
- lowercase `0x` hex
- wei values as **decimal strings** (never JSON numbers)

## Pipeline (3 stages)

1. `evm-extract`: RPC-bound, ABI-free. Writes `raw/*.ndjson` + `manifest.json`.
2. `evm-normalise`: deterministic validation + dedup. Writes `norm/*.ndjson`.
3. `evm-decode`: ABI-dependent replay. Reads `norm/event_logs.ndjson`, writes decoded NDJSON.

Tier-1 entities (block-range mode): `blocks,transactions,receipts,event_logs,call_traces`  
Tier-2 entities (tx-only mode): `state_diffs,storage_diffs`

## Install (dev)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

You should now have: `evm-extract`, `evm-normalise`, `evm-decode`.

## Quickstart: Local Anvil Demo (recommended)

If you have Foundry installed (`anvil`, `forge`, `cast`), run:

```bash
./scripts/anvil_demo.sh
```

It will:
- start Anvil on a local port
- deploy and call a demo contract that emits an event and mutates storage
- extract tier-1 logs over the block range and decode event logs using the Foundry build artifacts
- extract tier-2 `state_diffs` / `storage_diffs` (and `call_traces`) for the specific tx hash

See `docs/anvil-demo.md` for a step-by-step manual walkthrough.

## Manual Usage

### Extract (block range)

```bash
evm-extract \
  --rpc http://127.0.0.1:8545 \
  --from-block 0 --to-block latest \
  --entities blocks,transactions,receipts,event_logs,call_traces \
  --base-dir output \
  --label anvil-range
```

### Normalise

```bash
evm-normalise --in-dir output/<run_id>
```

### Decode (Foundry project ABIs)

```bash
evm-decode \
  --input output/<run_id>/norm/event_logs.ndjson \
  --out output/<run_id>/decoded/event_logs.ndjson \
  --foundry-project /path/to/foundry/project
```

### Extract Tier-2 Diffs (single tx)

```bash
evm-extract \
  --rpc http://127.0.0.1:8545 \
  --tx 0xYOUR_TX_HASH \
  --entities call_traces,state_diffs,storage_diffs \
  --base-dir output \
  --label anvil-diffs
```

Then:

```bash
evm-normalise --in-dir output/<run_id>
```

## Output Layout

```
output/<run_id>/
  manifest.json
  raw/
    blocks.ndjson
    transactions.ndjson
    receipts.ndjson
    event_logs.ndjson
    call_traces.ndjson
    state_diffs.ndjson          # only when requested (tx-only)
    storage_diffs.ndjson        # only when requested (tx-only)
  norm/
    ...
  decoded/
    event_logs.ndjson
    unmatched.ndjson
    abi_manifest.json
```

## Schemas

Canonical per-entity schemas and invariants live in `raw-log-schema.md`.
