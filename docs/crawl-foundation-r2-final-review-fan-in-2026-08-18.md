# Crawl foundation final-review fan-in — candidate R2

Candidate R2 is the exact ordered tuple:

- product `ea20b5e2a44a5cf2178eca63d20f94e6f3e88883`;
- control `b86dc04dd6cb9b3a7d6a14ef14bd5d01b06c6a3e`;
- Blueprint `9f889d252242c2a0c86563701c0de6bd68f7475a`;
- packet SHA-256
  `0548e7015c46f2a02d86b12f2cb2106d9a07b75bc77392b6f476a1fa0522a527`;
- 43-entry source-manifest SHA-256
  `27a6a67ac872f80505459d2b0925adb784fb598d19f0e77f8924e50fef7147ec`.

The fresh native Codex route validated both top-level hashes, all three Git
roots, and every manifest entry before judging. The controller did not invoke
Fable or Grok because the global frontier-review gate requires Codex to find
zero substantiated material blockers first. No peer output existed to
contaminate the review, and no peer review round or availability retry was
consumed.

## Route result

| Route | Frozen runtime | Result |
| --- | --- | --- |
| Codex | Codex CLI 0.147.0; fresh ephemeral read-only `gpt-5.6-sol`; maximum reasoning; session `01a01668-e285-72f3-94cf-18536e4b05e2` | `RESTART_REQUIRED`: three substantiated material blockers |
| Claude Fable | not invoked | gated off by Codex result |
| Grok | not invoked | gated off by Codex result |

The exact structured Codex result SHA-256 is
`207bed7d6a2da42d1571f9c232cee9837c8fa461a7423ecfcc677cfb7264b86a`.

## Substantiated material blockers

1. The real effect store cannot convert an ambiguously committed `failed` row
   to sticky `unknown`: `hold_unknown` excludes `failed`, while the workflow's
   mocked persistence matrix can rewrite arbitrary states and therefore masks
   the SQL-state defect. A later replay can treat the surviving row as
   definitively failed without the required exact readback proof.
2. When an authenticated provider rejection is followed by cleanup deadline
   expiry, the raised `ProviderRejectedError` bypasses the later
   `cleanup_ambiguous` check. The combined path is returned as definitive
   failure instead of sticky unknown and has no regression test.
3. The documented Pydantic Evals quality loop is non-executable:
   `evals/runner.py` synchronously unpacks the asynchronous `_run_inference`
   coroutine. The existing eval tests do not execute `run_eval`, and the exact
   source probe raises `TypeError`.

These are code/test and truthfulness defects, not acknowledged external release
holds. The open account, rights, provider-terms, spend, egress, supply-chain,
drain, approval, and rollback gates remain accurately held and were not treated
as defects merely because they remain open.

## Controller terminal state

`RESTART_REQUIRED`

R2 is immutable audit evidence. The bounded audit exhausted its second/final
candidate hash and one production remediation pass. It does not run Fable or
Grok, force consensus, weaken requirements, or amend production inside the
frozen baseline. Any repair is a separate implementation loop and must freeze a
new audit contract before another final review.

Deployment, provider dispatch, credential access or creation, spend, task
draining, Walk, public activation, authority expansion, broader Hermes,
tools/actions, outbound effects, signing, trading, transfers, and money movement
remain held.
