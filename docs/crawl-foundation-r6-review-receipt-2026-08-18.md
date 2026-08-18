# Crawl foundation R6 review receipt — 2026-08-18

Terminal state: `RESTART_REQUIRED`

## Exact frozen tuple

- product: `78a3d5a745113a87a7bb862c0498a218b66abc9a`
- control: `aa9253f3dd1ae32c4b80acc3a2768756165246d7`
- Blueprint: `efb212b1b2f657c0e915b7ff8a0577faa8489103`
- packet SHA-256: `0ced17806e30d1bc2b176cc1976b5bf8f224a19cf97573cbfa46c156b4482f8d`
- 52-entry manifest SHA-256: `5b7dc874ffb77b46c3fc286af874908173fa8915d19bd111892fa42c858e5c85`
- native Codex result-output SHA-256: `005acd0ff455a9bfeccddfc557ba275c687d02f690b10e449a1dfe2c8a24f356`
- tracked result JSON SHA-256: `07a57571a6df5a0641083fb98863d9578c301eea80c80d2959f361db14bb3088`

## Gate route

The accepted invocation used native Codex CLI `0.148.0`, ChatGPT login,
`gpt-5.6-sol`, maximum reasoning, `/Users/glupta/Dev` as the read root, a
read-only sandbox, ephemeral mode with `shell_snapshot` disabled, the exact
structured-output schema, and no API-key or base-URL override. Two earlier
incomplete invocations were terminated before any event or result because
their launcher flags did not fully match the frontier-review contract; neither
is review evidence or an availability retry.

The accepted invocation exited zero and returned a schema-valid result. A
single sampling stream disconnect was handled by the native Codex transport;
it did not change the packet, reviewer identity, or terminal result.

## Gate result

Fresh native Codex maximum found two substantiated material blockers:

1. Exception objects and capture-locals tracebacks can retain synthetic API-key
   and admitted-source bytes through provider/workflow frames and context
   chains, so ordinary formatted-traceback redaction tests do not prove the
   frozen sanitization contract.
2. Two canonical Blueprint current-state statements still name rejected R4
   product `8efd3cc…` while their historical and R6 sections correctly identify
   R4 as rejected and R6 product `78a3d5a…` as current.

The Codex-first gate therefore did not invoke Fable or Grok. R6 is immutable
rejected evidence. The two fixes belong to a new bounded candidate and require
new exact identities, packet, manifest, and frontier review.

No deployment, provider dispatch, credential access, spend, queue drain, Walk,
public, Hermes, or outbound activation occurred or is authorized by this
receipt.
