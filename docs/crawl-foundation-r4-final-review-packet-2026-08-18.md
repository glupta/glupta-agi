# Crawl foundation final-review packet — candidate R4

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

- Product: `8efd3cc1907a2887a6e6c3822b70e1fe0b350ade`, based on
  `a70e46a14132dbf3927e1f33941059203ba09aa3`.
- Control documents: `cfed13c41fe2ae5affb21f12537b5b6ad9eb3e35`, based on
  `9c0949c122d598521b4f285d80b33f0220f20d06`.
- Blueprint and operating state: `b80838e8c4d2fbba4aa472e051fc440d4254d904`,
  based on `9c7c43e78d38f78f4b2ef2621f9fd403d1c6d1d2`.

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
3. Before secret resolution or dispatch, the effect binds the exact request,
   schema, model and release digests; disclosure acknowledgement; rights;
   destination and credential identity/generation; token, USD, queue, wall and
   call ceilings; retry owner; data terms; and current release evidence.
   Unknown, changed, expired, or over-budget fields fail closed.
4. The provider edge adopts pinned official `openai==2.45.0` `AsyncOpenAI`
   behind `InferencePort`, with ambient proxy inheritance and SDK retries
   disabled. Only authenticated HTTP 400, 401, 403, 404, and 422 prove terminal
   rejection. HTTP 408, 409, 429, 5xx, and every unclassified status leave
   acceptance, execution, usage, or charge unproved and become sticky
   `unknown`. Transport, timeout, EOF, cleanup, and post-dispatch durable-commit
   ambiguity also become sticky `unknown`; replay cannot redispatch.
5. Provider errors are sanitized without raw response bodies in messages,
   causes, or tracebacks. A terminal status followed by cleanup ambiguity is
   still `unknown`, not `failed`.
6. Completed responses require provider request/response identity, exact model
   agreement, complete consistent usage, conservative price-bound cost, typed
   schema/citation validation, and immutable binding of the citation-resolved
   result and provider audit. Initial response and replay return that audit.
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
11. Conflicting historical claims and all C1/C2/R1/R2/R3 receipts are
    superseded, never rewritten. Historical reviewer outputs are not normative
    evidence for R4 and carry no approval forward.
12. After a foundation `PASS` and every independent release gate closes, Crawl
    first serves the approved Hammock and PEECH public-or-synthetic value lanes.
    The next proposed Walk remains three proposal-only families with no send or
    effect path. It is not activated by this review.
13. Glupta/Hermes may directionally become a universal conversational and
    supervisory front door, never a universal data plane or execution
    authority. Personal lanes remain local-only, minimum-necessary, and
    separately gated.

## R3 outcome and separate R4 repair

R3 remains immutable at product `cf4cd2ce0867244774a56324fdd20cbd2a606273`,
control `e32792bd552b7542f09208dbfe077fd689125d4c`, Blueprint
`8223c73c60c66deb3ed97e0889b46ed7c8d3f488`, packet SHA-256
`73b66f2033cc8c6e72d4dc05b79e9a13f5d2a3556d2c7dceeb49e7677968b798`.
Fresh Codex maximum returned `RESTART_REQUIRED` because every
`APIStatusError`, including 408 and 5xx, was treated as definitive `failed`.
The Codex-first gate correctly did not invoke Fable or Grok.

R4 is a separate five-file product change. It retains the official SDK and
existing state machine, reads `APIStatusError.status_code`, permits terminal
classification only for 400/401/403/404/422, and routes retryable or
unclassified statuses to the existing sticky-unknown path. Adapter, workflow,
and real PostgreSQL tests cover terminal statuses, 408/409/429/5xx and an
unclassified status, cleanup ambiguity, sanitization, single transport
invocation, and replay without adapter construction. No dependency, framework,
provider call, credential, deployment, spend, or authority was added.

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
  worker, store, compatibility layer, or review orchestrator. R4 is a local
  status predicate and tests, not a new abstraction.

## Deterministic evidence supplied

- Product `8efd3cc`: full exact-tip `wt verify` passed 95 pytest tests plus 111
  subtests on disposable loopback PostgreSQL 17.11, Ruff, and offline lock.
  Separate exact-tip gates passed offline no-sources wheel/sdist build with
  metadata `0.3.0`, release-boundary tests, semantic production census
  `1500/1500`, diff checks, and scoped security review.
- Control `cfed13c`: three exact docs/test paths; focused tests pass 3/3 and JSON
  validation/diff checks pass. It preserves R3 and records R4 review-pending.
- Blueprint `b80838e`: three exact paths; it preserves R3, records R4 pending,
  updates one deduplicated Task Spine row, and passes diff checks.
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
