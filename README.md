# vd-jev

A [VisiData](https://www.visidata.org/) plugin that asks closed questions about every cell of a text column and writes the answers back as typed columns: a probability (`noul`), a label from a fixed list (`choice`), or a position on an ordered scale (`score`), each with a calibrated confidence. Answers come from Jev, TypeSafe's decision model, called through [OpenRouter](https://openrouter.ai/docs/guides/community/jev).

It brings to VisiData the idea behind MotherDuck's [`prompt_jev()`](https://motherduck.com/docs/sql-reference/motherduck-sql-reference/ai-functions/prompt-jev/) SQL function.

Status: under development, not usable yet. See [PRD.md](PRD.md) for the requirements and [tasks/todo.md](tasks/todo.md) for the plan.

## Installation (development)

```bash
uv tool install visidata --with-editable ~/git/vd-jev
```

`uv tool install --reinstall` drops any extra package that is not passed again: repeat every `--with` you already use.

## License

GPL-3.0-only, same as VisiData.
