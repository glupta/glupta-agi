from __future__ import annotations

import asyncio
import os
import tempfile
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import pytest
from httpx import Request, Response
from openai import APIStatusError

from glupta_agi import effects, workflow
from glupta_agi.contracts import DISCLOSURE_NOTICE_DIGEST, EvidenceBrief
from glupta_agi.effects import AmbiguousEffectError
from glupta_agi.intake import admit_inline_request, validate_workflow_payload
from glupta_agi.openai_adapter import OpenAIResponsesAdapter
from tests.helpers import private_file, provider_audit, release_profile

_DATABASE_URL = os.environ.get("GLUPTA_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    _DATABASE_URL is None,
    reason="GLUPTA_TEST_DATABASE_URL is required for real PostgreSQL persistence tests",
)


@pytest.fixture(autouse=True)
def _configure_real_effect_store() -> None:
    if _DATABASE_URL is None:
        pytest.skip("real PostgreSQL test database is unavailable")
    effects.initialize(_DATABASE_URL)


def _packet(*, credential_file: str = "/private/synthetic-key", near_deadline: bool = False):
    workflow_id = str(uuid.uuid4())
    admitted_at = datetime.now(UTC)
    if near_deadline:
        admitted_at -= timedelta(seconds=299.5)
    admitted = admit_inline_request(
        question="question",
        sources=[{"path": "source.md", "content": "grounded fact"}],
        disclosure_profile="external_disclosed_v1",
        disclosure_notice_digest=DISCLOSURE_NOTICE_DIGEST,
        external_disclosure_ack=True,
    )
    return workflow._CrawlModelPacket(
        admitted_request=admitted.workflow_payload(),
        release_profile=release_profile(),
        credential_file=credential_file,
        credential_generation=1,
        admitted_at=admitted_at,
        workflow_id=workflow_id,
    )


def _prime_dispatch(packet: workflow._CrawlModelPacket):
    admitted = validate_workflow_payload(packet.admitted_request)
    request_body = workflow._request_body(
        workflow.build_user_prompt(admitted.question, packet.admitted_request["sources"]),
        packet.release_profile,
    )
    dispatch = workflow._dispatch(packet, admitted, request_body)
    effects.reserve(dispatch.model_dump(mode="json"), dispatch.digest())
    effects.transition(packet.workflow_id, "reserved", "dispatching")
    brief = EvidenceBrief(answer="Grounded.", citations=[], uncertainties=[], next_decisions=[])
    audit = provider_audit(
        brief,
        workflow_id=packet.workflow_id,
        request_digest=admitted.request_digest,
        release_profile_digest=dispatch.release_profile_digest,
        request_body_digest=dispatch.request_body_digest,
    ).model_dump(mode="json")
    return dispatch, audit


def _assert_replay_does_not_dispatch(packet: workflow._CrawlModelPacket, error: type[Exception]):
    def forbidden_factory(*_args: object, **_kwargs: object) -> None:
        pytest.fail("replay attempted provider dispatch")

    with pytest.raises(error):
        asyncio.run(workflow._run_inference(packet, adapter_factory=forbidden_factory))


def test_lost_failed_ack_exact_readback_remains_definitive_and_does_not_redispatch() -> None:
    packet = _packet()
    dispatch, audit = _prime_dispatch(packet)

    def commit_then_lose_ack(*args: object, **kwargs: object):
        effects.transition(*args, **kwargs)
        raise RuntimeError("lost commit acknowledgement")

    with patch.object(workflow, "transition", side_effect=commit_then_lose_ack):
        workflow._persist(dispatch, "failed", audit, reason="provider_rejected")

    recorded = effects.reserve(dispatch.model_dump(mode="json"), dispatch.digest())
    TestCase().assertEqual(
        (recorded.state, recorded.audit, recorded.hold_reason),
        ("failed", audit, "provider_rejected"),
    )
    _assert_replay_does_not_dispatch(packet, workflow.BriefGenerationError)


@pytest.mark.parametrize("readback", ["mismatched", "unavailable"])
def test_lost_failed_ack_without_exact_readback_becomes_sticky_unknown(readback: str) -> None:
    packet = _packet()
    dispatch, audit = _prime_dispatch(packet)

    def commit_then_lose_ack(*args: object, **kwargs: object):
        persisted = kwargs
        if readback == "mismatched":
            persisted = {**kwargs, "audit": {**audit, "response_id": "different"}}
        effects.transition(*args, **persisted)
        raise RuntimeError("lost commit acknowledgement")

    reserve_patch = (
        patch.object(workflow, "reserve", side_effect=RuntimeError("readback unavailable"))
        if readback == "unavailable"
        else patch.object(workflow, "reserve", wraps=effects.reserve)
    )
    with (
        patch.object(workflow, "transition", side_effect=commit_then_lose_ack),
        reserve_patch,
        pytest.raises(AmbiguousEffectError),
    ):
        workflow._persist(dispatch, "failed", audit, reason="provider_rejected")

    recorded = effects.reserve(dispatch.model_dump(mode="json"), dispatch.digest())
    case = TestCase()
    case.assertEqual(recorded.state, "unknown")
    case.assertEqual(recorded.hold_reason, "provider_rejected_persistence_ambiguous")
    _assert_replay_does_not_dispatch(packet, AmbiguousEffectError)
    replayed = effects.reserve(dispatch.model_dump(mode="json"), dispatch.digest())
    case.assertEqual(replayed.state, "unknown")


