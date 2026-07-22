# GitHub Copilot instructions

Primary setup/ops guide for this multi-agent repo:

→ **docs/AGENT_PLAYBOOK.md**

Always:
1. `git pull --ff-only origin main` before edits
2. Use Docker Compose (`db` + `terminal`); Postgres only
3. Migrations: Alembic, auto on container start
4. Offline build helper: `scripts/prepare-offline-build.sh`
5. Bump `APP_VERSION` on product changes

Do not reintroduce SQLite or file-based runtime settings.
