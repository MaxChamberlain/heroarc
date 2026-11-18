#!/usr/bin/env python3
"""HeroArc service: a small HTTP API around the logging scripts, plus the Oura sync timer.
Built for Render (or any host): n8n's AI agent calls it, and it keeps the app fresh on its own.

Every request except GET /health needs:  Authorization: Bearer <HEROARC_API_KEY>
  GET  /health                  -> {"ok": true}
  GET  /today                   -> today's totals, goals and last sleep/readiness
  POST /food      {"meal","items","kcal","p","c","f", "conf"?, "source"?, "notes"?, "date"?, "time"?, "dry_run"?}
  POST /weight    {"lb", "date"?}
  POST /training  {"workout", "status"?: done|partial|rest, "lift"?, "lb"?, "reps"?, "date"?}   (lift, lb, reps go together)
  POST /sync      {"days"?}
Scripts run as argument lists (never through a shell), one at a time.

Settings (environment variables, or .env when run locally):
  HEROARC_API_KEY            required; long random string shared with n8n
  HEROARC_DATA_DIR           persistent folder for token files (Render disk mount path)
  OURA_TOKENS_JSON           one-time seed: contents of oura/tokens.json, used only if the disk has none yet
  SYNC_EVERY_MIN=15, SYNC_START_HOUR=6, SYNC_END_HOUR=22   sync timer, in TIMEZONE local time (0 disables)
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID                     optional: message you when the sync breaks/recovers
"""
import hmac, json, os, re, subprocess, sys, threading, time, urllib.parse, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from config import env, now, OURA_TOKENS

KEY = env('HEROARC_API_KEY') or sys.exit('Set HEROARC_API_KEY (a long random string) before starting the server.')
if len(KEY) < 24: sys.exit('HEROARC_API_KEY is too short; use at least 24 random characters.')
RUN = threading.Lock()   # the scripts share one sheet and one Oura token: never run two at once
DATE, TIME = re.compile(r'^\d{4}-\d{2}-\d{2}$'), re.compile(r'^\d{2}:\d{2}$')

def seed_oura_tokens():
    """First boot on a fresh disk: write tokens from OURA_TOKENS_JSON. Later boots keep the disk copy,
    because Oura refresh tokens are single-use and the disk copy is the newest one."""
    if os.path.exists(OURA_TOKENS): return 'disk'
    raw = env('OURA_TOKENS_JSON')
    if not raw: return 'missing'
    t = json.loads(raw)
    if not t.get('refresh_token'): sys.exit('OURA_TOKENS_JSON has no refresh_token.')
    os.makedirs(os.path.dirname(OURA_TOKENS), exist_ok=True)
    with open(OURA_TOKENS, 'w') as f: json.dump(t, f)
    os.chmod(OURA_TOKENS, 0o600); return 'seeded'

def run(script, args, timeout=180):
    with RUN:
        p = subprocess.run([sys.executable, os.path.join(HERE, script), *args], capture_output=True, text=True, timeout=timeout, cwd=HERE)
    out = (p.stdout or '').strip(); err = (p.stderr or '').strip()
    return p.returncode == 0, out.splitlines()[-1] if out else '', err.splitlines()[-1][:400] if err else ''

# ---- request validation: turn JSON into a safe argument list ----
class Bad(Exception): pass
def num(b, k, lo, hi, required=True):
    v = b.get(k)
    if v is None:
        if required: raise Bad(f'{k} is required')
        return None
    if isinstance(v, str):   # AI tool calls often send numbers as text: accept "450" or "12.5"
        try: v = float(v.strip())
        except ValueError: raise Bad(f'{k} must be a number')
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v != v: raise Bad(f'{k} must be a number')
    if not lo <= v <= hi: raise Bad(f'{k}={v} is outside {lo}..{hi}')
    return v
def text(b, k, required=True, n=300):
    v = b.get(k)
    if v is None or v == '':
        if required: raise Bad(f'{k} is required')
        return None
    if not isinstance(v, str) or len(v) > n: raise Bad(f'{k} must be text up to {n} characters')
    return v.replace('\n', ' ').strip()
def when(b, a):
    for k, rx in (('date', DATE), ('time', TIME)):
        v = b.get(k)
        if v:
            if not isinstance(v, str) or not rx.match(v): raise Bad(f'{k} must look like ' + ('YYYY-MM-DD' if k == 'date' else 'HH:MM'))
            a.append(f'--{k}={v}')
    return a

def food(b):
    a = [f"--meal={text(b, 'meal', n=40)}", f"--items={text(b, 'items')}",
         f"--kcal={num(b, 'kcal', 0, 5000)}", f"--p={num(b, 'p', 0, 500)}", f"--c={num(b, 'c', 0, 1000)}", f"--f={num(b, 'f', 0, 500)}"]
    for k in ('conf', 'source', 'notes'):
        v = text(b, k, required=False, n=120 if k != 'notes' else 300)
        if v: a.append(f'--{k}={v}')
    if b.get('dry_run') is True: a.append('--dry-run')
    return 'log_food.py', when(b, a)
def weight(b):
    return 'log_weight.py', when(b, [str(num(b, 'lb', 50, 700))])
