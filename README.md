# vd-jev

[VisiData](https://www.visidata.org/) is a terminal tool for exploring and arranging tabular data. It opens CSV, TSV, JSON, SQLite, Excel, Parquet and many other formats, and a few keystrokes are enough to sort, filter, aggregate, pivot, plot and save them. It is a wonderful tool for anyone who has to explore, look at and summarize structured data.

vd-jev is a VisiData plugin that asks closed questions about every cell of a text column and writes the answers back as typed columns: a probability (yes/no), a label from a fixed list, or a position on an ordered scale, each with a calibrated confidence. Answers come from Jev, TypeSafe's decision model, by default, or from any other decision model on [OpenRouter](https://openrouter.ai/docs/guides/community/jev).

It brings to VisiData the idea behind MotherDuck's [`prompt_jev()`](https://motherduck.com/docs/sql-reference/motherduck-sql-reference/ai-functions/prompt-jev/) SQL function.

![vd-jev demo: three questions on ten citizen requests, a frequency table, and the uncertain rows selected](demo/demo.gif)

## Contents

- [Why a decision model](#why)
- [Requirements](#requirements)
- [Installation](#installation)
- [What it does](#what-it-does)
- [Choosing a model](#choosing-a-model)
- [Cost](#cost)
- [Privacy](#privacy)
- [Options](#options)
- [Tests](#tests)
- [License](#license)

<a id="why"></a>
## Why a decision model

If you love VisiData but have not used AI models much with it, this is the simplest place to start.

The AI models most people know are chat models: you write a prompt, they write text back. Text is hard to put in a table: it has to be read, parsed, checked. Decision models such as Jev work the other way round: you ask a closed question and they never answer with text, only with a quick, typed classification.

Start from a table with a column of free text, like `demo/city_requests.csv`:

| id | district | message |
|---|---|---|
| 1 | North | A tree has fallen across Elm Street after the storm and blocks both lanes. |
| 2 | Central | Please add a bench near the duck pond in Riverside Park. |
| 3 | East | The bar on Market Square plays loud music until 3am every night. |
| 4 | West | |
| 7 | Central | Road works on King Street start at 5am and wake the whole block. |

Ask three questions about the `message` column, one `jev-column` each:

| Question | Answers | Kind of answer |
|---|---|---|
| Does the message report a safety hazard? | *(empty)* | yes/no: the probability of yes, 0 to 1 |
| Which department should handle this? | `roads, parks, noise` | one of your labels, with a confidence |
| How urgent is this request? | `low < medium < high` | a place on your scale, 0 (low) to 2 (high), with a confidence |

and the same table comes back with typed columns next to the text:

| id | message | message_noul | message_choice | message_choice_conf | message_score | message_score_conf |
|---|---|---|---|---|---|---|
| 1 | A tree has fallen across Elm Street after the storm and blocks both lanes. | 0.97 | roads | 0.98 | 1.96 | 0.93 |
| 2 | Please add a bench near the duck pond in Riverside Park. | 0.03 | parks | 1.00 | 0.10 | 0.86 |
| 3 | The bar on Market Square plays loud music until 3am every night. | 0.16 | noise | 1.00 | 0.98 | 0.13 |
| 4 | | | | | | |
| 7 | Road works on King Street start at 5am and wake the whole block. | 0.18 | roads | 0.79 | 0.74 | 0.00 |

These are real answers from Jev 1.14 on the demo file (2026-10-18). The empty message is skipped. Row 7 shows the confidence at work: road works that wake people up sit between `roads` and `noise`, and the model says so (0.79); on urgency it has no idea (0.00).

In VisiData this changes what you can do with a column of free text. Once the answers are columns, everything you already know applies: `Shift+F` counts the requests per department, `[` and `]` sort by urgency, `z|` selects the hazards, or the rows where the model is unsure (low confidence), so you read by hand only those. Tickets to route, survey answers to code, complaints to triage, descriptions to tag: a few cents for thousands of rows (see [Cost](#cost)), instead of reading them all.

<a id="requirements"></a>
## Requirements

- VisiData 3.4 (Python 3.10 or later). No other package is needed.
- An [OpenRouter](https://openrouter.ai/) account with some credit: every row is a paid request (see [Cost](#cost)).
- An OpenRouter API key, created at <https://openrouter.ai/keys>, in the `OPENROUTER_API_KEY` environment variable of the shell that starts VisiData:

  ```bash
  export OPENROUTER_API_KEY=sk-or-...
  ```

  To keep it across sessions, add that line to your shell startup file (`~/.bashrc`, `~/.zshrc`). The key is read only from the environment, never from VisiData options.

The plugin checks these before sending anything. Without the key, the command stops with `set $OPENROUTER_API_KEY` and adds no columns. With a key that OpenRouter refuses (invalid, revoked, or without credit), the run stops at the first refusal and reports the reason given by OpenRouter.

<a id="installation"></a>
## Installation

The plugin is a single file with no dependencies beyond VisiData itself, and VisiData loads it automatically.

```bash
uv tool install visidata --with git+https://github.com/aborruso/vd-jev
```

or, from a local clone:

```bash
uv tool install visidata --with-editable ~/git/vd-jev
```

If VisiData is already installed as a `uv tool` with extra packages, add `--reinstall` and repeat every `--with` you already use: reinstalling drops any extra that is not passed again.

<a id="what-it-does"></a>
## What it does

Put the cursor on a column of text, press `Space`, type `jev-column` (or `jev-selected` for the selected rows only), and fill in the form: `Tab` moves between the two fields, `Enter` sends.

| `question` | `answers` | New columns |
|---|---|---|
| Does the message report a safety hazard? | *(empty)* | `message_noul`: probability of yes, 0 to 1 |
| Which department should handle this? | `roads, parks, noise` | `message_choice`: one of the labels; `message_choice_conf` |
| How urgent is this request? | `low < medium < high` | `message_score`: 0 (low) to 2 (high); `message_score_conf` |

What you write in `answers` sets the kind of question: nothing for yes/no, labels separated by commas to pick one, levels separated by `<` (lowest first) for an ordered scale. Empty cells are skipped. The cursor stays on the text column, so you can ask the next question right away; a status message reports rows answered, skipped, errors and cost. Each run also adds a hidden `_raw` column with the full answer as JSON (per-label probabilities included), or the error for that row.

The new columns are ordinary VisiData columns. In the demo above:

- `Shift+F` on `message_choice` counts the requests per department;
- `z|` with `0 < message_score_conf < 0.5` selects the rows where the model is unsure, to read them by hand (the `0 <` leaves out the empty row).

Try it on the demo file:

```bash
vd demo/city_requests.csv
```

<a id="choosing-a-model"></a>
## Choosing a model

The plugin talks to OpenRouter rather than to TypeSafe directly: with one key and one request format it can use any decision model OpenRouter serves through its Decisions API (Jev, Perplexity Decider, Microsoft Decision, Cloudflare Clef and others; see the [live catalog](https://openrouter.ai/api/v1/models?output_modalities=decisions)). Jev 1.14 is the default; to use another model, set `jev_model`:

```python
# ~/.visidatarc
vd.options.jev_model = 'perplexity/pplx-decider-flash-v1.2'
```

or press `Shift+O` inside VisiData, or start it with `vd --jev-model=perplexity/pplx-decider-flash-v1.2` (with `=`: with a space VisiData reads the value as a file to open).

Probabilities and confidences are not comparable across models: a threshold that works with one model has to be checked again with another.

<a id="cost"></a>
## Cost

Each row is one request, billed by OpenRouter on input tokens. Measured on the demo file (short messages, one question), on 2026-10-18:

| Model | Per row | 1,000 rows |
|---|---|---|
| `typesafe/jev-1.14` (default) | about 0.000012 USD | about 0.012 USD |
| `perplexity/pplx-decider-flash-v1.2` | about 0.000001 USD | about 0.001 USD |

Longer texts and more labels cost more, in proportion to the tokens sent; the status message at the end of each run reports the real cost. Above 100 non-empty rows (`jev_confirm_rows`) the plugin asks for confirmation before sending anything. Prices are in the [catalog](https://openrouter.ai/api/v1/models?output_modalities=decisions) and may change.

<a id="privacy"></a>
## Privacy

The text of each cell is sent to OpenRouter and to the provider of the chosen model (TypeSafe, in the United States, for Jev). Use it on public data; not on personal or confidential data without an agreement in place.

<a id="options"></a>
## Options

| Option | Default | Meaning |
|---|---|---|
| `jev_model` | `typesafe/jev-1.14` | decision model id on OpenRouter |
| `jev_api_url` | `https://openrouter.ai/api/alpha/decisions` | OpenRouter Decisions API endpoint |
| `jev_concurrency` | `8` | parallel requests |
| `jev_confirm_rows` | `100` | ask for confirmation above this many rows |
| `jev_timeout` | `30` | seconds per request |

<a id="tests"></a>
## Tests

```bash
uv run pytest            # unit tests, command tests and .vdx replays, no network
uv run pytest -m live    # one real call per question type; needs OPENROUTER_API_KEY, costs about 0.00004 USD
```

HTTP is tested against a local server that plays scripted answers. `.vdx` replays run in batch with `--config /dev/null`, so your own `.visidatarc` is not involved. The demo recording is made with [VHS](https://github.com/charmbracelet/vhs) and ffmpeg: `demo/record.sh` (real calls, about 0.0004 USD).

<a id="license"></a>
## License

GPL-3.0-only, same as VisiData.
