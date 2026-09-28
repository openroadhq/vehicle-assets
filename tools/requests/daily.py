#!/usr/bin/env python3
"""Daily read-only request intake. Local assets and review only; never publishes."""
import argparse
import datetime as dt
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
HOME=Path.home()
DEFAULT_REPO=HOME/'Desktop/DriverV2.nosync/vehicle-assets'
DEFAULT_DELTAS=HOME/'Projects/506-2026-09-12/vehicle-requests'
DEFAULT_REVIEWS=HOME/'Desktop/Galahad/vault/projects'


def git(repo,*args):
    return subprocess.check_output(['git','-C',str(repo),*args],text=True).strip()


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n');temp.replace(path)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--date',default=dt.date.today().isoformat())
    p.add_argument('--repo',type=Path,default=DEFAULT_REPO)
    p.add_argument('--worktree',type=Path)
    p.add_argument('--deltas',type=Path,default=DEFAULT_DELTAS)
    p.add_argument('--reviews',type=Path,default=DEFAULT_REVIEWS)
    p.add_argument('--state-dir',type=Path)
    p.add_argument('--prepare-only',action='store_true',help='Export and classify, without generation or notification')
    p.add_argument('--no-notify',action='store_true',help='Build the local review without Telegram')
    p.add_argument('--use-export',action='store_true',help='Use this day\'s existing export for explicit local recovery')
    a=p.parse_args();dt.date.fromisoformat(a.date)
    repo=a.repo.resolve()
    state_dir=a.state_dir or Path(git(repo,'rev-parse','--path-format=absolute','--git-common-dir'))/'requests-daily'
    state_dir.mkdir(parents=True,exist_ok=True)
    with (state_dir/'lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise SystemExit('A daily request run is already active.')
        return run(a,repo,state_dir)


def run(a,repo,state_dir):
    state_path=state_dir/'state.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else {'handled':{},'assets':{},'notifications':{}}
    delta=a.deltas/f'delta-{a.date}';data=delta/'data';data.mkdir(parents=True,exist_ok=True)
    review_dir=a.reviews/f'vehicle-requests-{a.date}'
    branch=f'renders-{a.date}'
    worktree=(a.worktree or repo.parent/f'vehicle-assets-{a.date}').resolve()
    if not worktree.exists():
        subprocess.run(['git','-C',str(repo),'fetch','origin'],check=True)
        subprocess.run(['git','-C',str(repo),'worktree','add',str(worktree),'-b',branch,'origin/main'],check=True)
    elif git(worktree,'branch','--show-current')!=branch:
        raise SystemExit('Existing worktree is not on the expected daily branch.')
    base_path=delta/'base.json'
    if not base_path.exists():
        save(base_path,{'commit':git(worktree,'rev-parse','HEAD'),'branch':branch,'worktree':str(worktree)})
    base=json.loads(base_path.read_text())['commit']
    os.environ.update(REQUESTS_DELTA=str(delta),REQUESTS_DATE=a.date,REQUESTS_WORKTREE=str(worktree),REQUESTS_BASE=base)
    if not a.use_export:
        # Keep previous snapshots so repeated runs never discard a raw export.
        stamp=dt.datetime.now().strftime('%H%M%S-%f')
        for collection in ('vehicleModelRequests','vehicleModelRequestsAgg'):
            raw=data/f'{collection}-raw-{a.date}.json'
            if raw.exists():
                archive=data/'archive'/stamp;archive.mkdir(parents=True,exist_ok=True)
                shutil.move(str(raw),archive/raw.name)
        subprocess.run([sys.executable,str(HERE/'export.py')],check=True)
    subprocess.run([sys.executable,str(HERE/'classify.py')],check=True)
    rows=json.loads((data/f'classified-{a.date}.json').read_text())
    # A changed count is retained in the fresh export, but does not rerender a known slug.
    selected={r['slug'] for r in rows if r['slug'] not in state['handled']}
    today={slug for slug,date in state['handled'].items() if date==a.date}
    if not selected:
        print('No new requests. No rendering or Telegram message.');return 0
    from prepare import prepare
    from render import add_aliases,load_generator,render
    from review import build
    previous_jobs=json.loads((delta/'jobs.json').read_text()) if (delta/'jobs.json').exists() else []
    reviewed,jobs,aliases=prepare(delta,a.date,worktree,selected|today)
    combined={j['slug']:j for j in previous_jobs}
    combined.update({j['slug']:j for j in jobs})
    jobs=list(combined.values());save(delta/'jobs.json',jobs)
    original=delta/'original-manifest.json'
    if not original.exists(): original.write_text(git(worktree,'show',f'{base}:manifest.json')+'\n')
    prior=a.deltas/'delta-2026-09-17/data/classified-2026-09-17.json'
    if prior.exists():
        old={r['slug'] for r in json.loads(prior.read_text())}
        save(delta/'new-since-2026-09-17.json',[{'slug':r['slug'],'class':r['class'],'requests':r['requests']} for r in reviewed if r['slug'] not in old])
    if a.prepare_only:
        print(f'Prepared {len(selected)} new requests in {delta}.');return 0
    added_path=delta/'aliases-added.json'
    added=json.loads(added_path.read_text()) if added_path.exists() else {}
    added.update(add_aliases(worktree,aliases));save(added_path,added)
    gen=load_generator(worktree)
    # Reuse an unpublished local asset for a newly spelled request for the same model.
    for job in jobs:
        previous=state['assets'].get(job['slug'])
        dst=worktree/'v1'/f"{job['slug']}.webp"
        if previous and not dst.exists() and Path(previous).is_file():
            dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(previous,dst)
    gen.rebuild_manifest()
    results=render(worktree,delta,jobs)
    for job in jobs:
        if results.get(job['slug'],{}).get('status') in ('generated','passed','reused'):
            added.update(add_aliases(worktree,job['aliases']))
            state['assets'][job['slug']]=str(worktree/'v1'/f"{job['slug']}.webp")
    save(added_path,added);gen.rebuild_manifest()
    from verify import verify
    verify(worktree,delta)
    page=build(worktree,delta,review_dir,a.date)
    stopped={s for j in jobs if results.get(j['slug'],{}).get('status')=='stopped' for s in j['request_slugs']}
    for slug in selected-stopped: state['handled'][slug]=a.date
    # Durable send intent prevents duplicate messages after a crash or timeout.
    # An uncertain delivery is left for review instead of being resent blindly.
    digest=hashlib.sha256(page.read_bytes()).hexdigest()
    notify_key=f'{a.date}:{digest}'
    if not a.no_notify and notify_key not in state['notifications']:
        state['notifications'][notify_key]={'status':'sending','page':str(page)};save(state_path,state)
        sender=HOME/'Desktop/Galahad/scripts/telegram_send_document.py'
        with (delta/'telegram-send.log').open('a') as log:
            result=subprocess.run([sys.executable,str(sender),str(page),f'Vehicle requests {a.date}: local review, release approval required.'],stdout=log,stderr=subprocess.DEVNULL)
        state['notifications'][notify_key]['status']='sent' if result.returncode==0 else 'delivery-uncertain'
        save(state_path,state)
        if result.returncode: raise SystemExit('Telegram delivery uncertain. No automatic resend; inspect telegram-send.log.')
    else:
        save(state_path,state)
    print(f'Review ready: {page}. Local branch {branch}. Nothing pushed or scheduled.')
    return 0


if __name__=='__main__':
    raise SystemExit(main())
