# Local Anvil Demo (End-to-End)

This walkthrough spins up a local Anvil chain, deploys a tiny demo contract, produces a few transactions, then runs:
- tier-1 extraction over a block range (`blocks,transactions,receipts,event_logs,call_traces`)
- `evm-normalise` validations
- `evm-decode` using Foundry artifacts
- tier-2 diffs for a single tx (`state_diffs,storage_diffs`) plus `call_traces`

Prereqs:
- Foundry installed: `anvil`, `forge`, `cast`
- Python venv for this repo: `pip install -e '.[dev]'`

## 1) Start Anvil

In terminal A:

```bash
anvil --port 8545
```

## 2) Build + deploy the demo contract

In terminal B:

```bash
cd examples/foundry-demo
forge build
```

Deploy:

```bash
RPC=http://127.0.0.1:8545
PK=0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80

forge create --rpc-url "$RPC" --private-key "$PK" src/Counter.sol:Counter --json > /tmp/counter_deploy.json
python -c "import json; print(json.load(open('/tmp/counter_deploy.json'))['deployedTo'])"
```

Capture the printed contract address as `COUNTER`.

## 3) Call the contract (emit an event + touch storage)

```bash
COUNTER=0x...
cast send --rpc-url "$RPC" --private-key "$PK" "$COUNTER" "inc()" --json > /tmp/counter_inc.json
python -c "import json; print(json.load(open('/tmp/counter_inc.json'))['transactionHash'])"
```

Capture that tx hash as `TX`.

## 4) Extract tier-1 logs over the block range

From repo root:

```bash
cd ../..
source .venv/bin/activate

LATEST=$(cast block-number --rpc-url "$RPC")
evm-extract --rpc "$RPC" --from-block 0 --to-block "$LATEST" \
  --entities blocks,transactions,receipts,event_logs,call_traces \
  --base-dir output --label anvil-range
```

The command prints a run directory: `output/<run_id>`.

## 5) Normalise

```bash
evm-normalise --in-dir output/<run_id>
```

## 6) Decode event logs using Foundry artifacts

```bash
evm-decode \
  --input output/<run_id>/norm/event_logs.ndjson \
  --out output/<run_id>/decoded/event_logs.ndjson \
  --foundry-project examples/foundry-demo
```

Sanity check:

```bash
rg -n '\"event_name\": \"Increment\"' output/<run_id>/decoded/event_logs.ndjson
```

## 7) Extract tier-2 diffs for the specific tx hash

```bash
TX=0x...
evm-extract --rpc "$RPC" --tx "$TX" \
  --entities call_traces,state_diffs,storage_diffs \
  --base-dir output --label anvil-diffs
```

Normalise that run too:

```bash
evm-normalise --in-dir output/<run_id>
```

Sanity checks:

```bash
head -n 5 output/<run_id>/raw/state_diffs.ndjson
head -n 5 output/<run_id>/raw/storage_diffs.ndjson
head -n 5 output/<run_id>/raw/call_traces.ndjson
```

## One-command version

From repo root:

```bash
./scripts/anvil_demo.sh
```

