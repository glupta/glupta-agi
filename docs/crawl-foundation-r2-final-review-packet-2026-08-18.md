# Crawl foundation final-review packet — candidate R2

Review date: 2026-08-18

Controller: Codex

Status: final bounded candidate, frozen only after the companion source manifest
and external packet digest are written. This packet grants no deployment,
provider dispatch, credential access or creation, spend, task drain, Walk,
public, Hermes, tool, action, outbound, signing, trading, transfer, or
money-movement authority.

## Review question

Does the reconciled Crawl foundation have zero substantiated material blockers
as an honest dispatch-held candidate, while preserving every open release gate?
Determine whether to keep, repair, partially rebuild, or fully rebuild it before
any Walk proposal. Cite primary evidence for every material blocker and name the
smallest safe disposition. Do not weaken a normative requirement to match code.

## Exact candidate tuple

- Product: `ea20b5e2a44a5cf2178eca63d20f94e6f3e88883`, parent
  `bb05166cc054a14e5fedadc3166369bca15ed743`.
- Control documents: `b86dc04dd6cb9b3a7d6a14ef14bd5d01b06c6a3e`, based on
  `a98d4199141f8e0209161aa37c4b1cb8981ec983` (three linear commits).
- Blueprint and operating state: `9f889d252242c2a0c86563701c0de6bd68f7475a`, based on
  `b17b301e6e63f0fd3f93318e9faa29fe65c3d52f` (two rebased linear commits).

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
   provider-neutral `InferencePort`. It disables ambient proxy inheritance.
   Complete authenticated provider rejection is terminal `failed`, sanitized
   without exception-cause leakage, and never retried. One absolute monotonic
   deadline covers transport and client cleanup. Timeout, EOF, uncertain
   acceptance/usage, cleanup-only expiry, or uncertain durable commit after
   dispatch becomes sticky `unknown`, suppresses output, and never redispatches.
5. Completed responses require provider request/response identity, exact
   returned-model agreement, internally consistent complete usage, a
   conservative price-bound USD upper bound, typed schema/citation validation,
   and immutable cross-binding of the citation-resolved result and provider
   audit. The initial API response and replay return the recorded audit.
6. One idempotent post-dispatch persistence proof covers both exact
   `reconciled` and exact `failed` outcomes. Acknowledgement loss is accepted
   only after exact state/result/audit/hold-reason readback. Pre-commit,
   mismatched, tampered, unreadable, or unholdable outcomes become redacted
   sticky `unknown`; replay never constructs the provider adapter or redispatches.
7. Runtime, package metadata, API, and DBOS application identity resolve from
   the same `0.3.0` version source.
8. The release image is wheel-only, digest-pinned, non-root, read-only,
   capability-dropped, resource-bounded, and restricted to the allowlisted
   provider destination. These are requirements; local source/test claims do
   not substitute for the exact release receipts below.
9. Live dispatch and release remain held until current independent evidence
   exists for the dedicated account/project/service-account/key generation and
   revocation; source rights; provider data-use/retention/region; rate/spend and
   allowlisted egress; exact manifest/SBOM/OS-vulnerability/provenance/signature/
   approval; dependency health/drain; and isolated rollback. The deployed
   consumer route is historical evidence, not a conforming rollback target.
10. Conflicting historical Stage-0 claims and all R1 receipts are superseded,
    never rewritten. Historical reviewer outputs are not normative evidence for
    R2 and are intentionally excluded from this packet's review closure.
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
    supervisory front door, never a universal data plane or execution authority.
    Personal lanes remain local-only, domain-specific, minimum-necessary, and
    separately gated; finance credentials/signing/submission/money movement and
    all Personal Health records remain outside shared Glupta authority/state.

## R1 remediation closure

R1 remains immutable at product `fc2dcac4d5d093168b527a424aefcc3be22d1eb7`,
control `c42394e0ffc96c5baf402627b614b7fb7ca50c9b`, Blueprint
`95fe95b40eba3f5724ec12bf02aa0ae847f28884`, packet SHA-256
`fa689205173271e4d6f7ea37addc88e6c0d4ad873cae81ee990d8a10a2ea8dc1`.
Its controller state was `RESTART_REQUIRED`. R2 claims closure only through
primary source and adversarial tests for the five substantiated R1 defects:

1. post-dispatch commit/acknowledgement ambiguity now uses exact readback or a
   sticky redacted unknown hold for successful and definitive-failure paths;
2. initial and replayed public responses now expose and validate the immutable
   provider audit, IDs, usage, and conservative cost upper bound;
