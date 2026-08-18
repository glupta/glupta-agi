# Crawl foundation restarted final-review fan-in — candidate R1

Candidate R1 is the exact ordered tuple:

- product `fc2dcac4d5d093168b527a424aefcc3be22d1eb7`;
- control `c42394e0ffc96c5baf402627b614b7fb7ca50c9b`;
- Blueprint `95fe95b40eba3f5724ec12bf02aa0ae847f28884`;
- packet SHA-256
  `fa689205173271e4d6f7ea37addc88e6c0d4ad873cae81ee990d8a10a2ea8dc1`;
- 68-entry source-manifest SHA-256
  `817a18c4ca4b3a5eee9b712bbcbd1d274e88801ba446f09ac1958e2a21043a67`.

All reviewers received the same prompt and exact candidate identity. Results
remained sealed until every route had reached its terminal state. This document
records conclusions, not private reasoning traces.

## Route results

| Route | Frozen runtime | Result |
| --- | --- | --- |
| Codex | fresh ephemeral read-only `gpt-5.6-sol`, maximum reasoning | `RESTART_REQUIRED`: five substantiated production defects |
| Claude Fable | `claude-fable-5`, maximum reasoning, `advisor_full`, goal `glupta-crawl-foundation-restart-audit-20260818`, gate `final`, round `0` | `PASS`: zero substantiated material blockers |
| Grok | Grok 4.6, `xhigh`, pinned full launcher | `INCOMPLETE_REVIEW`: initial route and its single allowed retry both ended in permission-cancelled evidence collection and tool-disabled incomplete synthesis |

The Codex result SHA-256 is
`7b9722bdd5495272bc16bcf9af04a539d609f2449a0b60f21b2cab4855846aef`.
The initial and retry Grok receipt SHA-256 values are respectively
`e6b7cb88868eb320c17d00f0b31c302a6b7045c8ad18cc300250dbdfcb49a0d2`
and
`231b9e7d2901ebecc18b5afc27cfa093f30e0d35928d0e478c5c6d64d55229c8`.
The Grok route exhausted its one availability retry; no provider or API
substitution was used.

## Substantiated material blockers

Codex validated both top-level hashes and all 68 manifest entries at their
pinned Git commits before classifying these defects:

1. A failure while persisting `returned` or `reconciled` after provider dispatch
   can escape as an ordinary DBOS model-step error instead of becoming a sticky
   ambiguous effect. The candidate does not prove no redispatch after uncertain
   post-dispatch commit.
2. The durable workflow, API, and client response omit the provider audit,
   request/response IDs, usage, and conservative cost that the packet and README
   claim initial completion and replay return.
3. The first-party loopback client builds an opener without explicitly disabling
   ambient HTTP proxies, so hostile proxy configuration can route the bearer
   outside the intended direct loopback transport.
4. A completed provider response followed by cleanup-only deadline expiry is
   converted to terminal `failed`, rather than the binding sticky `unknown`
   classification.
5. `glupta_agi.__version__` exports `0.2.10` while package metadata, FastAPI,
   DBOS runtime metadata, README, and the candidate identity declare `0.3.0`.

These are production-code and test defects, not acknowledged external release
holds. Requirements are not weakened to match the implementation. Fable's PASS
does not override substantiated primary evidence, and Grok's incomplete route is
not counted as agreement or a vote.

## Controller terminal state

`RESTART_REQUIRED`

R1 remains immutable and dispatch-disabled. Repair is a separate production
implementation loop and therefore invalidates this baseline. A new candidate
must fix the five defects, rerun deterministic verification, reconcile affected
traceability, freeze new exact hashes, and restart blind final review.

Deployment, provider dispatch, credential access or creation, spend, task
draining, Walk, public activation, authority expansion, broader Hermes,
tools/actions, outbound effects, signing, trading, transfers, and money movement
remain held.
