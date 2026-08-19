# Crawl foundation final-review packet — candidate R6

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

- Product: `78a3d5a745113a87a7bb862c0498a218b66abc9a`, based on the
  rejected R5 product `67f1b418ce308091b2dd7476bda32ede8df957c0`.
- Control documents: `aa9253f3dd1ae32c4b80acc3a2768756165246d7`, based on the
  rejected R5 control identity `4b8c468b871918d9113770a04fe3993d09040dbf`.
- Blueprint and operating state: `efb212b1b2f657c0e915b7ff8a0577faa8489103`,
  based on the rejected R5 Blueprint identity
  `6104558f4e7885f27ad176339000c794c39ec5c8`.

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
   `model-0` effect may issue at most one OpenAI Responses call using the exact
   `gpt-5.6-sol` profile at medium reasoning and explicit Standard service tier
   (`service_tier="default"`). Provider, SDK, application, and DBOS retries are
   zero. Tools, remote fetches, actions, fallback providers, streaming,
   background mode, and prior-response state are disabled.
3. Before secret resolution or dispatch, the effect binds the exact canonical
   admitted payload and disclosure acknowledgement; request, schema, model,
   service tier and release digests; rights; destination;
   project/service-account/key identity; credential generation and the
   approved SHA-256 of the canonical mounted key bytes; token, USD, queue, wall
   and call ceilings; retry owner; data terms; and current release evidence.
   Unknown, changed, expired, mismatched, or over-budget fields fail closed
   before client construction.
4. The provider edge adopts pinned official `openai==2.45.0` `AsyncOpenAI`
   behind `InferencePort`. Every ambient `OPENAI_*` setting is rejected before
   credential access or client construction; proxy inheritance, redirects,
   and SDK retries are disabled; approved project, Standard service tier, and
   wire headers are explicit. The returned response must attest the exact
   expected service tier; an absent or different tier becomes sticky `unknown`
   before a Standard-price audit can be constructed. Only authenticated HTTP
   400, 401, 403, 404, and 422 prove terminal rejection. HTTP 408, 409, 429,
   5xx, and every unclassified status leave acceptance, execution, usage, or
   charge unproved and become sticky `unknown`. Transport, timeout, EOF,
   cleanup, and post-dispatch durable-commit ambiguity also become sticky
   `unknown`; replay cannot redispatch.
5. Provider, output/parser, credential/private-file, client-response,
   admitted-payload, and durable-replay failures are sanitized without raw
   sensitive bytes in messages, causes, attributes, contexts, or tracebacks. A
   terminal status followed by cleanup ambiguity is still `unknown`, not
   `failed`.
6. Completed responses require provider request/response identity, exact model
   and service-tier agreement, strict non-boolean usage fields, total and
   cached/reasoning subset consistency, exact conservative price-bound cost on
   initial response and replay, typed schema/citation validation, and immutable
   binding of the citation-resolved result and provider audit. Initial response
   and replay return that audit.
7. One idempotent persistence proof covers exact `reconciled` and `failed`
   outcomes. Lost acknowledgement is accepted only after exact state, result,
   audit, and hold-reason readback. Every unproved outcome becomes sticky
   `unknown`; replay never constructs the provider adapter.
8. Runtime, package metadata, API, and DBOS application identity resolve from
   the same `0.3.0` source. Pydantic Evals genuinely awaits the async path.
9. The release image must be wheel-only, digest-pinned, non-root, read-only,
   capability-dropped, resource-bounded, and restricted to the allowlisted
   provider destination. Source tests do not substitute for release receipts.
10. Dispatch and release remain held until current independent evidence exists
    for account/project/service-account/key generation and revocation; rights;
    retention/region; rate/spend and egress; exact SBOM, vulnerability,
    provenance, signature and approval; dependency health/drain; and isolated
    rollback. Deployed `0.2.10` is historical, not a rollback target.
11. Conflicting historical claims and all C1/C2/R1/R2/R3/R4/R5 receipts are
    superseded, never rewritten. Historical reviewer outputs are evidence of
    their own immutable rounds but are not approval for R6.
12. After a foundation `PASS` and every independent release gate closes, Crawl
    first serves the approved Hammock and PEECH public-or-synthetic value lanes.
    The next proposed Walk remains three proposal-only families with no send or
    effect path. It is not activated by this review.
13. Glupta/Hermes may directionally become a universal conversational and
    supervisory front door, never a universal data plane or execution
    authority. Personal lanes remain local-only, minimum-necessary, and
    separately gated.

