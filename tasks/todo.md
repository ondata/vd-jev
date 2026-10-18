# vd-jev plan

A VisiData plugin that brings the ideas of MotherDuck's `prompt_jev()` into VisiData: closed questions over a text column, with typed answers and calibrated probabilities, using TypeSafe's Jev model through OpenRouter.

## Decisions (2026-10-18)

- Engine: Jev via OpenRouter, `POST https://openrouter.ai/api/v1/systemone`, key in `OPENROUTER_API_KEY`. Checked with a real call: an Italian tender description returned `choice` = `lavori` (p=1), `noul` urgency = 0.09, cost 0.000016 USD.
- Repo: `~/git/vd-jev`, on GitHub as `aborruso/vd-jev`. Changed 2026-10-18 at the user's request: created private at the end of phase 1, made public in phase 5 once the plugin works.
- Language: everything in the repo is in English, this plan included: code, comments, README, LOG, commit messages.
- v1 scope: `noul`, `choice` and `score` questions on text, over the whole column or the selected rows only. Out of scope: `box`, images, `multiple_choice`.
- Style reference: `visidata/experimental/llm.py` from VisiData 3.4, plus the official plugin docs: `docs/api/plugins.rst`, `docs/plugins.md`, `dev/STYLE.md`, `dev/TESTING.md` in `saulpw/visidata`, and the `visidata/visidata-plugin` template (copies in `tmp/vd-docs/`).
- Distribution and layout (2026-10-18, from the official docs): a pip package with a `visidata.plugins` entry point, the route `docs/plugins.md` describes. The `visidata/dlc` registry and `plugins-sheet` are dead in 3.4 (`plugins_url` commented out in `visidata/deprecated.py`, `dlc` last commit 2022-03-12). The plugin is a single file, `vd_jev.py` (docstring, `__author__`, `__version__`, options at the top, commands at the bottom), as `docs/api/plugins.rst` and `experimental/llm.py` do: the same file can be pip-installed, copied into the VisiData `plugins/` directory, or proposed upstream under `experimental/`.
- Dependencies (2026-10-18, changed): the plugin must run on a base VisiData install (`uv tool install visidata`, no extras) and add only what it strictly needs. Base VisiData 3.4 requires only `python-dateutil` (plus `standard-mailcap` on Python >= 3.13 and `windows-curses` on Windows); `requests` comes only with the `[all]` extra. HTTP is therefore done with the standard library (`urllib.request`, `json`, `concurrent.futures`): no runtime dependencies. The user's own extras stay on their machine but are never assumed by the plugin.

## Phase 1 - Repo skeleton

