"""One plain Telegram line to Galahad Prime. Never logs URLs or credential values."""
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request


def send(text):
    env=Path(os.environ.get('TELEGRAM_ENV',Path.home()/'.config/openroad/telegram.env'))
    values={}
    for line in env.read_text().splitlines():
        key,sep,value=line.partition('=')
        if sep and key.strip() in {'TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'}:
            values[key.strip()]=value.strip().strip('"').strip("'")
    if values['TELEGRAM_CHAT_ID']!='6603810891': raise ValueError('Unexpected destination')
    body=urllib.parse.urlencode({'chat_id':values['TELEGRAM_CHAT_ID'],'text':text}).encode()
    request=urllib.request.Request(f"https://api.telegram.org/bot{values['TELEGRAM_BOT_TOKEN']}/sendMessage",data=body)
    with urllib.request.urlopen(request,timeout=60) as response:
        if not json.load(response).get('ok'): raise RuntimeError('Telegram rejected message')
