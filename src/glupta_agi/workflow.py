"""One durable, provider-fenced Crawl evidence workflow."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from dbos import DBOS, Queue
from pydantic import BaseModel, ConfigDict, Field, StrictInt
from pydantic_ai import Agent
from pydantic_ai.durable_exec.dbos import DBOSDurability
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from . import contracts, openai_adapter
from .brief import SYSTEM_PROMPT, build_user_prompt, render_markdown, resolve_citations
from .effects import AmbiguousEffectError, EffectConflictError, hold_unknown, reserve, transition
from .inference import FrozenDispatch, ReleaseProfile, usd_upper_bound
from .intake import IntakeError, validate_workflow_payload

_REQUEST_OVERHEAD_BYTES = 4096


class BriefGenerationError(RuntimeError):
    pass


class _CrawlModelPacket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    admitted_request: dict[str, Any]
    release_profile: ReleaseProfile
    credential_file: str
    credential_generation: StrictInt = Field(ge=1)
    admitted_at: datetime
    workflow_id: str


def _request_body(prompt: str, profile: ReleaseProfile) -> dict[str, Any]:
    schema = contracts.EvidenceBrief.model_json_schema()
    return {"model": profile.model, "instructions": SYSTEM_PROMPT, "input": prompt,
        "reasoning": {"effort": "medium"}, "text": {"format": {"type": "json_schema",
            "name": "crawl_evidence_brief", "schema": schema, "strict": True}},
        "max_output_tokens": profile.max_output_tokens, "service_tier": profile.service_tier, "store": False, "background": False,  # noqa: E501
        "stream": False, "tools": [], "tool_choice": "none", "truncation": "disabled"}


def _dispatch(packet: _CrawlModelPacket, admitted: Any, request_body: dict[str, Any]) -> FrozenDispatch:  # noqa: E501
    now = datetime.now(UTC)
    profile = packet.release_profile
    if not profile.current_at(now):
        raise BriefGenerationError("release profile evidence is expired")
    if packet.admitted_at.tzinfo is None or packet.admitted_at > now + timedelta(seconds=5):
        raise BriefGenerationError("admission timestamp is invalid")
    encoded = json.dumps(request_body, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()  # noqa: E501
    input_bound = len(encoded) + _REQUEST_OVERHEAD_BYTES
    if input_bound > profile.max_input_tokens:
        raise BriefGenerationError("model request exceeds the input-token ceiling")
    cost_bound = usd_upper_bound(input_bound, profile.max_output_tokens)
    if cost_bound > profile.max_usd_micros:
        raise BriefGenerationError("model request exceeds the USD ceiling")
    queue_deadline = packet.admitted_at.astimezone(UTC) + timedelta(seconds=profile.queue_timeout_seconds)  # noqa: E501
    return FrozenDispatch(workflow_id=packet.workflow_id, request_digest=admitted.request_digest,
        request_body_digest=contracts.canonical_digest(request_body), model=profile.model,
        release_profile_digest=profile.digest(), disclosure_profile=admitted.disclosure_profile,
        disclosure_notice_digest=admitted.disclosure_notice_digest, external_disclosure_ack=admitted.external_disclosure_ack, service_tier=profile.service_tier,  # noqa: E501
        project_id=profile.project_id, service_account_id=profile.service_account_id, api_key_id=profile.api_key_id, credential_generation=packet.credential_generation,  # noqa: E501
        input_token_upper_bound=input_bound, max_output_tokens=profile.max_output_tokens, max_usd_micros=profile.max_usd_micros, queue_deadline=queue_deadline,  # noqa: E501
        wall_timeout_seconds=profile.wall_timeout_seconds, wall_deadline=packet.admitted_at.astimezone(UTC) + timedelta(seconds=profile.wall_timeout_seconds))  # noqa: E501


def _usage(audit: contracts.ProviderAudit) -> RequestUsage:
    return RequestUsage(input_tokens=audit.input_tokens, output_tokens=audit.output_tokens,
        cache_write_tokens=audit.cache_write_input_tokens, cache_read_tokens=audit.cached_input_tokens,  # noqa: E501
        details={"reasoning_output_tokens": audit.reasoning_tokens, "cost_upper_bound_micros": audit.cost_upper_bound_micros})  # noqa: E501


def _persist(
    frozen: FrozenDispatch, state: str, audit: dict[str, Any] | None, *,
    result: dict[str, Any] | None = None, reason: str | None = None,
) -> None:
    try:
        transition(frozen.workflow_id, "dispatching", state, result=result, audit=audit,
                   hold_reason=reason)
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


async def _run_inference(packet: _CrawlModelPacket, *, adapter_factory: Any = openai_adapter.OpenAIResponsesAdapter) -> tuple[contracts.ProviderResult, RequestUsage]:  # noqa: E501
    error: tuple[type[BriefGenerationError | AmbiguousEffectError], str] | None = None
    try:
        result = await _run_inference_sensitive(packet, adapter_factory=adapter_factory)
    except (BriefGenerationError, AmbiguousEffectError, EffectConflictError) as exc:
        error = (BriefGenerationError, "recorded model effect conflicts with request") if isinstance(exc, EffectConflictError) else (type(exc), str(exc))  # noqa: E501
    if error is not None:
        del packet, adapter_factory
        raise error[0](error[1]) from None
    return result


async def _run_inference_sensitive(packet: _CrawlModelPacket, *, adapter_factory: Any = openai_adapter.OpenAIResponsesAdapter) -> tuple[contracts.ProviderResult, RequestUsage]:  # noqa: E501
    invalid_admission = False
    try:
        admitted = validate_workflow_payload(packet.admitted_request)
    except IntakeError:
        invalid_admission = True
    if invalid_admission:
        raise BriefGenerationError("admitted request failed validation") from None
    if packet.credential_generation != packet.release_profile.credential_generation:
        raise BriefGenerationError("credential generation changed after admission")
    request_body = _request_body(build_user_prompt(admitted.question,
        [source.__dict__ for source in admitted.sources]), packet.release_profile)
    dispatch = _dispatch(packet, admitted, request_body)
    effect = reserve(dispatch.model_dump(mode="json"), dispatch.digest())

    def recorded() -> tuple[contracts.ProviderResult, RequestUsage]:
        if effect.result is None or effect.audit is None:
            raise BriefGenerationError("recorded model effect lacks result or usage audit")
        invalid_record = False
        try:
            record = contracts.ProviderResult.model_validate({"brief": effect.result, "audit": effect.audit})  # noqa: E501
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

    adapter = adapter_factory(packet.release_profile, Path(packet.credential_file), credential_generation=packet.credential_generation)  # noqa: E501
    effect = transition(packet.workflow_id, "reserved", "dispatching")
    try:
        provider_result = await adapter.generate(dispatch, request_body)
    except openai_adapter.ProviderRejectedError as exc:
        rejected_audit = None if exc.audit is None else exc.audit.model_dump(mode="json")
        _persist(dispatch, "failed", rejected_audit, reason="provider_rejected")
        raise BriefGenerationError("provider response was rejected") from None
    except openai_adapter.ProviderAmbiguousError as exc:
        audit = None if exc.audit is None else exc.audit.model_dump(mode="json")
        hold_unknown(packet.workflow_id, "provider_outcome_ambiguous", audit=audit)
    except openai_adapter.AdapterError:
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
    audit = audit.model_copy(update={"record_digest": contracts.provider_record_digest(brief, audit)})  # noqa: E501
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
    del info
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
        return ModelResponse(parts=[TextPart('"unknown"')], usage=RequestUsage())
    return ModelResponse(parts=[TextPart(result.model_dump_json())], usage=usage)


_crawl_durability = DBOSDurability(name="crawl_observe_agent", model_step_config={"retries_allowed": False}, parallel_execution_mode="sequential", register_legacy_workflows=False)  # noqa: E501
_crawl_agent = Agent(FunctionModel(_crawl_model, model_name="openai-responses-adapter"), name="crawl_observe_agent", output_type=contracts.ProviderResult | Literal["unknown"], retries=0, capabilities=[_crawl_durability])  # noqa: E501
crawl_observe_queue = Queue("crawl-observe-v1", concurrency=1, worker_concurrency=1)


@DBOS.workflow()
async def evidence_brief_workflow(
    payload: dict[str, Any], workflow_id: str, release_profile: dict[str, Any],
    credential_file: str, credential_generation: int, admitted_at: str) -> dict[str, Any]:
    error: tuple[type[BriefGenerationError | AmbiguousEffectError], str] | None = None
    try:
        result = await _evidence_brief_workflow_sensitive(payload, workflow_id, release_profile,
            credential_file, credential_generation, admitted_at)
    except (BriefGenerationError, AmbiguousEffectError) as exc:
        error = type(exc), str(exc)
    if error is not None:
        del payload, workflow_id, release_profile, credential_file, credential_generation, admitted_at  # noqa: E501
        raise error[0](error[1]) from None
    return result


async def _evidence_brief_workflow_sensitive(payload: dict[str, Any], workflow_id: str,
    release_profile: dict[str, Any], credential_file: str, credential_generation: int,
    admitted_at: str) -> dict[str, Any]:
    invalid_admission = False
    try:
        admitted = validate_workflow_payload(payload)
        profile = ReleaseProfile.model_validate(release_profile)
        packet = _CrawlModelPacket(admitted_request=admitted.workflow_payload(), release_profile=profile,  # noqa: E501
            credential_file=credential_file, credential_generation=credential_generation, admitted_at=admitted_at, workflow_id=workflow_id)  # noqa: E501
    except (IntakeError, ValueError):
        invalid_admission = True
    if invalid_admission:
        raise BriefGenerationError("workflow admission is invalid") from None
    result = (await _crawl_agent.run(packet.model_dump_json(), retries=0)).output
    if result == "unknown":
        raise AmbiguousEffectError("model effect outcome requires manual reconciliation")
    return contracts.EvidenceBriefResponse(**result.brief.model_dump(mode="json"), request_digest=admitted.request_digest, workflow_id=workflow_id,  # noqa: E501
        markdown=render_markdown(result.brief), provider_audit=result.audit).model_dump(mode="json")
