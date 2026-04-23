# EVM Forensics Log Extractor — Project Meta Prompt

## What We Are Building

A **forensics-grade EVM log extraction and normalisation tool** for investigating smart contract exploits, protocol attacks, and on-chain activity. The primary node target is **Anvil** (Foundry's local EVM node), but the tool must work against any EVM-compatible JSON-RPC endpoint (mainnet forks, testnets, live nodes).

---

## Architecture: 3-Stage Pipeline

```
[EXTRACT]  →  raw NDJSON       (ABI-free, hits the RPC once, store forever)
[NORMALISE] → norm NDJSON      (ABI-free, consistent shape, source of truth)
[DECODE]   →  decoded NDJSON   (ABI-dependent, re-runnable against norm NDJSON)
```

Each stage is a separate Python CLI script. Each stage outputs **NDJSON** (one JSON object per line, newline-delimited). Stages are composable via Unix pipes or run independently.

**Why separate stages:**
- Extract is slow (RPC calls). Do it once, never again.
- Normalise is deterministic and ABI-free. Always safe to rerun.
- Decode requires the client's ABI. Client gives ABI late, or wrong, or partial. Re-decode without re-extracting.

---

## Output Format: NDJSON

- One JSON object per line
- All files: `.ndjson` extension
- Newline `\n` after every record
- No trailing comma, no array wrapper

---

## 7 Raw Entities

### Tier 1 — Always Pull

| File | RPC Method | Primary Key |
|---|---|---|
| `blocks.ndjson` | `eth_getBlockByNumber` | `block_number` |
| `transactions.ndjson` | `eth_getBlockByNumber` (fullTx=true) | `tx_hash` |
| `receipts.ndjson` | `eth_getTransactionReceipt` | `tx_hash` |
| `event_logs.ndjson` | `eth_getLogs` | `(tx_hash, log_index)` |
| `call_traces.ndjson` | `debug_traceTransaction` (callTracer) | `(tx_hash, trace_address)` |

### Tier 2 — On Demand

| File | RPC Method | Primary Key |
|---|---|---|
| `state_diffs.ndjson` | `debug_traceTransaction` (prestateTracer diffMode=true) | `(tx_hash, address)` |
| `storage_diffs.ndjson` | `debug_traceTransaction` (prestateTracer diffMode=true) | `(tx_hash, address, slot)` |

**Join keys across all entities:**
- `block_number` → joins everything to `blocks`
- `tx_hash` → joins receipts, event_logs, call_traces, state_diffs, storage_diffs to transactions

---

## Complete Field Schemas

### blocks.ndjson

| Field | Type | Source | Notes |
|---|---|---|---|
| block_number | int | block | PK |
| block_hash | hex | block | 32 bytes |
| parent_hash | hex | block | |
| timestamp | int | block | unix epoch seconds |
| miner | addr | block | block producer / fee recipient |
| gas_limit | int | block | |
| gas_used | int | block | total across all txs |
| base_fee_per_gas | str | block | wei str; null pre-EIP-1559 |
| transaction_count | int | derived | len(transactions array) |
| size | int | block | block size in bytes |
| state_root | hex | block | post-block state trie root |
| transactions_root | hex | block | tx trie root |
| receipts_root | hex | block | receipts trie root |
| sha3_uncles | hex | block | 0x1dcc4d… if no uncles |
| logs_bloom | hex | block | 256-byte bloom filter of all logs |
| extra_data | hex | block | arbitrary miner data ≤32 bytes |
| nonce | hex | block | PoW 8-byte nonce; 0x0 post-Merge |
| mix_hash | hex | block | PoW mix hash; prevRandao post-Merge |
| difficulty | str | block | 0 post-Merge |
| total_difficulty | str | block | cumulative chain difficulty |
| withdrawals_root | hex | block | EIP-4895; null pre-Shanghai |

### transactions.ndjson

| Field | Type | Source | Notes |
|---|---|---|---|
| block_number | int | block | FK → blocks |
| block_hash | hex | block | |
| tx_hash | hex | tx | PK |
| tx_index | int | tx | position in block |
| tx_type | int | tx | 0=legacy 1=EIP-2930 2=EIP-1559 |
| chain_id | int | tx | EIP-155; null for pre-EIP-155 txs |
| from_address | addr | tx | checksummed |
| to_address | addr | tx | null → contract creation |
| value | str | tx | ETH sent, wei as string |
| input | hex | tx | full calldata |
| function_selector | hex | derived | input[0:4]; null if input < 4 bytes |
| nonce | int | tx | |
| gas_limit | int | tx | |
| gas_price | str | tx | wei str; type 0 only |
| max_fee_per_gas | str | tx | wei str; type 2 only |
| max_priority_fee_per_gas | str | tx | wei str; type 2 only |
| access_list | json | tx | [{address, storageKeys[]}]; type 1 & 2 |
| v | str | tx | ECDSA recovery value; legacy: 27/28 or chainId×2+35/36 |
| r | hex | tx | 32-byte ECDSA R component |
| s | hex | tx | 32-byte ECDSA S component |
| y_parity | int | tx | 0 or 1; type 1 & 2 only (replaces v) |

### receipts.ndjson

| Field | Type | Source | Notes |
|---|---|---|---|
| block_number | int | block | FK → blocks |
| block_hash | hex | block | |
| tx_hash | hex | receipt | PK, FK → transactions |
| tx_index | int | receipt | |
| tx_type | int | receipt | echoed from tx |
| from_address | addr | receipt | echoed by receipt RPC |
| to_address | addr | receipt | echoed by receipt RPC |
| status | int | receipt | 1=success 0=revert |
| gas_used | int | receipt | this tx only |
| cumulative_gas_used | int | receipt | all txs up to this one in block |
| effective_gas_price | str | receipt | actual price paid, wei str |
| contract_address | addr | receipt | deployed contract; null if not creation |
| logs_bloom | hex | receipt | 256-byte bloom filter for this tx's logs |
| logs_count | int | derived | len(logs in receipt); sanity check vs event_logs |

### event_logs.ndjson

| Field | Type | Source | Notes |
|---|---|---|---|
| block_number | int | block | FK → blocks |
| block_hash | hex | block | |
| tx_hash | hex | log | FK → transactions |
| tx_index | int | log | |
| log_index | int | log | PK; unique within block |
| address | addr | log | contract that emitted; checksummed |
| topic0 | hex | log | keccak256(event signature) |
| topic1 | hex | log | 1st indexed param; null if absent |
| topic2 | hex | log | 2nd indexed param; null if absent |
| topic3 | hex | log | 3rd indexed param; null if absent |
| topics_count | int | derived | 1–4 |
| data | hex | log | ABI-encoded non-indexed params |
| removed | bool | log | true if orphaned by reorg |

### call_traces.ndjson

| Field | Type | Source | Notes |
|---|---|---|---|
| block_number | int | block | FK → blocks |
| tx_hash | hex | tracer | FK → transactions |
| trace_address | str | tracer | PK per tx; "root" / "0" / "0.1" / "0.1.2" |
| depth | int | derived | 0 = top-level call |
| call_type | str | tracer | CALL STATICCALL DELEGATECALL CREATE CREATE2 SELFDESTRUCT |
| from_address | addr | tracer | |
| to_address | addr | tracer | null for CREATE before address known |
| value | str | tracer | ETH transferred in this frame, wei str |
| input | hex | tracer | calldata for this frame |
| function_selector | hex | derived | input[0:4]; null if empty |
| output | hex | tracer | return data |
| gas_provided | int | tracer | |
| gas_used | int | tracer | |
| error | str | tracer | "execution reverted" / "out of gas" / null |
| revert_reason | hex | tracer | raw ABI-encoded revert data; decode in decode pass |

### state_diffs.ndjson

| Field | Type | Source | Notes |
|---|---|---|---|
| block_number | int | block | FK → blocks |
| tx_hash | hex | tracer | FK → transactions |
| address | addr | tracer | PK per tx; EOA or contract |
| balance_before | str | tracer | wei str |
| balance_after | str | tracer | wei str |
| balance_delta | str | derived | signed wei str (after − before) |
| nonce_before | int | tracer | |
| nonce_after | int | tracer | |
| code_changed | bool | tracer | true if bytecode deployed or changed |

### storage_diffs.ndjson

| Field | Type | Source | Notes |
|---|---|---|---|
| block_number | int | block | FK → blocks |
| tx_hash | hex | tracer | FK → transactions |
| address | addr | tracer | contract whose storage changed |
| slot | hex | tracer | PK per tx+address; 32-byte storage key |
| value_before | hex | tracer | 32-byte previous value |
| value_after | hex | tracer | 32-byte new value |

---

## Critical Implementation Rules

### Data Types
- **All wei values are strings** — `value`, `balance_*`, `gas_price`, `max_fee_per_gas`, `effective_gas_price`, `balance_delta` etc. JSON numbers lose precision above 2^53. Always store as decimal strings.
- **All addresses are checksummed** — EIP-55 checksum via `Web3.to_checksum_address()`
- **All hex values are lowercase** — `0x` prefix, lowercase hex digits
- **Derived fields are clearly marked** — computed at normalisation time, not raw from RPC

### Extraction Inputs
The extractor must accept any combination of:
- `--address <addr>` — filter by contract address
- `--tx <hash>` — single transaction
- `--from-block <n>` — start block (int or "latest")
- `--to-block <n>` — end block (int or "latest")
- `--rpc <url>` — RPC endpoint (default: `http://127.0.0.1:8545`)
- `--entities blocks,transactions,receipts,event_logs,call_traces` — which entities to pull

### call_traces Tree Flattening
`debug_traceTransaction` with `callTracer` returns a **nested tree**. We flatten it to one record per call frame:
- `trace_address` encodes position: root call = `"root"`, first child = `"0"`, second child of first child = `"0.1"` etc.
- `depth` is derived from `trace_address` depth (number of dots + 1, or 0 for root)

### State/Storage Diffs RPC
Use `debug_traceTransaction` with `prestateTracer` and `diffMode: true`. This returns a `{pre: {...}, post: {...}}` object. Delta is computed as `post - pre`.

### Normalisation Pass
After extraction, the normaliser:
1. Checksums all addresses
2. Lowercases all hex
3. Converts hex ints to Python ints where appropriate
4. Computes derived fields (`function_selector`, `topics_count`, `depth`, `balance_delta`, `transaction_count`, `logs_count`)
5. Validates `logs_count` in receipts matches actual event_logs count for that tx

### Decode Pass (Separate, ABI-Dependent)
Input: `event_logs.ndjson` + one or more ABI files
Output: `decoded_event_logs.ndjson` — all normalised fields plus:
- `event_name` — e.g. "Transfer"
- `event_signature` — e.g. "Transfer(address,address,uint256)"
- `decoded` — dict of `{param_name: value}` for all params

Logs without a matching ABI pass through with `decoded: null`.

ABI files accepted: Foundry/Hardhat artifact format (has `.abi` key) or raw JSON array.

---

## Tech Stack

- **Python 3.11+**
- **web3.py ≥ 6.0** — RPC calls, address checksumming
- **eth-abi ≥ 4.0** — ABI decoding in decode pass
- **eth-utils ≥ 2.0** — event selector computation
- **click** — CLI argument parsing
- Output: NDJSON to stdout or `--out <file>`

---

## File Structure

```
evm-forensics/
├── extractor.py        # Pulls raw data from Anvil RPC
├── normaliser.py       # Normalises raw NDJSON, computes derived fields
├── decoder.py          # ABI-based decode of event_logs.ndjson
├── requirements.txt
└── README.md
```

---

## Typical Forensics Workflow

```bash
# 1. Extract all tier-1 entities for a block range
python extractor.py \
  --from-block 100 --to-block 200 \
  --entities blocks,transactions,receipts,event_logs,call_traces \
  --out-dir ./raw/

# 2. Normalise (adds checksums, derived fields, timestamps)
python normaliser.py --in-dir ./raw/ --out-dir ./norm/

# 3. Client gives ABI — decode event logs
python decoder.py \
  --input ./norm/event_logs.ndjson \
  --abi ./Token.json \
  --abi ./Vault.json \
  --out ./decoded_events.ndjson

# 4. Pull tier-2 on demand for suspicious txs
python extractor.py \
  --tx 0xABC... \
  --entities state_diffs,storage_diffs \
  --out-dir ./raw/
```

---

## What NOT to Build (Out of Scope)

- Token metadata (ERC20 symbol/decimals lookup)
- Contract bytecode analysis
- Derived `token_transfers` table (ethereum-etl does this; we decode from event_logs instead)
- Any blockchain indexing / streaming / live monitoring
- Database ingestion (output is flat NDJSON files only)
