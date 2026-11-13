"""Build the app snapshot from the sheet and push it to Cloudflare KV."""
import json, datetime as dt, urllib.request, urllib.parse
from config import env, now
import google_auth

def serial(v): return (dt.date(1899, 12, 30) + dt.timedelta(days=int(v))).isoformat()

def build(read=None):
    """read(range)->rows is injectable so this can be tested without Google."""
    if read is None:
        S = env('SHEET_ID', required=True); ts = google_auth.token()
        U = f'https://sheets.googleapis.com/v4/spreadsheets/{S}/values/'
        read = lambda rng: google_auth.api('GET', U + urllib.parse.quote(rng) + '?valueRenderOption=UNFORMATTED_VALUE', ts).get('values', [])
    nw = now(); today = nw.date().isoformat()
    n = lambda x: x if isinstance(x, (int, float)) and not isinstance(x, bool) else None
    mins = lambda x: round(x * 1440) if isinstance(x, (int, float)) else None
    oura = {}
    for r in read('Oura!A2:U400'):
        if r and isinstance(r[0], (int, float)): oura[serial(r[0])] = (list(r) + [''] * 21)[:21]
    wt = {}
    for r in read("'Weight Log'!A2:B400"):
        if len(r) > 1 and isinstance(r[0], (int, float)) and isinstance(r[1], (int, float)): wt[serial(r[0])] = r[1]
    cfg = [(r[0] if r else None) for r in read('Settings!B1:B4')]
    cfg = (cfg + [None] * 4)[:4]
    kcal_g, prot_g, steps_g, act_g = (cfg[0] or 2200), (cfg[1] or 150), (cfg[2] or 10000), (cfg[3] or 500)
    nut = {}
    for r in read("'Nutrition Log'!A2:H1000"):
        if r and isinstance(r[0], (int, float)):
            d = serial(r[0]); a = nut.setdefault(d, [0, 0, 0, 0]); r = (list(r) + [0] * 8)[:8]
            for k, i in enumerate((4, 5, 6, 7)): a[k] += r[i] if isinstance(r[i], (int, float)) else 0
    days = sorted(oura)
    lastfull = next((d for d in reversed(days) if n(oura[d][1]) is not None or n(oura[d][2]) is not None), None)
    o = oura.get(today); L = oura.get(lastfull, [''] * 21)
    lw = sorted(wt)[-1] if wt else None
    trend = []
    for i in range(13, -1, -1):
        d = (nw.date() - dt.timedelta(days=i)).isoformat(); r = oura.get(d, [''] * 21)
        trend.append({'d': d, 'sleep': n(r[1]), 'readiness': n(r[2]), 'weight': wt.get(d)})
    hist = {}
    for i in range(90):
        d = (nw.date() - dt.timedelta(days=i)).isoformat(); r = oura.get(d, [''] * 21); nn = nut.get(d)
        if any(n(r[j]) is not None for j in (1, 2, 13, 14, 15)) or (isinstance(r[20], str) and r[20]) or d in wt or nn:
            hist[d] = {'sleep': n(r[1]), 'readiness': n(r[2]), 'sleepHours': n(r[4]), 'hrv': n(r[9]), 'bed': mins(r[16]), 'wake': mins(r[17]),
                'stressMin': n(r[18]), 'recoverMin': n(r[19]), 'stressSummary': (r[20] if isinstance(r[20], str) and r[20] else None),
                'steps': n(r[13]), 'activeKcal': n(r[14]), 'totalKcal': n(r[15]),
                'weight': wt.get(d), 'kcalIn': round(nn[0]) if nn else None, 'protein': round(nn[1]) if nn else None}
    tn = nut.get(today, [0, 0, 0, 0])
    return {'sample': False, 'days': hist,
      'goals': {'steps': steps_g, 'activeKcal': act_g, 'kcal': kcal_g, 'protein': round(prot_g)}, 'date': today,
      'updated': nw.strftime('%-I:%M %p ') + (nw.tzname() or ''), 'ouraDay': lastfull,
      'today': {'steps': (n(o[13]) or 0) if o else 0, 'stepsGoal': steps_g, 'activeKcal': (n(o[14]) or 0) if o else 0,
        'totalKcal': (n(o[15]) if o else None), 'activeGoal': act_g,
        'kcalIn': round(tn[0]), 'kcalTarget': kcal_g, 'protein': round(tn[1]), 'proteinTarget': round(prot_g),
        'readiness': n(L[2]), 'sleep': n(L[1]), 'sleepHours': n(L[4]), 'hrv': n(L[9]), 'bed': mins(L[16]), 'wake': mins(L[17]),
        'weight': wt.get(lw)},
      'trend': trend}

def push(data):
    acct, tok = env('CLOUDFLARE_ACCOUNT_ID', required=True), env('CLOUDFLARE_API_TOKEN', required=True)
    H = {'Authorization': 'Bearer ' + tok}
    base = f'https://api.cloudflare.com/client/v4/accounts/{acct}/storage/kv/namespaces'
    ns = json.load(urllib.request.urlopen(urllib.request.Request(base, headers=H)))['result']
    nid = next(x['id'] for x in ns if x['title'] == 'health-data')
    r = urllib.request.Request(f'{base}/{nid}/values/data', json.dumps(data).encode(), {**H, 'Content-Type': 'text/plain'}, method='PUT')
    return json.load(urllib.request.urlopen(r)).get('success')

def safe_push(data=None):
    d = data or build(); g = d.get('goals', {})
    if not (800 < g.get('kcal', 0) < 8000 and 20 < g.get('protein', 0) < 500):
        raise RuntimeError(f'goals look wrong, not pushing: {g}')
    return push(d)

if __name__ == '__main__':
    d = build(); print(json.dumps(d)[:600]); print('pushed', safe_push(d))
