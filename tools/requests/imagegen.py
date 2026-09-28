#!/usr/bin/env python3
"""Use the installed subscription CLI with the explicitly requested model/effort."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path


def load_cli():
    path=Path(os.environ.get('CHATGPT_IMAGEGEN_CLI',Path.home()/'Projects/tools/chatgpt-imagegen/chatgpt-imagegen'))
    loader=importlib.machinery.SourceFileLoader('chatgpt_imagegen',str(path))
    spec=importlib.util.spec_from_loader(loader.name,loader)
    module=importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def configure(cli):
    os.environ.setdefault('CHATGPT_IMAGEGEN_MODEL','gpt-6-astra')
    effort=os.environ.get('CHATGPT_IMAGEGEN_EFFORT','high')
    if effort not in {'low','medium','high','xhigh'}: raise ValueError('Invalid image generation reasoning effort')
    original=cli._build_payload
    def payload(*args,**kwargs):
        body=original(*args,**kwargs)
        body['reasoning']['effort']=effort
        return body
    cli._build_payload=payload


if __name__=='__main__':
    cli=load_cli();configure(cli)
    raise SystemExit(cli.main())
