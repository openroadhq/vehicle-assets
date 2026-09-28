"""Read the same shared Codex meter used by the September render runs."""
import datetime as dt
import json
import math
from pathlib import Path
import urllib.request

MIRROR = Path.home() / 'Desktop/Galahad/mirror/data/usage.json'
LIMITS = 'http://127.0.0.1:6736/v1/limits'


def fresh(value):
    try:
        stamp = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return -60 <= (dt.datetime.now(dt.timezone.utc) - stamp).total_seconds() <= 900
    except (ValueError, TypeError, AttributeError):
        return False


def check():
    """Fail closed on unknown/stale usage, and at 85% used. No quota estimates."""
    evidence = None
    try:
        data = json.loads(MIRROR.read_text())
        row = next(p for p in data['providers'] if p.get('provider_id') == 'codex')
        if row.get('status') == 'known' and not row.get('stale') and fresh(row.get('last_updated')):
            evidence = {'source': str(MIRROR), 'percent_used': row['percent_used'],
                        'observed_at': row['last_updated']}
    except (OSError, ValueError, KeyError, StopIteration, TypeError):
        pass
    if evidence is None:
        try:
            with urllib.request.urlopen(LIMITS, timeout=10) as response:
                row = json.load(response)['providers']['codex']
            if not row.get('stale') and fresh(row.get('fetchedAt')):
                evidence = {'source': LIMITS, 'percent_used': row['resources']['weekly']['used'],
                            'observed_at': row['fetchedAt']}
        except (OSError, ValueError, KeyError, TypeError):
            pass
    if evidence is None:
        raise RuntimeError('Quota is unknown or stale. Generation stopped.')
    used = evidence['percent_used']
    if not isinstance(used, (int, float)) or not math.isfinite(used) or not 0 <= used <= 100:
        raise RuntimeError('Invalid quota reading. Generation stopped.')
    evidence['checked_at'] = dt.datetime.now(dt.timezone.utc).isoformat()
    evidence['meter'] = 'shared Codex weekly usage; image-specific remaining quota is not exposed'
    if used >= 85:
        raise RuntimeError(f'Codex usage is {used}%, at or above the 85% stop threshold.')
    return evidence


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
