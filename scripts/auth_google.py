#!/usr/bin/env python3
"""One-time: sign in to Google and store a refresh token in .env (prints no secrets)."""
import json, secrets, urllib.parse, urllib.request
from config import env, set_env
CID, SEC = env('GOOGLE_CLIENT_ID', required=True), env('GOOGLE_CLIENT_SECRET', required=True)
REDIR = 'http://localhost:8080/callback'
state = secrets.token_urlsafe(12)
url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode({
    'client_id': CID, 'redirect_uri': REDIR, 'response_type': 'code', 'access_type': 'offline',
    'prompt': 'consent', 'state': state, 'scope': 'https://www.googleapis.com/auth/spreadsheets'})
print('\n1) Open this link, sign in with YOUR Google account, click Allow:\n\n' + url)
print('\n2) Your browser will then show "can\'t connect to localhost". That is expected.')
print('   Copy the FULL address from the address bar and paste it here.\n')
back = input('Pasted address: ').strip()
q = urllib.parse.parse_qs(urllib.parse.urlparse(back).query)
if q.get('state', [''])[0] != state: raise SystemExit('State mismatch: start over and use the newest link.')
if 'code' not in q: raise SystemExit('No code in that address: ' + str(list(q)))
d = urllib.parse.urlencode({'code': q['code'][0], 'client_id': CID, 'client_secret': SEC,
    'redirect_uri': REDIR, 'grant_type': 'authorization_code'}).encode()
r = json.load(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', d)))
if 'refresh_token' not in r: raise SystemExit('Google returned no refresh token. Remove the app at myaccount.google.com/permissions and retry.')
set_env('GOOGLE_REFRESH_TOKEN', r['refresh_token'])
print('\nSaved GOOGLE_REFRESH_TOKEN to .env. Next: python3 scripts/setup_sheet.py')
