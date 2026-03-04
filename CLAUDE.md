# VN News Bot

Vietnamese Telegram bot for news aggregation, weather, and disaster alerts.

## Architecture

```
src/vn_news_bot/
  adapters/       # External integrations (RSS, NewsAPI, OpenWeather, Telegram)
  domain/         # Domain models (Pydantic)
  handlers/       # Telegram command handlers
  services/       # Business logic (news, weather, disaster, scoring, scheduler)
  config.py       # YAML + env config loading
  main.py         # App entrypoint, command registration, job scheduling
config/           # YAML configs (feeds, cities, scoring, schedule, disaster)
tests/unit/       # Unit tests mirroring src structure
tests/integration/
```

## Stack

- Python 3.13, python-telegram-bot, feedparser, httpx, pydantic-settings, loguru
- Package manager: `uv` (never pip)
- Linting: `ruff` (line-length 100)
- Type checking: `mypy --strict`
- Testing: `pytest` with `pytest-asyncio`

## Commands

```bash
uv run ruff check src/ tests/          # Lint
uv run ruff format --check src/ tests/  # Format check
uv run mypy src/                        # Type check
uv run pytest tests/ -v --no-cov        # Run all tests
uv run pytest tests/unit/test_X.py -v --no-cov -q  # Single test file
```

## Conventions

- All functions require type hints (`from __future__ import annotations`)
- Vietnamese commands use unaccented lowercase (e.g., `/thethao`, `/chungkhoan`)
- Config loaded from YAML via `config.py` accessors (cached with `functools.cache`)
- Telegram formatting uses HTML parse mode
- Domain models in `domain/models.py` (Pydantic)
- Each service is a focused module: news, weather, disaster, scoring, scheduler

## Team Roles

### Coder (`feature-dev:feature-dev`)

Implements features and fixes bugs. Responsibilities:

- Write code following existing patterns and conventions
- Add type hints to all function signatures
- Keep functions under 30 lines, prefer early returns
- Write unit tests for new code in `tests/unit/`
- Run `ruff check`, `ruff format`, and `mypy` before considering work done
- Follow DDD: adapters for external I/O, services for business logic, handlers for Telegram glue
- New commands: add handler in `commands.py`, register in `main.py`, add to bot menu
- New config: add YAML file in `config/`, add loader in `config.py`

### Architect (`feature-dev:code-architect`)

Designs features and makes structural decisions. Responsibilities:

- Analyze existing patterns before proposing changes
- Design data flow: adapter -> service -> handler -> telegram formatter
- Evaluate trade-offs (new dependency vs custom code, config vs hardcode)
- Ensure new features fit the existing module boundaries
- Plan multi-file changes with clear file-by-file scope
- Consider backward compatibility for existing bot subscribers
- Review YAML config schema changes for consistency
- Output: implementation blueprint with specific files to create/modify

### Quality Reviewer (`feature-dev:code-reviewer`)

Reviews code for correctness and quality. Responsibilities:

- Check for bugs, logic errors, and edge cases
- Verify type safety (mypy strict compliance)
- Ensure no security issues (input validation, no secrets in code)
- Validate error handling for external API calls (RSS, weather, Telegram)
- Check test coverage for new functionality
- Verify Vietnamese text handling (encoding, accent normalization)
- Confirm async patterns are correct (no blocking calls in async handlers)
- Flag over-engineering or unnecessary complexity

## Workflow

When working on a feature or fix, follow this order:

1. **Architect** plans the approach and identifies files to change
2. **Coder** implements the plan
3. **Quality Reviewer** reviews the implementation
4. Iterate if reviewer finds issues

For small fixes (typos, config tweaks), skip straight to Coder.
