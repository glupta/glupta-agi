# ruff: noqa: S101
from __future__ import annotations

import asyncio
import hashlib
import inspect
import json
import traceback
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from glupta_agi.api import WALK_ARTIFACT_MAX_BYTES, app, walk_proposal
from glupta_agi.client import ClientError, submit_walk_artifact
from glupta_agi.contracts import DISCLOSURE_NOTICE_DIGEST, Citation, canonical_digest
from glupta_agi.effects import AmbiguousEffectError, Effect, _effect
from glupta_agi.inference import (
    CRAWL_ROLLBACK_RELEASE_DIGEST,
    WALK_IMPLEMENTATION_SPEC_DIGEST,
    WalkFrozenDispatch,
)
from glupta_agi.intake import IntakeError
from glupta_agi.settings import Settings, SettingsError, get_settings
from glupta_agi.walk import (
    DELIVERABLE_TYPES,
    WALK_FAMILIES,
    WalkArtifact,
    WalkDeliverable,
    WalkEvidenceReview,
    WalkProviderResult,
    WalkResponse,
    WalkStateSynthesis,
    output_model,
    validate_citations,
    validate_output_identity,
    validate_walk_payload,
)
from glupta_agi.workflow import (
    BriefGenerationError,
    _run_inference,
    _walk_model_step,
    _WalkModelPacket,
    walk_proposal_workflow,
    walk_queue,
)
from tests.helpers import walk_provider_audit, walk_release_profile

WORKFLOW_ID = "0198be50-0000-7000-8000-000000000000"


def artifact(family: str = "walk_state_synthesis_v1", **changes: object) -> WalkArtifact:
    content = "grounded fact"
    values: dict[str, object] = {
        "schema_version": "glupta-walk-request-artifact-v1",
        "workflow_family": family,
        "question": "What should happen next?",
        "decision_owner": "Akshay",
        "deliverable_type": "decision_memo" if family == "walk_deliverable_v1" else None,
        "expected_disposition": "PASS" if family == "walk_evidence_review_v1" else None,
        "disclosure_profile": "external_disclosed_v1",
        "disclosure_notice_digest": DISCLOSURE_NOTICE_DIGEST,
        "external_disclosure_ack": True,
        "release_profile_digest": walk_release_profile().digest(),
        "sources": [{"path": "source.md", "content": content,
            "sha256": hashlib.sha256(content.encode()).hexdigest(), "byte_size": len(content)}],
    }
    values.update(changes)
    return WalkArtifact.model_validate(values)


def admitted(family: str = "walk_state_synthesis_v1"):
    item = artifact(family)
    raw = json.dumps(item.model_dump(mode="json"), separators=(",", ":"),
        sort_keys=True).encode()
    return item.admit(hashlib.sha256(raw).hexdigest())


def packet(family: str = "walk_state_synthesis_v1") -> _WalkModelPacket:
    request = admitted(family)
    return _WalkModelPacket(admitted_request=request.workflow_payload(),
        release_profile=walk_release_profile(), codex_home="/private/codex",
        auth_generation=1, admitted_at=datetime.now(UTC), workflow_id=WORKFLOW_ID)


def state_output() -> WalkStateSynthesis:
    return WalkStateSynthesis(kind="walk_state_synthesis_v1",
        current_facts=["Grounded fact."], blockers=[], uncertainties=[],
        prioritized_next_actions=[], summary_markdown="Grounded.",
        citations=[Citation(path="source.md", line_start=1, line_end=1,
            quote="grounded fact")])


def walk_dispatch() -> WalkFrozenDispatch:
    profile = walk_release_profile()
    return WalkFrozenDispatch(workflow_id=WORKFLOW_ID, request_digest="a" * 64,
        request_body_digest="b" * 64, release_profile_digest=profile.digest(),
        disclosure_profile="external_disclosed_v1",
        disclosure_notice_digest=DISCLOSURE_NOTICE_DIGEST,
        external_disclosure_ack=True, subscription_route_id=profile.subscription_route_id,
        subscription_plan="pro", auth_generation=1, model=profile.model,
        reasoning_effort="medium", input_bytes=100,
        queue_deadline=datetime.now(UTC) + timedelta(minutes=5),
        wall_deadline=datetime.now(UTC) + timedelta(minutes=5),
        workflow_family="walk_state_synthesis_v1",
        result_schema_digest=canonical_digest(WalkStateSynthesis.model_json_schema()),
        artifact_sha256="c" * 64)


