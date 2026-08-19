# Crawl foundation final-review packet — candidate R9

Review date: 2026-08-18

Controller: Codex

Status: frozen exact candidate. This packet grants no deployment, provider
dispatch, credential access or creation, spend, task drain, Walk, public,
Hermes, tool, action, outbound, signing, trading, transfer, or money authority.

## Review question

Does the reconciled Crawl foundation have zero substantiated material blockers
as an honest dispatch-held candidate, while preserving every open release gate?
Cite primary evidence for every material blocker and name the smallest safe
disposition. Do not weaken a normative requirement to match code.

## Exact candidate tuple

- Product: `8fb16e1433839f92600be4e8d310de1c4469c568`, based on rejected R8
  product `3bb568a2885132d584717cbed63f3cc08c99916e`.
- Control documents: `b18cfd753376cd29ba8efd37a15447361f064835`, based on
  rejected R8 control `52248283708cf2e489102c705e5775625f55cee6`.
- Blueprint and operating state: `87bdb5aa03e5c4775ef336a1535b2a961419b925`,
  based on rejected R8 Blueprint `de4d7e439d67b3823a2c8fbff88f99c6112ccc0f`.

The normative identity is this ordered tuple, this packet SHA-256, and the
companion source-manifest SHA-256. The Task Spine row is administrative state,
not evidence that a requirement passed.

## Frozen contract

1. Crawl is one authenticated loopback, source-grounded, read-only `OBSERVE`
   workflow over one to twenty explicitly selected local Markdown/text files.
   It returns a typed evidence brief with exact citations, uncertainties, and
   next decisions. FastAPI is admission/health only; PostgreSQL is the sole
   runtime database.
2. One DBOS workflow, one queue, one Pydantic AI agent, and one predeclared
   `model-0` effect may issue at most one OpenAI Responses call using exact
   `gpt-5.6-sol` at medium reasoning and explicit Standard service tier
   (`service_tier="default"`). Provider, SDK, application, and DBOS retries are
   zero. Tools, remote fetches, actions, fallback providers, streaming,
   background mode, and prior-response state are disabled.
3. Before secret resolution or dispatch, the effect binds the canonical
   admitted payload and disclosure acknowledgement; request, schema, model,
   service tier and release digests; rights; destination; project/service-
   account/key identity; credential generation and approved key-byte SHA-256;
   token, USD, queue, wall and call ceilings; retry owner; data terms; and
   current release evidence. Unknown, changed, expired, mismatched, or over-
   budget fields fail closed before client construction.
4. The provider edge adopts pinned official `openai==2.45.0` `AsyncOpenAI`
   behind `InferencePort`. Every ambient `OPENAI_*` setting is rejected before
   credential access or client construction; proxy inheritance, redirects,
   and SDK retries are disabled; approved project, Standard service tier, and
   wire headers are explicit. Returned service tier must be exact; absent or
   different tier becomes sticky `unknown` before a Standard-price audit.
   Only authenticated HTTP 400, 401, 403, 404, and 422 prove terminal rejection.
   HTTP 408, 409, 429, 5xx, and unclassified statuses are sticky `unknown`.
5. Provider, parser, credential/private-file, client-response, admitted-payload,
   and replay failures are sanitized. At public adapter, inference, model-step,
   and workflow boundaries, only expected domain exceptions are caught; safe
   type/message/audit fields are copied; sensitive scopes and arguments are
   released; and a fresh exception is raised with no cause or context. Raw
   sensitive bytes must not remain reachable through messages, attributes,
   exception chains, traceback frames, or capture-locals formatting.
6. Completed responses require provider request/response identity, exact model
   and service-tier agreement, strict non-boolean usage fields, total and
   cached/reasoning subset consistency, exact conservative price-bound cost on
   initial response and replay, typed schema/citation validation, and immutable
   citation-resolved result/provider-audit binding. Initial and replay responses
   return that audit.
7. One idempotent persistence proof covers exact `reconciled` and `failed`
   outcomes. Lost acknowledgement is accepted only after exact state, result,
   audit, and hold-reason readback. Every unproved transport, cleanup, or
   durable-commit outcome becomes sticky `unknown`; replay never constructs the
   provider adapter.
8. Static PEP 621 project metadata is the sole authoritative `0.3.0` source;
   runtime, API, and DBOS resolve the installed distribution identity through
   standard-library package metadata. Pydantic Evals genuinely awaits the async path.
9. The release image must be wheel-only, digest-pinned, non-root, read-only,
   capability-dropped, resource-bounded, and restricted to the allowlisted
   provider destination. Source tests do not substitute for release receipts.
10. Dispatch and release remain held until current independent evidence exists
    for account/project/service-account/key generation and revocation; rights;
    retention/region; rate/spend and egress; exact SBOM, vulnerability,
    provenance, signature and approval; dependency health/drain; and isolated
    rollback. Deployed `0.2.10` is historical, not a rollback target.
11. Conflicting historical claims and all C1/C2/R1/R2/R3/R4/R5/R6/R7/R8
    receipts are superseded, never rewritten. Historical reviewer outputs prove
    only their immutable rounds and are not approval for R9.
12. After foundation `PASS` and every independent release gate closes, Crawl
    first serves approved Hammock and PEECH public-or-synthetic value lanes.
    The next proposed Walk remains three proposal-only families with no send or
    effect path and is not activated by this review.
13. Glupta/Hermes may directionally become a universal conversational and
    supervisory front door, never a universal data plane or execution authority.
    Personal lanes remain local-only, minimum-necessary, and separately gated.

## R8 outcome and separate R9 repair

