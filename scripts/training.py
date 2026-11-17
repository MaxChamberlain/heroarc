"""Training feature helpers: the plan lives on the Plan tab (editable in the app), the history on the Training Log tab.

Training Log columns: A Date | B Workout | C Status (done/partial/rest) | D Lift (blank on the status row) |
E Direction (up/same/down) | F Weight (lb) | G Notes | H Logged at (ISO, local time) | I Event id.
Rows are only ever appended. The newest 'Logged at' per date wins, so an edit never deletes anything.
"""
import datetime as dt
from config import TZ

HEADER = ['Date', 'Workout', 'Status', 'Lift', 'Direction', 'Max (lb)', 'Notes', 'Logged at', 'Event id', 'Reps']


def _n(s): return ' '.join(str(s or '').lower().split())


def serial(v): return (dt.date(1899, 12, 30) + dt.timedelta(days=int(v))).isoformat()


def to_serial(iso): return (dt.date.fromisoformat(iso) - dt.date(1899, 12, 30)).days


def parse_log(rows, days=120):
    """rows = 'Training Log'!A2:I3000 UNFORMATTED. Returns (log list newest-last, last-weight per lift)."""
    by = {}
    for r in rows:
        r = (list(r) + [''] * 10)[:10]
        if not isinstance(r[0], (int, float)): continue
        d = serial(r[0]); stamp = str(r[7] or '')
        ev = by.setdefault(d, {}).setdefault(stamp, {'d': d, 'w': None, 's': None, 'lifts': {}, 't': stamp})
        if str(r[2]).strip(): ev['s'] = str(r[2]).strip().lower()
        if str(r[1]).strip(): ev['w'] = str(r[1]).strip()
        lift = str(r[3]).strip()
        if lift:
            ev['lifts'][lift] = {'dir': (str(r[4]).strip().lower() or None),
                                 'wt': r[5] if isinstance(r[5], (int, float)) else None,
                                 'reps': int(r[9]) if isinstance(r[9], (int, float)) and r[9] > 0 else None}
    log = [by[d][max(by[d])] for d in sorted(by)]
    return log[-days:]


def rows_for_event(ev, now=None):
    """Sheet rows for one event (status row first, then one row per lift)."""
    now = now or dt.datetime.now(TZ)
    stamp = ev.get('t') or now.strftime('%Y-%m-%d %H:%M:%S')
    base = [to_serial(ev['d']), ev.get('w') or '', ev['s']]
    rows = [base + ['', '', '', ev.get('notes', ''), stamp, ev.get('id', ''), '']]
    for lift, v in (ev.get('lifts') or {}).items():
        rows.append(base + [lift, v.get('dir') or '', v.get('wt') if v.get('wt') is not None else '', '', stamp, ev.get('id', ''),
                            v.get('reps') if v.get('reps') is not None else ''])
    return rows


def valid_event(ev):
    import re
    if not isinstance(ev, dict): return False
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(ev.get('d', ''))): return False
    if ev.get('s') not in ('done', 'partial', 'rest'): return False
    if ev.get('w') is not None and (not isinstance(ev['w'], str) or len(ev['w']) > 30): return False
    L = ev.get('lifts') or {}
    if not isinstance(L, dict) or len(L) > 8: return False
    for k, v in L.items():
        if not isinstance(k, str) or len(k) > 40 or not isinstance(v, dict): return False
        if v.get('dir') not in (None, 'up', 'same', 'down'): return False
        w = v.get('wt')
        if w is not None and (not isinstance(w, (int, float)) or isinstance(w, bool) or not 0 <= w <= 2000): return False
        rp = v.get('reps')
        if rp is not None and (not isinstance(rp, int) or isinstance(rp, bool) or not 1 <= rp <= 200): return False
    return True


# ---------------------------------------------------------------------------
# Snapshot + queue plumbing
# ---------------------------------------------------------------------------
import json, os, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TAB = 'Training Log'


def _env(k):
    for l in open(os.path.join(HERE, '..', '.env')):
        if l.startswith(k + '='): return l.split('=', 1)[1].strip().strip('"\'')


