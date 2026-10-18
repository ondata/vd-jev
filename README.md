# vd-jev

A [VisiData](https://www.visidata.org/) plugin that asks closed questions about every cell of a text column and writes the answers back as typed columns: a probability (`noul`), a label from a fixed list (`choice`), or a position on an ordered scale (`score`), each with a calibrated confidence. Answers come from Jev, TypeSafe's decision model, called through [OpenRouter](https://openrouter.ai/docs/guides/community/jev).

It brings to VisiData the idea behind MotherDuck's [`prompt_jev()`](https://motherduck.com/docs/sql-reference/motherduck-sql-reference/ai-functions/prompt-jev/) SQL function.

Status: under development, not usable yet. See [PRD.md](PRD.md) for the requirements and [tasks/todo.md](tasks/todo.md) for the plan.

## Installation (development)

The plugin needs nothing beyond a base VisiData install: it has no runtime dependencies.

```bash
uv tool install visidata --with-editable ~/git/vd-jev
```

If VisiData is already installed as a `uv tool` with extra packages, add `--reinstall` and repeat every `--with` you already use: reinstalling drops any extra that is not passed again.

## License

GPL-3.0-only, same as VisiData.
