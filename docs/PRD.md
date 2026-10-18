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
- **Why OpenRouter**: one entry point, one key and one request format for every decision model it serves, not only Jev. Its Decisions API (`POST /api/alpha/decisions`) takes the same body as Jev's own System One API, and on 2026-10-18 its live catalog (`/api/v1/models?output_modalities=decisions`) listed 27 decision models from 15 makers (TypeSafe, Perplexity, Microsoft, OpenAI, Cloudflare, Liquid, Upstage and others). The plugin uses Jev by default; switching to another model is the `jev_model` option, with no code change. Checked with real calls on the same sentence: Jev 1.14 and Perplexity Decider Flash 1.2 both answered all three question types.
- **VisiData 3.4** ships an experimental plugin, `visidata/experimental/llm.py`, that runs a free-form Claude prompt over a column. vd-jev follows its structure and style, so it could later be proposed upstream.

<a id="goals"></a>
## Goals and non-goals

Goals for v1:

- Interesting, easy and usable: someone who has never heard of Jev understands in a few seconds what the plugin does and how to use it. The README opens with a short terminal recording made with [VHS](https://github.com/charmbracelet/vhs) on the demo dataset: one question, the new columns, then a frequency table or a sort by confidence.
- Three question types, `noul`, `choice` and `score`, through two commands (`jev-column`, `jev-selected`) and one prompt: the type comes from what the user writes in `answers`.
- Typed result columns that VisiData can sort, filter, aggregate and use in frequency tables right away.
- Calibrated confidence exposed as a column, so users can filter or select low-confidence rows for manual review.
- Spend awareness: confirmation above a row threshold, and a final summary with rows processed, rows skipped, errors and total cost in USD.
- Installable with `uv` into the environment where VisiData already lives, and loaded automatically.

Non-goals for v1:

- Images, `box`, `multiple_choice`, label descriptions, several questions in one call.
- Several rows per request (see [Open questions](#open-questions)).
- Any other backend than OpenRouter's Decisions API.
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

Two commands, no default key bindings (same choice as `experimental/llm.py`), reachable with `Space` + command name and from the menu `Column > Jev`:

| Command | Rows |
|---|---|
| `jev-column` | all rows |
| `jev-selected` | selected rows |

Both open one prompt with two fields (VisiData allows one `input()` per command, `dev/STYLE.md`, so it is a `vd.inputMultiple` form, as `features/regex.py` does for search and replace):

- `question`: the closed question, required.
- `answers`: optional; it sets the question type, as the named argument does in MotherDuck's `prompt_jev()`:
  - empty: `noul`, a probability that the statement is true;
  - `roads, parks, noise`: `choice`, one label from the list;
  - `low < medium < high`: `score`, a position on the ordered scale, lowest first.

`jev-selected` fails with `no rows selected` when nothing is selected.

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
| `jev_model` | `typesafe/jev-1.14` | decision model id on OpenRouter; any `id` from the live catalog `https://openrouter.ai/api/v1/models?output_modalities=decisions` |
| `jev_api_url` | `https://openrouter.ai/api/alpha/decisions` | OpenRouter Decisions API endpoint |
| `jev_concurrency` | `8` | parallel requests |
| `jev_confirm_rows` | `100` | ask for confirmation above this many rows |
| `jev_timeout` | `30` | seconds per request |

The API key is read from `OPENROUTER_API_KEY`; if missing, the command fails with a message that says where to get one.

<a id="api"></a>
## Jev API

The plugin sends requests to OpenRouter's Decisions API, `POST https://openrouter.ai/api/alpha/decisions`, which serves every decision model in OpenRouter's catalog with one request format. The path is marked `alpha`, so OpenRouter may change it; `jev_api_url` makes that a configuration change. Jev's own System One endpoint on OpenRouter, `POST https://openrouter.ai/api/v1/systemone`, takes the same body but serves only models on TypeSafe's System One contract; it was used for the first check below.

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
  pyproject.toml          # package metadata, entry point, no runtime dependencies
  vd_jev.py               # the plugin: options, Jev client, commands, menu
  tests/
    test_client.py        # pytest on the pure functions: request building, answer parsing, no network
    test_commands.py      # in-process tests of the commands
    test_vdx.py           # runs every *.vdx in batch, compares with golden/
    *.vdx                 # batch replay tests of the commands
    golden/               # expected saved sheets
  demo/
    city_requests.csv     # tiny didactic dataset (see below)
    demo.tape, record.sh  # VHS recording of the README GIF
    demo.gif
  docs/
    PRD.md                # this document
    todo.md               # plan, phases, checks
  README.md
  LOG.md
  LICENSE                 # GPL-3.0-only, same as VisiData
```

The plugin is one file, as `docs/api/plugins.rst` recommends and `experimental/llm.py` does, so it can be pip-installed, copied into the VisiData `plugins/` directory, or proposed upstream. The request building and answer parsing are plain functions, unit-tested with `pytest`; behaviour is tested with `.vdx` replays, as `dev/STYLE.md` asks. The layout mirrors `experimental/llm.py`: `vd.option(...)`, `@Sheet.api` + `@asyncthread` worker, `Progress`, `vd.confirm`, `SettableColumn`, `Sheet.addCommand('', ...)`, `vd.addMenuItems(...)`. HTTP is done with the standard library (`urllib.request`, `json`, `concurrent.futures`), so the plugin runs on a base VisiData install with no extras: base VisiData 3.4 requires only `python-dateutil`, and `requests` comes only with its `[all]` extra. The TypeSafe SDK is not used.

<a id="installation"></a>
## Installation and loading

VisiData 3.4 auto-loads every installed package that registers an entry point in the `visidata.plugins` group (`visidata/settings.py`); this is the distribution route in `docs/plugins.md`. The older `visidata/dlc` registry and `plugins-sheet` are no longer used in 3.4. `pyproject.toml` declares:

```toml
[project.entry-points."visidata.plugins"]
jev = "vd_jev"
```

The plugin needs nothing beyond base VisiData: for end users, `uv tool install visidata --with vd-jev` (or `--with-editable` for a local clone) is enough.

On the development machine VisiData is a `uv tool` with ten extra packages, which are the user's own choice and are not required by the plugin. Reinstalling it drops any extra that is not passed again, and `.visidatarc` imports `humanize` and `fuzzywuzzy`, so the install line must repeat all of them:

```bash
uv tool install visidata --reinstall \
  --with humanize --with pyarrow --with fuzzywuzzy --with python-levenshtein \
  --with duckdb --with sqlite-utils --with openpyxl --with requests \
  --with pyshp --with pyyaml \
  --with-editable ~/git/vd-jev
```

The current list is in `$(uv tool dir)/visidata/uv-receipt.toml`; check it before reinstalling.

<a id="dataset"></a>
## Demo dataset

`demo/city_requests.csv` is deliberately tiny: three columns (`id`, `district`, `message`) and four rows, messages that residents send to a city's service desk, one of them empty. Its job is to show what the plugin is for, not to measure Jev:

- `noul` - "Does the message report a safety hazard?": a fallen tree blocking a road against a request for a bench.
- `choice` - "Which department should handle this?" with `roads, parks, noise`.
- `score` - "How urgent is this?" with `low < medium < high`.
- The empty message shows that empty cells are skipped.

After each question the answers are ordinary VisiData columns: a frequency table on the chosen label, a sort by confidence, a selection of the uncertain rows to read by hand.

Measuring accuracy on real data (ANAC, data.europa.eu) is left for after v1 (see Open questions).

<a id="testing"></a>
## Testing

- **One entry point**: `uv run pytest` runs unit tests and `.vdx` replays; GitHub Actions runs it on Python 3.9 to 3.14.
- **Unit tests** (`pytest`, no network): request body for each question type, label and level validation, parsing of each answer type; `send()` against a loopback `http.server` that plays scripted answers (`429`, errors, timeouts, malformed bodies), the same approach as VisiData's `tests/test-url.sh`.
- **Live smoke test**: one real request per question type on a fixed sentence, marked `live` and skipped by default; run by hand with `uv run pytest -m live`, never in CI, since it costs money.
- **VisiData batch replay**: `.vdx` command logs (format and `assert-expr` / `assert-cell` as in `saulpw/visidata/tests/*.vdx`) run in batch from pytest with `--config /dev/null`, against the loopback server; the saved sheet is compared with a golden file. This is the main integration test.
- **In-process command tests**, as `visidata/tests/test_llm.py` does: status counts, confirmation in the main thread, missing key, empty selection.
- **Golden files**: `.vdx` replays against the loopback server save their sheet, compared with `tests/golden/`.
- **Guided interactive test** with the user, on a step-by-step guide whose every step was checked beforehand (key bindings verified in the VisiData source or by replay).

<a id="privacy"></a>
## Privacy and cost

- Cell text is sent to OpenRouter and then to the provider of the chosen model (TypeSafe for Jev), whose servers are in the United States for Jev. The README must say so plainly: suitable for public data, not for personal or confidential data without an agreement in place.
- Cost is per input token. The verified call (one sentence, two questions) cost 0.000016 USD; about 400 input tokens per row with one question is a reasonable first estimate. The final summary reports the real cost from `usage.cost`.

<a id="milestones"></a>
## Milestones

The detailed checklist, with a verification for every step, is in [`todo.md`](todo.md).

1. Repo skeleton, packaging, install into VisiData's environment.
2. `client.py` with unit tests and a live smoke test.
3. VisiData commands, tested by batch replay.
4. Real calls on the demo dataset, guided interactive test.
5. README with the VHS recording, and publication on GitHub as `ondata/vd-jev` (moved from `aborruso/vd-jev` on 2026-10-18).

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
