# ruff: noqa: E501
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from dbos import DBOS, Queue
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from pydantic_ai import Agent
from pydantic_ai.durable_exec.dbos import DBOSDurability
from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from . import codex_adapter, contracts
from .brief import SYSTEM_PROMPT, build_user_prompt, render_markdown, resolve_citations
from .effects import AmbiguousEffectError, EffectConflictError, hold_unknown, reserve, transition
from .inference import FrozenDispatch, ReleaseProfile
from .intake import IntakeError, validate_workflow_payload


class BriefGenerationError(RuntimeError):
    pass


class AmbiguousResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    kind: Literal["unknown"]


class _CrawlModelPacket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    admitted_request: dict[str, Any]
    release_profile: ReleaseProfile
    codex_home: str
    auth_generation: StrictInt = Field(ge=1)
    admitted_at: datetime
    workflow_id: str


def _request_body(prompt: str, profile: ReleaseProfile) -> dict[str, Any]:
    return {"model": profile.model, "instructions": SYSTEM_PROMPT, "input": prompt,
        "reasoning_effort": profile.reasoning_effort,
        "output_schema_digest": contracts.canonical_digest(contracts.EvidenceBrief.model_json_schema()),
        "sandbox": "read-only", "approval_mode": "deny-all", "tools": [], "web_search": "disabled"}


def _dispatch(packet: _CrawlModelPacket, admitted: Any, request_body: dict[str, Any]) -> FrozenDispatch:
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
    return FrozenDispatch(workflow_id=packet.workflow_id, request_digest=admitted.request_digest,
        request_body_digest=contracts.canonical_digest(request_body), model=profile.model,
        reasoning_effort=profile.reasoning_effort, release_profile_digest=profile.digest(),
        disclosure_profile=admitted.disclosure_profile,
        disclosure_notice_digest=admitted.disclosure_notice_digest, external_disclosure_ack=admitted.external_disclosure_ack,
        subscription_route_id=profile.subscription_route_id, subscription_plan=profile.subscription_plan,
        auth_generation=packet.auth_generation, input_bytes=input_bytes,
        max_observed_input_tokens=profile.max_observed_input_tokens,
        max_observed_output_tokens=profile.max_observed_output_tokens,
        max_observed_reasoning_tokens=profile.max_observed_reasoning_tokens,
        queue_deadline=queue_deadline, wall_deadline=packet.admitted_at.astimezone(UTC)
        + timedelta(seconds=profile.wall_timeout_seconds))


def _usage(audit: contracts.ProviderAudit) -> RequestUsage:
    return RequestUsage(input_tokens=audit.input_tokens, output_tokens=audit.output_tokens,
        cache_write_tokens=audit.cache_write_input_tokens, cache_read_tokens=audit.cached_input_tokens,
        details={"reasoning_output_tokens": audit.reasoning_tokens})


def _persist(frozen: FrozenDispatch, state: str, audit: dict[str, Any] | None, *,
    result: dict[str, Any] | None = None, reason: str | None = None) -> None:
    try:
        transition(frozen.workflow_id, "dispatching", state, result=result, audit=audit, hold_reason=reason)
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


async def _run_inference(packet: _CrawlModelPacket, *, adapter_factory: Any = codex_adapter.CodexSubscriptionAdapter) -> tuple[contracts.ProviderResult, RequestUsage]:
    error: tuple[type[BriefGenerationError | AmbiguousEffectError], str] | None = None
    try:
        result = await _run_inference_sensitive(packet, adapter_factory=adapter_factory)
    except (BriefGenerationError, AmbiguousEffectError, EffectConflictError) as exc:
        error = (BriefGenerationError, "recorded model effect conflicts with request") if isinstance(exc, EffectConflictError) else (type(exc), str(exc))
    if error is not None:
        del packet, adapter_factory
        raise error[0](error[1]) from None
    return result


