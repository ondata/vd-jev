# vd-jev - Product Requirements Document

## Contents

- [Summary](#summary)
- [Background](#background)
- [Goals and non-goals](#goals)
- [Users and use cases](#users)
- [Functional requirements](#functional)
- [Jev API](#api)
- [Architecture](#architecture)
- [Installation and loading](#installation)
- [Demo dataset](#dataset)
- [Testing](#testing)
- [Privacy and cost](#privacy)
- [Milestones](#milestones)
- [Open questions](#open-questions)
- [References](#references)

<a id="summary"></a>
## Summary

vd-jev is a VisiData plugin that asks closed questions about every cell of a text column and writes the answers back as typed columns. It brings to VisiData the idea behind MotherDuck's `prompt_jev()` SQL function: instead of generated prose, each row gets a decision (a probability, a label from a fixed list, or a position on an ordered scale) with calibrated probabilities. The answers come from Jev, TypeSafe's decision model, called through OpenRouter.

<a id="background"></a>
## Background

- **Jev** is a "System One" model by TypeSafe. It takes a `state` (text) and a set of typed questions and returns typed answers with probabilities. It never returns free text. Question types: `noul` (is this statement true? returns a probability), `choice` (which label from a list? returns the label, per-label probabilities and a confidence), `score` (which level on an ordered rubric? returns a weighted position, per-level probabilities and a confidence). Newer types (`box` for images, `multiple_choice`) exist but are out of scope for v1.
- **MotherDuck** exposes Jev as `prompt_jev(input, instructions, choice := [...])` since 2026-09-21. Images, `box` and `multiple_choice` were added on 2026-10-16.
- **OpenRouter** serves Jev to anyone with an OpenRouter API key, with no TypeSafe account. Billing is per input token; output tokens are free.
- **VisiData 3.4** ships an experimental plugin, `visidata/experimental/llm.py`, that runs a free-form Claude prompt over a column. vd-jev follows its structure and style, so it could later be proposed upstream.

<a id="goals"></a>
## Goals and non-goals

Goals for v1:

- Three commands, `noul`, `choice` and `score`, each runnable over the whole current column or over the selected rows only.
- Typed result columns that VisiData can sort, filter, aggregate and use in frequency tables right away.
- Calibrated confidence exposed as a column, so users can filter or select low-confidence rows for manual review.
- Spend awareness: confirmation above a row threshold, and a final summary with rows processed, rows skipped, errors and total cost in USD.
- Installable with `uv` into the environment where VisiData already lives, and loaded automatically.

Non-goals for v1:

- Images, `box`, `multiple_choice`, label descriptions, several questions in one call.
- Several rows per request (see [Open questions](#open-questions)).
- Any other backend than OpenRouter's System One endpoint.
- Caching of answers across sessions.

<a id="users"></a>
## Users and use cases

The target user works with tabular data in the terminal and has columns of short free text to sort out: support tickets, citizen requests, tender descriptions, survey answers, reviews. Typical questions:

- `noul`: "Does this message report a safety hazard?"
- `choice`: "Which department should handle this request?" with `roads, waste, parks, noise, lighting`
- `score`: "How urgent is this request?" with `low, medium, high`

After running a command, the user sorts by confidence, opens a frequency table on the chosen label, or selects rows below a confidence threshold to read them by hand.

<a id="functional"></a>
## Functional requirements

### Commands

Six commands, no default key bindings (same choice as `experimental/llm.py`), reachable with `Space` + command name and from the menu `Column > Jev`.

| Command | Rows | Prompts |
|---|---|---|
| `jev-noul-column` / `jev-noul-selected` | all / selected | question |
| `jev-choice-column` / `jev-choice-selected` | all / selected | question, then labels separated by commas |
| `jev-score-column` / `jev-score-selected` | all / selected | question, then levels from lowest to highest, separated by commas |

The `*-selected` variants fail with a clear message when no rows are selected.

Validation before any request:

- `choice`: at least 2 unique, non-empty labels.
- `score`: between 2 and 10 unique, non-empty levels.
- The question must not be empty.

### Result columns

Added to the right of the source column. `<col>` is the source column name.

| Command | Columns | Type |
|---|---|---|
| noul | `<col>_noul` | float, 0 to 1 |
| choice | `<col>_choice`, `<col>_choice_conf` | str (one of the labels), float |
| score | `<col>_score`, `<col>_score_conf` | float, 0 to n-1, float |

Each command also adds a hidden `<col>_<type>_raw` column with the JSON answer for that row, so per-label probabilities are available without a new request.

### Behaviour

- Empty and null cells are skipped and left empty in the result columns.
- If the number of non-empty rows exceeds `jev_confirm_rows`, ask for confirmation before sending anything.
- Requests run in a background thread (`@asyncthread`) with a `Progress` indicator, so the interface stays responsive and the run can be cancelled with `Ctrl+C`.
- A per-row error (HTTP error, malformed answer) is caught, the row is left empty, the error is counted, and the run continues.
- Final status line: rows answered, rows skipped, errors, total cost from `usage.cost`.

### Options

| Option | Default | Meaning |
|---|---|---|
| `jev_model` | `typesafe/jev-1.14` | model id on OpenRouter |
| `jev_api_url` | `https://openrouter.ai/api/v1/systemone` | endpoint |
| `jev_concurrency` | `8` | parallel requests |
| `jev_confirm_rows` | `100` | ask for confirmation above this many rows |
| `jev_timeout` | `30` | seconds per request |

The API key is read from `OPENROUTER_API_KEY`; if missing, the command fails with a message that says where to get one.

<a id="api"></a>
## Jev API

Verified on 2026-10-18 with a real call (cost 0.000016 USD):

```bash
curl -sS https://openrouter.ai/api/v1/systemone \
  -H "Authorization: Bearer $OPENROUTER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "typesafe/jev-1.14",
    "state": "Lavori di manutenzione straordinaria del manto stradale di via Roma",
    "questions": {
      "categoria": {"type": "choice", "instructions": "Che tipo di appalto pubblico descrive il testo?",
        "criteria": {"lavori": "Opere edili, stradali, impiantistiche", "servizi": "Prestazioni di servizi", "forniture": "Acquisto di beni"}},
      "urgente": {"type": "noul", "instructions": "Il testo indica una situazione di urgenza"}
    }
  }'
```

Response:

```json
{
  "model": "typesafe/jev-1.14-20261014",
  "answers": {
    "categoria": {"type": "choice", "choice": "lavori",
      "probabilities": {"lavori": 1, "servizi": 0, "forniture": 0}, "confidence": 1},
    "urgente": {"type": "noul", "noul": 0.09}
  },
  "usage": {"input_tokens": 384, "output_tokens": 63, "cost": 0.000016128},
  "id": "gen-dec-...",
  "provider": "TypeSafe"
}
```

Request rules from the TypeSafe and OpenRouter docs:

- `choice.criteria`: an object mapping label to description (`null` allowed when there is no description).
- `score.criteria`: an ordered array, lowest level first. The answer has `score` (weighted position), `probabilities` keyed `"0"`, `"1"`, ..., a `legend` mapping those keys back to the levels, and `confidence`.
- `noul`: no criteria needed; the answer is `{"type": "noul", "noul": <probability>}`.
- Rate limits return `429`, possibly with `retry-after`.
- English is Jev's primary language; other languages are "handled but not equally well".

<a id="architecture"></a>
## Architecture

```
vd-jev/
  pyproject.toml          # package metadata, entry point, dependency on requests
  vd_jev/
    __init__.py           # imports the modules below
    client.py             # build request, send it, retry on 429, parse answer; no VisiData imports
    commands.py           # VisiData options, commands, menu, columns
  tests/
    test_client.py        # request building and answer parsing, no network
  demo/
    city_requests.csv     # didactic dataset (see below)
    expected.csv          # correct answers for the dataset
  README.md
  LOG.md
  PRD.md
  LICENSE                 # GPL-3.0-only, same as VisiData
  tasks/todo.md
```

`client.py` has no dependency on VisiData, so it can be tested with plain `pytest` and reused. `commands.py` mirrors `experimental/llm.py`: `vd.option(...)`, `@Sheet.api` + `@asyncthread` worker, `Progress`, `vd.confirm`, `SettableColumn`, `Sheet.addCommand('', ...)`, `vd.addMenuItems(...)`. HTTP is done with `requests`, already present in the VisiData environment; the TypeSafe SDK is not used.

<a id="installation"></a>
## Installation and loading

VisiData 3.4 auto-loads every installed package that registers an entry point in the `visidata.plugins` group (`visidata/settings.py`). `pyproject.toml` declares:

```toml
[project.entry-points."visidata.plugins"]
jev = "vd_jev"
```

On the development machine VisiData is a `uv tool` with ten extra packages. Reinstalling it drops any extra that is not passed again, and `.visidatarc` imports `humanize` and `fuzzywuzzy`, so the install line must repeat all of them:

```bash
uv tool install visidata --reinstall \
  --with humanize --with pyarrow --with fuzzywuzzy --with python-levenshtein \
  --with duckdb --with sqlite-utils --with openpyxl --with requests \
  --with pyshp --with pyyaml \
  --with-editable ~/git/vd-jev
```

The current list is in `$(uv tool dir)/visidata/uv-receipt.toml`; check it before reinstalling. For end users the README documents the short form: `uv tool install visidata --with vd-jev` (once published) or `--with-editable` for a local clone.

<a id="dataset"></a>
## Demo dataset

A hand-built English CSV, `demo/city_requests.csv`, designed to teach the three question types with examples anyone can follow. It doubles as a small accuracy check, because every row has a known answer in `demo/expected.csv`.

Theme: messages that residents send to a city's service desk. About 40 rows, columns `id`, `district`, `submitted` (date), `message`.

The messages are written so that each command has something clear to show:

- `noul` - "Does the message report a safety hazard?": clear yes (exposed wires, a fallen tree on the road), clear no (a request for a new bench), and a few borderline cases.
- `choice` - "Which department should handle this?" with `roads, waste, parks, noise, lighting`: several clear messages per department, plus a few that touch two departments (a broken streetlight in a park) to show lower confidence.
- `score` - "How urgent is this request?" with `low, medium, high`: a spread across the scale.
- A few empty messages, to show that empty cells are skipped.

`demo/expected.csv` holds, for each `id`, the expected `hazard` (true/false), `department` and `urgency`. A comparison (with `duckdb` or a VisiData join) gives accuracy per question type. Being written by the same person who sets the labels, this set is easier than real data; it shows how the plugin works, not how well Jev performs on real text.

For volume tests (confirmation threshold, concurrency, progress, cancellation) a larger file is generated with `fauxdata` from a YAML schema in `tmp/`. Its text is random, so it is used only to check behaviour, never accuracy.

<a id="testing"></a>
## Testing

- **Unit tests** (`pytest`, no network): request body for each question type, label and level validation, parsing of each answer type, handling of `429` and of malformed answers (with a mocked HTTP layer).
- **Live smoke test**: one real request per question type on a fixed sentence; run by hand, not in CI, since it costs money.
- **VisiData batch replay**: `.vdj` command logs run with `vd -b -p test.vdj demo/city_requests.csv -o out.csv`, then checked with `duckdb`: result columns present, typed, values in range, empty cells skipped. This is the main integration test.
- **Accuracy check**: compare the output of each command on `demo/city_requests.csv` with `demo/expected.csv`; record results in `LOG.md`.
- **Guided interactive test** with the user, on a step-by-step guide whose every step was checked beforehand (key bindings verified in the VisiData source or by replay).

<a id="privacy"></a>
## Privacy and cost

- Cell text is sent to OpenRouter and then to TypeSafe, whose servers are in the United States. The README must say so plainly: suitable for public data, not for personal or confidential data without an agreement in place.
- Cost is per input token. The verified call (one sentence, two questions) cost 0.000016 USD; about 400 input tokens per row with one question is a reasonable first estimate. The final summary reports the real cost from `usage.cost`.

<a id="milestones"></a>
## Milestones

The detailed checklist, with a verification for every step, is in [`tasks/todo.md`](tasks/todo.md).

1. Repo skeleton, packaging, install into VisiData's environment.
2. `client.py` with unit tests and a live smoke test.
3. VisiData commands, tested by batch replay.
4. Demo dataset, accuracy check, guided interactive test.
5. README and publication on GitHub as `aborruso/vd-jev`.

<a id="open-questions"></a>
## Open questions

- Several rows per request: a third-party PostgreSQL extension for Jev packs about 20 rows into one `state` (`{"rows": [...]}`, one question per row referencing `rows[i]`) and reports accuracy dropping above 20-25 rows; MotherDuck batches 32 rows by default. Not part of v1; measure against one-row-per-request first.
- Real-data evaluation after v1: Italian ANAC tender records, or an English dataset from the European open data portal (data.europa.eu), to measure accuracy outside the hand-built set.
- Should `jev_model` default to the pinned `typesafe/jev-1.14` (stable thresholds) or to the `~typesafe/jev-latest` alias (always newest)? Current choice: pinned.
- Package name on PyPI, if published there: `vd-jev`, or `visidata-jev`?

<a id="references"></a>
## References

- MotherDuck `prompt_jev`: https://motherduck.com/docs/sql-reference/motherduck-sql-reference/ai-functions/prompt-jev/
- MotherDuck release notes: https://motherduck.com/docs/about-motherduck/release-notes/
- Jev on OpenRouter: https://openrouter.ai/docs/guides/community/jev
- TypeSafe quick start: https://docs.typesafe.ai/introduction/quickstart
- TypeSafe models: https://docs.typesafe.ai/models
- OpenRouter Decisions API reference: https://github.com/OpenRouterTeam/skills/blob/main/skills/openrouter-decisions/references/decisions-api.md
- VisiData experimental LLM plugin: `visidata/experimental/llm.py` in VisiData 3.4
