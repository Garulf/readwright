# CLAUDE.md

See `AGENTS.md` for project layout, setup, and commands — it applies here too.

## Claude-specific notes

- `README.md` is a generated file (from `README.md.j2` + `readme.yaml`). If a task
  touches the README, edit the template/config and run `uv run readwright render`;
  never hand-edit `README.md` itself.
- After changing anything under `src/readwright/templates/`, `helpers.py`,
  `badges.py`, `images.py`, `toc.py`, or `changelog.py`, run
  `uv run pytest tests/test_examples.py` — it renders every project under
  `examples/` and is the fastest way to catch a broken helper across real usage.
- Prefer `uv run tox -e lint` over invoking `ruff` directly when you want the same
  check CI runs (`ruff check` + `ruff format --check`, no auto-fix).
- This repo is dogfooding itself: `readwright`'s own `README.md.j2`/`readme.yaml`
  are a real usage example of the tool, not just project docs — check them for
  helper usage patterns before asking "how do I use X helper".