def training(b):
    """Matches log_training.py: one workout per call, optionally with one lift's weight x reps."""
    a = [f"--workout={text(b, 'workout', n=60)}"]
    st = text(b, 'status', required=False, n=10)
    if st:
        if st.lower() not in ('done', 'partial', 'rest'): raise Bad('status must be done, partial or rest')
        a.append(f'--status={st.lower()}')
    lift = text(b, 'lift', required=False, n=80)
    lb, reps = num(b, 'lb', 0, 2000, required=False), num(b, 'reps', 1, 100, required=False)
    if lift or lb is not None or reps is not None:
        if not (lift and lb is not None and reps is not None): raise Bad('give lift, lb and reps together, or none of them')
        a += [f'--lift={lift}', f'--lb={lb}', f'--reps={int(reps)}']
    d = b.get('date')
    if d:
        if not isinstance(d, str) or not DATE.match(d): raise Bad('date must look like YYYY-MM-DD')
        a.append(f'--date={d}')
    return 'log_training.py', a
def sync_args(b):
    d = num(b, 'days', 1, 90, required=False)
    return 'sync.py', ['--days', str(int(d))] if d else []
ROUTES = {'/food': food, '/weight': weight, '/training': training, '/sync': sync_args}

def today():
    with RUN:
        import app_push
        d = app_push.build()
    return {'date': d['date'], 'updated': d['updated'], 'goals': d['goals'], 'today': d['today'], 'ouraDay': d['ouraDay']}

# ---- sync timer + Telegram alerts ----
def telegram(msg):
    tok, chat = env('TELEGRAM_BOT_TOKEN'), env('TELEGRAM_CHAT_ID')
    if not (tok and chat): return
    try:
        urllib.request.urlopen(urllib.request.Request(f'https://api.telegram.org/bot{tok}/sendMessage',
            urllib.parse.urlencode({'chat_id': chat, 'text': msg}).encode()), timeout=15)
    except Exception as e: print('telegram alert failed:', type(e).__name__, flush=True)

def sync_ok(ok, out):
    return ok and ('days upserted' in out or 'no Oura data' in out) and 'push failed' not in out

STATE = {'failing': False, 'last': None}
def sync_loop():
    every = int(env('SYNC_EVERY_MIN', '15')); start, end = int(env('SYNC_START_HOUR', '6')), int(env('SYNC_END_HOUR', '22'))
    if every <= 0: return
    while True:
        if start <= now().hour < end:
            try: ok, out, err = run('sync.py', [])
            except Exception as e: ok, out, err = False, '', f'{type(e).__name__}: {e}'
            good = sync_ok(ok, out); STATE['last'] = {'at': now().isoformat(timespec='minutes'), 'ok': good, 'out': out or err}
            print('sync', 'ok' if good else 'FAILED', out or err, flush=True)
            if not good and not STATE['failing']:
                telegram(f'HeroArc sync failed: {(out or err)[:300]}\nIt will keep retrying every {every} min.')
            elif good and STATE['failing']:
                telegram('HeroArc sync is working again.')
            STATE['failing'] = not good
        time.sleep(every * 60)

# ---- HTTP ----
class H(BaseHTTPRequestHandler):
    server_version = 'HeroArc'
    def reply(self, code, body):
        b = json.dumps(body).encode()
        self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store'); self.end_headers(); self.wfile.write(b)
    def authed(self):
        h = self.headers.get('Authorization', '').strip()
        if h[:7].lower() == 'bearer ': h = h[7:].strip()   # "Bearer <key>", any case; a bare "<key>" works too
        if h and hmac.compare_digest(h.encode(), KEY.encode()): return True
        # Say what arrived (never the key itself) so a misconfigured client is easy to fix.
        why = ('no Authorization header received (check the header name is exactly "Authorization")' if 'Authorization' not in self.headers
               else f'key does not match (received {len(h)} characters, expected {len(KEY)})')
        self.reply(401, {'ok': False, 'error': 'unauthorized: ' + why}); return False
    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        if p == '/health': return self.reply(200, {'ok': True})
        if not self.authed(): return
        if p == '/today':
            try: return self.reply(200, {'ok': True, **today(), 'lastSync': STATE['last']})
            except Exception as e: return self.reply(502, {'ok': False, 'error': f'{type(e).__name__}: {e}'[:400]})
        self.reply(404, {'ok': False, 'error': 'not found'})
    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path
        if not self.authed(): return
        if p not in ROUTES: return self.reply(404, {'ok': False, 'error': 'not found'})
        n = int(self.headers.get('Content-Length') or 0)
        if n > 10000: return self.reply(413, {'ok': False, 'error': 'body too large'})
        try:
            b = json.loads(self.rfile.read(n) or b'{}')
            if not isinstance(b, dict): raise Bad('body must be a JSON object')
            script, args = ROUTES[p](b)
        except (Bad, ValueError) as e: return self.reply(400, {'ok': False, 'error': str(e)})
        try: ok, out, err = run(script, args)
        except subprocess.TimeoutExpired: return self.reply(504, {'ok': False, 'error': 'timed out'})
        if p == '/sync': ok = sync_ok(ok, out)
        self.reply(200 if ok else 502, {'ok': ok, 'result': out, **({} if ok else {'error': err or out})})
    def log_message(self, fmt, *a):   # log method + path + status only, never bodies or headers
        print(fmt % a, flush=True)

if __name__ == '__main__':
    print('oura tokens:', seed_oura_tokens(), flush=True)
    threading.Thread(target=sync_loop, daemon=True).start()
    port = int(env('PORT', '8080'))
    print(f'HeroArc service on :{port}', flush=True)
    ThreadingHTTPServer(('0.0.0.0', port), H).serve_forever()
