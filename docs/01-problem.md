# 01 — The Problem

*Source: `evm-forensics-meta-prompt.md` ("What We Are Building", "Architecture: 3-Stage Pipeline"), `CLAUDE.md` ("What This Is"), `docs/superpowers/plans/2026-04-22-evm-log-extractor.md` ("Goal").*

## What the tool is for

Investigating smart-contract exploits, protocol attacks, and on-chain activity. The
primary target node is **Anvil** (Foundry's local EVM), but the tool must work
against any EVM-compatible JSON-RPC endpoint — mainnet forks, testnets, live nodes.

## The shape of the problem

Reconstructing what happened in an exploit means joining six kinds of evidence that
come from six different RPC methods and carry six different shapes:

| Evidence | RPC source |
|---|---|
| block metadata | `eth_getBlockByNumber` |
| transaction intent (from, to, input) | `eth_getBlockByNumber` (fullTx) |
| outcome (status, gas, logs emitted) | `eth_getTransactionReceipt` |
| events | `eth_getLogs` |
| internal call flow | `debug_traceTransaction` + `callTracer` |
| state / storage mutation | `debug_traceTransaction` + `prestateTracer` (diffMode) |

Raw JSON-RPC output is not usable as forensic evidence as-is. It is full of
heterogeneous quantities that must be made uniform before they can be compared or
joined:

- **Wei amounts exceed 2^53.** JSON numbers lose precision past that point, so a
  single wei value can silently round in transit. Every wei value has to be a
  decimal *string* — `value`, `balance_*`, `gas_price`, `max_fee_per_gas`,
  `effective_gas_price`, `balance_delta`. Never an int. (`CLAUDE.md`,
  "Non-Negotiable Data Rules")
- **Addresses arrive inconsistively cased.** They must be EIP-55 checksummed so a
  mistyped address is detectable. (`CLAUDE.md`)
- **Hex is inconsistently cased and prefixed.** It must be lowercase and
  `0x`-prefixed. (`CLAUDE.md`)
- **Derived facts are not in the RPC response.** `function_selector`,
  `topics_count`, `depth`, `balance_delta`, `transaction_count`, `logs_count` all
  have to be computed. (`CLAUDE.md`)
- **`debug_traceTransaction` returns a nested call tree**, not rows. It has to be
  flattened to one record per frame with a `trace_address` path (`"root"`, `"0"`,
  `"0.1"`, `"0.1.2"` …) and a `depth`. (`CLAUDE.md`, "call_traces Flattening")
- **Evidence has to be internally consistent before it is evidence.** A receipt
  claiming 3 logs while only 2 event rows exist for that tx is a red flag, not a
  formatting detail.

## The two constraints that shape everything

1. **Extraction is slow and expensive.** It is the only stage that touches RPC.
   Once extracted, it should never need to happen again.
2. **ABIs arrive late, wrong, or partial.** A client hands you logs first and the
   ABI afterwards, or hands you a partial one. Decoding therefore cannot be fused
   into extraction — it has to be re-runnable against already-captured data.

## Explicit non-goals

Recorded so they are not re-litigated (`CLAUDE.md`, "Out of Scope (do not build)"):
token metadata lookup (ERC20 symbol/decimals), bytecode analysis, a derived
`token_transfers` table (decode it from `event_logs` instead), live monitoring /
indexing / streaming, and database ingestion. The output is flat files — no DB,
no streaming, no indexing.

## Where the problem is specified

- `evm-forensics-meta-prompt.md` — original scope doc
- `raw-log-schema.md` — canonical per-entity field spec, the source of truth for
  every field name and type
- `DESIGN.md` / `apple/DESIGN.md` — presentation only, unrelated to the data problem

Next: [03-decision.md](03-decision.md).