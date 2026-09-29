"""Publish a daily renders branch to vehicle-assets main from the Dell, with the Sep 28 checks.

Merge into a fresh worktree of main, validate, push over the Dell's repo-only deploy key (never force),
wait for GitHub Pages to serve the new files, byte-compare them, and purge jsDelivr.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

REMOTE=os.environ.get('VEHICLE_ASSETS_PUSH_REMOTE','git@github-vehicle-assets:openroadhq/vehicle-assets.git')
PAGES='https://openroadhq.github.io/vehicle-assets'
PURGE='https://purge.jsdelivr.net/gh/openroadhq/vehicle-assets@main/'


def git(repo,*args,check=True):
    return subprocess.run(['git','-C',str(repo),*args],check=check,capture_output=True,text=True)


def unresolved(m):
    ok=set(m['vehicles'])|set(m['generations'])
    return {k for k,v in m['aliases'].items() if v not in ok}


def fetch_main(repo):
    r=git(repo,'fetch','-q',REMOTE,'main:refs/remotes/publish/main',check=False)
    if r.returncode: raise PermissionError('Cannot reach vehicle-assets over the Dell deploy key')


def pending(repo,branch):
    """True when the branch holds work that main does not have yet."""
    fetch_main(repo)
    return git(repo,'merge-base','--is-ancestor',branch,'publish/main',check=False).returncode!=0


def get(url,timeout=30):
    with urllib.request.urlopen(url,timeout=timeout) as r: return r.read()


def publish(repo,branch,label):
    fetch_main(repo)
    with tempfile.TemporaryDirectory(prefix='vehicle-publish-') as tmp:
        wt=Path(tmp)/'wt'
        git(repo,'worktree','add','-q','--detach',str(wt),'publish/main')
        try:
            before=json.loads(git(wt,'show','publish/main:manifest.json').stdout)
            git(wt,'merge','-q','--no-ff',branch,'-m',f'assets: publish requested vehicle renders ({label})')
            if not git(wt,'diff','--name-only','publish/main','HEAD').stdout.strip():
                return {'status':'nothing'}
            m=json.loads((wt/'manifest.json').read_text());json.loads((wt/'catalog.json').read_text())
            json.loads((wt/'aliases.json').read_text())
            missing=[k for k in m['vehicles'] if not (wt/'v1'/f'{k}.webp').exists()]
            if missing: raise ValueError(f'Manifest lists missing files: {missing[:5]}')
            newly=unresolved(m)-unresolved(before)
            if newly: raise ValueError(f'Newly unresolved aliases: {sorted(newly)[:5]}')
            lost=[k for k in before['vehicles'] if k not in m['vehicles']]
            if lost: raise ValueError(f'Vehicles would disappear: {lost[:5]}')
            new=sorted(set(m['vehicles'])-set(before['vehicles']))
            aliases=sorted(set(m['aliases'])-set(before['aliases']))
            sha=git(wt,'rev-parse','--short','HEAD').stdout.strip()
            push=git(wt,'push','-q',REMOTE,'HEAD:main',check=False)
            if push.returncode: raise RuntimeError('Push rejected (main moved or key refused); next run retries')
            live=None
            for _ in range(40):
                try:
                    lm=json.loads(get(f'{PAGES}/manifest.json?t={time.time_ns()}'))
                    if all(k in lm['vehicles'] for k in new) and all(a in lm['aliases'] for a in aliases):
                        live=time.strftime('%H:%M UTC',time.gmtime());break
                except Exception: pass
                time.sleep(20)
            same=[s for s in new[:2] if get(f'{PAGES}/v1/{s}.webp?t={time.time_ns()}')==(wt/'v1'/f'{s}.webp').read_bytes()] if live else []
            purged=[]
            for f in ('manifest.json','catalog.json','aliases.json'):
                try: json.loads(get(PURGE+f));purged.append(f)
                except Exception: pass
            return {'status':'published','sha':sha,'new':new,'aliases':aliases,'live':live,
                    'byte_identical':same,'purged':purged}
        finally:
            git(repo,'worktree','remove','--force',str(wt),check=False)
