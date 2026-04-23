# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project State

Pre-code. Only `evm-forensics-meta-prompt.md` exists — full spec for the tool. Read it before writing any code; it is the source of truth for schemas, RPC methods, and CLI flags.

## What This Is

Forensics-grade EVM log extractor + normaliser. Target node: Anvil (Foundry), but must work on any EVM JSON-RPC endpoint (mainnet forks, testnets, live). Output is flat NDJSON files — no DB, no streaming, no indexing.

## 3-Stage Pipeline (load-bearing)

```
[EXTRACT]   raw NDJSON      — RPC-bound, slow, run once, ABI-free
[NORMALISE] norm NDJSON     — deterministic, ABI-free, safe to rerun, source of truth
[DECODE]    decoded NDJSON  — ABI-dependent, re-runnable against norm NDJSON
```

Separation is deliberate: clients deliver ABIs late/wrong/partial, so decode must be replayable without re-hitting RPC. Do not collapse stages.

## Target File Layout

```
extractor.py     # Anvil/RPC → raw/*.ndjson
normaliser.py    # raw/ → norm/ (checksums, derived fields, validations)
decoder.py       # norm/event_logs.ndjson + ABIs → decoded_event_logs.ndjson
requirements.txt
```

Each stage is a Python CLI (click). Each outputs NDJSON — one JSON object per line, `\n` terminated, no array wrapper, `.ndjson` extension. Composable via Unix pipes.

## 7 Entities

Tier 1 (default pull): `blocks`, `transactions`, `receipts`, `event_logs`, `call_traces`.
Tier 2 (on demand): `state_diffs`, `storage_diffs` (both from `debug_traceTransaction` with `prestateTracer` + `diffMode: true`).

Join keys: `block_number` → blocks; `tx_hash` → receipts/event_logs/call_traces/state_diffs/storage_diffs. Field schemas for all 7 entities are exhaustively listed in `evm-forensics-meta-prompt.md` — do not invent fields.

## Non-Negotiable Data Rules

- **All wei values are decimal strings** (`value`, `balance_*`, `gas_price`, `max_fee_per_gas`, `effective_gas_price`, `balance_delta`, ...). JSON numbers lose precision >2^53. Never store as int.
- **All addresses EIP-55 checksummed** via `Web3.to_checksum_address()`.
- **All hex values lowercase**, `0x`-prefixed.
- **Derived fields** (`function_selector`, `topics_count`, `depth`, `balance_delta`, `transaction_count`, `logs_count`) computed at normalise time, not at extract.

## call_traces Flattening

`debug_traceTransaction` (callTracer) returns nested tree. Flatten to one record per frame:
- `trace_address`: `"root"`, then `"0"`, `"0.1"`, `"0.1.2"` ...
- `depth`: dot count + 1 (root = 0).

## Normalisation Pass Must

1. Checksum addresses. 2. Lowercase hex. 3. Hex int → Python int where appropriate. 4. Compute derived fields. 5. Validate receipt `logs_count` matches actual count in `event_logs` for that tx.

## Decode Pass

Input: `event_logs.ndjson` + one or more ABIs (Foundry/Hardhat artifact with `.abi` key, or raw JSON array). Output adds `event_name`, `event_signature`, `decoded` (dict). Unmatched logs pass through with `decoded: null` — do not drop.

## CLI Flags (extractor)

`--address`, `--tx`, `--from-block`, `--to-block` (int or `"latest"`), `--rpc` (default `http://127.0.0.1:8545`), `--entities <csv>`, `--out-dir` / `--out`.

## Tech

Python 3.11+. `web3.py ≥ 6.0`, `eth-abi ≥ 4.0`, `eth-utils ≥ 2.0`, `click`.

## Out of Scope (do not build)

Token metadata lookup (ERC20 symbol/decimals). Bytecode analysis. Derived `token_transfers` table (decode from `event_logs` instead). Live monitoring / indexing / streaming. DB ingestion.

## Typical Workflow

```bash
python extractor.py --from-block 100 --to-block 200 \
  --entities blocks,transactions,receipts,event_logs,call_traces --out-dir ./raw/
python normaliser.py --in-dir ./raw/ --out-dir ./norm/
python decoder.py --input ./norm/event_logs.ndjson --abi ./Token.json --abi ./Vault.json \
  --out ./decoded_events.ndjson
python extractor.py --tx 0xABC... --entities state_diffs,storage_diffs --out-dir ./raw/
```
