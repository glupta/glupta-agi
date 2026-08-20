# glupta agi

Small private runtime for Glupta AGI (Artificial Glupta Intelligence).

## Crawl MVP

The first vertical slice is `evidence_brief_v1`: an authenticated loopback API
accepts one question and up to 20 explicitly selected UTF-8 Markdown or text
files from a read-only input root. It produces a typed, source-grounded brief
with resolvable file-and-line citations, uncertainties, and next decisions.

Version `0.4.4` is a **deployment- and dispatch-held candidate**, not a running
production release. Crawl adopts the official `openai-codex` SDK and its pinned
Codex runtime, authenticated by an approved ChatGPT subscription. It does not
accept an OpenAI API key, project, service account, metered API route, or USD
budget.

The 0.4.2 candidate removed Crawl's Pydantic AI `FunctionModel` translation
bridge. The single native Codex turn now runs inside one named DBOS step with
retries disabled. Pydantic still owns typed contracts and Pydantic Evals remains
the offline evaluation primitive. The component-by-component evidence and
deferred alternatives are recorded in
[`docs/component-market-review-2026-08-19.md`](docs/component-market-review-2026-08-19.md).

The live 0.4.3 runtime adds only the standalone GNU coreutils `env` executable from
the digest-pinned Debian Bookworm image, with its GPL-3+ copyright and license
files. The Chainguard runtime does not provide an executable `env` on Python's
default search path, while the official SDK's environment overlay cannot clear
ambient state. Chainguard coreutils is not anonymously available, Wolfi
coreutils is a larger multicall binary with extra runtime libraries, and
BusyBox would reintroduce a shell applet. The dedicated 68 KiB Debian binary
therefore preserves the required `env -i` boundary without a launcher, shell,
service, or Python dependency.

The 0.4.4 candidate binds separately approved canary or conditional-drain
artifacts to the exact source bytes admitted through the existing endpoint.
It also sanitizes rejected API headers, expected client HTTP protocol failures,
and approval-helper preflight failures before they cross public traceback
boundaries. It does not change provider dispatch, effects, budgets, retries,
workflow topology, or any held deployment or task-drain authority.

Since 0.4.3, the material incident ledger is:

- **Held validation confidentiality failure:** FastAPI's default validation
  response could include rejected inline input, while an unpaired surrogate
  could escape admission encoding with sensitive traceback locals. The fix uses
  FastAPI's native `RequestValidationError` hook for a fixed 422 and remints
  inline UTF-8 failures only after the source-bearing probe returns. ASGI and
  direct capture-locals regressions prove no enqueue, provider call, marker, or
  exception chain; invalid input remains terminal and retry-free.
- **Setup/build failure:** a fresh worktree invoked a host `pytest` because the
  test tools were declared as an opt-in extra. They now live in uv's default
  `dev` dependency group, so `uv run --locked pytest` resolves the locked
  project executable; frozen/offline lock and package checks remain release gates.
- **Runtime and rollout relevance:** no service, store, dependency, container,
  database, deployment, restart, rollback, effect, budget, or retry behavior
  changed. Deployment, restart, rollback, provider dispatch, task drain, and the
  canary remain held; a future approved canary must use the exact-byte-bound
  inline route and the same fixed 422 boundary.

The source-stage package is Debian `coreutils 9.1-1`; its corresponding source
is Debian's `coreutils_9.1.orig.tar.xz` plus `coreutils_9.1-1.debian.tar.xz` in
the Bookworm archive. Final-image package scanners do not attribute the copied
binary because the Debian package database is intentionally not copied. Do not
claim a coreutils SBOM component from the final image alone: bind the source
image digest, package/version, executable SHA-256 and glibc-only ELF dependency,
and the copied copyright/GPL-3 text in release evidence. Any distribution must
also make the corresponding GPL source available.

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
uv run --frozen python -m evals.runner \
  --output runtime/evals/latest.json
