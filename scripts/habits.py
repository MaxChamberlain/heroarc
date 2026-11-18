"""Habits feature helpers.

Sheet layout (two tabs; the first can be edited by hand or from the app):
  'Habits'     A Habit (display name, edit freely) | B Id (auto-filled by the sync, do not edit) | C Archive (type x to hide a habit; history stays)
  'Habit Log'  A Date | B Habit id | C Done (1 or 0) | D Logged at (local time) | E Event id
Rows in 'Habit Log' are only ever appended. For each (date, habit) the newest 'Logged at' wins, so un-checking writes a 0 row and nothing is deleted.
"""
import datetime as dt
import json, os, re
from config import TZ

CFG_TAB, LOG_TAB = 'Habits', 'Habit Log'
CFG_HEADER = ['Habit', 'Id', 'Archive']
LOG_HEADER = ['Date', 'Habit id', 'Done', 'Logged at', 'Event id']
MAX_HABITS = 8
QUEUE_KEY = 'habit_pending'
HERE = os.path.dirname(os.path.abspath(__file__))


def serial(v): return (dt.date(1899, 12, 30) + dt.timedelta(days=int(v))).isoformat()
def to_serial(iso): return (dt.date.fromisoformat(iso) - dt.date(1899, 12, 30)).days


def slug(name, taken=()):
    base = re.sub(r'[^a-z0-9]+', '-', str(name).lower()).strip('-')[:24] or 'habit'
    out, n = base, 2
    while out in taken:
        out = f'{base}-{n}'; n += 1
    return out


def parse_config(rows):
    """rows = 'Habits'!A2:C40 (FORMATTED). Returns list of {id,n} for active habits (needs Id filled in), capped at MAX_HABITS."""
    out = []
    for r in rows:
        r = (list(r) + ['', '', ''])[:3]
        name, hid, arch = str(r[0]).strip(), str(r[1]).strip(), str(r[2]).strip()
        if not name or arch: continue
        if not re.fullmatch(r'[a-z0-9_-]{1,30}', hid): continue
        out.append({'id': hid, 'n': name[:30]})
    return out[:MAX_HABITS]


def parse_archived(rows):
    out = []
    for r in rows:
        r = (list(r) + ['', '', ''])[:3]
        name, hid, arch = str(r[0]).strip(), str(r[1]).strip(), str(r[2]).strip()
        if name and arch and re.fullmatch(r'[a-z0-9_-]{1,30}', hid): out.append({'id': hid, 'n': name[:30]})
    return out[:40]


def plan_ids(rows):
    """Which config rows still need an Id? Returns [(sheet_row_number, new_id)] (row numbers are 1-based, data starts at row 2)."""
    taken = {str((list(r) + ['', ''])[1]).strip() for r in rows if str((list(r) + ['', ''])[1]).strip()}
    plan = []
    for i, r in enumerate(rows):
        r = (list(r) + ['', '', ''])[:3]
        if str(r[0]).strip() and not str(r[1]).strip():
            new = slug(r[0], taken); taken.add(new); plan.append((i + 2, new))
    return plan


def parse_log(rows, days=400, today=None):
    """rows = 'Habit Log'!A2:E20000 UNFORMATTED. Returns {date: [habit ids done]} (newest stamp per date+habit wins)."""
    latest = {}
    for r in rows:
        r = (list(r) + [''] * 5)[:5]
        if not isinstance(r[0], (int, float)) or not str(r[1]).strip(): continue
        d, h, stamp = serial(r[0]), str(r[1]).strip(), str(r[3] or '')
        v = 1 if (r[2] in (1, 1.0, True, '1', 'TRUE')) else 0
        k = (d, h)
        if k not in latest or stamp >= latest[k][0]: latest[k] = (stamp, v)
    cut = ((today or dt.date.today()) - dt.timedelta(days=days)).isoformat()
    log = {}
    for (d, h), (_, v) in latest.items():
        if v and d >= cut: log.setdefault(d, []).append(h)
    return {d: sorted(v) for d, v in sorted(log.items())}


def rows_for_event(ev, now=None):
    now = now or dt.datetime.now(TZ)
    stamp = ev.get('t') or now.strftime('%Y-%m-%d %H:%M:%S')
    return [[to_serial(ev['d']), ev['h'], int(ev['v']), stamp, ev.get('id', '')]]


def valid_event(ev):
    if not isinstance(ev, dict): return False
    if not isinstance(ev.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{4,40}', ev['id']): return False
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(ev.get('d', ''))): return False
    try: dt.date.fromisoformat(ev['d'])
    except Exception: return False
    if not isinstance(ev.get('h'), str) or not re.fullmatch(r'[a-z0-9_-]{1,30}', ev['h']): return False
    if ev.get('v') not in (0, 1) or isinstance(ev.get('v'), bool): return False
    return True


