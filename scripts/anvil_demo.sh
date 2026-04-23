#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RPC_HOST="${RPC_HOST:-127.0.0.1}"
RPC_PORT="${RPC_PORT:-9545}"
RPC_URL="http://${RPC_HOST}:${RPC_PORT}"

# Anvil/Hardhat default first account private key (local demo only).
PK="${DEMO_PRIVATE_KEY:-0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80}"

OUT_BASE="${OUT_BASE:-${ROOT_DIR}/output}"

echo "[demo] repo=${ROOT_DIR}"
echo "[demo] rpc=${RPC_URL}"
echo "[demo] output_base=${OUT_BASE}"

cleanup() {
  if [[ -n "${ANVIL_PID:-}" ]] && kill -0 "${ANVIL_PID}" 2>/dev/null; then
    kill "${ANVIL_PID}" || true
  fi
}
trap cleanup EXIT

echo "[demo] starting anvil..."
anvil --host "${RPC_HOST}" --port "${RPC_PORT}" --silent > /tmp/anvil_demo.log 2>&1 &
ANVIL_PID=$!

echo "[demo] waiting for rpc..."
for _ in $(seq 1 40); do
  if cast chain-id --rpc-url "${RPC_URL}" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done

CHAIN_ID="$(cast chain-id --rpc-url "${RPC_URL}")"
echo "[demo] chain_id=${CHAIN_ID}"

echo "[demo] building foundry demo..."
pushd "${ROOT_DIR}/examples/foundry-demo" >/dev/null
forge build >/dev/null

echo "[demo] deploying Counter..."
DEPLOY_JSON="$(mktemp)"
forge create --rpc-url "${RPC_URL}" --private-key "${PK}" src/Counter.sol:Counter --json > "${DEPLOY_JSON}"
COUNTER_ADDR="$(python -c "import json; print(json.load(open('${DEPLOY_JSON}'))['deployedTo'])")"
DEPLOY_TX="$(python -c "import json; print(json.load(open('${DEPLOY_JSON}'))['transactionHash'])")"
echo "[demo] counter=${COUNTER_ADDR}"
echo "[demo] deploy_tx=${DEPLOY_TX}"

echo "[demo] calling Counter.inc()..."
INC_JSON="$(mktemp)"
cast send --rpc-url "${RPC_URL}" --private-key "${PK}" "${COUNTER_ADDR}" "inc()" --json > "${INC_JSON}"
INC_TX="$(python -c "import json; print(json.load(open('${INC_JSON}'))['transactionHash'])")"
echo "[demo] inc_tx=${INC_TX}"

popd >/dev/null

EVM_EXTRACT_BIN="${EVM_EXTRACT_BIN:-}"
EVM_NORMALISE_BIN="${EVM_NORMALISE_BIN:-}"
EVM_DECODE_BIN="${EVM_DECODE_BIN:-}"
if [[ -z "${EVM_EXTRACT_BIN}" && -x "${ROOT_DIR}/.venv/bin/evm-extract" ]]; then EVM_EXTRACT_BIN="${ROOT_DIR}/.venv/bin/evm-extract"; fi
if [[ -z "${EVM_NORMALISE_BIN}" && -x "${ROOT_DIR}/.venv/bin/evm-normalise" ]]; then EVM_NORMALISE_BIN="${ROOT_DIR}/.venv/bin/evm-normalise"; fi
if [[ -z "${EVM_DECODE_BIN}" && -x "${ROOT_DIR}/.venv/bin/evm-decode" ]]; then EVM_DECODE_BIN="${ROOT_DIR}/.venv/bin/evm-decode"; fi
if [[ -z "${EVM_EXTRACT_BIN}" ]]; then EVM_EXTRACT_BIN="evm-extract"; fi
if [[ -z "${EVM_NORMALISE_BIN}" ]]; then EVM_NORMALISE_BIN="evm-normalise"; fi
if [[ -z "${EVM_DECODE_BIN}" ]]; then EVM_DECODE_BIN="evm-decode"; fi

LATEST="$(cast block-number --rpc-url "${RPC_URL}")"
echo "[demo] latest_block=${LATEST}"

echo "[demo] extracting tier-1 logs over block range..."
RANGE_OUT="$("${EVM_EXTRACT_BIN}" --rpc "${RPC_URL}" --from-block 0 --to-block "${LATEST}" \
  --entities blocks,transactions,receipts,event_logs,call_traces \
  --base-dir "${OUT_BASE}" --label anvil-range | tail -n 1)"
echo "[demo] range_run=${RANGE_OUT}"

echo "[demo] normalising range run..."
"${EVM_NORMALISE_BIN}" --in-dir "${RANGE_OUT}" >/dev/null

echo "[demo] decoding range event_logs..."
mkdir -p "${RANGE_OUT}/decoded"
"${EVM_DECODE_BIN}" --input "${RANGE_OUT}/norm/event_logs.ndjson" --out "${RANGE_OUT}/decoded/event_logs.ndjson" \
  --foundry-project "${ROOT_DIR}/examples/foundry-demo" >/dev/null

echo "[demo] extracting tier-2 diffs for inc tx..."
DIFFS_OUT="$("${EVM_EXTRACT_BIN}" --rpc "${RPC_URL}" --tx "${INC_TX}" \
  --entities call_traces,state_diffs,storage_diffs \
  --base-dir "${OUT_BASE}" --label anvil-diffs | tail -n 1)"
echo "[demo] diffs_run=${DIFFS_OUT}"

echo "[demo] normalising diffs run..."
"${EVM_NORMALISE_BIN}" --in-dir "${DIFFS_OUT}" >/dev/null

echo "[demo] done."
echo "[demo] range: ${RANGE_OUT}"
echo "[demo] diffs: ${DIFFS_OUT}"
echo "[demo] decoded event logs: ${RANGE_OUT}/decoded/event_logs.ndjson"

