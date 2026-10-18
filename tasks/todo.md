# vd-jev plan

A VisiData plugin that brings the ideas of MotherDuck's `prompt_jev()` into VisiData: closed questions over a text column, with typed answers and calibrated probabilities, using TypeSafe's Jev model through OpenRouter.

## Decisions (2026-10-18)

- Engine: Jev via OpenRouter, `POST https://openrouter.ai/api/v1/systemone`, key in `OPENROUTER_API_KEY`. Checked with a real call: an Italian tender description returned `choice` = `lavori` (p=1), `noul` urgency = 0.09, cost 0.000016 USD.
- Repo: `~/git/vd-jev`, public on GitHub as `aborruso/vd-jev`, created only after this plan is approved.
- Language: everything in the repo is in English, this plan included: code, comments, README, LOG, commit messages.
- v1 scope: `noul`, `choice` and `score` questions on text, over the whole column or the selected rows only. Out of scope: `box`, images, `multiple_choice`.
- Style reference: `visidata/experimental/llm.py` from VisiData 3.4.

## Phase 1 - Repo skeleton

- [ ] `git init`, `.gitignore` (`tmp/`), `README.md`, `LOG.md`, `LICENSE` (GPL-3.0-only, same as VisiData) → check: clean `git status` after the first commit
- [ ] `pyproject.toml` with entry point `[project.entry-points."visidata.plugins"] jev = "vd_jev"` and a `requests` dependency → check: `uv build` produces a wheel without errors
- [ ] Install into VisiData's environment with `uv tool install visidata --reinstall --with-editable ~/git/vd-jev` plus all 10 current extras (`humanize pyarrow fuzzywuzzy python-levenshtein duckdb sqlite-utils openpyxl requests pyshp pyyaml`) → check: `uv tool list --show-with` lists all 11, and `vd` starts without a `plugin jev failed to load` warning

## Phase 2 - Jev client

- [ ] Function that builds the request (`state` = cell text, one question) and sends it; handles `429` with `retry-after`, timeouts, readable HTTP errors → check: `pytest` on request building (no network) and one real call per question type
- [ ] VisiData options: `jev_model` (default `typesafe/jev-1.14`), `jev_api_url`, `jev_concurrency`, `jev_confirm_rows` (row count above which it asks for confirmation) → check: they appear in `Shift+O`

## Phase 3 - VisiData commands

Test file for this phase: `demo/city_requests.csv` (see PRD, Demo dataset). For volume tests only (confirmation threshold, concurrency, cancellation), a larger file generated with `fauxdata` in `tmp/`: its text is random, so it never measures accuracy.

- [ ] Write `demo/city_requests.csv` (~40 rows, English, a few empty messages) and `demo/expected.csv` (hazard, department, urgency per id); user reviews both → check: user approves; `duckdb` join on `id` matches every row
- [ ] Generate `tmp/volume.csv` (1,000 rows) with `fauxdata generate --validate` → check: validation passes

- [ ] `jev-noul-column` / `jev-noul-selected`: asks for the question, adds a `<col>_noul` column (float) → check: batch `.vdj` replay on the test file, column present, values between 0 and 1
- [ ] `jev-choice-column` / `-selected`: asks for the question and comma-separated labels; adds `<col>_choice` (str), `<col>_confidence` (float), `<col>_jev_raw` (JSON, hidden) → check: batch replay, every `choice` is one of the given labels
- [ ] `jev-score-column` / `-selected`: asks for the question and levels from lowest to highest; adds `<col>_score` (float), `<col>_confidence` → check: batch replay, `score` between 0 and n-1
- [ ] Empty cells skipped, confirmation above the row threshold, `Progress` bar, final summary with rows, errors and cost (`usage.cost`) → check: replay on a file with empty cells; summary counts are correct
- [ ] Menu entries under Column > Jev → check: visible in the menu

## Phase 4 - Field test

- [ ] Run `jev-noul`, `jev-choice`, `jev-score` on `demo/city_requests.csv` and compare with `demo/expected.csv` → check: accuracy per question type and low-confidence rows recorded in `LOG.md`
- [ ] Guided interactive test with the user, step by step, on a guide whose every step was verified beforehand

## Phase 5 - Publication

- [ ] Create `aborruso/vd-jev` on GitHub and push → check: repo visible, README renders
- [ ] README with `uv tool` install, examples, indicative costs, and a note that cell text is sent to OpenRouter/TypeSafe (USA)

## After v1 (not in this plan)

- Several rows per request (`state.rows[i]` pattern, one question per row, at most ~20 rows): measure against v1 on accuracy and speed before adopting it
- `multiple_choice`, label descriptions, several questions in one call
- Other decision models on OpenRouter (same API, only `model` changes)
- Possible PR to VisiData under `experimental/`
- Real-data evaluation: Italian ANAC records or an English dataset from data.europa.eu

## Open questions

- See PRD, Open questions: batching several rows per request, real-data evaluation after v1 (ANAC or data.europa.eu), pinned model vs `latest` alias, PyPI package name.
