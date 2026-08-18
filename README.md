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
- one DBOS-native queue bounds all Crawl model work to one concurrent workflow;
- Pydantic AI v2's native `DBOSDurability` capability routes the one typed
  model request through a DBOS step with provider retries disabled;
- one predeclared `model-0` effect slot fences the external model call before
  dispatch through a DBOS datasource transaction and fails closed when a crash
  leaves its outcome ambiguous;
- the official Codex SDK binds a non-ephemeral thread and turn to that effect;
  the turn is read-only, web/tool-disabled, clean-environment launched, and
  pinned to `gpt-5.6-sol` with `medium` reasoning;
- runtime bearer material is read from a private file and never persisted;
- PostgreSQL is not published and the intake API is loopback-only;
- no live messaging or action tools are present.

Selected file contents are sent to the secondary Codex subscription to generate
the brief. Only select files that are appropriate to disclose to OpenAI; this
MVP does not claim local de-identification.

The Crawl acceptance boundary is this repository: one useful durable `OBSERVE`
brief, durable workflow/effect state, authenticated loopback intake, explicit
local files, and no action tools. DIRECT, COMPOUND, and EXECUTE remain disabled
until measured Crawl evidence earns the next Blueprint stage.

## Quality loop

Pydantic Evals runs the frozen 20-case workload against the same fenced Codex
generator used by DBOS. It runs sequentially, prints a report, and saves a
machine-readable receipt outside git. Pydantic AI's delegation, programmatic
hand-off, and graph patterns are complexity levels, not components Crawl must
install; the single-agent pattern is the only one this stage has earned.

```sh
uv run --extra dev python -m glupta_agi.evals --output runtime/evals/latest.json
```

Use `--case EV-001-single-source` or `--limit 1` for a bounded probe. A failed
task or deterministic assertion makes the command exit non-zero.

## Developer checks

```sh
uv run --extra dev ruff check .
uv run --extra dev pytest -q
uv lock --check
```

## Local deployment

The Community profile is exactly one non-root app executor plus PostgreSQL.
Only the intake port is published, on loopback. Codex mutable state is confined
to a bounded, hardened container tmpfs. Only the dedicated secondary
subscription's `auth.json` is mounted from the host; the rest of that Codex home
is never exposed to the app.

Create `inputs/` and `runtime/`, then place private mode-`0600` values at
`runtime/intake-token` and `runtime/postgres-password`. The secondary credential
must be dedicated to Crawl for the deployment lifetime; do not run another
Codex process or machine from the same credential family concurrently. Verify
only its metadata, then point the deployment-only mount variable at the exact
regular, non-symlink mode-`0600` file and start the two-service profile:

```sh
GLUPTA_CODEX_AUTH_FILE=/absolute/path/to/secondary/codex-home/auth.json
uv run python -c 'import os,stat,sys; s=os.lstat(sys.argv[1]); assert stat.S_ISREG(s.st_mode) and not stat.S_ISLNK(s.st_mode) and s.st_uid == os.getuid() and stat.S_IMODE(s.st_mode) == 0o600' "$GLUPTA_CODEX_AUTH_FILE"
export GLUPTA_SECONDARY_CODEX_AUTH_FILE="$GLUPTA_CODEX_AUTH_FILE"
export GLUPTA_UID=$(id -u) GLUPTA_GID=$(id -g)
docker compose up -d --build --remove-orphans
curl --fail http://127.0.0.1:8765/healthz
```

Submit only explicitly selected `.md` or `.txt` files from `inputs/`. The
bearer capability is required for `/v1/evidence-brief` and is never committed.
