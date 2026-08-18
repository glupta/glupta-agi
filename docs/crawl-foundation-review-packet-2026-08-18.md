# Glupta Crawl foundation review packet

Candidate: `C2` (one bounded amendment after blind C1 review)

Review date: 2026-08-18

Controller: Codex

Repository baseline: `glupta/glupta-agi` commit
`89962df27252a822d795a6b0bcdc9b89871a82bd`

## Review question

Given the normative Greenfield architecture, the amended Stage-0 package, the
current product repository, the deployed Crawl runtime, and the representative
outcome evidence below, should the Crawl foundation be kept, repaired,
partially rebuilt, or fully rebuilt before any Walk proposal?

Identify every substantiated material blocker. For each blocker, cite primary
evidence, state whether it is a normative-contract defect, implementation
defect, verification gap, deployment/provenance defect, or documentation drift,
and name the smallest safe disposition. Requirements must not be weakened to
make flawed code pass. Historical receipts must remain historical and may only
be superseded. Production-code remediation is outside this review candidate.

## Controller charter and stop rule

The controller freezes the exact path and requirement closure, runs mechanical
preflight, resolves factual disputes from primary evidence, permits at most one
bounded documentation/test-traceability remediation pass, integrates and
verifies, and owns durable closeout.

Blind final reviews use the identical candidate bytes and hash:

- fresh Codex `gpt-5.6-sol`, maximum reasoning;
- `claude-fable-5`, maximum reasoning, through `advisor_full`; only the
  contract-authorized `claude-opus-5` fallback is permitted;
- Grok 4.6, `xhigh`, through the pinned full launcher.

Peer results remain sealed until fan-in. “All three agree” means all three
completed reviews find zero substantiated material blockers on the exact final
candidate. It is not a vote or a requirement for matching prose. Factual
disputes are resolved from primary evidence. Irreducible material disagreement
returns `HOLD_MATERIAL_DISSENT`.

Hard limits: at most two candidate hashes, one remediation pass, six planned
model reviews (three initial and, only if amended, three final), and one
availability retry per route. Terminal states are `PASS`,
`HOLD_MATERIAL_DISSENT`, `HOLD_EVIDENCE`, `INCOMPLETE_REVIEW`, or
`RESTART_REQUIRED`. Any production-code change invalidates this baseline and
returns `RESTART_REQUIRED`.

Walk activation, public activation, authority expansion, external effects,
and broader Hermes activation remain frozen. This audit may recommend but may
not activate Walk.

## Normative precedence and non-goals

The final amended DBOS-first Blueprint is the product architecture. The
detailed Greenfield specification and Stage-0 package are the requirement and
test annexes until reconciled by a reviewed amendment. The current repository
and operating record are as-built evidence, not authority to weaken a
requirement.

Non-goals include new providers, recipients, credentials, spend, evaluators,
tools, actions, sends, money movement, signing, trading, transfers, public
release, data migration, or retrospective fabrication of missing Stage-0
closeout. The paired-vault shell-hook issue and general Hermes supervision are
separate infrastructure tasks.

## Exact evidence closure

Reviewers may read only the following relevant roots and files. Credential
contents, `.env` contents, private keys, wallet material, and Personal Health
are excluded.

Normative architecture and stage contract:

- `/Users/glupta/vault-wt/codex/glupta-crawl-foundation-review-20260818/wiki/operations/debates/greenfield-agent-farm-architecture-v3/idea.md`
- `/Users/glupta/Dev/studio-hub-wt/codex/glupta-crawl-foundation-reconcile-20260818/docs/studio-agent-farm-greenfield-spec.md`
- `/Users/glupta/Dev/studio-hub-wt/codex/glupta-crawl-foundation-reconcile-20260818/docs/glupta-security-threat-model.md`
- `/Users/glupta/Dev/studio-hub-wt/codex/glupta-crawl-foundation-reconcile-20260818/docs/glupta-launch-and-oversight-plan.md`
- `/Users/glupta/Dev/studio-hub-wt/codex/glupta-crawl-foundation-reconcile-20260818/docs/glupta-commercialization-ip-plan.md`
- all top-level files in `/Users/glupta/Dev/studio-hub-wt/codex/glupta-crawl-foundation-reconcile-20260818/docs/glupta/`
- the D2 source, projection profile, and nine generated SVG views under
  `/Users/glupta/Dev/studio-hub-wt/codex/glupta-crawl-foundation-reconcile-20260818/docs/glupta/visuals/`
