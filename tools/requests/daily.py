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


def commit_renders(worktree,label):
    """Commit this run's assets on the daily branch so the Mac can fetch and merge it. Never pushes."""
    paths=[x for x in ('v1','manifest.json','aliases.json','catalog.json') if (worktree/x).exists()]
    subprocess.run(['git','-C',str(worktree),'add','-A','--',*paths],check=True)
    if subprocess.run(['git','-C',str(worktree),'diff','--cached','--quiet']).returncode==0: return None
    subprocess.run(['git','-C',str(worktree),'commit','-q','-m',f'assets: requested vehicle renders and aliases ({label})'],check=True)
    return git(worktree,'rev-parse','--short','HEAD')


def overlay_nonsense():
    from interpret import load
    return {s for s,a in load().items() if a['decision']!='vehicle' or a.get('confidence')=='low'}


def ship(repo,branch,label):
    """Publish the daily branch if main lacks its work. Never raises."""
    try:
        from publish import pending,publish
        if not pending(repo,branch): return {'status':'nothing'}
        return publish(repo,branch,label)
    except PermissionError as exc: return {'status':'blocked','reason':str(exc)}
    except Exception as exc: return {'status':'failed','reason':f'{type(exc).__name__}: {exc}'}


def tell(report,held,nonsense,ready=0):
    from notify import send
    parts=[]
    if report.get('status')=='published':
        new=report['new'];parts.append(f"Cars: {len(new)} new published" + (f" ({', '.join(new)})" if new else '') + f", {len(report['aliases'])} aliases")
        if not report.get('live'): parts.append('not seen on Pages yet')
    elif ready:
        parts.append(f"Cars: {ready} ready, not published ({report.get('reason') or report.get('status')})")
    if held: parts.append(f"{len(held)} held: " + '; '.join(held))
    if nonsense: parts.append(f"{len(nonsense)} need you (can't tell what car): " + ', '.join(nonsense))
    if parts:
        try: send('. '.join(parts))
        except Exception as exc: print(f'Telegram failed: {type(exc).__name__}')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--date',default=dt.date.today().isoformat())
    p.add_argument('--repo',type=Path,default=DEFAULT_REPO)
    p.add_argument('--worktree',type=Path)
    p.add_argument('--deltas',type=Path,default=DEFAULT_DELTAS)
    p.add_argument('--reviews',type=Path,default=DEFAULT_REVIEWS)
    p.add_argument('--state-dir',type=Path)
    p.add_argument('--review-dir',type=Path,help='Exact output directory, for hourly runs')
    p.add_argument('--sender',type=Path,default=HOME/'Desktop/Galahad/scripts/telegram_send_document.py')
    p.add_argument('--force-prepare',action='store_true',help='Reclassify every request with --prepare-only')
    p.add_argument('--prepare-only',action='store_true',help='Export and classify, without generation or notification')
    p.add_argument('--no-notify',action='store_true',help='Build the local review without Telegram')
    p.add_argument('--use-export',action='store_true',help='Use this day\'s existing export for explicit local recovery')
    a=p.parse_args();dt.date.fromisoformat(a.date)
    if a.force_prepare and not a.prepare_only: p.error('--force-prepare requires --prepare-only')
    repo=a.repo.resolve()
    state_dir=a.state_dir or Path(git(repo,'rev-parse','--path-format=absolute','--git-common-dir'))/'requests-daily'
    state_dir.mkdir(parents=True,exist_ok=True)
    with (state_dir/'lock').open('a') as lock:
        try: fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError: raise SystemExit('A daily request run is already active.')
        streak=state_dir/'failure-streak'
        try:
            code=run(a,repo,state_dir)
            streak.write_text('0');return code
        except BaseException as exc:
            n=int(streak.read_text() or 0)+1 if streak.exists() else 1;streak.write_text(str(n))
            if n==3:
                try:
                    from notify import send;send(f'Cars: the Dell car routine failed 3 runs in a row ({type(exc).__name__}). Rendering and publishing are paused until it recovers.')
                except Exception: pass
            raise


