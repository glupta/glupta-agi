# Crawl foundation final-review fan-in — candidate R4

Candidate R4 is the exact ordered tuple:

- product `8efd3cc1907a2887a6e6c3822b70e1fe0b350ade`;
- control `cfed13c41fe2ae5affb21f12537b5b6ad9eb3e35`;
- Blueprint `b80838e8c4d2fbba4aa472e051fc440d4254d904`;
- packet SHA-256
  `a82235751f7a60cd29cce07252b8e89ee202b5fb8f7c2f5a249ac60330083a78`;
- 46-entry source-manifest SHA-256
  `c8293db7d7cb23b9bd1872f1dcfd311fad8ec0ace47795aa4a769cee453d49ba`.

The fresh native Codex route validated both top-level hashes, all three Git
roots, and every manifest entry before judging. The controller did not invoke
Fable or Grok because the global frontier-review gate requires Codex to find
zero substantiated material blockers first. No peer output existed to
contaminate the review, and no peer review round or availability retry was
consumed.

## Route result

| Route | Frozen runtime | Result |
| --- | --- | --- |
| Codex | Codex CLI 0.147.0; fresh ephemeral read-only `gpt-5.6-sol`; maximum reasoning; session `01a016bf-b9b2-71e1-b89b-1423c4fa5872` | `RESTART_REQUIRED`: four substantiated material blockers |
| Claude Fable | not invoked | gated off by Codex result |
| Grok | not invoked | gated off by Codex result |

The normalized structured Codex result SHA-256 is
`bd9e33fb39da6ff8c05e8ec336443ef090171d719c2260df4754579fe8ae0250`.

## Substantiated material blockers

1. The release profile's credential and project identity are not guaranteed to
   be the identity sent on the wire. The pinned official SDK accepts ambient
   project, organization, and custom-header configuration; a hostile environment
   can replace `Authorization` even though the adapter passes an explicit key.
2. Non-`APIStatusError` provider, parser, validation, and credential-decoding
   failures retain sensitive underlying exceptions through cause chains.
3. Usage validation does not enforce provider-defined subset relations. The
   exact adapter accepted `reasoning_tokens=4000` with `output_tokens=1`, which
   can understate the recorded conservative cost and survives replay validation.
4. The durable effect boundary does not carry and recompute the disclosure
   profile, notice digest, and acknowledgement. The eval path can dispatch with
   a question-and-sources digest and no explicit bound acknowledgement.

These are code/contract defects, not acknowledged external release holds. The
smallest safe disposition is a separate repair loop retaining the official
OpenAI SDK and existing modular-monolith/state-machine architecture, adding no
gateway, framework, queue, store, retry layer, or authority.

## Controller terminal state

`RESTART_REQUIRED`

R4 is immutable rejected audit evidence. It does not run Fable or Grok, force
consensus, weaken requirements, or amend production inside the frozen baseline.
Its repair must form a new exact candidate with newly reconciled control and
Blueprint identities and restart the Codex-first review.

Deployment, provider dispatch, credential access or creation, spend, task
draining, Walk, public activation, authority expansion, broader Hermes,
tools/actions, outbound effects, signing, trading, transfers, and money movement
remain held.
