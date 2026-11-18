#!/usr/bin/env python3
"""One-time: connect YOUR Oura account to YOUR Oura developer app. Stores oura/tokens.json."""
import json, os, time, secrets, urllib.parse, urllib.request, urllib.error
from config import env, OURA_TOKENS
CID, SEC = env('OURA_CLIENT_ID', required=True), env('OURA_CLIENT_SECRET', required=True)
REDIR = env('OURA_REDIRECT_URI', 'http://localhost:8080/callback')   # must match the developer portal EXACTLY
SCOPES = 'email personal daily heartrate workout session spo2 tag stress'
state = secrets.token_urlsafe(12)
url = 'https://cloud.ouraring.com/oauth/authorize?' + urllib.parse.urlencode({
    'response_type': 'code', 'client_id': CID, 'redirect_uri': REDIR, 'scope': SCOPES, 'state': state})
print('\n1) Open this link, sign in to Oura, click Allow:\n\n' + url)
print('\n2) The browser will end on a "can\'t connect" page. Copy the FULL address and paste it here.')
print('   Codes are single-use and expire fast: paste right away.\n')
back = input('Pasted address: ').strip()
q = urllib.parse.parse_qs(urllib.parse.urlparse(back).query)
if q.get('state', [''])[0] != state: raise SystemExit('State mismatch: start over with the newest link.')
d = urllib.parse.urlencode({'grant_type': 'authorization_code', 'code': q['code'][0], 'redirect_uri': REDIR,
    'client_id': CID, 'client_secret': SEC}).encode()
try:
    r = json.load(urllib.request.urlopen(urllib.request.Request('https://api.ouraring.com/oauth/token', d,
        {'User-Agent': 'HeroArc/1.0'})))
except urllib.error.HTTPError as e:
    raise SystemExit(f'Oura said {e.code}: {e.read()[:200].decode()}\nUsual causes: redirect URI not identical to the developer portal, code already used/expired.')
r['obtained_at'] = int(time.time())
p = OURA_TOKENS; os.makedirs(os.path.dirname(p), exist_ok=True); json.dump(r, open(p, 'w')); os.chmod(p, 0o600)
print('\nSaved Oura tokens. Next: python3 scripts/sync.py --days 60')
