# Crawl foundation restarted final-review packet — candidate R1

Review date: 2026-08-18

Controller: Codex

Status: frozen only after the companion source manifest and external packet
digest are written. This packet grants no deployment, provider dispatch,
credential access or creation, spend, task drain, Walk, public, Hermes, tool,
action, outbound, signing, trading, transfer, or money-movement authority.

## Review question

Does the reconciled Crawl foundation have zero substantiated material blockers
as an honest dispatch-held candidate, while preserving every open release gate?
Determine whether to keep, repair, partially rebuild, or fully rebuild it before
any Walk proposal. Cite primary evidence for every material blocker and name the
smallest safe disposition. Do not weaken a normative requirement to match code.

## Exact candidate tuple

- Product: `fc2dcac4d5d093168b527a424aefcc3be22d1eb7`, parent
  `1296e0cfa4d81da3db084aabdc8584308ddf3e2f`.
- Control documents: tip `c42394e0ffc96c5baf402627b614b7fb7ca50c9b`,
  based on `a98d4199141f8e0209161aa37c4b1cb8981ec983` (two linear commits).
- Blueprint: `95fe95b40eba3f5724ec12bf02aa0ae847f28884`, parent
  `0225d7e34fc7f9e837e80c823dbba5de6d6a8f99`.

The normative identity is the ordered tuple above, the exact packet SHA-256,
and the exact companion source-manifest SHA-256. Operational Task Spine state
and later review receipts are excluded from candidate identity.

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
   fallback providers, streaming, background mode, and prior-response state are
   disabled.
3. Before any secret resolution or dispatch, the durable effect binds the exact
   request/body/schema/model/release digests; disclosure acknowledgment;
   rights/evidence; provider destination; dedicated project service-account and
   key identity/generation; input/output/reasoning-token, conservative USD,
   queue, wall, and call ceilings; retry owner; data-use/retention/region; and
   current release evidence. Unknown, absent, changed, expired, or over-budget
   fields fail closed.
4. The provider edge adopts the official `AsyncOpenAI` Responses SDK behind the
   provider-neutral `InferencePort`. Complete authenticated provider rejection
   is terminal `failed`, sanitized without exception-cause leakage, and never
   retried. One absolute monotonic deadline covers transport and client cleanup.
   Timeout, EOF, uncertain acceptance/usage, or uncertain durable commit after
   dispatch becomes sticky `unknown`, suppresses output, and never redispatches.
5. Completed responses require provider request/response identity, exact
   returned-model agreement, internally consistent complete usage, a
   conservative price-bound USD upper bound, typed schema/citation validation,
   and immutable cross-binding of the citation-resolved result and provider
   audit. Replay returns the recorded result/audit and rejects either-side
   tampering.
6. The release image is wheel-only, digest-pinned, non-root, read-only,
   capability-dropped, resource-bounded, and restricted to the allowlisted
   provider destination. These are requirements; local source/test claims do
   not substitute for the exact release receipts below.
7. Live dispatch and release remain held until current independent evidence
   exists for the dedicated account/project/service-account/key generation and
   revocation; source rights; provider data-use/retention/region; rate/spend and
   allowlisted egress; exact manifest/SBOM/OS-vulnerability/provenance/signature/
   approval; dependency health/drain; and isolated rollback. The deployed
   consumer route is historical evidence, not a conforming rollback target.
8. Conflicting historical Stage-0 claims and receipts are superseded, never
   rewritten. Historical reviewer outputs are not normative evidence for R1 and
   are intentionally excluded from this packet's review closure.
9. After a PASS and every adapter/budget/provenance/rollback/release gate closes,
   Crawl first serves two value lanes: Hammock source-grounded architecture/GTM/
   decision briefs, and PEECH public-or-synthetic discovery/decision-product
   briefs. Existing project controllers continue independently. PEECH private or
   customer material remains separately rights/boundary/owner gated.
10. The next proposed Walk is limited to three proposal-only families:
    current-state/blocker synthesis; decision/spec/deliverable preparation; and
    evidence/quality review. It has no send/effect path. Only after Walk is
    earned may the first Run proposal create verified code/document candidates
    in isolated worktrees; merge, publication, deployment, and outbound remain
    separate gates.
11. Directionally, Glupta/Hermes may become a universal conversational and
    supervisory front door, never a universal data plane or execution authority.
    Personal lanes remain local-only, domain-specific, minimum-necessary, and
    separately gated; finance credentials/signing/submission/money movement and
    all Personal Health records remain outside shared Glupta authority/state.

## Build-versus-adopt disposition

The full touched stack was rechecked before freezing R1:

