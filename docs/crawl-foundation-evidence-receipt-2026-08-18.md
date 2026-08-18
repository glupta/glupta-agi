# Crawl foundation evidence receipt — 2026-08-18

Captured by the controller at `2026-08-18T15:20:46Z`. This is a de-identified,
read-only evidence projection. It contains no source packet body, model response
body, credential value, environment value, or private data.

## Runtime

- `/healthz`: `{"status":"healthy","stage":"Crawl","actions":"disabled"}`
- app image: `sha256:c8f66b2f106d3c3d6f313bd2313e7614c92f868b6b8f75c5e4ab1d3e4c6db9ad`
- PostgreSQL image: `sha256:f3bd19c606e442c3d7bdfa8002e03fe260a1023351e0ea4598032022b68dd6e3`
- both containers: running, healthy, restart count `0`
- workflow inventory: `100` total; `96 SUCCESS`, `4 ERROR`, `0` active

The workflow inventory was read through DBOS `SystemDatabase` with inputs and
outputs explicitly disabled and listen/notify disabled. No workflow was
launched, recovered, or mutated. Direct SQL was not used.

## Representative outcome 1 — OpenRec diligence

- workflow ID: `01a0154b-bad3-7680-a72c-825b9932e4bc`
- request digest: `acee275c00a37421f0da1a7871aabd7388efc42aef430eaac0d63f21ace2bbf3`
- input packet SHA-256: `ea0f460ef95ac83e688764cd4b208d7d5fa959380ad79418baa1c28829dc455a`
- DBOS status: `SUCCESS`; application version `0.2.10`; queue
  `crawl-observe-v1`; recovery attempts `1`
- native model steps: exactly one `crawl_observe_agent__model.request`
- typed result: four citations, eight uncertainties, one decision
- usage: input `5813`, cache read `0`, output `2751`, reasoning output `1142`;
  USD cost unavailable
- first-party client replay SHA-256, twice:
  `ae989cec0b8ace6b321b330b30365a7aee8de583bd39134caffe0470745df474`
- independent usefulness: one bounded disposable synthetic trial may be useful;
  private-meeting use remains blocked on provenance, consent, data-flow,
  deletion, exportability, reliability, retention, and webhook evidence

## Representative outcome 2 — Block architecture review

- workflow ID: `01a0154b-bad3-7680-a72c-825c68f59019`
- request digest: `2ddfe6175fc4bdb3c8683ac8fc2be8b473431b27df4fcbf60d5b4b5be53b5aea`
- input packet SHA-256: `a711f747c536915091cda88b9179d231f7e3490e0ce0149a57fa30da6d018c98`
- DBOS status: `SUCCESS`; application version `0.2.10`; queue
  `crawl-observe-v1`; recovery attempts `1`
- native model steps: exactly one `crawl_observe_agent__model.request`
- typed result: four citations, five uncertainties, one decision
- usage: input `5616`, cache read `2816`, output `2199`, reasoning output `1034`;
  USD cost unavailable
- first-party client replay SHA-256, twice:
  `6d98ea4ebd48601905a1d86d358741e50062fb1ae5e4dee745a1b9b530292338`
- independent usefulness: test narrowly through one preregistered read-only
  shadow experiment; do not adopt unproven hierarchy or “world model” claims

## Effect-state evidence and limitations

For each successful outcome, the observed single native model step plus exact
replay is consistent with one `model-0`, `max_calls=1` effect. The terminal
`reconciled` state is derived from the exact code invariant that transitions
`returned` to `reconciled` before returning the typed response; the application
effect row was not queried because direct database access is outside the
approved operating path. This receipt proves the narrow outcomes and replay
boundary, not provider contractual conformity, complete budget enforcement,
OCI release provenance, or Walk readiness.

## Controller checkpoint

- path: `/Users/glupta/.claude/checkpoints/glupta-mvp-blueprint-drain-20260818.md`
- SHA-256: `c6a5ba87b050049a8f1f5183791fb751e2475d0c03df846b74786e1a26e0fe72`
