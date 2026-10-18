'''
# vd-jev

Ask closed questions about every cell of a text column with a decision model
on OpenRouter: Jev, TypeSafe's model, by default, or any other model that
OpenRouter's Decisions API serves (set `vd.options.jev_model`). Answers come back as typed columns:
a probability (noul), a label from a fixed list (choice), or a position on an
ordered scale (score), each with a calibrated confidence.

## Usage

1. Move the cursor to a column of text.
2. Run `jev-column` (or `jev-selected` for the selected rows only).
3. Fill in the form:
   - `question`: a closed question, e.g. "Which department should handle this?"
   - `answers`: empty for a yes/no question, `roads, parks, noise` to pick one
     label, `low < medium < high` for a position on an ordered scale.
     A description for the model may follow a label in parentheses:
     `roads (potholes, street lighting), parks, noise`; it is never returned.
4. New columns appear next to the source column:
   - `{colname}_noul`: probability that the answer is yes (0-1)
   - `{colname}_choice`, `{colname}_choice_conf`: label and confidence
   - `{colname}_score`, `{colname}_score_conf`: position from 0 to n-1 and confidence
   - `{colname}_choice_p`, `{colname}_score_p`: probability of every label or level;
     `(` (expand-col) turns it into one column per label
   - `{colname}_<type>_raw` (hidden, `gv` shows it): the full answer as JSON, or the error

## Configuration

Set in ~/.visidatarc, or with Shift+O:

    vd.options.jev_model = 'typesafe/jev-1.14'   # any id from https://openrouter.ai/api/v1/models?output_modalities=decisions
    vd.options.jev_api_url = 'https://openrouter.ai/api/alpha/decisions'
    vd.options.jev_concurrency = 8      # parallel requests
    vd.options.jev_confirm_rows = 100   # ask before sending more rows than this
    vd.options.jev_timeout = 30         # seconds per request

    export OPENROUTER_API_KEY="..."

Cell text is sent to OpenRouter and TypeSafe (USA).
'''

__author__ = 'Andrea Borruso <aborruso@gmail.com>'
__version__ = '0.1.0'

import concurrent.futures
import json
import os
import threading
import time
import urllib.error
import urllib.request

from visidata import vd, VisiData, Sheet, SettableColumn, asyncthread, Progress

vd.option('jev_model', 'typesafe/jev-1.14', 'decision model id on OpenRouter (Jev by default)')
vd.option('jev_api_url', 'https://openrouter.ai/api/alpha/decisions', 'OpenRouter Decisions API endpoint')
vd.option('jev_concurrency', 8, 'number of parallel requests to the decision model')
vd.option('jev_confirm_rows', 100, 'ask for confirmation before sending more rows than this')
vd.option('jev_timeout', 30, 'seconds to wait for each request')

JEV_KINDS = ('noul', 'choice', 'score')
JEV_MAX_SCORE_LEVELS = 10
JEV_QUESTION_KEY = 'answer'


class JevError(Exception):
    'Any failure asking the decision model: invalid question, HTTP error, timeout, malformed answer.'
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status  # HTTP status code, when the failure is an HTTP error


# HTTP codes that would refuse every row in the same way: stop the run at the first one
JEV_STOP_HINTS = {
    401: 'check $OPENROUTER_API_KEY',
    402: 'add credit at https://openrouter.ai/settings/credits',
}


def _split_outside_parens(text, sep):
    'Split *text* on *sep*, except inside parentheses.'
    parts, depth, cur = [], 0, ''
    for ch in text:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth < 0:
                raise JevError('unbalanced parentheses in answers')
        if ch == sep and depth == 0:
            parts.append(cur)
            cur = ''
        else:
            cur += ch
    if depth != 0:
        raise JevError('unbalanced parentheses in answers')
    return parts + [cur]


def _outside_parens(text):
    'Return *text* without the parts in parentheses (balance is checked by _split_outside_parens).'
    out, depth = '', 0
    for ch in text:
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
        elif depth <= 0:
            out += ch
    return out


def _label_and_description(item):
    'Split `roads (potholes, markings)` into (`roads`, `potholes, markings`); no parentheses -> (item, None).'
    item = item.strip()
    if item.endswith(')') and '(' in item:
        name, desc = item[:-1].split('(', 1)
        return name.strip(), desc.strip() or None
    return item, None


def jev_parse_answers(text):
    '''Return (kind, labels, descriptions) from the answers the user typed:
    empty -> noul; `a, b, c` -> choice; `low < medium < high` -> score, lowest first.
    A label may carry a description for the model in parentheses: `roads (potholes, markings)`;
    commas and `<` inside parentheses do not separate. descriptions[i] is None when there is none.'''
    text = (text or '').strip()
    if not text:
        return 'noul', [], []
    kind, sep = ('score', '<') if '<' in _outside_parens(text) else ('choice', ',')
    items = [_label_and_description(item) for item in _split_outside_parens(text, sep)]
    return kind, [name for name, _ in items], [desc for _, desc in items]


