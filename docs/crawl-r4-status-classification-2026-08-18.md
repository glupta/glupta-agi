# Crawl R4 status-classification disposition — 2026-08-18

## Build versus adopt

The pinned official `openai==2.45.0` SDK remains the maintained provider primitive;
no dependency, provider wrapper, or retry layer is added. Its public error contract
exposes `APIStatusError.status_code`, maps 400, 401, 403, 404, and 422 to explicit
non-retryable client-error types, and documents 408, 409, 429, and 5xx as retryable.
The SDK retries remain disabled because Crawl permits one durable dispatch only.

Sources:

- <https://github.com/openai/openai-python/tree/v2.45.0#retries>
- <https://github.com/openai/openai-python/blob/v2.45.0/src/openai/_client.py>
- <https://github.com/openai/openai-python/blob/v2.45.0/src/openai/_exceptions.py>

## Conservative local policy

Only status codes 400, 401, 403, 404, and 422 prove terminal rejection. Statuses 408,
409, 429, and 5xx, plus every unclassified status, leave acceptance or billable usage
unproven and therefore become sticky `unknown`; replay cannot dispatch again.
