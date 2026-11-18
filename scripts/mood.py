"""Mood tracker helpers (same pattern as habits.py).

Sheet tab 'Mood Log' (append-only; nothing is ever deleted):
  A Date | B Time (local, h:mm AM/PM text) | C Mood (1-5) | D Note | E Logged at (local time) | F Event id
Many entries per day are normal. No streaks, no scoring: a day with no entries is unknown, not bad.
The app never writes to the sheet: it POSTs /api/mood to a KV queue ('mood_pending'); the sync drains it here.
"""
import datetime as dt
import json, re
from config import TZ

TAB = 'Mood Log'
HEADER = ['Date', 'Time', 'Mood (1-5)', 'Note', 'Logged at', 'Event id']
QUEUE_KEY = 'mood_pending'
DEN = TZ


def serial(v): return (dt.date(1899, 12, 30) + dt.timedelta(days=int(v))).isoformat()
def to_serial(iso): return (dt.date.fromisoformat(iso) - dt.date(1899, 12, 30)).days


def clean_note(s):
    s = re.sub(r'[\x00-\x08\x0b-\x1f]', ' ', str(s or '')).strip()
    s = re.sub(r'[ \t]+', ' ', s)[:200]
    return ("'" + s) if s[:1] in ('=', '+', '-', '@') else s   # a note can never become a sheet formula


def valid_event(ev):
    if not isinstance(ev, dict): return False
    if not isinstance(ev.get('id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{4,40}', ev['id']): return False
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(ev.get('d', ''))): return False
    try: dt.date.fromisoformat(ev['d'])
    except Exception: return False
    m = ev.get('m')
    if not isinstance(m, int) or isinstance(m, bool) or not 1 <= m <= 5: return False
    n = ev.get('n', '')
    if n is not None and (not isinstance(n, str) or len(n) > 200): return False
    return True


def local_time(iso_utc=None):
    t = dt.datetime.fromisoformat(iso_utc.replace('Z', '+00:00')) if iso_utc else dt.datetime.now(dt.timezone.utc)
    return t.astimezone(DEN)


def rows_for_event(ev):
    t = local_time(ev.get('t'))
    return [[to_serial(ev['d']), t.strftime('%-I:%M %p'), ev['m'], clean_note(ev.get('n')), t.strftime('%Y-%m-%d %H:%M:%S'), ev['id']]]


def parse_log(rows, days=120, today=None):
    """rows = 'Mood Log'!A2:F UNFORMATTED. Returns {date: [{t:'h:mm AM', m:int, n:str}]} oldest-first within a day."""
    cut = ((today or dt.date.today()) - dt.timedelta(days=days)).isoformat()
    out = {}
    for r in rows:
        r = (list(r) + [''] * 6)[:6]
        if not isinstance(r[0], (int, float)): continue
        m = r[2]
        if not isinstance(m, (int, float)) or isinstance(m, bool) or not 1 <= int(m) <= 5: continue
        d = serial(r[0])
        if d < cut: continue
        out.setdefault(d, []).append({'t': str(r[1]), 'm': int(m), 'n': str(r[3] or ''), 's': str(r[4] or '')})
    for d in out: out[d].sort(key=lambda e: e['s'])
    for d in out:
        for e in out[d]: e.pop('s', None)
    return dict(sorted(out.items()))


def snapshot_section(g, today=None):
    try: rows = g(f"'{TAB}'!A2:F20000", 'UNFORMATTED_VALUE')
    except Exception: return None
    return {'log': parse_log(rows, today=today), 'pending': []}


def known_ids(rows):
    return {str((list(r) + [''] * 6)[5]) for r in rows if r}


def _kv_default(method, key, body=None):
    from kvstore import kv
    return kv(method, key, body)


def read_queue(kv=_kv_default):
    raw = kv('GET', QUEUE_KEY)
    try: q = json.loads(raw) if raw else []
    except Exception: q = []
    return [e for e in q if valid_event(e)]


def drain_begin(append, known, kv=_kv_default):
    done = []
    for ev in sorted(read_queue(kv), key=lambda e: e.get('t', '')):
        if ev['id'] not in known: append(rows_for_event(ev))
        done.append(ev['id'])
    return done


def drain_end(ids, kv=_kv_default):
    if not ids: return 0
    left = [e for e in read_queue(kv) if e['id'] not in set(ids)]
    kv('PUT', QUEUE_KEY, json.dumps(left))
    return len(ids)
