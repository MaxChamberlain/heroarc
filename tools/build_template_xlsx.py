#!/usr/bin/env python3
"""Build template/HeroArc_Health_Log_Template.xlsx (blank logs + a Calculator with made-up examples).
Needs: pip install openpyxl     Run:  python3 tools/build_template_xlsx.py"""
import os, math
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter as L
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.formatting.rule import FormulaRule

# palette = the app's muted 90s-anime night theme
PAGE, BG, BG2, HDR, LINE = '050F15', '0A1A21', '0F262E', '16313A', '244D58'
TXT, MUT, CLAY, ROSE, TEAL, SAGE = 'E8DCC6', 'A4B6B6', 'C48A60', '984A5C', '3C7382', '4D8A68'
GOOD, BAD, INPUT = '7FC9A0', 'E58AA0', '1B3640'
fill = lambda c: PatternFill('solid', start_color=c, end_color=c)
side = lambda c, s='thin': Side(style=s, color=c)
F = lambda **k: Font(name=k.pop('name', 'Calibri'), size=k.pop('size', 11), color=k.pop('color', TXT), **k)
SERIF = 'Georgia'
WRAP = Alignment(wrap_text=True, vertical='center')
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'template', 'HeroArc_Health_Log_Template.xlsx')

def base(ws, widths, tab):
    ws.sheet_view.showGridLines = False
    ws.sheet_properties.tabColor = tab
    for i in range(1, 53):                      # dark canvas in every column, incl. empty ones
        d = ws.column_dimensions[L(i)]; d.fill = fill(BG); d.font = F()
    for col, w in widths.items(): ws.column_dimensions[col].width = w

def put(ws, ref, v=None, fmt=None, font=None, bg=BG, al=None, border=None):
    c = ws[ref]
    if v is not None: c.value = v
    c.font = font or F(); c.fill = fill(bg)
    if fmt: c.number_format = fmt
    if al: c.alignment = al
    if border: c.border = border
    return c

def header(ws, row, labels, c0=1, height=32):
    for i, t in enumerate(labels):
        put(ws, f'{L(c0+i)}{row}', t, font=F(bold=True, size=10), bg=HDR,
            al=Alignment(wrap_text=True, vertical='center', horizontal='left'), border=Border(bottom=side(CLAY, 'medium')))
    ws.row_dimensions[row].height = height

def band(ws, rng):
    ws.conditional_formatting.add(rng, FormulaRule(formula=['MOD(ROW(),2)=0'], fill=fill(BG2)))

wb = Workbook(); wb.properties.creator = 'HeroArc template'; wb.properties.title = 'HeroArc Health Log template'

# ---------------------------------------------------------------- README
ws = wb.active; ws.title = 'README'
base(ws, {'A': 3, 'B': 24, 'C': 70, 'D': 28}, CLAY)
for r in range(1, 70):
    for c in 'ABCD': put(ws, f'{c}{r}', bg=PAGE if r <= 5 else BG)
put(ws, 'B2', 'HeroArc', font=F(name=SERIF, size=30, bold=True, color=CLAY), bg=PAGE); ws.row_dimensions[2].height = 42
put(ws, 'B3', 'Health log template', font=F(name=SERIF, size=14, color=TXT), bg=PAGE)
put(ws, 'B4', 'One workbook for your Oura ring, weight, food and training. Only the Calculator tab holds numbers, and they are made-up examples.', font=F(size=10, color=MUT, italic=True), bg=PAGE)
ws.merge_cells('B4:D4')
row = [6]
def section(t):
    r = row[0]
    for c in 'BCD': put(ws, f'{c}{r}', bg=BG, border=Border(bottom=side(CLAY, 'medium')))
    put(ws, f'B{r}', t, font=F(size=10, bold=True, color=CLAY), border=Border(bottom=side(CLAY, 'medium')))
    ws.row_dimensions[r].height = 22; row[0] += 1
def para(t, color=TXT, italic=False):
    r = row[0]; ws.merge_cells(f'B{r}:D{r}'); put(ws, f'B{r}', t, font=F(color=color, italic=italic), al=WRAP)
    ws.row_dimensions[r].height = 18 * max(1, math.ceil(len(t) / 100)) + 14; row[0] += 1
