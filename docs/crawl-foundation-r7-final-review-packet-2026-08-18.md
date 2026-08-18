# Crawl foundation final-review packet — candidate R7

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

- Product: `61f817ffbe8dcb08626e2ffc10eccf825e048312`, based on rejected R6
  product `78a3d5a745113a87a7bb862c0498a218b66abc9a`.
- Control documents: `fd7b60e18b9df8dbdd40f6d5452bcf2b0597a6ef`, based on
  rejected R6 control `aa9253f3dd1ae32c4b80acc3a2768756165246d7`.
- Blueprint and operating state: `2babe42ca1298c0a42dc5b14716bc221efe88d21`,
  based on rejected R6 Blueprint `efb212b1b2f657c0e915b7ff8a0577faa8489103`.

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
8. Runtime, package metadata, API, and DBOS application identity resolve from
   one `0.3.0` source. Pydantic Evals genuinely awaits the async path.
9. The release image must be wheel-only, digest-pinned, non-root, read-only,
   capability-dropped, resource-bounded, and restricted to the allowlisted
   provider destination. Source tests do not substitute for release receipts.
10. Dispatch and release remain held until current independent evidence exists
    for account/project/service-account/key generation and revocation; rights;
    retention/region; rate/spend and egress; exact SBOM, vulnerability,
    provenance, signature and approval; dependency health/drain; and isolated
    rollback. Deployed `0.2.10` is historical, not a rollback target.
11. Conflicting historical claims and all C1/C2/R1/R2/R3/R4/R5/R6 receipts are
    superseded, never rewritten. Historical reviewer outputs prove only their
    immutable rounds and are not approval for R7.
12. After foundation `PASS` and every independent release gate closes, Crawl
    first serves approved Hammock and PEECH public-or-synthetic value lanes.
    The next proposed Walk remains three proposal-only families with no send or
    effect path and is not activated by this review.
13. Glupta/Hermes may directionally become a universal conversational and
    supervisory front door, never a universal data plane or execution authority.
    Personal lanes remain local-only, minimum-necessary, and separately gated.

## R6 outcome and separate R7 repair

R6 remains immutable at product `78a3d5a745113a87a7bb862c0498a218b66abc9a`,
control `aa9253f3dd1ae32c4b80acc3a2768756165246d7`, Blueprint
`efb212b1b2f657c0e915b7ff8a0577faa8489103`, packet SHA-256
`0ced17806e30d1bc2b176cc1976b5bf8f224a19cf97573cbfa46c156b4482f8d`,
and 52-entry manifest SHA-256
`5b7dc874ffb77b46c3fc286af874908173fa8915d19bd111892fa42c858e5c85`.
Fresh native Codex `gpt-5.6-sol` maximum returned `RESTART_REQUIRED` with two
material blockers: sensitive key and admitted-source bytes remained reachable
through traceback frame locals/context chains, and two Blueprint opening
current-state statements still named rejected R4 while later sections named R6.
The Codex-first gate correctly did not invoke Fable or Grok.

R7 is a separate bounded repair. It uses Python native exception semantics and
the existing official SDK/ports architecture rather than a new wrapper,
framework, dependency, or provider layer. Synthetic capture-locals/context
regressions inject marked provider body, key, client state, and admitted source
bytes and prove none escapes the public exception boundaries. Sticky `unknown`,
terminal `failed`, and replay no-redispatch behavior remain covered. The two
Blueprint opening statements now name the exact current R7 candidate while R6
is preserved as immutable rejected evidence.

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
  orchestrator. R7 is a boundary refactor plus regression proof.

## Deterministic evidence supplied

- Product `61f817ff`: exact verification passed 105 pytest tests plus 131
  subtests with nine expected PostgreSQL skips, Ruff, offline lock check,
  offline no-sources sdist/wheel build, semantic production census `1498/1500`,
  scoped security review, and diff checks. Exact-tip full attestation passed.
- Control `fd7b60e`: three exact docs/test paths preserve R6's terminal result
  and identify R7 pending. JSON, schema, visuals, 59 focused tests, diff, sync,
  and exact-tip smoke attestation passed.
- Blueprint `2babe42c`: three exact paths preserve R6's terminal result, identify
  R7 pending, update one deduplicated Task Spine row, and pass sync, source-key,
  diff, and exact-tip smoke checks.
- A delegated post-sync audit proved the four R7 repair blobs and all six R6
  evidence files byte-identical, with no upstream overlap.
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
