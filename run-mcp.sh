#!/usr/bin/env bash
set -euo pipefail
D1_PROJECT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ -d "$D1_PROJECT_DIR/.runtime/playwright" ]]; then
  export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$D1_PROJECT_DIR/.runtime/playwright}"
fi
exec "$D1_PROJECT_DIR/.venv/bin/python" -m d1_computer_use_mcp.server "$@"
