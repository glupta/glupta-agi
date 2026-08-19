# glupta agi

Small private runtime for Glupta AGI (Artificial Glupta Intelligence).

## Crawl MVP

The first vertical slice is `evidence_brief_v1`: an authenticated loopback API
accepts one question and up to 20 explicitly selected UTF-8 Markdown or text
files from a read-only input root. It produces a typed, source-grounded brief
with resolvable file-and-line citations, uncertainties, and next decisions.

Version `0.4.0` is a **deployment- and dispatch-held candidate**, not a running
production release. Crawl adopts the official `openai-codex` SDK and its pinned
Codex runtime, authenticated by an approved ChatGPT subscription. It does not
accept an OpenAI API key, project, service account, metered API route, or USD
budget.

Candidate controls:

- secure intake and canonical request identity;
- DBOS-owned durable execution and idempotency;
- one DBOS-native queue with one concurrent Crawl workflow;
- one predeclared `model-0` effect slot, reserved before dispatch through a
  PostgreSQL transaction and held sticky-unknown after an ambiguous crash;
- exactly one ephemeral Codex turn using `gpt-5.6-sol` at `medium` reasoning;
- the bundled Codex runtime pinned to `0.147.0` and a verified non-usage-based
  ChatGPT plan;
- read-only sandbox, deny-all approvals, no web, no tools, no plugins, no apps,
  no subagents, and no shell;
- runtime and stream retries set to zero;
- a typed output schema, source-citation resolution, and replay from the durable
  recorded result rather than a second model call;
- a 262,144-byte admitted-input ceiling, 300-second queue/wall deadlines, one
  call, and fail-closed post-observed usage ceilings;
- PostgreSQL unpublished, intake loopback-only, non-root read-only app, and no
  messaging or action tools.

Codex does not expose a provider idempotency key or a hard pre-dispatch output
token reservation for this subscription route. Crawl therefore never claims
either. Its application effect fence prevents redispatch after any state that
may have reached Codex, and observed usage is validated before release.

Selected file contents and the question are disclosed to the ChatGPT
subscription account through Codex. The local client requires
`--ack-external-disclosure`; select only material approved for that account.

The Crawl acceptance boundary is one useful durable `OBSERVE` brief, durable
workflow/effect state, authenticated loopback intake, explicit local files, and
no action tools. DIRECT, COMPOUND, EXECUTE, Walk, and broader Hermes activation
remain disabled.

## Quality loop

Pydantic Evals runs the frozen workload against the same fenced subscription
generator used by DBOS. It runs sequentially, prints a report, and saves a
machine-readable receipt outside git.

```sh
uv run --frozen --extra dev python -m evals.runner \
  --output runtime/evals/latest.json
```

Use `--case EV-001-single-source` or `--limit 1` for a bounded probe. This is a
model dispatch and remains independently gated.

## Developer checks

```sh
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev python -m pytest -q
uv lock --check --offline
```

## Held deployment contract

The Community profile is exactly one non-root app executor plus PostgreSQL.
Only the intake port is published on loopback. The app has a read-only root,
drops all Linux capabilities, forbids privilege escalation, and has bounded
CPU, memory, PIDs, and temporary storage.

Do not start this candidate until these separate gates close:

- an exact approved image reference and matching manifest, SBOM, provenance,
  signature, rollback, and release approval;
- a current non-usage-based ChatGPT subscription account and a private Codex
  home whose generation matches the release profile;
- approved disclosure, rights, retention, and account evidence;
- a verified native Codex network route with default-deny egress appropriate to
  the pinned runtime; and
- isolated startup, restart, rollback, and no-provider rehearsals.

The previous regional Responses-API firewall renderer was retired with that
metered API architecture. It must not be reused to imply that the native Codex
subscription route is constrained. Deployment remains held until the actual
runtime endpoints and a proportional egress control are proven.

The image reference is intentionally not embedded in Compose. An older signed
Responses-API image remains historical evidence and cannot accidentally start
as this candidate.

Compose mounts three external volumes:

- an immutable app-private volume containing the intake token, PostgreSQL
  password, and approved release profile;
- a separate immutable PostgreSQL-private volume; and
- an approved Codex-subscription volume at `/run/codex`, writable only because
  the official runtime may refresh its own subscription authentication state.

No credential value, auth file, host secret path, or `.env` file belongs in the
repository. `scripts/stage_private_volumes.py` stages only the app/PostgreSQL
bundle supplied to its short-lived process by the approved local broker. Codex
subscription-volume provisioning and rotation are a separate deployment gate;
the application never reads or prints the auth file itself.

After every independent gate is satisfied, the operator supplies only opaque
generation and volume/image references to Compose:

```sh
export GLUPTA_AUTH_GENERATION=<approved-generation>
export GLUPTA_APP_PRIVATE_VOLUME=<app-volume-from-staging-receipt>
export GLUPTA_POSTGRES_PRIVATE_VOLUME=<postgres-volume-from-staging-receipt>
export GLUPTA_CODEX_SUBSCRIPTION_VOLUME=<approved-codex-volume>
export GLUPTA_IMAGE=<exact-approved-image-reference>
docker compose up --detach --no-build --pull never --remove-orphans \
  --wait --wait-timeout 120
curl --fail http://127.0.0.1:8765/healthz
```

These are deployment instructions, not authorization to run them. Provider
dispatch, task draining, and a controlled canary each remain independently
approved actions.

PostgreSQL password rotation is a separate database migration gate. Replacing
`POSTGRES_PASSWORD_FILE` does not rotate the role in an existing data volume.

## Local submission

Submit only explicitly selected `.md` or `.txt` files from `inputs/`. The
bearer capability is required for `/v1/evidence-brief` and is never committed.

Use the local client so the bearer capability stays out of shell arguments and
environment variables. Paths are relative to `inputs/`; the default output is
the grounded Markdown brief, while `--json` returns the complete typed result:

```sh
uv run glupta-crawl-submit \
  --ack-external-disclosure \
  --question "What changed, what is uncertain, and what should we decide next?" \
  notes.md evidence/current.txt
```

The client accepts only the loopback Crawl endpoint, validates the private
`runtime/intake-token` file, creates a UUIDv7 idempotency key, performs no
retry, and never prints the capability. Pass `--idempotency-key` to replay an
exact prior request or `--token-file` when the private runtime directory is
elsewhere.

For replay-sensitive work, use a versioned input filename and preserve its
bytes. Record its SHA-256 and idempotency key; exact replay requires the same
question and selected content.