## R5 outcome and separate R6 repair

R5 remains immutable at product `67f1b418ce308091b2dd7476bda32ede8df957c0`,
control `4b8c468b871918d9113770a04fe3993d09040dbf`, Blueprint
`6104558f4e7885f27ad176339000c794c39ec5c8`, packet SHA-256
`b7ff94a6970557a451b20d56465cb4debbd2e125b15e9f928b3f0a3a48da29bd`,
and manifest SHA-256
`8c4e0693f0543d6bdd892380cb4b49b2e206ffe906575942cb95231df259ed60`.
Fresh native Codex `gpt-5.6-sol` maximum returned `RESTART_REQUIRED` with one
material blocker: the Responses request omitted `service_tier`, inherited
mutable project `auto` behavior, and could select Fast or Priority pricing
above the frozen Standard USD reservation while recording the lower Standard
estimate. The Codex-first gate correctly did not invoke Fable or Grok.

R6 is a separate bounded repair. It uses the official SDK's native
`service_tier="default"` field, which selects Standard processing rather than
project-configured `auto`. The required literal is bound through the approved
release profile, frozen dispatch, request digest, exact SDK call, provider
audit, durable effect, and replay validation. A missing or non-`default`
returned tier is ambiguous and suppresses output rather than constructing a
false Standard-price audit. Tests cover unapproved profile and reserved
request values, hostile ambient tier settings, exact outgoing request,
missing/priority returned tiers, effect tampering, and recomputed replay-record
tampering. No dependency, provider framework, gateway, retry, provider call,
credential access, deployment, spend, or authority was added.

Any substantiated residual production defect returns `RESTART_REQUIRED`; it is
not repaired inside this frozen audit.

## Build-versus-adopt disposition

- Adopt FastAPI/Pydantic, DBOS/PostgreSQL, Pydantic AI/Evals, official
  AsyncOpenAI Responses SDK including its native service-tier field, Python
  `asyncio.timeout_at`, `uv`, OCI/Compose, standard supply-chain tools, and
  provider-native frontier CLIs.
- Keep custom only for irreducible secure intake, disclosure/rights admission,
  durable effect/budget/release/ambiguity semantics, citation/audit binding,
  and exact packet/hash/sealed-fan-in policy.
- Do not add another agent framework, provider gateway, scheduler, queue,
  worker, store, compatibility layer, or review orchestrator. R6 is one native
  request control plus domain binding and regression proof, not a new
  abstraction.

## Deterministic evidence supplied

- Product `78a3d5a`: the R6 implementation is commit `75943176` and the child
  commit adds only immutable R5 review evidence. Exact R6 canonical verification
  passed 103 pytest tests plus 131 subtests with nine expected PostgreSQL skips;
  the focused disposable loopback PostgreSQL 17.6 boundary passed 9 tests. Ruff,
  lock check, offline no-sources sdist/wheel build, semantic production census
  `1499/1500`, and diff checks passed.
- Control `aa9253f`: three exact docs/test paths preserve R5's terminal result
  and identify R6 pending. Focused tests pass 59/59; JSON, schema, generated
  visuals, diff checks, sync, and exact-tip smoke attestation pass.
- Blueprint `efb212b`: three exact paths preserve R5's terminal result, identify
  R6 pending, update one deduplicated Task Spine row, and pass sync, exact
  source-key, diff, and exact-tip smoke checks.
- Live Compose remains healthy historical `0.2.10` with actions disabled, but
  is not the candidate, conforming release, or rollback target.
- No credentials, provider call, spend, live mutation, deployment, public
  action, task drain, Walk/Hermes activation, or business effect occurred.

The stronger DBOS duplicate-admission/UUID-clock regression remains a separate
P2 follow-up. It becomes a blocker only if primary evidence shows the current
implementation or proof is materially false or unsafe.

## Review protocol and hard stop

Codex is controller/integrator. It froze one exact candidate, assembled and
hashed one de-identified packet, ran mechanical preflight first, and permits no
in-audit production remediation. Any reviewed-byte change restarts the baseline.

Run fresh read-only Codex `gpt-5.6-sol` at maximum reasoning first as a hard
gate. Do not invoke Fable or Grok unless Codex finds zero substantiated material
blockers on this exact packet/hash. If Codex blocks, terminate
`RESTART_REQUIRED` with no peer spend.

Only after Codex clears, blind read-only Fable and Grok receive the identical
packet/hash: `claude-fable-5` maximum via `advisor_full` with only Opus 5 as the
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
