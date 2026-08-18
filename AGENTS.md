# Glupta AGI project rules

The canonical architecture is the final amended DBOS-first greenfield agent-farm
Blueprint in `obsidian/wiki/operations/debates/greenfield-agent-farm-architecture-v3/idea.md`.
The working Studio implementation in
`/Users/glupta/Dev/studio-hub/docs/studio-dbos-agent-system.md` is reference evidence,
not code to transplant.

Before an architectural or runtime change, compare the proposal with both sources.
Preserve these constraints:

- Build a small ports-and-adapters modular monolith. DBOS owns workflows, steps,
  queues, schedules, replay, retries, and application versions.
- Prefer maintained third-party primitives. Custom code is limited to irreducible
  product, privacy, budget, authority, and promotion policy.
- Before adding or changing any component, dependency, service, adapter, or
  control primitive anywhere in the Glupta stack, record a current
  build-versus-adopt check against official/native capabilities and relevant
  maintained open-source alternatives, including lightweight generic
  frameworks. Genericity is not a disqualifier: adopt the maintained primitive
  when it satisfies the frozen contract and materially removes custom code or
  operational burden. Any custom layer must name the exact missing contract and
  prove it with regression tests.
- Progress by measured stages. Crawl is one useful source-grounded read-only
  `OBSERVE` task at or below 1,500 production lines. Do not activate DIRECT,
  COMPOUND, or EXECUTE before the next stage is earned and explicitly approved.
- Treat Pydantic AI's single-agent, delegation, programmatic hand-off, and graph
  patterns as increasing complexity choices, not four components to install.
  Crawl uses only the simplest pattern that its measured task requires.
- Every external model or tool dispatch needs a predeclared durable effect identity,
  bounded budget, disabled provider retries, and fail-closed ambiguous recovery.
- FastAPI is admission and health only. PostgreSQL is the sole runtime database.
  Community deployment is one non-root app executor plus PostgreSQL.
- Do not add a custom scheduler, queue, worker system, graph engine, task/memory
  store, message bus, eval platform, provider framework, or compatibility layer.
- A stage advances only after a useful end-to-end result and its fixed gates pass.
  Prefer deleting a losing component to surrounding it with more control code.

If a requested change conflicts with the Blueprint, stop and surface the conflict
instead of silently implementing a parallel architecture.
