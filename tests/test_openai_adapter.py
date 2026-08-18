from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

import pytest

from glupta_agi.inference import FrozenDispatch, canonical_digest
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

    def create(self, **kwargs: object) -> object:
        self.request = kwargs
        return self.response

    def close(self) -> None:
        self.closed = True


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
        result = adapter.generate(_dispatch(body), body)

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
            adapter.generate(_dispatch(body), body)


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
                adapter.generate(_dispatch(body), body)
            TestCase().assertIsNotNone(caught.value.audit)


def test_profile_request_and_credential_drift_reject_without_transport() -> None:
    body = _body()

    def factory(**_kwargs: object) -> None:
        pytest.fail("transport constructed")

    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        key = private_file(root, "api-key", "secret-api-key-" + "x" * 32)
        adapter = OpenAIResponsesAdapter(release_profile(), key, client_factory=factory)
        with pytest.raises(AdapterError):
            adapter.generate(_dispatch(body, release_profile_digest="f" * 64), body)
        with pytest.raises(AdapterError):
            adapter.generate(_dispatch(body), {**body, "store": True})
        key.chmod(0o640)
        with pytest.raises(AdapterError):
            adapter.generate(_dispatch(body), body)

        expired = release_profile(
            credential_expires_at="2020-01-01T00:00:00Z",
            evidence_expires_at="2020-01-01T00:00:00Z",
        )
        with pytest.raises(AdapterError, match="expired"):
            OpenAIResponsesAdapter(expired, key, client_factory=factory).generate(
                _dispatch(body, release_profile_digest=expired.digest()), body
            )
