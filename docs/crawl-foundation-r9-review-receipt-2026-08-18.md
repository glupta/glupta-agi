# Crawl foundation R9 frontier-review receipt

Review date: 2026-08-18

Terminal state: `RESTART_REQUIRED`

## Exact frozen identity

- Product: `8fb16e1433839f92600be4e8d310de1c4469c568`
- Control: `b18cfd753376cd29ba8efd37a15447361f064835`
- Blueprint: `87bdb5aa03e5c4775ef336a1535b2a961419b925`
- Packet SHA-256: `2fe9b95461d66f745475f9f9bda11bc9486d47984b773150e0e9053ab06f1ed7`
- 70-entry manifest SHA-256: `a52bd82ad128d83658c7719b042335563bce2db2cb7699adf1b7ce66c7d71706`
- Prompt SHA-256: `ff908ef04099f124c29d114bc0bedff7cccd2a1a4674d2c8861780f2e8bf1c3c`
- Schema SHA-256: `9f69fde9cb6be1504e540ce586d320b9c557d9b3fe51306b54dc6a7d692ed4fe`
- Native Codex result SHA-256: `4cdd19712d2165453262737ebf1daa833680c3dfaf5f2a28b11ee8309a8ced47`

Mechanical preflight independently matched every top-level hash and all 70
Git-object manifest entries. The result validates against the frozen schema.

## Route and ordering

Fresh native Codex ran read-only with `gpt-5.6-sol`, maximum reasoning,
ephemeral mode, shell snapshots disabled, project root `/Users/glupta/Dev`, and
the exact output schema. It returned one substantiated material blocker.
Therefore the Codex-first hard gate terminated the round and neither Fable nor
Grok was invoked.

## Material blocker

Actual private-file and configuration rejection paths retain synthetic raw
private-file bytes, a complete short intake token, and a database password in
production traceback-frame locals. Existing tests covered formatted traceback
text and exception chains but not the stronger capture-locals property required
by the frozen confidentiality contract.

R9 is immutable rejected evidence. Dispatch, release, credential, spend,
deployment, task-drain, Walk, public, Hermes, tools/actions, outbound, signing,
trading, transfer, and money authority remain held. No production rollback is
required because R9 was not deployed.

