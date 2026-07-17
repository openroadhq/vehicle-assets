#!/bin/zsh
# Grind the car list to completion, however long the quota takes.
#
# render_worker gives up on a car after MAX_429_RETRIES (~1h of backoff) and
# exits — fine for a burst, useless overnight: the workers all quit before
# ChatGPT's rolling quota reopens. This just keeps re-running them.
#
# Every round rebuilds the pending list from the FILESYSTEM (never from slice
# bookkeeping — that silently orphaned 680 cars once). A car is pending iff it
# has no finished .webp and no raw render waiting. So retries, failures and
# quota-skips all self-heal, and finished work is never redone.
#
# Usage: nohup tools/supervisor.sh > supervisor.log 2>&1 &
set -u
REPO=~/Desktop/DriverV2.nosync/vehicle-assets
SP="/private/tmp/claude-501/-Users-razpe-Desktop/32217176-c0e7-4227-b97e-28881e8ea27a/scratchpad"
WORKERS=4
ROUND=0

cd "$REPO"
while true; do
  ROUND=$((ROUND + 1))

  python3 - "$SP" <<'EOF'
import sys
from pathlib import Path
SP = Path(sys.argv[1]); V1 = Path('v1')
full = {l.split('|')[0]: l for l in Path('cars-full.txt').read_text().splitlines() if '|' in l}
live = {str(p.relative_to(V1))[:-5] for p in V1.rglob('*.webp')}
staged = {p.stem.replace('__','/') for p in SP.glob('stage/*.png')}
rem = [full[s] for s in sorted(full) if s not in live and s not in staged]
(SP/'pending.txt').write_text('\n'.join(rem) + ('\n' if rem else ''))
for i in range(4):
    (SP/f'p-{i}.txt').write_text('\n'.join(rem[i::4]) + ('\n' if rem else ''))
print(f"pending={len(rem)} live={len(live)} staged={len(staged)}")
EOF

  PENDING=$(grep -c '|' "$SP/pending.txt" 2>/dev/null || echo 0)
  echo "=== round $ROUND @ $(date '+%H:%M:%S') — $PENDING pending ==="

  if [ "$PENDING" -eq 0 ]; then
    # Nothing left to render. Wait for the cutout to drain, then we're done.
    if ! ls "$SP"/stage/*.png >/dev/null 2>&1; then
      echo "COMPLETE @ $(date '+%H:%M:%S') — $(ls v1/*/*.webp | wc -l | tr -d ' ') cars live"
      exit 0
    fi
    echo "renders done; waiting on cutout backlog"
    sleep 120
    continue
  fi

  for i in 0 1 2 3; do
    nohup tools/render_worker.py --list "$SP/p-$i.txt" --stage "$SP/stage" --id p$i \
      > "$SP/wp-$i.log" 2>&1 &
  done
  wait   # workers exit fast now: either done, or exit 42 = quota shut

  DONE=$(grep -h '] ok ' "$SP"/wp-*.log 2>/dev/null | wc -l | tr -d ' ')
  SHUT=$(grep -hc 'QUOTA SHUT' "$SP"/wp-*.log 2>/dev/null | paste -sd+ - | bc)
  echo "round $ROUND rendered $DONE (quota-shut workers: ${SHUT:-0})"
  # Quota is account-wide, so one shut worker means the window is closed.
  # Idle instead of hammering — the cars stay pending and return next round.
  if [ "${SHUT:-0}" -gt 0 ] || [ "$DONE" -eq 0 ]; then
    # The 429 body carries resets_at. The ChatGPT Plus image cap is WEEKLY, not
    # a rolling window — on 2026-07-16 it was ~6.7 days out. Polling every 15min
    # for a week is 640 pointless rounds, so ask when it actually reopens and
    # sleep in 1h chunks until then (1h, not until-reset, so a manual `codex
    # login`, a plan change, or an early reset is picked up within the hour).
    RESET=$(~/Desktop/Galahad/tools/chatgpt-imagegen/chatgpt-imagegen "ping" \
              -o /tmp/_quota_probe.png --size 1024x1024 --timeout 30 2>&1 \
            | grep -oE '"resets_in_seconds":[0-9]+' | grep -oE '[0-9]+$')
    if [ -n "${RESET:-}" ] && [ "$RESET" -gt 3600 ]; then
      echo "quota shut — reopens in $((RESET/3600))h ($(date -v+${RESET}S '+%a %b %d %H:%M')); sleeping 1h"
      sleep 3600
    else
      echo "quota shut — idling 15m"
      sleep 900
    fi
  fi
done
