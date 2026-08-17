# glupta agi

Private, public-shaped source repository for Glupta AGI (Artificial Glupta
Intelligence).

## Crawl MVP

The first vertical slice is `evidence_brief_v1`: an authenticated loopback API
accepts one question and up to 20 explicitly selected UTF-8 Markdown or text
files from a read-only input root. It produces a typed, source-grounded brief
with resolvable file-and-line citations, uncertainties, and next decisions.

Current build state:

- secure intake and request canonicalization are implemented;
- DBOS owns durable execution and idempotency;
- Pydantic AI owns the typed, single-pass Ollama route;
- the only model route is local `qwen3.8:27b`;
- later model upgrades require a new exact local-artifact amendment;
- runtime bearer material is read from a mounted file and never persisted;
- local Docker deployment is supported on loopback only;
- no live messaging, external effect, or paid service is present.

The Crawl acceptance boundary is this repository: one useful local evidence
brief, durable workflow state, authenticated loopback intake, explicit local
files, and no external effects. Later-stage architecture and release controls
do not block this private MVP.

## Developer checks

Core tests use only the Python standard library and can run before dependency
selection:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

## Local deployment

The build may access official package and image registries. Application model
and database routes are limited to PostgreSQL and the existing host Ollama
endpoint; the API is published only on `127.0.0.1:8765`.

Create `inputs/`, then place private mode-`0600` random values at
`runtime/intake-token` and `runtime/postgres-password`. Start the service with:

```sh
docker compose up --build -d
curl --fail http://127.0.0.1:8765/healthz
```

Submit only explicitly selected `.md` or `.txt` files from `inputs/`. The
bearer capability is required for `/v1/evidence-brief` and is never committed.