- `/Users/glupta/Dev/studio-hub-wt/codex/glupta-crawl-foundation-reconcile-20260818/tests/test_glupta_crawl_foundation_amendment.py`

As-built product and verification:

- `/Users/glupta/Dev/glupta-agi/AGENTS.md`
- `/Users/glupta/Dev/glupta-agi/README.md`
- `/Users/glupta/Dev/glupta-agi/pyproject.toml`
- `/Users/glupta/Dev/glupta-agi/uv.lock`
- `/Users/glupta/Dev/glupta-agi/Dockerfile`
- `/Users/glupta/Dev/glupta-agi/compose.yaml`
- all Python files under `/Users/glupta/Dev/glupta-agi/src/glupta_agi/`
- all tests under `/Users/glupta/Dev/glupta-agi/tests/`
- `/Users/glupta/Dev/glupta-agi/evals/evidence_brief_v1.json`

Operating and decision evidence:

- Glupta sections of `/Users/glupta/vault-wt/codex/glupta-crawl-foundation-review-20260818/wiki/operations/stack.md`
- Glupta rows in `/Users/glupta/vault-wt/codex/glupta-crawl-foundation-review-20260818/ops/tasks.md`
- this packet and the active checkpoint
  `glupta-mvp-blueprint-drain-20260818`

The packet does not authorize reviewers to mutate any of those paths.

## Product goal and frozen Crawl boundary

Crawl is one useful, source-grounded, read-only `OBSERVE` workflow. It accepts
one authenticated loopback request containing a question and one to twenty
explicitly selected local Markdown/text files. It returns a typed evidence
brief with exact local file-and-line citations, uncertainties, and next
decisions. It has one DBOS workflow, one DBOS queue, one Pydantic AI agent, one
predeclared external model slot, and no tools or actions. The Community runtime
has one app executor and PostgreSQL. Production source is capped at 1,500 lines.

No Crawl result grants authority. Selected source contents are disclosed to
the fixed OpenAI subscription route; no local-only or de-identification claim
is made for the deployed product. Provider retries, web search, shell, tools,
apps, plugins, multi-agent execution, and remote plugins are disabled.

## As-built baseline

- Canonical product repository is clean and aligned with `origin/main` at
  `89962df`; package, FastAPI, and DBOS application version are `0.2.10`.
- Production Python is exactly 1,500 lines across eleven modules.
- Dependencies are frozen by `uv.lock`. Direct selections include DBOS
  `>=2.29,<3`, Pydantic AI Slim with DBOS `2.31.0`, official Codex Python
  package `0.144.4`, FastAPI, Psycopg, SQLAlchemy, and Uvicorn.
- Compose has exactly `app` and `postgres`. The app is loopback-published at
  `127.0.0.1:8765`; the input mount is read-only; runtime capabilities are
  file-backed. The app runs as host UID/GID `501:20`; the Dockerfile image
  declares non-root UID/GID `10001:10001` but Compose overrides it.
- The secondary Codex `auth.json` is bind-mounted into a private 64 MiB tmpfs
  target and is writable because the supported client mutates its local
  credential state. Metadata validation requires a regular, non-symlink,
  owner-matching, mode-0600 file. Credential contents were not read for this
  audit.
- `crawl_external_effects` is the sole application-owned table. It fixes slot
  `model-0`, model name, request digest, and `max_calls=1`, and records the
  states `reserved`, `dispatching`, `thread_started`, `turn_started`,
  `returned`, `reconciled`, `failed`, and `unknown`.
- The model invocation is ephemeral, read-only, tool-disabled, web-disabled,
  and launched with a cleared environment plus only a small allowlist.
  Provider and stream retries are zero. A crash after possible dispatch holds
  `unknown`; it does not redispatch.
- Current deterministic repository preflight: `49 passed, 56 subtests passed`;
  Ruff clean; `git diff --check` clean.
- Current Stage-0 docket/visual preflight in Studio Hub: 56 focused tests pass;
  checked-in visual verification passes.
- Live runtime: app image
  `sha256:c8f66b2f106d3c3d6f313bd2313e7614c92f868b6b8f75c5e4ab1d3e4c6db9ad`;
  PostgreSQL image
  `sha256:f3bd19c606e442c3d7bdfa8002e03fe260a1023351e0ea4598032022b68dd6e3`;
  both containers healthy with zero restarts. `/healthz` returns
  `{"status":"healthy","stage":"Crawl","actions":"disabled"}`.

## Representative real outcomes

