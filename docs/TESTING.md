# TESTING.md

Test, build, lint, and run commands for Headroom.
See also: `docs/VERIFICATION.md` — verification levels and what "verified enough" means.

---

## Install

```bash
pip install -r requirements.txt    # or: uv sync
```

## Test

```bash
pytest                             # unit + integration; uses a fake worker → no API key needed
```

## Eval (guardian quality)

```bash
python -m eval.run_eval            # confusion matrix + recall-on-dangerous + precision (needs ANTHROPIC_API_KEY)
```

## Lint

```bash
ruff check .          # lint (config in ruff.toml)
ruff format .         # auto-format
```

(ruff is a dev dependency — add it at scaffold time / `pip install ruff`; it ships in the dev container.)

## Build

```bash
# No build step (Python; the dashboard is Tailwind via CDN).
```

## Run locally

```bash
uvicorn headroom.api:app --reload    # dashboard → http://localhost:8000
python -m scripts.demo                 # drives the full demo run (curated + scripted fallback)
```

**Expected ready signal:** `Uvicorn running on http://127.0.0.1:8000`.
**Default URL:** http://localhost:8000

## Smoke check (the one command)

```bash
bash scripts/smoke-check.sh
```

Pre-implementation it verifies kit + project scaffolding files exist. Once `pyproject.toml`/`requirements.txt` and the `headroom/` package exist, it also runs `pytest` automatically.

---

## Notes

- Requires `ANTHROPIC_API_KEY` in `.env` for real worker/guardian runs and the eval. Tests do **not** need it (fake worker).
- If a check cannot be run, say so explicitly — never fabricate results.
- Never skip checks to make a commit pass — fix the underlying issue.

---

## Pre-Commit Hooks

Hooks run automatically on every `git commit`.

To run manually against all files:
```bash
# Python / Go:
pre-commit run --all-files

# Node:
npx lint-staged
```

To skip hooks in an emergency (use sparingly):
```bash
git commit --no-verify -m "..."
```
