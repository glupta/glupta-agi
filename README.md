# glupta agi

Small private runtime for Glupta AGI (Artificial Glupta Intelligence).

## Crawl MVP

The first vertical slice is `evidence_brief_v1`: an authenticated loopback API
accepts one question and up to 20 explicitly selected UTF-8 Markdown or text
files from a read-only input root. It produces a typed, source-grounded brief
with resolvable file-and-line citations, uncertainties, and next decisions.

Version `0.3.1` is a **dispatch-held candidate**, not a production release.
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
  ceiling, $2.00 USD upper-bound reservation (including the documented cache-write
  premium and regional-processing uplift), and 300-second queue/wall limits;
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
rollback rehearsal. The API key is a separate private mode-`0600` file; startup
validates its approved digest without a provider call, and the provider edge
resolves it for dispatch only after the durable effect reservation exists.
Neither file is committed.

The image uses a digest-pinned, non-root Chainguard Python runtime. Compose 5.4
cannot materialize non-file secrets into a read-only service, so the approved
local broker invokes `scripts/stage_private_volumes.py` to stream one complete
generation over stdin into fresh app/PostgreSQL Docker volumes. Compose mounts
those volumes read-only; plaintext values and host secret paths never belong in
this repository or a `.env` file. Preserve the immediately prior generation for
rollback and delete a retired volume only after its rollback window closes.

The release profile selects exactly `us` or `europe`, binds the corresponding
regional Responses endpoint, and uses the frozen 10% regional price schedule.
Static container addresses exist only so the separately approved Colima
nftables/dnsmasq gate can default-deny app egress.

Prepare—but do not apply—the reviewed Colima gate with the repository renderer.
It accepts only the exact Glupta-owned `provision: null` value or a prior marked
Glupta block, and verifies the Compose subnet/addresses against the regional
endpoint map before producing a candidate. Rendering does not change Colima:

```sh
candidate=$(mktemp)
uv run --frozen python deploy/egress/render_colima.py render \
  --region us \
  --config /Users/glupta/.colima/default/colima.yaml \
  --compose compose.yaml \
  --output "$candidate"
uv run --frozen python deploy/egress/render_colima.py verify \
  --region us --config "$candidate" --compose compose.yaml
```

Selecting `us` versus `europe`, installing the candidate, stopping or restarting
Colima, applying firewall state, and running live egress checks are an independent
deployment gate. Keep the app absent throughout an install or rollback. The gate
allows only established traffic, app-to-PostgreSQL TCP/5432, and TCP/443 to the
selected endpoint's DNS-derived IPv4 set; all other app traffic is rejected.
This is an L3/L4 destination-IP control, not TLS-host proof: shared provider IPs
remain a documented limitation and would require a separately approved L7 design.

Once every independent release gate is satisfied, the approved local secret
broker supplies the four private values only to the staging subprocess. Its JSON
receipt provides the two non-secret volume names used by Compose:

```sh
export GLUPTA_CREDENTIAL_GENERATION=1
uv run --frozen python scripts/stage_private_volumes.py
export GLUPTA_APP_PRIVATE_VOLUME=<app_volume-from-receipt>
export GLUPTA_POSTGRES_PRIVATE_VOLUME=<postgres_volume-from-receipt>
test "$(docker image inspect glupta-crawl@sha256:a6d4026c9753313a3a22e27fde5d121e4f0b95872293eaad84eeffecb68e1bdf --format '{{.Id}}')" = \
  'sha256:a6d4026c9753313a3a22e27fde5d121e4f0b95872293eaad84eeffecb68e1bdf'
docker compose up --detach --no-build --pull never --remove-orphans --wait --wait-timeout 120
curl --fail http://127.0.0.1:8765/healthz
```

Routine provider-key/profile rotation stages only a new app volume and preserves
the existing PostgreSQL private volume:

```sh
uv run --frozen python scripts/stage_private_volumes.py --app-only
```

PostgreSQL password rotation is a separate database migration gate. Replacing
`POSTGRES_PASSWORD_FILE` does not rotate the role in an existing data volume.

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
