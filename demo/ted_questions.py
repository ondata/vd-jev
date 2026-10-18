'Run the TED example questions through the plugin with real calls (about 0.03 USD); see README, A real example.'
import csv, curses, json, os, sys, time
sys.path.insert(0, '.')
import visidata
from visidata import vd
import vd_jev  # noqa: F401

curses.curs_set = lambda v: None
curses.doupdate = lambda: None
vd.options.confirm = 'y'
statuses = []
vd.status = lambda *a, **k: statuses.append(' '.join(map(str, a)))

sheet = vd.openSource('demo/ted_sample.csv')
sheet.ensureLoaded(); vd.sync()
QUESTIONS = [
    ('buyer', 'The buyer is a hospital or other health care provider', ''),
    ('buyer', 'What kind of organisation is this buyer?',
     'municipality or local government, hospital or health service, school or university, national ministry or agency, utility or transport company, other'),
    ('award_criteria', 'At least one award criterion concerns environmental sustainability (emissions, energy, recycling, eco-labels, sustainable development)', ''),
]
summary = []
for colname, question, answers in QUESTIONS:
    col = sheet.column(colname)
    t0 = time.time()
    sheet.jev_column(col, sheet.rows, question, answers)
    vd.sync()
    secs = round(time.time() - t0, 1)
    last = [s for s in statuses if s.startswith('jev ')][-1]
    summary.append(dict(column=colname, question=question, answers=answers, seconds=secs, status=last))
    print(secs, 's |', last, flush=True)

os.makedirs('tmp/ted', exist_ok=True)
cols = [c for c in sheet.columns]
with open('tmp/ted/ted_answers.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow([c.name for c in cols])
    for r in sheet.rows:
        row = []
        for c in cols:
            v = c.getValue(r)
            row.append(json.dumps(v) if isinstance(v, dict) else ('' if v is None else v))
        w.writerow(row)
json.dump(summary, open('tmp/ted/run_summary.json', 'w'), indent=1)