```

Use `--case EV-001-single-source` or `--limit 1` for a bounded probe. This is a
model dispatch and remains independently gated.

## Developer checks

```sh
uv run --frozen ruff check .
uv run --frozen python -m pytest -q
uv lock --check --offline
```

The built-image contract is opt-in and never authenticates or starts a turn:

```sh
GLUPTA_RUNTIME_IMAGE=<local-built-image> \
  uv run --frozen python -m pytest -q tests/test_runtime_image.py
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
metered API architecture. The native subscription route instead requires only
the pinned Codex backend at `chatgpt.com` and managed token refresh at
`auth.openai.com`. `deploy/egress/render_colima.py` prepares an exact Colima
`system` provisioning candidate that adopts Lima's root boot phase and the VM's
maintained nftables and dnsmasq primitives. On the first app-down application it
persistently masks Docker/containerd, installs a native systemd egress oneshot and
runtime dependency drop-ins, and starts the egress unit. That unit atomically
installs a default-deny rule for the fixed app address before the remaining
setup. Later failure leaves the first-application mask and failsafe in
place; success replaces the nft rule with the exact policy, verifies dnsmasq,
and only then removes the mask. On every later boot, Docker's service
and socket and containerd require the egress unit to succeed first.
The app may reach PostgreSQL on TCP 5432 and DNS-resolved addresses for those
two hosts on TCP 443; every other forwarded app packet is rejected. It does not
add a proxy, sidecar, custom daemon, dependency, or framework. The small native
oneshot and short first-application runtime hold are required because Lima
records a failed system provision but still signals boot completion, and the
container runtime can start before resumed-VM system provisioning begins.

The renderer validates the exact two-service Compose network identity, pinned
Codex 0.147.0 dependency, clean-environment launch, disabled extension surface,
and absence of an endpoint override before it writes a candidate. It never
changes Colima or live firewall state:

```sh
python3 deploy/egress/render_colima.py render \
  --config /Users/glupta/.colima/default/colima.yaml \
  --repo "$PWD" \
  --output /private/tmp/glupta-colima-candidate.yaml
python3 deploy/egress/render_colima.py verify \
  --config /private/tmp/glupta-colima-candidate.yaml \
  --repo "$PWD"
```

Applying that candidate, restarting shared Colima, proving the policy after a
reboot, and starting Compose remain separate deployment approvals. The
DNS-derived nftables set is a proportional L3/L4 control, not TLS-hostname
enforcement: dnsmasq also matches subdomains of the two owned domains, and a
compromised process could reuse an allowed shared CDN address.
That residual is accepted only with the exact immutable Crawl image, no tools,
no web search, no apps/plugins, a read-only root, and the separately verified
Codex runtime. A hostile-workload FQDN requirement would need an L7 gateway and
would change the approved two-service architecture.

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

Provision the Codex volume only through the official Codex login flow directly
into a newly labeled Docker volume; never copy a host `auth.json`. Before the
volume can be named in Compose, attest it offline against the exact local image:

```sh
python3 scripts/attest_codex_subscription_volume.py \
  --volume glupta-codex-subscription-g<generation>-<32-hex-nonce> \
  --generation <generation> \
  --image-id sha256:<exact-local-image-id>
```

