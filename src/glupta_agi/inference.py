"""Provider-neutral contracts for Crawl's single external model effect."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, StrictInt, model_validator

from .contracts import DISCLOSURE_NOTICE_DIGEST, ProviderResult, canonical_digest

DISCLOSURE_PROFILE, PINNED_MODEL = "external_disclosed_v1", "gpt-5.6-sol"
PRICE_SCHEDULE = "openai-gpt-5.6-sol-2026-08-18"
# Reserve the documented 1.25x cache-write premium for every input token.
INPUT_USD_MICROS_PER_MILLION, OUTPUT_USD_MICROS_PER_MILLION = 6_250_000, 30_000_000


PRICE_SCHEDULE_DIGEST = canonical_digest({"id": PRICE_SCHEDULE,
    "input_usd_micros_per_million": INPUT_USD_MICROS_PER_MILLION,
    "output_usd_micros_per_million": OUTPUT_USD_MICROS_PER_MILLION})


class ReleaseProfile(BaseModel):
    """Hash-bound non-secret evidence required before external dispatch."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: str
    disclosure_profile: str
    provider: str
    product: str
    endpoint: str
    account_class: str
    service_tier: Literal["default"]
    project_id: str = Field(pattern=r"^proj_[A-Za-z0-9_-]+$")
    service_account_id: str = Field(min_length=3, max_length=256)
    api_key_id: str = Field(min_length=3, max_length=256)
    credential_generation: StrictInt = Field(ge=1)
    credential_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    credential_expires_at: datetime
    evidence_expires_at: datetime
    data_terms_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rights_evidence_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    region: str = Field(min_length=2, max_length=64)
    rate_limit_rpm: StrictInt = Field(ge=1, le=60)
    model: str
    max_input_tokens: StrictInt
    max_output_tokens: StrictInt
    max_reasoning_tokens: StrictInt
    max_usd_micros: StrictInt
    queue_timeout_seconds: StrictInt
    wall_timeout_seconds: StrictInt
    retry_owner: str
    sdk_retries: StrictInt
    store: bool
    price_schedule_id: str
    price_schedule_digest: str
    manifest_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    sbom_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    provenance_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    signature_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    rollback_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def fixed_policy(self) -> ReleaseProfile:
        expected = {"schema_version": "crawl-openai-release-v1",
            "disclosure_profile": DISCLOSURE_PROFILE, "provider": "openai",
            "product": "Responses API", "endpoint": "https://api.openai.com/v1",
            "account_class": "project_service_account", "model": PINNED_MODEL,
            "max_input_tokens": 270_000, "max_output_tokens": 4_000,
            "max_reasoning_tokens": 4_000, "max_usd_micros": 1_850_000,
            "queue_timeout_seconds": 300, "wall_timeout_seconds": 300,
            "retry_owner": "dbos", "sdk_retries": 0, "store": False,
            "price_schedule_id": PRICE_SCHEDULE,
            "price_schedule_digest": PRICE_SCHEDULE_DIGEST}
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("release profile violates the frozen Crawl policy")
        if self.credential_expires_at.tzinfo is None or self.evidence_expires_at.tzinfo is None:
            raise ValueError("release evidence expiry must include timezone")
        return self

    def digest(self) -> str:
        return canonical_digest(self.model_dump(mode="json"))

    def current_at(self, now: datetime | None = None) -> bool:
        checked_at = now or datetime.now(UTC)
        return self.credential_expires_at > checked_at and self.evidence_expires_at > checked_at


class FrozenDispatch(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: str = "crawl-openai-dispatch-v1"
    workflow_id: str
    slot_id: str = "model-0"
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_body_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    release_profile_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    disclosure_profile: Literal["external_disclosed_v1"]
    disclosure_notice_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    external_disclosure_ack: Literal[True]
    service_tier: Literal["default"]
    project_id: str = Field(pattern=r"^proj_[A-Za-z0-9_-]+$")
    service_account_id: str = Field(min_length=3, max_length=256)
    api_key_id: str = Field(min_length=3, max_length=256)
    credential_generation: StrictInt = Field(ge=1)
    model: str = PINNED_MODEL
    input_token_upper_bound: StrictInt = Field(ge=1, le=270_000)
    max_output_tokens: StrictInt = 4_000
    max_usd_micros: StrictInt = 1_850_000
    queue_deadline: datetime
    wall_deadline: datetime
    wall_timeout_seconds: StrictInt = 300

    @model_validator(mode="after")
    def fixed_policy(self) -> FrozenDispatch:
        if (
            self.schema_version != "crawl-openai-dispatch-v1"
            or self.slot_id != "model-0"
            or self.disclosure_profile != DISCLOSURE_PROFILE
            or self.disclosure_notice_digest != DISCLOSURE_NOTICE_DIGEST
            or self.external_disclosure_ack is not True
            or self.model != PINNED_MODEL
            or self.max_output_tokens != 4_000
            or self.max_usd_micros != 1_850_000
            or self.wall_timeout_seconds != 300
            or self.queue_deadline.tzinfo is None
            or self.wall_deadline.tzinfo is None
            or self.queue_deadline != self.wall_deadline
        ):
            raise ValueError("dispatch violates the frozen Crawl policy")
        return self

    def digest(self) -> str:
        return canonical_digest(self.model_dump(mode="json"))


class InferencePort(Protocol):
    async def generate(self, dispatch: FrozenDispatch,
                       request_body: dict[str, Any]) -> ProviderResult: ...


def usd_upper_bound(input_tokens: int, output_tokens: int) -> int:
    numerator = input_tokens * INPUT_USD_MICROS_PER_MILLION + output_tokens * OUTPUT_USD_MICROS_PER_MILLION  # noqa: E501
    return (numerator + 999_999) // 1_000_000
