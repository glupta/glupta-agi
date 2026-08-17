# glupta agi

Small private runtime for Glupta AGI (Artificial Glupta Intelligence).

## Crawl MVP

The first vertical slice is `evidence_brief_v1`: an authenticated loopback API
accepts one question and up to 20 explicitly selected UTF-8 Markdown or text
files from a read-only input root. It produces a typed, source-grounded brief
with resolvable file-and-line citations, uncertainties, and next decisions.

Current build state:

- secure intake and request canonicalization are implemented;
- DBOS owns durable execution and idempotency;
- one DBOS step invokes the secondary Codex subscription with a JSON schema;
- Codex is ephemeral, read-only, tool-disabled, and pinned to `gpt-5.6-sol`
  with `medium` reasoning;
- runtime bearer material is read from a private file and never persisted;
- PostgreSQL and the intake API are exposed on loopback only;
- no live messaging or action tools are present.

Selected file contents are sent to the secondary Codex subscription to generate
the brief. Only select files that are appropriate to disclose to OpenAI; this
MVP does not claim local de-identification.

The Crawl acceptance boundary is this repository: one useful durable evidence
brief, durable workflow state, authenticated loopback intake, explicit local
files, and no action tools. Later-stage agent architecture does not block this
private MVP.

## Quality loop

Pydantic Evals runs the frozen 20-case workload against the same Codex
generator used by DBOS. It runs sequentially, prints a report, and saves a
machine-readable receipt outside git. The four later supervisory roles and the
Pydantic AI Harness are deliberately not Crawl runtime components.

```sh
uv run --extra dev python -m glupta_agi.evals --output runtime/evals/latest.json
```

Use `--case EV-001-single-source` or `--limit 1` for a bounded probe. A failed
task or deterministic assertion makes the command exit non-zero.

## Developer checks

Core tests use only the Python standard library and can run before dependency
selection:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Local deployment

PostgreSQL runs in Docker. The application runs on Studio so it can use the
existing secondary Codex subscription. Both database and intake ports are
published on loopback only.

Create `inputs/`, then place private mode-`0600` values at
`runtime/intake-token` and `runtime/postgres-password`. Start PostgreSQL, then
run the app in a named Studio `tmux` session:

```sh
docker compose up -d --remove-orphans
tmux new-session -d -s glupta-crawl \
  "GLUPTA_INPUT_ROOT=$PWD/inputs GLUPTA_ARTIFACT_ROOT=$PWD/runtime/artifacts \
   GLUPTA_INTAKE_TOKEN_FILE=$PWD/runtime/intake-token \
   GLUPTA_POSTGRES_PASSWORD_FILE=$PWD/runtime/postgres-password \
   GLUPTA_POSTGRES_HOST=127.0.0.1 GLUPTA_POSTGRES_PORT=55432 GLUPTA_PORT=8765 \
   uv run glupta-agi"
curl --fail http://127.0.0.1:8765/healthz
```

Submit only explicitly selected `.md` or `.txt` files from `inputs/`. The
bearer capability is required for `/v1/evidence-brief` and is never committed.
