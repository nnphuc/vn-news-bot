FROM python:3.13-slim AS base

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

FROM base AS deps

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM base

RUN groupadd --gid 1000 app && useradd --uid 1000 --gid app --no-create-home app

COPY --from=deps /app/.venv /app/.venv
COPY config/ config/
COPY src/ src/
COPY pyproject.toml uv.lock README.md ./

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER app

CMD ["vn-news-bot"]
