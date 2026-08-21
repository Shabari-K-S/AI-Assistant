#!/usr/bin/env bash
# ==============================================================================
# ATHENA — llama-server Android / Termux Launch Script
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODELS_DIR="${BACKEND_DIR}/models"

# Check if model exists
MODEL_PATH="${EV_LLAMA_MODEL_PATH:-${MODELS_DIR}/qwen2.5-1.5b-instruct-q4_k_m.gguf}"

if [ ! -f "${MODEL_PATH}" ]; then
    # Look for any .gguf file in models dir
    FIRST_GGUF=$(find "${MODELS_DIR}" -name "*.gguf" | head -n 1)
    if [ -n "${FIRST_GGUF}" ]; then
        MODEL_PATH="${FIRST_GGUF}"
    else
        echo "[!] No GGUF model found at: ${MODEL_PATH}"
        echo "[*] Run 'bash scripts/setup_llama_android.sh' to download the recommended model."
        exit 1
    fi
fi

HOST="${EV_LLAMA_HOST:-127.0.0.1}"
PORT="${EV_LLAMA_PORT:-8080}"
THREADS="${EV_LLAMA_THREADS:-$(nproc 2>/dev/null || echo 4)}"
CTX_SIZE="${EV_LLAMA_CTX:-16384}"
BATCH_SIZE="${EV_LLAMA_BATCH:-512}"

echo "=============================================================================="
echo "=== Starting ATHENA llama-server ==="
echo "Model:      ${MODEL_PATH}"
echo "Endpoint:   http://${HOST}:${PORT}"
echo "Threads:    ${THREADS}"
echo "Context:    ${CTX_SIZE}"
echo "Batch Size: ${BATCH_SIZE}"
echo "=============================================================================="

# Launch llama-server with optimized flags for mobile Android/Termux
exec llama-server \
    -m "${MODEL_PATH}" \
    --host "${HOST}" \
    --port "${PORT}" \
    -c "${CTX_SIZE}" \
    -b "${BATCH_SIZE}" \
    -t "${THREADS}" \
    -np 1 \
    --jinja \
    --cont-batching
