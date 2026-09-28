#!/usr/bin/env bash
set -euo pipefail

ROOT="${VEHICLE_ASSETS_ROOT:-$HOME/Projects/vehicle-assets}"
PYTHON="${VEHICLE_REQUESTS_PYTHON:-$HOME/Projects/vehicle-venv/bin/python}"
DATE="${REQUESTS_DATE:-$(date +%F)}"
STAMP="${REQUESTS_REVIEW_STAMP:-$(date +%F-%H)}"
REVIEW_ROOT="${VEHICLE_REVIEWS_ROOT:-$HOME/Projects/vehicle-reviews}"
DELTA_ROOT="${VEHICLE_DELTAS_ROOT:-$HOME/Projects/vehicle-request-deltas}"
STATE_ROOT="${VEHICLE_STATE_ROOT:-$HOME/Projects/vehicle-request-state}"
export PATH="$HOME/Projects/tools/webp/usr/bin:$PATH"
export REQUESTS_PYTHON="$PYTHON"
export VEHICLE_VENV="${VEHICLE_VENV:-$HOME/Projects/vehicle-venv}"
export CIMG="${CIMG:-$HOME/Projects/tools/vehicle-imagegen}"
export REQUESTS_QUOTA_SOURCE="${REQUESTS_QUOTA_SOURCE:-subscription}"

exec "$ROOT/tools/requests-daily.sh" \
  --repo "$ROOT" \
  --reviews "$REVIEW_ROOT" \
  --deltas "$DELTA_ROOT" \
  --state-dir "$STATE_ROOT" \
  --review-dir "$REVIEW_ROOT/$STAMP" \
  --sender "$HOME/Projects/tools/send-vehicle-review.py" \
  "$@"
