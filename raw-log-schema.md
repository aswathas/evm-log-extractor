# Raw Log Schema — EVM Forensics Meta-Prompt

**Purpose:** canonical specification for the **normalised raw log format** emitted by the EVM Forensics Log Extractor. Reuse this document as the source of truth when building any exporter, indexer, decoder, or analytics layer that consumes forensic-grade EVM data.

Scope: Anvil / Foundry local nodes as primary target. Works against any EVM-compatible JSON-RPC endpoint. 7 entity types, all emitted as NDJSON.

---

## 0. Global Rules (apply to every entity)

### 0.1 File format

- **NDJSON** — one JSON object per line, `\n` terminator, no array wrapper, no trailing commas.
- File extension: `.ndjson`.
- Encoding: UTF-8, no BOM.
- Record ordering: **ascending by primary key** (block_number, then tx_index, then log_index / trace_address).

### 0.2 Data type conventions

| Logical type | JSON representation | Why |
|---|---|---|
| `int` (block numbers, indexes, gas units, counts) | JSON number | Safe — all stay below 2^53. |
| `wei` (value, balances, gas prices, fee caps) | **decimal string** | JSON numbers lose precision above 2^53. uint256 maxes at 2^256−1. |
| `hex` (hashes, topics, calldata, bytecode) | lowercase `0x`-prefixed string | Canonicalised. Fixed width for hashes (32 bytes = 66 chars incl. `0x`). |
| `addr` (Ethereum address) | **EIP-55 checksummed** `0x`-prefixed string, 42 chars | `Web3.to_checksum_address()` applied. |
| `bool` | JSON true/false | |
| `json` (access_list, structured sub-objects) | nested JSON value | |
| `null` | JSON null | Used for absent / not-applicable fields. Never use empty string `""` or `0x` for missing data. |

### 0.3 Derived fields

Computed during the **normalisation** pass. Never pulled from the RPC. Always marked in the schema with source `derived`.

### 0.4 Run metadata

Every extractor run writes a sibling `manifest.json`. Not a log entity — see **Appendix B**.

### 0.5 Immutability

Once written, an entity record is never mutated in place. A re-run against the same `run_id` either (a) dedupes by primary key and appends only new records, or (b) fails with a conflict error (configurable). Records are never partially rewritten.

---

## 1. `blocks.ndjson`

### Purpose
One record per Ethereum block within the extraction range. Root of the join graph — every other entity references `block_number`.

### RPC source
`eth_getBlockByNumber(<block>, false)` — `false` means do not include full transactions (they come via stage 2 below).
Per block we additionally call `eth_getBlockByNumber(<block>, true)` to get full tx bodies for `transactions.ndjson`. Block metadata is taken from the `false` call (cheaper, no tx bloat).

### Primary key
`block_number`

### Join role
Parent of all other entities via `block_number`.

### Fields

