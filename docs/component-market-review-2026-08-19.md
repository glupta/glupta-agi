# Glupta component market review — 2026-08-19

## Decision

Crawl should keep its existing maintained runtime, API, schema, database,
evaluation, packaging, and deployment primitives. It should delete the Pydantic
AI runtime bridge around the official Codex SDK and use one native DBOS step for
the single model effect. Pydantic models and Pydantic Evals remain. Pydantic AI
remains the preferred first candidate if Walk demonstrates a real multi-turn,
tool, hand-off, or agent-loop requirement.

No whole-product candidate satisfies the frozen Glupta contract with less
operational surface. No new control plane, memory service, gateway, browser,
sandbox, approval service, secret store, database, sidecar, or deployment
service is justified for Crawl.

This review authorizes no deployment, provider dispatch, credential access,
spend, task drain, stage advancement, external send, or authority expansion.

## Requirement sources and precedence

The comparison used the following current requirement set rather than a generic
agent-feature checklist:

1. The paired canonical Blueprint,
   `obsidian/wiki/operations/debates/greenfield-agent-farm-architecture-v3/idea.md`,
   including its 2026-08-19 subscription-runtime amendment.
2. The greenfield specification,
   `/Users/glupta/Dev/studio-hub/docs/studio-agent-farm-greenfield-spec.md`.
3. The current Studio implementation reference,
   `/Users/glupta/Dev/studio-hub/docs/studio-dbos-agent-system.md`.
4. The current product README, package manifest, source, tests, Compose profile,
   and deployment helpers.
5. The current 0.4.1 held-candidate release evidence under
   `docs/releases/0.4.1-subscription-72b0d7d/`.
6. The final Crawl review fan-in and supported-adapter packet. R1–R10 prompts,
   packets, results, and receipts were treated as immutable incident evidence,
   not current requirements or authority.

Where historical text conflicts, the current Blueprint amendment, project
rules, exact runtime source, and held-release evidence win.

## Frozen Crawl contract

- One useful source-grounded read-only `OBSERVE` result.
- At most 1,500 semantic production Python lines.
- One non-root app executor and PostgreSQL; exactly two steady-state services.
- DBOS owns workflows, steps, queues, scheduling, recovery, replay, retries,
  and application versions.
- PostgreSQL is the only runtime database.
- One predeclared model-effect identity, provider retries disabled, bounded
  request/usage envelope, and sticky `unknown` after ambiguous dispatch.
- Official Codex subscription SDK, one model turn, read-only/deny-all, and no
  tools, web, apps, plugins, MCP, subagents, shell, or actions.
- FastAPI only for admission and health.
- No persistent memory and no custom task, queue, worker, schedule, graph,
  message, model-call, status, telemetry, or eval store.
- Custom code only for product semantics or a measured contract that a
  maintained primitive does not satisfy.

## Current custom baseline

At product commit `b606213`, Crawl has 1,499 semantic production Python lines,
11 production modules, seven direct runtime dependencies, one custom
`crawl_external_effects_v4` table, and two steady-state services. Deployment
adds 922 lines across the metadata-only Codex-volume attestor, private-volume
stager, Colima egress renderer, and after-boot firewall script.

## Scoring method

Candidates were evaluated on current maintenance, real adoption, license,
frozen-contract coverage, privacy, portability, added services/datastores,
operating burden, and net custom code removed. Stars are a maintenance/adoption
signal, not a fitness score. A candidate loses when it duplicates DBOS, adds a
control plane to solve an absent Crawl requirement, or leaves the same
irreducible policy code behind.

Verdicts are `ADOPT`, `RETAIN`, `DELETE`, `DEFER`, or `REJECT`.

### Adoption and maintenance snapshot

Repository metadata was checked on 2026-08-19. Counts are rounded point-in-time
signals and must not be read as architectural scores.

