#!/usr/bin/env python3
"""Deploy HeroArc to YOUR Cloudflare account and lock it to YOUR email.
Idempotent: safe to re-run after changing app/ files. usage: deploy.py [--dry-run]"""
import json, subprocess, sys, os, time, uuid, urllib.request, urllib.error
from config import env, set_env, ROOT
DRY = '--dry-run' in sys.argv
ACCT, TOK = env('CLOUDFLARE_ACCOUNT_ID', required=True), env('CLOUDFLARE_API_TOKEN', required=True)
EMAIL = env('ALLOWED_EMAIL', required=True).lower(); WORKER = env('WORKER_NAME', 'heroarc')
BASE = f'https://api.cloudflare.com/client/v4/accounts/{ACCT}'
def cf(method, path, body=None):
    r = urllib.request.Request(BASE + path, json.dumps(body).encode() if body is not None else None,
        {'Authorization': 'Bearer ' + TOK, 'Content-Type': 'application/json'}, method=method)
    try: return json.load(urllib.request.urlopen(r))
    except urllib.error.HTTPError as e:
        try: return json.loads(e.read())
        except Exception: return {'success': False, 'errors': [{'message': f'HTTP {e.code}'}]}
def need(r, what):
    if not r.get('success'): sys.exit(f'FAILED: {what}: {r.get("errors")}')
    return r['result']

# 0. syntax-check the page script before anything goes out
html = open(os.path.join(ROOT, 'app', 'index.html')).read()
tmp = os.path.join(ROOT, '.cache', 'chk.js'); os.makedirs(os.path.dirname(tmp), exist_ok=True)
open(tmp, 'w').write(html[html.index('<script>') + 8:html.rindex('</script>')])
if subprocess.run(['node', '--check', tmp], capture_output=True).returncode: sys.exit('Syntax error in app/index.html script: not deploying.')

need(cf('GET', '/storage/kv/namespaces?per_page=1'), 'token cannot read KV (needs Workers KV Storage: Edit)')

# 1. KV namespace
ns = need(cf('GET', '/storage/kv/namespaces?per_page=100'), 'list KV')
nid = next((x['id'] for x in ns if x['title'] == 'health-data'), None)
if not nid and not DRY: nid = need(cf('POST', '/storage/kv/namespaces', {'title': 'health-data'}), 'create KV')['id']
print('KV namespace:', nid or '(would create)')

# 2. workers.dev subdomain
sub = cf('GET', '/workers/subdomain')
if not sub.get('success') or not sub['result'].get('subdomain'):
    print('No workers.dev subdomain yet.')
    name = env('WORKERS_SUBDOMAIN') or sys.exit('Set WORKERS_SUBDOMAIN=<a unique name> in .env (becomes <worker>.<name>.workers.dev), then re-run.')
    if not DRY: need(cf('PUT', '/workers/subdomain', {'subdomain': name}), 'create subdomain'); sub = cf('GET', '/workers/subdomain')
host = f"{WORKER}.{sub['result']['subdomain'] if sub.get('success') else '<subdomain>'}.workers.dev"
print('Address:', 'https://' + host)

# 3. build + upload the Worker with the app files embedded
files = {k: open(os.path.join(ROOT, 'app', k)).read() for k in ['index.html', 'manifest.json', 'icon.svg', 'sw.js']}
code = open(os.path.join(ROOT, 'app', 'worker.template.js')).read().replace('__FILES__', json.dumps(files), 1)
if DRY: print('dry run: would upload worker', WORKER, len(code), 'bytes; would protect', host, 'for', EMAIL); sys.exit(0)
bd = uuid.uuid4().hex
meta = json.dumps({'main_module': 'worker.js', 'compatibility_date': '2025-01-01',
    'bindings': [{'type': 'kv_namespace', 'name': 'HEALTH', 'namespace_id': nid}]})
body = (f'--{bd}\r\nContent-Disposition: form-data; name="metadata"\r\nContent-Type: application/json\r\n\r\n{meta}\r\n'
        f'--{bd}\r\nContent-Disposition: form-data; name="worker.js"; filename="worker.js"\r\nContent-Type: application/javascript+module\r\n\r\n{code}\r\n--{bd}--\r\n').encode()
r = urllib.request.Request(f'{BASE}/workers/scripts/{WORKER}', body, {'Authorization': 'Bearer ' + TOK, 'Content-Type': f'multipart/form-data; boundary={bd}'}, method='PUT')
need(json.load(urllib.request.urlopen(r)), 'upload worker')
need(cf('POST', f'/workers/scripts/{WORKER}/subdomain', {'enabled': True, 'previews_enabled': False}), 'enable workers.dev route')
print('Worker deployed.')

# 4. Access app locked to ONE email (gate first, data second: no data is pushed here)
apps = need(cf('GET', '/access/apps'), 'list Access apps (token needs Access: Apps and Policies: Edit)')
existing = next((a for a in apps if a.get('domain') == host), None)
spec = {'name': 'HeroArc', 'type': 'self_hosted', 'domain': host, 'session_duration': '730h', 'app_launcher_visible': False}
pol = [{'name': 'Owner only', 'decision': 'allow', 'include': [{'email': {'email': EMAIL}}]}]
if existing:
    full = need(cf('GET', f"/access/apps/{existing['id']}"), 'read Access app')
    print('Access app exists; policies:', [p['name'] for p in full.get('policies', [])])
else:
    a = need(cf('POST', '/access/apps', {**spec, 'policies': pol}), 'create Access app')
    print('Access app created; policies:', [p['name'] for p in a.get('policies', [])])

# 5. gate test: all three must 302 before you load any data
time.sleep(4)
class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k): return None
op = urllib.request.build_opener(NoRedir)
def code_for(hdr):
    try: return op.open(urllib.request.Request(f'https://{host}/api/data', headers=hdr)).status
    except urllib.error.HTTPError as e: return e.code
res = {'no login': code_for({}), 'forged header': code_for({'Cf-Access-Jwt-Assertion': 'fake'}), 'forged cookie': code_for({'Cookie': 'CF_Authorization=fake'})}
for k, v in res.items(): print(f'gate {k}: {v} (want 302)')
if any(v != 302 for v in res.values()): sys.exit('GATE FAILED: do NOT push data. Fix before continuing.')
set_env('APP_HOST', host); print('\nGate OK. Next: python3 scripts/sync.py --days 60')
