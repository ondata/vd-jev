'Ask the buyer-kind question again with label descriptions and compare with the run of demo/ted_questions.py (about 0.02 USD).'
import csv, os, sys, concurrent.futures as cf
sys.path.insert(0, '.')
from vd_jev import jev_ask, jev_build_question, jev_parse_answers
URL = 'https://openrouter.ai/api/alpha/decisions'; KEY = os.environ['OPENROUTER_API_KEY']
ANSWERS = ('municipality or local government (county, city and town councils, local authorities), '
           'hospital or health service (hospitals, clinics, national or regional health services that run care), '
           'school or university (schools, colleges, universities, institutes of technology, education and training boards), '
           'national ministry or agency (government departments, national agencies, regulators, central purchasing bodies), '
           'utility or transport company (energy, water, waste, rail, bus, ports, airports), '
           'other (charities, foundations, private companies, anything else)')
kind, labels, descs = jev_parse_answers(ANSWERS)
q = jev_build_question(kind, 'What kind of organisation is this buyer?', labels, descs)
rows = list(csv.DictReader(open('tmp/ted/ted_answers.csv')))
with cf.ThreadPoolExecutor(8) as ex:
    res = list(ex.map(lambda r: jev_ask(r['buyer'], q, KEY, 'typesafe/jev-1.14', URL, 60, labels), rows))
print('cost', round(sum(r['cost'] for r in res), 6))
with open('tmp/ted/kind_v2.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['notice_id', 'buyer', 'main_activity', 'kind_v1', 'conf_v1', 'kind_v2', 'conf_v2'])
    for r, a in zip(rows, res):
        w.writerow([r['notice_id'], r['buyer'], r['main_activity'], r['buyer_choice'], r['buyer_choice_conf'], a['value'], a['confidence']])