| Family | Candidate | Stars | Declared license / caution | Current signal |
|---|---|---:|---|---|
| Whole product/shell | Provision | 29 | MIT | Created 2026; active but immature |
|  | OpenClaw | 386,796 | README says MIT; GitHub API did not classify it | Very high adoption and active |
|  | Hermes Agent | 232,987 | MIT | Very high adoption and active |
|  | Dapr Agents | 740 | Apache-2.0 | v1.0 documented GA; active |
| Durable runtime | DBOS | 1,536 | MIT | Active selected embedded runtime |
|  | Hatchet | 7,753 | MIT | Active, requires separate service/control plane |
|  | Temporal | 22,399 | MIT | Mature; specified HA fallback |
|  | Restate | 4,310 | Repository metadata did not classify license; legal check required | Active durable alternative |
|  | Dapr | 26,025 | Apache-2.0 | Mature sidecar/runtime ecosystem |
|  | Prefect | 23,643 | Apache-2.0 | Mature workflow platform |
| Agent/model loop | Pydantic AI | 19,396 | MIT | Active and already used |
|  | OpenAI Agents SDK | 28,772 | MIT | Active official orchestration SDK |
|  | LangGraph | 40,030 | MIT | Active graph/checkpoint framework |
|  | AutoGen | 60,521 | GitHub reports CC-BY-4.0; distribution/legal fit needs care | Mature research/agent framework |
|  | CrewAI | 57,329 | MIT | Active multi-agent framework |
| Governance | OpenFGA | 5,625 | Apache-2.0 | Mature authorization service |
|  | OPA | 12,119 | Apache-2.0 | Mature policy engine |
|  | Preloop | 47 | Apache-2.0; advanced/cloud boundaries vary | New, active MCP/AI firewall |
|  | DashClaw | 294 | MIT | New, active approval/receipt gateway |
|  | BoundFlow | 6 | Apache backend/MIT SDK; public preview | Too early for production ownership |
| Secrets | OpenBao | 7,091 | MPL-2.0 | Mature Vault-derived control plane |
|  | Infisical | 28,849 | MIT core with enterprise components | Mature full secrets platform |
| Memory | Letta | 24,305 | Apache-2.0 | Active stateful agent platform |
|  | Mem0 | 63,608 | Apache-2.0 | Active memory service/library |
|  | Graphiti | 30,095 | Apache-2.0 | Active temporal graph memory |
|  | LangMem | 1,619 | MIT | Active LangGraph memory layer |
| Observability | Langfuse | 33,393 | Repository license/package boundaries must be checked for deployment | Active multi-service platform |
|  | Phoenix | 11,113 | Elastic License 2.0, not OSI-approved | Active tracing/eval platform |
|  | OpenLineage | 2,608 | Apache-2.0 | Mature data-lineage standard |
| Gateway | LiteLLM | 56,762 | Repository license/package boundaries must be checked for deployment | Active proxy/control plane |
| Sandbox | E2B | 13,474 | Apache-2.0 | Active hosted sandbox API |
|  | Daytona | 71,960 | Repository metadata did not classify license | Active hosted sandbox platform |
|  | OpenHands | 84,491 | MIT | Active full software-agent platform |

## Component decisions

