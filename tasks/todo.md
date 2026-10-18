# vd-jev plan

A VisiData plugin that brings the ideas of MotherDuck's `prompt_jev()` into VisiData: closed questions over a text column, with typed answers and calibrated probabilities, using TypeSafe's Jev model through OpenRouter.

## Decisions (2026-10-18)

- Endpoint (changed 2026-10-18 with the user): OpenRouter Decisions API, `POST https://openrouter.ai/api/alpha/decisions`, model `typesafe/jev-1.14` by default, any decision model from the live catalog via `jev_model`; reason: one entry point for every decision model on OpenRouter. Same body as System One; real calls with Jev 1.14 and Perplexity Decider Flash 1.2 answered all three types. Path is `alpha`. First engine check was on System One, `POST https://openrouter.ai/api/v1/systemone`, key in `OPENROUTER_API_KEY`. Checked with a real call: an Italian tender description returned `choice` = `lavori` (p=1), `noul` urgency = 0.09, cost 0.000016 USD.
- Repo: `~/git/vd-jev`, on GitHub as `aborruso/vd-jev`. Changed 2026-10-18 at the user's request: created private at the end of phase 1, made public in phase 5 once the plugin works.
- Language: everything in the repo is in English, this plan included: code, comments, README, LOG, commit messages.
- v1 scope: `noul`, `choice` and `score` questions on text, over the whole column or the selected rows only, through two commands; the type comes from the `answers` field. Out of scope: `box`, images, `multiple_choice`.
- Style reference: `visidata/experimental/llm.py` from VisiData 3.4, plus the official plugin docs: `docs/api/plugins.rst`, `docs/plugins.md`, `dev/STYLE.md`, `dev/TESTING.md` in `saulpw/visidata`, and the `visidata/visidata-plugin` template (copies in `tmp/vd-docs/`).
- Distribution and layout (2026-10-18, from the official docs): a pip package with a `visidata.plugins` entry point, the route `docs/plugins.md` describes. The `visidata/dlc` registry and `plugins-sheet` are dead in 3.4 (`plugins_url` commented out in `visidata/deprecated.py`, `dlc` last commit 2022-03-12). The plugin is a single file, `vd_jev.py` (docstring, `__author__`, `__version__`, options at the top, commands at the bottom), as `docs/api/plugins.rst` and `experimental/llm.py` do: the same file can be pip-installed, copied into the VisiData `plugins/` directory, or proposed upstream under `experimental/`.
- Dependencies (2026-10-18, changed): the plugin must run on a base VisiData install (`uv tool install visidata`, no extras) and add only what it strictly needs. Base VisiData 3.4 requires only `python-dateutil` (plus `standard-mailcap` on Python >= 3.13 and `windows-curses` on Windows); `requests` comes only with the `[all]` extra. HTTP is therefore done with the standard library (`urllib.request`, `json`, `concurrent.futures`): no runtime dependencies. The user's own extras stay on their machine but are never assumed by the plugin.

- Testing (2026-10-18, modelled on `saulpw/visidata` `dev/TESTING.md`, `tests/test-url.sh`, `visidata/tests/test_llm.py`): one entry point, `uv run pytest`. Unit tests for the pure functions; `send()` tested against a loopback `http.server` on an ephemeral port that plays scripted answers (never the network in tests, as TESTING.md requires); `.vdx` replays run in batch from pytest with `--config /dev/null --visidata-dir <tmp>`, isolated from the user's config; real calls behind a `live` marker, skipped unless `-m live`; GitHub Actions with `astral-sh/setup-uv`, Python 3.10 to 3.14.

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

- [x] Turn the `vd_jev/` package into a single module `vd_jev.py`; add `__author__`; add `[dependency-groups] dev = ["pytest", "visidata"]` → check: `uv build` puts `vd_jev.py` at the wheel root (tested in `tmp/single`: works with no hatch config), replay in `tmp/base-venv` shows `visidata.plugins.jev` loaded
  - Done 2026-10-18, commit `4fb7224`. Wheel holds `vd_jev.py` at the root; plugin loads in `tmp/base-venv` and in the user's `uv tool` install (the editable `.pth` points at the project root, so no reinstall was needed).
