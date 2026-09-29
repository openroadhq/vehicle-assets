"""Safety and repeat-run regressions. No network, generation, or Telegram calls."""
import datetime as dt
import importlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock

os.environ.setdefault('REQUESTS_DELTA','/var/tmp/request-tests')
os.environ.setdefault('REQUESTS_DATE','2026-09-28')
os.environ.setdefault('REQUESTS_WORKTREE','/var/tmp/request-tests')
import quota
import render
import daily


class QuotaTests(unittest.TestCase):
    def check_usage(self,used,stale=False):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'usage.json'
            p.write_text(json.dumps({'providers':[{'provider_id':'codex','status':'known','stale':stale,
                'last_updated':dt.datetime.now(dt.timezone.utc).isoformat(),'percent_used':used}]}))
            with patch.object(quota,'MIRROR',p),patch.object(quota.urllib.request,'urlopen',side_effect=OSError('offline')):
                return quota.check()
    def test_under_threshold(self): self.assertEqual(self.check_usage(89)['percent_used'],84)
    def test_at_threshold_stops(self):
        with self.assertRaises(RuntimeError): self.check_usage(90)
    def test_unknown_fails_closed(self):
        with self.assertRaises(RuntimeError): self.check_usage(None)
    def test_stale_fails_closed(self):
        with self.assertRaises(RuntimeError): self.check_usage(1,True)
    def test_live_fallback(self):
        row={'providers':{'codex':{'stale':False,'fetchedAt':dt.datetime.now(dt.timezone.utc).isoformat(),
            'resources':{'weekly':{'used':23}}}}}
        response=Mock();response.read.return_value=json.dumps(row).encode()
        context=Mock();context.__enter__=Mock(return_value=response);context.__exit__=Mock(return_value=False)
        with patch.object(quota,'MIRROR',Path('/does-not-exist')),patch.object(quota.urllib.request,'urlopen',return_value=context):
            self.assertEqual(quota.check()['percent_used'],23)


class AliasTests(unittest.TestCase):
    def test_existing_alias_cannot_be_changed(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            (p/'aliases.json').write_text(json.dumps({'make/old':'make/a'}))
            (p/'manifest.json').write_text(json.dumps({'vehicles':{'make/a':{},'make/b':{}},'generations':{},'aliases':{'make/old':'make/a'}}))
            self.assertEqual(render.add_aliases(p,{'make/old':'make/b','make/new':'make/b'}),{'make/new':'make/b'})
            self.assertEqual(json.loads((p/'aliases.json').read_text())['make/old'],'make/a')
    def test_bad_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'aliases.json').write_text('{}');(p/'manifest.json').write_text('{"vehicles":{},"generations":{},"aliases":{}}')
            with self.assertRaises(ValueError): render.add_aliases(p,{'a/b':'missing/asset'})


class DailyTests(unittest.TestCase):
    def test_second_run_reads_but_does_not_generate_or_notify(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);work=root/'work';work.mkdir();state_dir=root/'state';state_dir.mkdir()
            (work/'manifest.json').write_text('{"vehicles":{},"aliases":{},"generations":{}}')
            (work/'aliases.json').write_text('{}')
            a=Mock(date='2026-09-28',worktree=work,deltas=root/'deltas',reviews=root/'reviews',use_export=False,prepare_only=False,no_notify=False)
            delta=a.deltas/'delta-2026-09-28'
            row={'slug':'already-supported','class':'EXACT','candidate':'test/model','alias':None,'matched':'test/model',
                'fields':{},'requests':1,'agg_request_count':1}
            manifest='{"vehicles":{},"aliases":{},"generations":{}}'
            def fake_git(repo,*args):
                if args[0]=='branch': return 'renders-2026-09-28'
                if args[0]=='show': return manifest
                return 'abc123'
            def fake_run(cmd,**kw):
                if str(cmd[1]).endswith('classify.py'):
                    (delta/'data/classified-2026-09-28.json').write_text(json.dumps([row]))
                return Mock(returncode=0)
            gen=Mock()
            with patch.object(daily,'git',side_effect=fake_git),patch.object(daily.subprocess,'run',side_effect=fake_run) as calls,patch.object(render,'load_generator',return_value=gen),patch.object(render,'render',return_value={}) as renders,patch('verify.verify',return_value={}):
                daily.run(a,root,state_dir)
                daily.run(a,root,state_dir)
                self.assertEqual(renders.call_count,1)
                send=[c for c in calls.call_args_list if str(c.args[0][1]).endswith('telegram_send_document.py')]
                self.assertEqual(len(send),0)
                exports=[c for c in calls.call_args_list if str(c.args[0][1]).endswith('export.py')]
                self.assertEqual(len(exports),2)


class RenderAttemptsTests(unittest.TestCase):
    def test_no_more_than_two_backend_calls(self):
        class Generator:
            PROMPT_TEMPLATE='{desc}'
            TWO_WHEEL_PROMPT_TEMPLATE='{desc}'
            CAR_STRICT_PROMPT_TEMPLATE='{desc}'
            TWO_WHEEL_STRICT_PROMPT_TEMPLATE='{desc}'
            def __init__(self): self.calls=0
            def ensure_venv(self): return Path('/unused')
            def generate_raw(self,prompt,out): self.calls+=1;out.write_bytes(b'image')
            def cutout(self,*args): pass
            def wait_for_build_clear(self): pass
            def rebuild_manifest(self): pass
            def process(self,slug,desc,force,py,two,strict):
                with tempfile.TemporaryDirectory() as td:
                    out=Path(td)/'raw.png'
                    self.generate_raw(desc,out)
                    self.generate_raw(desc,out)
                return False
        with tempfile.TemporaryDirectory() as td:
            delta=Path(td);gen=Generator()
            job={'slug':'test/car','description':'test car','two_wheel':False,'blocked':None}
            with patch.object(render,'load_generator',return_value=gen),patch.object(quota,'check',return_value={'percent_used':1}):
                result=render.render(delta,delta,[job],1)
            self.assertEqual(gen.calls,2)
            self.assertEqual(result['test/car']['status'],'failed')
            # A rerun leaves exhausted attempts alone.
            with patch.object(render,'load_generator',return_value=gen),patch.object(quota,'check',return_value={'percent_used':1}):
                render.render(delta,delta,[job],1)
            self.assertEqual(gen.calls,2)


if __name__=='__main__': unittest.main()