async def _run_inference_sensitive(packet: _CrawlModelPacket, *, adapter_factory: Any = codex_adapter.CodexSubscriptionAdapter) -> tuple[contracts.ProviderResult, RequestUsage]:
    invalid_admission = False
    try:
        admitted = validate_workflow_payload(packet.admitted_request)
    except IntakeError:
        invalid_admission = True
    if invalid_admission:
        raise BriefGenerationError("admitted request failed validation") from None
    if packet.auth_generation != packet.release_profile.auth_generation:
        raise BriefGenerationError("subscription auth generation changed after admission")
    request_body = _request_body(build_user_prompt(admitted.question,
        [source.__dict__ for source in admitted.sources]), packet.release_profile)
    dispatch = _dispatch(packet, admitted, request_body)
    effect = reserve(dispatch.model_dump(mode="json"), dispatch.digest())

    def recorded() -> tuple[contracts.ProviderResult, RequestUsage]:
        if effect.result is None or effect.audit is None:
            raise BriefGenerationError("recorded model effect lacks result or usage audit")
        invalid_record = False
        try:
            record = contracts.ProviderResult.model_validate({"brief": effect.result, "audit": effect.audit})
            contracts.validate_provider_record(record)
            audit, brief = record.audit, record.brief
            if resolve_citations(brief, packet.admitted_request["sources"]) != brief:
                raise ValueError
        except ValueError:
            invalid_record = True
        if invalid_record:
            raise BriefGenerationError("recorded model effect failed validation") from None
        return contracts.ProviderResult(brief=brief, audit=audit), _usage(audit)

    if effect.state == "reconciled":
        return recorded()
    if effect.state == "failed":
        raise BriefGenerationError("recorded model effect failed")
    if effect.state in {"dispatching", "returned", "unknown"}:
        hold_unknown(packet.workflow_id, f"recovery_from_{effect.state}", audit=effect.audit)
    if datetime.now(UTC) > dispatch.queue_deadline:
        transition(packet.workflow_id, "reserved", "failed", hold_reason="queue_deadline_expired")
        raise BriefGenerationError("model request exceeded the queue deadline")

    adapter = adapter_factory(packet.release_profile, Path(packet.codex_home), auth_generation=packet.auth_generation)
    effect = transition(packet.workflow_id, "reserved", "dispatching")
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
        hold_unknown(packet.workflow_id, "provider_outcome_ambiguous")
    invalid_citation = False
    try:
        brief = resolve_citations(provider_result.brief, packet.admitted_request["sources"])
    except ValueError:
        invalid_citation = True
    if invalid_citation:
        rejected_audit = provider_result.audit.model_dump(mode="json")
        _persist(dispatch, "failed", rejected_audit, reason="invalid_citation")
        raise BriefGenerationError("provider output failed citation validation") from None
    result = brief.model_dump(mode="json")
    digest = contracts.canonical_digest(result)
    audit = provider_result.audit.model_copy(update={"validated_result_digest": digest})
    audit = audit.model_copy(update={"record_digest": contracts.provider_record_digest(brief, audit)})
    audit_json = audit.model_dump(mode="json")
    _persist(dispatch, "reconciled", audit_json, result=result)
    return contracts.ProviderResult(brief=brief, audit=audit), _usage(audit)


async def _crawl_model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    error: tuple[type[BriefGenerationError], str] | None = None
    try:
        response = await _crawl_model_sensitive(messages, info)
    except BriefGenerationError as exc:
        error = type(exc), str(exc)
    if error is not None:
        del messages, info
        raise error[0](error[1]) from None
    return response


async def _crawl_model_sensitive(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    if info.allow_text_output or {tool.name for tool in info.output_tools} != {
        "final_result_ProviderResult", "final_result_AmbiguousResult"
    }:
        raise BriefGenerationError("Crawl model output contract changed")
    parts = (part for message in reversed(messages) for part in reversed(message.parts))
    contents = (part.content for part in parts if isinstance(part, UserPromptPart))
    raw_packet = next((content for content in contents if isinstance(content, str)), None)
    if raw_packet is None:
        raise BriefGenerationError("Crawl model packet is missing")
    invalid_packet = False
    try:
        packet = _CrawlModelPacket.model_validate_json(raw_packet)
    except ValueError:
        invalid_packet = True
    if invalid_packet:
        raise BriefGenerationError("Crawl model packet is invalid") from None
    try:
        result, usage = await _run_inference(packet)
    except AmbiguousEffectError:
        return ModelResponse(parts=[ToolCallPart(
            "final_result_AmbiguousResult", {"kind": "unknown"}
        )], usage=RequestUsage())
    return ModelResponse(parts=[ToolCallPart(
        "final_result_ProviderResult", result.model_dump(mode="json")
    )], usage=usage)


_crawl_durability = DBOSDurability(name="crawl_observe_agent", model_step_config={"retries_allowed": False}, parallel_execution_mode="sequential", register_legacy_workflows=False)
_crawl_agent = Agent(FunctionModel(_crawl_model, model_name="codex-subscription-adapter"), name="crawl_observe_agent", output_type=contracts.ProviderResult | AmbiguousResult, retries=0, capabilities=[_crawl_durability])
crawl_observe_queue = Queue("crawl-observe-v1", concurrency=1, worker_concurrency=1)


@DBOS.workflow()
async def evidence_brief_workflow(
    payload: dict[str, Any], workflow_id: str, release_profile: dict[str, Any],
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


async def _evidence_brief_workflow_sensitive(
    payload: dict[str, Any], workflow_id: str, release_profile: dict[str, Any],
    codex_home: str, auth_generation: int, admitted_at: str) -> dict[str, Any]:
    invalid_admission = False
    try:
        admitted = validate_workflow_payload(payload)
        profile = ReleaseProfile.model_validate(release_profile)
        packet = _CrawlModelPacket(admitted_request=admitted.workflow_payload(), release_profile=profile,
            codex_home=codex_home, auth_generation=auth_generation, admitted_at=admitted_at,
            workflow_id=workflow_id)
    except (IntakeError, ValueError):
        invalid_admission = True
    if invalid_admission:
        raise BriefGenerationError("workflow admission is invalid") from None
    result = (await _crawl_agent.run(packet.model_dump_json(), retries=0)).output
    if isinstance(result, AmbiguousResult):
        raise AmbiguousEffectError("model effect outcome requires manual reconciliation")
    return contracts.EvidenceBriefResponse(**result.brief.model_dump(mode="json"),
        request_digest=admitted.request_digest, workflow_id=workflow_id,
        markdown=render_markdown(result.brief), provider_audit=result.audit).model_dump(mode="json")
