'In-process tests of jev-column / jev-selected, modelled on visidata/tests/test_llm.py.'

import json
import threading
import time

import pytest

import visidata
from visidata import vd, ItemColumn
from visidata.errors import ExpectedException

import vd_jev  # noqa: F401  registers the commands
from conftest import deterministic_answer

OPTIONS = ('jev_api_url', 'jev_confirm_rows', 'jev_concurrency', 'jev_model', 'jev_timeout')


@pytest.fixture
def jev(fakejev, monkeypatch):
    'Point the plugin at the loopback server and record status messages.'
    import curses
    monkeypatch.setattr(curses, 'curs_set', lambda v: None, raising=False)
    monkeypatch.setattr(curses, 'doupdate', lambda: None, raising=False)
    monkeypatch.setenv('OPENROUTER_API_KEY', 'sk-test')
    saved = {k: vd.options[k] for k in OPTIONS}
    vd.options.jev_api_url = fakejev.url
    fakejev.responder = deterministic_answer
    fakejev.statuses = []
    monkeypatch.setattr(vd, 'status', lambda *args, **kwargs: fakejev.statuses.append(' '.join(map(str, args))), raising=False)
    fakejev.warnings = []
    monkeypatch.setattr(vd, 'warning', lambda *args, **kwargs: fakejev.warnings.append(' '.join(map(str, args))), raising=False)
    yield fakejev
    for k, v in saved.items():
        vd.options[k] = v


def textsheet(*texts):
    sheet = visidata.Sheet('jevtest', columns=[ItemColumn('text', 0), ItemColumn('other', 1)], rows=[[t, 'x'] for t in texts])
    sheet.ensureLoaded()
    return sheet


def ask(sheet, question='q?', answers=''):
    sheet.jevAsk(sheet.column('text'), sheet.rows, question, answers)
    vd.sync()
    return {c.name: [c.getValue(r) for r in sheet.rows] for c in sheet.columns}


def test_noul(jev):
    cols = ask(textsheet('abc', '', 'abcdefg'), 'Does it report a hazard?')
    assert list(cols) == ['text', 'text_noul', 'text_noul_raw', 'other']
    assert cols['text_noul'] == [0.3, None, 0.7]
    assert json.loads(cols['text_noul_raw'][0]) == {'type': 'noul', 'noul': 0.3}
    assert len(jev.requests) == 2
    assert jev.statuses[-1] == 'jev noul: 2 rows answered, 1 skipped (empty), 0 errors, 0.000020 USD'


def test_choice(jev):
    cols = ask(textsheet('ab', 'abc'), 'Which department?', 'roads, parks, noise')
    assert list(cols) == ['text', 'text_choice', 'text_choice_conf', 'text_choice_p', 'text_choice_raw', 'other']
    assert cols['text_choice'] == ['noise', 'roads']
    assert cols['text_choice_conf'] == [0.9, 0.9]
    assert cols['text_choice_p'][1] == {'roads': 0.9, 'parks': 0.05, 'noise': 0.05}
    assert jev.requests[0]['body']['questions']['answer']['criteria'] == {'roads': None, 'parks': None, 'noise': None}


def test_score(jev):
    cols = ask(textsheet('ab'), 'How urgent?', 'low < medium < high')
    assert cols['text_score'] == [2.0]
    assert cols['text_score_conf'] == [0.8]
    assert cols['text_score_p'] == [{'low': 0.1, 'medium': 0.1, 'high': 0.8}]
    assert jev.requests[0]['body']['questions']['answer']['criteria'] == ['low', 'medium', 'high']


def test_probabilities_expand_into_columns(jev):
    'VisiData expand-col (`(`) turns the _p column into one float column per label.'
    sheet = textsheet('ab', 'abc')
    ask(sheet, 'Which department?', 'roads, parks, noise')
    sheet.expand_cols_deep([sheet.column('text_choice_p')], depth=1)
    vd.sync()
    names = [c.name for c in sheet.columns]
    assert ['text_choice_p.roads', 'text_choice_p.parks', 'text_choice_p.noise'] == [n for n in names if n.startswith('text_choice_p.')]
    assert [sheet.column('text_choice_p.roads').getTypedValue(r) for r in sheet.rows] == [0.05, 0.9]


def test_descriptions_sent_but_not_returned(jev):
    cols = ask(textsheet('ab', 'abc'), 'Which department?', 'roads (potholes, markings), parks (green areas), noise')
    assert jev.requests[0]['body']['questions']['answer']['criteria'] == {'roads': 'potholes, markings', 'parks': 'green areas', 'noise': None}
    assert cols['text_choice'] == ['noise', 'roads']
    assert list(cols['text_choice_p'][0]) == ['roads', 'parks', 'noise']
    cols = ask(textsheet('ab'), 'How urgent?', 'low (can wait) < medium < high (danger now)')
    assert jev.requests[-1]['body']['questions']['answer']['criteria'] == ['low: can wait', 'medium', 'high: danger now']
    assert list(cols['text_score_p'][0]) == ['low', 'medium', 'high']


def test_request_uses_options(jev):
    vd.options.jev_model = 'typesafe/jev-test'
    ask(textsheet('a fallen tree'), 'Is it a hazard?')
    req, = jev.requests
    assert req['body'] == {'model': 'typesafe/jev-test', 'state': 'a fallen tree',
                           'questions': {'answer': {'type': 'noul', 'instructions': 'Is it a hazard?'}}}
    assert req['headers']['Authorization'] == 'Bearer sk-test'


