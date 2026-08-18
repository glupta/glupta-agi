# Crawl foundation R7 review receipt — 2026-08-18

Terminal state: `RESTART_REQUIRED`

## Exact frozen tuple

- product: `61f817ffbe8dcb08626e2ffc10eccf825e048312`
- control: `fd7b60e18b9df8dbdd40f6d5452bcf2b0597a6ef`
- Blueprint: `2babe42ca1298c0a42dc5b14716bc221efe88d21`
- packet SHA-256: `000fa84c191c8271ac83f1fffb161b8bb9838e52428698492c1071720714ad27`
- 58-entry manifest SHA-256: `d4c055ec527d5e0c671211fc78568b48040ddfed92d7acc2b64dfdacd9a74baf`
- prompt SHA-256: `fbecf56ba2c384b95648cde9aa838bb184d344634dff235dd194cf8ac9fe196c`
- schema SHA-256: `c2528480855d6578c5d1f8a1cde59f2b9ce3d96dd59749bd31b7da7d059b3b84`
- native Codex result-output SHA-256: `66a09a51e9ef57902c2ccf0af7aa4e775de7ae08df26848d5f797ed089d25ba3`

## Gate route

The accepted invocation used native Codex CLI `0.148.0`, ChatGPT login,
`gpt-5.6-sol`, maximum reasoning, `/Users/glupta/Dev` as the read root, a
read-only sandbox, ephemeral mode with `shell_snapshot` disabled, the exact
structured-output schema, and no API-key or base-URL override. It exited zero
with a schema-valid result after independently verifying all 58 manifest
entries and the three exact commit roots.

## Gate result

Fresh native Codex maximum found two substantiated material blockers:

1. External `asyncio.CancelledError` bypasses the `Exception`-based adapter
   boundary. A read-only no-network diagnostic using synthetic markers found
   both credential and admitted-source markers in production traceback locals,
   while the unproved transport outcome also bypassed the immediate sticky
   `unknown` classification.
2. The normative control amendment falsely says the two Blueprint openings
   identify R6 as the then-current candidate. The exact Blueprint artifacts and
   the frozen packet correctly identify R7 as current and R6 as immutable
   rejected history.

The Codex-first gate therefore did not invoke Fable or Grok. R7 is immutable
rejected evidence. Both fixes belong to a separate bounded R8 candidate and
require new exact identities, packet, manifest, and frontier review.

No deployment, provider dispatch, credential access, spend, queue drain, Walk,
public, Hermes, or outbound activation occurred or is authorized by this
receipt.