| Field | Type | Nullable | Source | Meaning | Example | Edge cases |
|---|---|---|---|---|---|---|
| `block_number` | int | no | rpc | Height of the block. PK. | `18_500_123` | Zero for genesis. |
| `block_hash` | hex | no | rpc | Keccak hash of the block header. 32 bytes. | `0xabc...` | Stable identity — use for reorg detection. |
| `parent_hash` | hex | no | rpc | Block hash of the parent block. | `0xdef...` | Zero hash for genesis. |
| `timestamp` | int | no | rpc | Unix epoch seconds of block production. | `1_713_791_204` | On Anvil with default mining may be synthetic — record as-is. |
| `miner` | addr | no | rpc | Block producer / fee recipient (`coinbase`). Checksummed. | `0xC0ff...` | On Anvil often `0x0000...0000` unless `--block-base-fee-per-gas` is used with a custom coinbase. |
| `gas_limit` | int | no | rpc | Max total gas across all txs in the block. | `30_000_000` | Anvil defaults ~30M; configurable via `--gas-limit`. |
| `gas_used` | int | no | rpc | Total gas consumed by all txs in the block. | `14_712_309` | ≤ `gas_limit`. |
| `base_fee_per_gas` | wei | yes | rpc | EIP-1559 base fee per gas unit. | `"15000000000"` | `null` for pre-London blocks. |
| `transaction_count` | int | no | **derived** | Number of tx hashes in the block. | `128` | Computed from length of `transactions` array in the full block call. |
| `size` | int | no | rpc | RLP-encoded block size in bytes. | `76_512` | |
| `state_root` | hex | no | rpc | Post-block world state trie root. | `0x7af...` | 32 bytes. |
| `transactions_root` | hex | no | rpc | Root of the transactions trie. | `0x9c1...` | 32 bytes. |
| `receipts_root` | hex | no | rpc | Root of the receipts trie. | `0x2e0...` | 32 bytes. |
| `sha3_uncles` | hex | no | rpc | Keccak of the uncles list. | `0x1dcc4d...` | Constant `0x1dcc4de8dec75d7aab85b567b6ccd41ad312451b948a7413f0a142fd40d49347` when no uncles (post-Merge always). |
| `logs_bloom` | hex | no | rpc | 256-byte bloom filter over all logs in the block. | `0x000...` | 512 hex chars + `0x`. |
| `extra_data` | hex | no | rpc | Arbitrary miner-provided data (≤ 32 bytes). | `0x`… | On Anvil typically empty (`0x`). |
| `nonce` | hex | no | rpc | PoW nonce (8 bytes). | `0x0000000000000000` | Post-Merge always zero. |
| `mix_hash` | hex | no | rpc | PoW mix hash. Post-Merge: `prevRandao`. | `0x...` | 32 bytes. |
| `difficulty` | wei | no | rpc | Block difficulty. | `"0"` | Zero post-Merge. |
| `total_difficulty` | wei | yes | rpc | Cumulative chain difficulty through this block. | `"58_750_003_716_598_352_816_469"` | Some clients omit — accept null. |
| `withdrawals_root` | hex | yes | rpc | Post-Shanghai beacon withdrawal trie root. | `0x...` | `null` for pre-Shanghai blocks. |

### Forensic use
- Establishes timeline (`timestamp`).
- Anchors every other entity via `block_number` join.
- `gas_used` vs `gas_limit` ratio — signals congested / attacker-filled blocks.
- `base_fee_per_gas` trend — MEV / fee spike detection.

### Anvil notes
- Default mining mode (instant) produces a block per transaction. Timestamps may be identical across blocks if txs are mined in the same second.
- `anvil --block-time <n>` forces fixed-interval mining.
- Forked Anvil inherits real mainnet headers up to the fork block, then synthesises from there.

---

## 2. `transactions.ndjson`

### Purpose
One record per transaction submitted and included in a block within the range.

### RPC source
`eth_getBlockByNumber(<block>, true)` — `true` returns the full transaction bodies. Avoid per-tx `eth_getTransactionByHash` calls; batch via the block.

### Primary key
`tx_hash`

### Join role
- FK: `block_number` → `blocks`.
- Children (all keyed on `tx_hash`): `receipts`, `event_logs`, `call_traces`, `state_diffs`, `storage_diffs`.

### Fields

