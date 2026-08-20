from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, StrictInt, model_validator

from .contracts import DISCLOSURE_NOTICE_DIGEST, ProviderResult, canonical_digest

DISCLOSURE_PROFILE = "external_disclosed_v1"
PINNED_MODEL, PINNED_EFFORT = "gpt-5.6-sol", "medium"
SDK_VERSION = RUNTIME_VERSION = "0.147.0"
ALLOWED_PLANS = frozenset({"plus", "pro", "prolite", "team", "business", "enterprise", "edu"})


class ReleaseProfile(BaseModel, extra="forbid", frozen=True):
    schema_version: Literal["crawl-codex-subscription-release-v1"]
    disclosure_profile: Literal["external_disclosed_v1"]
    provider: Literal["openai"]
    product: Literal["Codex subscription"]
    account_class: Literal["chatgpt_subscription"]
    subscription_route_id: str = Field(min_length=3, max_length=128)
    subscription_plan: str = Field(min_length=2, max_length=64)
    auth_generation: StrictInt = Field(ge=1)
    auth_evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    auth_expires_at: datetime
    evidence_expires_at: datetime
    data_terms_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rights_evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    model: Literal["gpt-5.6-sol"]
    reasoning_effort: Literal["medium"]
    max_input_bytes: StrictInt
    max_observed_input_tokens: StrictInt
    max_observed_output_tokens: StrictInt
    max_observed_reasoning_tokens: StrictInt
    max_calls: Literal[1]
    queue_timeout_seconds: StrictInt
    wall_timeout_seconds: StrictInt
    sdk_version: Literal["0.147.0"]
    runtime_version: Literal["0.147.0"]
    request_retries: Literal[0]
    stream_retries: Literal[0]
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    sbom_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    signature_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rollback_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def fixed_policy(self) -> ReleaseProfile:
        expected = (262_144, 270_000, 8_000, 8_000, 300, 300)
        observed = (self.max_input_bytes, self.max_observed_input_tokens,
                    self.max_observed_output_tokens, self.max_observed_reasoning_tokens,
                    self.queue_timeout_seconds, self.wall_timeout_seconds)
        if self.subscription_plan not in ALLOWED_PLANS or observed != expected:
            raise ValueError("release profile violates the frozen Crawl policy")
        if self.auth_expires_at.tzinfo is None or self.evidence_expires_at.tzinfo is None:
            raise ValueError("release evidence expiry must include timezone")
        return self

    def digest(self) -> str:
        return canonical_digest(self.model_dump(mode="json"))

    def current_at(self, now: datetime | None = None) -> bool:
        checked_at = now or datetime.now(UTC)
        return self.auth_expires_at > checked_at and self.evidence_expires_at > checked_at


class FrozenDispatch(BaseModel, extra="forbid", frozen=True):
    schema_version: Literal["crawl-codex-subscription-dispatch-v1"] = (
        "crawl-codex-subscription-dispatch-v1")
    workflow_id: str
    slot_id: Literal["model-0"] = "model-0"
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_body_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    release_profile_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    disclosure_profile: Literal["external_disclosed_v1"]
    disclosure_notice_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    external_disclosure_ack: Literal[True]
    subscription_route_id: str
    subscription_plan: str
    auth_generation: StrictInt = Field(ge=1)
    model: Literal["gpt-5.6-sol"]
    reasoning_effort: Literal["medium"]
    max_calls: Literal[1] = 1
    input_bytes: StrictInt = Field(ge=1, le=262_144)
    max_observed_input_tokens: StrictInt = 270_000
    max_observed_output_tokens: StrictInt = 8_000
    max_observed_reasoning_tokens: StrictInt = 8_000
    queue_deadline: datetime
    wall_deadline: datetime

    @model_validator(mode="after")
    def fixed_policy(self) -> FrozenDispatch:
        if (
            self.disclosure_notice_digest != DISCLOSURE_NOTICE_DIGEST
            or self.subscription_plan not in ALLOWED_PLANS
            or self.queue_deadline.tzinfo is None
            or self.wall_deadline.tzinfo is None
        ):
            raise ValueError("dispatch violates the frozen Crawl policy")
        return self

    def digest(self) -> str:
        return canonical_digest(self.model_dump(mode="json"))


class InferencePort(Protocol):
    async def generate(
        self, dispatch: FrozenDispatch, request_body: dict[str, Any]
    ) -> ProviderResult: ...