def parse_plan(rows):
    """'Plan'!A2:E (FORMATTED): A Workout | B Exercise | C Sets | D Key lift (x) | E Order. Rows are kept in sheet order."""
    wk, order = {}, []
    for r in rows:
        r = (list(r) + [''] * 5)[:5]
        w, x = str(r[0]).strip(), str(r[1]).strip()
        if not w or not x: continue
        if w not in wk: wk[w] = {'name': w, 'exercises': [], 'keyLifts': []}; order.append(w)
        wk[w]['exercises'].append({'n': x, 'sets': str(r[2]).strip(), 'type': ''})
        if str(r[3]).strip().lower() in ('x', '1', 'yes', 'true'): wk[w]['keyLifts'].append(x)
    return {'workouts': [wk[n] for n in order], 'keyLifts': []}


def plan_rows(ev):
    """ev = {'workouts':[{'name','ex':[{'n','sets','star'}]}]} -> sheet rows for 'Plan'!A2:E."""
    out, k = [], 0
    for w in ev['workouts']:
        for x in w['ex']:
            k += 1; out.append([w['name'].strip(), x['n'].strip(), (x.get('sets') or '').strip(), 'x' if x.get('star') else '', k])
    return out


def valid_plan(ev):
    import re
    if not isinstance(ev, dict) or not re.fullmatch(r'[A-Za-z0-9_-]{4,40}', str(ev.get('id', ''))): return False
    W = ev.get('workouts')
    if not isinstance(W, list) or not 1 <= len(W) <= 7: return False
    seen = set()
    for w in W:
        if not isinstance(w, dict) or not isinstance(w.get('name'), str): return False
        n = w['name'].strip()
        if not 1 <= len(n) <= 30 or re.match(r'^[=+@]', n) or re.search(r'[\x00-\x1f]', n) or n.lower() in seen: return False
        seen.add(n.lower()); E = w.get('ex')
        if not isinstance(E, list) or not 1 <= len(E) <= 14: return False
        xs, stars = set(), 0
        for x in E:
            if not isinstance(x, dict) or not isinstance(x.get('n'), str): return False
            xn, sets = x['n'].strip(), x.get('sets') or ''
            if not 1 <= len(xn) <= 40 or re.match(r'^[=+@]', xn) or re.search(r'[\x00-\x1f]', xn) or xn.lower() in xs: return False
            if not isinstance(sets, str) or len(sets) > 20 or re.match(r'^[=+@]', sets) or re.search(r'[\x00-\x1f]', sets): return False
            if x.get('star') not in (0, 1) or isinstance(x.get('star'), bool): return False
            xs.add(xn.lower()); stars += x['star']
        if stars > 8: return False
    return True


def snapshot_section(g):
    """g(range, mode) -> rows. The program comes from the Plan tab; a missing/empty tab yields an empty plan (the card shows 'Set up plan')."""
    try: prog = parse_plan(g("'Plan'!A2:E200", 'FORMATTED_VALUE'))
    except Exception: prog = {'workouts': [], 'keyLifts': []}
    try: rows = g(f"'{TAB}'!A2:J3000", 'UNFORMATTED_VALUE')
    except Exception: rows = []
    return {'program': prog, 'log': parse_log(rows), 'pending': []}


def denver_stamp(iso_utc=None):
    t = dt.datetime.fromisoformat(iso_utc.replace('Z', '+00:00')) if iso_utc else dt.datetime.now(dt.timezone.utc)
    return t.astimezone(TZ).strftime('%Y-%m-%d %H:%M:%S')


def _kv(method, key, body=None):
    from kvstore import kv
    return kv(method, key, body)


def read_queue(kv=_kv):
    raw = kv('GET', 'training_pending')
    try: q = json.loads(raw) if raw else []
    except Exception: q = []
    return [e for e in q if valid_event(e) and isinstance(e.get('id'), str)]


def drain_begin(append, known_ids, kv=_kv):
    """Append every queued tap that is not already in the sheet. `append(rows)` writes rows (RAW). Returns drained ids."""
    q = sorted(read_queue(kv), key=lambda e: e.get('t', ''))
    done = []
    for ev in q:
        if ev['id'] not in known_ids:
            append(rows_for_event({**ev, 't': denver_stamp(ev.get('t'))}))
        done.append(ev['id'])
    return done


def drain_end(ids, kv=_kv):
    """After the fresh snapshot is live, drop the drained taps from the queue (re-read first so new taps survive)."""
    if not ids: return 0
    left = [e for e in read_queue(kv) if e['id'] not in set(ids)]
    kv('PUT', 'training_pending', json.dumps(left))
    return len(ids) - 0


def known_ids(rows):
    return {str((list(r) + [''] * 9)[8]) for r in rows if r}
