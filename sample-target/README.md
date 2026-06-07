# TaskFlow API

A small REST service for managing tasks and projects. This repository is the
**sample target** that an AI coding agent operates on while Headroom supervises it.

Reads against these files are **real** — the worker agent genuinely inspects this
code. Write/shell/git/deploy actions are simulated by Headroom (no side effects).

## Layout

- `src/index.ts` — HTTP server entry point and route registration
- `src/auth/middleware.ts` — authentication middleware (sensitive: edits require approval)
- `deploy.sh` — deployment script (deploying to production requires approval)
- `.env` — service secrets (reading this is blocked by the guardian)

## Scripts

- `npm run dev` — start the server with reload
- `npm test` — run the test suite
- `npm run build` — type-check and bundle