| Field | Type | Nullable | Source | Meaning | Example | Edge cases |
|---|---|---|---|---|---|---|
| `block_number` | int | no | rpc | Host block height. FK → blocks. | `18_500_123` | |
| `block_hash` | hex | no | rpc | Host block hash. | `0xabc...` | |
| `tx_hash` | hex | no | rpc | Keccak hash of the signed tx. PK. | `0xdea...` | 32 bytes. |
| `tx_index` | int | no | rpc | Position in the block's tx list. | `7` | Starts at 0. |
| `tx_type` | int | no | rpc | Envelope type. `0` legacy, `1` EIP-2930, `2` EIP-1559, `3` EIP-4844 blob. | `2` | |
| `chain_id` | int | yes | rpc | EIP-155 chain id. | `31337` | `null` for pre-EIP-155 legacy tx. Anvil default: `31337`. |
| `from_address` | addr | no | rpc | Signer (EOA). Checksummed. | `0xabCd...` | Recovered from signature. |
| `to_address` | addr | yes | rpc | Recipient. `null` for contract-creation tx. | `0x1234...` | Null ⇒ see `contract_address` in receipt. |
| `value` | wei | no | rpc | ETH sent with the tx, wei as decimal string. | `"1000000000000000000"` | `"0"` when none. |
| `input` | hex | no | rpc | Full calldata / creation bytecode. | `0xa9059cbb...` | `0x` for pure ETH transfer. |
| `function_selector` | hex | yes | **derived** | First 4 bytes of `input`. | `0xa9059cbb` | `null` when `len(input) < 4`. |
| `nonce` | int | no | rpc | Sender nonce at tx submission. | `42` | |
| `gas_limit` | int | no | rpc | Gas the sender was willing to pay for. | `120_000` | Named `gas` in raw RPC. |
| `gas_price` | wei | yes | rpc | Legacy gas price, wei str. | `"30000000000"` | `null` for type-2 (EIP-1559). |
| `max_fee_per_gas` | wei | yes | rpc | EIP-1559 max total fee per gas. | `"40000000000"` | `null` for type-0. |
| `max_priority_fee_per_gas` | wei | yes | rpc | EIP-1559 tip to producer. | `"2000000000"` | `null` for type-0. |
| `access_list` | json | yes | rpc | Array of `{address, storageKeys[]}`. | `[{"address":"0x...","storageKeys":["0x..."]}]` | `null` or `[]` for type-0. |
| `v` | str | yes | rpc | ECDSA recovery id. Legacy encoding: `27/28` or `chainId*2+35/36`. | `"28"` | `null` for type-1/2 (use `y_parity`). |
| `r` | hex | no | rpc | 32-byte ECDSA R. | `0x...` | |
| `s` | hex | no | rpc | 32-byte ECDSA S. | `0x...` | |
| `y_parity` | int | yes | rpc | 0 or 1, replaces `v` for type-1/2. | `1` | `null` for type-0. |

### Forensic use
- `from_address` + `function_selector` — identify actor and intent.
- `input` — calldata for decode; attacker payload often lives here.
- `nonce` — replay / sequencing analysis.
- `value` — ETH flow.
- Signature fields enable off-chain replay proofs.

### Anvil notes
- `eth_sendTransaction` from default unlocked accounts is common; signature fields will still be present.
- `anvil_impersonateAccount` produces txs signed by Anvil on behalf of an address — signatures are synthetic but still valid-shaped.

---

## 3. `receipts.ndjson`

### Purpose
One record per transaction's **post-execution** metadata: status, gas usage, contract deployment address, logs bloom.

### RPC source
`eth_getTransactionReceipt(tx_hash)` — one call per tx. Batch via JSON-RPC batch for throughput.

### Primary key
`tx_hash`

### Join role
- FK: `tx_hash` → `transactions`, `block_number` → `blocks`.
- 1:1 with `transactions`.

### Fields

| Field | Type | Nullable | Source | Meaning | Example | Edge cases |
|---|---|---|---|---|---|---|
| `block_number` | int | no | rpc | Host block. FK → blocks. | `18_500_123` | |
| `block_hash` | hex | no | rpc | Host block hash. | `0xabc...` | |
| `tx_hash` | hex | no | rpc | PK, FK → transactions. | `0xdea...` | |
| `tx_index` | int | no | rpc | Position in block. | `7` | |
| `tx_type` | int | no | rpc | Echoed from tx envelope. | `2` | |
| `from_address` | addr | no | rpc | Echoed by receipt RPC. Checksummed. | `0xabCd...` | |
| `to_address` | addr | yes | rpc | Echoed by receipt. `null` for contract creation. | `0x1234...` | |
| `status` | int | no | rpc | `1` success, `0` revert. | `1` | Pre-Byzantium chains use `root` instead — not applicable on Anvil. |
| `gas_used` | int | no | rpc | Gas consumed by this tx alone. | `52_314` | |
| `cumulative_gas_used` | int | no | rpc | Gas used by every tx in the block up to and including this one. | `732_981` | Strictly ≥ `gas_used`. |
| `effective_gas_price` | wei | no | rpc | Actual gas price paid. | `"32100000000"` | For type-2 = `min(max_fee_per_gas, base_fee + max_priority_fee_per_gas)`. |
| `contract_address` | addr | yes | rpc | Deployed contract address. | `0xbEeF02...` | `null` when tx was not a creation. |
| `logs_bloom` | hex | no | rpc | 256-byte bloom filter over this tx's logs. | `0x000...` | |
| `logs_count` | int | no | **derived** | Number of log entries in this receipt. | `4` | Validated during normalise against actual count in `event_logs.ndjson`. |

