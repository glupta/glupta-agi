FROM ghcr.io/astral-sh/uv:0.12.4@sha256:d0a6eca6c669dc7e9c51218707b8438a3d30402733d739dcc00adb3e213e8f5c AS uv

FROM debian:bookworm-slim@sha256:abd67ffcfa541b485a3dff59865ab629aa048a6c613e639d36e7456b0b229241 AS env

FROM cgr.dev/chainguard/python:latest-dev@sha256:91418fa26adfd56d959d80e5da0d7470b5653e4f00ba698ef5d8212e58e3f7f8 AS build

USER root
COPY --from=uv /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-install-project \
    && uv build --wheel --out-dir /dist \
    && uv pip install --python /app/.venv --no-deps /dist/*.whl

FROM cgr.dev/chainguard/python:latest@sha256:6d71f8dbd199350964ce8b10d50fb9d4d8e2bd50316f3a1821dbdc6eef5252fb

WORKDIR /app
COPY --from=env /usr/bin/env /usr/bin/env
COPY --from=env /usr/share/doc/coreutils/copyright /usr/share/licenses/coreutils/copyright
COPY --from=env /usr/share/common-licenses/GPL-3 /usr/share/licenses/coreutils/GPL-3
COPY --from=build --chown=65532:65532 /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1
USER 65532:65532
ENTRYPOINT ["/app/.venv/bin/python"]
CMD ["-m", "glupta_agi"]