@pytest.mark.parametrize("status", [408, 409, 429, 500, 503])
def test_retryable_status_is_sticky_unknown_and_replay_never_redispatches(status: int) -> None:
    with tempfile.TemporaryDirectory() as temporary:
        key = private_file(Path(temporary), "api-key", "secret-api-key-" + "x" * 32)
        packet = _packet(credential_file=str(key))
        request = Request("POST", "https://api.openai.com/v1/responses")
        response = Response(status, request=request, headers={"x-request-id": "req_unknown"})
        rejection = APIStatusError(
            "RAW_PROVIDER_BODY", response=response, body={"secret": "marker"}
        )

        class RejectingClient:
            def __init__(self) -> None:
                self.responses = self
                self.create_calls = 0

            async def create(self, **_kwargs: object) -> None:
                self.create_calls += 1
                raise rejection

            async def close(self) -> None:
                pass

        client = RejectingClient()

        def adapter_factory(profile: object, credential_file: Path, *, credential_generation: int):
            return OpenAIResponsesAdapter(
                profile,
                credential_file,
                credential_generation=credential_generation,
                client_factory=lambda **_kwargs: client,
            )

        with pytest.raises(AmbiguousEffectError):
            asyncio.run(workflow._run_inference(packet, adapter_factory=adapter_factory))

    admitted = validate_workflow_payload(packet.admitted_request)
    dispatch = workflow._dispatch(
        packet,
        admitted,
        workflow._request_body(
            workflow.build_user_prompt(admitted.question, packet.admitted_request["sources"]),
            packet.release_profile,
        ),
    )
    recorded = effects.reserve(dispatch.model_dump(mode="json"), dispatch.digest())
    case = TestCase()
    case.assertEqual(recorded.state, "unknown")
    case.assertEqual(recorded.hold_reason, "provider_outcome_ambiguous")
    case.assertEqual(client.create_calls, 1)
    _assert_replay_does_not_dispatch(packet, AmbiguousEffectError)
    case.assertEqual(client.create_calls, 1)


def test_terminal_rejection_with_cleanup_expiry_is_sticky_unknown() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        key = private_file(Path(temporary), "api-key", "secret-api-key-" + "x" * 32)
        packet = _packet(credential_file=str(key), near_deadline=True)
        request = Request("POST", "https://api.openai.com/v1/responses")
        response = Response(400, request=request, headers={"x-request-id": "req_rejected"})
        rejection = APIStatusError(
            "RAW_PROVIDER_BODY", response=response, body={"secret": "marker"}
        )

        class RejectingSlowCloseClient:
            def __init__(self) -> None:
                self.responses = self
                self.create_calls = 0

            async def create(self, **_kwargs: object) -> None:
                self.create_calls += 1
                raise rejection

            async def close(self) -> None:
                await asyncio.sleep(10)

        client = RejectingSlowCloseClient()

        def adapter_factory(profile: object, credential_file: Path, *, credential_generation: int):
            return OpenAIResponsesAdapter(
                profile,
                credential_file,
                credential_generation=credential_generation,
                client_factory=lambda **_kwargs: client,
            )

        with pytest.raises(AmbiguousEffectError):
            asyncio.run(workflow._run_inference(packet, adapter_factory=adapter_factory))

    admitted = validate_workflow_payload(packet.admitted_request)
    dispatch = workflow._dispatch(
        packet,
        admitted,
        workflow._request_body(
            workflow.build_user_prompt(admitted.question, packet.admitted_request["sources"]),
            packet.release_profile,
        ),
    )
    recorded = effects.reserve(dispatch.model_dump(mode="json"), dispatch.digest())
    case = TestCase()
    case.assertEqual(recorded.state, "unknown")
    case.assertEqual(recorded.hold_reason, "provider_outcome_ambiguous")
    case.assertEqual(client.create_calls, 1)
    _assert_replay_does_not_dispatch(packet, AmbiguousEffectError)
    case.assertEqual(client.create_calls, 1)