R8 remains immutable at product `3bb568a2885132d584717cbed63f3cc08c99916e`,
control `52248283708cf2e489102c705e5775625f55cee6`, Blueprint
`de4d7e439d67b3823a2c8fbff88f99c6112ccc0f`, packet SHA-256
`96f25dada6013bec33a2ac9cc683be2dbe8b628ed096efd2adc94fa0fcaab37c`,
and 64-entry manifest SHA-256
`4e196fc0712814d0e05845cdb0ba45a27f3af2c8fe6538a701ca23da9d446995`.
Fresh native Codex `gpt-5.6-sol` maximum returned `RESTART_REQUIRED` with two
material blockers: the actual existing-effect reservation identity-conflict
path escaped as raw `RuntimeError` while retaining admitted-source traceback
locals; and `pyproject.toml` plus `__init__.py` independently declared
`0.3.0` rather than resolving package, runtime, API, and DBOS identity from one
source. The Codex-first gate correctly did not invoke Fable or Grok. The exact
R8 packet, manifest, prompt, schema, result, and terminal receipt are preserved
byte-for-byte in the R9 product history.

R9 is a separate bounded repair. It keeps the existing effect store and
sanitized workflow boundary. A narrow `EffectConflictError` identifies only a
valid existing effect bound to a different dispatch; the workflow boundary
converts it outside sensitive frames to a fresh fixed `BriefGenerationError`.
The regression executes the actual reservation transaction twice with synthetic
source bytes and proves capture-locals safety, zero adapter construction, and no
redispatch.

R9 also adopts native packaging identity instead of adding a generator,
dependency, framework, or second source. Static PEP 621 `pyproject.toml`
metadata remains the sole version authority used by the existing Hatch/wheel
build. Runtime, API, and DBOS resolve that installed distribution identity
through standard-library `importlib.metadata`; the duplicate runtime literal is
removed. Exact wheel metadata and release-boundary tests bind the relation.

Any substantiated residual production defect returns `RESTART_REQUIRED`; it is
not repaired inside this frozen audit.

## Build-versus-adopt disposition

- Adopt FastAPI/Pydantic, DBOS/PostgreSQL, Pydantic AI/Evals, official
  AsyncOpenAI Responses SDK, Python native exception semantics and
  `asyncio.timeout_at`, `uv`, OCI/Compose, supply-chain tools, and provider-
  native frontier CLIs.
- Keep custom only for irreducible secure intake, disclosure/rights admission,
  durable effect/budget/release/ambiguity semantics, citation/audit binding,
  and exact packet/hash/sealed-fan-in policy.
- Do not add another agent framework, provider gateway, scheduler, queue,
  worker, store, compatibility layer, exception framework, or review
  orchestrator. R9 is one narrow reservation-conflict type and boundary mapping, native
  package-metadata resolution, and regression proof.

## Deterministic evidence supplied

- Product `8fb16e1`: exact verification passed 108 pytest tests plus 131
  subtests with nine expected PostgreSQL skips, Ruff, offline lock check,
  offline no-sources sdist/wheel build with exact `0.3.0` wheel metadata,
  semantic production census `1500/1500`, scoped security review, and exact-tip
  full attestation. Implementation commit `49d9a72` changes only the conflict
  boundary, native version resolution, and their regressions; the final product
  commit adds only immutable R8 evidence.
- Control `b18cfd7`: three exact docs/test paths preserve R8's terminal result,
  identify R9 pending, and pass JSON, visuals, 59 focused tests, sync, and
  exact-tip smoke attestation.
- Blueprint `87bdb5aa`: three exact paths preserve R8's terminal result,
  identify R9 pending, update one deduplicated Task Spine row, and pass sync,
  source-key, diff, and exact-tip smoke checks.
- Live Compose remains healthy historical `0.2.10` with actions disabled, but
  is not the candidate, conforming release, or rollback target.
- No credential, provider call, spend, live mutation, deployment, public action,
  task drain, Walk/Hermes activation, or business effect occurred.

The stronger DBOS duplicate-admission/UUID-clock regression remains a separate
P2 Task Spine follow-up. It becomes a blocker only if primary evidence shows
the current implementation or proof is materially false or unsafe.

## Review protocol and hard stop

Codex is controller/integrator. It froze one exact candidate, assembled and
hashed one de-identified packet, ran mechanical preflight first, and permits no
in-audit production remediation. Any reviewed-byte change restarts the baseline.

Run fresh read-only Codex `gpt-5.6-sol` at maximum reasoning first as a hard
gate. Do not invoke Fable or Grok unless Codex finds zero substantiated material
blockers on this exact packet/hash. If Codex blocks, terminate
`RESTART_REQUIRED` with no peer spend.

Only after Codex clears, blind read-only Fable and Grok receive the identical
packet/hash: `claude-fable-5` maximum via `advisor_full` with only Opus 5 as
allowed fallback, and Grok 4.6 xhigh through the pinned full launcher. One
availability retry per route is permitted. Results remain sealed until fan-in.

All three agree only when all three completed reviews find zero substantiated
material blockers. This is not voting or forced consensus. Resolve facts from
primary evidence and preserve irreducible material disagreement as
`HOLD_MATERIAL_DISSENT`. Terminal states are `PASS`,
`HOLD_MATERIAL_DISSENT`, `HOLD_EVIDENCE`, `INCOMPLETE_REVIEW`, or
`RESTART_REQUIRED`.

## Required reviewer output

Return JSON matching the supplied schema:

1. `verdict`.
2. `material_blockers`, with evidence, defect class, and disposition.
3. `non_blocking_findings`.
4. `factual_corrections`.
5. `foundation_disposition`: action, cost, risk, rollback, dispatch held.
6. `confidence_and_uncertainty`.

`PASS` means zero substantiated material blockers on these exact bytes. It does
not approve deployment, provider dispatch, task drain, Walk, public activation,
Hermes expansion, or effects.

