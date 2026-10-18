import json

import pytest

import vd_jev
from vd_jev import JevError, jev_build_question, jev_build_request, jev_parse_answer, jev_parse_labels, jev_send

NOUL = {'type': 'noul', 'noul': 0.09}
CHOICE = {'type': 'choice', 'choice': 'roads', 'probabilities': {'roads': 0.9, 'parks': 0.1}, 'confidence': 0.8}
SCORE = {'type': 'score', 'score': 1.6, 'probabilities': {'0': 0.1, '1': 0.2, '2': 0.7},
         'legend': {'0': 'low', '1': 'medium', '2': 'high'}, 'confidence': 0.7}


def response(answer, cost=0.000016):
    return {'model': 'typesafe/jev-1.14-20261014', 'answers': {'answer': answer},
            'usage': {'input_tokens': 384, 'output_tokens': 63, 'cost': cost}}


# labels and questions

def test_parse_labels():
    assert jev_parse_labels(' roads, waste ,,parks ') == ['roads', 'waste', 'parks']
    assert jev_parse_labels('') == []
    assert jev_parse_labels(None) == []


def test_noul_question():
    assert jev_build_question('noul', ' Is it a hazard? ') == {'type': 'noul', 'instructions': 'Is it a hazard?'}


def test_choice_question():
    q = jev_build_question('choice', 'Which department?', ['roads', 'parks'])
    assert q['criteria'] == {'roads': None, 'parks': None}


def test_score_question_keeps_order():
    q = jev_build_question('score', 'How urgent?', ['low', 'medium', 'high'])
    assert q['criteria'] == ['low', 'medium', 'high']


@pytest.mark.parametrize('kind, instructions, labels, message', [
    ('maybe', 'q', None, 'unknown question type `maybe`'),
    ('noul', '  ', None, 'no question'),
    ('choice', 'q', ['roads'], 'choice needs at least 2 labels'),
    ('choice', 'q', ['roads', 'roads'], 'labels must be unique'),
    ('choice', 'q', ['roads', ' '], 'empty label'),
    ('score', 'q', [str(i) for i in range(11)], 'score accepts at most 10 levels'),
])
def test_invalid_question(kind, instructions, labels, message):
    with pytest.raises(JevError, match=message):
        jev_build_question(kind, instructions, labels)


def test_build_request():
    q = jev_build_question('noul', 'Is it a hazard?')
    assert jev_build_request('a fallen tree', q, 'typesafe/jev-1.14') == {
        'model': 'typesafe/jev-1.14', 'state': 'a fallen tree', 'questions': {'answer': q}}


# answers

def test_parse_noul():
    q = jev_build_question('noul', 'q')
    assert jev_parse_answer(q, response(NOUL)) == dict(value=0.09, confidence=None, raw=json.dumps(NOUL), cost=0.000016)


def test_parse_choice():
    q = jev_build_question('choice', 'q', ['roads', 'parks'])
    r = jev_parse_answer(q, response(CHOICE))
    assert (r['value'], r['confidence']) == ('roads', 0.8)
    assert json.loads(r['raw'])['probabilities'] == {'roads': 0.9, 'parks': 0.1}


def test_parse_score():
    q = jev_build_question('score', 'q', ['low', 'medium', 'high'])
    r = jev_parse_answer(q, response(SCORE))
    assert (r['value'], r['confidence']) == (1.6, 0.7)


def test_parse_missing_cost():
    q = jev_build_question('noul', 'q')
    assert jev_parse_answer(q, {'answers': {'answer': NOUL}})['cost'] == 0


def test_parse_choice_outside_labels():
    q = jev_build_question('choice', 'q', ['waste', 'parks'])
    with pytest.raises(JevError, match='Jev chose `roads`'):
        jev_parse_answer(q, response(CHOICE))


@pytest.mark.parametrize('resp', [
    {},
    {'answers': {}},
    {'answers': {'answer': {'type': 'noul'}}},
    {'answers': {'answer': {'type': 'noul', 'noul': 'high'}}},
    {'answers': {'answer': NOUL}, 'usage': 'free'},
])
def test_parse_malformed(resp):
    with pytest.raises(JevError, match='malformed noul answer'):
        jev_parse_answer(jev_build_question('noul', 'q'), resp)


# HTTP, against the loopback server

@pytest.fixture
def nosleep(monkeypatch):
    slept = []
    monkeypatch.setattr(vd_jev.time, 'sleep', slept.append)
    return slept


def test_send(fakejev):
    fakejev.reply(response(NOUL))
    body = jev_build_request('text', jev_build_question('noul', 'q'), 'm')
    assert jev_send(body, 'sk-test', fakejev.url, timeout=5) == response(NOUL)
    req, = fakejev.requests
    assert req['path'] == '/api/v1/systemone'
    assert req['headers']['Authorization'] == 'Bearer sk-test'
    assert req['headers']['Content-Type'] == 'application/json'
    assert req['body'] == body


def test_send_non_ascii(fakejev):
    fakejev.reply(response(NOUL))
    jev_send({'state': 'via Roma, città'}, 'k', fakejev.url, timeout=5)
    assert fakejev.requests[0]['body'] == {'state': 'via Roma, città'}


def test_retry_after(fakejev, nosleep):
    fakejev.reply({'error': {'message': 'rate limited'}}, status=429, headers={'Retry-After': '2'})
    fakejev.reply(response(NOUL))
    assert jev_send({}, 'k', fakejev.url, timeout=5) == response(NOUL)
    assert nosleep == [2.0]
    assert len(fakejev.requests) == 2


def test_retry_backoff_without_retry_after(fakejev, nosleep):
    for _ in range(2):
        fakejev.reply(b'', status=429)
    fakejev.reply(response(NOUL))
    jev_send({}, 'k', fakejev.url, timeout=5)
    assert nosleep == [1, 2]


def test_retries_exhausted(fakejev, nosleep):
    for _ in range(4):
        fakejev.reply({'error': {'message': 'rate limited'}}, status=429)
    with pytest.raises(JevError, match='HTTP 429: rate limited'):
        jev_send({}, 'k', fakejev.url, timeout=5, retries=3)
    assert len(fakejev.requests) == 4
    assert nosleep == [1, 2, 4]


def test_http_error_message(fakejev):
    fakejev.reply({'error': {'message': 'No cookie auth credentials found', 'code': 401}}, status=401)
    with pytest.raises(JevError, match='Jev returned HTTP 401: No cookie auth credentials found'):
        jev_send({}, 'bad', fakejev.url, timeout=5)


def test_http_error_without_json_body(fakejev):
    fakejev.reply(b'<html>bad gateway</html>', status=502)
    with pytest.raises(JevError, match='Jev returned HTTP 502: Bad Gateway'):
        jev_send({}, 'k', fakejev.url, timeout=5)


def test_non_json_answer(fakejev):
    fakejev.reply(b'not json')
    with pytest.raises(JevError, match='Jev answer is not JSON'):
        jev_send({}, 'k', fakejev.url, timeout=5)


def test_timeout(fakejev):
    fakejev.reply(response(NOUL), delay=1)
    with pytest.raises(JevError, match='Jev'):
        jev_send({}, 'k', fakejev.url, timeout=0.2)


def test_connection_refused(fakejev):
    url = fakejev.url
    fakejev.close()
    with pytest.raises(JevError, match='cannot reach Jev'):
        jev_send({}, 'k', url, timeout=2)