### Forensic use
- `status == 0` — find reverted tx; inspect `revert_reason` in `call_traces`.
- `contract_address` — pinpoint deployments in the range.
- `effective_gas_price` vs block `base_fee_per_gas` — attacker priority-fee burn.
- `logs_count` mismatch vs `event_logs` — silent data corruption signal.

### Anvil notes
- Receipts are returned immediately after mining — no wait required on instant-mine mode.

---

## 4. `event_logs.ndjson`

### Purpose
One record per EVM `LOGn` opcode emission. The primary evidence surface for on-chain events: token transfers, state changes, exploit invariants.

### RPC source
Preferred: `eth_getLogs({fromBlock, toBlock, address?})` — server-side filtered, efficient.
Alternative: receipts already contain logs; can be extracted from receipts if `eth_getLogs` is unavailable. Always prefer `eth_getLogs` for completeness (captures logs from internal calls that may be missed otherwise — though for Anvil both are equivalent).

### Primary key
`(tx_hash, log_index)` — `log_index` is unique within the block but we include `tx_hash` for clarity and FK joins.

### Join role
- FK: `tx_hash` → `transactions`, `block_number` → `blocks`, `address` → contract (not modelled as a separate entity).

### Fields

| Field | Type | Nullable | Source | Meaning | Example | Edge cases |
|---|---|---|---|---|---|---|
| `block_number` | int | no | rpc | Host block. | `18_500_123` | |
| `block_hash` | hex | no | rpc | Host block hash. | `0xabc...` | |
| `tx_hash` | hex | no | rpc | FK → transactions. | `0xdea...` | |
| `tx_index` | int | no | rpc | Position of parent tx in block. | `7` | |
| `log_index` | int | no | rpc | Position of this log within the block's flat log stream. PK component. | `23` | Unique per block, **not** per tx. |
| `address` | addr | no | rpc | Emitting contract. Checksummed. | `0xA0b86...` | Inner calls propagate: emitter is whoever executed the LOGn opcode. |
| `topic0` | hex | yes | rpc | `keccak256(event_signature)` when anonymous=false. | `0xddf252ad...` | `null` for anonymous events. |
| `topic1` | hex | yes | rpc | First indexed param (32 bytes padded). | `0x000...abCd` | `null` when absent. |
| `topic2` | hex | yes | rpc | Second indexed param. | `0x000...1234` | `null` when absent. |
| `topic3` | hex | yes | rpc | Third indexed param. | `0x000...` | `null` when absent. |
| `topics_count` | int | no | **derived** | Number of non-null topics (1–4, or 0 for anonymous). | `3` | Useful for quick filter without scanning nulls. |
| `data` | hex | no | rpc | ABI-encoded non-indexed parameters. | `0x0000...0000064` | `0x` when all params are indexed. |
| `removed` | bool | no | rpc | `true` if the log was orphaned by a reorg. | `false` | Always `false` on Anvil (no reorgs). |

### Forensic use
- `topic0` — event signature classifier (matched against ABI in decode pass).
- Transfer graph reconstruction (`Transfer(from,to,value)` on ERC20/721/1155).
- Protocol-specific exploit indicators (e.g. `FlashLoan(...)`, `Withdraw(...)`).

