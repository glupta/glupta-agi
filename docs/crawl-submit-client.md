# Crawl submit client contract

Status: implementation contract for the measured Crawl operability gap.

## Outcome

An operator can submit one disclosure-approved `evidence_brief_v1` request to
the authenticated loopback API without placing the intake capability in shell
arguments, environment variables, logs, or output.

The client is a local text adapter for the existing API. It does not add a
service, workflow, queue, model route, provider retry, database, dependency, or
action authority. The server remains the sole owner of intake validation,
durability, effect fencing, citation resolution, and replay.

## Interface

`glupta-crawl-submit --question <text> [--idempotency-key <uuid7>] [--json] FILE...`

- `FILE` values are normalized relative `.md` or `.txt` paths already present
  under the server's read-only input root. The client sends path names only.
- The endpoint defaults to `http://127.0.0.1:8765` and may be overridden only
  with a literal `127.0.0.1` HTTP URL that contains no credentials, path,
  query, or fragment. Redirects are rejected so they cannot forward the bearer.
- The token path defaults to `runtime/intake-token`. The client opens it with
  no symlink following, requires an owner-only regular file owned by the
  current user, and keeps the value in process memory only.
- A supplied idempotency key must be canonical lowercase UUIDv7. Otherwise the
  client generates one locally.
- Default output is the returned Markdown brief. `--json` emits the complete
  typed response. Errors never include the bearer capability.

## Fixed acceptance

1. A mocked successful request proves the exact endpoint, body, generated or
   supplied UUIDv7, in-memory bearer header, and Markdown/JSON output.
2. Missing, symlinked, non-regular, wrong-owner, group/world-readable, short,
   or oversized token files fail before network dispatch.
3. Non-loopback endpoints, malformed source paths, duplicate files, and
   malformed/non-v7 idempotency keys fail before network dispatch.
4. Redirect, HTTP, connection, invalid-response, and oversized-response
   failures are bounded and redact the capability.
5. The full repository suite, Ruff, lock check, package build, Compose render,
   and production-source census pass; production remains at or below the
   Blueprint Crawl ceiling of 1,500 lines.

## Rollback and stop rules

Rollback is removal of the console entry point, client module, tests, and this
contract. Stop rather than broaden the client if acceptance would require a
new dependency, non-loopback transport, credential store, retry engine,
background process, server contract change, or any authority beyond read-only
`OBSERVE` submission.