def gap(): row[0] += 1

section('WHAT THIS IS')
para('This is the spreadsheet behind the HeroArc phone app. The app reads these tabs and shows your sleep, readiness, weight, calories and protein. Every log tab is blank. Nothing in this file belongs to a real person.')
gap(); section('THE TABS')
header(ws, row[0], ['Tab', 'What it holds', 'Who edits it'], c0=2, height=22); row[0] += 1
for a, b, c in [
  ('Calculator', 'Works out daily calorie and protein targets from your bodyweight. It is filled with example numbers so you can see how it works.', 'You: the clay-outlined cells'),
  ('Settings', 'Your four goals: calories, protein, steps and active calories. The app reads these. They are linked to the Calculator; type a number over a formula to set your own.', 'You, if you want to override'),
  ('Oura', 'One row per day: sleep, readiness, activity, HRV, bedtime and stress.', 'Nobody. The sync script fills it.'),
  ('Nutrition Log', 'One row per meal, plus the Today box in M1:P5 that totals the day against your goals.', 'You or your AI assistant'),
  ('Weight Log', 'One row per morning weight. The 7-day average and the daily change are calculated.', 'You: date and weight'),
  ('Training Log', 'One row per exercise: weight, sets and reps.', 'You or your AI assistant')]:
    r = row[0]
    put(ws, f'B{r}', a, font=F(bold=True, color=CLAY), al=WRAP, border=Border(bottom=side(LINE)))
    put(ws, f'C{r}', b, al=WRAP, border=Border(bottom=side(LINE)))
    put(ws, f'D{r}', c, font=F(color=MUT), al=WRAP, border=Border(bottom=side(LINE)))
    ws.row_dimensions[r].height = 18 * max(1, math.ceil(len(b) / 56)) + 16; row[0] += 1
gap(); section('COLOR KEY')
r = row[0]; put(ws, f'B{r}', 180, font=F(bold=True, color=CLAY), bg=INPUT, al=Alignment(horizontal='center', vertical='center'), border=Border(*(side(CLAY, 'medium'),) * 4))
ws.merge_cells(f'C{r}:D{r}'); put(ws, f'C{r}', 'Clay outline: type here. These are the cells meant for your own numbers.', al=WRAP); ws.row_dimensions[r].height = 32; row[0] += 1
r = row[0]; put(ws, f'B{r}', 'Header', font=F(bold=True, size=10), bg=HDR, border=Border(bottom=side(CLAY, 'medium')))
ws.merge_cells(f'C{r}:D{r}'); put(ws, f'C{r}', 'Dark teal header row: leave as is. The app finds columns by their position.', al=WRAP); ws.row_dimensions[r].height = 32; row[0] += 1
r = row[0]; put(ws, f'B{r}', '2,300', font=F(color=TXT), al=Alignment(horizontal='center', vertical='center'), border=Border(bottom=side(LINE)))
ws.merge_cells(f'C{r}:D{r}'); put(ws, f'C{r}', 'Plain cell with a formula: calculated for you. Do not type over it unless you mean to.', al=WRAP); ws.row_dimensions[r].height = 32; row[0] += 1
gap(); section('RULES THAT KEEP THE APP WORKING')
for t in ['1.  Do not rename, reorder or delete tabs. The app finds them by name.',
          '2.  Do not move or delete the Today box in Nutrition Log (M1:P5), and do not insert whole rows above it. Add each new meal in the next empty row below the last one.',
          '3.  Type real dates (2026-11-13) and plain numbers. No "kcal" or "g" inside number cells.',
          '4.  Keep the column order as it is. The app reads columns by position.',
          '5.  Weights are in pounds (lb).']: para(t)
