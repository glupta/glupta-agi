# ruff: noqa: E501,I001
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from dbos import DBOS, Queue
from pydantic import BaseModel, Field, StrictInt

from . import codex_adapter, contracts
from .brief import SYSTEM_PROMPT, build_user_prompt, render_markdown, resolve_citations
from .effects import (PRE_TURN_PHASES, AmbiguousEffectError, EffectConflictError, dispatch_phase, hold_unknown, phase_marker, reserve, transition)
from .inference import (
    FrozenDispatch,
    ReleaseProfile,
    SubscriptionDispatch,
    SubscriptionProfile,
    WalkFrozenDispatch,
    WalkReleaseProfile,
)
from .intake import IntakeError, validate_workflow_payload
from .walk import (WalkProviderResult, WalkRequest, WalkResponse,
    output_model, validate_citations, validate_output_identity, validate_walk_payload,
    validate_walk_record, walk_prompt, walk_record_digest)


class BriefGenerationError(RuntimeError):
    pass


class AmbiguousResult(BaseModel, extra="forbid", frozen=True, strict=True):
    kind: Literal["unknown"]


class _CrawlModelPacket(BaseModel, extra="forbid", frozen=True):
    admitted_request: dict[str, Any]
    release_profile: ReleaseProfile
    codex_home: str
    auth_generation: StrictInt = Field(ge=1)
    admitted_at: datetime
    workflow_id: str


class _WalkModelPacket(BaseModel, extra="forbid", frozen=True):
    admitted_request: dict[str, Any]
    release_profile: WalkReleaseProfile
    codex_home: str
    auth_generation: StrictInt = Field(ge=1)
    admitted_at: datetime
    workflow_id: str


def _request_body(prompt: str, profile: SubscriptionProfile, *, instructions: str = SYSTEM_PROMPT,
    schema: type[BaseModel] = contracts.EvidenceBrief) -> dict[str, Any]:
    return {"model": profile.model, "instructions": instructions, "input": prompt,
        "reasoning_effort": profile.reasoning_effort,
        "output_schema_digest": contracts.canonical_digest(schema.model_json_schema()),
        "sandbox": "read-only", "approval_mode": "deny-all", "tools": [],
        "web_search": "disabled"}