class WalkAdapter:
    calls = 0

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    async def generate(self, dispatch: WalkFrozenDispatch,
        _request_body: dict[str, object]) -> WalkProviderResult:
        type(self).calls += 1
        output = state_output()
        audit = walk_provider_audit(output, workflow_id=dispatch.workflow_id,
            request_digest=dispatch.request_digest, workflow_family=dispatch.workflow_family,
            result_schema_digest=dispatch.result_schema_digest,
            release_profile_digest=dispatch.release_profile_digest,
            request_body_digest=dispatch.request_body_digest)
        return WalkProviderResult(output=output, audit=audit)


def effect(state: str, dispatch: dict[str, object], **changes: object) -> Effect:
    values = dict(workflow_id=str(dispatch["workflow_id"]),
        request_digest=str(dispatch["request_digest"]), dispatch_digest="d" * 64,
        state=state, dispatch=dispatch, result=None, audit=None, hold_reason=None)
    values.update(changes)
    return Effect(**values)  # type: ignore[arg-type]


def transition(workflow_id: str, _expected: str, state: str, **kwargs: object) -> Effect:
    return Effect(workflow_id=workflow_id, request_digest="a" * 64,
        dispatch_digest="d" * 64, state=state, dispatch={},
        result=kwargs.get("result"), audit=kwargs.get("audit"),
        hold_reason=kwargs.get("hold_reason"))  # type: ignore[arg-type]


def test_three_exact_families_and_conditional_contracts() -> None:
    assert WALK_FAMILIES == ("walk_state_synthesis_v1", "walk_deliverable_v1",
        "walk_evidence_review_v1")
    assert DELIVERABLE_TYPES == ("decision_memo", "specification", "experiment_design",
        "diligence_packet")
    for family in WALK_FAMILIES:
        request = admitted(family)
        assert validate_walk_payload(request.workflow_payload()) == request
        assert output_model(family).model_fields["kind"]
    with pytest.raises(ValueError):
        artifact("walk_state_synthesis_v1", deliverable_type="decision_memo")
    with pytest.raises(ValueError):
        artifact("walk_deliverable_v1", deliverable_type=None)
    payload = admitted("walk_deliverable_v1").workflow_payload()
    payload["deliverable_type"] = None
    with pytest.raises(IntakeError):
        validate_walk_payload(payload)


def test_family_outputs_bind_request_identity_and_word_limits() -> None:
    deliverable = WalkDeliverable(kind="walk_deliverable_v1", deliverable_type="decision_memo",
        decision_owner="Akshay", objective="Decide", non_goals=[], proposed_artifact="Draft",
        alternatives=[], risks_and_rollback=[], verification_plan=[], open_decisions=[],
        citations=[], summary_markdown="Draft only.")
    assert validate_output_identity(admitted("walk_deliverable_v1"), deliverable) == deliverable
    with pytest.raises(ValueError, match="deliverable identity"):
        validate_output_identity(admitted("walk_deliverable_v1"),
            deliverable.model_copy(update={"decision_owner": "Other"}))
    review = WalkEvidenceReview(kind="walk_evidence_review_v1", verdict="PASS",
        material_blockers=[], verified_claims=[], unverified_claims=[],
        smallest_sufficient_remediation=[], citations=[], summary_markdown="Pass.")
    assert validate_output_identity(admitted("walk_evidence_review_v1"), review) == review
    with pytest.raises(ValueError, match="frozen disposition"):
        validate_output_identity(admitted("walk_evidence_review_v1"),
            review.model_copy(update={"verdict": "HOLD", "material_blockers": [{
                "requirement": "r", "evidence": "e", "impact": "i", "remediation": "x"}]}))
    with pytest.raises(ValueError, match="word limit"):
        WalkStateSynthesis(kind="walk_state_synthesis_v1", current_facts=[], blockers=[],
            uncertainties=[], prioritized_next_actions=[], citations=[],
            summary_markdown="word " * 901)