gap(); section('TWO WAYS TO USE THIS FILE')
para('A. Easiest: run scripts/setup_sheet.py. It builds this same layout inside your own Google account and saves the sheet ID for you.')
para('B. Or import this file: in Google Sheets choose File > Import > Upload this file > Create new spreadsheet. Copy the long ID from its web address (the text between /d/ and /edit) into your .env file as SHEET_ID=...')
gap(); section('HOW TO USE THE CALCULATOR')
for t in ['1.  Open the Calculator tab. Type your bodyweight in pounds in the first clay-outlined cell.',
          '2.  Pick your goal from the dropdown: Cut to lose fat, Recomp to hold your weight while changing shape, or Bulk to gain.',
          '3.  Leave the multiplier at 15 to start. Raise it toward 16 if you are very active or burn through food, and lower it toward 14 if you are not very active. It is how many calories per pound of bodyweight you burn in a day.',
          '4.  The deficit and surplus cells set how far below or above maintenance you eat on a Cut or Bulk. 400 below suits a steady cut and 250 above suits a lean bulk. Choose smaller numbers if you want slower change.',
          '5.  Set protein per pound. 0.8 is a good default. 0.7 to 1.0 is the usual range.',
          '6.  Read the two big results: your daily calorie target and your daily protein target. The Settings tab picks them up, and the app measures you against them.',
          '7.  Update your bodyweight every few weeks, or after you lose or gain about 5 lb, so the targets keep up with you.',
          '8.  To override a target by hand, type a number over the formula on the Settings tab. To go back, re-enter the link (=Calculator!C20 for calories, =Calculator!C21 for protein).',
          '9.  The examples at the bottom of the Calculator tab are made-up people. They show how the same rules change the targets. Delete them if you like. Nothing else depends on them.']: para(t)
para('Reading the results: if your 7-day average weight is not moving after two to three weeks, change the multiplier by 0.5 or the deficit or surplus by 100 and give it another two weeks. Predicted weekly change is only a rough guide.', color=MUT, italic=True)
gap(); section('ABOUT THE CALCULATOR')
para('The Calculator uses a common rule of thumb: maintenance calories = bodyweight x a multiplier (about 14 to 16). A cut subtracts a fixed deficit and a bulk adds a surplus. Protein = bodyweight x grams per pound. These are starting points, not medical advice.')
para('Watch your 7-day weight average for two to three weeks, and change the multiplier if your weight is not moving the way the calculator predicts. The predicted weekly change uses the rough 3,500 kcal per pound estimate.')
gap(); para('Template v1. Made-up examples only.', color=MUT, italic=True)
for r in range(1, row[0] + 2): ws.row_dimensions[r].height = ws.row_dimensions[r].height or 18

# ---------------------------------------------------------------- Calculator
ws = wb.create_sheet('Calculator'); base(ws, {'A': 3, 'B': 32, 'C': 17, 'D': 15, 'E': 19, 'F': 16, 'G': 14, 'H': 19}, CLAY)
for r in range(1, 36):
    for c in 'ABCDEFGH': put(ws, f'{c}{r}', bg=PAGE if r <= 3 else BG)
put(ws, 'B2', 'Calculator', font=F(name=SERIF, size=24, bold=True, color=CLAY), bg=PAGE); ws.row_dimensions[2].height = 36
put(ws, 'B3', 'Type in the clay-outlined cells. Everything else is calculated. The numbers shown are made-up examples.', font=F(size=10, color=MUT, italic=True), bg=PAGE)
def sect(r, t):
    for c in 'BCDEFGH': put(ws, f'{c}{r}', bg=BG, border=Border(bottom=side(CLAY, 'medium')))
    put(ws, f'B{r}', t, font=F(size=10, bold=True, color=CLAY), border=Border(bottom=side(CLAY, 'medium'))); ws.row_dimensions[r].height = 22
def inp(r, label, val, fmt, note):
    put(ws, f'B{r}', label, border=Border(bottom=side(LINE)))
    put(ws, f'C{r}', val, fmt=fmt, font=F(bold=True, color=CLAY, size=12), bg=INPUT, al=Alignment(horizontal='center', vertical='center'), border=Border(*(side(CLAY, 'medium'),) * 4))
    ws.merge_cells(f'D{r}:H{r}'); put(ws, f'D{r}', note, font=F(color=MUT, size=10), al=WRAP, border=Border(bottom=side(LINE)))
    ws.row_dimensions[r].height = 38
