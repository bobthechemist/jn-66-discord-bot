# Coding Instructions — jn-66

Purpose: concise, actionable best-practices for contributors to the jn-66 Discord task bot.

## 1) Tech stack (quick)
- Python 3.10+
- discord.py (bot)
- Ollama (local LLM) via `ollama` client
- Pydantic for validation
- parsedatetime for natural date parsing
- Flask (docker sandbox) for code execution
- Google Calendar API (google-auth / googleapiclient)
- SQLite (sqlite3) for local storage
- Docker for sandbox service
- Dev dependencies: Pillow, requests, pytest (recommended)

## 2) Repo & runtime layout
- jn-66.py — main bot bootstrap
- /cogs — discord cogs (llm_cog.py, calendar_cog.py, utils_cog.py, admin_cog.py)
- /utils — helpers (ui, scheduler, db, agent, discord helpers)
- /docker — sandbox app and Dockerfile
- bot_config.json.template, .env for secrets (never commit real secrets)

## 3) Code style & linting
- Use black for formatting and isort for imports. Example:
  - black . --fast
  - isort .
- Type hints encouraged (mypy-compatible). Keep function/variable annotations where helpful.
- Keep functions small and single-responsibility.

## 4) Async best practices
- Use asyncio and discord.py's coroutines consistently.
- Avoid blocking calls on the event loop:
  - Wrap blocking IO (requests, heavy CPU) in asyncio.to_thread or use an async client (aiohttp).
- Prefer discord.py helpers (commands.Cog, tasks.loop) for scheduled work.
- Use timeouts on network calls (requests timeout or aiohttp ClientTimeout).

## 5) LLM & sandbox safety
- Never send secrets (tokens, credentials) to an LLM.
- Ollama calls should use low temperature for deterministic extraction (already used).
- Sandbox:
  - The sandbox runs untrusted code—keep it isolated in Docker, non-root user, no host mounts.
  - Validate and size-limit code and results; close matplotlib figures after each run.
  - Limit request payload size and timeouts (e.g., 30s).
  - Log sandbox errors but avoid leaking internal stack traces to users.

## 6) Validation & security
- Use Pydantic for structured user inputs and LLM outputs (already used).
- Sanitize DB input and avoid SQL string concatenation (DatabaseManager uses parameterized queries; keep that pattern).
- Keep secrets in .env and local gtoken/gcredentials in .gitignore. Confirm bot_config.json.template has no secrets.
- Use least-privilege for Google OAuth credentials and rotate keys as needed.

## 7) Database & migrations
- SQLite is used: keep schema changes explicit in DatabaseManager.create_tables.
- Backups: export DB files periodically; provide export/import commands for migration (CSV/JSON).
- Soft-delete pattern recommended for recovery (e.g., status + deleted_at).

## 8) Logging & error handling
- Use structured logging (module-based loggers). Keep sensitive data out of logs.
- Log exceptions with exc_info=True when diagnosing, but return user-friendly messages in DMs.
- Use RotatingFileHandler (already configured) and respect log_location from config.

## 9) Testing
- Add pytest tests for:
  - utils (time parsing, scheduler logic)
  - database manager operations (create/read/update/delete)
  - task_agent parsing with representative prompts and edge cases
- Mock external services (Ollama, Google Calendar, sandbox) in unit tests.

## 10) Docker & deployment
- Build the sandbox using the Dockerfile under /docker. Keep the sandbox minimal and isolated.
- Avoid copying secrets into images.
- Use docker-compose or systemd unit (jn-66.service provided) for production on a single host.
- For the bot: run under a dedicated service user, restart on failure, and limit file permissions.

## 11) Dependency management
- Keep requirements.txt updated. Pin versions for production.
- Use a virtualenv during development. Do not commit venv/.

## 12) Pull requests & commits
- Small, incremental PRs with a single focused change.
- Commit messages: Describe why, not just what.
- Add tests for new logic; run linters and black before merging.

## 13) Performance & scalability notes
- For larger servers, add sharding and per-guild storage (avoid a single global DB if multi-user support is added).
- Cache expensive API calls where possible.
- Respect rate limits for Discord and third-party APIs.

## 14) Contributor checklist (before PR)
- Run black and isort
- Run unit tests (pytest)
- Confirm no secrets in diffs
- Add/update documentation (README or this file) if behavior changed
- Include a short PR description and rollout plan for anything touching integrations or DB schema

Appendix: quick commands
- Format & sort: `black . && isort .`
- Run tests: `pytest -q`
- Start sandbox locally: `docker build -t llm-sandbox ./docker && docker run -p 5000:5000 llm-sandbox`
- Start bot: `source venv/bin/activate && python jn-66.py`

Keep this file focused and evolve it with the project.