The start gate required two additional public/disclosure-safe outcomes after
Crawl was fully set up.

### OpenRec product diligence

- packet SHA-256:
  `ea0f460ef95ac83e688764cd4b208d7d5fa959380ad79418baa1c28829dc455a`
- workflow: `01a0154b-bad3-7680-a72c-825b9932e4bc`
- request digest:
  `acee275c00a37421f0da1a7871aabd7388efc42aef430eaac0d63f21ace2bbf3`
- response replay SHA-256, twice:
  `ae989cec0b8ace6b321b330b30365a7aee8de583bd39134caffe0470745df474`
- one successful `crawl_observe_agent__model.request` step; one reconciled
  `model-0` effect with `max_calls=1`; zero active workflows afterward
- native usage: 5,813 input, 0 cache-read, 2,751 output, 1,142 reasoning-output
  tokens; USD cost unavailable
- four grounded citations and eight explicit uncertainties
- useful disposition: one bounded disposable synthetic/non-private trial may
  be considered separately; private-meeting use remains blocked on binary
  provenance, participant consent, actual data flow, downstream deletion,
  exportability, capture/diarization reliability, retention, and webhook proof

### Block “From Hierarchy to Intelligence” architecture review

- packet SHA-256:
  `a711f747c536915091cda88b9179d231f7e3490e0ce0149a57fa30da6d018c98`
- workflow: `01a0154b-bad3-7680-a72c-825c68f59019`
- request digest:
  `2ddfe6175fc4bdb3c8683ac8fc2be8b473431b27df4fcbf60d5b4b5be53b5aea`
- response replay SHA-256, twice:
  `6d98ea4ebd48601905a1d86d358741e50062fb1ae5e4dee745a1b9b530292338`
- one successful native model step; one reconciled `model-0` effect with
  `max_calls=1`; zero active workflows afterward
- native usage: 5,616 input, 2,816 cache-read, 2,199 output, 1,034
  reasoning-output tokens; USD cost unavailable
- four grounded citations and five explicit uncertainties
- useful disposition: `test narrowly` through one preregistered, fixed-duration,
  read-only shadow experiment; do not copy the article's unproven hierarchy or
  “world model” claims into production authority

These prove real usefulness and the narrow live replay/effect boundary. They do
not prove the entire historical Stage-0 or Walk gate.

## Build and deployment reconstruction

1. The original private repository began on 2026-08-15.
2. On 2026-08-17, an initial evidence-brief slice was built, first with local
   Qwen/Ollama, then deployed, then changed to the secondary Codex subscription.
3. PRs 1 and 2 produced a useful live system but retained architecture drift.
4. PR 3 (`d23e3f1`) rebuilt Crawl around the final amended Blueprint: DBOS,
   PostgreSQL, a one-slot effect fence, the official Codex SDK, typed Pydantic
   AI, and two Compose services.
5. PRs 4–11 removed unused artifacts, bounded the DBOS queue, strengthened
   conformance/fidelity, switched to native Pydantic AI DBOS durability,
   hardened the credential/runtime environment, disabled global plugins/apps,
   and reduced retained Codex state.
6. Later commits added a safe local submit client, immutable packet
   documentation, typed client response validation, and native token usage.
7. The deployed `0.2.10` app is healthy and has completed multiple live,
   exactly replayed, single-effect tasks. The repository history nevertheless
   shows repeated post-deployment corrections rather than one manifest-bound,
   build-once release rail.

## Preliminary requirements traceability

Statuses are evidence classifications, not final reviewer verdicts:
`PASS`, `PARTIAL`, `OPEN`, `CONFLICT`, or `NOT_CURRENT_STAGE`.

### Architecture and product constraints

| Requirement | Status | Primary evidence |
| --- | --- | --- |
| One useful read-only OBSERVE workflow | PASS | live representative outcomes, `workflow.py` |
| One executor plus PostgreSQL | PASS | `compose.yaml`, live container inventory |
| Production LOC at or below 1,500 | PASS with no headroom | exact `wc -l` = 1,500 |
| DBOS owns workflow/step/queue/replay | PASS | DBOS workflow/queue and native DBOS durability |
| No action/tool authority | PASS | health contract and Codex feature configuration |
| Every model dispatch has frozen identity and no provider retry | PASS for the single route | `effects.py`, `workflow.py`, tests and live receipts |
| Ports-and-adapters domain isolation | PARTIAL | small modules exist, but vendor SDKs are imported directly in workflow/application code and no import-contract suite maps every module to a policy clause |
| Non-root, host-neutral OCI runtime | PARTIAL | non-root in image and deployment, but Compose overrides to host-specific `501:20` |
| Exact image/build provenance | OPEN | Docker bases and PostgreSQL use mutable tags; no product-owned SBOM, provenance, signature, or build-twice receipt |
| Standard telemetry without a second truth store | PARTIAL | DBOS state and native usage exist; no explicit OpenTelemetry export/operating contract is implemented |
| Operator health reflects dependencies and work state | PARTIAL | health is a static stage/action response; it does not verify PostgreSQL, DBOS queue, provider availability, ambiguity, or freshness |