3. the first-party bearer client disables ambient proxy inheritance;
4. cleanup-only deadline expiry is ambiguous/unknown, not definitive failed;
5. runtime and package version identity are unified at `0.3.0`.

Any substantiated residual production defect returns `RESTART_REQUIRED`; it is
not repaired inside this frozen audit.

## Build-versus-adopt disposition

The full touched Glupta stack was rechecked before freezing R2:

- Adopt FastAPI/Pydantic for admission and schemas; DBOS/PostgreSQL for durable
  workflow/concurrency; Pydantic AI/Evals for the typed one-agent/eval path;
  official AsyncOpenAI Responses SDK for provider transport; Python
  `asyncio.timeout_at` for absolute cancellation; `uv`, OCI, and Compose for
  packaging/operation; standard CycloneDX/SPDX, Syft/Grype, ORT/ScanCode,
  Cosign/SLSA for release evidence; and provider-native Codex, Claude, and
  pinned Grok CLIs for frontier review.
- Keep custom only where the frozen contract is not supplied by those
  primitives: secure local intake; disclosure/rights admission; the durable
  effect/budget/release/sticky-ambiguity state machine; citation/audit binding;
  and exact packet hashing, native-route policy, and sealed fan-in.
- Do not add OpenAI Agents SDK, Pydantic's provider model wrapper, LiteLLM or a
  model gateway, OpenAI background mode, MCO, or AGPair. Under this frozen
  contract they add loop/routing/retry/state/policy translation without
  replacing the required effect, credential, deadline, native-route,
  exact-packet, or sealed-fan-in semantics. Reassess touched boundaries and
  maintained alternatives; sunk cost never justifies custom infrastructure.
- The custom Grok permission-cancellation recovery is separately queued for
  adopt-versus-build reassessment and retirement when a native pinned route
  passes the same live receipt/sandbox fixture. That follow-up does not weaken
  or expand R2.

## Deterministic evidence supplied

- Product `ea20b5e…`: exact synced pre-merge candidate passed 75 pytest tests
  plus 111 subtests, Ruff, lock, release-boundary, wheel/sdist build and wheel
  metadata `0.3.0`, Compose parse, dependency audit with no known
  vulnerabilities, semantic production census `1500/1500`, diff checks, and
  scoped security review. The protected squash merge changed only commit
  identity, not candidate tree bytes.
- Control `b86dc04…`: checksum-pinned visual checks, schema validation, 59
  focused amendment/traceability/visual tests, diff check, clean exact-tip
  smoke attestation, and no production-runtime change.
- Blueprint `9f889d25…`: exact candidate wording, durable value sequence, one
  deduplicated future Grok-route task, three-path diff closure, clean exact-tip
  smoke attestation, and no canonical-vault write.
- No credential contents, provider call, spend, live runtime mutation,
  deployment, public action, task drain, Walk/Hermes activation, or business
  effect occurred.

The DBOS queue-admission implementation captures an aware server UTC timestamp
as a workflow argument; DBOS 2.29 preserves first-recorded inputs on duplicate
workflow identity and uses them on recovery. A stronger real PostgreSQL
duplicate-admission/UUID-clock regression remains a separate P2 follow-up. It
does not change the current contract or authorize dispatch. Promote it to a
blocker only if primary evidence shows the present implementation or proof is
materially false or unsafe.

## Review protocol and hard stop

Codex is controller/integrator. It froze the charter and exact path/requirement
closure, assembled and hashed one de-identified packet, ran deterministic
mechanical preflight first, reconciles findings from primary evidence, and owns
durable closeout.

R2 is the second and final candidate hash after the one permitted production
remediation pass. The three planned R2 reviews are the remaining planned review
rounds. Run fresh read-only Codex `gpt-5.6-sol` at maximum reasoning first as a
hard gate. Do not invoke Fable or Grok unless Codex finds zero substantiated
material blockers on this exact packet/hash. If Codex blocks, terminate
`RESTART_REQUIRED`; no peer spend or in-audit production repair is allowed.

Only after Codex clears, blind read-only Fable and Grok receive this identical
packet/hash: `claude-fable-5` maximum via `advisor_full` with only the allowed
native Opus 5 fallback, and Grok 4.6 `xhigh` through the pinned full launcher.
One availability retry per route is permitted by the frozen protocol. Results
remain sealed until fan-in.

“All three agree” means all three completed reviews find zero substantiated
material blockers. It is not voting or verbal unanimity. Resolve factual
disputes from primary evidence; preserve irreducible material disagreement as
`HOLD_MATERIAL_DISSENT`. Terminal states are `PASS`,
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
