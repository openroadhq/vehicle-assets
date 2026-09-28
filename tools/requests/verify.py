"""Validate an additive daily change against its pinned base, without network I/O."""
import hashlib
import json
from pathlib import Path
import subprocess
from PIL import Image


def verify(worktree,delta):
    base=json.loads((delta/'base.json').read_text())['commit']
    def old(name): return json.loads(subprocess.check_output(['git','-C',str(worktree),'show',f'{base}:{name}'],text=True))
    before=old('manifest.json');after=json.loads((worktree/'manifest.json').read_text())
    old_aliases=old('aliases.json');new_aliases=json.loads((worktree/'aliases.json').read_text())
    assert all(after['aliases'].get(k)==v for k,v in before['aliases'].items()),'Existing manifest aliases changed'
    assert all(new_aliases.get(k)==v for k,v in old_aliases.items()),'Existing alias-file entries changed'
    assert all(after['vehicles'].get(k)==v for k,v in before['vehicles'].items()),'Existing vehicle records changed'
    changed=subprocess.check_output(['git','-C',str(worktree),'diff',base,'--name-only','--diff-filter=MDR','--','v1'],text=True).splitlines()
    assert not changed,'An existing tracked asset changed'
    new=sorted(set(after['vehicles'])-set(before['vehicles']))
    images={}
    for slug in new:
        p=worktree/'v1'/f'{slug}.webp';im=Image.open(p)
        assert im.format=='WEBP' and im.width==1024 and im.mode=='RGBA',f'Wrong image format: {slug}'
        assert p.stat().st_size==after['vehicles'][slug]['bytes'],f'Manifest byte mismatch: {slug}'
        alpha=im.getchannel('A');box=alpha.getbbox()
        assert box and alpha.getextrema()[0]==0 and alpha.getextrema()[1]>200,f'Bad alpha: {slug}'
        assert box[0]>1 and box[1]>1 and box[2]<im.width-1 and box[3]<im.height-1,f'Clipped subject: {slug}'
        images[slug]={'bytes':p.stat().st_size,'size':list(im.size),'alpha_bbox':list(box),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    additions={k:v for k,v in after['aliases'].items() if k not in before['aliases']}
    for alias in additions:
        target=alias;seen=set()
        while target in after['aliases']:
            assert target not in seen,f'Alias cycle: {alias}'
            seen.add(target);target=after['aliases'][target]
        assert target in after['vehicles'] or target in after['generations'],f'Dangling alias: {alias}'
    proof={'base':base,'new_images':len(new),'new_aliases':len(additions),'existing_aliases_preserved':True,
           'existing_images_preserved':True,'images':images}
    (delta/'verification.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('worktree',type=Path);p.add_argument('delta',type=Path);a=p.parse_args()
    proof=verify(a.worktree,a.delta);print(json.dumps({k:v for k,v in proof.items() if k!='images'},indent=2))