### Canonical-contract conflicts

| Conflict | Current facts | Required disposition |
| --- | --- | --- |
| Runtime topology/model | Final Blueprint/repo use `app + postgres` and external Codex; detailed Stage-0 docs and visuals retain `app + postgres + ollama` and Qwen | Reconcile the normative package and visuals; do not rewrite historical receipts |
| Disclosure class | Deployed source contents go to fixed OpenAI; Stage-0 package says `local_private`, zero network egress | Define an immutable externally-disclosed Crawl data class and exact destination schema, or reject the deployed route |
| Runtime credential | Deployed app mounts a secondary consumer-subscription credential; `T-GF-043` says subscription credentials never enter Compose/runtime and headless consumer clients fail closed | Amend with an explicit, reviewed subscription-supervised adapter boundary or remove the route in a separate code loop |
| Specialist SDK | Deployed app imports and launches the official Codex SDK; `T-GF-018` forbids privileged nested agent SDKs | Supersede the old exclusion only through a reviewed architecture amendment with equivalent tests |
| Application-table writes | The final Blueprint requires an effect fence for every model dispatch; the detailed Stage-0 package says Crawl writes zero application rows including `external_effects` | Choose and document one rule. Safety floors forbid deleting the fence merely to match old prose |
| Test truth | Stage-0 advertises 54 `T-GF` families, but product tests are not mapped to them and several families literally test the superseded local-Ollama design | Replace stale branches with current falsifiable requirements; keep genuinely unproven gates open |
| Review receipt | The 2026-08-13 receipt bound an earlier candidate and was repeatedly invalidated by later amendments | Mark it historical/superseded; never present it as approval of the deployed candidate |

### Current Womb/Crawl test families

| Test family | Status against deployed Crawl |
| --- | --- |
| T-GF-001 import-boundary | PARTIAL: no legacy imports observed; no product AST prohibition test |
| T-GF-002 architecture-budget | PARTIAL: exact LOC/service/table counts known; module-to-policy mapping absent |
| T-GF-003 compose-cold-start | CONFLICT: literal Ollama test is stale; live clean-host evidence is not a repo-owned reproducible current-route gate |
| T-GF-008 isolation | PARTIAL: tools/shell/web/plugins disabled and Firecracker absent; externally disclosed content and writable credential state require an explicit threat boundary |
| T-GF-009 status-truth | OPEN: DBOS is authoritative, but no `OutcomeSnapshotV1`/cross-adapter status contract exists |
| T-GF-010 harness-contract | PASS: Harness and second loop are absent; typed Pydantic AI core is present |
| T-GF-011 model-policy | CONFLICT: literal frozen Ollama route is stale; Codex route evidence exists but no equivalent current model-policy comparison is mapped |
| T-GF-015 dependency-upgrade | PARTIAL: lock and upgrade checks have been exercised; no single product-owned complete upgrade rehearsal gate |
| T-GF-016 knowledge-provenance | PARTIAL: exact source digests/line citations and uncertainty are enforced; valid-time/supersession semantics are not a general runtime contract |
| T-GF-018 opaque-specialist-exclusion | CONFLICT: deployed code intentionally uses Codex SDK |
| T-GF-021 upgrade-proof | OPEN: no product SBOM/interface/deployment blast-radius proof |
| T-GF-022 adapter-substitution | PARTIAL: deterministic fakes cover the model edge; vendor imports and missing explicit ports prevent a full conformance claim |
| T-GF-023 dependency-direction | OPEN: no import-contract test; workflow/application code imports vendors directly |
| T-GF-026 artifact-completeness | OPEN: Stage-0 visuals verify in Studio Hub, but product release artifacts/provenance are absent and product changes do not own visual drift checks |
| T-GF-028 progressive-rollout | PARTIAL: useful Crawl evidence and frozen authority pass; its old “no effect-fence dependency” clause conflicts with the safer live fence |
| T-GF-030 privileged-binary-graph | PARTIAL: Codex package is pinned, but the executed binary/configuration has no product content digest/graph gate |
| T-GF-033 intake-conformance | PARTIAL: authenticated API/client, UUIDv7, immutable source digest, replay, and key-conflict checks exist; full golden-vector and concurrent-first-write evidence is incomplete |
| T-GF-035 intake-reply-authority | PASS negative branch: no reply or messaging adapter exists and untrusted source commands cannot become tools/actions |
| T-GF-036 privacy-egress | CONFLICT: external disclosure is documented as-built but contradicts the Stage-0 local-only class and zero-cloud branch |
| T-GF-042 capability-first-substitution | PARTIAL and CURRENT: narrow source/model substitution exists; the general outcome/supervisory adapter suite remains open |
| T-GF-043 model-access-modes | CONFLICT: headless subscription route is the deployed design and credential state enters the Compose runtime boundary |
| T-GF-047 identity-separation | PARTIAL: names/account/model are distinguished in docs/settings; no complete product test family maps the contract |
| T-GF-049 launch-rail-reproducibility | OPEN: no build-twice, digest-pinned base, SBOM/provenance/signature, promote-without-rebuild, or rollback receipt; literal Ollama/zero-effect-row clauses are stale |
| T-GF-052 GitHub delivery controls | PARTIAL/OPEN: PR-required squash landing is observed, but the complete expected-control/workflow/attestation gate is not product-owned |
| T-GF-050 Stage-0 closure | OPEN/STALE: documents and visuals mechanically validate, but the receipt predates the deployed architecture and post-build evidence is incomplete |
| T-GF-051 pattern-policy conformance | OPEN for future patterns; Crawl negative branches need rewriting against the current single-pass design |
| T-GF-053 outcome/autonomy/correction/dispatch | PARTIAL negative branch: no autonomy/actions; the massive future contract is not proof of current Crawl and some no-effect-row language is stale |