- [x] Pure functions in `vd_jev.py` that build the request (`state` = cell text, one question), send it with `urllib.request` (no `requests`), handle `429` with `retry-after`, timeouts, readable HTTP errors, and parse the answer; messages follow the 11 rules in `dev/STYLE.md` → check: `uv run pytest` on request building and parsing, and on `send()` against the loopback server (200, 429 with and without `retry-after`, 401 with OpenRouter error body, non-JSON body, timeout, connection refused); `uv run pytest -m live`: one real call per question type
  - Done 2026-10-18. `uv run pytest`: 30 tests in `tests/test_client.py` pass (loopback server in `tests/conftest.py`). `uv run pytest -m live`: 3 passed. Real answers for the fallen-tree sentence: noul 0.98; choice `roads` (confidence 0.99); score 1.98 of 2 (confidence 0.98); about 0.000013 USD per call. Confirms `null` label descriptions for choice and an array of levels for score are accepted.
- [x] VisiData options: `jev_model` (default `typesafe/jev-1.14`), `jev_api_url`, `jev_concurrency`, `jev_confirm_rows` (row count above which it asks for confirmation), `jev_timeout` → check: they appear in `Shift+O` (checked by `tests/options-nosave.vdx`, `assert-expr` on `vd.options`, run from pytest; a deliberately failing assertion makes the run fail)
  - Done 2026-10-18. `tests/test_vdx.py` replays every `tests/*.vdx` with `--batch --config /dev/null --visidata-dir <tmp>`; `options-nosave.vdx` checks the five defaults and their presence on the `options-global` (Shift+O) sheet; `test_failing_assert_fails` guards against vacuous passes.
- [x] GitHub Actions workflow: `uv run pytest` on Python 3.10 to 3.14 → check: workflow green on the push
  - Done 2026-10-18, `.github/workflows/test.yml` (`actions/checkout@v7`, `astral-sh/setup-uv@v10.3.0`, `uv run --locked pytest`); run 39118684186 on `d190e37` green on 3.10, 3.11, 3.12, 3.13, 3.14.

## Phase 3 - VisiData commands

Decided with the user on 2026-10-18: the question type comes from what the user types, as in MotherDuck's `prompt_jev()`, so two commands instead of six; the demo is a handful of rows that shows what the plugin is for, not an accuracy benchmark; no large volume file (the confirmation threshold is tested on a synthetic sheet in pytest). The 40-row draft and `tmp/volume.csv` are dropped.

- [x] Write `demo/city_requests.csv`: 3 columns (`id`, `district`, `message`), 4 rows, one with an empty message → check: user approves it
  - Written 2026-10-18 (fallen tree, bench request, loud bar, empty); approved by the user on 2026-10-18.
- [x] `jev_parse_answers()`: empty → `noul`; `a, b, c` → `choice`; `low < medium < high` → `score` → check: unit tests for each form and for invalid input
  - Done 2026-10-18, `test_parse_answers*` in `tests/test_client.py`.
- [x] `jev-column` / `jev-selected`: one `vd.inputMultiple` prompt with `question` and `answers` (STYLE.md: one `input()` per command; pattern from `features/regex.py`), through an `inputJev()` helper kept in the execstr; question built, key read and confirmation asked in the main thread, requests in an `@asyncthread` with a thread pool of `jev_concurrency`; adds `<col>_noul` (float), or `<col>_choice` (str) + `<col>_choice_conf` (float), or `<col>_score` (float) + `<col>_score_conf` (float), plus a hidden `<col>_<type>_raw` → check: `.vdx` replays on `demo/city_requests.csv` against the loopback server, output compared with golden files in `tests/golden/` (as VisiData does); `choice` is one of the labels, `score` between 0 and n-1, `noul` between 0 and 1
  - Done 2026-10-18. `tests/demo-{noul,choice,score,selected}.vdx` replayed by `tests/test_vdx.py` against the loopback server (`--jev-api-url=URL`: the option needs `=`, with a space VisiData opens the URL as a file), output equal to `tests/golden/*.tsv`; the hidden raw column is not saved; the empty message stays empty; `jev-selected` answers only the selected row.
