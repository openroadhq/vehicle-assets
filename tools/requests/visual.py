"""Codex looks at every new render before it can ship: right vehicle, left-facing flat side profile,
not clipped, no text or logos, no artifacts. A reject gets one strict re-render; a second reject is held."""
import json
from pathlib import Path
import shutil
import tempfile
from PIL import Image
from codex_call import ask

SCHEMA={'type':'object','additionalProperties':False,'required':['verdict','reason'],
        'properties':{'verdict':{'type':'string','enum':['pass','reject']},'reason':{'type':'string'}}}
PROMPT='''You are the quality gate for a vehicle-image library used in a driving app. The attached image should be: {desc} (the driver typed: {names}).
Pass only if ALL hold: it shows that vehicle (right make, model, body style and era); it is a flat side profile facing LEFT (front of the vehicle on the left side of the image); the whole vehicle is visible and not cut off; there is no text, watermark, readable plate, or badge/logo on the body or grille (small emblems on wheel center caps are fine, they are invisible at app size); there are no rendering artifacts (melted or duplicated parts, extra wheels, broken edges, leftover background).
Otherwise reject and say why in one short sentence.'''


def _load(path,default):
    return json.loads(path.read_text()) if path.exists() else default


def _save(path,data):
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False)+'\n')


def check(image,job):
    with tempfile.TemporaryDirectory() as tmp:
        im=Image.open(image).convert('RGBA');bg=Image.new('RGBA',im.size,(255,255,255,255));bg.alpha_composite(im)
        flat=Path(tmp)/'check.png';bg.convert('RGB').save(flat)
        return ask(PROMPT.format(desc=job['description'],names='; '.join(job['names'][:3])),SCHEMA,[flat],timeout=300)


def review(worktree,delta,jobs,slugs):
    """Check the given new slugs. Returns (passed, retry, held) slug lists."""
    by={j['slug']:j for j in jobs}
    reviews=_load(delta/'visual-review.json',{});rejections=_load(delta/'visual-rejections.json',{})
    results=_load(delta/'render-results.json',{})
    passed,retry,held=[],[],[]
    for slug in sorted(slugs):
        path=worktree/'v1'/f'{slug}.webp'
        if not path.exists() or slug not in by: continue
        if reviews.get(slug,{}).get('verdict')=='passed':
            passed.append(slug);continue
        answer=check(path,by[slug])
        if answer['verdict']=='pass':
            reviews[slug]={'verdict':'passed','reason':answer['reason']};passed.append(slug)
            if slug in results: results[slug]['visual_review']='passed'
            continue
        out=delta/'rejected';out.mkdir(exist_ok=True)
        n=len(list(out.glob(slug.replace('/','--')+'-*.webp')))+1
        shutil.move(str(path),out/f"{slug.replace('/','--')}-{n}.webp")
        reviews[slug]={'verdict':'rejected','reason':answer['reason']}
        if slug not in rejections:
            rejections[slug]=answer['reason'];results.pop(slug,None);retry.append(slug)
        else:
            results[slug]={'status':'held','reason':'Visual check: '+answer['reason'],'attempts':2,'visual_review':'rejected'}
            held.append(slug)
    _save(delta/'visual-review.json',reviews);_save(delta/'visual-rejections.json',rejections);_save(delta/'render-results.json',results)
    return passed,retry,held
