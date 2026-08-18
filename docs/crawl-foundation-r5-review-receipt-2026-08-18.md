# Crawl foundation R5 review receipt — 2026-08-18

Terminal state: `RESTART_REQUIRED`

## Exact frozen tuple

- product: `67f1b418ce308091b2dd7476bda32ede8df957c0`
- control: `4b8c468b871918d9113770a04fe3993d09040dbf`
- Blueprint: `6104558f4e7885f27ad176339000c794c39ec5c8`
- packet SHA-256: `b7ff94a6970557a451b20d56465cb4debbd2e125b15e9f928b3f0a3a48da29bd`
- 46-entry manifest SHA-256: `8c4e0693f0543d6bdd892380cb4b49b2e206ffe906575942cb95231df259ed60`
- native Codex result-output SHA-256: `b3fef08d2ecd4d6bee12e205a6fd0fa75bfc09e0a91bf2b766a13a427b9c43b6`
- tracked result JSON SHA-256: `6f0550b4a1b3f47e35576c800333361c6bcb416f07a4d13f939b2e32f7de942c`

## Gate result

Fresh native Codex `gpt-5.6-sol` at maximum reasoning completed with one
substantiated material blocker. The Responses API request omitted
`service_tier`, inherited mutable project `auto` behavior, and could select
Fast/Priority pricing above the frozen Standard USD reservation while the audit
persisted the lower Standard estimate.

The Codex-first gate therefore did not invoke Fable or Grok. R5 is immutable
rejected evidence. A separate bounded R6 repair must bind explicit
`service_tier="default"` through the release profile, frozen dispatch, exact
request, provider audit, returned response, effect record, and replay checks,
then restart exact-candidate review on new identities.

No deployment, provider dispatch, credential access, spend, queue drain, Walk,
public, Hermes, or outbound activation occurred or is authorized by this
receipt.
