"""Ask the Dell's Codex CLI one question and get a JSON answer back. Read-only sandbox, no tools needed."""
import json
import os
from pathlib import Path
import subprocess
import re
import tempfile

USAGE={'codex_calls':0,'codex_tokens':0}


def ask(prompt, schema, images=(), timeout=600):
    with tempfile.TemporaryDirectory(prefix='codex-ask-') as tmp:
        tmp=Path(tmp)
        (tmp/'schema.json').write_text(json.dumps(schema))
        cmd=['codex','exec','--skip-git-repo-check','--ephemeral','-s','read-only','-C',str(tmp),
             '--output-schema',str(tmp/'schema.json'),'-o',str(tmp/'out.json')]
        for image in images: cmd+=['-i',str(image)]
        cmd.append('-')  # prompt from stdin; -i takes several values and would swallow a positional prompt
        result=subprocess.run(cmd,input=prompt,text=True,capture_output=True,timeout=timeout,
                              env={**os.environ,'NO_COLOR':'1'})
        out=tmp/'out.json'
        USAGE['codex_calls']+=1
        m=re.search(r'tokens used\s*\n?\s*([\d,]+)',result.stderr+result.stdout)
        if m: USAGE['codex_tokens']+=int(m.group(1).replace(',',''))
        if result.returncode or not out.exists():
            raise RuntimeError(f'Codex call failed (exit {result.returncode})')
        return json.loads(out.read_text())
