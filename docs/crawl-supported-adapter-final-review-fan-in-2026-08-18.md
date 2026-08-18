# Crawl supported-adapter final-review fan-in — 2026-08-18

All routes were assigned the identical candidate whose packet SHA-256 is
`ee14b577d98eedac9bd2f9d040856d8bcb01fb50632389e1e9a7979efc930c6a`.
Results remained sealed until fan-in. This records conclusions, not private
reasoning traces.

## Route results

| Route | Frozen runtime | Result |
| --- | --- | --- |
| Codex | fresh ephemeral read-only `gpt-5.6-sol`, maximum reasoning | `BLOCK`: three substantiated material candidate defects |
| Claude Fable | `claude-fable-5`, maximum reasoning, `advisor_full`, goal `glupta-crawl-030-foundation-audit`, gate `final`, round 0 | `PASS`: zero material blockers, conditional anchors independently confirmed by controller |
| Grok | Grok 4.6, `xhigh`, pinned full launcher | `INCOMPLETE`: initial route and its single allowed availability retry both failed closed with `stopReason='cancelled'` |

The Codex normalized result SHA-256 is
`4315484b59a629b0d0e6b38db118477eb7532fe5e1a2ef2765a0838719c8c4bc`.
The controller independently confirmed the exact commit/parent tuple, clean
worktrees, frozen packet hash, and `gpt-5.6-sol`/medium request contract.

## Substantiated material blockers

1. The OpenAI SDK raises complete authenticated 4xx/5xx responses as typed
   status exceptions, but the adapter converts every `responses.create`
   exception to ambiguous. Terminal provider rejection is therefore recorded
   as sticky `unknown` instead of the contractually required `failed` state.
2. The 300-second HTTPX timeout is an inactivity timeout, not an absolute wall
   deadline. A response that continues producing chunks can occupy the only
   executor beyond the frozen ceiling; the post-return clock check does not
   enforce bounded execution.
3. `validated_result_digest` is computed before citation resolution may mutate
   the returned brief. The resolved result and provider audit are persisted
   without independent row digests, and replay schema-validates without
   recomputing their cross-binding. Exact authoritative replay is not proven.

These are production-code/test defects, not acknowledged account or release
evidence holds. Requirements will not be weakened to make the candidate pass.

## Controller terminal state

`RESTART_REQUIRED`

The audit cannot return PASS: one completed reviewer found substantiated
material blockers, and a second route did not complete after its one allowed
retry. The bounded remediation pass belongs to the already frozen audit and is
exhausted; fixing production code invalidates the candidate identity. A new
implementation loop must correct and verify the three defects, reconcile the
traceability projection, freeze a new exact hash, and restart the final audit.

Dispatch, deployment, credentials, spend, Crawl task draining, Walk, public
activation, broader Hermes activation, tools/actions, authority expansion, and
business effects remain held.
