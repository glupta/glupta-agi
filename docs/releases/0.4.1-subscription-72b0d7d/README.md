# Crawl 0.4.1 subscription artifact evidence

This directory binds the locally built `linux/arm64` Crawl image
`sha256:08ef38c9d4c85501005a85abf923debb2a95244c8cb4f4243528d84520d910ad`
to landed source revision `72b0d7dc4c984d5c32fd1708788efcec06a26930` and tree
`227caa8c4ce88f424f06ab907f420bf6357dda41`.

BuildKit generated embedded SPDX and SLSA v0.2 statements. The detached
CycloneDX SBOM and Trivy report were generated from the exact local image
digest with Trivy 0.74.0 in offline mode against the database updated at
`2026-08-18T18:30:40.017638579Z`; they report zero vulnerability and zero
secret findings. Runtime inspection proved Glupta AGI 0.4.1, Codex CLI 0.147.0,
non-root UID/GID 65532, and the exact source/version labels.

An isolated synthetic rehearsal proved cold start, restart, rollback to the
deployed 0.4.0 image, forward restore, two-service steady state, cleanup, and a
metadata-only attestation of the existing subscription authentication volume.
It made no intake request and no provider dispatch.

The exact recovery candidate also passed the bounded frontier gate in the
required order: Codex gpt-5.6-sol/max first, then Claude Fable/max and Grok
4.6/xhigh, all against the same packet and candidate tree. The packet contains
the concise deduplicated release-incident ledger, including setup, container,
build, deployment, restart, rollback, and canary learnings.

This is evidence, not release authority. Signing the final artifact manifest,
projecting the matching release profile, zero-provider deployment, and a fresh
controlled canary remain independent gates. The original 0.4.0 canary workflow
remains permanently sticky unknown and must not be replayed or retried.

`release-manifest.json` is the machine-readable index. Its evidence hashes
cover sibling files but intentionally do not self-hash the manifest.
