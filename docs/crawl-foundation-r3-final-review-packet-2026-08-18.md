# Crawl foundation final-review packet — candidate R3

Review date: 2026-08-18

Controller: Codex

Status: final bounded candidate, frozen only after the companion source
manifest and external packet digest are written. This packet grants no
deployment, provider dispatch, credential access or creation, spend, task
drain, Walk, public, Hermes, tool, action, outbound, signing, trading,
transfer, or money-movement authority.

## Review question

Does the reconciled Crawl foundation have zero substantiated material blockers
as an honest dispatch-held candidate, while preserving every open release
gate? Determine whether to keep, repair, partially rebuild, or fully rebuild it
before any Walk proposal. Cite primary evidence for every material blocker and
name the smallest safe disposition. Do not weaken a normative requirement to
match code.

## Exact candidate tuple

- Product: `cf4cd2ce0867244774a56324fdd20cbd2a606273`, based on
  `cccceaccc205bd173950b2ffdb0e819b81c658fc` (one protected squash commit).
- Control documents: `e32792bd552b7542f09208dbfe077fd689125d4c`, based on
  `a3e4c3e775e7f9243d4bdf14adb5ee6e0e0dd2f1` (one linear commit).
- Blueprint and operating state: `8223c73c60c66deb3ed97e0889b46ed7c8d3f488`, based on
  `82a650ac32000b56bbf031a76348e29a5c2e1c96` (one linear commit).

The normative identity is the ordered tuple above, the exact packet SHA-256,
and the exact companion source-manifest SHA-256. The Task Spine row is durable
administrative state, not evidence that a requirement passed.

## Frozen contract

1. Crawl is one authenticated loopback, source-grounded, read-only `OBSERVE`
   workflow over one to twenty explicitly selected local Markdown/text files.
   It returns a typed evidence brief with exact file-and-line citations,
   uncertainties, and next decisions. FastAPI is admission/health only;
   PostgreSQL is the sole runtime database.
2. One DBOS workflow, one queue, one Pydantic AI agent, and one predeclared
   `model-0` effect may issue at most one OpenAI Responses call using the exact
   `gpt-5.6-sol` snapshot/profile at **medium** reasoning. Provider, SDK,
   application, and DBOS retries are zero. Tools, remote fetches, actions,
   fallback providers, streaming, background mode, and prior-response state
   are disabled.
3. Before any secret resolution or dispatch, the durable effect binds the
   exact request/body/schema/model/release digests; disclosure acknowledgment;
   rights/evidence; provider destination; dedicated project service-account
   and key identity/generation; input/output/reasoning-token, conservative USD,
   queue, wall, and call ceilings; retry owner; data-use/retention/region; and
   current release evidence. Unknown, absent, changed, expired, or over-budget
   fields fail closed.
4. The provider edge adopts the official `AsyncOpenAI` Responses SDK behind
   the provider-neutral `InferencePort`. It disables ambient proxy inheritance.
   Complete authenticated provider rejection is terminal `failed`, sanitized
   without exception-cause leakage, unless transport cleanup exceeds the same
   absolute monotonic deadline, in which case the combined outcome is sticky
   `unknown`. Timeout, EOF, uncertain acceptance/usage, cleanup ambiguity, or
   uncertain durable commit after dispatch suppresses output and never
   redispatches.
5. Completed responses require provider request/response identity, exact
   returned-model agreement, internally consistent complete usage, a
   conservative price-bound USD upper bound, typed schema/citation validation,
   and immutable cross-binding of the citation-resolved result and provider
   audit. The initial API response and replay return the recorded audit.
6. One idempotent post-dispatch persistence proof covers both exact
   `reconciled` and exact `failed` outcomes. Acknowledgement loss is accepted
   only after exact state/result/audit/hold-reason readback. If a purported
   terminal `failed` write cannot be proved exact, the real PostgreSQL effect
   store permits its fail-closed transition to sticky `unknown`. Pre-commit,
   mismatched, tampered, unreadable, or unholdable outcomes become redacted
   sticky `unknown`; replay never constructs the provider adapter.
7. Runtime, package metadata, API, and DBOS application identity resolve from
   the same `0.3.0` version source. The documented Pydantic Evals task genuinely
   awaits the async inference path and is executable end to end.
