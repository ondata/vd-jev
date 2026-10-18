# Log

## 2026-10-18

- Phase 3: two commands, `jev-column` and `jev-selected`, one form (`question`, `answers`); the type comes from `answers` (empty = noul, `a, b, c` = choice, `a < b < c` = score), as in MotherDuck `prompt_jev()`. Demo cut to 4 rows. 60 tests pass (`uv run pytest`): unit, in-process commands, `.vdx` replays with golden files.
- OpenRouter Decisions API (`/api/alpha/decisions`) takes the same body as System One and serves 27 decision models (live catalog `?output_modalities=decisions`); real check: Jev 1.14 0.97 / `roads` / 1.98 at ~0.000013 USD, Perplexity Decider Flash 1.2 0.97 / `roads` / 1.54 at ~0.000001 USD.
- Phase 2: plugin is one file, `vd_jev.py` (official plugin docs); stdlib Jev client; five `jev_*` options. Tests: `uv run pytest` (unit tests, loopback HTTP server, `.vdx` replays in batch), `-m live` for real calls, GitHub Actions on Python 3.10-3.14. Live check: noul 0.98, choice `roads` 0.99, score 1.98/2, ~0.000013 USD per call.
- `visidata/dlc` plugin registry and `plugins-sheet` are dead in VisiData 3.4; pip entry point is the current route.
- GitHub repo `aborruso/vd-jev` created private, `main` pushed; to be made public in phase 5.
- No runtime dependencies: `requests` dropped, HTTP will use `urllib.request`. Base VisiData 3.4 does not ship `requests` (only its `[all]` extra does). Checked in a clean venv with only `visidata` and `vd-jev`: plugin loads.
- Phase 1: repo skeleton (`git init`, `.gitignore`, `README.md`, `LOG.md`, `LICENSE` GPL-3.0-only), `pyproject.toml` with `visidata.plugins` entry point `jev = "vd_jev"` and `requests` dependency.
- VisiData reinstalled with all 10 extras plus `--with-editable ~/git/vd-jev`; plugin auto-loads (`visidata.plugins.jev` registered, checked by `.vdj` replay, no warnings).
- PRD and plan written; Jev API verified with a real OpenRouter call (0.000016 USD).
