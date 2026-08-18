from __future__ import annotations

import asyncio
import json
import tempfile
import time
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

import pytest
from httpx import Request, Response
from openai import APIStatusError

from glupta_agi.contracts import canonical_digest
from glupta_agi.inference import FrozenDispatch
from glupta_agi.openai_adapter import (
    AdapterError,
    OpenAIResponsesAdapter,
    ProviderAmbiguousError,
    ProviderRejectedError,
)
from tests.helpers import private_file, release_profile


def _body() -> dict[str, object]:
    return {
        "model": "gpt-5.6-sol",
        "instructions": "ground sources",
        "input": "question",
        "reasoning": {"effort": "medium"},
        "text": {"format": {"type": "json_schema"}},
        "max_output_tokens": 4000,
        "store": False,
        "background": False,
        "stream": False,
        "tools": [],
        "tool_choice": "none",
        "truncation": "disabled",
    }


def _dispatch(body: dict[str, object], **overrides: object) -> FrozenDispatch:
    values: dict[str, object] = {
        "workflow_id": "0198be50-0000-7000-8000-000000000000",
        "request_digest": "a" * 64,
        "request_body_digest": canonical_digest(body),
        "release_profile_digest": release_profile().digest(),
        "input_token_upper_bound": 10_000,
        "queue_deadline": "2099-01-01T00:00:00Z",
        "wall_deadline": "2099-01-01T00:00:00Z",
    }
    values.update(overrides)
    return FrozenDispatch.model_validate(values)


