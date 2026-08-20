# ruff: noqa: S101
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from glupta_agi import effects, workflow
from glupta_agi.codex_adapter import ProviderAmbiguousError
from glupta_agi.contracts import DISCLOSURE_NOTICE_DIGEST, EvidenceBrief
from glupta_agi.effects import AmbiguousEffectError
from glupta_agi.intake import admit_inline_request, validate_workflow_payload
from glupta_agi.walk import WalkArtifact
from tests.helpers import provider_audit, release_profile, walk_release_profile

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


def _packet() -> workflow._CrawlModelPacket:
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
        codex_home="/private/codex",
        auth_generation=1,
        admitted_at=datetime.now(UTC),
        workflow_id=str(uuid.uuid4()),
    )


def _walk_packet(workflow_id: str) -> workflow._WalkModelPacket:
    profile = walk_release_profile()
    content = "grounded fact"
    artifact = WalkArtifact.model_validate({
        "schema_version": "glupta-walk-request-artifact-v1",
        "workflow_family": "walk_state_synthesis_v1",
        "question": "question", "decision_owner": "Akshay",
        "deliverable_type": None, "expected_disposition": None,
        "disclosure_profile": "external_disclosed_v1",
        "disclosure_notice_digest": DISCLOSURE_NOTICE_DIGEST,
        "external_disclosure_ack": True, "release_profile_digest": profile.digest(),
        "sources": [{"path": "source.md", "content": content,
            "sha256": hashlib.sha256(content.encode()).hexdigest(),
            "byte_size": len(content)}]})
    raw = json.dumps(artifact.model_dump(mode="json"), separators=(",", ":"),
        sort_keys=True).encode()
    admitted = artifact.admit(hashlib.sha256(raw).hexdigest())
    return workflow._WalkModelPacket(admitted_request=admitted.workflow_payload(),
        release_profile=profile, codex_home="/private/codex", auth_generation=1,
        admitted_at=datetime.now(UTC), workflow_id=workflow_id)


def _prime_dispatch(packet: workflow._CrawlModelPacket, *, phase: str | None = None):
    admitted = validate_workflow_payload(packet.admitted_request)
    body = workflow._request_body(
        workflow.build_user_prompt(admitted.question, packet.admitted_request["sources"]),
        packet.release_profile,
    )
    dispatch = workflow._dispatch(packet, admitted, body)
    effects.reserve(dispatch.model_dump(mode="json"), dispatch.digest())
    effects.transition(packet.workflow_id, "reserved", "dispatching",
        hold_reason=None if phase is None else effects.phase_marker(phase))
    brief = EvidenceBrief(answer="Grounded.", citations=[], uncertainties=[], next_decisions=[])
    audit = provider_audit(
        brief,
        workflow_id=packet.workflow_id,
        request_digest=admitted.request_digest,
        release_profile_digest=dispatch.release_profile_digest,
        request_body_digest=dispatch.request_body_digest,
    ).model_dump(mode="json")
    return dispatch, audit


def _assert_replay_does_not_dispatch(
    packet: workflow._CrawlModelPacket, error: type[Exception]
) -> None:
    def forbidden_factory(*_args: object, **_kwargs: object) -> None:
        pytest.fail("replay attempted subscription dispatch")

    with pytest.raises(error):
        asyncio.run(workflow._run_inference(packet, adapter_factory=forbidden_factory))


def test_lost_failed_ack_exact_readback_remains_definitive() -> None:
    packet = _packet()
    dispatch, audit = _prime_dispatch(packet)

    def commit_then_lose_ack(*args: object, **kwargs: object):
        effects.transition(*args, **kwargs)
        raise RuntimeError("lost commit acknowledgement")

    with patch.object(workflow, "transition", side_effect=commit_then_lose_ack):
        workflow._persist(dispatch, "failed", audit, reason="provider_rejected")

    recorded = effects.reserve(dispatch.model_dump(mode="json"), dispatch.digest())
    assert (recorded.state, recorded.audit, recorded.hold_reason) == (
        "failed",
        audit,
        "provider_rejected",
    )
    _assert_replay_does_not_dispatch(packet, workflow.BriefGenerationError)


def test_lost_reconciled_ack_clears_phase_and_replays_exact_result() -> None:
    packet = _packet()
    dispatch, audit = _prime_dispatch(packet, phase="turn_returned")
    brief = EvidenceBrief(answer="Grounded.", citations=[], uncertainties=[], next_decisions=[])
    result = brief.model_dump(mode="json")

    def commit_then_lose_ack(*args: object, **kwargs: object):
        effects.transition(*args, **kwargs)
        raise RuntimeError("lost commit acknowledgement")

    with patch.object(workflow, "transition", side_effect=commit_then_lose_ack):
        workflow._persist(dispatch, "reconciled", audit, result=result)

    recorded = effects.reserve(dispatch.model_dump(mode="json"), dispatch.digest())
    assert (recorded.state, recorded.result, recorded.hold_reason) == ("reconciled", result, None)