def jev_build_question(kind, instructions, labels=None, descriptions=None):
    '''Return the question object for one question of type *kind*.
    *descriptions* (optional, aligned with *labels*) are sent to the model only.'''
    if kind not in JEV_KINDS:
        raise JevError(f'unknown question type `{kind}`; use one of {", ".join(JEV_KINDS)}')
    instructions = (instructions or '').strip()
    if not instructions:
        raise JevError('no question')

    question = {'type': kind, 'instructions': instructions}
    if kind == 'noul':
        return question

    labels = [label.strip() for label in (labels or [])]
    if any(not label for label in labels):
        raise JevError('empty label')
    if len(set(labels)) != len(labels):
        raise JevError('labels must be unique')
    if len(labels) < 2:
        raise JevError(f'{kind} needs at least 2 labels')

    descriptions = list(descriptions or []) + [None] * (len(labels) - len(descriptions or []))
    if kind == 'choice':
        question['criteria'] = dict(zip(labels, descriptions))
    else:
        if len(labels) > JEV_MAX_SCORE_LEVELS:
            raise JevError(f'score accepts at most {JEV_MAX_SCORE_LEVELS} levels')
        # lowest level first; a level is plain text, so the description goes after the label
        question['criteria'] = [f'{label}: {desc}' if desc else label for label, desc in zip(labels, descriptions)]
    return question


def jev_build_request(state, question, model):
    'Return the request body asking *question* about the text *state*.'
    return {'model': model, 'state': state, 'questions': {JEV_QUESTION_KEY: question}}


def _http_error_message(e):
    'Readable message from an HTTPError, from the OpenRouter error body when there is one.'
    try:
        message = json.loads(e.read().decode('utf-8'))['error']['message']
    except Exception:
        message = e.reason
    return f'request failed with HTTP {e.code}: {str(message).rstrip(".")}'


def _retry_delay(e, attempt):
    'Seconds to wait before retrying a 429: retry-after if numeric, else exponential backoff.'
    try:
        return float(e.headers.get('retry-after'))
    except (TypeError, ValueError):
        return 2 ** attempt


def jev_send(body, api_key, url, timeout, retries=3):
    'POST *body* to OpenRouter and return the decoded JSON response; retry up to *retries* times on 429.'
    data = json.dumps(body).encode('utf-8')
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                time.sleep(_retry_delay(e, attempt))
                continue
            raise JevError(_http_error_message(e), status=e.code) from e
        except urllib.error.URLError as e:
            raise JevError(f'cannot reach OpenRouter: {e.reason}') from e
        except TimeoutError as e:
            raise JevError(f'no answer from OpenRouter within {timeout}s') from e
        except json.JSONDecodeError as e:
            raise JevError('answer from OpenRouter is not JSON') from e


def _float_or_none(x):
    return None if x is None else float(x)


def jev_parse_answer(question, response, labels=None):
    '''Return dict(value, confidence, probabilities, raw, cost) from a Jev *response* to *question*.

    value is a float for noul and score, one of the labels for choice;
    confidence is None for noul; probabilities maps each label (choice) or level
    (score, in scale order) to its probability, None for noul or when the model omits them.
    *labels* are the short labels, used as keys when the score levels carry descriptions.'''
    kind = question['type']
    probabilities = None
    try:
        answer = response['answers'][JEV_QUESTION_KEY]
        if kind == 'noul':
            value, confidence = float(answer['noul']), None
        elif kind == 'choice':
            value, confidence = answer['choice'], float(answer['confidence'])
            if answer.get('probabilities') is not None:
                probs = answer['probabilities']
                probabilities = {label: _float_or_none(probs.get(label)) for label in question['criteria']}
        else:
            value, confidence = float(answer['score']), float(answer['confidence'])
            if answer.get('probabilities') is not None:  # keyed "0", "1", ...: back to the level names
                probs = answer['probabilities']
                probabilities = {level: _float_or_none(probs.get(str(i))) for i, level in enumerate(labels or question['criteria'])}
        cost = float((response.get('usage') or {}).get('cost') or 0)
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        raise JevError(f'malformed {kind} answer from the model') from e
    if kind == 'choice' and value not in question['criteria']:
        raise JevError(f'the model chose `{value}`, which is not one of the labels')
    return dict(value=value, confidence=confidence, probabilities=probabilities, raw=json.dumps(answer), cost=cost)


def jev_ask(state, question, api_key, model, url, timeout, labels=None):
    'Ask *question* about *state* and return the parsed answer.'
    return jev_parse_answer(question, jev_send(jev_build_request(state, question, model), api_key, url, timeout), labels)