### Anvil notes
- Anonymous events (no `topic0`) are rare but valid — do not filter them out.
- `removed` always `false`.

---

## 5. `call_traces.ndjson`

### Purpose
**Flattened** internal call graph — every call frame executed inside the tx, including internal `CALL`, `STATICCALL`, `DELEGATECALL`, `CREATE`, `CREATE2`, `SELFDESTRUCT`. This is the exploit path.

### RPC source
`debug_traceTransaction(tx_hash, {tracer: "callTracer"})` — returns a **nested tree**:
```json
{ "type": "CALL", "from": "...", "to": "...", "input": "0x...", "calls": [ { ... }, { ... } ] }
```

The normaliser flattens this tree into one record per frame.

### Primary key
`(tx_hash, trace_address)`

### Join role
- FK: `tx_hash` → `transactions`, `block_number` → `blocks`.
- Self-join: parent frame identified by prefix of `trace_address`.

### Flattening convention

| `trace_address` | Meaning |
|---|---|
| `"root"` | Top-level (external) call. |
| `"0"` | First child call made by root. |
| `"1"` | Second child call made by root. |
| `"0.0"` | First child of `"0"`. |
| `"0.1"` | Second child of `"0"`. |
| `"0.1.2"` | Third child of `"0.1"`. |

`depth` = number of dots in `trace_address` (root = 0, `"0"` = 1, `"0.1.2"` = 3).

### Fields

| Field | Type | Nullable | Source | Meaning | Example | Edge cases |
|---|---|---|---|---|---|---|
| `block_number` | int | no | rpc | Host block. | `18_500_123` | |
| `tx_hash` | hex | no | rpc | FK → transactions. | `0xdea...` | |
| `trace_address` | str | no | **derived** | Dotted path identifying frame position. PK per tx. | `"0.1.2"` | Root = `"root"`. |
| `depth` | int | no | **derived** | Call-stack depth. Root = 0. | `3` | |
| `call_type` | str | no | rpc | One of `CALL`, `STATICCALL`, `DELEGATECALL`, `CALLCODE`, `CREATE`, `CREATE2`, `SELFDESTRUCT`. | `"DELEGATECALL"` | `CALLCODE` is legacy/rare. |
| `from_address` | addr | no | rpc | Caller. Checksummed. | `0xabCd...` | For CREATE this is the deployer. |
| `to_address` | addr | yes | rpc | Callee. `null` for `CREATE`/`CREATE2` *before* address is known (normaliser populates once computable). | `0xbEeF02...` | |
| `value` | wei | no | rpc | ETH transferred in this frame. | `"0"` | Zero for STATICCALL / DELEGATECALL. |
| `input` | hex | no | rpc | Calldata for this frame. | `0xa9059cbb...` | For CREATE: init bytecode. |
| `function_selector` | hex | yes | **derived** | `input[0:4]`. | `0xa9059cbb` | `null` when `len(input) < 4`. Undefined for CREATE. |
| `output` | hex | yes | rpc | Return data. | `0x000...001` | `null` if frame reverted without return data. |
| `gas_provided` | int | no | rpc | Gas forwarded to this frame. | `83_000` | |
| `gas_used` | int | no | rpc | Gas consumed by this frame. | `31_402` | |
| `error` | str | yes | rpc | Error name when frame failed. `"execution reverted"`, `"out of gas"`, `"invalid jump destination"`, `null` on success. | `"execution reverted"` | Parent may succeed while child reverts (try/catch, callee reverts). |
| `revert_reason` | hex | yes | rpc | Raw ABI-encoded revert data. | `0x08c379a0...` | Decode via `Error(string)` ABI in decode pass. `null` when no revert data. |

### Forensic use
- Attack path reconstruction — which function called which, in what order, with what args.
- Reentrancy detection — look for the same `(from, to)` pair reappearing at deeper depth.
- Silent failures — child frame `error` set but parent `status` == 1.
- `DELEGATECALL` analysis — proxy / upgradeable contract behaviour.