def snapshot_section(g, today=None):
    """g(range, mode) -> rows. Returns the `habits` block, or None when the Habits tab is missing/empty (the card then stays hidden)."""
    try: cfg = parse_config(g(f"'{CFG_TAB}'!A2:C40", 'FORMATTED_VALUE'))
    except Exception: return None
    if not cfg: return {'list': [], 'archived': [], 'log': {}, 'pending': []}   # a fresh sheet starts empty: the card shows an Add prompt
    try: rows = g(f"'{LOG_TAB}'!A2:E20000", 'UNFORMATTED_VALUE')
    except Exception: rows = []
    try: arch = parse_archived(g(f"'{CFG_TAB}'!A2:C40", 'FORMATTED_VALUE'))
    except Exception: arch = []
    return {'list': cfg, 'archived': arch, 'log': parse_log(rows, today=today), 'pending': []}


def denver_stamp(iso_utc=None):
    t = dt.datetime.fromisoformat(iso_utc.replace('Z', '+00:00')) if iso_utc else dt.datetime.now(dt.timezone.utc)
    return t.astimezone(TZ).strftime('%Y-%m-%d %H:%M:%S')


def read_queue(kv):
    raw = kv('GET', QUEUE_KEY)
    try: q = json.loads(raw) if raw else []
    except Exception: q = []
    return [e for e in q if valid_event(e)]


def drain_begin(append, known, kv):
    q = sorted(read_queue(kv), key=lambda e: e.get('t', ''))
    done = []
    for ev in q:
        if ev['id'] not in known:
            append(rows_for_event({**ev, 't': denver_stamp(ev.get('t'))}))
        done.append(ev['id'])
    return done


def drain_end(ids, kv):
    if not ids: return 0
    left = [e for e in read_queue(kv) if e['id'] not in set(ids)]
    kv('PUT', QUEUE_KEY, json.dumps(left))
    return len(ids)


def known_ids(rows):
    return {str((list(r) + [''] * 5)[4]) for r in rows if r}


def _env(k):
    for l in open(os.path.join(HERE, '..', '.env')):
        if l.startswith(k + '='): return l.split('=', 1)[1].strip().strip('"\'')


def _kv_default(method, key, body=None):
    from kvstore import kv
    return kv(method, key, body)


CFG_KEY = 'habit_cfg_pending'


def valid_config(ev):
    """{id, list:[{id,n,a}]}: the full desired Habits tab, active habits first. App-side 'remove' means a=1 (hidden), never a delete."""
    if not isinstance(ev, dict) or not isinstance(ev.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{4,40}', ev['id']): return False
    L = ev.get('list')
    if not isinstance(L, list) or not 1 <= len(L) <= 40: return False
    seen = set()
    for x in L:
        if not isinstance(x, dict): return False
        n, i, a = x.get('n'), x.get('id'), x.get('a', 0)
        if not isinstance(n, str) or not 1 <= len(n.strip()) <= 30 or re.search(r'[\x00-\x1f=+@]', n.strip()[:1]) : return False
        if not isinstance(i, str) or not re.fullmatch(r'[a-z0-9_-]{1,30}', i) or i in seen: return False
        if a not in (0, 1) or isinstance(a, bool): return False
        seen.add(i)
    if sum(1 for x in L if not x.get('a')) > MAX_HABITS: return False
    return True


def config_rows(ev):
    """Rows for 'Habits'!A2:C: [name, id, 'x' or '']. Names starting with = + @ are rejected above so the sheet never gets a formula."""
    return [[x['n'].strip(), x['id'], 'x' if x.get('a') else ''] for x in ev['list']]


def read_config(kv):
    raw = kv('GET', CFG_KEY)
    try: ev = json.loads(raw) if raw else None
    except Exception: ev = None
    return ev if valid_config(ev) else None


def apply_config(write, kv):
    """write(rows) rewrites Habits!A2:C (and clears leftovers). Returns the applied event id (to pass to finish_config) or None."""
    ev = read_config(kv)
    if not ev: return None
    write(config_rows(ev)); return ev['id']


def finish_config(applied_id, kv):
    """Only clear the pending config if it is still the one we applied (a newer edit made meanwhile survives)."""
    cur = read_config(kv)
    if applied_id and cur and cur['id'] == applied_id: kv('PUT', CFG_KEY, 'null'); return True
    return False
