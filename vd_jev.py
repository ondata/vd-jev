'''
# vd-jev

Ask closed questions about every cell of a text column with Jev, TypeSafe's
decision model, called through OpenRouter. Answers come back as typed columns:
a probability (noul), a label from a fixed list (choice), or a position on an
ordered scale (score), each with a calibrated confidence.

## Configuration

Set in ~/.visidatarc, or with Shift+O:

    vd.options.jev_model = 'typesafe/jev-1.14'
    vd.options.jev_api_url = 'https://openrouter.ai/api/v1/systemone'
    vd.options.jev_concurrency = 8      # parallel requests
    vd.options.jev_confirm_rows = 100   # ask before sending more rows than this
    vd.options.jev_timeout = 30         # seconds per request

    export OPENROUTER_API_KEY="..."

Cell text is sent to OpenRouter and TypeSafe (USA).
'''

__author__ = 'Andrea Borruso <aborruso@gmail.com>'
__version__ = '0.1.0'

import json
import time
import urllib.error
import urllib.request

from visidata import vd

vd.option('jev_model', 'typesafe/jev-1.14', 'Jev model id on OpenRouter')
vd.option('jev_api_url', 'https://openrouter.ai/api/v1/systemone', 'Jev System One endpoint')
vd.option('jev_concurrency', 8, 'number of parallel Jev requests')
vd.option('jev_confirm_rows', 100, 'ask for confirmation before sending more rows than this to Jev')
vd.option('jev_timeout', 30, 'seconds to wait for each Jev request')

JEV_KINDS = ('noul', 'choice', 'score')
JEV_MAX_SCORE_LEVELS = 10
JEV_QUESTION_KEY = 'answer'


class JevError(Exception):
    'Any failure asking Jev: invalid question, HTTP error, timeout, malformed answer.'


def jev_parse_labels(text):
    'Split comma-separated labels, drop blanks, keep order.'
    return [label.strip() for label in (text or '').split(',') if label.strip()]


def jev_build_question(kind, instructions, labels=None):
    'Return the question object for one Jev question of type *kind*.'
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

    if kind == 'choice':
        question['criteria'] = {label: None for label in labels}
    else:
        if len(labels) > JEV_MAX_SCORE_LEVELS:
            raise JevError(f'score accepts at most {JEV_MAX_SCORE_LEVELS} levels')
        question['criteria'] = labels  # lowest level first
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
    return f'Jev returned HTTP {e.code}: {message}'


def _retry_delay(e, attempt):
    'Seconds to wait before retrying a 429: retry-after if numeric, else exponential backoff.'
    try:
        return float(e.headers.get('retry-after'))
    except (TypeError, ValueError):
        return 2 ** attempt


def jev_send(body, api_key, url, timeout, retries=3):
    'POST *body* to Jev and return the decoded JSON response; retry up to *retries* times on 429.'
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
            raise JevError(_http_error_message(e)) from e
        except urllib.error.URLError as e:
            raise JevError(f'cannot reach Jev: {e.reason}') from e
        except TimeoutError as e:
            raise JevError(f'no answer from Jev within {timeout}s') from e
        except json.JSONDecodeError as e:
            raise JevError('Jev answer is not JSON') from e


def jev_parse_answer(question, response):
    '''Return dict(value, confidence, raw, cost) from a Jev *response* to *question*.

    value is a float for noul and score, one of the labels for choice;
    confidence is None for noul.'''
    kind = question['type']
    try:
        answer = response['answers'][JEV_QUESTION_KEY]
        if kind == 'noul':
            value, confidence = float(answer['noul']), None
        elif kind == 'choice':
            value, confidence = answer['choice'], float(answer['confidence'])
        else:
            value, confidence = float(answer['score']), float(answer['confidence'])
        cost = float((response.get('usage') or {}).get('cost') or 0)
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        raise JevError(f'malformed {kind} answer from Jev') from e
    if kind == 'choice' and value not in question['criteria']:
        raise JevError(f'Jev chose `{value}`, which is not one of the labels')
    return dict(value=value, confidence=confidence, raw=json.dumps(answer), cost=cost)


def jev_ask(state, question, api_key, model, url, timeout):
    'Ask *question* about *state* and return the parsed answer.'
    return jev_parse_answer(question, jev_send(jev_build_request(state, question, model), api_key, url, timeout))