### Anvil notes
- `debug_traceTransaction` is enabled by default on Anvil — no `--debug` flag needed.
- `callTracer` is the cheapest tracer; avoid default opcode-level tracer unless needed (orders of magnitude slower).

---

## 6. `state_diffs.ndjson`

### Purpose
Per-tx **account-level** state changes — balance, nonce, code. One record per (tx, address). Tier-2 entity: extract only on demand.

### RPC source
`debug_traceTransaction(tx_hash, {tracer: "prestateTracer", tracerConfig: {diffMode: true}})` returns `{pre: {addr: {...}}, post: {addr: {...}}}`. Normaliser computes `post - pre` per address.

### Primary key
`(tx_hash, address)`

### Join role
- FK: `tx_hash` → `transactions`, `block_number` → `blocks`.

### Fields

| Field | Type | Nullable | Source | Meaning | Example | Edge cases |
|---|---|---|---|---|---|---|
| `block_number` | int | no | rpc | Host block. | `18_500_123` | |
| `tx_hash` | hex | no | rpc | FK → transactions. | `0xdea...` | |
| `address` | addr | no | rpc | EOA or contract whose state changed. | `0xabCd...` | Checksummed. |
| `balance_before` | wei | no | rpc | Account balance at start of tx. | `"1500000000000000000"` | |
| `balance_after` | wei | no | rpc | Account balance at end of tx. | `"1200000000000000000"` | |
| `balance_delta` | wei | no | **derived** | Signed `balance_after - balance_before`. | `"-300000000000000000"` | Negative strings permitted (leading `-`). |
| `nonce_before` | int | no | rpc | Nonce at start of tx. | `42` | |
| `nonce_after` | int | no | rpc | Nonce at end. | `43` | For EOAs increments by 1 per tx. For contracts increments on CREATE/CREATE2. |
| `code_changed` | bool | no | **derived** | `true` if bytecode was deployed or replaced. | `false` | Detected by `pre.code != post.code`. |

### Forensic use
- Drained accounts — negative `balance_delta` over tx.
- Attacker profit — `balance_delta` summed by `from_address` across txs.
- Malicious redeployment — `code_changed == true` for proxy-like patterns.

### Anvil notes
- `prestateTracer` with `diffMode: true` requires Anvil recent enough (post mid-2023 releases all support it).
- On forked Anvil, prestate is pulled from the fork source for untouched accounts.

---

## 7. `storage_diffs.ndjson`

### Purpose
Per-tx **storage-slot-level** changes. One record per (tx, address, slot). Tier-2 entity: extract only on demand.

### RPC source
Same call as `state_diffs`: `debug_traceTransaction(tx_hash, {tracer: "prestateTracer", tracerConfig: {diffMode: true}})`. The `storage` sub-object of each address delta yields these records.

### Primary key
`(tx_hash, address, slot)`

### Join role
- FK: `tx_hash` → `transactions`, `block_number` → `blocks`, `address` → contract.

### Fields

| Field | Type | Nullable | Source | Meaning | Example | Edge cases |
|---|---|---|---|---|---|---|
| `block_number` | int | no | rpc | Host block. | `18_500_123` | |
| `tx_hash` | hex | no | rpc | FK → transactions. | `0xdea...` | |
| `address` | addr | no | rpc | Contract whose storage changed. | `0xA0b86...` | |
| `slot` | hex | no | rpc | 32-byte storage key. | `0x0000...0002` | Lowercase, zero-padded to 32 bytes. |
| `value_before` | hex | no | rpc | 32-byte previous value. | `0x0000...064` | |
| `value_after` | hex | no | rpc | 32-byte new value. | `0x0000...0ff` | |

### Forensic use
- Storage layout diffing — reveals mutated balances in ERC20 mappings.
- Proxy implementation slot changes (EIP-1967 slot = `0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc`).
- Reserve / pool invariant violations.
- Upgrade event detection (`_IMPLEMENTATION_SLOT` write).

