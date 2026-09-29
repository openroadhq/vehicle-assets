"""Credit tracking for the car routine: one row per run that spent anything, and a summary.

Razpe, 2026-09-29: track how many credits it uses; keep it efficient; have a maximum speed.
Codex exposes only a whole-percent weekly meter, so rows record the meter before and after
plus what was spent: images drawn, Codex checks and their tokens.
"""
import datetime as dt
import json
import os
from pathlib import Path

LOG=Path(os.environ.get('REQUESTS_USAGE_LOG',Path.home()/'Projects/vehicle-request-state/usage.jsonl'))
# Maximum speed. A flood of requests queues up instead of burning credits.
MAX_IMAGES_PER_RUN=int(os.environ.get('CARS_MAX_IMAGES_PER_RUN',6))
MAX_IMAGES_PER_DAY=int(os.environ.get('CARS_MAX_IMAGES_PER_DAY',40))
PAUSE_AT_WEEKLY_PERCENT=int(os.environ.get('CARS_PAUSE_AT_WEEKLY_PERCENT',60))


def rows():
    if not LOG.exists(): return []
    return [json.loads(l) for l in LOG.read_text().splitlines() if l.strip()]


def images_today():
    today=dt.datetime.now(dt.timezone.utc).date().isoformat()
    return sum(r.get('images',0) for r in rows() if r['at'][:10]==today)


def record(**row):
    row={'at':dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),**row}
    LOG.parent.mkdir(parents=True,exist_ok=True)
    with LOG.open('a') as f: f.write(json.dumps(row)+'\n')


def summary(days=7):
    since=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(days=days)).isoformat()
    rs=[r for r in rows() if r['at']>=since]
    total={k:sum(r.get(k) or 0 for r in rs) for k in ('images','checks','interpret_calls','codex_tokens','published')}
    meter=[r.get('weekly_after') for r in rs if r.get('weekly_after') is not None]
    return {'days':days,'runs_that_spent':len(rs),**total,'weekly_meter_now':meter[-1] if meter else None,
            'limits':{'per_run':MAX_IMAGES_PER_RUN,'per_day':MAX_IMAGES_PER_DAY,'pause_at_weekly_percent':PAUSE_AT_WEEKLY_PERCENT}}


if __name__=='__main__':
    for d in (1,7,30): print(json.dumps(summary(d)))