- Adopt: FastAPI/Pydantic for admission and schemas; DBOS/PostgreSQL for durable
  workflow/concurrency; Pydantic AI/Evals for the typed one-agent/eval path;
  official AsyncOpenAI Responses SDK for provider transport; Python
  `asyncio.timeout_at` for the absolute cancellation boundary; `uv`, OCI, and
  Compose for packaging/operation; standard CycloneDX/SPDX, Syft/Grype,
  ORT/ScanCode, Cosign/SLSA primitives for release evidence; and provider-native
  Codex, Claude, and pinned Grok CLIs for frontier review.
- Keep custom only where the frozen Glupta contract is not supplied by those
  primitives: secure local intake; disclosure/rights admission; the durable
  effect/budget/release/sticky-ambiguity state machine; citation/audit
  cross-binding; exact packet hashing and sealed fan-in; and the narrowly tested
  Grok permission-cancellation synthesis recovery.
- Do not add OpenAI Agents SDK, Pydantic's provider model wrapper, LiteLLM or a
  model gateway, OpenAI background mode, MCO, or AGPair. Under this frozen
  contract they add loop/routing/retry/state/policy translation without
  replacing the required effect, credential, deadline, native-route,
  exact-packet, or sealed-fan-in semantics. Reassess when a maintained primitive
  can remove custom code while preserving the same regression boundary.

## Deterministic evidence supplied

- Product exact-tip: Ruff clean; 66 pytest tests plus 95 subtests passed; lock
  check; Compose parse; package/wheel/sdist inventory; dependency audit with no
  known vulnerability; adversarial concurrency/effect/replay/deadline/status-
  exception tests; independent scoped adversarial review; and security review.
- Control documents exact-tip: JSON parse, checksum-pinned official D2 0.7.1
  format and byte-identical render, focused amendment/traceability assertions,
  diff check, and the repository's full fixed boundary.
- Blueprint exact-tip: unique source-key checks, exact candidate/repair wording,
  diff check, and the repository's smoke attestation.
- No credential contents, provider call, spend, live runtime mutation,
  deployment, public action, task drain, Walk/Hermes activation, or business
  effect occurred.

The DBOS queue-admission implementation captures an aware server UTC timestamp
as a workflow argument; DBOS 2.29 preserves first-recorded inputs on duplicate
workflow identity and uses them on recovery. A stronger real PostgreSQL
duplicate-admission/UUID-clock regression is captured as a separate P2
follow-up. It does not change the current contract or authorize dispatch. A
reviewer should promote it to a blocker only if primary evidence shows the
current implementation or present proof is materially false or unsafe.

## Review protocol and stop rule

Codex is the controller/integrator. It froze the charter and exact path/
requirement closure, assembled and hashed one de-identified evidence packet,
ran deterministic mechanical preflight first, reconciles findings from primary
evidence, permits at most one bounded remediation pass, integrates/verifies,
and owns durable closeout.

Blind, read-only final reviews receive the identical exact packet/hash:

- fresh `gpt-5.6-sol`, maximum reasoning, native Codex CLI;
- `claude-fable-5`, maximum reasoning, through `advisor_full`, with only the
  native `claude-opus-5` fallback permitted by route policy;
- Grok 4.6, `xhigh`, through the pinned full launcher.

Peer results remain sealed until fan-in. “All three agree” means all three
completed reviews find zero substantiated material blockers on the exact final
candidate. It is not verbal unanimity or voting. Do not force consensus.
Resolve factual disputes from primary evidence; preserve irreducible material
disagreement as `HOLD_MATERIAL_DISSENT`.

This restarted audit permits at most two candidate hashes, one remediation
pass, six planned reviews (three R1 plus three R2 only if amended), and one
availability retry per route. A production-code change invalidates the baseline
and returns `RESTART_REQUIRED`. Terminal states are `PASS`,
`HOLD_MATERIAL_DISSENT`, `HOLD_EVIDENCE`, `INCOMPLETE_REVIEW`, or
`RESTART_REQUIRED`.

## Required reviewer output

Return exactly:

1. `VERDICT`: one terminal state above.
2. `MATERIAL_BLOCKERS`: every substantiated blocker with exact primary evidence,
   defect class, and smallest safe disposition; write `none` for zero.
3. `NON_BLOCKING_FINDINGS`.
4. `FACTUAL_CORRECTIONS`.
5. `FOUNDATION_DISPOSITION`: keep, repair, partial rebuild, or full rebuild,
   including cost, risk, rollback, and whether dispatch remains held.
6. `CONFIDENCE_AND_UNCERTAINTY`.

`PASS` means zero substantiated material blockers on these exact bytes. It does
not approve deployment, provider dispatch, task draining, Walk, public
activation, Hermes expansion, or effects.
