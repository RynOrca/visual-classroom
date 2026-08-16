#!/usr/bin/env bash
# Start the local llama.cpp vision server used by UnlimitedOCR.
#
# The server is optional; it only needs to run when you want scanned-PDF OCR
# through UNLIMITED_OCR_COMMAND. The model GGUF files are expected under
# ./unlimited-ocr (not tracked by git).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -W 2>/dev/null || pwd)"
LLAMA_CPP_DIR="${LLAMA_CPP_DIR:-/d/llama.cpp}"
MODEL_DIR="${UNLIMITED_OCR_MODEL_DIR:-$ROOT/unlimited-ocr}"
HOST="${UNLIMITED_OCR_HOST:-127.0.0.1}"
PORT="${UNLIMITED_OCR_PORT:-10000}"
ALIAS="${UNLIMITED_OCR_ALIAS:-unlimited-ocr}"
SERVER_BIN="$LLAMA_CPP_DIR/llama-server.exe"
MODEL_FILE="$MODEL_DIR/Unlimited-OCR-Q4_K_M.gguf"
MMPROJ_FILE="$MODEL_DIR/mmproj-Unlimited-OCR-F16.gguf"

if ! [ -f "$SERVER_BIN" ]; then
  echo "llama-server.exe not found at $SERVER_BIN" >&2
  echo "Set LLAMA_CPP_DIR to the directory containing llama.cpp binaries." >&2
  exit 1
fi

if ! [ -f "$MODEL_FILE" ] || ! [ -f "$MMPROJ_FILE" ]; then
  echo "UnlimitedOCR model files not found under $MODEL_DIR" >&2
  echo "Expected: $MODEL_FILE and $MMPROJ_FILE" >&2
  exit 1
fi

mkdir -p "$ROOT/logs"

if curl -s --max-time 2 "http://$HOST:$PORT/v1/models" >/dev/null 2>&1; then
  echo "UnlimitedOCR server already running at http://$HOST:$PORT"
  exit 0
fi

echo "Starting llama.cpp UnlimitedOCR server on http://$HOST:$PORT (alias: $ALIAS)"
nohup "$SERVER_BIN" \
  -m "$MODEL_FILE" \
  --mmproj "$MMPROJ_FILE" \
  --host "$HOST" \
  --port "$PORT" \
  --alias "$ALIAS" \
  > "$ROOT/logs/unlimited-ocr-server.log" 2>&1 &
echo $! > "$ROOT/logs/unlimited-ocr-server.pid"

sleep 2
if curl -s --max-time 2 "http://$HOST:$PORT/v1/models" >/dev/null 2>&1; then
  echo "UnlimitedOCR server started (PID $(cat "$ROOT/logs/unlimited-ocr-server.pid"))"
else
  echo "UnlimitedOCR server may still be loading; check $ROOT/logs/unlimited-ocr-server.log" >&2
fi
