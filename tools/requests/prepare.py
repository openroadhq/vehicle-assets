"""Review known exceptions, deduplicate render jobs, preserve every existing alias."""
import collections
import csv
import json
import os
from pathlib import Path
import re
import sys
sys.path.insert(0, str(Path(__file__).parent))
import classify as classifier


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def prepare(delta, date, worktree, selected=None):
    rows = json.loads((delta / 'data' / f'classified-{date}.json').read_text())
    manifest = json.loads((worktree / 'manifest.json').read_text())
    rules = json.loads((Path(__file__).parent / 'curated.json').read_text())
    from interpret import overlay
    extra = overlay(manifest)
    for slug, rule in extra['requests'].items():
        current = rules['requests'].get(slug, {})
        if not (current.get('target') or (current.get('candidate') and not current.get('blocked'))):
            rules['requests'][slug] = rule
    for key, brief in extra['briefs'].items():
        rules['briefs'].setdefault(key, brief)
    aliases, jobs = {}, {}
    for row in rows:
        original = row['candidate']
        rule = rules['requests'].get(row['slug'], {})
        target = rule.get('target') or rules['targets'].get(original)
        candidate = rule.get('candidate') or rules['render_overrides'].get(original)
        row['reason'] = rule.get('reason', '')
        row['original_candidate'] = original
        if rule.get('junk'):
            row.update({'class':'JUNK', 'candidate':'', 'alias':None, 'matched':'', 'reason':rule['junk']})
        elif rule.get('blocked'):
            row.update({'class':'MISSING', 'candidate':candidate or original, 'alias':None, 'blocked':rule['blocked']})
        elif target:
            if not classifier.resolve(target, row['fields'].get('year'), manifest):
                raise ValueError(f'Unresolved curated target: {target}')
            row.update({'class':'ALIAS GAP', 'matched':target, 'alias':{original:target} if original else {}, 'target':target})
        elif candidate:
            row.update({'class':'MISSING', 'candidate':candidate, 'alias':None, 'matched':candidate})
            if classifier.resolve(candidate, row['fields'].get('year'), manifest):
                row.update({'class':'ALIAS GAP', 'alias':{original:candidate} if original != candidate else {}, 'target':candidate})
        elif row['class'] == 'ALIAS GAP':
            # A new named body style must not inherit a sedan/coupe by prefix.
            body = re.search(r'\b(cabriolet|convertible|sportback|avant|tourer|coupe|wagon|regular-cab|supercab)\b', original)
            if body and original not in rules['targets']:
                row.update({'class':'MISSING', 'alias':None, 'matched':original})
            else:
                row['target'] = next(iter(row['alias'].values()))
        if selected is not None and row['slug'] not in selected:
            continue
        if row['class'] == 'ALIAS GAP':
            target = row['target']
            proposed = dict(row.get('alias') or {})
            # Retain raw-field keys too, since the app can send misspelled makes.
            f = row['fields']
            make, model, trim = (classifier.slug_component(f.get(k)) for k in ('make','model','trim'))
            if make and model:
                proposed[f'{make}/{model}' + (f'-{trim}' if trim else '')] = target
            for key, value in proposed.items():
                if key and key != value and key not in manifest['vehicles'] and key not in manifest['aliases']:
                    if key in aliases and aliases[key] != value:
                        raise ValueError(f'Conflicting alias proposal: {key}')
                    aliases[key] = value
        if row['class'] == 'MISSING':
            slug = row['candidate']
            if not re.fullmatch(r'[a-z0-9][a-z0-9-]*/[a-z0-9][a-z0-9.-]*', slug):
                raise ValueError(f'Unsafe asset slug: {slug}')
            brief = rules['briefs'].get(slug)
            fields = row['fields']
            desc = brief[0] if brief else ' '.join(str(fields.get(k) or '') for k in ['year','make','model','trim']).strip()
            two = brief[1] if brief else slug.split('/')[0] in {'honda-motorcycles','yamaha','ktm','triumph','kawasaki','ducati','aprilia','harley-davidson','senzo','angwatt'}
            entry = jobs.setdefault(slug, {'slug':slug, 'description':desc, 'two_wheel':two,
                'requests':0,'names':[], 'request_slugs':[], 'aliases':{}, 'blocked':row.get('blocked')})
            entry['requests'] += max(row['requests'], row['agg_request_count'])
            entry['names'].append(fields.get('rawText') or row['slug'])
            entry['request_slugs'].append(row['slug'])
            if original and original != slug:
                entry['aliases'][original] = slug
            make, model, trim = (classifier.slug_component(fields.get(k)) for k in ('make','model','trim'))
            if make and model:
                key = f'{make}/{model}' + (f'-{trim}' if trim else '')
                if key != slug:
                    entry['aliases'][key] = slug
    jobs = sorted(jobs.values(), key=lambda x:(-x['requests'],x['slug']))
    write(delta/'classified-reviewed.json', rows)
    with (delta/'triage-reviewed.csv').open('w',newline='') as handle:
        writer=csv.writer(handle);writer.writerow(['slug','requests','class','candidate','target','reason'])
        for row in rows:
            writer.writerow([row['slug'],max(row['requests'],row['agg_request_count']),row['class'],row['candidate'],row.get('target',row['matched']),row.get('blocked') or row.get('reason','')])
    write(delta/'jobs.json', jobs)
    write(delta/'aliases-proposed.json', dict(sorted(aliases.items())))
    for two, name in [(False,'four-wheel'),(True,'two-wheel')]:
        (delta/f'{name}.txt').write_text(''.join(f"{j['slug']}|{j['description']}\n" for j in jobs if j['two_wheel']==two and not j['blocked']))
    counts = dict(collections.Counter(r['class'] for r in rows))
    summary = {'counts':counts,'rows':len(rows),'aliases':len(aliases),'render_jobs':len(jobs),
               'renderable':sum(not j['blocked'] for j in jobs), 'unresolved':sum(bool(j['blocked']) for j in jobs)}
    write(delta/'preparation.json',summary)
    print(json.dumps(summary))
    return rows, jobs, aliases


if __name__ == '__main__':
    prepare(Path(os.environ['REQUESTS_DELTA']),os.environ['REQUESTS_DATE'],Path(os.environ['REQUESTS_WORKTREE']))