| Contract piece | Current owner | Strongest current candidates | Evidence and contract result | Verdict |
|---|---|---|---|---|
| Whole product | Glupta modular monolith | [Provision](https://github.com/provision-org/provision-core), [OpenClaw](https://github.com/openclaw/openclaw), [Hermes](https://github.com/NousResearch/hermes-agent), [Dapr Agents](https://github.com/dapr/dapr-agents) | OpenClaw and Hermes are mature assistant shells but do not provide the frozen DBOS/PostgreSQL effect semantics. Provision is the closest product concept but is new and adds PHP, Node, Redis, and a daemon. Dapr Agents 1.0 is the strongest durable alternative but introduces Dapr sidecars, actor/workflow state, and another control plane. | RETAIN Glupta; DEFER optional shell integration |
| Durable workflows, queues, schedules, replay | DBOS | [Hatchet](https://github.com/hatchet-dev/hatchet), [Temporal](https://github.com/temporalio/temporal), [Restate](https://github.com/restatedev/restate), [Dapr](https://github.com/dapr/dapr), [Prefect](https://github.com/PrefectHQ/prefect) | [DBOS workflows](https://docs.dbos.dev/python/tutorials/workflow-tutorial) already provide the selected embedded Python/PostgreSQL owner and workflow-ID idempotency. Alternatives add servers, sidecars, or a second runtime without removing the model-effect ambiguity. Temporal remains the specified HA fallback if permissive self-hosted multi-node recovery becomes mandatory. | RETAIN DBOS |
| Single Crawl model turn | Pydantic AI `Agent(FunctionModel)` bridge around official Codex SDK | Direct official Codex SDK inside native DBOS step; [Pydantic AI](https://pydantic.dev/docs/ai/); [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/); LangGraph, AutoGen, CrewAI | The installed official Codex SDK already accepts the output schema and returns the typed JSON used by the adapter. Pydantic AI currently owns no native provider, tool, hand-off, session, or multi-turn loop; its `FunctionModel` only translates the packet into and out of a custom model response. Its [DBOS capability](https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/) registers a DBOS step around that custom call, which native `@DBOS.step(retries_allowed=False)` supplies directly. The larger frameworks add unused orchestration. | DELETE Crawl runtime bridge; ADOPT direct DBOS step; DEFER Pydantic AI to measured Walk need |
| Typed domain and wire contracts | Pydantic models | msgspec, dataclasses, framework-native schemas | FastAPI and the Codex output schema already use Pydantic. Replacement would duplicate conversion and validation without deleting a subsystem. | RETAIN Pydantic |
| Admission and health | FastAPI/Uvicorn | Starlette, Litestar, Flask, Django Ninja | [FastAPI](https://fastapi.tiangolo.com/) already supplies typed validation, OpenAPI, dependency injection, and the current thin ASGI boundary. No alternative removes meaningful custom code. | RETAIN FastAPI/Uvicorn |
| Runtime database and effect transactions | PostgreSQL, SQLAlchemy, psycopg | SQLite, Redis, vendor state stores | PostgreSQL is frozen as DBOS and product truth. SQLAlchemy/psycopg are maintained primitives already used at the one custom-table edge. Adding another store violates the contract. | RETAIN |
| External model-effect correctness | One custom PostgreSQL effect table | DBOS outbox, provider idempotency, generic workflow engines | DBOS explicitly documents that non-transactional operations may run at least once and must be idempotent in its [outbox example](https://docs.dbos.dev/python/examples/outbox). The subscription Codex route exposes neither a provider idempotency key nor exact request lookup. Therefore a completed DBOS step prevents replay only after checkpoint; it cannot prove non-acceptance across the dispatch/checkpoint gap. The bounded reserve/dispatch/unknown fence is irreducible domain policy. | RETAIN one-table fence |
| Identity, policy, approvals, budgets, audit | Frozen release profile, admission checks, DBOS/effect records; no action approvals in Crawl | [OpenFGA](https://openfga.dev/), [OPA](https://www.openpolicyagent.org/docs), [Preloop](https://github.com/preloop/preloop), [DashClaw](https://github.com/ucsandman/DashClaw), BoundFlow | OpenFGA and OPA answer generic authorization/policy questions but do not own durable human approval or model-effect recovery. Preloop and DashClaw are promising gateways for future action surfaces but add services and overlap the current route; several advanced controls are hosted/enterprise or very new. BoundFlow is pre-1.0 and duplicates lifecycle infrastructure. Crawl has no action authority to approve. | RETAIN small frozen policy structs; DEFER approval gateway until an action stage |
| Secrets | Existing Studio `secret` broker, official Codex login, staged private volumes | [OpenBao](https://openbao.org/), [Infisical](https://infisical.com/docs), Compose secrets | OpenBao and Infisical are capable secret platforms but add a new control plane and secret-zero/migration burden while Studio already has a broker. [Compose secrets](https://docs.docker.com/reference/compose-file/secrets/) restrict grants, but file-backed secrets use bind mounts and [silently ignore UID/GID/mode](https://docs.docker.com/reference/compose-file/services/), failing the non-root immutable-volume contract. | RETAIN existing broker and bounded staging |
| Login-volume metadata proof | Custom metadata-only attestor | Cosign, SLSA/in-toto, OPA | [Cosign](https://docs.sigstore.dev/cosign/verifying/verify/) and [SLSA](https://slsa.dev/spec/v1.2/) bind signatures/provenance to build artifacts. They do not observe the live Docker volume’s owner, mode, labels, and top-level inventory. A generic policy engine would still need a custom collector and the exact same domain assertions. The attestor must remain byte-blind. | RETAIN bounded attestor |
| Persistent memory | None | [Letta](https://docs.letta.com/), [Mem0](https://docs.mem0.ai/introduction), [Graphiti](https://github.com/getzep/graphiti), [LangMem](https://github.com/langchain-ai/langmem) | All add a stateful memory abstraction, service, or graph for a capability Crawl explicitly does not need. Adding one would violate the database/table budget without measured retrieval gain. | RETAIN no component; DEFER to eval-proven need |
| Source retrieval and claim provenance | Admitted inline sources plus domain citation resolver | Vector databases, Graphiti, OpenLineage | Crawl receives bounded sources and validates exact path/line/quote binding. OpenLineage targets data-pipeline lineage, not claim-level source fidelity. A vector store is unnecessary for the current admitted packet. | RETAIN domain resolver; DEFER retrieval service |
| Evals | pytest plus Pydantic Evals | OpenAI Evals, custom harness, LangSmith/Langfuse evals | [Pydantic Evals](https://pydantic.dev/docs/ai/evals/evals/) is code-first, async-capable, and already runs the real inference boundary with fakes. A hosted or stateful eval platform adds storage and disclosure surface. | RETAIN |
| Tracing and observability | DBOS records/logs plus OpenTelemetry-compatible path | [Langfuse](https://langfuse.com/self-hosting), [Phoenix](https://arize.com/docs/phoenix/) | Langfuse self-hosting adds multiple application/storage components. Phoenix is useful for richer AI tracing/evals but adds a service and uses Elastic License 2.0. Crawl has no measured observability gap requiring either. | RETAIN native records; DEFER platform |
| Model gateway and routing | Direct fixed Codex route | [LiteLLM](https://docs.litellm.ai/) | LiteLLM provides routing, budgets, auth, and logging but adds a proxy/database/service and does not replace the native ChatGPT-subscription Codex route. Crawl intentionally has one model and no failover. | REJECT for Crawl |
| Browser, tools, and sandbox | No tools/browser; native Codex read-only/deny-all | [E2B](https://www.e2b.dev/docs), [Daytona](https://www.daytona.io/docs/en/), [OpenHands](https://docs.openhands.dev/openhands/usage/sandboxes/overview) | These solve code execution and interactive tool use that Crawl forbids. They add remote services, credentials, or a full agent runtime. Native Codex restrictions and zero enabled tools are smaller and stricter. | RETAIN no component; DEFER to Run bakeoff |
| Supply-chain provenance and vulnerability evidence | OCI digest, CycloneDX SBOM, Trivy, in-toto provenance, release manifest | Cosign/Sigstore, Docker build attestations/Scout | Standards and scanners are already adopted in the held artifact. [Docker build attestations](https://docs.docker.com/scout/policy/) and Cosign can strengthen later signed distribution, but they do not replace runtime volume/egress checks and some Docker Scout use transmits package/layer metadata. | RETAIN existing offline evidence; DEFER signing activation |
| Community deployment | Docker Compose, one app plus PostgreSQL | Kubernetes, Nomad, Dapr, serverless platforms | Compose exactly matches the frozen two-service/non-root community profile. Orchestrators add services and operational ownership before HA is earned. | RETAIN Compose |
| Default-deny native-route egress | Bounded Colima VM renderer plus nftables/dnsmasq/systemd gate | Envoy/Squid proxy, Cilium, OpenSnitch, Podman networking | Docker documents native iptables/nftables integration but no Compose FQDN allowlist with reboot ordering. Cilium is Kubernetes-specific. Envoy/Squid adds a steady-state proxy and changes TLS/proxy semantics; host firewalls do not prove the exact VM/container route. The current helper composes native Lima/systemd/nftables/dnsmasq and keeps the two-service profile. Retain its documented L3/L4 limitation; a hostile-workload/L7 requirement needs a separate architecture decision. | RETAIN bounded native renderer/firewall |
| Supervisory shell and channels | Outside Crawl | OpenClaw, Hermes, Provision | OpenClaw/Hermes may be useful user-facing shells later, but cannot become source of truth, authority, recovery, or effect ownership. Existing Hermes trial should remain isolated until a measured shell requirement and privacy/authority adapter exist. | DEFER |

## Source-bound bakeoff: Pydantic AI bridge versus direct DBOS step

### Current route

`evidence_brief_workflow` calls a Pydantic AI `Agent` backed by a custom
`FunctionModel`. The bridge:

1. serializes `_CrawlModelPacket` to a user-prompt string;
2. finds and parses that string from Pydantic AI message objects;
3. checks generated union tool names;
4. calls the existing official Codex adapter;
5. converts the typed result or ambiguity into Pydantic AI `ToolCallPart`s; and
6. asks Pydantic AI to validate the union it just constructed.

`DBOSDurability` wraps the `FunctionModel.request` call in a DBOS step with
retries disabled. It does not wrap a native Pydantic provider because none is
used.

### Direct route

DBOS 2.29 exposes `@DBOS.step(name=..., retries_allowed=False)` for async
functions. Outside a workflow the wrapper calls the function normally; inside
a workflow it checkpoints the return or exception as the durable step. Calling
the existing `_run_inference(packet)` through that step preserves:

- the same single durable model boundary and no provider retry;
- the existing typed `ProviderResult` validation in the official adapter and
  domain contracts;
- the same one-table effect reservation and sticky ambiguity behavior;
- the same queue/workflow identity and application version;
- the same faked deterministic tests without a provider call.

It deletes the message translation, generated output-tool contract, synthetic
usage conversion, and a runtime dependency. No alternative framework is added.

### Rejected integration-soup variants

- Pydantic AI plus a direct step: two durability owners for one call.
- Dapr/Temporal/Hatchet around DBOS: two workflow/recovery owners.
- LiteLLM or an approval gateway in front of Codex: a new control plane with no
  Crawl routing/action requirement.
- A memory or observability service: a datastore/service for an absent need.

## Amendment and implementation boundary

Amend Crawl—not the future Farm—to use the direct official Codex SDK inside one
native DBOS step. Retain Pydantic AI in the architecture as a conditional Walk
candidate, activated only when a measured multi-turn/tool/handoff requirement
and an executable bakeoff show net deletion or reliability gain.

Implementation must:

1. add a named async DBOS step with `retries_allowed=False`;
2. route the workflow through it;
3. preserve result and ambiguity behavior on initial execution and replay;
4. remove Pydantic AI runtime imports and dependency, while explicitly retaining
   Pydantic and Pydantic Evals;
5. update current tests and docs without rewriting historical review packets;
6. remain at or below 1,500 production lines; and
7. pass the fixed deterministic, PostgreSQL, package/lock, security, and
   exact-tip review gates before landing.

Deployment and dispatch remain held after implementation.

## Candidate 0.4.2 implementation evidence

The implementation deletes 36 net tracked lines across the runtime, tests,
manifest, lock, and README before adding this report. Semantic production
Python falls from 1,499 to 1,467 lines. The production manifest replaces
`pydantic-ai-slim[dbos]` with an explicit Pydantic dependency; Pydantic AI is
absent from production imports and remains only transitively in the development
environment through Pydantic Evals.

Deterministic local evidence, with no provider call or credential read:

- Ruff: pass.
- Full pytest: 140 passed, 102 subtests passed, 4 environment-gated skips.
- Focused release/workflow boundary: 14 passed plus 5 subtests.
- Disposable PostgreSQL/DBOS 2.29 execution: the success workflow executed
  `crawl_observe_model_v2` once and replayed an identical result without a
  second execution; the ambiguity workflow executed the step once, held on
  initial execution, and held again on replay without re-entering the step.
- All four real-PostgreSQL effect persistence and replay tests passed.
- Diff-scoped deterministic secret/money/send/shell/SQL scan: no candidate
  pattern matched. Manual review found no new route, authority, credential
  read, outbound capability, provider retry, or dependency vulnerability
  surface; the change removes a runtime dependency and preserves deny-all.
- Production semantic line ceiling: 1,467 / 1,500.

The disposable database and container were removed after the bakeoff. The live
0.4.0 app/PostgreSQL pair was not inspected, restarted, or changed.
