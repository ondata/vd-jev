# Log

## 2026-10-18

- Demo GIF slowed down (90 ms typing, pauses after question, answers, command name and results) and re-encoded with ffmpeg via `demo/record.sh`: XnView refused VHS's 1x1-delta GIF.
- README actually rewritten (the previous commit `5b9f93e` claimed it but the write had failed): requirements (OpenRouter account, credit, `OPENROUTER_API_KEY`), install, usage, model choice, cost, privacy, options. Run now stops at the first HTTP 401 (bad key, checked live: `User not found`) or 402 (no credit, per OpenRouter docs, tested on the fake only) with a hint; 403 is not a stop code, OpenRouter uses it for moderation of a single input.
- Cursor now stays on the source column after `jev-column` (test first, failed, then fixed). Demo extended to 10 rows. VHS recording `demo/demo.gif` from `demo/demo.tape`. README rewritten with GIF, usage, costs (Jev ~0.000012 USD/row, Perplexity Decider Flash ~0.000001), privacy, options.
- Guided manual test with the user passed (noul, choice, frequency table, score, selection of the uncertain row). UX finding: cursor moves to the new column, so the next question was asked on `message_choice` by mistake.
- Phase 4, real calls on the demo (Jev 1.14, Decisions API): hazard 0.97 / 0.04 / 0.16; department `roads` 0.98 / `parks` 1.00 / `noise` 1.00; urgency 1.96 (conf 0.94) / 0.11 (0.85) / 0.91 (0.19) for tree / bench / bar; empty row skipped. The bar's urgency is the uncertain case to show.
- Guide for the manual test verified as `tests/guide-nosave.vdx`; `go-col-regex` searches forward and `select-expr` lets empty cells pass `< x`.
- Default endpoint switched to OpenRouter Decisions API (`/api/alpha/decisions`), Jev 1.14 default model, any decision model via `jev_model`; messages name OpenRouter and the model, not Jev. `uv run pytest -m live` passes on the new endpoint. Demo approved.
- Phase 3: two commands, `jev-column` and `jev-selected`, one form (`question`, `answers`); the type comes from `answers` (empty = noul, `a, b, c` = choice, `a < b < c` = score), as in MotherDuck `prompt_jev()`. Demo cut to 4 rows. 60 tests pass (`uv run pytest`): unit, in-process commands, `.vdx` replays with golden files.
- OpenRouter Decisions API (`/api/alpha/decisions`) takes the same body as System One and serves 27 decision models (live catalog `?output_modalities=decisions`); real check: Jev 1.14 0.97 / `roads` / 1.98 at ~0.000013 USD, Perplexity Decider Flash 1.2 0.97 / `roads` / 1.54 at ~0.000001 USD.
- Phase 2: plugin is one file, `vd_jev.py` (official plugin docs); stdlib Jev client; five `jev_*` options. Tests: `uv run pytest` (unit tests, loopback HTTP server, `.vdx` replays in batch), `-m live` for real calls, GitHub Actions on Python 3.10-3.14. Live check: noul 0.98, choice `roads` 0.99, score 1.98/2, ~0.000013 USD per call.
- `visidata/dlc` plugin registry and `plugins-sheet` are dead in VisiData 3.4; pip entry point is the current route.
- GitHub repo `aborruso/vd-jev` created private, `main` pushed; to be made public in phase 5.
- No runtime dependencies: `requests` dropped, HTTP will use `urllib.request`. Base VisiData 3.4 does not ship `requests` (only its `[all]` extra does). Checked in a clean venv with only `visidata` and `vd-jev`: plugin loads.
- Phase 1: repo skeleton (`git init`, `.gitignore`, `README.md`, `LOG.md`, `LICENSE` GPL-3.0-only), `pyproject.toml` with `visidata.plugins` entry point `jev = "vd_jev"` and `requests` dependency.
- VisiData reinstalled with all 10 extras plus `--with-editable ~/git/vd-jev`; plugin auto-loads (`visidata.plugins.jev` registered, checked by `.vdj` replay, no warnings).
- PRD and plan written; Jev API verified with a real OpenRouter call (0.000016 USD).