8. The release image is wheel-only, digest-pinned, non-root, read-only,
   capability-dropped, resource-bounded, and restricted to the allowlisted
   provider destination. These are requirements; local source/test claims do
   not substitute for exact release receipts.
9. Live dispatch and release remain held until current independent evidence
   exists for the dedicated account/project/service-account/key generation and
   revocation; source rights; provider data-use/retention/region; rate/spend and
   allowlisted egress; exact manifest/SBOM/OS-vulnerability/provenance/signature/
   approval; dependency health/drain; and isolated rollback. The deployed
   consumer route is historical evidence, not a conforming rollback target.
10. Conflicting historical Stage-0 claims and all C1/C2/R1/R2 receipts are
    superseded, never rewritten. Historical reviewer outputs are not normative
    evidence for R3 and are intentionally excluded from review closure.
11. After a `PASS` and every adapter/budget/provenance/rollback/release gate
    closes, Crawl first serves two value lanes: Hammock source-grounded
    architecture/GTM/decision briefs, and PEECH public-or-synthetic discovery/
    decision-product briefs. Existing project controllers continue
    independently. PEECH private/customer material remains separately rights/
    boundary/owner gated.
12. The next proposed Walk is limited to three proposal-only families:
    current-state/blocker synthesis; decision/spec/deliverable preparation; and
    evidence/quality review. It has no send/effect path. Only after Walk is
    earned may the first Run proposal create verified code/document candidates
    in isolated worktrees; merge, publication, deployment, and outbound remain
    separate gates.
13. Directionally, Glupta/Hermes may become a universal conversational and
    supervisory front door, never a universal data plane or execution
    authority. Personal lanes remain local-only, domain-specific,
    minimum-necessary, and separately gated; finance credentials/signing/
    submission/money movement and all Personal Health records remain outside
    shared Glupta authority/state.

## R2 outcome and separate remediation closure

R2 remains immutable at product `ea20b5e2a44a5cf2178eca63d20f94e6f3e88883`,
control `b86dc04dd6cb9b3a7d6a14ef14bd5d01b06c6a3e`, Blueprint
`9f889d252242c2a0c86563701c0de6bd68f7475a`, packet SHA-256
`0548e7015c46f2a02d86b12f2cb2106d9a07b75bc77392b6f476a1fa0522a527`.
Its controller state was `RESTART_REQUIRED`; the Codex-first gate correctly did
not invoke Fable or Grok. R3 carries no R2 reviewer approval forward.

The separate protected implementation loop at product `cf4cd2c` claims closure
only through primary source and adversarial tests for R2's three blockers:

1. the real effect store now permits an ambiguously committed terminal
   `failed` row to transition to sticky `unknown`, with real PostgreSQL
   commit/readback/replay coverage;
2. authenticated provider rejection followed by cleanup-deadline expiry is
   sticky ambiguity rather than definitive failure, with the combined path
   covered; and
3. the Pydantic Evals runner now awaits the asynchronous task and a synthetic
   end-to-end evaluation proves the public runner path executes.

No dependency, framework, provider call, deployment, credential, spend, or
authority surface was added. Any substantiated residual production defect
returns `RESTART_REQUIRED`; it is not repaired inside this frozen audit.

## Build-versus-adopt disposition

The touched Glupta stack was rechecked before freezing R3:

- Adopt FastAPI/Pydantic for admission and schemas; DBOS/PostgreSQL for durable
  workflow/concurrency; Pydantic AI/Evals for the typed one-agent/eval path;
  official AsyncOpenAI Responses SDK for provider transport; Python
  `asyncio.timeout_at` for absolute cancellation; `uv`, OCI, and Compose for
  packaging/operation; standard CycloneDX/SPDX, Syft/Grype, ORT/ScanCode, and
  Cosign/SLSA for release evidence; and provider-native Codex, Claude, and
  pinned Grok CLIs for frontier review.
- Keep custom only where those maintained primitives do not supply the frozen
  contract: secure local intake; disclosure/rights admission; durable effect,
  budget, release, and sticky-ambiguity semantics; citation/audit binding; and
  exact packet hashing, native-route policy, and sealed fan-in.
- Do not add an agent framework, model gateway, scheduler, queue, worker,
  store, compatibility layer, or review orchestrator when adopted primitives
  already satisfy the contract. Any future custom code must name and test the
  irreducible missing contract. Reassess the current market; sunk cost is not
  justification.
