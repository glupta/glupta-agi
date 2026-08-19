from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

DISCLOSURE_NOTICE = "The selected source bytes and question will be sent to the OpenAI Responses API."  # noqa: E501
DISCLOSURE_NOTICE_DIGEST = hashlib.sha256(DISCLOSURE_NOTICE.encode()).hexdigest()


class EvidenceBriefRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=1, max_length=32_768)
    files: list[str] = Field(min_length=1, max_length=20)
    disclosure_profile: Literal["external_disclosed_v1"]
    disclosure_notice_digest: str = Field(pattern=f"^{DISCLOSURE_NOTICE_DIGEST}$")
    external_disclosure_ack: Literal[True]


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str
    line_start: StrictInt = Field(ge=1)
    line_end: StrictInt = Field(ge=1)
    quote: str = Field(min_length=1)


class EvidenceBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str = Field(min_length=1)
    citations: list[Citation]
    uncertainties: list[str]
    next_decisions: list[str]


def canonical_digest(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()
    return hashlib.sha256(encoded).hexdigest()


class ProviderAudit(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: str = "crawl-openai-audit-v2"
    workflow_id: str
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    release_profile_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    region: Literal["us", "europe"]
    endpoint: str
    price_schedule_id: str
    price_schedule_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    client_request_id: str
    provider_request_id: str
    response_id: str
    requested_model: str
    returned_model: str
    service_tier: Literal["default"]
    status: str
    input_tokens: StrictInt = Field(ge=0)
    cached_input_tokens: StrictInt = Field(ge=0)
    cache_write_input_tokens: StrictInt = Field(ge=0)
    output_tokens: StrictInt = Field(ge=0)
    reasoning_tokens: StrictInt = Field(ge=0)
    total_tokens: StrictInt = Field(ge=0)
    cost_upper_bound_micros: StrictInt = Field(ge=0)
    request_body_digest: str
    output_digest: str
    validated_result_digest: str | None = None
    record_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    started_at: datetime
    completed_at: datetime


def provider_record_digest(brief: EvidenceBrief, audit: ProviderAudit) -> str:
    audit_json = audit.model_dump(mode="json", exclude={"record_digest"})
    return canonical_digest({"result": brief.model_dump(mode="json"), "audit": audit_json})


class ProviderResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    brief: EvidenceBrief
    audit: ProviderAudit


def validate_provider_record(record: ProviderResult) -> ProviderResult:
    from . import inference

    result_digest = canonical_digest(record.brief.model_dump(mode="json"))
    audit = record.audit
    if (audit.validated_result_digest != result_digest
            or audit.record_digest != provider_record_digest(record.brief, audit)
            or audit.endpoint != inference.REGIONAL_ENDPOINTS[audit.region]
            or audit.price_schedule_id != inference.PRICE_SCHEDULE
            or audit.price_schedule_digest != inference.PRICE_SCHEDULE_DIGEST
            or audit.total_tokens != audit.input_tokens + audit.output_tokens
            or audit.cached_input_tokens + audit.cache_write_input_tokens > audit.input_tokens
            or audit.reasoning_tokens > audit.output_tokens
            or audit.cost_upper_bound_micros != inference.usd_upper_bound(audit.input_tokens,
                                                                 audit.output_tokens)):
        raise ValueError("provider result does not match its audit")
    return record


class EvidenceBriefResponse(EvidenceBrief):
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    workflow_id: str
    markdown: str
    provider_audit: ProviderAudit

    @model_validator(mode="after")
    def bound_provider_record(self) -> EvidenceBriefResponse:
        brief = EvidenceBrief(answer=self.answer, citations=self.citations,
                              uncertainties=self.uncertainties,
                              next_decisions=self.next_decisions)
        record = validate_provider_record(ProviderResult(brief=brief, audit=self.provider_audit))
        if (record.audit.workflow_id != self.workflow_id
                or record.audit.request_digest != self.request_digest):
            raise ValueError("provider audit does not match the public result")
        return self
