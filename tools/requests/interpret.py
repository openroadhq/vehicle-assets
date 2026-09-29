"""Work out what car each unserved request means, the way a person would, and remember the answer.

Razpe, 2026-09-29: "if we can interpret what they meant, even if they type in some shit like a
Cessna, we should end up generating an image for them." Only true nonsense is held for him.
Answers are cached per request slug in the state dir, so each request is asked about once.
Curated targets and candidates in curated.json still win; curated junk/blocked calls are
re-asked, because the rule changed.
"""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parent))
import classify as classifier
from codex_call import ask

SCHEMA={'type':'object','additionalProperties':False,'required':['answers'],'properties':{'answers':{'type':'array','items':{
    'type':'object','additionalProperties':False,
    'required':['slug','decision','confidence','existing','make','model','year','kind','description','reason'],
    'properties':{
        'slug':{'type':'string'},
        'decision':{'type':'string','enum':['vehicle','nonsense']},
        'confidence':{'type':'string','enum':['high','medium','low']},
        'existing':{'type':'string'},
        'make':{'type':'string'},'model':{'type':'string'},
        'year':{'type':'integer'},
        'kind':{'type':'string','enum':['car','truck','van','motorcycle','scooter','bicycle','aircraft','boat','other']},
        'description':{'type':'string'},'reason':{'type':'string'}}}}}}

PROMPT='''You map what drivers typed in a car app to one real vehicle, so we can draw a side-profile picture of it.
For each request below, decide what vehicle the person most likely drives. Be a helpful human: fix spelling
("Hyunday" is Hyundai, "Lads" is Lada), pull the model out of the wrong field ("BMW X3 M40i" typed as the make),
and when they only gave a body type ("Acura Sedan 2018", "Hyundai SUV 2013") pick the single most likely model
for that make, market and year. A plane, boat or bike is fine: answer with that vehicle. Only say "nonsense" when
no real vehicle can be identified at all (random letters, jokes, placeholders like "na na").

For each answer give:
- make and model: the official names, model without trim (e.g. make "Audi", model "A6"; make "Toyota", model "Vios").
- year: the year they gave, or your best guess of a typical year if they gave none; 0 only for nonsense.
- kind: car, truck, van, motorcycle, scooter, bicycle, aircraft, boat or other.
- description: one line for an illustrator, precise enough to draw the right generation and body, for example
  "2019 Audi A6 C8 four-door sedan" or "1971 Cessna 172 single-engine high-wing light aircraft".
- confidence: high when the vehicle is clear, medium when you picked the most likely model from vague input,
  low when it is really a guess (e.g. an unknown model name you had to replace).
- existing: if one of the images we already have (listed per request) fits this vehicle and year, its exact key;
  otherwise "". Prefer an existing image over a new one when it is the same vehicle and body.
- reason: a few words on why.
Return one answer per request, same slug.

Requests (slug | what they typed | fields | images we already have for that make):
{rows}
'''

BATCH=25


def state_path():
    return Path(os.environ.get('REQUESTS_INTERPRETED',Path.home()/'Projects/vehicle-request-state/interpreted.json'))


def load():
    p=state_path()
    return json.loads(p.read_text()) if p.exists() else {}


def unserved(rows,curated):
    """Rows that would end up with no picture: junk, blocked, or generic misses not fixed by hand."""
    out=[]
    for row in rows:
        rule=curated['requests'].get(row['slug'],{})
        if rule.get('target') or (rule.get('candidate') and not rule.get('blocked')):
            continue
        if row['class']=='JUNK' or rule.get('junk') or rule.get('blocked'):
            out.append(row)
    return out


def existing_keys(row,manifest):
    make=classifier.slug_component(row['fields'].get('make')) or ''
    make=classifier.COMMON_MAKE_ALIASES.get(make,make)
    keys=sorted(k for k in set(manifest['vehicles'])|set(manifest['generations']) if k.split('/',1)[0]==make or (make and k.split('/',1)[0].startswith(make)))
    return ', '.join(keys[:400]) or 'none'


def interpret(rows,curated,manifest=None):
    """Ask about every unserved row not asked before. Returns the slugs answered this time."""
    known=load();todo=[r for r in unserved(rows,curated) if r['slug'] not in known]
    new=[]
    for n in range(0,len(todo),BATCH):
        chunk=todo[n:n+BATCH]
        lines='\n'.join(f"{r['slug']} | {r['fields'].get('rawText') or ''} | {json.dumps({k:r['fields'].get(k) for k in ('make','model','trim','year')},ensure_ascii=False)} | {existing_keys(r,manifest) if manifest else 'unknown'}" for r in chunk)
        answers=ask(PROMPT.replace('{rows}',lines),SCHEMA)['answers']
        wanted={r['slug'] for r in chunk}
        for a in answers:
            if a['slug'] in wanted and a['slug'] not in known:
                known[a['slug']]=a;new.append(a['slug'])
        p=state_path();p.parent.mkdir(parents=True,exist_ok=True)
        tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(known,indent=1,ensure_ascii=False,sort_keys=True)+'\n');tmp.replace(p)
    return new


TWO_WHEEL={'motorcycle','scooter','bicycle'}


def overlay(manifest):
    """Turn cached answers into curated-style rules: an alias when we already have the vehicle, else a render job."""
    rules={'requests':{},'briefs':{},'nonsense':{}}
    for slug,a in load().items():
        if a['decision']!='vehicle' or a.get('confidence')=='low':
            rules['nonsense'][slug]=a['reason'];continue
        pick=a.get('existing') or ''
        if pick and (pick in manifest['vehicles'] or pick in manifest['generations']):
            rules['requests'][slug]={'target':pick,'reason':'Interpreted: '+a['reason']};continue
        make=classifier.slug_component(a['make']);model=classifier.slug_component(a['model'])
        if not make or not model: continue
        year=a['year'] if 1900<=a['year']<=2100 else None
        base=f'{make}/{model}'
        target=base if classifier.resolve(base,year,manifest) else None
        if not target:
            # Year-suffixed keys only (e.g. hyundai/creta-2015): take the newest one not after their year.
            dated=sorted((int(k[-4:]),k) for k in manifest['vehicles'] if k.startswith(base+'-') and k[-4:].isdigit() and k[len(base)+1:].isdigit())
            if dated: target=next((k for y,k in reversed(dated) if year is None or y<=year),dated[0][1])
        if target:
            rules['requests'][slug]={'target':target,'reason':'Interpreted: '+a['reason']}
        else:
            rules['requests'][slug]={'candidate':base,'reason':'Interpreted: '+a['reason']}
            rules['briefs'].setdefault(base,[a['description'],a['kind'] in TWO_WHEEL])
    return rules