- The R2 repair deliberately reused existing DBOS, PostgreSQL, asyncio,
  Pydantic Evals, and test primitives. It is the smallest complete change, not
  a new abstraction.

## Deterministic evidence supplied

- Product `cf4cd2c`: its exact synced pre-squash tree passed 81 pytest tests
  plus 111 subtests, including real loopback PostgreSQL effect persistence and
  replay, Ruff, frozen lock, offline wheel/sdist build with matching hashes,
  package metadata `0.3.0`, semantic production census `1500/1500`, diff
  checks, and scoped security review. The protected squash merge changed only
  commit identity, not candidate tree bytes.
- Control `e32792b`: exact candidate identity, immutable R2 outcome, post-R2
  remediation claims, held live-state boundary, traceability, visual/schema
  checks, and 59 focused tests; no production-runtime change.
- Blueprint `8223c73c`: exact candidate wording, immutable R2 outcome, durable
  value sequence, one deduplicated R3-pending Task Spine row, three-path diff
  closure, and no canonical-vault write.
- Live Compose remains healthy historical `0.2.10` with actions disabled, but
  it is not the candidate or a conforming release/rollback: it runs as host UID
  `501:20`, without read-only root, capability drop, or resource caps, with a
  writable consumer-auth mount and historical image digest. This accurately
  held state is not evidence of R3 deployment.
- No credential contents, provider call, spend, live mutation, deployment,
  public action, task drain, Walk/Hermes activation, or business effect
  occurred.

The DBOS queue-admission implementation captures an aware server UTC timestamp
as a workflow argument; DBOS 2.29 preserves first-recorded inputs on duplicate
workflow identity and uses them on recovery. A stronger real PostgreSQL
duplicate-admission/UUID-clock regression remains a separate P2 follow-up. It
does not change the current contract or authorize dispatch. Promote it to a
blocker only if primary evidence shows the present implementation or proof is
materially false or unsafe.

## Review protocol and hard stop

Codex is controller/integrator. It froze the charter and exact path/requirement
closure, assembled and hashed one de-identified packet, runs deterministic
mechanical preflight first, reconciles findings from primary evidence, permits
at most one bounded remediation pass over at most two candidate hashes, and
owns durable closeout. Production-code remediation is a separate implementation
loop and restarts the frozen baseline.

Run fresh read-only Codex `gpt-5.6-sol` at maximum reasoning first as a hard
gate. Do not invoke Fable or Grok unless Codex finds zero substantiated material
blockers on this exact packet/hash. If Codex blocks, terminate
`RESTART_REQUIRED`; no peer spend or in-audit production repair is allowed.

Only after Codex clears, blind read-only Fable and Grok receive this identical
packet/hash: `claude-fable-5` maximum via `advisor_full` with only the allowed
native Opus 5 fallback, and Grok 4.6 `xhigh` through the pinned full launcher.
One availability retry per route is permitted. Results remain sealed until
fan-in. Across an initial and, only if amended, final round, the protocol caps
planned model reviews at six.

“All three agree” means all three completed reviews find zero substantiated
material blockers. It is not voting or verbal unanimity. Resolve factual
disputes from primary evidence; preserve irreducible material disagreement as
`HOLD_MATERIAL_DISSENT`. Terminal states are `PASS`,
`HOLD_MATERIAL_DISSENT`, `HOLD_EVIDENCE`, `INCOMPLETE_REVIEW`, or
`RESTART_REQUIRED`.

## Required reviewer output

Return exactly:

1. `VERDICT`: one terminal state above.
2. `MATERIAL_BLOCKERS`: every substantiated blocker with exact primary
   evidence, defect class, and smallest safe disposition; write `none` for
   zero.
3. `NON_BLOCKING_FINDINGS`.
4. `FACTUAL_CORRECTIONS`.
5. `FOUNDATION_DISPOSITION`: keep, repair, partial rebuild, or full rebuild,
   including cost, risk, rollback, and whether dispatch remains held.
6. `CONFIDENCE_AND_UNCERTAINTY`.

`PASS` means zero substantiated material blockers on these exact bytes. It does
not approve deployment, provider dispatch, task draining, Walk, public
activation, Hermes expansion, or effects.
