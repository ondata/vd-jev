'Real calls to Jev on OpenRouter: run by hand with `uv run pytest -m live`, never in CI (about 0.00002 USD each).'

import os

import pytest

from vd_jev import jev_ask, jev_build_question

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get('OPENROUTER_API_KEY'), reason='no OPENROUTER_API_KEY'),
]

MODEL = 'typesafe/jev-1.14'
URL = 'https://openrouter.ai/api/v1/systemone'
TEXT = 'A large tree has fallen across Elm Street after the storm and is blocking both lanes.'


def ask(question):
    return jev_ask(TEXT, question, os.environ['OPENROUTER_API_KEY'], MODEL, URL, timeout=30)


def test_noul():
    r = ask(jev_build_question('noul', 'The message reports a safety hazard'))
    assert 0 <= r['value'] <= 1
    assert r['confidence'] is None
    assert r['cost'] > 0


def test_choice():
    labels = ['roads', 'waste', 'parks', 'noise', 'lighting']
    r = ask(jev_build_question('choice', 'Which city department should handle this request?', labels))
    assert r['value'] in labels
    assert 0 <= r['confidence'] <= 1


def test_score():
    levels = ['low', 'medium', 'high']
    r = ask(jev_build_question('score', 'How urgent is this request?', levels))
    assert 0 <= r['value'] <= len(levels) - 1
    assert 0 <= r['confidence'] <= 1
