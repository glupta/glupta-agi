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
- the only model route is local `qwen3.6:27b`;
- runtime bearer material is read from a mounted file and never persisted;
- no deployment, activation, live messaging, external effect, or paid service
  is authorized.

The reviewed Stage-0 design remains authoritative in Studio Hub. Its dependency
capture/selection and seven-file Spec Kit promotion gates are independent of
build admission; this repository does not bypass them.

## Developer checks

Core tests use only the Python standard library and can run before dependency
selection:

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The runtime environment and launch commands are added only after their exact
dependency and activation receipts exist.