def res(r, label, formula, fmt, note='', big=False):
    put(ws, f'B{r}', label, font=F(bold=big, color=CLAY if big else TXT), bg=HDR if big else BG, border=Border(bottom=side(LINE)))
    put(ws, f'C{r}', formula, fmt=fmt, font=F(bold=True, size=14 if big else 11, color=CLAY if big else TXT), bg=HDR if big else BG,
        al=Alignment(horizontal='center', vertical='center'), border=Border(bottom=side(LINE)))
    ws.merge_cells(f'D{r}:H{r}'); put(ws, f'D{r}', note, font=F(color=MUT, size=10), bg=HDR if big else BG, al=WRAP, border=Border(bottom=side(LINE)))
    ws.row_dimensions[r].height = 26 if big else 22
sect(5, 'YOUR INPUTS')
inp(6, 'Bodyweight', 180, '0.0', 'Pounds (lb). Update it when your weight changes by about 5 lb or more.')
inp(7, 'Goal', 'Cut', None, 'Pick from the list: Cut (lose fat), Recomp (hold weight), Bulk (gain).')
inp(8, 'Maintenance multiplier', 15, '0.0', 'Calories per lb of bodyweight. About 14 = less active, 15 = average, 16 = very active.')
inp(9, 'Cut deficit', 400, '#,##0', 'Calories per day below maintenance when the goal is Cut.')
inp(10, 'Bulk surplus', 250, '#,##0', 'Calories per day above maintenance when the goal is Bulk.')
inp(11, 'Protein per lb', 0.8, '0.00', 'Grams of protein per lb of bodyweight. 0.7 to 1.0 is the usual range.')
inp(12, 'Steps goal', 10000, '#,##0', 'Daily steps the app measures you against.')
inp(13, 'Active calorie goal', 500, '#,##0', 'Calories burned through activity (from Oura) the app measures you against.')
sect(15, 'RESULTS')
res(16, 'Maintenance calories', '=C6*C8', '#,##0', 'Bodyweight x multiplier.')
res(17, 'Cut calories', '=C16-C9', '#,##0', 'Maintenance minus the deficit.')
res(18, 'Recomp calories', '=C16', '#,##0', 'Same as maintenance.')
res(19, 'Bulk calories', '=C16+C10', '#,##0', 'Maintenance plus the surplus.')
res(20, 'Daily calorie target', '=IF(C7="Cut",C17,IF(C7="Bulk",C19,C18))', '#,##0', 'Follows the goal you picked. This feeds the Settings tab and the app.', big=True)
res(21, 'Daily protein target (g)', '=ROUND(C6*C11,0)', '#,##0', 'Bodyweight x protein per lb. Feeds the Settings tab and the app.', big=True)
res(22, 'Protein share of calories', '=C21*4/C20', '0%', 'Protein has 4 calories per gram.')
res(23, 'Predicted weekly change (lb)', '=(C20-C16)*7/3500', '+0.0;-0.0;0.0', 'Rough: uses 3,500 calories per lb. Trust your 7-day weight average more.')
sect(25, 'WORKED EXAMPLES (ALL MADE UP)')
header(ws, 26, ['Example', 'Bodyweight (lb)', 'Goal', 'Maintenance (kcal)', 'Target (kcal)', 'Protein (g)', 'Weekly change (lb)'], c0=2, height=40)
for i, (nm, w_, g) in enumerate([('Lighter, cutting', 150, 'Cut'), ('Average, holding weight', 180, 'Recomp'), ('Heavier, bulking', 210, 'Bulk')]):
    r = 27 + i; bd = Border(bottom=side(LINE)); ctr = Alignment(horizontal='center', vertical='center')
    put(ws, f'B{r}', nm, border=bd); put(ws, f'C{r}', w_, fmt='0', al=ctr, border=bd); put(ws, f'D{r}', g, al=ctr, border=bd)
    put(ws, f'E{r}', f'=C{r}*$C$8', fmt='#,##0', al=ctr, border=bd)
    put(ws, f'F{r}', f'=E{r}+IF(D{r}="Cut",-$C$9,IF(D{r}="Bulk",$C$10,0))', fmt='#,##0', font=F(bold=True, color=CLAY), al=ctr, border=bd)
    put(ws, f'G{r}', f'=ROUND(C{r}*$C$11,0)', fmt='#,##0', al=ctr, border=bd)
    put(ws, f'H{r}', f'=(F{r}-E{r})*7/3500', fmt='+0.0;-0.0;0.0', al=ctr, border=bd); ws.row_dimensions[r].height = 22
