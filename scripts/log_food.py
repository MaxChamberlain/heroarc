#!/usr/bin/env python3
"""Append one meal to the Nutrition Log and refresh the app.
usage: log_food.py --meal Snack --items "..." --kcal 205 --p 16 --c 34 --f 0.3 [--conf Medium] [--source Label] [--notes ""] [--date YYYY-MM-DD] [--time HH:MM] [--dry-run]"""
import argparse, urllib.parse, sys
from config import now
from google_auth import token, api
import app_push
from config import env
ap = argparse.ArgumentParser()
for a in ('meal', 'items'): ap.add_argument('--' + a, required=True)
for a in ('kcal', 'p', 'c', 'f'): ap.add_argument('--' + a, type=float, required=True)
ap.add_argument('--conf', default='Medium'); ap.add_argument('--source', default='Photo estimate'); ap.add_argument('--notes', default='')
ap.add_argument('--date'); ap.add_argument('--time'); ap.add_argument('--dry-run', action='store_true')
a = ap.parse_args()
nw = now(); d = a.date or nw.date().isoformat(); t = a.time or nw.strftime('%H:%M')
S = env('SHEET_ID', required=True); ts = token()
U = f'https://sheets.googleapis.com/v4/spreadsheets/{S}/values/'
box = lambda: api('GET', U + urllib.parse.quote("'Nutrition Log'!M1:P5") + '?valueRenderOption=FORMATTED_VALUE', ts).get('values')
before = box()
if not before or before[1][0] != 'Calories': sys.exit(f'Today box is not where expected, refusing to write: {before}')
if a.dry_run: print('dry run ok; box intact:', before[1]); sys.exit(0)
row = [d, t, a.meal, a.items, a.kcal, a.p, a.c, a.f, a.conf, a.source, a.notes]
r = api('POST', U + urllib.parse.quote("'Nutrition Log'!A:K") + ':append?valueInputOption=USER_ENTERED&insertDataOption=OVERWRITE', ts, {'values': [row]})
if 'error' in r: sys.exit(f'append failed: {r}')
after = box()
if not after or after[1][0] != 'Calories': sys.exit(f'WARNING box moved after append: {after}')
data = app_push.build(); x = data['days'].get(d, {})
ok = app_push.safe_push(data)
print(f"Logged {a.meal} {a.kcal:.0f} kcal P{a.p:g} C{a.c:g} F{a.f:g} on {d} {t}. Today: {after[1][1]} kcal, {after[2][1]} g protein. App pushed: {ok}. App sees {x.get('kcalIn')} kcal / {x.get('protein')} g.")