- [x] `git init`, `.gitignore` (`tmp/`), `README.md`, `LOG.md`, `LICENSE` (GPL-3.0-only, same as VisiData) → check: clean `git status` after the first commit
  - Done 2026-10-18, commit `Repo skeleton`; `git status --short` empty. `.gitignore` also covers `__pycache__/`, `*.egg-info/`, `dist/`, `.venv/`. `LICENSE` is the FSF text from `/usr/share/common-licenses/GPL-3` (VisiData's copy differs only in `http` vs `https` URLs).
- [x] `pyproject.toml` with entry point `[project.entry-points."visidata.plugins"] jev = "vd_jev"` and a `requests` dependency → check: `uv build` produces a wheel without errors
  - Superseded on 2026-10-18 by the next step: the `requests` dependency is dropped.
  - Done 2026-10-18, hatchling backend, SPDX `license = "GPL-3.0-only"`. `uv build -o tmp/dist` builds sdist and wheel; wheel `entry_points.txt` holds `[visidata.plugins] jev = vd_jev`.
- [x] Drop `requests` from `pyproject.toml` (`dependencies = []`), fix README → check: in a clean venv `tmp/base-venv` with `uv pip install visidata ./`, `uv pip list` shows only VisiData's own dependencies plus `vd-jev`, and the `.vdj` replay shows `visidata.plugins.jev` loaded
  - Done 2026-10-18. `uv pip list` in `tmp/base-venv`: `python-dateutil`, `six` (needed by `python-dateutil`), `standard-mailcap`, `visidata` 3.4, `vd-jev` 0.1.0; `import requests` fails there. `tmp/base-venv/bin/vd -b --config /dev/null -p tmp/check_plugin.vdj` exits 0 and shows `visidata.plugins.jev` = `vd_jev` (`--config /dev/null` skips the user's `~/.visidatarc`, which imports extras missing from that venv).
- [x] Install into VisiData's environment with `uv tool install visidata --reinstall --with-editable ~/git/vd-jev` plus all 10 current extras (`humanize pyarrow fuzzywuzzy python-levenshtein duckdb sqlite-utils openpyxl requests pyshp pyyaml`) → check: `uv tool list --show-with` lists all 11, and `vd` starts without a `plugin jev failed to load` warning
  - Done 2026-10-18. Extras checked first in `uv-receipt.toml` (same 10). `uv tool list --show-with` shows the 10 extras plus `vd-jev` (editable). `vd -b tmp/x.csv -o tmp/out.csv` exits 0 with no output; replay `tmp/check_plugin.vdj` (`exec-python`) shows `sys.modules['visidata.plugins.jev']` = `vd_jev` from `~/git/vd-jev/vd_jev/__init__.py`.

## Phase 2 - Jev client

- [ ] Turn the `vd_jev/` package into a single module `vd_jev.py`; add `__author__`; add `[dependency-groups] dev = ["pytest", "visidata"]` → check: `uv build` puts `vd_jev.py` at the wheel root (tested in `tmp/single`: works with no hatch config), replay in `tmp/base-venv` shows `visidata.plugins.jev` loaded
- [ ] Pure functions in `vd_jev.py` that build the request (`state` = cell text, one question), send it with `urllib.request` (no `requests`), handle `429` with `retry-after`, timeouts, readable HTTP errors, and parse the answer; messages follow the 11 rules in `dev/STYLE.md` → check: `uv run pytest` on request building and parsing (no network, mocked HTTP) and one real call per question type
- [ ] VisiData options: `jev_model` (default `typesafe/jev-1.14`), `jev_api_url`, `jev_concurrency`, `jev_confirm_rows` (row count above which it asks for confirmation), `jev_timeout` → check: they appear in `Shift+O` (checked by `.vdx` replay with `assert-expr` on `vd.options`)

## Phase 3 - VisiData commands

Test file for this phase: `demo/city_requests.csv` (see PRD, Demo dataset). For volume tests only (confirmation threshold, concurrency, cancellation), a larger file generated with `fauxdata` in `tmp/`: its text is random, so it never measures accuracy.

- [ ] Write `demo/city_requests.csv` (~40 rows, English, a few empty messages) and `demo/expected.csv` (hazard, department, urgency per id); user reviews both → check: user approves; `duckdb` join on `id` matches every row
- [ ] Generate `tmp/volume.csv` (1,000 rows) with `fauxdata generate --validate` → check: validation passes

- [ ] `jev-noul-column` / `jev-noul-selected`: asks for the question, adds a `<col>_noul` column (float) → check: batch `.vdx` replay on the test file, column present, values between 0 and 1
- [ ] `jev-choice-column` / `-selected`: asks for the question and comma-separated labels in one `vd.inputMultiple` prompt (STYLE.md: one `input()` per command; pattern from `features/regex.py`), wrapped in an `inputJev...()` helper kept in the execstr; adds `<col>_choice` (str), `<col>_confidence` (float), `<col>_jev_raw` (JSON, hidden) → check: batch replay, every `choice` is one of the given labels
- [ ] `jev-score-column` / `-selected`: asks for the question and levels from lowest to highest in one `vd.inputMultiple` prompt; adds `<col>_score` (float), `<col>_confidence` → check: batch replay, `score` between 0 and n-1
- [ ] Empty cells skipped, confirmation above the row threshold, `Progress` bar, final summary with rows, errors and cost (`usage.cost`) → check: replay on a file with empty cells; summary counts are correct
- [ ] Menu entries under Column > Jev → check: visible in the menu

## Phase 4 - Field test

- [ ] Run `jev-noul`, `jev-choice`, `jev-score` on `demo/city_requests.csv` and compare with `demo/expected.csv` → check: accuracy per question type and low-confidence rows recorded in `LOG.md`
- [ ] Guided interactive test with the user, step by step, on a guide whose every step was verified beforehand

## Phase 5 - Publication

- [x] Create `aborruso/vd-jev` on GitHub (private) and push → check: `gh repo view` shows it private, `main` pushed
  - Done 2026-10-18, see LOG.
- [ ] Make `aborruso/vd-jev` public, after explicit user confirmation → check: repo visible logged out, README renders
- [ ] README with `uv tool` install, examples, indicative costs, and a note that cell text is sent to OpenRouter/TypeSafe (USA)

## After v1 (not in this plan)

- Several rows per request (`state.rows[i]` pattern, one question per row, at most ~20 rows): measure against v1 on accuracy and speed before adopting it
- `multiple_choice`, label descriptions, several questions in one call
- Other decision models on OpenRouter (same API, only `model` changes)
- Possible PR to VisiData under `experimental/`
- Real-data evaluation: Italian ANAC records or an English dataset from data.europa.eu

## Open questions

- See PRD, Open questions: batching several rows per request, real-data evaluation after v1 (ANAC or data.europa.eu), pinned model vs `latest` alias, PyPI package name.
