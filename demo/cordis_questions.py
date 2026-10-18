'Ask the field of science of 1000 Horizon 2020 projects, without and with label descriptions, through the plugin (real calls, about 0.06 USD).'
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

QUESTION = 'Which field of science is this research project mainly about?'
PLAIN = 'natural sciences, engineering and technology, medical and health sciences, agricultural sciences, social sciences, humanities'
DESCRIBED = ('natural sciences (mathematics, computer and information sciences, physics, chemistry, earth and environmental sciences, biology), '
             'engineering and technology (civil, electrical, mechanical, chemical, materials and environmental engineering, biotechnology, nanotechnology), '
             'medical and health sciences (basic and clinical medicine, health sciences, medical biotechnology), '
             'agricultural sciences (agriculture, forestry, fisheries, animal and dairy science, veterinary science), '
             'social sciences (psychology, economics, business, education, sociology, law, political science, geography, media), '
             'humanities (history, archaeology, languages, literature, philosophy, ethics, religion, arts)')

sheet = vd.openSource('demo/cordis_sample.csv')
sheet.ensureLoaded(); vd.sync()
results = {}
for name, answers in [('plain', PLAIN), ('described', DESCRIBED)]:
    t0 = time.time()
    sheet.jevAsk(sheet.column('objective'), sheet.rows, QUESTION, answers)
    vd.sync()
    print(name, round(time.time() - t0, 1), 's |', [s for s in statuses if s.startswith('jev ')][-1], flush=True)
    valuecol = [c for c in sheet.columns if c.name == 'objective_choice'][0]
    confcol = [c for c in sheet.columns if c.name == 'objective_choice_conf'][0]
    results[name] = [(valuecol.getValue(r), confcol.getValue(r)) for r in sheet.rows]
    sheet.columns = [c for c in sheet.columns if not c.name.startswith('objective_choice')]  # next run starts clean

os.makedirs('tmp/cordis', exist_ok=True)
field = sheet.column('field'); pid = sheet.column('project_id')
with open('tmp/cordis/cordis_answers.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['project_id', 'field', 'plain', 'plain_conf', 'described', 'described_conf'])
    for r, a, b in zip(sheet.rows, results['plain'], results['described']):
        w.writerow([pid.getValue(r), field.getValue(r), *a, *b])
