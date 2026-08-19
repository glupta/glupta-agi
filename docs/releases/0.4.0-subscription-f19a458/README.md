# Crawl 0.4.0 subscription artifact evidence

This directory binds the locally built `linux/arm64` Crawl image
`sha256:6f8af6a08661f8315d1285e8764ec8b260097426ccd3b8c6d937218250bc9850`
to landed source revision `f19a458246de6529e7fcfc61f94498a3401dc12d` and tree
`7b4cdefe994eded88377dbbeb375748f5d3f3d17`.

BuildKit generated an embedded SPDX SBOM and SLSA v0.2 provenance statement.
The detached CycloneDX SBOM and Trivy report were generated from the exact local
image digest with Trivy 0.74.0 in offline mode against the database updated at
`2026-08-18T18:30:40.017638579Z`. The report contains zero vulnerability and
zero secret findings. Runtime inspection proved Glupta AGI 0.4.0, OpenAI Codex
SDK/runtime 0.147.0, non-root UID/GID 65532, and the exact source/version labels.

An isolated synthetic rehearsal proved cold start, restart, rollback to the
prior subscription-native image, forward restore, two-service steady state,
metadata-only Codex volume attestation, and cleanup. It made no intake request
and no provider dispatch.

This is evidence, not release authority. The candidate remains held for an
approved signing identity/signature, real subscription account and official
login evidence, applied/reboot-proven host egress controls, exact deployment
approval, and separately approved read-only canary and task drain.

`release-manifest.json` is the concise machine-readable index. Its evidence
hashes cover the sibling files but intentionally do not self-hash the manifest.
