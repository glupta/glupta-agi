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
    ReleaseProfile,
)


def release_profile(**overrides: object) -> ReleaseProfile:
    digest = "a" * 64
    values: dict[str, object] = {
        "schema_version": "crawl-codex-subscription-release-v1",
        "disclosure_profile": DISCLOSURE_PROFILE,
        "provider": "openai",
        "product": "Codex subscription",
        "account_class": "chatgpt_subscription",
        "subscription_route_id": "crawl_subscription",
        "subscription_plan": "pro",
        "auth_generation": 1,
        "auth_evidence_digest": digest,
        "auth_expires_at": "2099-01-01T00:00:00Z",
        "evidence_expires_at": "2099-01-01T00:00:00Z",
        "data_terms_digest": digest,
        "rights_evidence_digest": digest,
        "model": PINNED_MODEL,
        "reasoning_effort": "medium",
        "max_input_bytes": 262_144,
        "max_observed_input_tokens": 270_000,
        "max_observed_output_tokens": 8_000,
        "max_observed_reasoning_tokens": 8_000,
        "max_calls": 1,
        "queue_timeout_seconds": 300,
        "wall_timeout_seconds": 300,
        "sdk_version": "0.147.0",
        "runtime_version": "0.147.0",
        "request_retries": 0,
        "stream_retries": 0,
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
        "subscription_route_id": "crawl_subscription",
        "subscription_plan": "pro",
        "sdk_version": "0.147.0",
        "runtime_version": "0.147.0",
        "thread_id": "thread_1",
        "turn_id": "turn_1",
        "requested_model": PINNED_MODEL,
        "reasoning_effort": "medium",
        "status": "completed",
        "input_tokens": 100,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 20,
        "reasoning_tokens": 5,
        "total_tokens": 120,
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


def codex_home(root: Path) -> Path:
    home = root / "codex-home"
    home.mkdir(mode=0o700)
    private_file(home, "auth.json", "synthetic-auth-metadata")
    return home


def write_profile(root: Path, profile: ReleaseProfile | None = None) -> Path:
    return private_file(
        root,
        "release-profile.json",
        json.dumps((profile or release_profile()).model_dump(mode="json")),
    )
