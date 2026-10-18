# vd-jev

A [VisiData](https://www.visidata.org/) plugin that asks closed questions about every cell of a text column and writes the answers back as typed columns: a probability (`noul`), a label from a fixed list (`choice`), or a position on an ordered scale (`score`), each with a calibrated confidence. Answers come from Jev, TypeSafe's decision model, by default.

The plugin talks to [OpenRouter](https://openrouter.ai/docs/guides/community/jev) rather than to TypeSafe directly: with one key and one request format it can use any decision model OpenRouter serves (Jev, Perplexity Decider, Microsoft Decision, Cloudflare Clef and others; see the [live catalog](https://openrouter.ai/api/v1/models?output_modalities=decisions)). Jev is the default; to use another model, set `jev_model`:

```python
# ~/.visidatarc
vd.options.jev_model = 'perplexity/pplx-decider-flash-v1.2'
```

or press `Shift+O` inside VisiData, or start it with `vd --jev-model=perplexity/pplx-decider-flash-v1.2`.

It brings to VisiData the idea behind MotherDuck's [`prompt_jev()`](https://motherduck.com/docs/sql-reference/motherduck-sql-reference/ai-functions/prompt-jev/) SQL function.

Status: under development, not usable yet. See [PRD.md](PRD.md) for the requirements and [tasks/todo.md](tasks/todo.md) for the plan.

## Installation (development)

The plugin needs nothing beyond a base VisiData install: it has no runtime dependencies.

```bash
uv tool install visidata --with-editable ~/git/vd-jev
```

If VisiData is already installed as a `uv tool` with extra packages, add `--reinstall` and repeat every `--with` you already use: reinstalling drops any extra that is not passed again.

## Tests

```bash
uv run pytest            # unit tests and .vdx replays, no network
uv run pytest -m live    # one real call per question type; needs OPENROUTER_API_KEY, costs about 0.00004 USD
```

HTTP is tested against a local server that plays scripted answers. `.vdx` replays run in batch with `--config /dev/null`, so your own `.visidatarc` is not involved.

## License

GPL-3.0-only, same as VisiData.
