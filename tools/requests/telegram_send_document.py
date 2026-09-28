#!/usr/bin/env python3
"""One review document to Galahad Prime. Never log URLs or credential values."""
import json
import os
from pathlib import Path
import sys
import urllib.request
import uuid


def main():
    env=Path(os.environ.get('TELEGRAM_ENV',Path.home()/'.config/openroad/telegram.env'))
    values={}
    for line in env.read_text().splitlines():
        key,sep,value=line.partition('=')
        if sep and key.strip() in {'TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID'}:
            values[key.strip()]=value.strip().strip('\"').strip("'")
    path=Path(sys.argv[1]);caption=sys.argv[2] if len(sys.argv)>2 else ''
    token=values['TELEGRAM_BOT_TOKEN'];chat=values['TELEGRAM_CHAT_ID']
    if chat!='6603810891': raise ValueError('Unexpected destination')
    boundary=uuid.uuid4().hex;body=b''
    for key,value in {'chat_id':chat,'caption':caption}.items():
        body+=f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n'.encode()
    body+=f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="review.html"\r\nContent-Type: text/html\r\n\r\n'.encode()
    body+=path.read_bytes()+f'\r\n--{boundary}--\r\n'.encode()
    request=urllib.request.Request(f'https://api.telegram.org/bot{token}/sendDocument',data=body,
        headers={'Content-Type':f'multipart/form-data; boundary={boundary}'})
    with urllib.request.urlopen(request,timeout=120) as response: result=json.load(response)
    if not result.get('ok'): raise RuntimeError('Telegram rejected document')
    print('Review document sent.')


if __name__=='__main__':
    try: main()
    except Exception as exc:
        print(f'Telegram delivery failed: {type(exc).__name__}',file=sys.stderr)
        raise SystemExit(1)
