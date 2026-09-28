"""Run the established generator with durable attempts and per-image quota checks."""
import concurrent.futures
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
import sys
sys.path.insert(0,str(Path(__file__).parent))
import quota
from prepare import write


def load_generator(worktree):
    spec=importlib.util.spec_from_file_location('vehicle_generator',worktree/'tools/generate.py')
    gen=importlib.util.module_from_spec(spec); spec.loader.exec_module(gen)
    return gen


def add_aliases(worktree, additions):
    path=worktree/'aliases.json'
    current=json.loads(path.read_text()); manifest=json.loads((worktree/'manifest.json').read_text())
    added={}
    for key,target in additions.items():
        if key in current or key in manifest['aliases'] or key in manifest['vehicles']:
            continue
        if target not in manifest['vehicles'] and target not in manifest['generations'] and target not in manifest['aliases']:
            raise ValueError(f'Unresolved alias target {key} -> {target}')
        current[key]=target; added[key]=target
    if added: path.write_text(json.dumps(dict(sorted(current.items())), indent=1) + "\n")
    return added


def render(worktree,delta,jobs,workers=2):
    with (delta/'render.lock').open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('A render batch is already active for this delta')
        return _render(worktree,delta,jobs,workers)


def _render(worktree,delta,jobs,workers=2):
    gen=load_generator(worktree)
    shared=Path(os.environ.get('VEHICLE_VENV',worktree.parent/'vehicle-assets/tools/.venv'))
    if shared.exists(): gen.VENV=shared
    py=gen.ensure_venv()
    gen_raw=gen.generate_raw; gen_cut=gen.cutout
    local=threading.local(); lock=threading.Lock(); cut_lock=threading.Lock(); stop=threading.Event()
    result_path=delta/'render-results.json'
    results=json.loads(result_path.read_text()) if result_path.exists() else {}
    attempts_path=delta/'attempts.json'
    attempts=json.loads(attempts_path.read_text()) if attempts_path.exists() else {}
    (delta/'raw').mkdir(exist_ok=True)
    (delta/'cutouts').mkdir(exist_ok=True)
    def raw(prompt,out):
        slug=local.slug
        with lock:
            reading=quota.check()
            with (delta/'quota.jsonl').open('a') as f: f.write(json.dumps(reading)+'\n')
            if stop.is_set(): raise RuntimeError('Generation stopped by another quota check')
            count=attempts.get(slug,0)
            if count>=2: raise RuntimeError('Two-attempt limit reached, including visual retries')
            attempts[slug]=count+1;write(attempts_path,attempts)
            stem=f"{slug.replace('/','--')}-{count+1}"
            (delta/'raw'/f'{stem}.prompt.txt').write_text(prompt+'\n')
        gen_raw(prompt,out)
        if out.resolve() != (delta/'raw'/f'{stem}.png').resolve():
            shutil.copy2(out,delta/'raw'/f'{stem}.png')
    def cut(py,src,dst):
        with cut_lock:
            gen.wait_for_build_clear()
            gen_cut(py,src,dst)
            shutil.copy2(dst,delta/'cutouts'/f"{local.slug.replace('/','--')}-{attempts[local.slug]}.png")
    gen.cutout=cut
    # Remote image requests can continue while the single local cutout waits for Xcode.
    pool=concurrent.futures.ThreadPoolExecutor(max_workers=workers)
    initial_futures={}
    rejection_path=delta/'visual-rejections.json'
    rejections=json.loads(rejection_path.read_text()) if rejection_path.exists() else {}
    def initial(j):
        local.slug=j['slug']
        existing=delta/'raw'/f"{j['slug'].replace('/','--')}-1.png"
        if existing.exists() and j['slug'] not in rejections: return existing
        if j['slug'] in rejections:
            existing=delta/'raw'/f"{j['slug'].replace('/','--')}-2.png"
            if existing.exists(): return existing
            template=gen.TWO_WHEEL_STRICT_PROMPT_TEMPLATE if j['two_wheel'] else gen.CAR_STRICT_PROMPT_TEMPLATE
            raw(template.format(desc=j['description'])+' Visual correction: '+rejections[j['slug']],existing)
            return existing
        template=gen.TWO_WHEEL_PROMPT_TEMPLATE if j['two_wheel'] else gen.PROMPT_TEMPLATE
        raw(template.format(desc=j['description']),existing)
        return existing
    for j in jobs:
        if (j['slug'] not in results or results[j['slug']].get('status') == 'stopped') and not j.get('blocked') and not (worktree/'v1'/f"{j['slug']}.webp").exists():
            initial_futures[j['slug']]=pool.submit(initial,j)
    consumed=set()
    def consume_or_retry(prompt,out):
        slug=local.slug
        if slug in initial_futures and slug not in consumed:
            consumed.add(slug)
            shutil.copy2(initial_futures[slug].result(),out)
        else:
            raw(prompt,out)
    gen.generate_raw=consume_or_retry
    def job(j):
        slug=j['slug'];local.slug=slug
        if slug in results and results[slug].get('status') != 'stopped': return
        if j.get('blocked'):
            outcome={'status':'unresolved','reason':j['blocked'],'attempts':0}
        else:
            try:
                passed=gen.process(slug,j['description'],False,py,j['two_wheel'],False)
                outcome={'status':'generated' if passed else 'failed','attempts':attempts.get(slug,0),
                         'visual_review':'pending'}
            except Exception as exc:
                reason=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
                if 'Quota' in reason or 'quota' in reason or '85%' in reason: stop.set()
                outcome={'status':'stopped' if stop.is_set() else 'failed','reason':reason,'attempts':attempts.get(slug,0)}
            # A backend generation failure gets one strict retry too.
            if outcome['status']=='failed' and attempts.get(slug,0)<2:
                try:
                    passed=gen.process(slug,j['description'],False,py,j['two_wheel'],True)
                    outcome={'status':'generated' if passed else 'failed','attempts':attempts.get(slug,0),'visual_review':'pending'}
                except Exception as exc:
                    reason=str(exc) if isinstance(exc,RuntimeError) else type(exc).__name__
                    if 'Quota' in reason or 'quota' in reason or '85%' in reason: stop.set()
                    outcome={'status':'stopped' if stop.is_set() else 'failed','reason':reason,'attempts':attempts.get(slug,0)}
        with lock:
            results[slug]=outcome;write(result_path,results)
            print(slug,json.dumps(outcome),flush=True)
    try:
        for j in jobs: job(j)
    finally:
        pool.shutdown(wait=True)
    gen.rebuild_manifest()
    return results


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('worktree',type=Path);p.add_argument('delta',type=Path);p.add_argument('--workers',type=int,default=2)
    a=p.parse_args();render(a.worktree,a.delta,json.loads((a.delta/'jobs.json').read_text()),a.workers)
