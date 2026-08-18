# Crawl foundation final-review fan-in — candidate R3

Candidate R3 is the exact ordered tuple:

- product `cf4cd2ce0867244774a56324fdd20cbd2a606273`;
- control `e32792bd552b7542f09208dbfe077fd689125d4c`;
- Blueprint `8223c73c60c66deb3ed97e0889b46ed7c8d3f488`;
- packet SHA-256
  `73b66f2033cc8c6e72d4dc05b79e9a13f5d2a3556d2c7dceeb49e7677968b798`;
- 45-entry source-manifest SHA-256
  `e3ed24290f0a52fabc8dcfd50eca6671b63cd585f50c7f50cb0decbea3f3ec29`.

The fresh native Codex route validated both top-level hashes, all three Git
roots, and every manifest entry before judging. The controller did not invoke
Fable or Grok because the global frontier-review gate requires Codex to find
zero substantiated material blockers first. No peer output existed to
contaminate the review, and no peer review round or availability retry was
consumed.

## Route result

| Route | Frozen runtime | Result |
| --- | --- | --- |
| Codex | Codex CLI 0.147.0; fresh ephemeral read-only `gpt-5.6-sol`; maximum reasoning; session `01a0169c-a4ea-7432-82c5-76080f85bac4` | `RESTART_REQUIRED`: one substantiated material blocker |
| Claude Fable | not invoked | gated off by Codex result |
| Grok | not invoked | gated off by Codex result |

The normalized structured Codex result SHA-256 is
`79a0df1fa8851394849ddc01e788b8eac527fe442b8c0a80cfd862c700826ad4`.

## Substantiated material blocker

The adapter treats every OpenAI `APIStatusError` as a definitive provider
rejection. That class also covers HTTP 408 and 5xx responses where acceptance,
execution, usage, or charging may be uncertain. The frozen contract requires
those unproved outcomes to become sticky `unknown`, but the exact candidate
persists them as terminal `failed`; its HTTP 500 regression test encodes the
same wrong classification. This is an external-effect state-machine defect,
not an acknowledged release hold.

The smallest safe disposition is a separate implementation loop that retains
the official SDK and existing state machine, introduces no framework or
dependency, classifies only proved non-acceptance as terminal rejection, maps
408/409/429/5xx and every otherwise unproved case to `ProviderAmbiguousError`,
and proves sticky unknown/no-redispatch through adapter, workflow, replay, and
real PostgreSQL tests.

The three R2 blockers are otherwise closed in R3. The open account, rights,
provider-terms, spend, egress, supply-chain, drain, approval, deployment, and
rollback gates remain accurately held and were not treated as defects merely
because they remain open.

## Controller terminal state

`RESTART_REQUIRED`

R3 is immutable rejected audit evidence. It does not run Fable or Grok, force
consensus, weaken requirements, or amend production inside the frozen
baseline. Its repair is a separate implementation loop and must freeze a new
audit contract before another final review.

Deployment, provider dispatch, credential access or creation, spend, task
draining, Walk, public activation, authority expansion, broader Hermes,
tools/actions, outbound effects, signing, trading, transfers, and money
movement remain held.
