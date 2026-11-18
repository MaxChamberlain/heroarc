"""Google Sheets access with YOUR OWN OAuth refresh token (see auth_google.py)."""
import json, time, os, urllib.request, urllib.parse, urllib.error
from config import env, DATA
CACHE = os.path.join(DATA, '.cache', 'google_token.json')

def token(scope=None):
    try:
        c = json.load(open(CACHE))
        if c['exp'] > time.time() + 60: return c['access_token']
    except Exception: pass
    d = urllib.parse.urlencode({'client_id': env('GOOGLE_CLIENT_ID', required=True),
        'client_secret': env('GOOGLE_CLIENT_SECRET', required=True),
        'refresh_token': env('GOOGLE_REFRESH_TOKEN', required=True),
        'grant_type': 'refresh_token'}).encode()
    r = json.load(urllib.request.urlopen(urllib.request.Request('https://oauth2.googleapis.com/token', d)))
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    json.dump({'access_token': r['access_token'], 'exp': time.time() + r['expires_in']}, open(CACHE, 'w'))
    os.chmod(CACHE, 0o600)
    return r['access_token']

def api(method, url, tok, body=None):
    r = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None,
        {'Authorization': 'Bearer ' + tok, 'Content-Type': 'application/json'}, method=method)
    try:
        raw = urllib.request.urlopen(r).read()
        return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        return {'error': e.code, 'body': e.read()[:400].decode()}
