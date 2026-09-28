#!/bin/bash
# Run directly; does not start another Codex session or install a schedule.
set -euo pipefail
TOOLS_DIR="$(cd "$(dirname "$0")" && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
exec "${REQUESTS_PYTHON:-python3}" "$TOOLS_DIR/requests/daily.py" "$@"
