# Crawl foundation final-review packet — candidate R5

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

- Product: `67f1b418ce308091b2dd7476bda32ede8df957c0`, based on
  `15a1603ebc772140c1e88828bcd685f2d495cfff`.
- Control documents: `4b8c468b871918d9113770a04fe3993d09040dbf`, based on
  `60d3f4fd002a9fdd746a115f6cde9080bf4f0c38`.
- Blueprint and operating state: `6104558f4e7885f27ad176339000c794c39ec5c8`,
  based on `261e30f1c91e456beb537b9470a3ee12385bed6e`.

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
   `gpt-5.6-sol` profile at medium reasoning. Provider, SDK, application, and
   DBOS retries are zero. Tools, remote fetches, actions, fallback providers,
   streaming, background mode, and prior-response state are disabled.
3. Before secret resolution or dispatch, the effect binds the exact canonical
   admitted payload and disclosure acknowledgement; request, schema, model and
   release digests; rights; destination; project/service-account/key identity;
   credential generation and the approved SHA-256 of the canonical mounted key
   bytes; token, USD, queue, wall and call ceilings; retry owner; data terms;
   and current release evidence. Unknown, changed, expired, mismatched, or
   over-budget fields fail closed before client construction.
4. The provider edge adopts pinned official `openai==2.45.0` `AsyncOpenAI`
   behind `InferencePort`. Every ambient `OPENAI_*` setting is rejected before
   credential access or client construction; proxy inheritance, redirects, and
   SDK retries are disabled; approved project and wire headers are explicit.
   Only authenticated HTTP 400, 401, 403, 404, and 422 prove terminal
   rejection. HTTP 408, 409, 429, 5xx, and every unclassified status leave
   acceptance, execution, usage, or charge unproved and become sticky
   `unknown`. Transport, timeout, EOF, cleanup, and post-dispatch durable-commit
   ambiguity also become sticky `unknown`; replay cannot redispatch.
5. Provider, output/parser, credential/private-file, client-response,
   admitted-payload, and durable-replay failures are sanitized without raw
   sensitive bytes in messages, causes, attributes, contexts, or tracebacks. A
   terminal status followed by cleanup ambiguity is still `unknown`, not
   `failed`.
6. Completed responses require provider request/response identity, exact model
   agreement, strict non-boolean usage fields, total and cached/reasoning subset
   consistency, exact conservative price-bound cost on initial response and
   replay, typed schema/citation validation, and immutable binding of the
   citation-resolved result and provider audit. Initial response and replay
   return that audit.
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
11. Conflicting historical claims and all C1/C2/R1/R2/R3/R4 receipts are
    superseded, never rewritten. Historical reviewer outputs are not normative
    evidence for R5 and carry no approval forward.
12. After a foundation `PASS` and every independent release gate closes, Crawl
    first serves the approved Hammock and PEECH public-or-synthetic value lanes.
    The next proposed Walk remains three proposal-only families with no send or
    effect path. It is not activated by this review.
13. Glupta/Hermes may directionally become a universal conversational and
    supervisory front door, never a universal data plane or execution
    authority. Personal lanes remain local-only, minimum-necessary, and
    separately gated.

## R4 outcome and separate R5 repair

R4 remains immutable at product `8efd3cc1907a2887a6e6c3822b70e1fe0b350ade`,
control `cfed13c41fe2ae5affb21f12537b5b6ad9eb3e35`, Blueprint
`b80838e8c4d2fbba4aa472e051fc440d4254d904`, packet SHA-256
`a82235751f7a60cd29cce07252b8e89ee202b5fb8f7c2f5a249ac60330083a78`,
and manifest SHA-256
`c8293db7d7cb23b9bd1872f1dcfd311fad8ec0ace47795aa4a769cee453d49ba`.
Fresh Codex maximum returned `RESTART_REQUIRED` with four material blockers:
ambient SDK configuration could override credential/project identity; sensitive
provider and credential causes remained attached; reasoning-token subset/cost
integrity was not enforced; and disclosure acknowledgement was not bound at the
effect/eval boundary. The Codex-first gate correctly did not invoke Fable or
Grok.

R5 is a separate bounded product repair. It retains the official SDK and
existing DBOS effect architecture. It rejects every ambient `OPENAI_*` key
before credential access or client construction, explicitly binds project and
wire headers, sanitizes every sensitive exception boundary, strictly validates
usage subsets and exact conservative cost on initial and replay paths, and
rebinds the canonical disclosure acknowledgement before reserve, adapter,
credential, and eval dispatch. The release profile additionally binds the
SHA-256 of the canonical mounted key bytes to the approved key identity and
credential generation; the exact bytes used by the SDK are verified with a
constant-time comparison before client construction. Tests cover hostile
ambient settings, wrong-but-valid mode-0600 key bytes, cause/context/attribute/
traceback redaction, usage adversaries, effect/replay tampering, and disclosure
drift. No dependency, framework, provider call, credential access, deployment,
spend, retry, or authority was added.

Any substantiated residual production defect returns `RESTART_REQUIRED`; it is
not repaired inside this frozen audit.

## Build-versus-adopt disposition

- Adopt FastAPI/Pydantic, DBOS/PostgreSQL, Pydantic AI/Evals, official
  AsyncOpenAI Responses SDK, Python `asyncio.timeout_at`, `uv`, OCI/Compose,
  standard supply-chain tools, and provider-native frontier CLIs.
- Keep custom only for irreducible secure intake, disclosure/rights admission,
  durable effect/budget/release/ambiguity semantics, citation/audit binding,
  and exact packet/hash/sealed-fan-in policy.
- Do not add another agent framework, provider gateway, scheduler, queue,
  worker, store, compatibility layer, or review orchestrator. R5 is local
  boundary validation and tests, not a new abstraction.

## Deterministic evidence supplied

- Product `67f1b418`: exact-tip full verification passed 99 pytest tests plus
  129 subtests with nine expected PostgreSQL skips. A separate exact-tip
  disposable loopback PostgreSQL 17.6 run passed 108 tests plus 129 subtests.
  Ruff, offline lock, offline no-sources sdist/wheel build, semantic production
  census `1500/1500`, diff checks, and scoped security review passed.
- Control `4b8c468`: three exact docs/test paths; focused tests pass 59/59,
  JSON and schema validation, generated-visual checks, diff checks, sync, and
  exact-tip smoke attestation pass. It preserves R4 and records R5 pending.
- Blueprint `6104558`: three exact paths; it preserves R4, records R5 pending,
  updates one deduplicated Task Spine row, and passes sync, exact source-key,
  diff, and exact-tip smoke checks.
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
