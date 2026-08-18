# glupta agi

Small private runtime for Glupta AGI (Artificial Glupta Intelligence).

## Crawl MVP

The first vertical slice is `evidence_brief_v1`: an authenticated loopback API
accepts one question and up to 20 explicitly selected UTF-8 Markdown or text
files from a read-only input root. It produces a typed, source-grounded brief
with resolvable file-and-line citations, uncertainties, and next decisions.

Version `0.3.0` is a **dispatch-held candidate**, not a production release.
It replaces the unsupported consumer-session route with a provider-supported
OpenAI Responses API edge, while requiring external account and release evidence
that this repository cannot manufacture.

Candidate controls:

- secure intake and request canonicalization are implemented;
- DBOS owns durable execution and idempotency;
- one DBOS-native queue bounds all Crawl model work to one concurrent workflow;
- Pydantic AI v2's native `DBOSDurability` capability routes the one typed
  model request through a DBOS step with provider retries disabled;
- one predeclared `model-0` effect slot fences the external model call before
  dispatch through a DBOS datasource transaction and fails closed when a crash
  leaves its outcome ambiguous;
- the official OpenAI SDK sends exactly one synchronous Responses API request
  with SDK retries disabled, `store=false`, no tools, no redirects or ambient
  proxy configuration, `gpt-5.6-sol`, and `medium` reasoning;
- the frozen effect binds the request-body and release-profile digests, a
  conservative 270,000-token input ceiling, 4,000-token total output/reasoning
  ceiling, $1.85 USD upper-bound reservation (including the documented cache-write
  premium), and 300-second queue/wall limits;
- successful replay returns the recorded provider request/response IDs, token
  usage, conservative USD upper bound, and typed output instead of fabricating
  missing usage;
- runtime bearer material is read from a private file and never persisted;
- PostgreSQL is not published and the intake API is loopback-only;
- no live messaging or action tools are present.

Selected file contents and the question are sent to the named OpenAI project.
The local client requires `--ack-external-disclosure`; only select files that
are appropriate to disclose. `store=false` does not itself prove zero provider
retention, so a current data-terms receipt remains mandatory release evidence.

The Crawl acceptance boundary is this repository: one useful durable `OBSERVE`
brief, durable workflow/effect state, authenticated loopback intake, explicit
local files, and no action tools. DIRECT, COMPOUND, and EXECUTE remain disabled
until measured Crawl evidence earns the next Blueprint stage.

## Quality loop

Pydantic Evals runs the frozen 20-case workload against the same fenced OpenAI
generator used by DBOS. It runs sequentially, prints a report, and saves a
machine-readable receipt outside git. Pydantic AI's delegation, programmatic
hand-off, and graph patterns are complexity levels, not components Crawl must
install; the single-agent pattern is the only one this stage has earned.

```sh
uv run --extra dev python -m evals.runner --output runtime/evals/latest.json
```

Use `--case EV-001-single-source` or `--limit 1` for a bounded probe. A failed
task or deterministic assertion makes the command exit non-zero.

## Developer checks

```sh
uv run --extra dev ruff check .
uv run --extra dev pytest -q
uv lock --check
```

## Held deployment contract

The Community profile remains exactly one non-root app executor plus PostgreSQL.
Only the intake port is published on loopback. The app has a read-only root,
drops all Linux capabilities, forbids privilege escalation, and has bounded
CPU, memory, PIDs, and temporary storage.

Do not start this candidate until an exact release profile has been produced and
approved. The private mode-`0600` JSON profile must bind the dedicated OpenAI
project/service-account/key identifiers and generation, disclosure and rights
evidence, data terms and region, model, rate and token/USD/time ceilings, expiry,
price schedule, manifest, SBOM, provenance, signature, approval, and isolated
rollback rehearsal. The API key is a separate private mode-`0600` file and is
read only after the durable effect reservation exists. Neither file is committed.

Once every independent release gate is satisfied, the operator may set the two
absolute mount paths and start the profile:

```sh
export GLUPTA_RELEASE_PROFILE_FILE=/absolute/path/to/release-profile.json
export GLUPTA_OPENAI_API_KEY_FILE=/absolute/path/to/openai-api-key
export GLUPTA_CREDENTIAL_GENERATION=1
export GLUPTA_UID=$(id -u) GLUPTA_GID=$(id -g)
docker compose up -d --build --remove-orphans
curl --fail http://127.0.0.1:8765/healthz
```

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

For replay-sensitive work, create a versioned input filename and leave its
contents unchanged after submission. Record its SHA-256 and idempotency key;
exact replay requires the same question and selected content, while changing a
selected file under the same key is rejected. Mutable `current` aliases may
continue to evolve, but do not select them when historical replay is required.