def test_citations_are_resolved_only_from_admitted_sources() -> None:
    output = state_output().model_copy(update={"citations": [Citation(path="source.md",
        line_start=1, line_end=1, quote="provider-controlled")]})
    resolved = validate_citations(output, admitted().workflow_payload()["canonical"]["sources"])
    assert resolved.citations[0].quote == "grounded fact"
    with pytest.raises(ValueError):
        validate_citations(output.model_copy(update={"citations": [Citation(path="other.md",
            line_start=1, line_end=1, quote="x")]}),
            admitted().workflow_payload()["canonical"]["sources"])


def test_release_profile_is_stage_specific_and_crawl_entrypoint_rejects_it() -> None:
    profile = walk_release_profile()
    assert profile.implementation_spec_digest == WALK_IMPLEMENTATION_SPEC_DIGEST
    assert profile.crawl_rollback_release_digest == CRAWL_ROLLBACK_RELEASE_DIGEST
    with pytest.raises(ValueError):
        walk_release_profile(implementation_spec_digest="0" * 64)
    with pytest.raises(ValueError):
        walk_release_profile(crawl_rollback_release_digest="0" * 64)
    settings = Settings(input_root=Path("/data/inputs"), token="t" * 32, release_profile=profile,
        release_profile_digest=profile.digest(), codex_home=Path("/private/codex"),
        auth_generation=1)
    with pytest.raises(SettingsError):
        settings.require_external_profile()
    with patch("glupta_agi.settings._validate_codex_home"):
        assert settings.require_walk_profile()[0] == profile


def test_walk_uses_distinct_native_step_and_shared_single_queue() -> None:
    assert _walk_model_step.dbos_function_name == "walk_proposal_model_v1"
    assert walk_proposal_workflow.dbos_function_name == "walk_proposal_workflow"
    assert (walk_queue.name, walk_queue.concurrency, walk_queue.worker_concurrency) == (
        "crawl-observe-v1", 1, 1)
    assert 'retries_allowed=False' in inspect.getsource(_walk_model_step)


def test_walk_success_uses_shared_effect_path_and_replay_never_redispatches() -> None:
    WalkAdapter.calls = 0
    with (patch("glupta_agi.workflow.reserve",
            side_effect=lambda dispatch, _digest: effect("reserved", dispatch)),
          patch("glupta_agi.workflow.transition", side_effect=transition) as writes):
        result = asyncio.run(_run_inference(packet(), adapter_factory=WalkAdapter))
    assert result.output.citations[0].quote == "grounded fact"
    assert WalkAdapter.calls == 1 and writes.call_args_list[-1].args[2] == "reconciled"

    def replay(dispatch: dict[str, object], _digest: str) -> Effect:
        frozen = WalkFrozenDispatch.model_validate(dispatch)
        output = state_output()
        audit = walk_provider_audit(output, workflow_id=frozen.workflow_id,
            request_digest=frozen.request_digest, workflow_family=frozen.workflow_family,
            result_schema_digest=frozen.result_schema_digest,
            release_profile_digest=frozen.release_profile_digest,
            request_body_digest=frozen.request_body_digest)
        return effect("reconciled", dispatch, result=output.model_dump(mode="json"),
            audit=audit.model_dump(mode="json"))

    with patch("glupta_agi.workflow.reserve", side_effect=replay):
        replayed = asyncio.run(_run_inference(packet(),
            adapter_factory=lambda *_a, **_k: pytest.fail("redispatched")))
    assert replayed.output.kind == "walk_state_synthesis_v1"


