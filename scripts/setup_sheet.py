#!/usr/bin/env python3
"""Create the tracking spreadsheet in YOUR Google account and save SHEET_ID to .env."""
import urllib.parse
from config import env, set_env
from google_auth import token, api
if env('SHEET_ID'): raise SystemExit('SHEET_ID already set in .env; delete that line first if you really want a new sheet.')
ts = token(); tz = env('TIMEZONE', 'UTC')
names = ['Settings', 'Oura', 'Nutrition Log', 'Weight Log', 'Training Log']
r = api('POST', 'https://sheets.googleapis.com/v4/spreadsheets', ts, {
    'properties': {'title': 'HeroArc Health Log', 'timeZone': tz},
    'sheets': [{'properties': {'title': n}} for n in names]})
if 'spreadsheetId' not in r: raise SystemExit(f'Could not create sheet: {r}')
S = r['spreadsheetId']; ids = {s['properties']['title']: s['properties']['sheetId'] for s in r['sheets']}
U = f'https://sheets.googleapis.com/v4/spreadsheets/{S}'
oura_h = ['Date','Sleep score','Readiness score','Activity score','Total sleep (h)','Deep (min)','REM (min)','Light (min)',
  'Efficiency %','Avg HRV','Lowest HR','Avg HR','Temp deviation (C)','Steps','Active kcal','Total kcal','Bedtime','Wake time',
  'High-stress (min)','High-recovery (min)','Stress summary']
nut_h = ['Date','Time','Meal','Items (est. grams)','Calories','Protein (g)','Carbs (g)','Fat (g)','Confidence','Source','Notes']
box = [['Today','Eaten','Target','Remaining'],
  ['Calories','=SUMIF(A:A,TODAY(),E:E)','=Settings!B1','=O2-N2'],
  ['Protein (g)','=SUMIF(A:A,TODAY(),F:F)','=Settings!B2','=O3-N3'],
  ['Carbs (g)','=SUMIF(A:A,TODAY(),G:G)'],['Fat (g)','=SUMIF(A:A,TODAY(),H:H)']]
settings = [['Calorie goal (kcal)', int(env('CALORIE_GOAL', 2200))], ['Protein goal (g)', int(env('PROTEIN_GOAL', 150))],
  ['Steps goal', int(env('STEPS_GOAL', 10000))], ['Active kcal goal', int(env('ACTIVE_KCAL_GOAL', 500))],
  [], ['Edit the numbers in column B. The app and the Today box read them from here.']]
data = [
 {'range': 'Settings!A1:B6', 'values': settings},
 {'range': 'Oura!A1:U1', 'values': [oura_h]},
 {'range': 'Nutrition Log!A1:K1', 'values': [nut_h]},
 {'range': 'Nutrition Log!M1:P5', 'values': box},
 {'range': 'Weight Log!A1:D1', 'values': [['Date','Weight (lb)','7-day avg','Change vs prev day']]},
 {'range': 'Training Log!A1:H1', 'values': [['Date','Time','Workout','Exercise','Weight (lb)','Sets','Reps','Notes']]}]
x = api('POST', U + '/values:batchUpdate', ts, {'valueInputOption': 'USER_ENTERED', 'data': data})
if 'error' in x: raise SystemExit(f'Write failed: {x}')
def fmt(sheet, col, pattern, typ='DATE'):
    return {'repeatCell': {'range': {'sheetId': ids[sheet], 'startRowIndex': 1, 'startColumnIndex': col, 'endColumnIndex': col + 1},
        'cell': {'userEnteredFormat': {'numberFormat': {'type': typ, 'pattern': pattern}}}, 'fields': 'userEnteredFormat.numberFormat'}}
reqs = [{'repeatCell': {'range': {'sheetId': ids[n], 'startRowIndex': 0, 'endRowIndex': 1},
          'cell': {'userEnteredFormat': {'textFormat': {'bold': True}}}, 'fields': 'userEnteredFormat.textFormat.bold'}} for n in names]
reqs += [{'updateSheetProperties': {'properties': {'sheetId': ids[n], 'gridProperties': {'frozenRowCount': 1}}, 'fields': 'gridProperties.frozenRowCount'}} for n in names[1:]]
reqs += [fmt('Oura', 0, 'yyyy-mm-dd'), fmt('Oura', 16, 'h:mm AM/PM', 'TIME'), fmt('Oura', 17, 'h:mm AM/PM', 'TIME'),
         fmt('Nutrition Log', 0, 'yyyy-mm-dd'), fmt('Nutrition Log', 1, 'h:mm AM/PM', 'TIME'),
         fmt('Weight Log', 0, 'yyyy-mm-dd'), fmt('Training Log', 0, 'yyyy-mm-dd'), fmt('Training Log', 1, 'h:mm AM/PM', 'TIME')]
y = api('POST', U + ':batchUpdate', ts, {'requests': reqs})
if 'error' in y: print('Formatting skipped (data is fine):', y)
set_env('SHEET_ID', S)
print(f'Created "HeroArc Health Log". SHEET_ID saved to .env.\nOpen it: https://docs.google.com/spreadsheets/d/{S}/edit\nEdit your goals on the Settings tab.')