@VisiData.api
def inputJev(vd):
    'Ask for the question and the answers in one form; return dict(question=, answers=).'
    return vd.inputMultiple(
        question=dict(prompt='question: ', type='jev-question',
                      help='a closed question about each cell, e.g. `Does the message report a safety hazard?`'),
        answers=dict(prompt='answers: ', type='jev-answers',
                     help='empty for yes/no; `roads, parks, noise` to pick one label; `low < medium < high` for an ordered scale'))


@Sheet.api
def jev_column(sheet, col, rows, question='', answers=''):
    'Ask the decision model *question* about the text of *col* in each of *rows*; add the answers as new columns.'
    try:
        kind, labels, descriptions = jev_parse_answers(answers)
        q = jev_build_question(kind, question, labels, descriptions)
    except JevError as e:
        vd.fail(str(e))

    api_key = os.environ.get('OPENROUTER_API_KEY') or vd.fail('set $OPENROUTER_API_KEY (get a key at https://openrouter.ai/keys)')
    if not rows:
        vd.fail('no rows selected')

    todo = []
    for row in rows:
        text = col.getFullDisplayValue(row).strip()
        if text:
            todo.append((row, text))

    if len(todo) > vd.options.jev_confirm_rows:
        vd.confirm(f'send {len(todo)} rows to `{vd.options.jev_model}`? ')

    valuecol = SettableColumn(f'{col.name}_{kind}', type=str if kind == 'choice' else float)
    newcols = [valuecol]
    confcol = probcol = None
    if kind != 'noul':
        confcol = SettableColumn(f'{col.name}_{kind}_conf', type=float)
        probcol = SettableColumn(f'{col.name}_{kind}_p')  # dict of probabilities; `(` expands it into columns
        newcols += [confcol, probcol]
    rawcol = SettableColumn(f'{col.name}_{kind}_raw', type=str, width=0)  # hidden
    newcols.append(rawcol)
    sheet.addColumnAtCursor(*newcols)
    if col in sheet.visibleCols:  # stay on the text column, ready for the next question
        sheet.cursorVisibleColIndex = sheet.visibleCols.index(col)

    sheet._jev_run(todo, q, labels, api_key, len(rows)-len(todo), valuecol, confcol, probcol, rawcol)


@Sheet.api
@asyncthread
def _jev_run(sheet, todo, question, labels, api_key, nskipped, valuecol, confcol, probcol, rawcol):
    'Send one request per (row, text) in *todo*, *jev_concurrency* at a time, and fill the result columns.'
    args = (question, api_key, vd.options.jev_model, vd.options.jev_api_url, vd.options.jev_timeout)
    answered = errors = 0
    cost = 0.0
    stopped = False
    refused = threading.Event()

    def ask(text):
        'Run in the pool: do not send anything once a request has been refused.'
        if refused.is_set():
            return None
        try:
            return jev_ask(text, *args, labels=labels)
        except JevError as e:
            if e.status in JEV_STOP_HINTS:
                refused.set()
            raise

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=max(1, vd.options.jev_concurrency))
    try:
        pending = {pool.submit(ask, text): row for row, text in todo}
        with Progress(gerund=f'asking {vd.options.jev_model}', total=len(pending)) as prog:
            while pending and not stopped:
                # short waits, so that Ctrl+C reaches this thread quickly
                done, _ = concurrent.futures.wait(pending, timeout=0.25, return_when=concurrent.futures.FIRST_COMPLETED)
                for fut in done:
                    row = pending.pop(fut)
                    prog.addProgress(1)
                    try:
                        r = fut.result()
                    except Exception as e:
                        vd.exceptionCaught(e)
                        rawcol.setValue(row, f'error: {e}')
                        errors += 1
                        hint = JEV_STOP_HINTS.get(getattr(e, 'status', None))
                        if hint:
                            vd.warning(f'stopped: {e}; {hint}')
                            stopped = True
                            break
                        continue
                    if r is None:  # not sent, after a refusal
                        continue
                    valuecol.setValue(row, r['value'])
                    if confcol:
                        confcol.setValue(row, r['confidence'])
                        probcol.setValue(row, r['probabilities'])
                    rawcol.setValue(row, r['raw'])
                    answered += 1
                    cost += r['cost']
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
        vd.status(f'jev {question["type"]}: {answered} rows answered, {nskipped} skipped (empty), {errors} errors, {cost:.6f} USD')


# no default keybindings, as in experimental/llm.py
Sheet.addCommand('', 'jev-column', 'jev_column(cursorCol, rows, **vd.inputJev())',
    'ask a decision model a closed question about every row of current column; add the answers as new columns')
Sheet.addCommand('', 'jev-selected', 'jev_column(cursorCol, someSelectedRows, **vd.inputJev())',
    'ask a decision model a closed question about selected rows of current column; add the answers as new columns')

vd.addMenuItems('''
    Column > Jev > all rows > jev-column
    Column > Jev > selected rows > jev-selected
''')