### Anvil notes
- Storage diffs are emitted only for slots actually touched — not a full trie dump.
- Slot-key computation for mapping entries: `keccak256(abi.encode(key, slot_index))`. Downstream tools decode this separately.

---

## 8. Join Graph (complete)

```
                           ┌────────────┐
                           │  blocks    │
                           │ block_number│
                           └─────┬──────┘
                                 │  block_number (FK)
       ┌─────────────────────────┼────────────────────────────┐
       │                         │                            │
┌──────▼────────┐      ┌─────────▼────────┐       ┌───────────▼────────┐
│ transactions  │      │    receipts      │       │  event_logs        │
│ tx_hash (PK)  │◄────►│ tx_hash (PK,FK)  │       │ (tx_hash,log_idx)  │
└──────┬────────┘      └──────────────────┘       └────────────────────┘
       │
       │ tx_hash (FK)
       │
┌──────▼──────────┐    ┌───────────────────┐    ┌─────────────────────────┐
│  call_traces    │    │  state_diffs      │    │  storage_diffs          │
│ (tx_hash,trace) │    │ (tx_hash,address) │    │ (tx_hash,address,slot)  │
└─────────────────┘    └───────────────────┘    └─────────────────────────┘
```

Every non-block entity joins to `blocks` via `block_number` and (for the bottom five) to `transactions` via `tx_hash`.

---

## 9. Derived Fields — summary

Computed by the normaliser, never read from the RPC:

| Entity | Field | Formula |
|---|---|---|
| blocks | `transaction_count` | `len(transactions)` from full block call |
| transactions | `function_selector` | `input[0:4]` if `len(input) >= 4` else `null` |
| receipts | `logs_count` | `len(receipt.logs)` |
| event_logs | `topics_count` | number of non-null topics (0–4) |
| call_traces | `trace_address` | assigned during tree-flatten (dotted path) |
| call_traces | `depth` | `trace_address.count('.')` if ≠ "root" else 0 |
| call_traces | `function_selector` | `input[0:4]` rules as above |
| state_diffs | `balance_delta` | `balance_after - balance_before` (signed decimal string) |
| state_diffs | `code_changed` | `pre.code != post.code` |

---

## 10. Validation rules (run at end of normalisation)

Normaliser must **fail loudly** on any of:

1. Duplicate primary key within a single file.
2. `receipts.logs_count != count(event_logs where tx_hash == X)` for any tx.
3. `transactions.block_number` not present in `blocks.ndjson`.
4. `event_logs.tx_hash` not present in `transactions.ndjson`.
5. Any address not EIP-55-checksum-valid.
6. Any hex field not lowercase or missing `0x` prefix.
7. Any wei field not a decimal string.
8. Any `call_traces` frame with a non-null `to_address` that fails checksum.

Validation failures write an error to stderr and produce an `errors.ndjson` file in the run directory. Do not proceed to decode with invalid raw/norm data.

---

## 11. NDJSON output rules — exact

- File name: `<entity>.ndjson` — e.g. `blocks.ndjson`.
- Every record is a single-line JSON object with a trailing `\n`.
- No BOM, no UTF-16, no leading whitespace.
- Records ordered ascending by primary key.
- Field order within an object **does not matter** functionally but should be stable for diffability (recommended: the order given in each fields table above).
- No pretty-printing, no indentation.
- Missing optional values = JSON `null`. Never empty string, never `"0x"` for a missing hash, never `0` for a missing int.

---

## 12. Anvil / Foundry specifics (relevant across entities)

