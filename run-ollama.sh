#!/usr/bin/env bash
set -euo pipefail
D1_PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -f "$D1_PROJECT_DIR/.ollama-local.env" ]]; then
  source "$D1_PROJECT_DIR/.ollama-local.env"
fi
export OLLAMA_HOST="${OLLAMA_HOST:-127.0.0.1:11434}"
if [[ -n "${OLLAMA_MODELS:-}" ]]; then export OLLAMA_MODELS; fi
D1_OLLAMA_EXECUTABLE="${D1_OLLAMA_BIN:-$(command -v ollama)}"
exec "$D1_OLLAMA_EXECUTABLE" "$@"
