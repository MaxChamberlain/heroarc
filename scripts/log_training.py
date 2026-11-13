#!/usr/bin/env python3
"""Append sets to the Training Log. One row per exercise (sets x reps at a weight).
usage: log_training.py --workout "Push A" --exercise "Bench press" --lb 185 --sets 4 --reps 6 [--notes ""] [--date --time]"""
import argparse, sys, urllib.parse
from config import now, env
from google_auth import token, api
ap = argparse.ArgumentParser()
ap.add_argument('--workout', required=True); ap.add_argument('--exercise', required=True)
ap.add_argument('--lb', type=float, required=True); ap.add_argument('--sets', type=int, required=True); ap.add_argument('--reps', required=True)
ap.add_argument('--notes', default=''); ap.add_argument('--date'); ap.add_argument('--time'); a = ap.parse_args()
nw = now(); d = a.date or nw.date().isoformat(); t = a.time or nw.strftime('%H:%M')
S = env('SHEET_ID', required=True); ts = token(); U = f'https://sheets.googleapis.com/v4/spreadsheets/{S}/values/'
r = api('POST', U + urllib.parse.quote("'Training Log'!A:H") + ':append?valueInputOption=USER_ENTERED&insertDataOption=INSERT_ROWS', ts,
        {'values': [[d, t, a.workout, a.exercise, a.lb, a.sets, a.reps, a.notes]]})
if 'error' in r: sys.exit(f'append failed: {r}')
print(f'Logged {a.exercise}: {a.sets} x {a.reps} @ {a.lb:g} lb ({a.workout}) on {d}.')