- **Default chain id**: `31337`.
- **Default RPC**: `http://127.0.0.1:8545`.
- **Tracers available**: `callTracer`, `prestateTracer` (with `diffMode`), `4byteTracer`, `noopTracer`, `muxTracer`. Opcode-level default tracer is slow — avoid.
- **Instant mining**: default. One tx per block. Use `--block-time <n>` for real-time mining or `--no-mining` for manual.
- **Fork mode**: `anvil --fork-url <mainnet_rpc>` inherits state up to the fork block. Extracted records post-fork differ from mainnet post-fork-block even at the same block number — always record `fork_url` and `fork_block_number` in `manifest.json` when present (`anvil_nodeInfo`).
- **State snapshot**: `anvil_dumpState` returns a blob that restores the exact chain via `anvil_loadState`. Consider storing alongside raw/ for reproducibility (out of core spec, optional).
- **Impersonation**: `anvil_impersonateAccount` produces txs signed by Anvil. These appear identical to real txs in receipts and traces.
- **Gas estimation**: Anvil's `eth_estimateGas` is permissive; don't rely on gas values to diagnose pre-submission simulation.
- **Reorgs**: never occur on vanilla Anvil. `event_logs.removed` always `false`.

---

## Appendix A — RPC method inventory

| RPC method | Used for |
|---|---|
| `eth_chainId` | Manifest metadata. |
| `eth_blockNumber` | Resolve `"latest"` for ranges. |
| `eth_getBlockByNumber(n, false)` | `blocks.ndjson` fields. |
| `eth_getBlockByNumber(n, true)` | `transactions.ndjson`. |
| `eth_getTransactionReceipt(hash)` | `receipts.ndjson`. |
| `eth_getLogs({fromBlock, toBlock, address?, topics?})` | `event_logs.ndjson`. |
| `debug_traceTransaction(hash, {tracer: "callTracer"})` | `call_traces.ndjson`. |
| `debug_traceTransaction(hash, {tracer: "prestateTracer", tracerConfig: {diffMode: true}})` | `state_diffs.ndjson` + `storage_diffs.ndjson`. |
| `anvil_nodeInfo` *(Anvil-only)* | Manifest metadata — fork info, hardfork, base fee config. |
| `anvil_dumpState` *(Anvil-only, optional)* | Full-state reproducibility snapshot. |
| `eth_getCode(addr, blockTag)` | Optional `contracts.ndjson` (not in core 7). |

All calls should use JSON-RPC batch where possible (especially per-block receipt fetches and per-tx trace fetches).

---

## Appendix B — `manifest.json` shape (per run)

Not a log entity, but mandatory sibling of raw/:

```json
{
  "run_id": "2026-04-22T14-33-07Z__curve-reentrancy",
  "tool_version": "0.1.0",
  "created_at": "2026-04-22T14:33:07Z",
  "rpc": {
    "url": "http://127.0.0.1:8545",
    "chain_id": 31337,
    "client": "anvil/0.2.0",
    "fork_url": null,
    "fork_block_number": null
  },
  "cli_args": {
    "from_block": 0,
    "to_block": 250,
    "address_filter": null,
    "tx_filter": null,
    "entities": ["blocks","transactions","receipts","event_logs","call_traces"]
  },
  "counts": {
    "blocks": 251,
    "transactions": 412,
    "receipts": 412,
    "event_logs": 1503,
    "call_traces": 2847
  },
  "hashes": {
    "raw/blocks.ndjson": "sha256:...",
    "raw/transactions.ndjson": "sha256:...",
    "raw/receipts.ndjson": "sha256:...",
    "raw/event_logs.ndjson": "sha256:...",
    "raw/call_traces.ndjson": "sha256:..."
  }
}
```

The manifest is the anchor for every reproducibility and audit claim the tool makes.

---

## Appendix C — reserved / out-of-scope fields

Fields deliberately **not** included in the canonical schema:

- `token_symbol`, `token_decimals` (decode-pass concern, not raw).
- `usd_value` (price feed dependency — out of tool scope).
- `implementation_address` (proxy resolution — decode-pass optional extension).
- `trace_opcodes` (opcode-level trace is too large and not needed for call-path forensics).

Adding any of these belongs in a separate decoded or enriched stage, not in the raw schema.

---

**End of spec.** Reuse this document verbatim when scoping any new exporter, normaliser, or ingestion target.