Walk, Run, Bike, Drive, Fly, and Space positive branches remain
`NOT_CURRENT_STAGE`. Their directional requirements may be clarified, but no
implementation or activation is in scope.

## Preliminary risk and cost assessment

The deployed vertical slice has demonstrated useful value and strong local
effect/replay controls. A full rebuild would discard working behavior without
yet proving that a replacement reduces risk or complexity. A simple “keep” is
also unsupported because the normative chain, release provenance, and several
hard privacy/credential tests contradict the live design.

The controller's preliminary disposition is **partial rebuild of the
foundation contract and release/adapter boundaries, while preserving the
working Crawl behavior until a separate verified code plan exists**. In this
audit candidate, “partial rebuild” means reconcile specs/checklists/tests/docs/
visuals/roadmap first; it does not authorize production code changes.

Likely priority order if reviewers substantiate it:

1. establish one current normative Crawl profile for externally disclosed,
   subscription-supervised, one-slot read-only generation;
2. replace stale local-Ollama and no-effect-row checklist branches with tests
   that preserve or strengthen disclosure, credential, retry, ambiguity, and
   authority floors;
3. bind each current requirement to a product test, live receipt, explicit open
   gap, or future-stage negative branch;
4. make release inputs and images immutable and add reproducible
   SBOM/provenance/rollback evidence;
5. decide whether the Codex adapter can satisfy a stable ports-and-adapters and
   credential-isolation contract. If it cannot, a later production-code loop
   should replace it rather than add wrappers;
6. retain Walk as closed until the reconciled Crawl foundation has zero
   material blockers and measurable Walk entry/exit criteria are separately
   approved.

Rollback for this audit is the unchanged deployed `0.2.10` product plus the
unchanged historical documents. Documentation reconciliation must be one
reviewed branch and is removable without touching production. Any later code
candidate must have its own exact baseline, tests, deployment rollback, and
frontier gate.

## Known uncertainty

- Historical live receipts establish many individual fault/replay checks, but
  they are distributed through operating notes rather than one machine-readable
  current test manifest.
- The provider does not expose USD cost through the current native subscription
  usage object; token usage is authoritative while USD cost remains unknown.
- The static `/healthz` endpoint proves process responsiveness, not dependency
  readiness or provider/queue freshness.
- The official Codex subscription/client contract may not support the desired
  long-term unattended product boundary. Reviewers must distinguish this
  portability/licensing risk from the currently observed technical controls.
