# Crawl foundation initial review fan-in — candidate C1

All three reviewers received identical candidate bytes with framed SHA-256
`fdcb356278b4e8cfdbdb3963c9804d3c6a4b16a97b1d1de3377ac59ff36d7041`.
Results were sealed until fan-in. This normalization records conclusions, not
private chain-of-thought.

## Routes

| Route | Runtime | Result |
| --- | --- | --- |
| Codex | `gpt-5.6-sol`, maximum reasoning, Codex CLI `0.147.0`, fresh read-only session `01a0155c-235c-7100-a214-710849ab5042` | `REVISE_CANDIDATE` |
| Claude Fable | `claude-fable-5`, maximum reasoning, `advisor_full`, goal `glupta-crawl-foundation-audit-20260818`, gate `plan`, revision `0` | `REVISE_CANDIDATE` |
| Grok | Grok `4.6`, `xhigh`, pinned full launcher, fresh request `e9065f38-2545-42bc-84d2-f9a5db21acc4` | `revise` |

Grok's first route attempt ended `cancelled`; the one charter-permitted
availability retry completed normally. No other route used a retry.

## Converged material findings

1. The successful outcome, runtime, replay, and checkpoint evidence had to be
   hash-bound rather than asserted only in prose.
2. The current headless consumer-subscription route is nonconforming. It must
   remain held; a future external route must be provider-supported and satisfy
   disclosure, credential, budget, retry, audit, isolation, and release floors.
3. `max_calls=1` is necessary but insufficient without immutable input/output/
   reasoning-token, USD, wall-time, and queue-time ceilings.
4. `0.2.10` is an evidence baseline, not a conforming release or rollback
   artifact. Read-only root, resource limits, exact manifest, SBOM, provenance,
   signature, rollback rehearsal, and current approval remain open.
5. The exact current-stage matrix must include Crawl `T-GF-042` and Womb
   `T-GF-050`, `051`, and `053`; stale Ollama/local-private/no-effect branches
   and the 2026-08-13 receipt must be explicitly superseded, never rewritten.

## Controller reconciliation

Primary evidence supports a partial contract/traceability rebuild. Keep the
working DBOS/PostgreSQL read-only core, typed citations, effect fence, retry=0,
ambiguity hold, and no-tool/no-action boundary. Hold the inference adapter and
release rail. Preserve all open gaps. Make no production-code change. Walk,
public activation, broader Hermes, authority expansion, and effects remain
frozen.

One reviewer could not resolve the active checkpoint from its default working
directory. The controller verified the checkpoint directly and bound its exact
path and digest in the evidence receipt. This factual correction does not change
the disposition. There was no irreducible material disagreement.
