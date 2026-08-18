"""One durable, provider-fenced Crawl evidence workflow."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from dbos import DBOS, Queue
from pydantic import BaseModel, ConfigDict
from pydantic_ai import Agent
from pydantic_ai.durable_exec.dbos import DBOSDurability
from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.usage import RequestUsage

from .brief import SYSTEM_PROMPT, build_user_prompt, render_markdown, resolve_citations
from .contracts import EvidenceBrief
from .effects import hold_unknown, reserve, transition
from .inference import (
    FrozenDispatch,
    ProviderAudit,
    ReleaseProfile,
    canonical_digest,
    provider_record_digest,
    usd_upper_bound,
)
from .openai_adapter import (
    AdapterError,
    OpenAIResponsesAdapter,
    ProviderAmbiguousError,
    ProviderRejectedError,
)

_REQUEST_OVERHEAD_BYTES = 4096


class BriefGenerationError(RuntimeError):
    pass


class _CrawlModelPacket(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    prompt: str
    sources: list[dict[str, Any]]
    release_profile: ReleaseProfile
    credential_file: str
    admitted_at: datetime
    workflow_id: str
    request_digest: str


def _request_body(prompt: str, profile: ReleaseProfile) -> dict[str, Any]:
    schema = EvidenceBrief.model_json_schema()
    return {
        "model": profile.model,
        "instructions": SYSTEM_PROMPT,
        "input": prompt,
        "reasoning": {"effort": "medium"},
        "text": {
            "format": {
                "type": "json_schema",
                "name": "crawl_evidence_brief",
                "schema": schema,
                "strict": True,
            }
        },
        "max_output_tokens": profile.max_output_tokens,
        "store": False,
        "background": False,
        "stream": False,
        "tools": [],
        "tool_choice": "none",
        "truncation": "disabled",
    }


def _dispatch(packet: _CrawlModelPacket, request_body: dict[str, Any]) -> FrozenDispatch:
    now = datetime.now(UTC)
    profile = packet.release_profile
    if not profile.current_at(now):
        raise BriefGenerationError("release profile evidence is expired")
    if packet.admitted_at.tzinfo is None or packet.admitted_at > now + timedelta(seconds=5):
        raise BriefGenerationError("admission timestamp is invalid")
    encoded = json.dumps(
        request_body, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode()
    input_bound = len(encoded) + _REQUEST_OVERHEAD_BYTES
    if input_bound > profile.max_input_tokens:
        raise BriefGenerationError("model request exceeds the input-token ceiling")
    cost_bound = usd_upper_bound(input_bound, profile.max_output_tokens)
    if cost_bound > profile.max_usd_micros:
        raise BriefGenerationError("model request exceeds the USD ceiling")
    queue_deadline = packet.admitted_at.astimezone(UTC) + timedelta(
        seconds=profile.queue_timeout_seconds
    )
    return FrozenDispatch(
        workflow_id=packet.workflow_id,
        request_digest=packet.request_digest,
        request_body_digest=canonical_digest(request_body),
        release_profile_digest=profile.digest(),
        model=profile.model,
        input_token_upper_bound=input_bound,
        max_output_tokens=profile.max_output_tokens,
        max_usd_micros=profile.max_usd_micros,
        queue_deadline=queue_deadline,
        wall_deadline=packet.admitted_at.astimezone(UTC)
        + timedelta(seconds=profile.wall_timeout_seconds),
        wall_timeout_seconds=profile.wall_timeout_seconds,
    )


def _usage(audit: ProviderAudit) -> RequestUsage:
    return RequestUsage(
        input_tokens=audit.input_tokens,
        cache_write_tokens=audit.cache_write_input_tokens,
        cache_read_tokens=audit.cached_input_tokens,
        output_tokens=audit.output_tokens,
        details={
            "reasoning_output_tokens": audit.reasoning_tokens,
            "cost_upper_bound_micros": audit.cost_upper_bound_micros,
        },
    )


async def _run_inference(
    packet: _CrawlModelPacket, *, adapter_factory: Any = OpenAIResponsesAdapter
) -> tuple[EvidenceBrief, RequestUsage]:
    request_body = _request_body(packet.prompt, packet.release_profile)
    dispatch = _dispatch(packet, request_body)
    effect = reserve(dispatch.model_dump(mode="json"), dispatch.digest())

    def recorded() -> tuple[EvidenceBrief, RequestUsage]:
        if effect.result is None or effect.audit is None:
            raise BriefGenerationError("recorded model effect lacks result or usage audit")
        try:
            audit = ProviderAudit.model_validate(effect.audit)
            brief = EvidenceBrief.model_validate(effect.result)
            result_digest = canonical_digest(brief.model_dump(mode="json"))
            invalid = (
                audit.validated_result_digest != result_digest,
                audit.record_digest != provider_record_digest(brief, audit),
                resolve_citations(brief, packet.sources) != brief,
            )
            if any(invalid):
                raise ValueError
        except ValueError:
            raise BriefGenerationError("recorded model effect failed validation") from None
        if effect.state == "returned":
            transition(packet.workflow_id, "returned", "reconciled")
        return brief, _usage(audit)

    if effect.state in {"returned", "reconciled"}:
        return recorded()
    if effect.state == "failed":
        raise BriefGenerationError("recorded model effect failed")
    if effect.state in {"dispatching", "unknown"}:
        hold_unknown(effect, f"recovery_from_{effect.state}")
    if datetime.now(UTC) > dispatch.queue_deadline:
        transition(packet.workflow_id, "reserved", "failed", hold_reason="queue_deadline_expired")
        raise BriefGenerationError("model request exceeded the queue deadline")

    adapter = adapter_factory(packet.release_profile, Path(packet.credential_file))
    effect = transition(packet.workflow_id, "reserved", "dispatching")
    try:
        provider_result = await adapter.generate(dispatch, request_body)
    except ProviderRejectedError as exc:
        rejected_audit = None if exc.audit is None else exc.audit.model_dump(mode="json")
        transition(packet.workflow_id, "dispatching", "failed", audit=rejected_audit,
                   hold_reason="provider_rejected")
        raise BriefGenerationError("provider response was rejected") from None
    except (ProviderAmbiguousError, AdapterError):
        hold_unknown(effect, "provider_outcome_ambiguous")
    try:
        brief = resolve_citations(provider_result.brief, packet.sources)
    except ValueError:
        rejected_audit = provider_result.audit.model_dump(mode="json")
        transition(packet.workflow_id, "dispatching", "failed", audit=rejected_audit,
                   hold_reason="invalid_citation")
        raise BriefGenerationError("provider output failed citation validation") from None
    result = brief.model_dump(mode="json")
    digest = canonical_digest(result)
    audit = provider_result.audit.model_copy(update={"validated_result_digest": digest})
    audit = audit.model_copy(update={"record_digest": provider_record_digest(brief, audit)})
    audit_json = audit.model_dump(mode="json")
    transition(packet.workflow_id, "dispatching", "returned", result=result, audit=audit_json)
    transition(packet.workflow_id, "returned", "reconciled")
    return brief, _usage(audit)


async def _crawl_model(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
    del info
    parts = (part for message in reversed(messages) for part in reversed(message.parts))
    contents = (part.content for part in parts if isinstance(part, UserPromptPart))
    raw_packet = next((content for content in contents if isinstance(content, str)), None)
    if raw_packet is None:
        raise BriefGenerationError("Crawl model packet is missing")
    brief, usage = await _run_inference(_CrawlModelPacket.model_validate_json(raw_packet))
    return ModelResponse(parts=[TextPart(brief.model_dump_json())], usage=usage)


_crawl_durability = DBOSDurability(
    name="crawl_observe_agent",
    model_step_config={"retries_allowed": False},
    parallel_execution_mode="sequential",
    register_legacy_workflows=False,
)
_crawl_agent = Agent(
    FunctionModel(_crawl_model, model_name="openai-responses-adapter"),
    name="crawl_observe_agent",
    output_type=EvidenceBrief,
    retries=0,
    capabilities=[_crawl_durability],
)
crawl_observe_queue = Queue("crawl-observe-v1", concurrency=1, worker_concurrency=1)


@DBOS.workflow()
async def evidence_brief_workflow(
    payload: dict[str, Any],
    workflow_id: str,
    release_profile: dict[str, Any],
    credential_file: str,
    admitted_at: str,
) -> dict[str, Any]:
    packet = _CrawlModelPacket(
        prompt=build_user_prompt(str(payload["question"]), payload["sources"]),
        sources=payload["sources"],
        release_profile=ReleaseProfile.model_validate(release_profile),
        credential_file=credential_file,
        admitted_at=admitted_at,
        workflow_id=workflow_id,
        request_digest=str(payload["request_digest"]),
    )
    brief = (await _crawl_agent.run(packet.model_dump_json(), retries=0)).output
    return {
        **brief.model_dump(mode="json"),
        "request_digest": payload["request_digest"],
        "workflow_id": workflow_id,
        "markdown": render_markdown(brief),
    }
