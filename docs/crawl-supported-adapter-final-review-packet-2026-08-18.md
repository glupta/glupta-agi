# Crawl supported-adapter final-review packet — candidate C1

Packet date: 2026-08-18

Frozen packet SHA-256:
`ee14b577d98eedac9bd2f9d040856d8bcb01fb50632389e1e9a7979efc930c6a`.

This durable copy preserves the exact normative packet submitted to all three
review routes. It is de-identified and read-only. It grants no deployment,
dispatch, credential, spend, Walk, public, messaging, tool, or business-effect
authority.

## Exact candidate tuple

- Product: `874f7191acc09f32f856b2571e0bcb272ad089df`, parent
  `62972b3113ad179a3014765abe7d585563a27852`.
- Control documents: `ae58569830a7d23c4a1c933b6b5d1c97906782df`,
  parent `ef4c701ef3a343fedbb6a2ec3b79030c6cfaa610`.
- Blueprint: `520911583f38c6d05464319cb11410bf86e5d5db`, parent
  `3442631917c30839367ebc5896f30a96af34ccc4`.

The normative identity is the ordered tuple above plus this packet's frozen
SHA-256. Operational Task Spine state and sealed review receipts are excluded.

## Frozen contract

1. Crawl is one source-grounded, read-only `OBSERVE` workflow on one executor.
   It may make exactly one predeclared `model-0` OpenAI Responses API call using
   `gpt-5.6-sol` at medium reasoning. Provider, DBOS, and application retries are
   zero. Input, output/reasoning, USD-upper-bound, queue, wall, and call ceilings
   are immutable and durably bound before key read or dispatch.
2. The provider edge uses a dedicated project service-account API key only via
   a read-only mode-0600 runtime file. Domain/application code imports no OpenAI
   client. Subscription sessions are forbidden runtime credentials.
3. Disclosure acknowledgment, rights/evidence digests, project/service-account/
   key identity and generation, expiry, provider IDs, complete usage,
   conservative cost upper bound, output/audit digests, release identity, and
   exact replay are durable. Ambiguous send/usage/audit persistence becomes
   sticky `unknown` and never redispatches. Complete authenticated terminal
   provider rejection is `failed`, not `unknown`, and never retries.
4. Tools, remote source fetches, human sends, business effects, Walk, Run,
   public activation, and authority expansion remain disabled.
5. The container is digest-pinned, wheel-only, non-root, read-only,
   capability-dropped, resource-bounded, and has only the allowlisted provider
   egress route. PostgreSQL is the sole durable result truth.
6. Live dispatch and release remain held until exact current evidence exists
   for the dedicated account/project/service-account/key generation and
   revocation; source rights and data-use/retention/region; rate/spend controls;
   SBOM and OS vulnerability state; provenance/signature/approval; dependency
   health/drain; and isolated rollback. The consumer route is not a rollback.
7. Requirements are not weakened to match code. Conflicting historical Stage-0
   assertions are superseded, never rewritten. Stricter rules win.
8. After the audit and all release gates close, Crawl's two value lanes are
   source-grounded architecture/GTM/decision briefs and public-or-synthetic
   discovery/decision-product briefs. Private inputs remain separately gated.
9. The next proposed Walk has exactly three proposal-only families:
   current-state/blocker synthesis; decision/spec/deliverable preparation; and
   evidence/quality review. The first later Run proposal is verified code/doc
   candidates in isolated worktrees. All effects remain separately gated.
10. The conversational supervisor may directionally become a universal front
    door, never a universal data plane or execution authority. Personal lanes
    remain local-only, domain-specific, and minimum-necessary.

## Deterministic evidence supplied

- Product exact-tip: 60 tests / 93 subtests; Ruff, lock, diff, package boundary,
  Compose parse, dependency audit, secret-pattern scan, pinned image build,
  semantic production SLOC 1494, and one-row PostgreSQL concurrency fence.
- Control docs: 53 focused tests, JSON parse, D2 v0.7.1 clean render, visual
  contract, diff check, and exact-tip smoke attestation.
- Blueprint: exact two-path diff check and exact-tip smoke attestation.
- No credential contents, provider call, spend, live mutation, deployment,
  public action, Walk activation, or business effect occurred.

## Verdict contract

Each reviewer was required to return `PASS` only for zero substantiated material
blockers on the exact candidate, otherwise `BLOCK`, with primary evidence.
Reviewers could not vote, force consensus, or treat peer language as evidence.
A PASS would not itself grant any held authority.
