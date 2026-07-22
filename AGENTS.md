# Agent / AI instructions (MANDATORY)

This repository is actively developed by multiple people and AIs.
**Stale checkouts cause wasted work and broken deploys.**

## Before ANY work — always do this first

1. Confirm you are in the project root of `iran-market-terminal`.
2. **Sync with GitHub before reading or editing anything:**

```bash
git fetch origin
git checkout main
git pull --ff-only origin main
```

3. If `git pull --ff-only` fails (local commits / dirty tree):
   - Show `git status` and `git log --oneline -5` to the user.
   - Do **not** invent a parallel fix on top of an old base.
   - Prefer: stash or commit local work, then `git pull --rebase origin main` (only with user approval if history rewrite is involved).

4. Only **after** a successful pull may you:
   - read the codebase
   - change files
   - run builds / tests
   - deploy

## If the user says "continue" or "fix X"

Still run `git pull --ff-only origin main` first. Do not assume your previous session is up to date.

## After you finish a change

```bash
git status
git pull --ff-only origin main   # again, in case something landed while you worked
# then commit + push as the user requested
```

## Project notes (short)

- Backend: FastAPI in `backend/` (collector + API + static UI).
- Frontend: React/Vite in `frontend/` (build into `frontend/dist`).
- Server deploy: Docker via parent `docker-compose` / `Dockerfile` — collector must stay enabled (`RUN_COLLECTOR=1`).
- Do not reintroduce unbounded concurrent exchange fetches (see `MAX_INFLIGHT` in `backend/app/connectors.py`).

## Rule of thumb

**No pull → no code.** Always start from latest `origin/main`.
