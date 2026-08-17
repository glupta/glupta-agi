FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS build

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.13-slim-bookworm

RUN groupadd --gid 10001 glupta \
    && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent glupta
WORKDIR /app
COPY --from=build --chown=10001:10001 /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1
USER 10001:10001
CMD ["glupta-agi"]