The volume must carry `com.glupta.private=true`,
`com.glupta.purpose=codex-subscription`, and the matching
`com.glupta.generation` label. The attestor runs the exact image with no network,
a read-only root, no capabilities, and the volume mounted read-only. It reads
only filesystem metadata and exact filename inventories outside the non-secret
native system-skill tree, whose regular-file bytes it hashes for integrity. It
does not open any other regular file. It never reads authentication bytes, log
bytes, installation bytes, or model-cache bytes. `/run/codex` must be owned by
UID 65532 at mode `0700` and match one of
two complete official Codex 0.147.0 file-store layouts: completed-login before
first use, or the exact post-use layout materialized by the native runtime.
Both layouts contain a regular mode-`0600`, single-link `auth.json`;
`log/codex-login.log`, also regular mode `0600` and single-link; and mode-`0700`
`tmp/arg0`. Direct device login exits through the Codex CLI's
immediate success path, so its one native arg0-helper directory remains after a
normal exit. The directory name must match `codex-arg0[A-Za-z0-9]{6}`, be mode
`0755`, and contain exactly a regular mode-`0644`, single-link `.lock` plus the
four single-link symlinks `apply_patch`, `applypatch`, `codex-execve-wrapper`,
and `codex-linux-sandbox`. Each symlink must target the exact bundled
`/app/.venv/lib/python3.14/site-packages/codex_cli_bin/bin/codex` executable.
After first native use, the root additionally contains only single-link,
mode-`0644` regular files `installation_id` and `models_cache.json`, plus the
mode-`0755` `skills/.system` tree installed by the pinned runtime. The attestor
binds every relative path, directory inventory, and regular-file SHA-256 in
that tree to a manifest independently reproduced by a networkless, no-auth
native Codex 0.147.0 app-server startup in the exact release image and matched
against the observed post-use volume. It permits only the six bundled system
skills and marker, requires directories at mode `0755` and regular files at
mode `0644`, and rejects every symlink there before opening any skill file. Every
node must be owned by UID 65532 and have the exact native link count; the `log`
and `tmp` directories must grant their owner full access and must have no
special or group/world write bits. The attestor rejects incomplete or mixed
layouts, zero or multiple arg0 sessions, alternate helper targets, user skills,
and any missing or additional configuration, hook, MCP, or state entry. Its
receipt records inventories, modes, and the non-secret system-skill manifest;
it does not prove the account/plan.

Build-versus-adopt: Codex owns native system-skill materialization but 0.147.0
does not expose a supported offline integrity receipt for the persisted tree;
Docker supplies isolation but not that product-specific admission decision.
The bounded attestor composes the exact official image, Docker's read-only
probe, and Python's standard SHA-256 implementation. It adds no service or
dependency and owns only the missing label, layout, and content-binding policy.
Account identity, live route egress, and official-login rotation remain
independent deployment gates.
The receipt is point-in-time metadata evidence: re-run it against the same
volume and image immediately before the separately approved Compose start.

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

### Canary and conditional-drain approval requests

Use the tracked v2 helper when a submission requires approval. It binds each
repository path to the exact path the client will select, then proves the
selected path is a non-symlink regular file with the approved SHA-256 before
emitting the artifact:

```sh
uv run python scripts/crawl_request_v2.py create \
  --purpose canary \
  --question "What changed, what is uncertain, and what should we decide next?" \
  inputs/versioned-packet.txt > /private/review/glupta-canary-request-v2.json
```

Hash and approve that exact JSON artifact. Immediately before execution, the
same helper rechecks the artifact digest and source SHA, retains the exact
verified `CanonicalRequest` source bytes, and submits them inline using only
the approved `client_selected_path`. The existing strict Pydantic endpoint
schema and `admit_inline_request` validator admit those bytes; the server's
configured input root is irrelevant to this path. Artifact digest and source
preflight complete before capability access or submission:

```sh
uv run python scripts/crawl_request_v2.py execute \
  --artifact-sha256 <approved-artifact-sha256> \
  --idempotency-key <approved-uuidv7> \
  /private/review/glupta-canary-request-v2.json
```

Use `--purpose conditional_drain` for a separately approved drain artifact.
`verify` performs the same deterministic preflight without reading a token or
dispatching: `uv run python scripts/crawl_request_v2.py verify \
--artifact-sha256 SHA256 REQUEST.json`.

Build-versus-adopt: Pydantic's strict request models and the existing intake,
client transport, API endpoint, and workflow payload already own validation,
HTTP, authentication, admission, and durable request identity. The inline
request branch is custom only for the missing approval-to-admission byte
binding; it adds no dependency, service, store, endpoint, retry, or effect.
