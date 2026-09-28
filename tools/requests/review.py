"""Portable, self-contained phone review and transparent-cutout contact sheets."""
import base64
import html
import json
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def build(worktree, delta, destination, date):
    destination.mkdir(parents=True,exist_ok=True)
    jobs=json.loads((delta/'jobs.json').read_text())
    results=json.loads((delta/'render-results.json').read_text()) if (delta/'render-results.json').exists() else {}
    visual_path=delta/'visual-review.json'
    if visual_path.exists():
        for slug,verdict in json.loads(visual_path.read_text()).items():
            if slug in results: results[slug]['visual_review']=verdict['verdict']
    aliases=json.loads((delta/'aliases-added.json').read_text()) if (delta/'aliases-added.json').exists() else {}
    summary=json.loads((delta/'preparation.json').read_text())
    def esc(value): return html.escape(str(value))
    cards=[];images=[]
    for j in jobs:
        slug=j['slug'];r=results.get(slug,{'status':'pending'})
        p=worktree/'v1'/f'{slug}.webp'
        visual=r.get('visual_review','pending')
        good=p.exists() and r['status'] in ('generated','passed','reused') and visual!='rejected'
        figure=''
        if good:
            b64=base64.b64encode(p.read_bytes()).decode()
            figure=f'<div class="picture"><img src="data:image/webp;base64,{b64}" alt="{esc(j["description"])}"></div>'
            images.append((j,p))
        status='Visual QC passed' if visual=='passed' else ('Awaiting visual review' if good else r['status'].title())
        reason=r.get('reason') or j.get('blocked') or ''
        cards.append(f'<article>{figure}<h2>{esc(slug)}</h2><p>{esc("; ".join(j["names"]))}</p><p class="meta">{j["requests"]} request(s) · {esc(status)} · {r.get("attempts",0)} attempt(s)</p><p>{esc(reason)}</p></article>')
    alias_html=''.join(f'<li><code>{esc(k)}</code><span> → </span><code>{esc(v)}</code></li>' for k,v in sorted(aliases.items()))
    new_path=delta/'new-since-2026-09-17.json'
    new=json.loads(new_path.read_text()) if new_path.exists() else []
    new_html=''.join(f'<li>{esc(r["slug"])}: {esc(r["class"])}</li>' for r in new)
    refs_path=delta/'source-references.json'
    refs=json.loads(refs_path.read_text()) if refs_path.exists() else {}
    refs_html=''.join(f'<li><a href="{esc(url)}">{esc(slug)}</a></li>' for slug,url in refs.items())
    counts=' · '.join(f'{k}: {v}' for k,v in summary['counts'].items())
    good_count=sum(r.get('visual_review')=='passed' for r in results.values())
    review=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Vehicle requests · {date}</title>
<style>:root{{color-scheme:light}}*{{box-sizing:border-box}}body{{margin:0;background:#f7f7f4;color:#20211e;font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}main{{max-width:740px;margin:auto;padding:28px 16px 60px}}h1{{font-size:30px;line-height:1.15;margin:8px 0 20px}}h2{{font-size:19px;overflow-wrap:anywhere}}p{{margin:10px 0}}article{{margin:24px 0;padding:16px;background:white;border-radius:12px}}.picture{{background:repeating-conic-gradient(#eee 0 25%,#fafafa 0 50%) 0/20px 20px;border-radius:8px}}img{{display:block;width:100%;height:auto}}.meta{{font-size:14px;color:#555}}code{{font-size:14px;overflow-wrap:anywhere}}li{{margin:12px 0;overflow-wrap:anywhere}}ul{{padding-left:20px}}summary{{cursor:pointer;font-weight:600}}a{{color:#165b91}}</style>
<main><p class="meta">OPEN ROAD · {date}</p><h1>Requested vehicles</h1><p>Local review only. Release chat reviews every render before publication.</p><p>{len(images)} images available · {good_count} visually passed · {len(aliases)} new aliases</p><p class="meta">{summary['rows']} distinct requested names. {esc(counts)}</p><p>House style: left-facing flat side profile, transparent WebP, 1024 px wide.</p>
{''.join(cards)}<h2>New aliases</h2><ul>{alias_html or '<li>None.</li>'}</ul>
<details><summary>{len(new)} names new since September 17</summary><ul>{new_html}</ul></details>
<details><summary>Model reference checks</summary><ul>{refs_html}</ul></details>
<h2>Publishing note</h2><p>Nothing has been pushed, merged, or purged. GitHub Pages is the primary asset host. jsDelivr has exceeded its 50 MB package limit and cannot reliably serve new files.</p></main></html>'''
    (destination/'review.html').write_text(review)
    # Every model is also large enough for inspection in paginated 6-item sheets.
    font_path='/System/Library/Fonts/Supplemental/Arial.ttf'
    font=ImageFont.truetype(font_path,20) if Path(font_path).exists() else ImageFont.load_default()
    def sheet(entries,cols,width,path):
        cw=width//cols;ch=int(cw*.75)
        image=Image.new('RGB',(width,max(1,math.ceil(len(entries)/cols))*ch),'#f5f5f2');draw=ImageDraw.Draw(image)
        for i,(job,p) in enumerate(entries):
            x=(i%cols)*cw;y=(i//cols)*ch
            vehicle=Image.open(p).convert('RGBA');vehicle.thumbnail((cw-24,ch-64))
            image.paste(vehicle,(x+(cw-vehicle.width)//2,y+8),vehicle)
            draw.text((x+12,y+ch-47),job['slug'],fill='#252525',font=font)
            draw.text((x+12,y+ch-23),f"{job['requests']} request(s)",fill='#555555',font=font)
        image.save(path)
    sheet(images,3,1800,destination/'contact-sheet.png')
    for n in range(0,len(images),6): sheet(images[n:n+6],2,1600,destination/f'inspect-{n//6+1:02d}.png')
    return destination/'review.html'


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('worktree',type=Path);p.add_argument('delta',type=Path);p.add_argument('destination',type=Path);p.add_argument('date')
    a=p.parse_args(); print(build(a.worktree,a.delta,a.destination,a.date))
