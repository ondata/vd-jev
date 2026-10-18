'Replay every tests/*.vdx in batch, isolated from the user config, as VisiData does in tests/test-vdx.sh.'

import pathlib
import subprocess
import sys

import pytest

TESTS = pathlib.Path(__file__).parent
VDX = sorted(TESTS.glob('*.vdx'))


def run_vdx(path, tmp_path, *args):
    cmd = [sys.executable, '-m', 'visidata', '--batch', '--config', '/dev/null',
           '--visidata-dir', str(tmp_path / 'vd'), '--play', str(path),
           '--output', str(tmp_path / 'out.tsv'), *args]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=60)


@pytest.mark.parametrize('path', VDX, ids=[p.stem for p in VDX])
def test_vdx(path, tmp_path):
    r = run_vdx(path, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr


def test_failing_assert_fails(tmp_path):
    'Guard: a false assert-expr must make the replay fail, or every vdx test above passes vacuously.'
    bad = tmp_path / 'bad.vdx'
    bad.write_text("assert-expr vd.options.jev_model == 'nope'\n")
    r = run_vdx(bad, tmp_path)
    assert r.returncode != 0
    assert 'not true' in r.stdout + r.stderr