- Future-stage requirements are intentionally elaborate. The audit should
  delete or simplify only requirements that are truly stale, duplicated, or
  falsely stage-assigned; it must not silently lower safety, privacy,
  authorization, recovery, or release floors.

## C2 controller adjudication and amendment

The three sealed C1 reviews all required revision and converged on a **partial
contract and traceability rebuild**. Their normalized fan-in and route metadata
are hash-bound in `docs/crawl-foundation-initial-review-fan-in-2026-08-18.md`.
The representative outcomes, live runtime, replay, workflow inventory, evidence
method, and limitations are hash-bound in
`docs/crawl-foundation-evidence-receipt-2026-08-18.md`.

C2 incorporates exactly one documentation/test-traceability/visual/roadmap
pass:

- Studio Hub adds a current normative amendment, machine-readable exact stage
  map, deterministic tests, and a standalone D2/SVG current-Crawl projection;
- the amendment explicitly supersedes named clauses in the byte-preserved
  detailed spec, security, launch, visual, and concise Blueprint artifacts;
  historical Stage-0 files and receipts remain unchanged;
- the paired canonical Blueprint, operating stack, and Task Spine record the
  same held boundary;
- the deployed consumer-subscription route is evidence-only and held. External
  inference is permitted only through a provider-supported service/automation
  adapter satisfying immutable disclosure, rights, credential, token/USD/time/
  call budgets, retry, audit, isolation, revocation, and release floors;
- `local_only` remains a stricter supported profile;
- `model-0`, `max_calls=1`, provider retry=0, and fail-closed ambiguity are
  normative safety state, not prohibited external-action authority;
- the current matrix is exactly Womb `050/051/053` and Crawl
  `001/002/003/008/009/010/011/015/016/018/021/022/023/026/028/030/033/035/036/042/043/047/049/052`;
- token/cost/time ceilings, read-only root and resource limits, exact manifest,
  SBOM/provenance/signature, rollback rehearsal, current release approval, and
  full product-test mapping remain `OPEN` and block dispatch/promotion;
- version `0.2.10` is an evidence baseline, not a conforming release or approved
  rollback candidate;
- no production code changed. Walk, public activation, broader Hermes,
  authority expansion, tools/actions, and effects remain frozen.

The 2026-08-18 principal decision also fixes the post-audit value sequence. Only
after the audit and every held adapter/budget/provenance/rollback/release gate
closes, Crawl serves Hammock source-grounded architecture/GTM/decision briefs
and PEECH public-or-synthetic discovery/decision-product briefs. PEECH private
or customer material separately requires rights, an approved data boundary,
and Anmol or owner participation. The next proposed Walk has exactly three
proposal-only families: current-state/blocker synthesis; decision/spec/
deliverable preparation; evidence/quality review. It has no send/effect path.
After Walk is earned, the first proposed Run category is verified code/document
candidates in isolated worktrees; merge, publication, deployment, and outbound
remain independent approval gates. Existing Codex Hammock/PEECH work continues
under normal gates. The sequence is evidence-gated, never calendar-gated.

Directional compatibility only: Glupta/Hermes may eventually be the universal
conversational/supervisory front door, never a universal data plane or execution
authority. Future home, personal-finance, and Personal Health lanes remain
local-only, domain-by-domain, minimally projected, and separately gated;
Personal Health stays a distinct silo and shared state receives only opaque
intent/lifecycle status. Cross-domain decisions use approved minimum constraints
or pass/fail gates, never pooled raw records. Existing Studio controllers remain
independent. Private-domain execution always requires a separately approved
local executor and domain evidence gate. These are non-current constraints, not
C2 acceptance criteria or activation authority.

The old preliminary recommendation to establish a “subscription-supervised”
runtime profile is superseded: supervision or renaming cannot make a consumer
session a conforming unattended adapter. Any production remediation is a
separate loop and restarts the audit baseline.

## Required reviewer output

Return:

1. verdict: `PASS_CANDIDATE`, `REVISE_CANDIDATE`, `HOLD_EVIDENCE`, or
   `RESTART_REQUIRED`;
2. substantiated material blockers, each with exact primary evidence;
3. non-blocking findings;
4. factual corrections to this packet;
5. keep/repair/partial-rebuild/full-rebuild recommendation with cost, risk, and
   rollback rationale;
6. the smallest bounded amendment needed before a blind final review;
7. confidence and unresolved uncertainty.

Do not edit files, deploy, send, spend, access secrets, sign, transact, or
activate any stage.
