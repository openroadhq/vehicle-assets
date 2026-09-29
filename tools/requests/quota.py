"""Read the same shared Codex meter used by the September render runs."""
import datetime as dt
import json
import math
import os
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


def subscription_usage():
    """Read the Dell account's live meter without relying on a Mac daemon."""
    from imagegen import load_cli
    cli=load_cli()
    auth=cli._load_auth()
    access,account,refresh=cli._extract_access_token(auth)
    url='https://chatgpt.com/backend-api/wham/usage'
    def read(token):
        headers={'Authorization':f'Bearer {token}','User-Agent':'vehicle-requests/1.0'}
        if account: headers['ChatGPT-Account-Id']=account
        with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=20) as response:
            return json.load(response)
    try:
        data=read(access)
    except urllib.error.HTTPError as exc:
        if exc.code!=401 or not refresh: raise
        refreshed=cli._refresh_access_token(refresh)
        cli._persist_refreshed_auth(auth,refreshed)
        data=read(refreshed['access_token'])
    rate=data['rate_limit']
    weekly=rate.get('secondary_window') or rate.get('primary_window')
    if not weekly or weekly.get('limit_window_seconds')!=604800: raise ValueError('Unexpected quota window')
    used=weekly['used_percent']
    primary=rate.get('primary_window') or {}
    if rate.get('limit_reached') or rate.get('allowed') is False or primary.get('used_percent',0)>=100:
        raise RuntimeError('Codex quota exhausted. Generation stopped.')
    return {'source':'Dell subscription usage endpoint','percent_used':used,
            'observed_at':dt.datetime.now(dt.timezone.utc).isoformat()}


def check():
    """Fail closed on unknown/stale usage, and at 90% used. No quota estimates."""
    evidence = None
    if os.environ.get('REQUESTS_QUOTA_SOURCE')=='subscription':
        try: evidence=subscription_usage()
        except Exception as exc:
            raise RuntimeError(f'Quota unavailable ({type(exc).__name__}). Generation stopped.') from None
    try:
        data = json.loads(MIRROR.read_text())
        row = next(p for p in data['providers'] if p.get('provider_id') == 'codex')
        if evidence is None and row.get('status') == 'known' and not row.get('stale') and fresh(row.get('last_updated')):
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
    if used >= 90:
        raise RuntimeError(f'Codex usage is {used}%, at or above the 90% stop threshold.')
    return evidence


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