def test_walk_post_turn_or_legacy_dispatching_is_sticky_unknown() -> None:
    for marker in (None, "dispatch_phase:turn_invocation_started"):
        with (patch("glupta_agi.workflow.reserve", side_effect=lambda dispatch, _digest,
                value=marker: effect("dispatching", dispatch, hold_reason=value)),
              patch("glupta_agi.workflow.hold_unknown",
                side_effect=AmbiguousEffectError("manual reconciliation")),
              pytest.raises(AmbiguousEffectError)):
            asyncio.run(_run_inference(packet(), adapter_factory=WalkAdapter))


def test_effect_accepts_walk_identity_and_rejects_cross_family_audit() -> None:
    dispatch = walk_dispatch()
    output = state_output()
    audit = walk_provider_audit(output, workflow_id=dispatch.workflow_id,
        request_digest=dispatch.request_digest, workflow_family=dispatch.workflow_family,
        result_schema_digest=dispatch.result_schema_digest,
        release_profile_digest=dispatch.release_profile_digest,
        request_body_digest=dispatch.request_body_digest).model_dump(mode="json")
    row = {"workflow_id": dispatch.workflow_id, "slot_id": "model-0",
        "request_digest": dispatch.request_digest, "dispatch_digest": dispatch.digest(),
        "max_calls": 1, "max_input_bytes": dispatch.input_bytes, "state": "reconciled",
        "dispatch_json": dispatch.model_dump(mode="json"),
        "result_json": output.model_dump(mode="json"), "audit_json": audit,
        "hold_reason": None}
    assert _effect(row).state == "reconciled"
    row["audit_json"] = {**audit, "workflow_family": "walk_evidence_review_v1"}
    with pytest.raises(RuntimeError):
        _effect(row)


def test_walk_response_cross_binds_output_and_complete_provider_record() -> None:
    dispatch = walk_dispatch()
    output = state_output()
    audit = walk_provider_audit(output, workflow_id=dispatch.workflow_id,
        request_digest=dispatch.request_digest, workflow_family=dispatch.workflow_family,
        result_schema_digest=dispatch.result_schema_digest,
        release_profile_digest=dispatch.release_profile_digest,
        request_body_digest=dispatch.request_body_digest)
    values = {"workflow_id": dispatch.workflow_id, "request_digest": dispatch.request_digest,
        "release_profile_digest": dispatch.release_profile_digest,
        "workflow_family": dispatch.workflow_family, "artifact_sha256": "c" * 64,
        "output": output, "provider_audit": audit}
    assert WalkResponse.model_validate(values).output == output
    with pytest.raises(ValueError, match="identity"):
        WalkResponse.model_validate({**values,
            "workflow_family": "walk_evidence_review_v1"})
    with pytest.raises(ValueError, match="provider result"):
        WalkResponse.model_validate({**values,
            "output": output.model_copy(update={"current_facts": ["tampered"]})})


def test_api_rejects_unapproved_artifact_before_auth_or_queue() -> None:
    item = artifact()
    raw = item.model_dump_json().encode()
    settings = Settings(input_root=Path("/unused"), token="TOKEN" + "t" * 32)
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with patch("glupta_agi.api.walk_queue.enqueue_async", new=AsyncMock()) as enqueue:
            async def request() -> object:
                async with AsyncClient(transport=ASGITransport(app=app),
                    base_url="http://test") as client:
                    return await client.post("/v1/walk/proposals", content=raw,
                        headers={"X-Artifact-SHA256": "0" * 64,
                            "Idempotency-Key": WORKFLOW_ID})
            response = asyncio.run(request())
        assert response.status_code == 422
        enqueue.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()


def test_api_bounds_walk_body_before_auth_or_queue() -> None:
    settings = Settings(input_root=Path("/unused"), token="TOKEN" + "t" * 32)
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with patch("glupta_agi.api.walk_queue.enqueue_async", new=AsyncMock()) as enqueue:
            async def request() -> object:
                async with AsyncClient(transport=ASGITransport(app=app),
                    base_url="http://test") as client:
                    return await client.post("/v1/walk/proposals",
                        content=b"x" * (WALK_ARTIFACT_MAX_BYTES + 1),
                        headers={"X-Artifact-SHA256": "0" * 64,
                            "Idempotency-Key": WORKFLOW_ID})
            response = asyncio.run(request())
        assert response.status_code == 422
        enqueue.assert_not_awaited()
    finally:
        app.dependency_overrides.clear()


