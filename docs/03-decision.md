# 03 — Decisions

*The git history is two commits with no bodies (`e34f8c3` scaffold, `09c7361`
end-to-end pipeline + anvil demo), so it records no decision narrative of its own.
The decisions below are quoted or paraphrased from documents that shipped with the
repo; each entry names its source. Nothing here is reconstructed from assumption.*

## D1 — Three separate CLIs, not one

> "Extract is slow (RPC calls). Do it once, never again. Normalise is deterministic
> and ABI-free. Always safe to rerun. Decode requires the client's ABI. Client gives
> ABI late, or wrong, or partial. Re-decode without re-extracting."
> — `evm-forensics-meta-prompt.md`

Three console scripts — `evm-extract`, `evm-normalise`, `evm-decode` — declared in
`pyproject.toml` `[project.scripts]`. `CLAUDE.md` states the separation is
load-bearing: *"Do not collapse stages."*

## D2 — NDJSON everywhere, no DB

One JSON object per line, `\n` terminated, no array wrapper, `.ndjson` extension,
streamed in and out at every stage. No database, no streaming service, no
indexing. (`evm-forensics-meta-prompt.md`, "Output Format: NDJSON";
`docs/superpowers/plans/2026-04-22-evm-log-extractor.md` — *"Streaming NDJSON in/out
at every stage. Zero global state, zero auto-discovery magic."*)

## D3 — Data rules that are not negotiable

From `CLAUDE.md`, "Non-Negotiable Data Rules":

- wei values as decimal strings, never JSON numbers (precision loss past 2^53)
- addresses EIP-55 checksummed
- hex lowercase, `0x`-prefixed
- derived fields computed, not read

Implemented in `src/evm_log_extractor/types.py` (`wei_str`, `checksum_address`,
`hex_lower`, `signed_wei_delta`) and applied at the extractors.

**Divergence worth recording:** `CLAUDE.md` assigns derived fields
(`function_selector`, `topics_count`, `depth`, `balance_delta`,
`transaction_count`, `logs_count`) to the *normalise* stage. In the shipped code
they are computed at *extract* time (`extractors/transactions.py`,
`extractors/blocks.py`, `extractors/event_logs.py`, `extractors/call_traces.py`,
`extractors/state_diffs.py`). `normaliser.py` does not recompute them — it copies
`raw/` to `norm/`, rejects duplicate primary keys, and runs cross-entity
validation. `CLAUDE.md` is stale on this point; the code is the truth.

## D4 — Tiered entities, and the mode each one requires

Tier 1 (`blocks`, `transactions`, `receipts`, `event_logs`, `call_traces`) is
block-range mode. Tier 2 (`state_diffs`, `storage_diffs`) needs a single tx hash
because `debug_traceTransaction` is per-transaction. The CLI enforces this rather
than producing empty files: tier-2 without `--tx` exits 2, and `event_logs` in
`--tx` mode exits 2 (`cli/extract.py`) because `eth_getLogs` is range-based.

**Divergence worth recording:** the implementation plan says *"Tier-2
(`state_diffs`, `storage_diffs`) deferred."* They shipped in `09c7361` and are
covered by tests.

## D5 — Flatten the call tree with a path address

`debug_traceTransaction` (callTracer) returns nested frames. Flattened to one row
per frame with `trace_address` (`"root"`, `"0"`, `"0.1"`, `"0.1.2"`) and `depth`
= dot count + 1, root = 0. (`CLAUDE.md`, "call_traces Flattening";
implemented in `extractors/call_traces.py`.)

## D6 — Validation is a cross-entity check, not a per-record one

`normalise_run` enforces two invariants across files:

1. every receipt's `logs_count` equals the number of `event_logs` rows for that
   `tx_hash`
2. every `transactions` row references a `block_number` present in `blocks`

Failure raises `ValidationError` and the CLI exits non-zero naming the offending
tx. This is the point of the stage — evidence that contradicts itself is not
evidence.

## D7 — Decode never drops a log

Unmatched logs pass through with `event_name`, `event_signature`, and `decoded` all
`null`, and are additionally copied to `unmatched.ndjson`. A decode error adds
`decode_error` and is likewise counted as unmatched rather than raised.
(`decoder.py`; rule stated in `CLAUDE.md`, "Decode Pass".)

## D8 — Per-run manifest with hashes

Each run writes `manifest.json`: `run_id`, `tool_version`, `created_at`, an `rpc`
block (`url`, `chain_id`, `client`, and fork info where `anvil_nodeInfo` returns
them), the `cli_args` used, per-entity `counts`, and a `sha256:` of every raw
NDJSON file. (`manifest.py`; reproducibility called for in the implementation
plan.) Run ids are `<timestamp>__<label>`, or `<timestamp>__blk-<from>-<to>` with
no label.

## D9 — ABIs from three sources, all CLI-plumbed

`--abi FILE` (Foundry/Hardhat artifact with an `.abi` key, or a raw JSON array),
`--abi-dir DIR`, and `--foundry-project DIR` (walks `out/`). All three are
repeatable and combined into one topic0 → event index by `abi_loader.py`.

## D10 — Demo over docs

`scripts/anvil_demo.sh` + `docs/anvil-demo.md` stand up a real Anvil node, deploy
`examples/foundry-demo/src/Counter.sol`, and run all three stages end to end. The
binaries are resolved from `.venv/bin/` when present, else `PATH`, and are
overridable per-command (`EVM_EXTRACT_BIN`, `EVM_NORMALISE_BIN`,
`EVM_DECODE_BIN`), so the script works against an uninstalled checkout too.

## Not decided, still open

- No CLI flag exists to pass a raw ABI bundle path by directory of mixed artifact
  shapes; `--abi-dir` assumes every file is an ABI bundle.
- `normalise_run` does no per-record rewriting (see D3), so the `norm/` files are
  currently byte-equivalent to `raw/` for well-formed input.
- Public endpoints generally disable the two `debug_traceTransaction` tracers, so
  tier-1 minus `call_traces` is the widest portable subset. Not documented in-repo
  until someone hits it in practice.

See [01-problem.md](01-problem.md) for the problem these decisions answer.