dv = DataValidation(type='list', formula1='"Cut,Recomp,Bulk"', allow_blank=False, showErrorMessage=True, errorTitle='Goal', error='Choose Cut, Recomp or Bulk.'); ws.add_data_validation(dv); dv.add('C7')
dn = DataValidation(type='decimal', operator='between', formula1='50', formula2='700', showErrorMessage=True, errorTitle='Bodyweight', error='Enter pounds, between 50 and 700.'); ws.add_data_validation(dn); dn.add('C6')

# ---------------------------------------------------------------- Settings
ws = wb.create_sheet('Settings'); base(ws, {'A': 28, 'B': 14, 'C': 64}, TEAL)
for r in range(1, 12):
    for c in 'ABC': put(ws, f'{c}{r}')
for r, (lab, f_, note) in enumerate([('Calorie goal (kcal)', '=Calculator!C20', ''), ('Protein goal (g)', '=Calculator!C21', ''),
        ('Steps goal', '=Calculator!C12', ''), ('Active kcal goal', '=Calculator!C13', '')], 1):
    put(ws, f'A{r}', lab, border=Border(bottom=side(LINE)))
    put(ws, f'B{r}', f_, fmt='#,##0', font=F(bold=True, size=14, color=CLAY), bg=HDR, al=Alignment(horizontal='center', vertical='center'), border=Border(bottom=side(LINE)))
    put(ws, f'C{r}', 'Linked to the Calculator. Type a number over the formula to set your own.', font=F(color=MUT, size=10), border=Border(bottom=side(LINE)))
    ws.row_dimensions[r].height = 26
put(ws, 'A6', 'The app and the Today box read these four cells. Keep them in rows 1 to 4.', font=F(color=MUT, italic=True, size=10))

# ---------------------------------------------------------------- Oura
ws = wb.create_sheet('Oura'); base(ws, {'A': 12, **{L(i): 12.5 for i in range(2, 22)}, 'U': 18}, SAGE)
oh = ['Date', 'Sleep score', 'Readiness score', 'Activity score', 'Total sleep (h)', 'Deep (min)', 'REM (min)', 'Light (min)', 'Efficiency %', 'Avg HRV',
      'Lowest HR', 'Avg HR', 'Temp deviation (C)', 'Steps', 'Active kcal', 'Total kcal', 'Bedtime', 'Wake time', 'High-stress (min)', 'High-recovery (min)', 'Stress summary']
header(ws, 1, oh, height=40); ws.freeze_panes = 'B2'
for col, fmt in {'A': 'yyyy-mm-dd', 'E': '0.0', 'I': '0', 'M': '0.00', 'N': '#,##0', 'O': '#,##0', 'P': '#,##0', 'Q': 'h:mm AM/PM', 'R': 'h:mm AM/PM'}.items():
    for r in range(2, 402): ws[f'{col}{r}'].number_format = fmt
ws.conditional_formatting.add('B2:D1000', FormulaRule(formula=['AND(ISNUMBER(B2),B2>=85)'], font=Font(color=GOOD, bold=True)))
ws.conditional_formatting.add('B2:D1000', FormulaRule(formula=['AND(ISNUMBER(B2),B2<70)'], font=Font(color=BAD, bold=True)))
band(ws, 'A2:U1000')

# ---------------------------------------------------------------- Nutrition Log
ws = wb.create_sheet('Nutrition Log'); base(ws, {'A': 12, 'B': 9, 'C': 11, 'D': 46, 'E': 10, 'F': 11, 'G': 10, 'H': 9, 'I': 12, 'J': 16, 'K': 40, 'L': 3, 'M': 15, 'N': 11, 'O': 11, 'P': 12}, CLAY)
header(ws, 1, ['Date', 'Time', 'Meal', 'Items (est. grams)', 'Calories', 'Protein (g)', 'Carbs (g)', 'Fat (g)', 'Confidence', 'Source', 'Notes'], height=30); ws.freeze_panes = 'A2'
for col, fmt in {'A': 'yyyy-mm-dd', 'B': 'h:mm AM/PM', 'E': '#,##0', 'F': '0.0', 'G': '0.0', 'H': '0.0'}.items():
    for r in range(2, 1001): ws[f'{col}{r}'].number_format = fmt