def test_pre_turn_recovery_lost_ack_stays_failed_without_redispatch() -> None:
    packet = _packet()
    dispatch, _audit = _prime_dispatch(packet, phase="thread_start_started")

    def commit_then_lose_ack(*args: object, **kwargs: object):
        effects.transition(*args, **kwargs)
        raise RuntimeError("lost commit acknowledgement")

    with (
        patch.object(workflow, "transition", side_effect=commit_then_lose_ack),
        pytest.raises(workflow.BriefGenerationError, match="before turn invocation"),
    ):
        asyncio.run(workflow._run_inference(packet,
            adapter_factory=lambda *_a, **_k: pytest.fail("recovery attempted dispatch")))

    recorded = effects.reserve(dispatch.model_dump(mode="json"), dispatch.digest())
    assert (recorded.state, recorded.hold_reason) == ("failed", "pre_turn_recovery")
    _assert_replay_does_not_dispatch(packet, workflow.BriefGenerationError)


@pytest.mark.parametrize("fault", ["precommit", "lost_ack", "lost_ack_unavailable"])
def test_initial_phase_write_fault_is_terminal_or_sticky_without_dispatch(fault: str) -> None:
    packet, reservations, writes = _packet(), 0, 0

    def reserve(*args: object, **kwargs: object):
        nonlocal reservations
        reservations += 1
        if fault == "lost_ack_unavailable" and reservations == 2:
            raise RuntimeError("readback unavailable")
        return effects.reserve(*args, **kwargs)

    def transition(*args: object, **kwargs: object):
        nonlocal writes
        writes += 1
        if writes == 1:
            if fault != "precommit":
                effects.transition(*args, **kwargs)
            raise RuntimeError("initial phase acknowledgement lost")
        return effects.transition(*args, **kwargs)

    expected = (
        AmbiguousEffectError if fault == "lost_ack_unavailable" else workflow.BriefGenerationError
    )
    with (
        patch.object(workflow, "reserve", side_effect=reserve),
        patch.object(workflow, "transition", side_effect=transition),
        pytest.raises(expected),
    ):
        asyncio.run(workflow._run_inference(packet,
            adapter_factory=lambda *_a, **_k: pytest.fail("phase failure attempted dispatch")))

    admitted = validate_workflow_payload(packet.admitted_request)
    body = workflow._request_body(workflow.build_user_prompt(
        admitted.question, packet.admitted_request["sources"]), packet.release_profile)
    dispatch = workflow._dispatch(packet, admitted, body)
    recorded = effects.reserve(dispatch.model_dump(mode="json"), dispatch.digest())
    assert recorded.state == ("unknown" if fault == "lost_ack_unavailable" else "failed")
    _assert_replay_does_not_dispatch(packet, expected)


@pytest.mark.parametrize("readback", ["mismatched", "unavailable"])
def test_lost_failed_ack_without_exact_readback_becomes_unknown(readback: str) -> None:
    packet = _packet()
    dispatch, audit = _prime_dispatch(packet)

    def commit_then_lose_ack(*args: object, **kwargs: object):
        persisted = kwargs
        if readback == "mismatched":
            persisted = {**kwargs, "audit": {**audit, "turn_id": "different"}}
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
    assert recorded.state == "unknown"
    assert recorded.hold_reason == "provider_rejected_persistence_ambiguous"
    _assert_replay_does_not_dispatch(packet, AmbiguousEffectError)


def test_subscription_ambiguity_is_sticky_and_never_redispatches() -> None:
    packet = _packet()

    class AmbiguousAdapter:
        calls = 0

        async def generate(self, *_args: object, **_kwargs: object) -> None:
            self.calls += 1
            raise ProviderAmbiguousError("synthetic ambiguous turn")

    adapter = AmbiguousAdapter()
    with pytest.raises(AmbiguousEffectError):
        asyncio.run(workflow._run_inference(packet, adapter_factory=lambda *_a, **_k: adapter))

    admitted = validate_workflow_payload(packet.admitted_request)
    body = workflow._request_body(
        workflow.build_user_prompt(admitted.question, packet.admitted_request["sources"]),
        packet.release_profile,
    )
    dispatch = workflow._dispatch(packet, admitted, body)
    recorded = effects.reserve(dispatch.model_dump(mode="json"), dispatch.digest())
    assert recorded.state == "unknown"
    assert recorded.hold_reason == "provider_outcome_ambiguous"
    assert adapter.calls == 1
    _assert_replay_does_not_dispatch(packet, AmbiguousEffectError)


def test_crawl_and_walk_cannot_share_a_workflow_effect_identity() -> None:
    crawl = _packet()
    dispatch, _audit = _prime_dispatch(crawl)
    with pytest.raises(workflow.BriefGenerationError,
            match="recorded model effect conflicts with request"):
        asyncio.run(workflow._run_inference(_walk_packet(crawl.workflow_id),
            adapter_factory=lambda *_a, **_k: pytest.fail("cross-stage collision dispatched")))
    recorded = effects.reserve(dispatch.model_dump(mode="json"), dispatch.digest())
    assert recorded.dispatch["schema_version"] == "crawl-codex-subscription-dispatch-v1"