def _response(**overrides: object) -> SimpleNamespace:
    brief = {
        "answer": "Grounded.",
        "citations": [],
        "uncertainties": [],
        "next_decisions": [],
    }
    values: dict[str, object] = {
        "status": "completed",
        "_request_id": "req_1",
        "id": "resp_1",
        "model": "gpt-5.6-sol",
        "output_text": json.dumps(brief),
        "usage": SimpleNamespace(
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
            input_tokens_details=SimpleNamespace(cached_tokens=10, cache_write_tokens=0),
            output_tokens_details=SimpleNamespace(reasoning_tokens=5),
        ),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeClient:
    def __init__(self, response: object) -> None:
        self.response = response
        self.responses = self
        self.request: dict[str, object] | None = None
        self.closed = False

    async def create(self, **kwargs: object) -> object:
        self.request = kwargs
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    async def close(self) -> None:
        self.closed = True


def _generate(adapter: OpenAIResponsesAdapter, body: dict[str, object], **overrides: object):
    return asyncio.run(adapter.generate(_dispatch(body, **overrides), body))


def test_exact_supported_api_request_uses_zero_retries_and_private_key() -> None:
    body = _body()
    client = FakeClient(_response())
    constructed: dict[str, object] = {}

    def factory(**kwargs: object) -> FakeClient:
        constructed.update(kwargs)
        return client

    with tempfile.TemporaryDirectory() as temporary:
        key = private_file(Path(temporary), "api-key", "secret-api-key-" + "x" * 32)
        adapter = OpenAIResponsesAdapter(release_profile(), key, client_factory=factory)
        result = _generate(adapter, body)

    case = TestCase()
    case.assertEqual(result.brief.answer, "Grounded.")
    case.assertEqual(result.audit.reasoning_tokens, 5)
    case.assertEqual(constructed["api_key"], "secret-api-key-" + "x" * 32)
    case.assertEqual(constructed["base_url"], "https://api.openai.com/v1")
    case.assertEqual(constructed["max_retries"], 0)
    case.assertGreater(constructed["timeout"], 0)
    case.assertLessEqual(constructed["timeout"], 300)
    case.assertIsNotNone(client.request)
    case.assertEqual({key: client.request[key] for key in body}, body)
    case.assertEqual(set(client.request["extra_headers"]), {"X-Client-Request-Id"})
    case.assertTrue(client.closed)


@pytest.mark.parametrize(
    "response",
    [
        _response(usage=None),
        _response(_request_id=""),
        _response(
            usage=SimpleNamespace(
                input_tokens=100,
                output_tokens=20,
                total_tokens=119,
                input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
                output_tokens_details=SimpleNamespace(reasoning_tokens=0),
                novel_usage_category=1,
            )
        ),
        _response(
            usage=SimpleNamespace(
                input_tokens=10_001,
                output_tokens=20,
                total_tokens=10_021,
                input_tokens_details=SimpleNamespace(cached_tokens=0, cache_write_tokens=0),
                output_tokens_details=SimpleNamespace(reasoning_tokens=0),
            )
        ),
    ],
)
def test_missing_inconsistent_or_over_budget_usage_is_ambiguous(response: object) -> None:
    body = _body()
    with tempfile.TemporaryDirectory() as temporary:
        key = private_file(Path(temporary), "api-key", "secret-api-key-" + "x" * 32)
        adapter = OpenAIResponsesAdapter(
            release_profile(), key, client_factory=lambda **_kwargs: FakeClient(response)
        )
        with pytest.raises(ProviderAmbiguousError):
            _generate(adapter, body)


def test_model_or_schema_rejection_is_definitive_and_audited() -> None:
    body = _body()
    for response in (
        _response(model="drifted"),
        _response(output_text="not-json"),
        _response(status="failed"),
    ):
        with tempfile.TemporaryDirectory() as temporary:
            key = private_file(Path(temporary), "api-key", "secret-api-key-" + "x" * 32)
            adapter = OpenAIResponsesAdapter(
                release_profile(),
                key,
                client_factory=lambda _response=response, **_kwargs: FakeClient(_response),
            )
            with pytest.raises(ProviderRejectedError) as caught:
                _generate(adapter, body)
            TestCase().assertIsNotNone(caught.value.audit)


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_explicit_terminal_status_error_is_definitive_and_sanitized(status: int) -> None:
    body = _body()
    request = Request("POST", "https://api.openai.com/v1/responses")
    response = Response(status, request=request, headers={"x-request-id": "req_rejected"})
    error = APIStatusError("RAW_PROVIDER_BODY", response=response, body={"secret": "marker"})
    client = FakeClient(error)
    with tempfile.TemporaryDirectory() as temporary:
        key = private_file(Path(temporary), "api-key", "secret-api-key-" + "x" * 32)
        adapter = OpenAIResponsesAdapter(
            release_profile(), key, client_factory=lambda **_kwargs: client
        )
        with pytest.raises(ProviderRejectedError) as caught:
            _generate(adapter, body)
    case = TestCase()
    case.assertEqual(str(caught.value), "OpenAI request was rejected")
    case.assertIsNone(caught.value.audit)
    case.assertIsNone(caught.value.__cause__)
    case.assertNotIn("RAW_PROVIDER_BODY", "".join(traceback.format_exception(caught.value)))
    case.assertTrue(client.closed)


@pytest.mark.parametrize("status", [408, 409, 418, 429, 500, 503])
def test_retryable_or_unclassified_status_error_is_ambiguous_and_sanitized(
    status: int,
) -> None:
    body = _body()
    request = Request("POST", "https://api.openai.com/v1/responses")
    response = Response(status, request=request, headers={"x-request-id": "req_unknown"})
    error = APIStatusError("RAW_PROVIDER_BODY", response=response, body={"secret": "marker"})
    client = FakeClient(error)
    with tempfile.TemporaryDirectory() as temporary:
        key = private_file(Path(temporary), "api-key", "secret-api-key-" + "x" * 32)
        adapter = OpenAIResponsesAdapter(
            release_profile(), key, client_factory=lambda **_kwargs: client
        )
        with pytest.raises(ProviderAmbiguousError) as caught:
            _generate(adapter, body)
    case = TestCase()
    case.assertEqual(str(caught.value), "OpenAI request outcome is ambiguous")
    case.assertIsNone(caught.value.audit)
    case.assertIsNone(caught.value.__cause__)
    case.assertNotIn("RAW_PROVIDER_BODY", "".join(traceback.format_exception(caught.value)))
    case.assertTrue(client.closed)


def test_authenticated_status_error_with_expired_cleanup_is_ambiguous() -> None:
    body = _body()
    request = Request("POST", "https://api.openai.com/v1/responses")
    response = Response(429, request=request, headers={"x-request-id": "req_rejected"})
    error = APIStatusError("RAW_PROVIDER_BODY", response=response, body={"secret": "marker"})

    class RejectingSlowCloseClient(FakeClient):
        close_started = False
        close_finished = False

        async def close(self) -> None:
            self.close_started = True
            await asyncio.sleep(10)
            self.close_finished = True

    client = RejectingSlowCloseClient(error)
    deadline = (datetime.now(UTC) + timedelta(milliseconds=20)).isoformat()
    with tempfile.TemporaryDirectory() as temporary:
        key = private_file(Path(temporary), "api-key", "secret-api-key-" + "x" * 32)
        adapter = OpenAIResponsesAdapter(
            release_profile(), key, client_factory=lambda **_kwargs: client
        )
        with pytest.raises(ProviderAmbiguousError) as caught:
            _generate(adapter, body, queue_deadline=deadline, wall_deadline=deadline)
    case = TestCase()
    case.assertIsNone(caught.value.audit)
    case.assertNotIn("RAW_PROVIDER_BODY", "".join(traceback.format_exception(caught.value)))
    case.assertTrue(client.close_started)
    case.assertFalse(client.close_finished)


def test_absolute_wall_deadline_cancels_transport_and_closes_client() -> None:
    body = _body()

    class SlowClient(FakeClient):
        close_started = False
        close_finished = False

        async def create(self, **kwargs: object) -> object:
            self.request = kwargs
            await asyncio.sleep(10)
            return self.response

        async def close(self) -> None:
            self.close_started = True
            await asyncio.sleep(10)
            self.close_finished = True

    client = SlowClient(_response())
    deadline = (datetime.now(UTC) + timedelta(milliseconds=20)).isoformat()
    with tempfile.TemporaryDirectory() as temporary:
        key = private_file(Path(temporary), "api-key", "secret-api-key-" + "x" * 32)
        adapter = OpenAIResponsesAdapter(
            release_profile(), key, client_factory=lambda **_kwargs: client
        )
        started = time.monotonic()
        with pytest.raises(ProviderAmbiguousError):
            _generate(adapter, body, queue_deadline=deadline, wall_deadline=deadline)
        elapsed = time.monotonic() - started
    case = TestCase()
    case.assertLess(elapsed, 0.2)
    case.assertTrue(client.close_started)
    case.assertFalse(client.close_finished)


def test_cleanup_only_deadline_is_ambiguous_with_response_receipt_time() -> None:
    body = _body()

    class SlowCloseClient(FakeClient):
        async def close(self) -> None:
            await asyncio.sleep(10)

    client = SlowCloseClient(_response())
    deadline = datetime.now(UTC) + timedelta(milliseconds=20)
    with tempfile.TemporaryDirectory() as temporary:
        key = private_file(Path(temporary), "api-key", "secret-api-key-" + "x" * 32)
        adapter = OpenAIResponsesAdapter(
            release_profile(), key, client_factory=lambda **_kwargs: client
        )
        with pytest.raises(ProviderAmbiguousError) as caught:
            _generate(
                adapter,
                body,
                queue_deadline=deadline.isoformat(),
                wall_deadline=deadline.isoformat(),
            )
    audit = caught.value.audit
    case = TestCase()
    case.assertIsNotNone(audit)
    case.assertLessEqual(audit.completed_at, deadline)


def test_profile_request_and_credential_drift_reject_without_transport() -> None:
    body = _body()

    def factory(**_kwargs: object) -> None:
        pytest.fail("transport constructed")

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        key = private_file(root, "api-key", "secret-api-key-" + "x" * 32)
        adapter = OpenAIResponsesAdapter(release_profile(), key, client_factory=factory)
        with pytest.raises(AdapterError):
            _generate(adapter, body, release_profile_digest="f" * 64)
        with pytest.raises(AdapterError):
            asyncio.run(adapter.generate(_dispatch(body), {**body, "store": True}))
        key.chmod(0o640)
        with pytest.raises(AdapterError):
            _generate(adapter, body)

        expired = release_profile(
            credential_expires_at="2020-01-01T00:00:00Z",
            evidence_expires_at="2020-01-01T00:00:00Z",
        )
        with pytest.raises(AdapterError, match="expired"):
            asyncio.run(
                OpenAIResponsesAdapter(expired, key, client_factory=factory).generate(
                    _dispatch(body, release_profile_digest=expired.digest()), body
                )
            )
