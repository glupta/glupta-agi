# Crawl foundation final review fan-in — candidate C2

Candidate C2 was the sole amended candidate. All three reviewers received the
same exact bytes with framed SHA-256
`8b24160a6e132e858937491418a7fcbe074e3c7cb4d750a155f1964737201874`.
The packet SHA-256 was
`5fa4df93e592794221644bfd59d061f9a60d736868971f9a0477a54eddf7e5b6`;
the 64-entry manifest SHA-256 was
`b33fb1c03a563a3a21693f54dbceb419f1a7514ae2039f4b75a0904b301d2cfe`.
Results were sealed until all routes completed. This document records
conclusions, not private chain-of-thought.

## Routes

| Route | Runtime | Result |
| --- | --- | --- |
| Codex | `gpt-5.6-sol`, maximum reasoning, fresh ephemeral read-only Codex CLI session | `HOLD_MATERIAL_DISSENT` |
| Claude Fable | `claude-fable-5`, maximum reasoning, `advisor_full`, goal `glupta-crawl-foundation-audit-20260818`, gate `final`, revision `0` | `PASS` |
| Grok | Grok `4.6`, `xhigh`, pinned full launcher, request `f1b4e46b-085a-4d70-8519-6f69bf0cd1ba` | `PASS` |

All three routes completed normally. No final route used an availability retry.
The Codex normalized result had SHA-256
`3f5c06143f8151e2d55f81f88e51f87925c474f9c95e8e7952a8cb578523f75a`.
The Grok launcher receipt had SHA-256
`fe3da0e1144fc2796ed955ff8399f283a529f8610f7d36599dec06eace473018`.

## Verified agreement

The reviewers agreed that C2 preserves the working DBOS/PostgreSQL read-only
Crawl core, typed cited output, the durable one-slot effect fence, retry zero,
fail-closed ambiguity, and disabled tools/actions. They agreed that production
code and historical receipts were not rewritten, the consumer-subscription
route remains evidence-only and held, `0.2.10` is not a conforming release or
approved rollback, and dispatch remains held until the provider adapter,
disclosure, budget, isolation, provenance, rollback, release, and product-test
gates close. The foundation disposition remains a partial contract and
traceability rebuild rather than a product-core rebuild.

## Material disagreement

The exact packet's charter defines the final terminal states as `PASS`,
`HOLD_MATERIAL_DISSENT`, `HOLD_EVIDENCE`, `INCOMPLETE_REVIEW`, and
`RESTART_REQUIRED`, caps the audit at two candidate hashes, and permits one
remediation pass. Its later `Required reviewer output` section still asks for
the C1-era `PASS_CANDIDATE` or `REVISE_CANDIDATE` vocabulary and a further
amendment before a blind final review.

This factual inconsistency is present in the frozen bytes. Codex classified it
as a material internal-contract blocker. Fable and Grok independently found the
same stale section but classified it as non-blocking because the dedicated
final-review prompt and earlier charter control. Primary evidence establishes
the defect but does not eliminate the materiality dispute without changing the
already frozen protocol.

## Controller terminal state

`HOLD_MATERIAL_DISSENT`

The protocol defines agreement as three completed reviews finding zero
substantiated material blockers, not a vote. That condition is not met. The
single remediation pass and two-candidate cap are exhausted, so the controller
will not silently create C3 or rewrite C2. Crawl dispatch, deployment, Walk,
public activation, broader Hermes, tools/actions, authority expansion, and
external effects remain frozen. A later audit may start only from an explicitly
authorized new baseline whose reviewer contract is internally consistent.

