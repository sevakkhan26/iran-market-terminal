# Claude Code / AI session rules

**Primary instructions:** [`docs/AGENT_PLAYBOOK.md`](docs/AGENT_PLAYBOOK.md)

1. Read `docs/AGENT_PLAYBOOK.md` at session start.
2. `git pull --ff-only origin main` before any edit/build/deploy.
3. Stack = Docker Compose (`db` + `terminal`), Postgres only, migrations on boot.
4. Bump `APP_VERSION` on every user-facing change.
5. If Docker cannot reach PyPI/npm: `./scripts/prepare-offline-build.sh` then rebuild.
6. Verify with `curl http://127.0.0.1:4000/api/health` and Admin diagnostics.

Same rules when the user says "continue", "fix", or "resume": **pull first**.
