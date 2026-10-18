'Real calls to Jev on the OpenRouter Decisions API: run by hand with `uv run pytest -m live`, never in CI (about 0.00002 USD each).'

import os

import pytest

from vd_jev import jev_ask, jev_build_question

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get('OPENROUTER_API_KEY'), reason='no OPENROUTER_API_KEY'),
]

MODEL = 'typesafe/jev-1.14'
URL = 'https://openrouter.ai/api/alpha/decisions'
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
    assert list(r['probabilities']) == labels and abs(sum(r['probabilities'].values()) - 1) < 0.05


def test_score():
    levels = ['low', 'medium', 'high']
    r = ask(jev_build_question('score', 'How urgent is this request?', levels))
    assert 0 <= r['value'] <= len(levels) - 1
    assert 0 <= r['confidence'] <= 1
    assert list(r['probabilities']) == levels and None not in r['probabilities'].values()


def test_choice_with_descriptions():
    'Descriptions go to the model only: the answer is still one of the short labels.'
    from vd_jev import jev_parse_answers
    kind, labels, descriptions = jev_parse_answers('roads (streets, potholes, street lighting), parks (green areas, playgrounds), noise (anything that disturbs rest)')
    r = jev_ask(TEXT, jev_build_question(kind, 'Which city department should handle this request?', labels, descriptions),
                os.environ['OPENROUTER_API_KEY'], MODEL, URL, timeout=30, labels=labels)
    assert r['value'] in labels
    assert list(r['probabilities']) == labels