def test_error_row(jev):
    vd.options.jev_concurrency = 1  # so that the scripted error goes to the first row
    jev.reply({'error': {'message': 'boom'}}, status=500)
    cols = ask(textsheet('a', 'b'))
    assert cols['text_noul'] == [None, 0.1]
    assert cols['text_noul_raw'][0] == 'error: request failed with HTTP 500: boom'
    assert jev.statuses[-1] == 'jev noul: 1 rows answered, 0 skipped (empty), 1 errors, 0.000010 USD'


@pytest.mark.parametrize('question, answers, message', [
    ('', '', 'no question'),
    ('q?', 'roads', 'choice needs at least 2 labels'),
    ('q?', 'roads, roads', 'labels must be unique'),
    ('q?', 'low <', 'empty label'),
])
def test_invalid_input_fails_before_anything(jev, question, answers, message):
    sheet = textsheet('a')
    with pytest.raises(ExpectedException, match=message):
        sheet.jevAsk(sheet.column('text'), sheet.rows, question, answers)
    assert len(sheet.columns) == 2
    assert jev.requests == []


def test_missing_key_fails_before_anything(jev, monkeypatch):
    monkeypatch.delenv('OPENROUTER_API_KEY')
    sheet = textsheet('a')
    with pytest.raises(ExpectedException, match='OPENROUTER_API_KEY'):
        sheet.jevAsk(sheet.column('text'), sheet.rows, 'q?', '')
    assert len(sheet.columns) == 2


def test_no_rows(jev):
    sheet = textsheet('a')
    with pytest.raises(ExpectedException, match='no rows selected'):
        sheet.jevAsk(sheet.column('text'), [], 'q?', '')


def test_confirm_in_main_thread(jev, monkeypatch):
    confirmed = []
    monkeypatch.setattr(vd, 'confirm', lambda prompt, *a, **kw: confirmed.append((prompt, threading.current_thread())), raising=False)
    vd.options.jev_confirm_rows = 2
    ask(textsheet('a', 'b', '', 'c'))
    assert confirmed == [('send 3 rows to `typesafe/jev-1.14`? ', threading.current_thread())]


def test_no_confirm_at_threshold(jev, monkeypatch):
    monkeypatch.setattr(vd, 'confirm', lambda *a, **kw: pytest.fail('confirm called'), raising=False)
    vd.options.jev_confirm_rows = 2
    ask(textsheet('a', 'b'))


def test_cancel_stops_pending_requests(jev):
    vd.options.jev_concurrency = 1
    for _ in range(10):
        jev.reply({'answers': {'answer': {'type': 'noul', 'noul': 0.5}}}, delay=0.2)
    sheet = textsheet(*'abcdefghij')
    vd.options.jev_confirm_rows = 100
    sheet.jevAsk(sheet.column('text'), sheet.rows, 'q?', '')
    time.sleep(0.5)
    vd.cancelThread(*[t for t in vd.unfinishedThreads if t.name.startswith('jevRun')])
    vd.sync()
    time.sleep(0.3)  # let an in-flight request finish
    assert len(jev.requests) < 10
    assert any(s.startswith('jev noul: ') for s in jev.statuses)  # partial summary, then VisiData's `jevRun aborted`


def test_menu():
    column = next(m for m in vd.menus if m.title == 'Column')
    jevmenu = next(m for m in column.menus if m.title == 'Jev')
    assert [(m.title, m.longname) for m in jevmenu.menus] == [('all rows', 'jev-column'), ('selected rows', 'jev-selected')]


@pytest.mark.parametrize('longname', ['jev-column', 'jev-selected'])
def test_execstr_compiles(longname):
    'As test_command_execstrs_compile in VisiData; `input` in the execstr lets the menu show that the command asks for input.'
    cmd = visidata.Sheet('x').getCommand(longname)
    compile(cmd.execstr, longname, 'exec')
    assert 'input' in cmd.execstr


def test_cursor_stays_on_source_column(jev):
    'So that several questions can be asked in a row without moving back to the text column.'
    sheet = textsheet('abc')
    sheet.cursorVisibleColIndex = 0
    ask(sheet, 'q?', 'roads, parks')
    assert sheet.cursorCol.name == 'text'


@pytest.mark.parametrize('status, message, hint', [
    (401, 'User not found.', 'check $OPENROUTER_API_KEY'),
    (402, 'Insufficient credits', 'add credit at https://openrouter.ai/settings/credits'),
])
def test_refused_key_stops_the_run(jev, status, message, hint):
    'A key OpenRouter refuses fails every row the same way: stop at the first refusal instead of sending them all.'
    vd.options.jev_concurrency = 1
    jev.reply({'error': {'message': message, 'code': status}}, status=status)
    sheet = textsheet(*'abcde')
    ask(sheet)
    time.sleep(0.3)  # nothing else may arrive late
    assert len(jev.requests) == 1
    assert jev.warnings[-1] == f'stopped: request failed with HTTP {status}: {message.rstrip(".")}; {hint}'
    assert jev.statuses[-1] == 'jev noul: 0 rows answered, 0 skipped (empty), 1 errors, 0.000000 USD'
