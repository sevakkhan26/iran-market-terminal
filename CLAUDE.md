# Claude Code / AI session rules

## REQUIRED: sync before work

At the **start of every session** (and again before any non-trivial change), run:

```bash
git fetch origin && git checkout main && git pull --ff-only origin main
```

Do **not** explore, edit, build, or deploy until that succeeds.

If pull fails, stop and report `git status` to the user — do not keep coding on an outdated tree.

Same rule when the user says "continue", "fix", or "resume": pull first.

See `AGENTS.md` for full workflow.
