# Glupta Crawl 0.4.1 bounded recovery review packet

Candidate number: 1 of at most 2. Review class: material provider-effect recovery correction.

## Exact identity

- Repository/worktree: `/Users/glupta/Dev/glupta-agi-wt/codex/glupta-canary-unknown-sentinel-fix-20260819`
- Approved/current parent: `0e3fe9b6ad40df80a070c1f32e4f7008c9eb5c04`, tree `421c35076f4dcd83613412eb075c0cba076c7a11`
- Candidate: `f2add8607a1f614bcd0fe6f651c7599422fa3135`, tree `227caa8c4ce88f424f06ab907f420bf6357dda41`
- Exact binary diff SHA-256: `919866c7a4d0d1135dd8f7be204c45433ae79ba33b3d491650e65f5364568d9c`
- Changed paths: `AGENTS.md`, `README.md`, `pyproject.toml`, `src/glupta_agi/client.py`, `src/glupta_agi/workflow.py`, `tests/test_client.py`, `tests/test_workflow.py`, `uv.lock`.
- No dependency version changed. Package version changes `0.4.0 -> 0.4.1` because DBOS application/workflow bytes change.

## Approved baseline and live incident

The deployed 0.4.0 subscription route uses the official pinned Pydantic AI/DBOS/Codex stack, one model slot, provider retries disabled, and a PostgreSQL effect fence with sticky ambiguous recovery. The live image is `sha256:6f8af6a08661f8315d1285e8764ec8b260097426ccd3b8c6d937218250bc9850`; deployment and default-deny egress receipts are recorded in checkpoint `/Users/glupta/.claude/checkpoints/glupta-mvp-deploy-drain-20260819.md`.

Exactly one authorized, customer-free synthetic canary was admitted. Workflow `01a01a92-ff23-7feb-bd9d-b55d7b18d3db` durably ended DBOS `ERROR`; its effect row is `unknown`, reason `provider_outcome_ambiguous`, with no result or provider audit. Adapter execution began, but provider invocation/acceptance is unproven, so no retry is allowed. The secondary defect was deterministic: `_crawl_model_sensitive` serialized ambiguity as scalar JSON `"unknown"`, while Pydantic AI 2.31 generated a structured union output contract and rejected the scalar, producing `UnexpectedModelBehavior` and HTTP 500 instead of the intended sanitized ambiguity/HTTP 503.

## Frozen requirements and change

1. Any post-dispatch uncertainty remains sticky `unknown`; no provider redispatch or fallback.
2. DBOS/Pydantic model-step replay must checkpoint ambiguity as a successful typed value, then the workflow maps it to the existing sanitized `AmbiguousEffectError`.
3. Pydantic AI owns structured union validation; no parallel parser, framework, queue, effect store, or retry layer.
4. Success and ambiguity must each use the exact output tool supplied by `AgentInfo`; drift fails closed.
5. A client HTTP error must preserve the generated non-secret workflow UUID for supported reconciliation without revealing response bodies or credentials.
6. No new provider call, authority, action, service, dependency, secret access, or stage transition.
7. Production semantic code remains <=1,500 lines.

Candidate implementation adds one strict frozen Pydantic object `AmbiguousResult(kind: Literal['unknown'])`; emits native `ToolCallPart` for both `ProviderResult` and `AmbiguousResult`; validates the exact two-tool/no-text contract; maps `AmbiguousResult` to the existing domain ambiguity error; includes workflow UUID in sanitized HTTP errors. It does not add an adapter-stage receipt because the existing DBOS/effect fence already owns recovery truth.

`AGENTS.md` now permanently requires every Glupta release packet to include a concise, deduplicated ledger of material bugs, failures, and recurrence-preventing learnings since the prior release, always covering relevant container/runtime and setup-to-canary behavior. Related incidents are grouped; entries contain only root cause, correction/hold, proof, and residual constraint—not raw logs, chronology noise, or unrelated backlog.

Build-versus-adopt result: retain Pydantic AI 2.31 structured output and DBOS durability. Native scalar `Literal` uses an internal response envelope and retry/error primitives would make the durable model step fail rather than checkpoint an ambiguity value. The one-field domain sentinel is the irreducible translation; adopting another framework would duplicate existing maintained primitives.

## Impact closure

Direct: model response encoding/validation, ambiguity-to-domain mapping, HTTP client diagnostics, package/DBOS application version.

Transitive: API already maps `AmbiguousEffectError` to sanitized 503; DBOS model durability records the typed model result; effect reservation/transition/unknown logic is unchanged; Codex adapter/request/auth/egress/budgets are unchanged; Compose/deployment/signing are unchanged but a new exact image will be required after landing.

Excluded by exact diff and tests: admission payload, source disclosure, credential handling, provider request construction, provider retry count, provider model/effort, network policy, PostgreSQL schema, actions/Walk/Run, outbound effects.

