from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from glupta_agi.contracts import (
    EvidenceBrief,
    ProviderAudit,
    canonical_digest,
    provider_record_digest,
)
from glupta_agi.inference import (
    DISCLOSURE_PROFILE,
    PINNED_MODEL,
    PRICE_SCHEDULE,
    PRICE_SCHEDULE_DIGEST,
    ReleaseProfile,
)


def release_profile(**overrides: object) -> ReleaseProfile:
    digest = "a" * 64
    values: dict[str, object] = {
        "schema_version": "crawl-openai-release-v1",
        "disclosure_profile": DISCLOSURE_PROFILE,
        "provider": "openai",
        "product": "Responses API",
        "endpoint": "https://api.openai.com/v1",
        "account_class": "project_service_account",
        "project_id": "proj_crawl",
        "service_account_id": "svc_crawl",
        "api_key_id": "key_crawl",
        "credential_generation": 1,
        "credential_expires_at": "2099-01-01T00:00:00Z",
        "evidence_expires_at": "2099-01-01T00:00:00Z",
        "data_terms_digest": digest,
        "rights_evidence_digest": digest,
        "region": "global",
        "rate_limit_rpm": 1,
        "model": PINNED_MODEL,
        "max_input_tokens": 270_000,
        "max_output_tokens": 4_000,
        "max_reasoning_tokens": 4_000,
        "max_usd_micros": 1_850_000,
        "queue_timeout_seconds": 300,
        "wall_timeout_seconds": 300,
        "retry_owner": "dbos",
        "sdk_retries": 0,
        "store": False,
        "price_schedule_id": PRICE_SCHEDULE,
        "price_schedule_digest": PRICE_SCHEDULE_DIGEST,
        "manifest_digest": digest,
        "sbom_digest": digest,
        "provenance_digest": digest,
        "signature_digest": digest,
        "rollback_receipt_digest": digest,
        "approval_digest": digest,
    }
    values.update(overrides)
    return ReleaseProfile.model_validate(values)


def provider_audit(
    brief: EvidenceBrief | dict[str, object],
    *,
    workflow_id: str,
    request_digest: str,
    **overrides: object,
) -> ProviderAudit:
    result = EvidenceBrief.model_validate(brief)
    values: dict[str, object] = {
        "workflow_id": workflow_id,
        "request_digest": request_digest,
        "release_profile_digest": release_profile().digest(),
        "client_request_id": "client_1",
        "provider_request_id": "req_1",
        "response_id": "resp_1",
        "requested_model": PINNED_MODEL,
        "returned_model": PINNED_MODEL,
        "status": "completed",
        "input_tokens": 100,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 20,
        "reasoning_tokens": 5,
        "total_tokens": 120,
        "cost_upper_bound_micros": 1_100,
        "request_body_digest": "b" * 64,
        "output_digest": "c" * 64,
        "validated_result_digest": canonical_digest(result.model_dump(mode="json")),
        "started_at": datetime.now(UTC),
        "completed_at": datetime.now(UTC),
    }
    values.update(overrides)
    audit = ProviderAudit.model_validate(values)
    return audit.model_copy(update={"record_digest": provider_record_digest(result, audit)})


def private_file(root: Path, name: str, value: str) -> Path:
    path = root / name
    path.write_text(value, encoding="utf-8")
    path.chmod(0o600)
    return path


def write_profile(root: Path, profile: ReleaseProfile | None = None) -> Path:
    return private_file(
        root,
        "release-profile.json",
        json.dumps((profile or release_profile()).model_dump(mode="json")),
    )
