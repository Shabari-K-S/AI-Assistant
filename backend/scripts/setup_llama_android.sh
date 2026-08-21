#!/usr/bin/env bash
# ==============================================================================
# ATHENA — llama.cpp Android / Termux Automated Setup Script
# ==============================================================================
set -e

echo "=== [ATHENA] Setting up llama.cpp for Android / Termux ==="

# 1. Install llama-cpp package in Termux if available
if command -v pkg &> /dev/null; then
    echo "[+] Updating Termux package list and installing llama-cpp & curl..."
    pkg update -y || true
    pkg install -y llama-cpp curl wget || {
        echo "[!] 'llama-cpp' package not in default repo. Installing clang & cmake to build or verify..."
    }
fi

# 2. Check for llama-server
if ! command -v llama-server &> /dev/null; then
    echo "[!] Warning: 'llama-server' binary not found in PATH."
    echo "[*] In Termux, you can install it with: pkg install -y llama-cpp"
    echo "[*] Or build from source with: pkg install git cmake clang && git clone https://github.com/ggerganov/llama.cpp && cd llama.cpp && cmake -B build && cmake --build build --config Release -j4"
else
    echo "[+] Found llama-server: $(command -v llama-server)"
fi

# 3. Create models directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
MODELS_DIR="${BACKEND_DIR}/models"
mkdir -p "${MODELS_DIR}"

echo "[+] Models directory: ${MODELS_DIR}"

# 4. Model Selection & Download
DEFAULT_MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
DEFAULT_MODEL_FILE="${MODELS_DIR}/qwen2.5-1.5b-instruct-q4_k_m.gguf"

if [ -f "${DEFAULT_MODEL_FILE}" ]; then
    echo "[✓] Default model already downloaded: ${DEFAULT_MODEL_FILE}"
else
    echo "[+] Downloading Qwen 2.5 1.5B Instruct Q4_K_M (~1.1 GB)..."
    echo "    (Ultra-lightweight, high intelligence, native tool calling for Android)"
    if command -v wget &> /dev/null; then
        wget -c "${DEFAULT_MODEL_URL}" -O "${DEFAULT_MODEL_FILE}"
    else
        curl -L "${DEFAULT_MODEL_URL}" -o "${DEFAULT_MODEL_FILE}"
    fi
    echo "[✓] Download complete!"
fi

echo "=============================================================================="
echo "=== [ATHENA] llama.cpp Setup Complete! ==="
echo "To start the local model server, run:"
echo "    bash scripts/run_llama_server.sh"
echo "=============================================================================="
