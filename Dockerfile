FROM ghcr.io/astral-sh/uv:0.12.4 AS uv

FROM python:3.13.7-slim-bookworm

COPY --from=uv /uv /uvx /bin/

RUN groupadd --gid 10001 glupta \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin glupta

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev --no-editable \
    && mkdir /artifacts \
    && chown glupta:glupta /artifacts

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER glupta

CMD ["glupta-agi"]