- [x] Empty cells skipped, confirmation above `jev_confirm_rows`, `Progress`, final status with rows answered, skipped, errors and cost (`usage.cost`), per-row errors kept in the raw column, cancellation with Ctrl+C stops pending requests → check: in-process pytest (as `visidata/tests/test_llm.py`): counts in the status, confirm called once in the main thread above the threshold, missing key fails before any column is added, `jev-selected` with no selection fails
  - Done 2026-10-18, `tests/test_commands.py` (14 tests, incl. cancellation: with 10 slow requests and concurrency 1, `vd.cancelThread` stops the run before all are sent; the partial summary is posted, then VisiData's `jevRun aborted`). In batch the final status is not printed to stdout, so the summary is checked in-process only.
- [x] Menu entries under Column > Jev → check: pytest on `vd.menus` (TESTING.md: Python-level assertions with no output go in pytest, not `.vdx`; changed 2026-10-18)
  - Done 2026-10-18, `test_menu` and `test_execstr_compiles` in `tests/test_commands.py`.

## Phase 4 - Field test

- [x] Run the three kinds of question on `demo/city_requests.csv` with real calls → check: answers and cost recorded in `LOG.md`
  - Done 2026-10-18, `tests/demo-{noul,choice,score}.vdx` in batch on the Decisions API with Jev 1.14, see LOG. Cost not printed in batch; 9 calls at ~0.000013 USD each (from the live tests), ~0.00012 USD.
- [x] Guided interactive test with the user in their shell, step by step, on a guide whose every step was verified beforehand
  - Guide steps verified 2026-10-18: keys in the VisiData 3.4 source (`Space` exec-longname, `c` go-col-regex, `Tab` next form field, `F` freq-col, `q` quit-sheet, `l` go-right, `[` sort-asc, `z|` select-expr, `gq` quit-all) and the whole sequence as `tests/guide-nosave.vdx`. Found while checking: the cursor moves to the new column after `jev-column`; `go-col-regex` searches forward, so the guide uses `^message$`; in `select-expr` an empty cell passes `< 0.5`, so the guide uses `0 < message_score_conf < 0.5`.
  - Done 2026-10-18 with the user, Windows Terminal, screenshots. All three types worked on real calls (~0.000012-0.000013 USD per row); status summary shown in the `statuses` box; the bar row was the only one selected (urgency 0.91, confidence 0.17). Found: the user asked the urgency question while the cursor was still on `message_choice`, because the plugin moves the cursor to the new column; proposal: keep the cursor on the source column.

## Phase 5 - Publication

- [x] Create `aborruso/vd-jev` on GitHub (private) and push → check: `gh repo view` shows it private, `main` pushed
  - Done 2026-10-18, see LOG.
- [x] VHS recording (`demo/demo.tape` -> `demo/demo.gif`, VHS v0.11.0 installed in `~/go/bin`, ttyd and ffmpeg present): `vd demo/city_requests.csv`, `jev-column` with one question, the new columns, then `Shift+F` on the choice column or a sort by confidence; real calls on 3 rows (~0.00004 USD per take); every key in the tape checked in the VisiData source or by replay first → check: `vhs demo/demo.tape` produces the GIF; user reviews it
  - Recorded 2026-10-18 on the 10-row demo (extended with the user's agreement): 27 s, 1.4 MB; frames checked: noul summary 9 answered / 1 skipped / 0.000109 USD, form with both fields, frequency table roads 4 / parks 4 / noise 1, 5 uncertain rows selected. The narrow `~` column after the last visible one is VisiData 3.4 drawing hidden columns (`calcColLayout` lays out `availCols`, hidden ones 1 char wide), not a plugin bug. Waiting for the user's review.
- [ ] Make `aborruso/vd-jev` public, after explicit user confirmation → check: repo visible logged out, README renders
- [x] README with `uv tool` install, examples, indicative costs, how to choose another model with `jev_model`, and a note that cell text is sent to OpenRouter and the model provider (TypeSafe, USA, for Jev)
  - Done 2026-10-18: GIF at the top, usage table, install from git (checked with `git+file://` in `tmp/gitvenv`: plugin loads), model choice, measured costs, privacy, options, tests.

## After v1 (not in this plan)

- Several rows per request (`state.rows[i]` pattern, one question per row, at most ~20 rows): measure against v1 on accuracy and speed before adopting it
- `multiple_choice`, label descriptions, several questions in one call
- Model picker: a sheet of the live decision-model catalog, where Enter sets `jev_model`
- Possible PR to VisiData under `experimental/`
- Real-data evaluation: Italian ANAC records or an English dataset from data.europa.eu

## Open questions

- See PRD, Open questions: batching several rows per request, real-data evaluation after v1 (ANAC or data.europa.eu), pinned model vs `latest` alias, PyPI package name.