## Deterministic evidence at exact candidate

- Focused: `26 passed, 26 subtests` for workflow/API/client/release boundary.
- Full: `140 passed, 4 skipped, 102 subtests`; skips are the existing environment-gated real-PostgreSQL tests.
- Ruff: pass. `uv lock --check --offline`: pass.
- Offline `uv build --offline --no-sources`: wheel SHA-256 `bd4d082d775716bc8f0ad337322b0907c207b1ad179e056acb2280dc2f58ada1`; sdist SHA-256 `401d02b379399ed19defd43aea42c2328cefa05367ccb1e739ab3f931046183d`.
- Semantic production lines: `1499/1500`. `git diff --check`: pass. Worktree clean.
- New execution regressions: actual Agent accepts one structured ambiguity response without retry; sentinel maps to sanitized domain ambiguity; initial ambiguous adapter call plus replay constructs/invokes adapter exactly once; HTTP failure exposes workflow UUID but not secret/cause/context.
- Security scan/manual review: exact production delta adds no secret read/log, command execution, outbound communication, money/signing path, dependency, authz change, or user-controlled URL. Whole-tree scanner hits are pre-existing controlled surfaces or synthetic test markers; no material finding.

## Container/runtime configuration and incident ledger since 0.4.0

Current steady state is exactly `app` + PostgreSQL. The app is non-root, read-only, cap-drop-all, no-new-privileges, fixed at `172.30.47.2`; PostgreSQL is fixed at `.3`; only loopback intake is published. Private material is projected from broker inputs into pre-staged generation volumes and mounted read-only. Colima installs a boot-persistent systemd/nftables/dnsmasq gate before Docker, allowing app-to-PostgreSQL and approved Codex subscription TCP/443 only. The live 0.4.0 stack remains healthy and untouched during this review.

Bounded incidents and closure:

1. **macOS bind ownership drift.** Colima virtiofs exposed host 0600 files as container `0:0`, failing the non-root exact-owner check. Direct binds and file-sourced Compose secrets were rejected. Correction: broker-fed, fresh named generation volumes staged by a disposable no-network root container, then read-only consumption. Proof: exact UID/mode/inventory attestation, two-service cold start and restart. Residual: plaintext exists in Docker-managed private volumes until gated retirement.
2. **Compose environment secrets versus read-only root.** Compose 5.4 cannot materialize non-file secrets into a read-only service. Correction: keep Compose steady-state at two services and stage externally; no root app, sidecar, or custom secret store.
3. **Stager stdin and capability defects.** Missing `docker run --interactive` caused BusyBox tar EOF; cap-drop-all silently lost target ownership. Correction: `--interactive`, no network, no-new-privileges, cap-drop-all plus only `CHOWN`, and post-extraction metadata attestation. Regression verifies ownership rather than trusting tar exit status.
4. **Docker executable lookup.** Restricting lookup to macOS `os.defpath` omitted the reviewed Homebrew/Studio Docker path. Correction: resolve once from operator PATH and pass the absolute executable with sanitized child environment.
5. **Multiline release-profile broker import.** The `secret set` CLI consumes one line, truncating pretty JSON to one byte. Correction: validate and compact JSON before hidden stdin import; staging receipt binds source hash, projected compact hash, and canonical ReleaseProfile digest. No secret value was logged.
6. **Build isolation.** Exact offline BuildKit failed because the required locked target-platform wheel was absent. Correction: one network-enabled build using digest-pinned bases, `uv sync --frozen`, artifact hashes, provenance/SBOM, then offline scans; no secrets in build context/args. Residual: provenance is evidence, not reproducibility or signing identity.
7. **Colima egress provision privilege/failure semantics.** `after-boot` ran as VM uid 501 and Colima continued Docker startup after failure. Correction: native system provision installs a systemd egress unit; Docker/socket/containerd all `Require` and start `After` it; failure retains a persistent runtime mask/failsafe. Boot journal and structural nft proof show egress finished before all runtimes.
8. **Colima renderer normalization.** Real config included a blank separator after `provision: null`; Colima later stripped ownership marker comments. Correction: canonicalize only isolated trailing newline trivia and verify exact marker-normalized owned content; reject extra/ambiguous provision lists. Full regression suite covers null, marked, normalized, and hostile extras.
9. **Attestation command assumptions.** nft canonical text quotes counter names/omits `type`; `render_colima.py` is intentionally invoked with Python rather than executable mode; `StateChangeTimestampMonotonic` can move after socket bookkeeping. Correction: structural nft JSON, supported `python3.14` renderer invocation, same-boot journal start order plus Requires/After.
10. **Restart health race.** `docker compose restart` returns before health becomes `healthy`; an immediate assertion failed. Correction: bounded POSIX polling (<=120 seconds) before accepting restart/rollback evidence.
11. **0.4.0 canary ambiguity presentation.** The effect correctly became sticky `unknown`, but scalar sentinel validation escaped as HTTP 500. Candidate 0.4.1 fixes only the Pydantic structured-output translation and client workflow-ID evidence. Original workflow remains permanently unknown; no provider retry.