def test_walk_body_cancellation_clears_request_and_capability_locals() -> None:
    source_marker = "WALK_CANCEL_SOURCE_MARKER"
    token_marker = "WALK_CANCEL_TOKEN_MARKER_" + "t" * 32

    class CancelledRequest:
        async def stream(self):
            yield source_marker.encode()
            raise asyncio.CancelledError

    try:
        asyncio.run(walk_proposal(CancelledRequest(), authorization=f"Bearer {token_marker}",
            artifact_sha256="a" * 64, idempotency_key=WORKFLOW_ID,
            settings=Settings(input_root=Path("/unused"), token=token_marker)))  # type: ignore[arg-type]
    except asyncio.CancelledError as caught:
        error = caught
    else:
        pytest.fail("Walk request cancellation did not propagate")
    assert error.__cause__ is None and error.__context__ is None
    cursor = error.__traceback__
    product_frames = []
    while cursor is not None:
        if "/src/glupta_agi/" in cursor.tb_frame.f_code.co_filename:
            product_frames.append(cursor.tb_frame.f_code.co_name)
            locals_text = repr(cursor.tb_frame.f_locals)
            assert source_marker not in locals_text and token_marker not in locals_text
        cursor = cursor.tb_next
    assert product_frames == ["walk_proposal"]


def test_walk_workflow_remints_sensitive_failures_without_payload_locals() -> None:
    source_marker = "WALK_WORKFLOW_SOURCE_MARKER"
    raw_payload = {"source": source_marker}
    with patch("glupta_agi.workflow._walk_proposal_workflow_sensitive",
            side_effect=BriefGenerationError("bounded failure")):
        try:
            asyncio.run(inspect.unwrap(walk_proposal_workflow)(raw_payload, WORKFLOW_ID, {},
                "/private/codex", 1, datetime.now(UTC).isoformat()))
        except BriefGenerationError as caught:
            error = caught
        else:
            pytest.fail("Walk workflow did not fail")
    assert error.__cause__ is None and error.__context__ is None
    captured = traceback.TracebackException.from_exception(error, capture_locals=True)
    product_frames = []
    cursor = error.__traceback__
    while cursor is not None:
        if "/src/glupta_agi/" in cursor.tb_frame.f_code.co_filename:
            product_frames.append(cursor.tb_frame.f_code.co_name)
            assert source_marker not in repr(cursor.tb_frame.f_locals)
        cursor = cursor.tb_next
    assert product_frames == ["walk_proposal_workflow"]
    for frame in captured.stack:
        if "/src/glupta_agi/" in frame.filename:
            assert source_marker not in repr(frame.locals)


def test_walk_client_rejects_changed_artifact_before_capability_or_network() -> None:
    item = artifact()
    raw = item.model_dump_json().encode()
    with (patch("glupta_agi.client._read_capability") as capability,
          patch("glupta_agi.client._submit_payload") as submit,
          pytest.raises(ClientError, match="approved digest")):
        submit_walk_artifact(raw, "0" * 64, "http://127.0.0.1:8765", Path("token"))
    capability.assert_not_called()
    submit.assert_not_called()


def test_walk_client_submits_exact_bytes_route_and_digest_header() -> None:
    item = artifact()
    raw = item.model_dump_json().encode()
    digest = hashlib.sha256(raw).hexdigest()
    expected = {"workflow_id": WORKFLOW_ID}
    with patch("glupta_agi.client._submit_payload", return_value=expected) as submit:
        result = submit_walk_artifact(raw, digest, "http://127.0.0.1:8765", Path("token"),
            WORKFLOW_ID)
    assert result == expected
    assert submit.call_args.args[:2] == (raw, "http://127.0.0.1:8765")
    assert submit.call_args.kwargs == {"route": "/v1/walk/proposals",
        "response_model": WalkResponse,
        "extra_headers": {"X-Artifact-SHA256": digest}}
