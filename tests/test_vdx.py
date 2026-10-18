'''Replay every tests/*.vdx in batch, isolated from the user config, against the loopback Jev server,
as VisiData does in tests/test-vdx.sh: the saved sheet must match tests/golden/<name>.tsv,
except for *-nosave.vdx, which only have to run without errors.'''

import os
import pathlib
import subprocess
import sys

import pytest

from conftest import FakeJev, deterministic_answer

TESTS = pathlib.Path(__file__).parent
ROOT = TESTS.parent
VDX = sorted(TESTS.glob('*.vdx'))


@pytest.fixture
def server():
    fake = FakeJev()
    fake.responder = deterministic_answer
    yield fake
    fake.close()


def run_vdx(path, tmp_path, url):
    cmd = [sys.executable, '-m', 'visidata', '--batch', '--config', '/dev/null',
           '--visidata-dir', str(tmp_path / 'vd'), f'--jev-api-url={url}',
           '--play', str(path), '--output', str(tmp_path / 'out.tsv')]
    env = dict(os.environ, OPENROUTER_API_KEY='sk-test')
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=ROOT, env=env)


@pytest.mark.parametrize('path', VDX, ids=[p.stem for p in VDX])
def test_vdx(path, tmp_path, server):
    r = run_vdx(path, tmp_path, server.url)
    assert r.returncode == 0, r.stdout + r.stderr
    if not path.stem.endswith('-nosave'):
        golden = TESTS / 'golden' / f'{path.stem}.tsv'
        assert (tmp_path / 'out.tsv').read_text() == golden.read_text()


def test_failing_assert_fails(tmp_path, server):
    'Guard: a false assert-expr must make the replay fail, or every vdx test above passes vacuously.'
    bad = tmp_path / 'bad.vdx'
    bad.write_text("assert-expr vd.options.jev_model == 'nope'\n")
    r = run_vdx(bad, tmp_path, server.url)
    assert r.returncode != 0
    assert 'not true' in r.stdout + r.stderr