Evidence pointers: checkpoint `/Users/glupta/.claude/checkpoints/glupta-mvp-deploy-drain-20260819.md`; repository `compose.yaml`, `scripts/stage_private_volumes.py`, `deploy/egress/`, attestation tests, and release docs under `docs/releases/0.4.0-subscription-f19a458/`. Reviewers must verify relevant claims from these primary artifacts rather than treating this summary as authority.

## Ordered execution evidence

Observed incident: admission -> DBOS queue -> effect `reserved` -> `dispatching` -> adapter ambiguity -> effect `unknown` -> model emitted scalar sentinel -> Pydantic validation failure -> DBOS `ERROR` -> HTTP 500. Provider acceptance is unknown; no retry occurred.

Candidate negative regression: first reservation -> one adapter ambiguity -> `hold_unknown` -> structured ambiguity tool result -> domain ambiguity; replay observes `unknown`, does not construct/call adapter, and returns the same domain ambiguity. Expected adapter calls=1; observed=1.

Candidate success regression: provider result is emitted through the exact `final_result_ProviderResult` output tool and validated by Pydantic; existing result/audit/effect validations remain unchanged.

### Exact execution receipts added after the first Codex evidence hold

These receipts amend review evidence only. Candidate commit, tree, diff, source,
tests, dependencies, and release semantics remain byte-identical.

1. `/private/tmp/glupta-041-frontier/dbos-ambiguity-harness.json`
   - SHA-256: `5c84dfcb966edb6206e6591ba5513f30d90a1aac13107970edcdefab548788c6`
   - Harness SHA-256: `db0e557b828cd86e57d1453cf7cd68afc1e9d34ff286aa039493ec64042db30c`
   - Binds exact candidate `f2add8607a1f614bcd0fe6f651c7599422fa3135`
     and tree `227caa8c4ce88f424f06ab907f420bf6357dda41`.
   - Uses production DBOS 2.29 queue/workflow, Pydantic Agent and DBOSDurability
     with a disposable loopback PostgreSQL 17.6 database and a synthetic fake
     adapter that raises `ProviderAmbiguousError`; it performs no provider,
     authentication, secret, or external-network action.
   - The durable model step `crawl_observe_agent__model.request` checkpoints a
     successful `ModelResponse` containing the exact ambiguity output
     `ToolCallPart`, with no step error. The outer workflow returns the existing
     sanitized `AmbiguousEffectError`; the effect is sticky `unknown` with
     `provider_outcome_ambiguous`. DBOS resume and retrieve keep the durable
     step count at one and adapter-call count at exactly one, proving no
     redispatch. The disposable database container was removed and its exact
     container count is zero.
2. `/private/tmp/glupta-041-frontier/live-unknown-workflow-readonly-receipt.json`
   - SHA-256: `3d0cb31105397f4735ac43e843c6887a449f696e0c0e39bf80a7a364519539a5`
   - Binds original workflow `01a01a92-ff23-7feb-bd9d-b55d7b18d3db` to DBOS
     `ERROR`, one durable model step, no pending/enqueued match, and effect
     `unknown` / `provider_outcome_ambiguous` with null result, audit, provider
     identifiers, thread/turn identifiers, and provider timestamps.
   - It performed no replay, resume, enqueue, provider call, restart, or
     mutation and loaded no workflow input/output/source/provider body.
   - Method limitation: DBOS list APIs provided workflow metadata, but the
     application exposes no public effect-inspection endpoint. The effect
     metadata was therefore read through the configured application
     `SQLAlchemyDatasource` in an explicit `SET TRANSACTION READ ONLY`
     transaction selecting only named metadata columns. This is sufficient to
     prove the sticky local row and absence of redispatch evidence, but the
     null audit cannot resolve whether the provider accepted the original call;
     the original workflow remains permanently unknown.

All three receipt/harness `.sha256` sidecars pass. Review the compact receipts,
not raw logs. They are external review artifacts under `/private/tmp` and are
not release payload or tracked candidate bytes.

## Reviewer question and admissibility

Does exact candidate `f2add86...` contain any substantiated material blocker to landing, building, attesting, and deploying it **without a provider call**, while preserving the original workflow as permanently unknown and requiring separate approval for any later canary?

A blocker must identify a frozen requirement/standing invariant, exact evidence, plausible material impact, and smallest sufficient fix or missing proof. Novel hardening and preferences are backlog, not blockers. Return PASS only with zero substantiated material blockers. Do not edit, deploy, authenticate, access secrets, or invoke a provider.
