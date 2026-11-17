"""Read/write the app's Cloudflare KV (the small queue of edits made in the app, and the snapshot)."""
import json, urllib.request, urllib.error, urllib.parse
from config import env
_NS = None
def _base():
    global _NS
    acct, tok = env('CLOUDFLARE_ACCOUNT_ID', required=True), env('CLOUDFLARE_API_TOKEN', required=True)
    b = f'https://api.cloudflare.com/client/v4/accounts/{acct}/storage/kv/namespaces'
    H = {'Authorization': 'Bearer ' + tok, 'User-Agent': 'heroarc-sync'}
    if _NS is None:
        ns = json.load(urllib.request.urlopen(urllib.request.Request(b, headers=H)))['result']
        _NS = next(x['id'] for x in ns if x['title'] == 'health-data')
    return f'{b}/{_NS}/values/', H
def kv(method, key, body=None):
    """kv('GET', key) -> text or None; kv('PUT', key, text) -> True."""
    base, H = _base()
    u = base + urllib.parse.quote(key, safe='')
    if method == 'GET':
        try: return urllib.request.urlopen(urllib.request.Request(u, headers=H)).read().decode()
        except urllib.error.HTTPError as e:
            if e.code == 404: return None
            raise
    r = urllib.request.Request(u, body.encode(), {**H, 'Content-Type': 'text/plain'}, method='PUT')
    return json.load(urllib.request.urlopen(r)).get('success')