band(ws, 'A2:K1000')
dm = DataValidation(type='list', formula1='"Breakfast,Lunch,Dinner,Snack,Dessert,Meal"', allow_blank=True); ws.add_data_validation(dm); dm.add('C2:C1000')
dc = DataValidation(type='list', formula1='"High,Medium,Low"', allow_blank=True); ws.add_data_validation(dc); dc.add('I2:I1000')
for i, t in enumerate(['Today', 'Eaten', 'Target', 'Remaining']):
    put(ws, f'{L(13+i)}1', t, font=F(bold=True, size=10), bg=HDR, al=Alignment(horizontal='center', vertical='center'), border=Border(bottom=side(CLAY, 'medium')))
box = [('Calories', '=SUMIF(A:A,TODAY(),E:E)', '=Settings!B1', '=O2-N2'), ('Protein (g)', '=SUMIF(A:A,TODAY(),F:F)', '=Settings!B2', '=O3-N3'),
       ('Carbs (g)', '=SUMIF(A:A,TODAY(),G:G)', None, None), ('Fat (g)', '=SUMIF(A:A,TODAY(),H:H)', None, None)]
for r, (a, b, c, d) in enumerate(box, 2):
    bd = Border(bottom=side(LINE)); ctr = Alignment(horizontal='center', vertical='center')
    put(ws, f'M{r}', a, font=F(bold=True, color=CLAY), bg=BG, border=bd)
    put(ws, f'N{r}', b, fmt='#,##0', al=ctr, bg=BG, border=bd); put(ws, f'O{r}', c, fmt='#,##0', al=ctr, bg=BG, border=bd); put(ws, f'P{r}', d, fmt='#,##0;-#,##0;0', al=ctr, bg=BG, border=bd)
ws.conditional_formatting.add('P2:P3', FormulaRule(formula=['AND(ISNUMBER(P2),P2<0)'], font=Font(color=BAD, bold=True)))
put(ws, 'M7', 'Today box: the app reads M1:P5. Do not move it.', font=F(color=MUT, italic=True, size=9), bg=BG)

# ---------------------------------------------------------------- Weight Log
ws = wb.create_sheet('Weight Log'); base(ws, {'A': 12, 'B': 14, 'C': 12, 'D': 18}, TEAL)
header(ws, 1, ['Date', 'Weight (lb)', '7-day avg', 'Change vs prev day'], height=30); ws.freeze_panes = 'A2'
for r in range(2, 401):
    put(ws, f'A{r}', fmt='yyyy-mm-dd'); put(ws, f'B{r}', fmt='0.0')
    put(ws, f'C{r}', f'=IF(ISNUMBER(B{r}),ROUND(AVERAGEIFS($B$2:$B$1000,$A$2:$A$1000,">"&A{r}-7,$A$2:$A$1000,"<="&A{r}),1),"")', fmt='0.0')
    put(ws, f'D{r}', f'=IF(AND(ISNUMBER(B{r}),ISNUMBER(A{r-1}),ISNUMBER(B{r-1})),IF(A{r}-A{r-1}=1,B{r}-B{r-1},""),"")', fmt='+0.0;-0.0;0.0')
band(ws, 'A2:D1000')

# ---------------------------------------------------------------- Training Log
ws = wb.create_sheet('Training Log'); base(ws, {'A': 12, 'B': 9, 'C': 18, 'D': 28, 'E': 13, 'F': 8, 'G': 10, 'H': 40}, ROSE)
header(ws, 1, ['Date', 'Time', 'Workout', 'Exercise', 'Weight (lb)', 'Sets', 'Reps', 'Notes'], height=30); ws.freeze_panes = 'A2'
for col, fmt in {'A': 'yyyy-mm-dd', 'B': 'h:mm AM/PM', 'E': '0.#'}.items():
    for r in range(2, 1001): ws[f'{col}{r}'].number_format = fmt
band(ws, 'A2:H1000')

wb.active = 0
os.makedirs(os.path.dirname(OUT), exist_ok=True); wb.save(OUT); print('saved', OUT)
