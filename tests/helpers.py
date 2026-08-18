from __future__ import annotations

import json
from pathlib import Path

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
