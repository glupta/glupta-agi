# Crawl foundation R8 frontier-review receipt

Review date: 2026-08-18

Terminal state: `RESTART_REQUIRED`

## Exact frozen identity

- Product: `3bb568a2885132d584717cbed63f3cc08c99916e`
- Control: `52248283708cf2e489102c705e5775625f55cee6`
- Blueprint: `de4d7e439d67b3823a2c8fbff88f99c6112ccc0f`
- Packet SHA-256: `96f25dada6013bec33a2ac9cc683be2dbe8b628ed096efd2adc94fa0fcaab37c`
- 64-entry manifest SHA-256: `4e196fc0712814d0e05845cdb0ba45a27f3af2c8fe6538a701ca23da9d446995`
- Prompt SHA-256: `fb45d29d7d41025933ebf77a51408b36db30545a621545c727a58297da176e61`
- Schema SHA-256: `c2528480855d6578c5d1f8a1cde59f2b9ce3d96dd59749bd31b7da7d059b3b84`
- Native Codex result SHA-256: `2ec48d8e3b93f58769472df435bd6442d78cc5c09a23b49b42f2c7c99ed2c306`

Mechanical preflight independently matched every top-level hash and all 64
Git-object manifest entries. The result validates against the frozen schema.

## Route and ordering

Fresh native Codex ran read-only with `gpt-5.6-sol`, maximum reasoning,
ephemeral mode, shell snapshots disabled, project root `/Users/glupta/Dev`, and
the exact output schema. It returned two substantiated material blockers.
Therefore the Codex-first hard gate terminated the round and neither Fable nor
Grok was invoked.

## Material blockers

1. The existing-effect identity-conflict path escapes reservation as raw
   `RuntimeError`, retaining admitted-source data in workflow traceback locals
   instead of crossing a fresh sanitized domain boundary.
2. Runtime/API/DBOS and package versions currently match `0.3.0`, but
   `pyproject.toml` and `__init__.py` independently declare the version rather
   than resolving from one canonical source as the frozen contract claims.

R8 is immutable rejected evidence. Dispatch, release, credential, spend,
deployment, task-drain, Walk, public, Hermes, tools/actions, outbound, signing,
trading, transfer, and money authority remain held. No production rollback is
required because R8 was not deployed.