def run(a,repo,state_dir):
    state_path=state_dir/'state.json'
    state=json.loads(state_path.read_text()) if state_path.exists() else {'handled':{},'assets':{},'notifications':{}}
    delta=a.deltas/f'delta-{a.date}';data=delta/'data';data.mkdir(parents=True,exist_ok=True)
    review_override=getattr(a,'review_dir',None)
    if not isinstance(review_override,(str,Path)): review_override=None
    review_dir=Path(review_override) if review_override else a.reviews/f'vehicle-requests-{a.date}'
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
    if getattr(a,'force_prepare',False) is True: selected={r['slug'] for r in rows}
    interpreted=[]
    try:
        import quota;quota.check()
        from interpret import interpret
        interpreted=interpret(rows,json.loads((HERE/'curated.json').read_text()),json.loads((worktree/'manifest.json').read_text()))
        if interpreted: print(f'Interpreted {len(interpreted)} request(s): {", ".join(interpreted)}')
    except Exception as exc:
        print(f'Interpretation skipped: {exc}')
    # Interpreted requests are worked until served once, even if the raw request was handled long ago.
    served=state.setdefault('interpreted_served',{})
    try:
        from interpret import overlay
        waiting={s for s in overlay(json.loads((worktree/'manifest.json').read_text()))['requests'] if s not in served}
    except Exception as exc:
        waiting=set();print(f'Interpreted backlog skipped: {exc}')
    waiting&={r['slug'] for r in rows}
    selected|=set(interpreted)|waiting
    if not selected:
        report=ship(repo,branch,'retry')
        if report.get('status')=='published': tell(report,[],[])
        print(f"No new requests. Publish: {report.get('status')}{(' ('+report['reason']+')') if report.get('reason') else ''}.");return 0
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
    existing_images={p.relative_to(worktree/'v1').as_posix() for p in (worktree/'v1').rglob('*.webp')}
    results=render(worktree,delta,jobs)
    new_images={p.relative_to(worktree/'v1').as_posix() for p in (worktree/'v1').rglob('*.webp')}-existing_images
    from visual import review as visual_review
    by={j['slug']:j for j in jobs}
    passed,retry,held=visual_review(worktree,delta,jobs,{p[:-5] for p in new_images})
    if retry:
        render(worktree,delta,[by[s] for s in retry])
        again={s for s in retry if (worktree/'v1'/f'{s}.webp').exists()}
        more,_,held2=visual_review(worktree,delta,jobs,again)
        passed+=more;held+=held2+[s for s in retry if s not in again]
    results=json.loads((delta/'render-results.json').read_text())
    gen.rebuild_manifest()
    new_images={f'{s}.webp' for s in passed}
    for job in jobs:
        if (worktree/'v1'/f"{job['slug']}.webp").exists() and results.get(job['slug'],{}).get('status') in ('generated','passed','reused'):
            added.update(add_aliases(worktree,job['aliases']))
            state['assets'][job['slug']]=str(worktree/'v1'/f"{job['slug']}.webp")
    save(added_path,added);gen.rebuild_manifest()
    from verify import verify
    verify(worktree,delta)
    page=build(worktree,delta,review_dir,a.date)
    stopped={s for j in jobs if results.get(j['slug'],{}).get('status')=='stopped' for s in j['request_slugs']}
    for slug in selected - stopped: state['handled'][slug]=a.date
    for slug in waiting|set(interpreted):
        job=next((j for j in jobs if slug in j['request_slugs']),None)
        done=job is None or (worktree/'v1'/f"{job['slug']}.webp").exists() or results.get(job['slug'],{}).get('status') in ('held','failed','unresolved')
        if slug not in stopped and done: served[slug]=a.date
    save(state_path,state)
    commit=commit_renders(worktree,f'Dell run {review_dir.name}')
    report=ship(repo,branch,f'Dell run {review_dir.name}')
    nonsense=[s for s in interpreted if s in overlay_nonsense()]
    held_notes=[f"{s} ({json.loads((delta/'render-results.json').read_text()).get(s,{}).get('reason','held')})" for s in held]
    if not a.no_notify and (new_images or added or held or nonsense or report.get('status')=='published'):
        tell(report,held_notes,nonsense,ready=len(new_images))
        if held and a.sender.exists():
            subprocess.run([sys.executable,str(a.sender),str(page),f'Vehicle requests {a.date}: {len(held)} held after two tries.'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    print(f"Review ready: {page}. New renders: {len(new_images)}, held: {len(held)}. Branch {branch}, commit {commit or 'none'}. Publish: {report.get('status')}{(' '+report['sha']) if report.get('sha') else ''}{(' ('+report['reason']+')') if report.get('reason') else ''}.")
    return 0


if __name__=='__main__':
    raise SystemExit(main())