def _dispatch(packet: _CrawlModelPacket | _WalkModelPacket, admitted: Any,
    request_body: dict[str, Any]) -> SubscriptionDispatch:
    now = datetime.now(UTC)
    profile = packet.release_profile
    if not profile.current_at(now):
        raise BriefGenerationError("release profile evidence is expired")
    if packet.admitted_at.tzinfo is None or packet.admitted_at > now + timedelta(seconds=5):
        raise BriefGenerationError("admission timestamp is invalid")
    encoded = json.dumps(request_body, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    input_bytes = len(encoded)
    if input_bytes > profile.max_input_bytes:
        raise BriefGenerationError("model request exceeds the input-byte ceiling")
    queue_deadline = packet.admitted_at.astimezone(UTC) + timedelta(seconds=profile.queue_timeout_seconds)
    common = dict(workflow_id=packet.workflow_id, request_digest=admitted.request_digest,
        request_body_digest=contracts.canonical_digest(request_body), model=profile.model, reasoning_effort=profile.reasoning_effort, release_profile_digest=profile.digest(), disclosure_profile=admitted.disclosure_profile,
        disclosure_notice_digest=admitted.disclosure_notice_digest, external_disclosure_ack=admitted.external_disclosure_ack, subscription_route_id=profile.subscription_route_id, subscription_plan=profile.subscription_plan,
        auth_generation=packet.auth_generation, input_bytes=input_bytes, max_observed_input_tokens=profile.max_observed_input_tokens, max_observed_output_tokens=profile.max_observed_output_tokens, max_observed_reasoning_tokens=profile.max_observed_reasoning_tokens,
        queue_deadline=queue_deadline, wall_deadline=packet.admitted_at.astimezone(UTC) + timedelta(seconds=profile.wall_timeout_seconds))
    if isinstance(packet, _WalkModelPacket):
        return WalkFrozenDispatch(workflow_family=admitted.workflow_family,
            result_schema_digest=request_body["output_schema_digest"],
            artifact_sha256=admitted.artifact_sha256, **common)
    return FrozenDispatch(**common)


def _persist(frozen: SubscriptionDispatch, state: str, audit: dict[str, Any] | None, *, result: dict[str, Any] | None = None, reason: str | None = None, expected: str = "dispatching") -> None:
    try:
        transition(frozen.workflow_id, expected, state, result=result, audit=audit, hold_reason=reason)
    except Exception:
        ambiguity = f"{reason or 'result'}_persistence_ambiguous"
        try:
            recorded = reserve(frozen.model_dump(mode="json"), frozen.digest())
        except Exception:
            hold_unknown(frozen.workflow_id, ambiguity, audit=audit)
        target = state, result, audit, reason
        observed = recorded.state, recorded.result, recorded.audit, recorded.hold_reason
        if observed != target:
            hold_unknown(frozen.workflow_id, ambiguity, audit=audit)


def _begin_dispatch(frozen: SubscriptionDispatch) -> None:
    try:
        transition(frozen.workflow_id, "reserved", "dispatching",
            hold_reason=phase_marker("adapter_construction_started"))
    except Exception:  # noqa: S110 -- exact readback reconciles an ambiguous commit acknowledgement
        pass
    else:
        return
    try:
        effect = reserve(frozen.model_dump(mode="json"), frozen.digest())
    except Exception:
        hold_unknown(frozen.workflow_id, "initial_phase_persistence_ambiguous")
    safe = effect.state == "reserved" or (effect.state == "dispatching"
        and dispatch_phase(effect) == "adapter_construction_started")
    if not safe:
        hold_unknown(frozen.workflow_id, "initial_phase_persistence_ambiguous")
    _persist(frozen, "failed", None, reason="pre_turn_failure", expected=effect.state)
    raise BriefGenerationError("provider failed before turn invocation")


async def _run_inference(packet: _CrawlModelPacket | _WalkModelPacket, *,
    adapter_factory: Any = codex_adapter.CodexSubscriptionAdapter) -> Any:
    error: tuple[type[BriefGenerationError | AmbiguousEffectError], str] | None = None
    try:
        result = await _run_inference_sensitive(packet, adapter_factory=adapter_factory)
    except (BriefGenerationError, AmbiguousEffectError, EffectConflictError) as exc:
        error = (BriefGenerationError, "recorded model effect conflicts with request") if isinstance(exc, EffectConflictError) else (type(exc), str(exc))
    if error is not None:
        del packet, adapter_factory
        raise error[0](error[1]) from None
    return result


async def _run_inference_sensitive(packet: _CrawlModelPacket | _WalkModelPacket, *,
    adapter_factory: Any = codex_adapter.CodexSubscriptionAdapter) -> Any:
    invalid_admission = False
    try:
        admitted = (validate_walk_payload(packet.admitted_request) if isinstance(
            packet, _WalkModelPacket) else validate_workflow_payload(packet.admitted_request))
    except IntakeError:
        invalid_admission = True
    if invalid_admission:
        raise BriefGenerationError("admitted request failed validation") from None
    if packet.auth_generation != packet.release_profile.auth_generation:
        raise BriefGenerationError("subscription auth generation changed after admission")
    if isinstance(admitted, WalkRequest):
        instructions, prompt = walk_prompt(admitted)
        request_body = _request_body(prompt, packet.release_profile,
            instructions=instructions, schema=output_model(admitted.workflow_family))
    else:
        request_body = _request_body(build_user_prompt(admitted.question,
            [source.__dict__ for source in admitted.sources]), packet.release_profile)
    dispatch = _dispatch(packet, admitted, request_body)
    effect = reserve(dispatch.model_dump(mode="json"), dispatch.digest())

    def recorded() -> Any:
        if effect.result is None or effect.audit is None:
            raise BriefGenerationError("recorded model effect lacks result or usage audit")
        invalid_record = False
        try:
            if isinstance(dispatch, WalkFrozenDispatch):
                record = validate_walk_record(WalkProviderResult.model_validate(
                    {"output": effect.result, "audit": effect.audit}))
                audit = record.audit
                output = validate_output_identity(admitted, record.output)
                sources = packet.admitted_request["canonical"]["sources"]
                if validate_citations(output, sources) != output:
                    raise ValueError
            else:
                record = contracts.ProviderResult.model_validate(
                    {"brief": effect.result, "audit": effect.audit})
                contracts.validate_provider_record(record)
                audit, output = record.audit, record.brief
                if resolve_citations(output, packet.admitted_request["sources"]) != output:
                    raise ValueError
        except ValueError:
            invalid_record = True
        if invalid_record:
            raise BriefGenerationError("recorded model effect failed validation") from None
        return (WalkProviderResult(output=output, audit=audit) if isinstance(
            dispatch, WalkFrozenDispatch) else contracts.ProviderResult(brief=output, audit=audit))

    if effect.state == "reconciled":
        return recorded()
    if effect.state == "failed":
        raise BriefGenerationError("recorded model effect failed")
    if effect.state == "dispatching" and dispatch_phase(effect) in PRE_TURN_PHASES:
        _persist(dispatch, "failed", None, reason="pre_turn_recovery")
        raise BriefGenerationError("recorded model effect failed before turn invocation")
    if effect.state in {"dispatching", "returned", "unknown"}:
        hold_unknown(packet.workflow_id, f"recovery_from_{effect.state}", audit=effect.audit)
    if datetime.now(UTC) > dispatch.queue_deadline:
        transition(packet.workflow_id, "reserved", "failed", hold_reason="queue_deadline_expired")
        raise BriefGenerationError("model request exceeded the queue deadline")

    _begin_dispatch(dispatch)
    def record_phase(phase: str) -> None:
        transition(packet.workflow_id, "dispatching", "dispatching", hold_reason=phase_marker(phase))
    try:
        adapter = adapter_factory(packet.release_profile, Path(packet.codex_home),
            auth_generation=packet.auth_generation, phase_recorder=record_phase)
    except Exception:
        _persist(dispatch, "failed", None, reason="pre_turn_failure")
        raise BriefGenerationError("provider failed before turn invocation") from None
    try:
        provider_result = await adapter.generate(dispatch, request_body)
    except codex_adapter.ProviderRejectedError as exc:
        rejected_audit = None if exc.audit is None else exc.audit.model_dump(mode="json")
        _persist(dispatch, "failed", rejected_audit, reason="provider_rejected")
        raise BriefGenerationError("provider response was rejected") from None
    except codex_adapter.ProviderAmbiguousError as exc:
        audit = None if exc.audit is None else exc.audit.model_dump(mode="json")
        hold_unknown(packet.workflow_id, "provider_outcome_ambiguous", audit=audit)
    except codex_adapter.AdapterError:
        _persist(dispatch, "failed", None, reason="pre_turn_failure")
        raise BriefGenerationError("provider failed before turn invocation") from None
    invalid_citation = False
    try:
        if isinstance(dispatch, WalkFrozenDispatch):
            output = validate_output_identity(admitted, provider_result.output)
            output = validate_citations(output,
                packet.admitted_request["canonical"]["sources"])
        else:
            output = resolve_citations(provider_result.brief, packet.admitted_request["sources"])
    except ValueError:
        invalid_citation = True
    if invalid_citation:
        rejected_audit = provider_result.audit.model_dump(mode="json")
        _persist(dispatch, "failed", rejected_audit, reason="invalid_citation")
        raise BriefGenerationError("provider output failed citation validation") from None
    result = output.model_dump(mode="json")
    digest = contracts.canonical_digest(result)
    audit = provider_result.audit.model_copy(update={"validated_result_digest": digest})
    record_digest = (walk_record_digest(output, audit) if isinstance(
        dispatch, WalkFrozenDispatch) else contracts.provider_record_digest(output, audit))
    audit = audit.model_copy(update={"record_digest": record_digest})
    audit_json = audit.model_dump(mode="json")
    _persist(dispatch, "reconciled", audit_json, result=result)
    return (WalkProviderResult(output=output, audit=audit) if isinstance(
        dispatch, WalkFrozenDispatch) else contracts.ProviderResult(brief=output, audit=audit))


@DBOS.step(name="crawl_observe_model_v2", retries_allowed=False)
async def _crawl_model_step(packet: _CrawlModelPacket) -> contracts.ProviderResult | AmbiguousResult:
    error: tuple[type[BriefGenerationError], str] | None = None
    try:
        result = await _run_inference(packet)
    except AmbiguousEffectError:
        return AmbiguousResult(kind="unknown")
    except BriefGenerationError as exc:
        error = type(exc), str(exc)
    if error is not None:
        del packet
        raise error[0](error[1]) from None
    return result


@DBOS.step(name="walk_proposal_model_v1", retries_allowed=False)
async def _walk_model_step(packet: _WalkModelPacket) -> WalkProviderResult | AmbiguousResult:
    try:
        return await _run_inference(packet)
    except AmbiguousEffectError:
        return AmbiguousResult(kind="unknown")
    except BriefGenerationError as exc:
        del packet
        raise BriefGenerationError(str(exc)) from None


crawl_observe_queue = Queue("crawl-observe-v1", concurrency=1, worker_concurrency=1)
walk_queue = crawl_observe_queue


@DBOS.workflow()
async def evidence_brief_workflow(payload: dict[str, Any], workflow_id: str, release_profile: dict[str, Any],
    codex_home: str, auth_generation: int, admitted_at: str) -> dict[str, Any]:
    error: tuple[type[BriefGenerationError | AmbiguousEffectError], str] | None = None
    try:
        result = await _evidence_brief_workflow_sensitive(payload, workflow_id, release_profile,
            codex_home, auth_generation, admitted_at)
    except (BriefGenerationError, AmbiguousEffectError) as exc:
        error = type(exc), str(exc)
    if error is not None:
        del payload, workflow_id, release_profile, codex_home, auth_generation, admitted_at
        raise error[0](error[1]) from None
    return result


async def _evidence_brief_workflow_sensitive(payload: dict[str, Any], workflow_id: str, release_profile: dict[str, Any],
    codex_home: str, auth_generation: int, admitted_at: str) -> dict[str, Any]:
    invalid_admission = False
    try:
        admitted = validate_workflow_payload(payload)
        profile = ReleaseProfile.model_validate(release_profile)
        packet = _CrawlModelPacket(admitted_request=admitted.workflow_payload(), release_profile=profile, codex_home=codex_home, auth_generation=auth_generation, admitted_at=admitted_at,
            workflow_id=workflow_id)
    except (IntakeError, ValueError):
        invalid_admission = True
    if invalid_admission:
        raise BriefGenerationError("workflow admission is invalid") from None
    result = await _crawl_model_step(packet)
    if isinstance(result, AmbiguousResult):
        raise AmbiguousEffectError("model effect outcome requires manual reconciliation")
    return contracts.EvidenceBriefResponse(**result.brief.model_dump(mode="json"), request_digest=admitted.request_digest, workflow_id=workflow_id,
        markdown=render_markdown(result.brief), provider_audit=result.audit).model_dump(mode="json")


@DBOS.workflow()
async def walk_proposal_workflow(payload: dict[str, Any], workflow_id: str,
    release_profile: dict[str, Any], codex_home: str, auth_generation: int,
    admitted_at: str) -> dict[str, Any]:
    error: tuple[type[BriefGenerationError | AmbiguousEffectError], str] | None = None
    try:
        result = await _walk_proposal_workflow_sensitive(payload, workflow_id, release_profile,
            codex_home, auth_generation, admitted_at)
    except (BriefGenerationError, AmbiguousEffectError) as exc:
        error = type(exc), str(exc)
    if error is not None:
        del payload, workflow_id, release_profile, codex_home, auth_generation, admitted_at
        raise error[0](error[1]) from None
    return result


async def _walk_proposal_workflow_sensitive(payload: dict[str, Any], workflow_id: str,
    release_profile: dict[str, Any], codex_home: str, auth_generation: int,
    admitted_at: str) -> dict[str, Any]:
    invalid_admission = False
    try:
        admitted = validate_walk_payload(payload)
        profile = WalkReleaseProfile.model_validate(release_profile)
        if admitted.release_profile_digest != profile.digest():
            raise ValueError
        packet = _WalkModelPacket(admitted_request=admitted.workflow_payload(),
            release_profile=profile, codex_home=codex_home,
            auth_generation=auth_generation, admitted_at=admitted_at,
            workflow_id=workflow_id)
    except (IntakeError, ValueError):
        invalid_admission = True
    if invalid_admission:
        raise BriefGenerationError("Walk workflow admission is invalid") from None
    result = await _walk_model_step(packet)
    if isinstance(result, AmbiguousResult):
        raise AmbiguousEffectError("model effect outcome requires manual reconciliation")
    return WalkResponse(workflow_id=workflow_id, request_digest=admitted.request_digest,
        release_profile_digest=profile.digest(), workflow_family=admitted.workflow_family,
        artifact_sha256=admitted.artifact_sha256, output=result.output,
        provider_audit=result.audit).model_dump(mode="json")
